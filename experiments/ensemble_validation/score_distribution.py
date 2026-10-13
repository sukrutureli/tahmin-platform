"""Football exact-score distributions, selected on prior validation only.

Mean-goal regressions remain immutable. A separate snapshot stores a modal score,
its probability and alternatives; this is not the same objective as mean-score MAE.
"""
import argparse,hashlib,json,math
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from prepare import dump
from report import parse_score,page,table
from outcome_learning import score_metrics

CANDIDATES=[{'dispersion':None,'rho':r} for r in [-.2,-.1,0,.1,.2]]+[
    {'dispersion':k,'rho':0} for k in [5,10,20]]

def intensities(mean):
    if len(mean)!=2 or not all(math.isfinite(x) for x in mean):raise ValueError('Invalid goal means')
    return [min(12,max(.05,float(x))) for x in mean]

def log_probability(score,mean,model):
    lh,la=intensities(mean);h,a=score
    if h<0 or a<0 or int(h)!=h or int(a)!=a:raise ValueError('Scores must be nonnegative integers')
    k=model['dispersion']
    if k is not None:
        return sum(math.lgamma(g+k)-math.lgamma(k)-math.lgamma(g+1)+k*math.log(k/(k+l))+g*math.log(l/(k+l)) for g,l in [(h,lh),(a,la)])
    rho=min(min(.95,.95/(lh*la)),max(-.95/max(lh,la),model['rho']))
    tau={(0,0):1-lh*la*rho,(0,1):1+lh*rho,(1,0):1+la*rho,(1,1):1-rho}.get((h,a),1)
    return -lh-la+h*math.log(lh)+a*math.log(la)-math.lgamma(h+1)-math.lgamma(a+1)+math.log(tau)

def forecast(mean,model):
    lh,la=intensities(mean)
    # Marginal modes are <= mean; the dependence adjustment changes only 0/1 cells.
    candidates=[(log_probability((h,a),mean,model),h,a) for h in range(max(3,math.ceil(lh)+2)) for a in range(max(3,math.ceil(la)+2))]
    ranked=sorted(candidates,key=lambda v:(-v[0],v[1],v[2]))
    best=ranked[0]
    return {'score':[best[1],best[2]],'scoreline':f'{best[1]}-{best[2]}','probability':math.exp(best[0]),
            'alternatives':[{'scoreline':f'{h}-{a}','probability':math.exp(p)} for p,h,a in ranked[:3]]}

def measure(matches,model):
    if not matches:return None
    actual=[m['actual'] for m in matches];means=[m['learned'] for m in matches]
    pred=[forecast(mu,model)['score'] for mu in means];old=np.rint(means).astype(int).tolist()
    counts=Counter(tuple(p) for p in pred)
    return {'count':len(matches),'exactHits':sum(list(y)==p for y,p in zip(actual,pred)),
            'exactAccuracy':sum(list(y)==p for y,p in zip(actual,pred))/len(matches),
            'roundedMeanExactHits':sum(list(y)==p for y,p in zip(actual,old)),
            'modalScore':score_metrics(actual,pred),'roundedMeanScore':score_metrics(actual,old),
            'meanGoalScore':score_metrics(actual,means),'jointLogLoss':-sum(log_probability(y,mu,model) for y,mu in zip(actual,means))/len(matches),
            'distinctPredictedScores':len(counts),'mostCommonScore':list(counts.most_common(1)[0][0]),'mostCommonScoreCount':counts.most_common(1)[0][1]}

def learn(report):
    source=next(m for m in report['models'] if m['sport']=='football' and m['market']=='score')
    if not source.get('model'):return {'targetDate':report['targetDate'],'model':None,'status':'score mean model unavailable'}
    assert source['validationDate']<source['untouchedTestDate']<report['targetDate']
    assert all(m['date']==source['validationDate'] for m in source['validation']['matches'])
    assert all(m['date']==source['untouchedTestDate'] for m in source['test']['matches'])
    candidates=[{'model':m,'validation':measure(source['validation']['matches'],m)} for m in CANDIDATES]
    chosen=min(candidates,key=lambda c:c['validation']['jointLogLoss'])['model']
    return {'targetDate':report['targetDate'],'model':chosen,'meanTrainingDates':source['trainingDates'],
            'forecastMeanTrainingDates':source['forecastTrainingDates'],'validationDate':source['validationDate'],
            'untouchedTestDate':source['untouchedTestDate'],'selectionObjective':'Prior-validation joint score log loss; test results do not select model. Modal score targets exact-score probability, mean remains available for MAE.',
            'candidates':candidates,'validation':measure(source['validation']['matches'],chosen),'test':measure(source['test']['matches'],chosen)}

def freeze(output,data,previous=None):
    source=output/'learned-before-results.json';book=json.loads(source.read_text());digest=hashlib.sha256(source.read_bytes()).hexdigest()
    old=previous/'score-before-results.json' if previous else None
    if old and old.exists() and json.loads(old.read_text())['targetDate']==book['targetDate']:
        assert json.loads(old.read_text())['meanForecastSha256']==digest
        (output/'score-before-results.json').write_bytes(old.read_bytes())
        for name in ['score-distribution.json','score-distribution.html']:
            if (previous/name).exists():(output/name).write_bytes((previous/name).read_bytes())
        return
    model=learn(json.loads((output/'outcome-learning.json').read_text()));dump(output/'score-distribution.json',model)
    now=datetime.now(timezone.utc);times={(r['date'],str(r['eventId'])):r.get('time') for r in data['football']}
    saved={'targetDate':book['targetDate'],'createdAt':now.isoformat(),'meanForecastSha256':digest,'model':model['model'],'predictions':[],'status':'Separate modal-score experiment; original forecasts unchanged'}
    for e in book['predictions']:
        if e['sport']!='football' or e.get('score') is None or not model['model']:continue
        f=forecast(e['score'],model['model'])
        try:before=e['prospectiveBeforeKickoff'] and now<datetime.fromisoformat(e['date']+'T'+times[(e['date'],str(e['eventId']))]).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
        except (KeyError,TypeError,ValueError):before=False
        saved['predictions'].append(dict(f,sport='football',date=e['date'],eventId=str(e['eventId']),name=e['name'],meanGoals=e['score'],prospectiveBeforeKickoff=before))
    dump(output/'score-before-results.json',saved)
    lines=[]
    for split in ['validation','test']:
        if model.get(split):
            r=model[split];lines.append((split,r['count'],r['roundedMeanExactHits'],r['exactHits'],f"{r['roundedMeanScore']['teamMAE']:.3f} → {r['modalScore']['teamMAE']:.3f}",f"{r['jointLogLoss']:.3f}"))
    body='<p>Futbol skorunda ortalamayı yuvarlamak yerine skor dağılımının en olası hücresi gösterilir. Poisson, düşük-skor bağımlılığı ve negatif binom adayları yalnız önceki doğrulama gününden seçilir. Basketbolun mevcut skor modeli korunur. Tam skor isabeti ile ortalama hata farklı hedeflerdir; modal skor daha yüksek MAE verebilir. Mevcut günün yeni skor kayıtları sonuçlardan sonra üretildiyse araştırmadır.</p>'+table(['Dönem','N','Yuvarlanan ortalama tam isabet','Yeni tam isabet','MAE eski → yeni','Dağılım log loss'],lines)
    body+=table(['Maç','Yeni en olası skor','Bu skorun olasılığı','Alternatifler','Önceki ortalama beklenti'],[(e['name'],e['scoreline'],f"%{100*e['probability']:.1f}",', '.join(f"{x['scoreline']} (%{100*x['probability']:.1f})" for x in e['alternatives']),f"{e['meanGoals'][0]:.2f}–{e['meanGoals'][1]:.2f}") for e in saved['predictions']])
    (output/'score-distribution.html').write_text(page('Skor dağılımı deneyi',body))

def settle(output,data):
    saved=json.loads((output/'score-before-results.json').read_text());assert hashlib.sha256((output/'learned-before-results.json').read_bytes()).hexdigest()==saved['meanForecastSha256']
    labels={(r['date'],str(r['eventId'])):parse_score({'scoreline':r.get('realScore')}) for r in data['football']}
    report={'targetDate':saved['targetDate'],'createdAt':saved['createdAt'],'status':'Frozen-score settlement; late forecasts are retrospective'}
    for name,es in [('all',saved['predictions']),('prospective',[e for e in saved['predictions'] if e['prospectiveBeforeKickoff']])]:
        matches=[{'actual':labels[(e['date'],e['eventId'])],'learned':e['meanGoals']} for e in es if labels.get((e['date'],e['eventId'])) is not None]
        report[name]=measure(matches,saved['model']) if saved['model'] else None
    dump(output/'score-distribution-evaluation.json',report)

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path);a=p.parse_args()
    data={s:json.loads((a.output/(s+'-replay.json')).read_text()) for s in ['football','basketball']}
    if a.mode=='freeze':freeze(a.output,data,a.previous)
    else:settle(a.output,data)
if __name__=='__main__':main()
