"""Learn scores and market probabilities from real outcomes; main is evaluation only."""
import argparse, hashlib, json, math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from mine_rules import predictors
from prepare import dump
from report import BASE,GROUPS,metrics,result,candidate_vector,parse_score,page,table

HISTORY=['attackDefenceDiff','expectedTotal','minimumHistory','totalSigma','winRateDifference','formTrendDifference',
         'venueMarginDifference','venueExpectedTotal','meanBlankRate','meanBttsRate','meanOverRate',
         'expectedTotalMinusLine','recentVsWideMarginDifference','wideMinimumCount','absoluteStrengthDifference',
         'homeFor','homeAgainst','awayFor','awayAgainst']
ODDS=['marketHome','marketDraw','marketAway','marketOver','marketBtts','msOverround','ouOverround','bttsOverround','totalLine']
MODES={'history':HISTORY,'odds':ODDS,'history+odds':HISTORY+ODDS}
PENALTIES=(.1,1.,10.)


def features(row,sport):
    f=predictors(row,sport)
    if 'attackDefenceDiff' in f:f['absoluteStrengthDifference']=abs(f['attackDefenceDiff'])
    a=row.get('variants',{}).get('six-simple',{}).get('audit',{})
    for side,prefix in [('home','home'),('away','away')]:
        rows=a.get(side,{}).get('rows',[])
        if rows:
            f[prefix+'For']=sum(r['for'] for r in rows)/len(rows)
            f[prefix+'Against']=sum(r['against'] for r in rows)/len(rows)
    odds=row.get('odds',{})
    def market(keys,names,margin):
        vals=[odds.get(k) for k in keys]
        if all(isinstance(v,(int,float)) and math.isfinite(v) and v>1 for v in vals):
            inv=[1/v for v in vals];total=sum(inv)
            f.update(zip(names,[v/total for v in inv]));f[margin]=total-1
    market(['ms1','msX','ms2'] if sport=='football' else ['ms1','ms2'],
           ['marketHome','marketDraw','marketAway'] if sport=='football' else ['marketHome','marketAway'],'msOverround')
    market(['over25','under25'] if sport=='football' else ['over','under'],['marketOver','marketUnder'],'ouOverround')
    if sport=='football':market(['bttsYes','bttsNo'],['marketBtts','marketNoBtts'],'bttsOverround')
    else:
        line=odds.get('hOverUnderValue',0)
        if isinstance(line,(int,float)) and line>0:f['totalLine']=line
    return f


def fit_transform(values,keys):
    raw=np.array([[f.get(k,np.nan) for k in keys] for f in values],dtype=float)
    med=np.array([float(np.median(raw[np.isfinite(raw[:,i]),i])) if np.any(np.isfinite(raw[:,i])) else 0 for i in range(len(keys))])
    filled=np.where(np.isfinite(raw),raw,med);mean=filled.mean(axis=0);scale=filled.std(axis=0);scale[scale<1e-9]=1
    transform={'keys':keys,'median':med.tolist(),'mean':mean.tolist(),'scale':scale.tolist()}
    return transform,transform_values(values,transform)


def transform_values(values,t):
    raw=np.array([[f.get(k,np.nan) for k in t['keys']] for f in values],dtype=float).reshape(-1,len(t['keys']))
    missing=~np.isfinite(raw);filled=np.where(missing,t['median'],raw)
    z=(filled-np.array(t['mean']))/np.array(t['scale'])
    return np.column_stack([np.ones(len(raw)),z,missing.astype(float)])


def softmax(x):
    z=x-x.max(axis=1,keepdims=True);p=np.exp(z);return p/p.sum(axis=1,keepdims=True)


def fit_classifier(x,y,k,penalty):
    # Convex multinomial likelihood + L2; intercept remains unpenalized.
    w=np.zeros((x.shape[1],k));target=np.eye(k)[y]
    strength=penalty/len(x)
    step=1/(.5*np.linalg.norm(x,2)**2/len(x)+strength+1e-9)
    for _ in range(600):
        grad=x.T@(softmax(x@w)-target)/len(x)
        grad[1:]+=strength*w[1:]
        w-=step*grad
    return w


def fit_score(x,y,penalty):
    regularizer=np.eye(x.shape[1])*penalty;regularizer[0,0]=0
    return np.linalg.solve(x.T@x+regularizer,x.T@y)


def samples(rows,sport,market,target):
    items=[]
    for row in rows:
        if row['date']>=target:continue
        y=parse_score({'scoreline':row.get('realScore')}) if market=='score' else result(row,sport,market)
        if y is not None:items.append({'row':row,'f':features(row,sport),'y':y})
    return items


def score_metrics(actual,predicted):
    if len(actual)==0:return None
    errors=np.asarray(predicted)-np.asarray(actual)
    return {'count':len(actual),'teamMAE':float(np.abs(errors).mean()),'teamRMSE':float(np.sqrt((errors**2).mean())),
            'totalMAE':float(np.abs(errors.sum(axis=1)).mean()),'marginMAE':float(np.abs(errors[:,0]-errors[:,1]).mean())}


def evaluate(group,sport,market,model):
    if not group:return {'count':0,'learned':None,'main':None,'matches':[]}
    x=transform_values([r['f'] for r in group],model['transform']);w=np.array(model['weights'])
    predictions=np.maximum(0,x@w) if market=='score' else softmax(x@w)
    if market=='score':
        own=score_metrics([r['y'] for r in group],predictions)
        paired=[(i,parse_score(r['row']['variants']['legacy']['models'][BASE[sport]])) for i,r in enumerate(group)]
        paired=[(i,y) for i,y in paired if y is not None]
        base=score_metrics([group[i]['y'] for i,y in paired],[y for i,y in paired]) if paired else None
        main_paired_own=score_metrics([group[i]['y'] for i,y in paired],[predictions[i] for i,y in paired]) if paired else None
    else:
        own=metrics([(p.tolist(),r['y']) for p,r in zip(predictions,group)],GROUPS[sport][market])
        paired=[(i,candidate_vector(r['row'],sport,market,('legacy',BASE[sport],0))) for i,r in enumerate(group)]
        paired=[(i,p) for i,p in paired if p is not None]
        base=metrics([(p,group[i]['y']) for i,p in paired],GROUPS[sport][market])
        main_paired_own=metrics([(predictions[i].tolist(),group[i]['y']) for i,p in paired],GROUPS[sport][market])
    return {'count':len(group),'learned':own,'main':base,'learnedOnMainCohort':main_paired_own,
            'matches':[{'date':r['row']['date'],'eventId':r['row']['eventId'],'name':r['row']['name'],
                        'actual':r['y'],'learned':p.tolist()} for r,p in zip(group,predictions)]}


def learn(rows,sport,market,target):
    items=samples(rows,sport,market,target);dates=sorted({r['row']['date'] for r in items})
    if len(dates)<4:return {'sport':sport,'market':market,'status':'insufficient dates','model':None}
    td=dates[-1];validation_dates=[dates[-2]]
    # Sparse days may pool earlier validation dates; never borrow the untouched test day.
    for d in reversed(dates[:-2]):
        if sum(r['row']['date'] in validation_dates for r in items)>=20:break
        validation_dates.insert(0,d)
    vd=validation_dates[0];train=[r for r in items if r['row']['date']<vd]
    val=[r for r in items if r['row']['date'] in validation_dates];test=[r for r in items if r['row']['date']==td]
    if len(train)<80 or len(val)<20:return {'sport':sport,'market':market,'status':'insufficient train/validation samples','model':None}
    candidates=[];ablations=[]
    for mode,keys in MODES.items():
        t,x=fit_transform([r['f'] for r in train],keys);y=np.array([r['y'] for r in train])
        for penalty in PENALTIES:
            w=fit_score(x,y,penalty) if market=='score' else fit_classifier(x,y,len(GROUPS[sport][market]),penalty)
            model={'mode':mode,'penalty':penalty,'transform':t,'weights':w.tolist()}
            measured=evaluate(val,sport,market,model)['learned'];loss=measured['teamMAE'] if market=='score' else measured['logLoss']
            candidates.append((loss,mode,penalty,model));ablations.append({'mode':mode,'penalty':penalty,'validation':measured})
    chosen=min(candidates,key=lambda x:x[:3])[3]
    # Main metrics are calculated only after the outcome-driven choice is final.
    w=np.array(chosen['weights']);names=['intercept']+chosen['transform']['keys']+['missing:'+k for k in chosen['transform']['keys']]
    important=sorted([(float(np.linalg.norm(w[i])),names[i],w[i].tolist()) for i in range(1,len(names))],reverse=True)[:12]
    # Only after immutable test evaluation: refit chosen settings on completed past rows for future forecasts.
    ft,fx=fit_transform([r['f'] for r in items],MODES[chosen['mode']]);fy=np.array([r['y'] for r in items])
    fw=fit_score(fx,fy,chosen['penalty']) if market=='score' else fit_classifier(fx,fy,len(GROUPS[sport][market]),chosen['penalty'])
    future_model={'mode':chosen['mode'],'penalty':chosen['penalty'],'transform':ft,'weights':fw.tolist()}
    return {'sport':sport,'market':market,'status':'retrospective development; prospective validation required','model':chosen,'forecastModel':future_model,'forecastTrainingDates':dates,
            'trainingDates':[d for d in dates if d<vd],'validationDate':vd,'validationDates':validation_dates,'untouchedTestDate':td,'ablations':ablations,
            'coefficients':[{'feature':name,'standardizedWeights':values} for size,name,values in important],
            'training':evaluate(train,sport,market,chosen),'validation':evaluate(val,sport,market,chosen),'test':evaluate(test,sport,market,chosen)}


def freeze(output,data,report,previous=None):
    from zoneinfo import ZoneInfo
    old=previous/'learned-before-results.json' if previous else None
    if old and old.exists() and json.loads(old.read_text()).get('targetDate')==report['targetDate']:
        (output/'learned-before-results.json').write_bytes(old.read_bytes());return
    now=datetime.now(timezone.utc);book={'targetDate':report['targetDate'],'createdAt':now.isoformat(),'status':'independent outcome model shadow','predictions':[]}
    models={(m['sport'],m['market']):m.get('forecastModel',m['model']) for m in report['models']}
    for sport,rows in data.items():
        for r in rows:
            if r['date']!=report['targetDate']:continue
            f=features(r,sport)
            try:prospective=now<datetime.fromisoformat(r['date']+'T'+r['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
            except (ValueError,KeyError):prospective=False
            e={'sport':sport,'date':r['date'],'eventId':r['eventId'],'name':r['name'],'prospectiveBeforeKickoff':prospective,'markets':{},'score':None,'baselineMarkets':{market:candidate_vector(r,sport,market,('legacy',BASE[sport],0)) for market in GROUPS[sport]},'baselineScore':parse_score(r['variants']['legacy']['models'][BASE[sport]])}
            for market in list(GROUPS[sport])+['score']:
                m=models.get((sport,market))
                if not m:continue
                x=transform_values([f],m['transform']);v=x@np.array(m['weights'])
                if market=='score':e['score']=np.maximum(0,v)[0].tolist()
                else:e['markets'][market]=softmax(v)[0].tolist()
            book['predictions'].append(e)
    dump(output/'learned-before-results.json',book)


def settle(output,data,target):
    book=json.loads((output/'learned-before-results.json').read_text());assert book['targetDate']==target
    labels={(s,r['date'],str(r['eventId'])):r for s,rows in data.items() for r in rows}
    report={'targetDate':target,'markets':[],'scores':[],'status':'saved forecast settlement; late records are retrospective'}
    for sport in BASE:
        entries=[e for e in book['predictions'] if e['sport']==sport]
        for market,names in GROUPS[sport].items():
            samples=[]
            for e in entries:
                r=labels.get((sport,e['date'],str(e['eventId'])));y=result(r,sport,market) if r else None
                p=e['markets'].get(market);b=e['baselineMarkets'].get(market)
                if y is not None and p is not None and b is not None:samples.append((e,b,p,y))
            m={'sport':sport,'market':market}
            for name,items in [('all',samples),('prospective',[x for x in samples if x[0]['prospectiveBeforeKickoff']])]:
                m[name]={'main':metrics([(b,y) for e,b,p,y in items],names),'learned':metrics([(p,y) for e,b,p,y in items],names)}
            report['markets'].append(m)
        pairs=[]
        for e in entries:
            r=labels.get((sport,e['date'],str(e['eventId'])));y=parse_score({'scoreline':r.get('realScore')}) if r else None
            if y is not None and e['score'] is not None and e['baselineScore'] is not None:pairs.append((e,y))
        for name,items in [('all',pairs),('prospective',[x for x in pairs if x[0]['prospectiveBeforeKickoff']])]:
            report['scores'].append({'sport':sport,'cohort':name,'main':score_metrics([y for e,y in items],[e['baselineScore'] for e,y in items]),'learned':score_metrics([y for e,y in items],[e['score'] for e,y in items])})
    dump(output/'learned-daily-evaluation.json',report)

def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--target-date',required=True);p.add_argument('--previous',type=Path);p.add_argument('--settle',action='store_true');a=p.parse_args()
    data=json.loads(a.dataset.read_text())
    if a.settle:
        settle(a.output,data,a.target_date)
        return
    report={'targetDate':a.target_date,'createdAt':datetime.now(timezone.utc).isoformat(),'datasetSha256':hashlib.sha256(a.dataset.read_bytes()).hexdigest(),
            'policy':'Train on actual outcomes only; initial saved odds only; train-only preprocessing; validation-only hyperparameters; untouched chronological test. Main is evaluation only. Coefficients are associations, not causal importance.',
            'models':[learn(data[s],s,m,a.target_date) for s in BASE for m in list(GROUPS[s])+['score']]}
    dump(a.output/'outcome-learning.json',report);freeze(a.output,data,report,a.previous)
    lines=[]
    for m in report['models']:
        if not m['model']:continue
        e=m['test'];b=e['main'];n=e['learnedOnMainCohort']
        if m['market']=='score':lines.append((m['sport'],'Skor',m['model']['mode'],m['untouchedTestDate'],b['count'] if b else 0,f"{b['teamMAE']:.3f} → {n['teamMAE']:.3f}" if b else '—','—','—'))
        else:lines.append((m['sport'],m['market'],m['model']['mode'],m['untouchedTestDate'],b['count'] if b else 0,f"{b['accuracy']:.1%} → {n['accuracy']:.1%}" if b else '—',f"{b['brier']:.3f} → {n['brier']:.3f}" if b else '—',f"{b['logLoss']:.3f} → {n['logLoss']:.3f}" if b else '—'))
    body='<p>Gerçek sonuçtan öğrenen bağımsız model. Geçmiş / ilk oran / birlikte özellikler ayrı sınanır. Main eğitime veya seçime girmez. Bu geliştirme raporu geriye dönüktür; sonraki gün kaydedilen tahminlerle sınanmalıdır.</p>'
    body+=table(['Spor','Hedef','Seçilen girdiler','Test günü','Aynı kohort N','Main → öğrenilen isabet / skor MAE','Brier','Log loss'],lines)
    for m in report['models']:
        if m['model']:body+='<h2>'+m['sport']+' / '+m['market']+'</h2>'+table(['Özellik','Öğrenilen standart ağırlıklar'],[(r['feature'],str([round(x,4) for x in r['standardizedWeights']])) for r in m['coefficients']])
    (a.output/'outcome-learning.html').write_text(page('Geçmiş ve ilk oranlardan doğrudan sonuç öğrenme',body),encoding='utf-8')
    print(json.dumps([{'sport':m['sport'],'market':m['market'],'mode':m['model']['mode'] if m['model'] else None} for m in report['models']]))

if __name__=='__main__':main()
