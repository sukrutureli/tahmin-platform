"""Two-condition subgroup rules with chronological selection and untouched test labels.
Research only: no production predictions, daybook, scores or Telegram mutations.
"""
import argparse
import hashlib
import itertools
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from prepare import dump
from report import BASE, GROUPS, candidate_vector, result, metrics, page, table

MIN_TRAIN=40
MIN_VALIDATION=15
MAX_ATOMS=16
MAX_FINALISTS=10
PRIOR=20
QUANTILES=(.25,.5,.75)


def predictors(row,sport):
    # Read only dated pre-match rows. Outcome/realScore is deliberately absent.
    audit=row.get('variants',{}).get('six-simple',{}).get('audit',{})
    h=audit.get('home',{}).get('rows',[]);a=audit.get('away',{}).get('rows',[])
    if not h or not a:return {}
    if any(r['date']>=row['date'] for r in h+a):raise ValueError('Future history in rule predictors')
    def avg(rows,key):return statistics.mean(r[key] for r in rows)
    def margin(rows):return statistics.mean(r['for']-r['against'] for r in rows)
    def wins(rows):
        known=[r['win'] for r in rows if r.get('win') is not None]
        return statistics.mean(known) if known else None
    def trend(rows):return margin(rows[:3])-margin(rows[3:]) if len(rows)>=6 else None
    def variance(rows):return statistics.pvariance(r['for']+r['against'] for r in rows)
    values={'attackDefenceDiff':avg(h,'for')-avg(a,'for')+avg(a,'against')-avg(h,'against'),
            'expectedTotal':(avg(h,'for')+avg(h,'against')+avg(a,'for')+avg(a,'against'))/2,
            'minimumHistory':min(len(h),len(a)),
            'totalSigma':math.sqrt((variance(h)+variance(a))/2)}
    hw,aw=wins(h),wins(a)
    if hw is not None and aw is not None:values['winRateDifference']=hw-aw
    ht,at=trend(h),trend(a)
    if ht is not None and at is not None:values['formTrendDifference']=ht-at
    hv=[r for r in h if r['venue']=='home'];av=[r for r in a if r['venue']=='away']
    if len(hv)>=2 and len(av)>=2:
        values['venueMarginDifference']=margin(hv)-margin(av)
        values['venueExpectedTotal']=(avg(hv,'for')+avg(hv,'against')+avg(av,'for')+avg(av,'against'))/2
    wide=row.get('variants',{}).get('wide-balanced',{}).get('audit',{})
    wh=wide.get('home',{}).get('rows',[]);wa=wide.get('away',{}).get('rows',[])
    if min(len(wh),len(wa))>=10 and wide.get('historyBeforeKickoff') is not False:
        if any(r['date']>=row['date'] for r in wh+wa):raise ValueError('Future wide history in rule predictors')
        values['recentVsWideMarginDifference']=(margin(h)-margin(wh))-(margin(a)-margin(wa))
        values['wideMinimumCount']=min(len(wh),len(wa))
    if sport=='football':
        values['meanBlankRate']=(sum(r['for']==0 for r in h)/len(h)+sum(r['for']==0 for r in a)/len(a))/2
        values['meanBttsRate']=(sum(r['for']>0 and r['against']>0 for r in h)/len(h)+sum(r['for']>0 and r['against']>0 for r in a)/len(a))/2
        values['meanOverRate']=(sum(r['for']+r['against']>2.5 for r in h)/len(h)+sum(r['for']+r['against']>2.5 for r in a)/len(a))/2
    else:
        line=row.get('odds',{}).get('hOverUnderValue',0)
        if line>0:values['expectedTotalMinusLine']=values['expectedTotal']-line
    return {k:v for k,v in values.items() if math.isfinite(v)}


def applies(conditions,features):
    return all(c['feature'] in features and ((features[c['feature']]<=c['cut'])==c['below']) for c in conditions)


def observations(rows,sport,market,target):
    out=[]
    for row in rows:
        if row['date']>=target:continue
        p=candidate_vector(row,sport,market,('legacy',BASE[sport],0))
        y=result(row,sport,market)
        if p is not None and y is not None:
            f=predictors(row,sport)
            if f:out.append({'row':row,'p':p,'y':y,'features':f})
    return out


def distribution(group):
    k=len(group[0]['p']);n=len(group)
    return [(sum(x['y']==i for x in group)+PRIOR*statistics.mean(x['p'][i] for x in group))/(n+PRIOR) for i in range(k)]


def summary(group,probabilities,labels,option):
    if not group:return {'count':0,'baseline':None,'rule':None,'targetHits':0,'baselineHits':0,'gainHits':0,'matches':[]}
    b=metrics([(x['p'],x['y']) for x in group],labels)
    n=metrics([(probabilities,x['y']) for x in group],labels)
    bh=sum(max(range(len(x['p'])),key=x['p'].__getitem__)==x['y'] for x in group)
    hits=sum(x['y']==option for x in group)
    return {'count':len(group),'baseline':b,'rule':n,'targetHits':hits,'baselineHits':bh,'gainHits':hits-bh,
            'matches':[{'date':x['row']['date'],'eventId':x['row']['eventId'],'name':x['row']['name'],
                        'actual':labels[x['y']],'baselinePick':labels[max(range(len(x['p'])),key=x['p'].__getitem__)],
                        'rulePick':labels[option],'features':x['features']} for x in group]}


def quick(group,probabilities,option):
    n=len(group)
    gain=sum((x['y']==option)-(max(range(len(x['p'])),key=x['p'].__getitem__)==x['y']) for x in group)
    delta=sum(-math.log(max(probabilities[x['y']],1e-15))+math.log(max(x['p'][x['y']],1e-15)) for x in group)/n
    return gain,delta


def select(train,validation,option):
    # Thresholds and two-condition combinations are derived from TRAIN ONLY.
    atoms=[]
    for key in sorted({k for x in train for k in x['features']}):
        vals=sorted(x['features'][key] for x in train if key in x['features'])
        if len(set(vals))<4:continue
        for cut in sorted({vals[int((len(vals)-1)*q)] for q in QUANTILES}):
            for below in (True,False):
                condition={'feature':key,'cut':cut,'below':below}
                group=[x for x in train if applies([condition],x['features'])]
                if len(group)<MIN_TRAIN:continue
                p=distribution(group)
                # Keep weak atoms too: their conjunction may carry the signal.
                gain,delta=quick(group,p,option)
                atoms.append((delta,-gain,json.dumps(condition,sort_keys=True),condition))
    atoms=[x[3] for x in sorted(atoms)[:MAX_ATOMS]]
    combos=[[x] for x in atoms]+[[a,b] for a,b in itertools.combinations(atoms,2) if a['feature']!=b['feature']]
    candidates=[]
    for conditions in combos:
        group=[x for x in train if applies(conditions,x['features'])]
        if len(group)<MIN_TRAIN:continue
        p=distribution(group)
        # A rule naming an option must actually predict that option.
        if max(range(len(p)),key=p.__getitem__)!=option:continue
        gain,delta=quick(group,p,option)
        if gain<3 or delta>=0:continue
        candidates.append({'conditions':conditions,'probabilities':p,'trainCount':len(group),'trainGain':gain,'trainDeltaLogLoss':delta})
    candidates.sort(key=lambda c:(c['trainDeltaLogLoss'],-c['trainGain'],json.dumps(c['conditions'],sort_keys=True)))
    finalists=candidates[:MAX_FINALISTS];accepted=[]
    for c in finalists:
        group=[x for x in validation if applies(c['conditions'],x['features'])]
        if len(group)<MIN_VALIDATION:continue
        gain,delta=quick(group,c['probabilities'],option)
        if gain>=0 and delta<0:accepted.append((delta,-gain,json.dumps(c['conditions'],sort_keys=True),c))
    chosen=dict(min(accepted)[3],validationDeltaLogLoss=min(accepted)[0]) if accepted else None
    return chosen,finalists,{'searched':len(combos),'trainingQualified':len(candidates),'validationQualified':len(accepted)}


def mine(rows,sport,market,target):
    items=observations(rows,sport,market,target)
    dates=sorted({x['row']['date'] for x in items})
    if len(dates)<4:return {'sport':sport,'market':market,'status':'insufficient source dates','rules':[]}
    validation_date,test_date=dates[-2:]
    train=[x for x in items if x['row']['date']<validation_date]
    validation=[x for x in items if x['row']['date']==validation_date]
    test=[x for x in items if x['row']['date']==test_date]
    labels=GROUPS[sport][market];rules=[]
    for option,label in enumerate(labels):
        chosen,finalists,search=select(train,validation,option)
        entry={'option':label,'candidate':chosen,'search':search,'status':'validation accepted research candidate' if chosen else 'no candidate passed validation',
               'rejectedFinalists':[]}
        if chosen:
            for name,group in [('training',train),('validation',validation),('test',test)]:
                matched=[x for x in group if applies(chosen['conditions'],x['features'])]
                entry[name]=summary(matched,chosen['probabilities'],labels,option)
            entry['testStatus']='not yet tested prospectively; chronological retrospective holdout only'
        else:
            for c in finalists[:3]:
                g=[x for x in validation if applies(c['conditions'],x['features'])]
                entry['rejectedFinalists'].append({'candidate':c,'validation':summary(g,c['probabilities'],labels,option)})
        rules.append(entry)
    return {'sport':sport,'market':market,'sourceDates':dates,'trainingDates':[d for d in dates if d<validation_date],
            'validationDate':validation_date,'untouchedTestDate':test_date,'rules':rules}


def merge_dataset(current,previous,target):
    # Save raw rows for future chronological work; current archive may prune older days.
    data={s:{} for s in BASE}
    for source in (previous,current):
        for sport,rows in source.items():
            for r in rows:
                if r['date']<=target:
                    key=(r['date'],str(r['eventId']))
                    row=dict(r)
                    old=data[sport].get(key)
                    if old and result(row,sport,'MS') is None and result(old,sport,'MS') is not None:
                        row['realScore']=old['realScore']
                    data[sport][key]=row
    return {s:sorted(rows.values(),key=lambda r:(r['date'],str(r['eventId']))) for s,rows in data.items()}


def render(output,report):
    body='<p>Geçmiş özelliklerinden en çok iki koşul. Eşikler yalnız eğitimden; son iki kaynak gün sırasıyla seçim ve dokunulmamış test. Bu yeni geliştirilmiş geriye dönük araştırmadır; maç öncesi başarı değildir. Main, skor ve Telegram değişmez.</p>'
    for market in report['markets']:
        body+='<h2>'+market['sport']+' / '+market['market']+'</h2>'
        for r in market['rules']:
            body+='<h3>'+r['option']+'</h3>'
            if not r['candidate']:
                body+='<p>Doğrulamayı geçen kural yok. Elenen adaylar JSON içinde korunur.</p>';continue
            conditions=' VE '.join(c['feature']+(' ≤ ' if c['below'] else ' > ')+f"{c['cut']:.3f}" for c in r['candidate']['conditions'])
            body+='<p>'+conditions+'</p>'
            values=[]
            for name in ('training','validation','test'):
                x=r[name];b=x['baseline'];n=x['rule']
                values.append((name,x['count'],x['baselineHits'],x['targetHits'],x['gainHits'],f"{b['accuracy']:.1%}" if b else '—',f"{n['accuracy']:.1%}" if n else '—',f"{b['brier']:.4f} → {n['brier']:.4f}" if b else '—',f"{b['logLoss']:.4f} → {n['logLoss']:.4f}" if b else '—'))
            body+=table(['Bölüm','N','Main doğru','Kural doğru','Fark','Main isabet','Kural isabet','Brier','Log loss'],values)
            body+=table(['Test tarihi','Maç ID','Maç','Main','Kural','Sonuç'],[(m['date'],m['eventId'],m['name'],m['baselinePick'],m['rulePick'],m['actual']) for m in r['test']['matches']])
    (output/'mined-rules.html').write_text(page('Geçmişten koşullu kural araması',body),encoding='utf-8')


def freeze_snapshot(output,current,report,previous=None):
    from zoneinfo import ZoneInfo
    path=output/'mined-before-results.json'
    old=previous/'mined-before-results.json' if previous else None
    if old and old.exists() and json.loads(old.read_text()).get('targetDate')==report['targetDate']:
        path.write_bytes(old.read_bytes())
        return
    now=datetime.now(timezone.utc)
    book={'targetDate':report['targetDate'],'createdAt':now.isoformat(),'status':'research shadow; production unchanged','predictions':[]}
    fitted={(m['sport'],m['market']):m for m in report['markets']}
    for sport,rows in current.items():
        for row in rows:
            if row['date']!=report['targetDate']:continue
            f=predictors(row,sport)
            try:prospective=now<datetime.fromisoformat(row['date']+'T'+row['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
            except (ValueError,KeyError):prospective=False
            entry={'sport':sport,'date':row['date'],'eventId':row['eventId'],'name':row['name'],'prospectiveBeforeKickoff':prospective,'markets':{},
                   'score':row['variants']['legacy']['models'][BASE[sport]].get('scoreline')}
            for market in GROUPS[sport]:
                base=candidate_vector(row,sport,market,('legacy',BASE[sport],0))
                options=[r for r in fitted[(sport,market)]['rules'] if r['candidate'] and applies(r['candidate']['conditions'],f)]
                chosen=min(options,key=lambda r:(r['candidate']['validationDeltaLogLoss'],r['option'])) if options else None
                entry['markets'][market]={'baseline':base,'probabilities':chosen['candidate']['probabilities'] if chosen and base is not None else base,
                    'appliedRule':{'option':chosen['option'],'conditions':chosen['candidate']['conditions']} if chosen and base is not None else None}
            book['predictions'].append(entry)
    dump(path,book)


def settle_snapshot(output,current,target):
    book=json.loads((output/'mined-before-results.json').read_text())
    assert book['targetDate']==target
    labels={(s,r['date'],str(r['eventId'])):r for s,rows in current.items() for r in rows}
    evaluated={'targetDate':target,'status':'saved forecast settlement; late records are retrospective','markets':[]}
    for sport in BASE:
        for market,names in GROUPS[sport].items():
            samples=[]
            for e in book['predictions']:
                if e['sport']!=sport:continue
                row=labels.get((sport,e['date'],str(e['eventId'])))
                y=result(row,sport,market) if row else None
                p=e['markets'][market]
                if y is not None and p['baseline'] is not None and p['probabilities'] is not None:samples.append((e,p,y))
            entry={'sport':sport,'market':market}
            for prefix,items in [('all',samples),('prospective',[x for x in samples if x[0]['prospectiveBeforeKickoff']]),('applied',[x for x in samples if x[1]['appliedRule']])]:
                entry[prefix]={'baseline':metrics([(p['baseline'],y) for e,p,y in items],names),'rule':metrics([(p['probabilities'],y) for e,p,y in items],names)}
            evaluated['markets'].append(entry)
    dump(output/'mined-daily-evaluation.json',evaluated)
    old=output/'rule-mining-dataset.json'
    dataset=json.loads(old.read_text()) if old.exists() else {}
    dump(old,merge_dataset(current,dataset,target))

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path);p.add_argument('--bootstrap',type=Path);p.add_argument('--settle',action='store_true');p.add_argument('--target-date',required=True);a=p.parse_args()
    current={s:json.loads((a.input/(s+'-replay.json')).read_text()) for s in BASE}
    if a.settle:
        settle_snapshot(a.output,current,a.target_date)
        return
    old=a.previous/'rule-mining-dataset.json' if a.previous else None
    previous=json.loads(old.read_text()) if old and old.exists() else {}
    bootstrap_hashes={}
    if a.bootstrap and a.bootstrap.exists():
        for path in sorted(a.bootstrap.rglob('*-replay.json')):
            sport=path.name.split('-')[0]
            if sport not in BASE:continue
            previous=merge_dataset({sport:json.loads(path.read_text())},previous,a.target_date)
            bootstrap_hashes[str(path.relative_to(a.bootstrap))]=hashlib.sha256(path.read_bytes()).hexdigest()
    data=merge_dataset(current,previous,a.target_date)
    report={'createdAt':datetime.now(timezone.utc).isoformat(),'targetDate':a.target_date,
            'policy':{'maxConditions':2,'minTrain':MIN_TRAIN,'minValidation':MIN_VALIDATION,'prior':PRIOR,'maxFinalists':MAX_FINALISTS,
                      'thresholdSelection':'train only','ruleSelection':'validation only','testSelection':'never','productionPromotion':False,
                      'status':'retrospective development; future saved-day validation required'},
            'bootstrapHashes':bootstrap_hashes,'inputHashes':{s:hashlib.sha256((a.input/(s+'-replay.json')).read_bytes()).hexdigest() for s in BASE},
            'markets':[mine(data[s],s,m,a.target_date) for s in BASE for m in GROUPS[s]]}
    dump(a.output/'rule-mining-dataset.json',data);dump(a.output/'mined-rules.json',report);render(a.output,report)
    freeze_snapshot(a.output,current,report,a.previous)
    print(json.dumps([{'sport':m['sport'],'market':m['market'],'accepted':[r['option'] for r in m['rules'] if r['candidate']]} for m in report['markets']]))

if __name__=='__main__':main()
