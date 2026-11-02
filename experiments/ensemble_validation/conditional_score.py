"""Scores conditional on the already selected market; never selects the market."""
import math
import numpy as np
from score_distribution import intensities,log_probability

def compatible(h,a,sport,market,option,line=2.5):
    if sport=='basketball' and h==a:return False
    if market=='MS':
        return h>a if option==0 else (h==a if sport=='football' and option==1 else h<a)
    if market=='BTTS':return h>0 and a>0 if option==0 else h==0 or a==0
    if market=='OU':return h+a>line if option==0 else h+a<line
    raise ValueError('Unsupported market')

def football_score(mean,model,market,option,line=2.5):
    lh,la=intensities(mean);k=model['dispersion']
    sd=lambda l:math.sqrt(l+(l*l/k if k else 0))
    bounds=[max(40,math.ceil(l+16*sd(l)),math.ceil(line)+2 if market=='OU' else 0) for l in [lh,la]]
    # Includes effectively all marginal mass; conditions do not change the original density.
    probs=[]
    for l,n in zip([lh,la],bounds):
        p=np.empty(n+1);p[0]=math.exp(-l) if k is None else (k/(k+l))**k
        for g in range(1,n+1):p[g]=p[g-1]*l/g if k is None else p[g-1]*(g-1+k)/g*l/(k+l)
        probs.append(p)
    joint=probs[0][:,None]*probs[1][None,:]
    if k is None:
        rho=min(min(.95,.95/(lh*la)),max(-.95/max(lh,la),model['rho']))
        joint[0,0]*=1-lh*la*rho;joint[0,1]*=1+lh*rho;joint[1,0]*=1+la*rho;joint[1,1]*=1-rho
    h,a=np.indices(joint.shape)
    if market=='MS':mask=h>a if option==0 else h==a if option==1 else h<a
    elif market=='BTTS':mask=(h>0)&(a>0) if option==0 else (h==0)|(a==0)
    elif market=='OU':mask=h+a>line if option==0 else h+a<line
    else:raise ValueError('Unsupported market')
    mass=float(joint[mask].sum())
    if mass<=0:raise ValueError('Selected event has zero score probability')
    eligible=np.where(mask,joint,-1);flat=int(eligible.argmax());u,v=np.unravel_index(flat,joint.shape);p=float(joint[u,v])
    assert compatible(u,v,'football',market,option,line)
    return {'score':[int(u),int(v)],'probability':p,'conditionalProbability':p/mass,'conditionMass':mass,'method':'conditional_distribution'}

def basket_covariance(report):
    model=next((m for m in report.get('models',[]) if m['sport']=='basketball' and m['market']=='score'),None)
    matches=model.get('training',{}).get('matches',[]) if model else []
    if len(matches)<20:return [[1.,0.],[0.,1.]]
    assert all(r['date']<model['validationDate'] for r in matches)
    residual=np.array([r['actual'] for r in matches])-np.array([r['learned'] for r in matches])
    cov=np.cov(residual.T);cov=.9*cov+.1*np.diag(np.diag(cov))+np.eye(2)
    return cov.tolist()

def basketball_score(mean,covariance,market,option,line):
    if len(mean)!=2 or not all(math.isfinite(x) and 0<=x<=1000 for x in mean):raise ValueError('Invalid basketball score means')
    if market=='OU' and not (math.isfinite(line) and 0<line<=1000):raise ValueError('Invalid total line')
    cov=np.array(covariance,dtype=float);inverse=np.linalg.inv(cov)
    if not np.isfinite(inverse).all() or np.linalg.eigvalsh(cov).min()<=0:raise ValueError('Invalid residual covariance')
    bounds=[math.ceil(max(mu,line if market=='OU' else 0)+6*math.sqrt(cov[i,i]))+2 for i,mu in enumerate(mean)]
    h,a=np.indices((bounds[0]+1,bounds[1]+1));dh=h-mean[0];da=a-mean[1]
    distance=inverse[0,0]*dh*dh+2*inverse[0,1]*dh*da+inverse[1,1]*da*da
    if market=='MS':mask=h>a if option==0 else h<a
    elif market=='OU':mask=h+a>line if option==0 else h+a<line
    else:raise ValueError('Unsupported basketball market')
    mask&=h!=a;distance=np.where(mask,distance,np.inf);u,v=np.unravel_index(int(distance.argmin()),distance.shape)
    if not math.isfinite(distance[u,v]):raise ValueError('No compatible basketball score')
    assert compatible(u,v,'basketball',market,option,line)
    return {'score':[int(u),int(v)],'probability':None,'conditionalProbability':None,'conditionMass':None,'method':'conditional_residual_gaussian'}
