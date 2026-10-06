"""Conditional calibration shadow experiment. Never changes the daily daybook or scores."""
import argparse, hashlib, json, math, statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from prepare import dump
from report import BASE, GROUPS, candidate_vector, result, metrics, page, table

VERSION = 1

def features(row, sport):
    entry = row['variants'].get('six-balanced', {})
    audit = entry.get('marketFeatureAudit')
    if not audit:
        return {}
    h, a = audit['home'], audit['away']
    values = {
        'expectedTotal': (h['totalMean'] + a['totalMean']) / 2,
        'totalSigma': math.sqrt((h['totalVariance'] + a['totalVariance']) / 2),
        'attackDefenceDifference': h['goalsFor'] - a['goalsFor'] + a['goalsAgainst'] - h['goalsAgainst'],
        'minimumHistoryCount': min(h['count'], a['count']),
    }
    if sport == 'football':
        values.update(minimumBttsRate=min(h['bttsRate'], a['bttsRate']),
                      maximumBlankRate=max(h['blankRate'], a['blankRate']),
                      meanOverRate=(h['over25Rate'] + a['over25Rate']) / 2)
    else:
        line = row['odds'].get('hOverUnderValue', 0)
        if line > 0:
            values['expectedTotalMinusLine'] = values['expectedTotal'] - line
    # No labels, current score, or future histories can enter these features.
    return values

def baseline(row, sport, market):
    return candidate_vector(row, sport, market, ('legacy', BASE[sport], 0))

def matches(rule, values):
    if rule.get('feature') == 'all':
        return True
    v = values.get(rule.get('feature'))
    return v is not None and (v <= rule['cut']) == rule['below']

def apply(rule, probability, values):
    if probability is None or not rule or not matches(rule, values):
        return probability
    return [(1-rule['blend'])*p + rule['blend']*q
            for p,q in zip(probability, rule['target'])]

def observations(rows, sport, market):
    out=[]
    for r in rows:
        p=baseline(r,sport,market); y=result(r,sport,market)
        if p is not None and y is not None:
            out.append((r,p,y,features(r,sport)))
    return out

def measure(items, sport, market, rule=None):
    return metrics([(apply(rule,p,f),y) for r,p,y,f in items], GROUPS[sport][market])

def fit(rows, sport, market, target_date):
    past=[r for r in rows if r['date'] < target_date]
    items=observations(past,sport,market)
    dates=sorted({r['date'] for r,p,y,f in items})
    if len(dates)<3:
        return {'active':None,'reason':'at least three settled source dates required'}
    validation_date=dates[-1]
    train=[x for x in items if x[0]['date']<validation_date]
    validation=[x for x in items if x[0]['date']==validation_date]
    minimum=30 if sport=='football' else 10
    if len(train)<minimum:
        return {'active':None,'reason':'insufficient chronological train/validation sample'}
    conditions=[{'feature':'all'}]
    keys=sorted({k for r,p,y,f in train for k in f})
    for key in keys:
        vals=sorted(f[key] for r,p,y,f in train if key in f)
        if len(set(vals))<3:
            continue
        for q in (.25,.5,.75):
            cut=vals[int((len(vals)-1)*q)]
            for below in (True,False):
                conditions.append({'feature':key,'cut':cut,'below':below})
    candidates=[]
    for condition in conditions:
        group=[x for x in train if matches(condition,x[3])]
        if len(group)<minimum:
            continue
        n=len(group); k=len(group[0][1])
        # Twenty baseline pseudo-observations keep a small subgroup from dominating.
        means=[statistics.mean(x[1][i] for x in group) for i in range(k)]
        target=[(sum(x[2]==i for x in group)+20*means[i])/(n+20) for i in range(k)]
        for blend in (.25,.5):
            rule=dict(condition,target=target,blend=blend,trainingGroupCount=n)
            m=measure(train,sport,market,rule)
            candidates.append((m['logLoss'],json.dumps(rule,sort_keys=True),rule,m))
    _,_,chosen,trained=min(candidates)
    b=measure(validation,sport,market)
    v=measure(validation,sport,market,chosen)
    accepted=len(validation)>=minimum and v['logLoss']<b['logLoss'] and v['accuracy']>=b['accuracy']
    return {'active':chosen if accepted else None,'researchCandidate':chosen,
            'training':trained,'validationDate':validation_date,
            'validationBaseline':b,'validationCandidate':v,'candidateCount':len(candidates),
            'reason':'passed historical validation; requires prospective test' if accepted
                     else ('small historical validation sample; baseline retained' if len(validation)<minimum
                           else 'rejected on historical validation; baseline retained')}

def freeze(data, previous=None, now=None):
    targets={r['date'] for rows in data.values() for r in rows if r['role']=='holdout'}
    if len(targets)!=1:
        raise ValueError('Exactly one target date required')
    target=next(iter(targets));now=now or datetime.now(timezone.utc)
    if previous and previous.get('targetDate')==target:
        return previous
    carry=bool(previous and previous.get('version')==VERSION
               and previous.get('targetDate','9999')<target
               and target<=previous.get('frozenThrough',''))
    rules=previous['rules'] if carry else {
        s:{m:fit(rows,s,m,target) for m in GROUPS[s]} for s,rows in data.items()}
    out={'version':VERSION,'targetDate':target,'createdAt':now.isoformat(),
         'rulesFrozenOn':previous['rulesFrozenOn'] if carry else target,
         'frozenThrough':previous['frozenThrough'] if carry else
             (date.fromisoformat(target)+timedelta(days=6)).isoformat(),
         'rules':rules,'scorePolicy':'original score unchanged','autoPromotion':False,
         'historyScope':'frozen 1 October pool; new teams can lack wide history',
         'predictions':[]}
    for s,rows in data.items():
        for r in rows:
            if r['date']!=target:
                continue
            try:
                kickoff=datetime.fromisoformat(target+'T'+r['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
                prospective=now<kickoff
            except (ValueError,KeyError):
                prospective=False
            markets={}
            for m in GROUPS[s]:
                p=baseline(r,s,m)
                markets[m]={'baseline':p,'probabilities':apply(rules[s][m]['active'],p,features(r,s)),
                            'researchProbabilities':apply(rules[s][m].get('researchCandidate'),p,features(r,s))}
            out['predictions'].append({'sport':s,'date':target,'eventId':r['eventId'],
                                      'name':r['name'],'prospectiveBeforeKickoff':prospective,
                                      'markets':markets})
    return out

def settle(book,data):
    rows={(s,r['date'],r['eventId']):r for s,rs in data.items() for r in rs}
    out={'date':book['targetDate'],'rulesFrozenOn':book['rulesFrozenOn'],'markets':[],
         'status':'shadow research; historical selection is not independent success'}
    for s in BASE:
        for m,labels in GROUPS[s].items():
            old=[];new=[];po=[];pn=[];research=[];pr=[]
            for e in book['predictions']:
                if e['sport']!=s:
                    continue
                r=rows.get((s,e['date'],e['eventId']))
                y=result(r,s,m) if r else None
                p=e['markets'][m]
                if y is None or p['baseline'] is None or p['probabilities'] is None:
                    continue
                old.append((p['baseline'],y));new.append((p['probabilities'],y))
                research.append((p['researchProbabilities'],y))
                if e['prospectiveBeforeKickoff']:
                    po.append((p['baseline'],y));pn.append((p['probabilities'],y))
                    pr.append((p['researchProbabilities'],y))
            out['markets'].append({'sport':s,'market':m,'baseline':metrics(old,labels),
                'conditional':metrics(new,labels),'prospectiveBaseline':metrics(po,labels),
                'prospectiveConditional':metrics(pn,labels),'researchCandidate':metrics(research,labels),
                'prospectiveResearchCandidate':metrics(pr,labels)})
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['freeze','settle'])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True)
    a=p.parse_args()
    data={s:json.loads((a.output/(s+'-replay.json')).read_text()) for s in BASE}
    path=a.output/'conditional-before-results.json'
    if a.mode=='freeze':
        saved=a.previous/path.name
        previous=json.loads(saved.read_text()) if saved.exists() else None
        book=freeze(data,previous)
        if previous and book is previous:
            path.write_bytes(saved.read_bytes())
        else:
            dump(path,book)
    else:
        book=json.loads(path.read_text())
        evaluation=settle(book,data)
        evaluation['predictionFileSha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        dump(a.output/'conditional-evaluation.json',evaluation)
        body='<p>Koşullu kalibrasyon ayrı gölge deneyidir. Kurallar önceki günlerden seçilir, son kaynak günde kontrol edilir ve yedi takvim günü sabit tutulur. Geçmiş kontrol araştırmadır; bağımsız başarı yalnız maç öncesi kaydedilen sonraki sonuçlarla ölçülür. Skor ve mevcut günlük defter değişmez. Lig/rakip gücü özellikleri henüz eklenmemiştir; geniş havuz 1 Ekimden dondurulmuştur.</p>'
        body+=table(['Spor','Pazar','Kural','Geçmiş kontrol günü','Karar'],[
            (s,m,json.dumps(v.get('active'),ensure_ascii=False),v.get('validationDate','—'),v['reason'])
            for s,markets in book['rules'].items() for m,v in markets.items()])
        body+=table(['Spor','Pazar','N','Mevcut isabet','Aday isabet','Öncesinde N'],[
            (x['sport'],x['market'],x['baseline']['count'] if x['baseline'] else 0,
             x['baseline']['accuracy'] if x['baseline'] else '—',
             x['conditional']['accuracy'] if x['conditional'] else '—',
             x['prospectiveConditional']['count'] if x['prospectiveConditional'] else 0)
            for x in evaluation['markets']])
        (a.output/'conditional-rules.html').write_text(page('Koşullu kurallar — ayrı deney',body),encoding='utf-8')
