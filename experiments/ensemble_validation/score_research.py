"""Isolated football score research v1. Never modifies locked forecasts or model."""
import argparse,hashlib,html,json,math
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from conditional_score import compatible
from score_distribution import intensities,log_probability
from report import parse_score

VERSION='score-research-v1'
FIRST='2026-10-23'
SNAPSHOT='score-research-before-results.json'
JOURNAL='score-research-journal.json'
CANDIDATES=('locked','calibrated','overdispersed')
LABELS={'locked':'Mevcut dağılım','calibrated':'Düzeltilmiş gol beklentisi','overdispersed':'Geniş gol dağılımı'}
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def signature(v):return hashlib.sha256(json.dumps(v,sort_keys=True,allow_nan=False).encode()).hexdigest()
def valid_mean(v):return isinstance(v,list) and len(v)==2 and all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) and 0<=x<=12 for x in v)
def finished(row):
    value=parse_score({'scoreline':row.get('realScore')})
    return [int(x) for x in value] if value is not None else None
def baseline_rows(root):
    if not (root/'priced-before-results.json').exists():return []
    b=read(root/'priced-before-results.json');model=read(root/'stability-model.json')
    if b['modelSha256']!=sha(root/'stability-model.json'):raise ValueError('Model provenance mismatch')
    labels={str(r['eventId']):r for r in read(root/'football-replay.json') if r['date']==b['targetDate']}
    out=[]
    for e in b['systems']['football']['experiment']:
        r=labels.get(str(e['eventId']),{});c=e.get('chosen');mean=e.get('scoreMean')
        if not c or not valid_mean(mean):continue
        out.append({'date':b['targetDate'],'eventId':str(e['eventId']),'name':e['name'],'time':e.get('time',''),
                    'mean':mean,'chosen':c,'lockedScore':e.get('score'),
                    'distribution':model['payload']['footballDistribution'],
                    'originalBeforeKickoff':bool(e.get('prospectiveBeforeKickoff')),'actual':finished(r)})
    return out
def history(previous,target):
    if not previous or not previous.exists():return []
    records=read(previous/JOURNAL).get('records',[]) if (previous/JOURNAL).exists() else []
    merged={(r['date'],r['eventId']):r for r in records if r['date']<target}
    for r in baseline_rows(previous):
        if r['date']<target:merged[(r['date'],r['eventId'])]=r
    return sorted(merged.values(),key=lambda r:(r['date'],r['eventId']))
def fit(records,target):
    train=[r for r in records if r['date']<target and r.get('originalBeforeKickoff') and r.get('actual') is not None and valid_mean(r.get('mean'))]
    n=len(train)
    # Prespecified additive residual calibration with shrinkage; no same-day tuning.
    bias=[max(-1.,min(1.,sum(r['actual'][j]-r['mean'][j] for r in train)/(n+30))) if n>=30 else 0. for j in (0,1)]
    return {'bias':bias,'trainingCount':n,'trainingDates':sorted({r['date'] for r in train}),
            'active':n>=30,'minimumTrainingCount':30,'shrinkage':30,'maxAbsBias':1.,'dispersionCandidate':5}
def forecast(row,candidate,params):
    mean=intensities([x+(params['bias'][i] if candidate!='locked' else 0) for i,x in enumerate(row['mean'])])
    model=dict(row['distribution']) if candidate!='overdispersed' else {'dispersion':5,'rho':0}
    k=model['dispersion'];bounds=[max(40,math.ceil(x+16*math.sqrt(x+(x*x/k if k else 0)))) for x in mean]
    marg=[]
    for x,n in zip(mean,bounds):
        p=np.empty(n+1);p[0]=math.exp(-x) if k is None else (k/(k+x))**k
        for g in range(1,n+1):p[g]=p[g-1]*x/g if k is None else p[g-1]*(g-1+k)/g*x/(k+x)
        marg.append(p)
    joint=marg[0][:,None]*marg[1][None,:]
    if k is None:
        x,y=mean;rho=min(min(.95,.95/(x*y)),max(-.95/max(x,y),model['rho']))
        joint[0,0]*=1-x*y*rho;joint[0,1]*=1+x*rho;joint[1,0]*=1+y*rho;joint[1,1]*=1-rho
    h,a=np.indices(joint.shape);c=row['chosen'];m=c['market'];i=c['option']
    if m=='MS':mask=h>a if i==0 else h==a if i==1 else h<a
    elif m=='BTTS':mask=(h>0)&(a>0) if i==0 else (h==0)|(a==0)
    elif m=='OU':mask=h+a>2.5 if i==0 else h+a<2.5
    else:raise ValueError('Unknown market')
    mass=float(joint[mask].sum())
    indices=np.argsort(-np.where(mask,joint,-1).ravel(),kind='stable')[:3]
    top=[]
    for flat in indices:
        u,v=np.unravel_index(flat,joint.shape)
        if not mask[u,v]:continue
        top.append({'score':[int(u),int(v)],'probability':float(joint[u,v]),'conditionalProbability':float(joint[u,v]/mass)})
    return {'mean':mean,'distribution':model,'top3':top,'score':top[0]['score'],
            'zeroGoalProbability':float(joint[(h==0)|(a==0)].sum()),'fourPlusProbability':float(joint[h+a>=4].sum()),
            'conditionMass':mass}
def metrics(rows,candidate):
    pairs=[(r,r['candidates'][candidate]) for r in rows if r.get('actual') is not None]
    n=len(pairs)
    if not n:return {'count':0,'exactHits':0,'top3Hits':0,'exactAccuracy':None,'top3Accuracy':None,'teamMAE':None,'logLoss':None}
    return {'count':n,'exactHits':sum(r['actual']==p['score'] for r,p in pairs),
            'top3Hits':sum(any(r['actual']==a['score'] for a in p['top3']) for r,p in pairs),
            'exactAccuracy':sum(r['actual']==p['score'] for r,p in pairs)/n,
            'top3Accuracy':sum(any(r['actual']==a['score'] for a in p['top3']) for r,p in pairs)/n,
            'teamMAE':sum(sum(abs(x-y) for x,y in zip(r['actual'],p['score']))/2 for r,p in pairs)/n,
            'logLoss':-sum(log_probability(r['actual'],p['mean'],p['distribution']) for r,p in pairs)/n,
            'zeroGoalBrier':sum((p['zeroGoalProbability']-int(0 in r['actual']))**2 for r,p in pairs)/n,
            'fourPlusBrier':sum((p['fourPlusProbability']-int(sum(r['actual'])>=4))**2 for r,p in pairs)/n}
def blocks(rows):
    subsets={'all':rows,'zeroGoal':[r for r in rows if r.get('actual') is not None and 0 in r['actual']],
             'fourPlus':[r for r in rows if r.get('actual') is not None and sum(r['actual'])>=4]}
    return {name:{c:metrics(rs,c) for c in CANDIDATES} for name,rs in subsets.items()}
def diagnostics(rows):
    result={}
    for c in CANDIDATES:
        ps=[r['candidates'][c] for r in rows];counts={}
        for p in ps:
            s='-'.join(map(str,p['score']));counts[s]=counts.get(s,0)+1
        result[c]={'count':len(ps),'modalScoreCounts':counts,
                   'meanGoals':np.mean([p['mean'] for p in ps],axis=0).tolist() if ps else None,
                   'betweenMatchGoalStd':np.std([p['mean'] for p in ps],axis=0).tolist() if ps else None}
    return result
def retrospective(records):
    out=[]
    for day in sorted({r['date'] for r in records}):
        params=fit(records,day)
        for r in records:
            if r['date']==day and r.get('originalBeforeKickoff') and r.get('actual') is not None:
                out.append(dict(r,candidates={c:forecast(r,c,params) for c in CANDIDATES}))
    return {'policy':'Retrospective walk-forward; not independent success','metrics':blocks(out)}
def freeze(root,previous=None,now=None):
    path=root/SNAPSHOT
    if path.exists():
        b=read(path)
        if b['version']!=VERSION or b['sourceSha256']!=sha(root/'priced-before-results.json') or b['modelSha256']!=sha(root/'stability-model.json'):raise ValueError('Research source mismatch')
        if b['snapshotSha256']!=signature({k:v for k,v in b.items() if k!='snapshotSha256'}):raise ValueError('Research snapshot changed')
        return b
    source=read(root/'priced-before-results.json');target=source['targetDate']
    now=now or datetime.now(timezone.utc);records=history(previous,target);params=fit(records,target);rows=[]
    source_rows=baseline_rows(root)
    for r in source_rows:
        r=dict(r);r.pop('actual',None)
        try:before=now<datetime.fromisoformat(target+'T'+r['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
        except (ValueError,TypeError):before=False
        r['beforeKickoff']=bool(target>=FIRST and r['originalBeforeKickoff'] and before)
        r['candidates']={c:forecast(r,c,params) for c in CANDIDATES}
        if r.get('lockedScore')!=r['candidates']['locked']['score']:raise ValueError('Research baseline differs from frozen displayed score')
        rows.append(r)
    b={'version':VERSION,'targetDate':target,'firstIndependentDate':FIRST,'createdAt':now.isoformat(),
       'sourceSha256':sha(root/'priced-before-results.json'),'modelSha256':sha(root/'stability-model.json'),
       'parameters':params,'trainingDataSha256':signature(records),'rows':rows,
       'excludedFixtures':len(source['systems']['football']['experiment'])-len(rows),'retrospective':retrospective(records)}
    b['snapshotSha256']=signature(b);write(path,b);write(root/JOURNAL,{'version':VERSION,'records':records})
    return b
def settle(root):
    if not (root/SNAPSHOT).exists():return None
    b=freeze(root);labels={str(r['eventId']):r for r in read(root/'football-replay.json') if r['date']==b['targetDate']}
    rows=[dict(r,actual=finished(labels.get(r['eventId'],{}))) for r in b['rows']]
    journal=read(root/JOURNAL) if (root/JOURNAL).exists() else {'version':VERSION,'records':[]}
    records={(r['date'],r['eventId']):r for r in journal['records']}
    for r in baseline_rows(root):records[(r['date'],r['eventId'])]=r
    write(root/JOURNAL,{'version':VERSION,'records':list(records.values())})
    prospective=[r for r in rows if r['beforeKickoff']]
    result={'version':VERSION,'targetDate':b['targetDate'],'firstIndependentDate':FIRST,'snapshotSha256':b['snapshotSha256'],
            'updatedAt':datetime.now(timezone.utc).isoformat(),'parameters':b['parameters'],'excludedFixtures':b['excludedFixtures'],
            'recorded':len(rows),'beforeKickoffRecorded':len(prospective),'lateOrPreview':len(rows)-len(prospective),
            'pending':sum(r['actual'] is None for r in rows),'concentration':diagnostics(rows),
            'beforeKickoff':blocks(prospective),'allIncludingLate':blocks(rows),'retrospective':b['retrospective']}
    write(root/'score-research-evaluation.json',result);render(root,b,rows,result);return result
def render(root,book,rows,result):
    esc=lambda s:html.escape(str(s))
    score=lambda s:'-'.join(map(str,s)) if s is not None else '—'
    cells=[]
    for r in sorted(rows,key=lambda r:(r['time'],r['eventId'])):
        c=r['chosen'];label={'MS':['MS1','MSX','MS2'],'BTTS':['KG Var','KG Yok'],'OU':['2.5 Üst','2.5 Alt']}[c['market']][c['option']]
        forecasts=''.join('<div><small>'+LABELS[name]+'</small><b>'+score(r['candidates'][name]['score'])+'</b><span>'+esc(' · '.join(score(a['score'])+' (%'+format(100*a['probability'],'.1f')+')' for a in r['candidates'][name]['top3']))+'</span></div>' for name in CANDIDATES)
        cells.append('<article data-search="'+esc(r['name'])+'"><h2>'+esc(r['time']+' '+r['name'])+'</h2><p>'+esc(label)+' · '+('Maç öncesi' if r['beforeKickoff'] else 'Geç kayıt / hazırlık')+' · Gerçek skor: <b>'+score(r['actual'])+'</b></p><section>'+forecasts+'</section></article>')
    def panel(title,data):
        body=''
        for name in CANDIDATES:
            m=data['all'][name];fmt=lambda v:'—' if v is None else format(v,'.3f')
            body+='<tr><td>'+LABELS[name]+'</td><td>'+str(m['count'])+'</td><td>'+str(m['exactHits'])+'</td><td>'+str(m['top3Hits'])+'</td><td>'+fmt(m['teamMAE'])+'</td><td>'+fmt(m['logLoss'])+'</td></tr>'
        return '<h2>'+title+'</h2><div class="scroll"><table><tr><th>Yöntem</th><th>N</th><th>Tam skor</th><th>İlk 3</th><th>MAE ↓</th><th>Log loss ↓</th></tr>'+body+'</table></div>'
    doc='<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Futbol Skor Deneyi · '+book['targetDate']+'</title><style>body{font:16px system-ui;background:#eff3f8;color:#18344b;margin:0;padding:16px}main{max-width:1100px;margin:auto}h1{background:#15334d;color:white;padding:24px;border-radius:18px}article{background:white;padding:16px;border-radius:14px;margin:14px 0}h2{font-size:18px}section{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}section div{background:#f2f7fa;padding:12px;border-radius:10px}small,span,b{display:block}b{font-size:22px}span,small{font-size:13px}input{font:inherit;padding:12px;width:100%;box-sizing:border-box}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;background:white}th,td{padding:10px;border-bottom:1px solid #ccd7e0;text-align:left}p{line-height:1.6}[hidden]{display:none!important}@media(max-width:650px){section{grid-template-columns:1fr}section div{display:grid;grid-template-columns:1fr auto}section span{grid-column:1/-1}}</style><main><h1>Futbol Skor Deneyi · '+book['targetDate']+'</h1><p>Ayrı araştırma: score-research-v1. Bağımsız başlangıç 23 Ekim 2026. Ana model ve bahis tercihleri değişmez. Kontroller kayıtlı skorları yeniden hesaplamaz.</p><p>Son değerlendirme: '+esc(result['updatedAt'])+' · Bekleyen: '+str(result['pending'])+' · Eksik oran/girdi nedeniyle dışarıda: '+str(result['excludedFixtures'])+'</p><p>Gol düzeltmesinin geçmiş örnek sayısı: '+str(book['parameters']['trainingCount'])+'. En az 30 örnek yoksa düzeltme uygulanmaz. Yüzdeler tam skorun koşulsuz olasılığıdır; bahsin güveni değildir. İlk üç skor bahisle uyumludur. Log loss tüm gerçek skorları değerlendirir.</p>'+panel('Bağımsız maç öncesi ölçüm',result['beforeKickoff'])+panel('En az bir takımın gol atamadığı maçlar',{'all':result['beforeKickoff']['zeroGoal']})+panel('Toplam 4+ gollü maçlar',{'all':result['beforeKickoff']['fourPlus']})+'<details><summary>Geç kayıtlar dahil — keşif amaçlı</summary>'+panel('Bağımsız başarı sayılmaz',result['allIncludingLate'])+'</details><details><summary>Geçmiş gün gün test — geriye dönük</summary>'+panel('Her gün yalnız önceki günlerle ayarlandı',result['retrospective']['metrics'])+'</details><h2>Maçlar</h2><input type="search" id="q" placeholder="Takım / maç ara" aria-label="Maç ara">'+''.join(cells)+'</main><script>const norm=s=>s.replace(/ı/g,"i").normalize("NFD").replace(/[\\u0300-\\u036f]/g,"").toLowerCase();document.getElementById("q").addEventListener("input",e=>{const terms=norm(e.target.value).split(/\\s+/).filter(Boolean);document.querySelectorAll("article").forEach(r=>r.hidden=!terms.every(t=>norm(r.dataset.search).includes(t)))});</script></html>'
    (root/'futbol-skor-deneyi.html').write_text(doc)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path);a=p.parse_args()
    if a.mode=='freeze':freeze(a.output,a.previous)
    else:settle(a.output)

