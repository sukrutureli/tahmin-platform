"""Opponent/competition ablations; frozen research snapshots, independent own-pick comparisons."""
import argparse,copy,hashlib,html,json,math
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from context_features import Context,STRENGTH,LEAGUE,build_ledger,bounded_enrichment
from outcome_learning import learn,features,transform_values,softmax,score_metrics,samples
from prepare import dump
from report import BASE,GROUPS,result,parse_score,metrics,page,table,wilson,candidate_vector
from score_distribution import learn as learn_distribution,forecast,log_probability
from conditional_score import football_score,basketball_score,basket_covariance

ARMS={'baseline':[],'opponent':STRENGTH,'league':LEAGUE,'opponent+league':STRENGTH+LEAGUE}
FILES=['context-before-results.json','context-learning.json','context-ledger.json','context-features.json','context-enrichment.json','context-lock.json']
DEVELOPMENT='2026-10-15'

def table(headers,rows):
    return '<section class="context-table"><table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td data-label="'+html.escape(h,quote=True)+'">'+html.escape(str(v))+'</td>' for h,v in zip(headers,row))+'</tr>' for row in rows)+'</tbody></table></section>'

REPORT_CSS="""body{background:#f3f6fa;color:#172a40}main{max-width:1100px;margin:auto;padding:14px}h1{background:#11283e;color:white;padding:24px;border-radius:18px}section.context-table{overflow:auto}table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;border-bottom:1px solid #dce5ec;white-space:normal}details{padding:14px;border:1px solid #dce5ec;border-radius:12px;margin:14px 0;background:white}summary{cursor:pointer;font-weight:650}@media(max-width:650px){main{padding:8px}section.context-table{overflow:visible}table,tbody{display:block}thead{display:none}tr{display:grid;grid-template-columns:1fr 1fr;padding:12px;gap:8px;border-bottom:1px solid #dce5ec}td{display:block;padding:0;border:0;min-width:0}td:before{content:attr(data-label);display:block;font-size:11px;color:#65768a}td:first-child{grid-column:1/-1;font-weight:700}}"""


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def valid(p):return bool(p) and all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in p) and abs(sum(p)-1)<1e-6

def choice(e,row,sport):
    options=[]
    for market in GROUPS[sport]:
        p=e.get('markets',{}).get(market)
        if not valid(p) or len(p)!=len(GROUPS[sport][market]):continue
        if market=='OU' and sport=='basketball' and row.get('odds',{}).get('hOverUnderValue',0)<=0:continue
        i=max(range(len(p)),key=lambda i:p[i]);options.append((p[i],market,i))
    if not options:return None
    conf,market,i=max(options,key=lambda x:x[0]);return {'confidence':conf,'market':market,'option':i,'eventId':str(e['eventId']),'score':e.get('score')}


def own_comparison(systems,rows,sport,prospective=False):
    labels={str(r['eventId']):r for r in rows};chosen={}
    for name,entries in systems.items():
        selected={}
        for e in entries:
            if prospective and not e.get('prospectiveBeforeKickoff'):continue
            row=labels.get(str(e['eventId']));c=choice(e,row,sport) if row else None
            if c:selected[c['eventId']]=c
        chosen[name]=selected
    shared=set.intersection(*(set(x) for x in chosen.values())) if chosen else set()
    complete={i for i in shared if all(result(labels[i],sport,picks[i]['market']) is not None for picks in chosen.values())}
    report=[]
    for name,picks in chosen.items():
        ranked=sorted([picks[i] for i in shared],key=lambda x:(-x['confidence'],x['eventId']))
        for fraction in [.25,.5,.75,1.]:
            group=ranked[:math.ceil(len(ranked)*fraction)];items=[e for e in group if e['eventId'] in complete];n=len(items);hits=sum(result(labels[e['eventId']],sport,e['market'])==e['option'] for e in items)
            actual=[];predicted=[]
            for e in items:
                score=parse_score({'scoreline':labels[e['eventId']].get('realScore')})
                if score is not None and e.get('score') is not None:actual.append(score);predicted.append(e['score'])
            measured={'count':n,'hits':hits,'accuracy':hits/n,'interval95':wilson(hits,n),
                'meanConfidence':sum(e['confidence'] for e in items)/n,
                'brier':sum((e['confidence']-int(result(labels[e['eventId']],sport,e['market'])==e['option']))**2 for e in items)/n,
                'logLoss':-sum(math.log(max(1e-12,e['confidence'] if result(labels[e['eventId']],sport,e['market'])==e['option'] else 1-e['confidence'])) for e in items)/n,
                'score':score_metrics(actual,predicted),'exactScoreHits':sum(list(y)==list(p) for y,p in zip(actual,predicted)),
                'marketCounts':dict(Counter(e['market'] for e in items))} if n else None
            report.append({'sport':sport,'system':name,'fraction':fraction,'plannedCount':len(group),'measured':measured,
               'eventIds':[e['eventId'] for e in group],'finishedEventIds':[e['eventId'] for e in items]})
    return {'policy':'Each system selects its own highest-probability market and its own confidence-ranked subset. Ranks include pending fixtures; measurement uses common settled fixtures only, excluding pushes/live/missing. Subset memberships may differ.',
            'sharedForecastCount':len(shared),'commonFinishedCount':len(complete),'rows':report}


def predict(model,f,market):
    if not model:return None
    x=transform_values([f],model['transform']);v=x@np.array(model['weights'])
    return (np.maximum(0,v) if market=='score' else softmax(v))[0].tolist()


def score_diagnostics(model,distribution=None):
    if not model or not model.get('model'):return None
    train=model['training']['matches'];test=model['test']['matches'];val=model['validation']['matches']
    if not test:return None
    actual=[x['actual'] for x in test];means=[x['learned'] for x in test];out={'count':len(test),'meanScore':score_metrics(actual,means),'retrospective':True}
    if model['sport']=='football' and distribution and distribution.get('model'):
        dm=distribution['model'];points=[forecast(x,dm)['score'] for x in means]
        probabilities=[max(0,min(1,1-sum(math.exp(log_probability((h,a),mu,dm)) for h in range(4) for a in range(4-h)))) for mu in means]
        ys=[int(sum(y)>=4) for y in actual]
        out.update(exactHits=sum(list(y)==p for y,p in zip(actual,points)),modalScore=score_metrics(actual,points),
           modalCounts={str(k):v for k,v in Counter(tuple(p) for p in points).items()},highTotalThreshold=4,
           actualHighCount=sum(ys),modalHighCount=sum(sum(p)>=4 for p in points),meanPredictedHighProbability=sum(probabilities)/len(probabilities),
           highTotalBrier=sum((p-y)**2 for p,y in zip(probabilities,ys))/len(ys),jointLogLoss=-sum(log_probability(y,mu,dm) for y,mu in zip(actual,means))/len(actual))
    if model['sport']=='basketball' and train and val:
        threshold=float(np.quantile([sum(m['actual']) for m in train],.9));residuals=[sum(m['actual'])-sum(m['learned']) for m in val]
        sigma=max(8,float(np.std(residuals)));probs=[.5*math.erfc((threshold-sum(mu))/(math.sqrt(2)*sigma)) for mu in means];ys=[int(sum(y)>threshold) for y in actual]
        out.update(highTotalThreshold=threshold,actualHighCount=sum(ys),pointHighCount=int(sum(sum(np.rint(mu))>threshold for mu in means)),
                   meanPredictedHighProbability=sum(probs)/len(probs),highTotalBrier=sum((p-y)**2 for p,y in zip(probs,ys))/len(ys),
                   highTotalPolicy='Threshold = training totals 90th percentile; Gaussian total residual scale = validation std, floor 8; untouched-test measurement.')
    if 'modalHighCount' in out:out['pointHighCount']=out['modalHighCount']
    if val:
        q=float(np.quantile([abs(sum(m['actual'])-sum(m['learned'])) for m in val],.8))
        out.update(validationAbsoluteTotalError80=q,testTotalInterval80Coverage=sum(abs(sum(y)-sum(mu))<=q for y,mu in zip(actual,means))/len(actual),
                   intervalPolicy='80th percentile absolute total residual on prior validation only; report untouched-test coverage, no claimed guarantee.')
    return out


def learn_context(rows,sport,market,target,feature_function,keys,baseline):
    required=[]
    if any(k in STRENGTH for k in keys):required.append('eloDifference')
    if any(k in LEAGUE for k in keys):required.append('leagueExpectedTotal')
    items=samples(rows,sport,market,target,feature_function)
    available=lambda r:all(k in r['f'] and math.isfinite(r['f'][k]) for k in required)
    train_dates=baseline.get('trainingDates',[]);validation_dates=baseline.get('validationDates',[])
    ntrain=sum(r['row']['date'] in train_dates and available(r) for r in items)
    nval=sum(r['row']['date'] in validation_dates and available(r) for r in items)
    status={'trainingContextCount':ntrain,'validationContextCount':nval,'minimumTraining':30,'minimumValidation':10,'requiredFeatures':required}
    if not baseline.get('model') or ntrain<30 or nval<10:
        model=copy.deepcopy(baseline);status['status']='fallback-insufficient-context';model['contextStatus']=status;return model
    model=learn(rows,sport,market,target,feature_function,keys);status['status']='context-candidate';model['contextStatus']=status;return model


def prepare(root,previous,target,extra_teams=8):
    root=Path(root);previous=Path(previous) if previous else None
    existing=root/'context-before-results.json'
    old=previous/'context-before-results.json' if previous else None
    source=existing if existing.exists() and json.loads(existing.read_text()).get('targetDate')==target else old
    if source and source.exists() and json.loads(source.read_text()).get('targetDate')==target:
        base=source.parent
        for name in FILES:
            if (base/name).exists() and (base/name).resolve()!=(root/name).resolve():(root/name).write_bytes((base/name).read_bytes())
        check_snapshot(root)
        if not (root/'context-lock.json').exists():dump(root/'context-lock.json',{'forecastSha256':digest(root/'context-before-results.json')})
        return
    data=json.loads((root/'rule-mining-dataset.json').read_text());baseline=json.loads((root/'outcome-learning.json').read_text());assert baseline['targetDate']==target
    ledger,index=build_ledger(root,previous,target)
    if extra_teams:
        cutoffs={s:min((m['validationDate'] for m in baseline['models'] if m['sport']==s and m.get('model')),default='0000') for s in BASE}
        extra=bounded_enrichment(root,target,ledger,max_teams=extra_teams,data=data,index=index,train_cutoffs=cutoffs)
        ledger,index=build_ledger(root,previous,target,extra['requests'],extra['identityBindings'])
    else:dump(root/'context-enrichment.json',{'targetDate':target,'policy':'additional HTTP disabled for this reproducible offline build','requests':[]})
    ctx=Context(ledger,index);bank={};coverage=[]
    for sport,rows in data.items():
        for r in rows:
            key=(sport,r['date'],str(r['eventId']));bank[key]=ctx.features(r,sport)
        for day in sorted({r['date'] for r in rows}):
            ds=[r for r in rows if r['date']==day];fs=[bank[sport,day,str(r['eventId'])] for r in ds]
            coverage.append({'sport':sport,'date':day,'count':len(ds),'opponentAvailable':sum('eloDifference' in f for f in fs),'leagueAvailable':sum('leagueExpectedTotal' in f for f in fs)})
    dump(root/'context-features.json',{'targetDate':target,'coverage':coverage,'features':[{'sport':s,'date':d,'eventId':i,'values':f} for (s,d,i),f in bank.items()],
       'limitation':'Initial context reconstructed after old fixtures: all historical tests are development/backtests. No name joins, no guessed provider IDs; missing context is retained and imputed by train-only preprocessing.'})
    report={'targetDate':target,'createdAt':datetime.now(timezone.utc).isoformat(),'developmentDate':DEVELOPMENT,'arms':{},'coverage':coverage,
       'selectionPolicy':'No automatic promotion: validate feature group/regularization on prior validation, retain untouched chronological test. Fixed Elo K=.15, sparse strength shrinkage=5, league shrinkage=30, trailing 365 days; these are development hypotheses, not optimized thresholds.',
       'dataPolicy':ledger['policy'],'backtestLimitation':'Historical context was first assembled on development date. Same-day comparison or old test results do not establish prospective benefit.'}
    def ff(row,sport):return dict(features(row,sport),**bank.get((sport,row['date'],str(row['eventId'])),{}))
    for arm,keys in ARMS.items():
        models=copy.deepcopy(baseline['models']) if arm=='baseline' else [learn_context(data[s],s,m,target,ff,[k for k in keys if not(s=='basketball' and k in ('leagueMeanBtts','leagueMeanOver'))],next(x for x in baseline['models'] if x['sport']==s and x['market']==m)) for s in BASE for m in list(GROUPS[s])+['score']]
        arm_report={'targetDate':target,'models':models};distribution=learn_distribution(arm_report)
        report['arms'][arm]={'models':models,'footballDistribution':distribution,
             'scores':[score_diagnostics(m,distribution if m['sport']=='football' else None) for m in models if m['market']=='score']}
    dump(root/'context-learning.json',report)
    now=datetime.now(timezone.utc);book={'targetDate':target,'createdAt':now.isoformat(),'developmentDate':DEVELOPMENT,'independentDay':target>DEVELOPMENT,
       'policy':'Experimental arms only; existing published/learned forecasts, main and Telegram unchanged. Each arm selects its own maximum market. Same-day bytes reused.',
       'hashes':{n:digest(root/n) for n in ['context-learning.json','context-features.json','context-ledger.json']},'systems':{s:{} for s in BASE}}
    frozen=json.loads((root/'learned-before-results.json').read_text());saved={(e['sport'],str(e['eventId'])):e for e in frozen['predictions']}
    for sport,rows in data.items():
        day=[r for r in rows if r['date']==target];systems={'main':[],'baseline':[]}
        for arm in ARMS:
            if arm!='baseline':systems[arm]=[]
        for r in day:
            e=saved.get((sport,str(r['eventId'])))
            if not e:continue
            try:before=now<datetime.fromisoformat(target+'T'+r['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
            except (ValueError,KeyError,TypeError):before=False
            base={'sport':sport,'date':target,'eventId':str(r['eventId']),'name':r['name'],'time':r.get('time'),'prospectiveBeforeKickoff':before,'independentBeforeKickoff':before and target>DEVELOPMENT}
            systems['main'].append(dict(base,markets=e['baselineMarkets'],score=e['baselineScore'],originalForecastBeforeKickoff=e['prospectiveBeforeKickoff']))
            for arm,ar in report['arms'].items():
                ms={m['market']:m for m in ar['models'] if m['sport']==sport};f=ff(r,sport);markets={};fallback=[]
                for market in GROUPS[sport]:
                    model=ms.get(market,{}).get('forecastModel');p=predict(model,f,market) if model else None
                    if p is None:p=e['markets'].get(market);fallback.append(market)
                    elif ms.get(market,{}).get('contextStatus',{}).get('status')=='fallback-insufficient-context':fallback.append(market)
                    markets[market]=p
                model=ms.get('score',{}).get('forecastModel');mean=predict(model,f,'score') if model else e['score'];entry=dict(base,markets=markets,score=mean,scoreMean=mean,fallbackMarkets=fallback)
                chosen=choice(entry,r,sport)
                if mean is not None and chosen:
                    line=2.5 if sport=='football' else r.get('odds',{}).get('hOverUnderValue',0)
                    if sport=='football':sc=football_score(mean,ar['footballDistribution']['model'] or {'dispersion':None,'rho':0},chosen['market'],chosen['option'],line)
                    else:sc=basketball_score(mean,basket_covariance({'models':ar['models']}),chosen['market'],chosen['option'],line)
                    entry['score']=sc['score']
                systems[arm].append(entry)
        book['systems'][sport]=systems
    dump(existing,book);dump(root/'context-lock.json',{'forecastSha256':digest(existing)});check_snapshot(root)


def check_snapshot(root):
    root=Path(root);b=json.loads((root/'context-before-results.json').read_text())
    lock=root/'context-lock.json'
    if lock.exists() and json.loads(lock.read_text())['forecastSha256']!=digest(root/'context-before-results.json'):raise ValueError('Context forecast snapshot changed')
    for name,expected in b['hashes'].items():
        if digest(root/name)!=expected:raise ValueError('Context snapshot/model changed: '+name)
    return b


def heldout_comparisons(report,data):
    comparisons=[]
    for sport,rows in data.items():
        dates={m['untouchedTestDate'] for arm in report['arms'].values() for m in arm['models'] if m['sport']==sport and m.get('model')}
        if len(dates)!=1:continue
        day=dates.pop();dayrows=[r for r in rows if r['date']==day];systems={}
        for arm,ar in report['arms'].items():
            models=[m for m in ar['models'] if m['sport']==sport and m.get('model')];by={}
            for m in models:
                for r in m['test']['matches']:
                    e=by.setdefault(str(r['eventId']),{'eventId':str(r['eventId']),'markets':{},'score':None})
                    if m['market']=='score':e['score']=r['learned']
                    else:e['markets'][m['market']]=r['learned']
            day_by_id={str(r['eventId']):r for r in dayrows}
            covariance=basket_covariance({'models':ar['models']}) if sport=='basketball' else None
            for e in by.values():
                row=day_by_id[e['eventId']];selected=choice(e,row,sport);mean=e.get('score')
                if selected and mean is not None:
                    line=2.5 if sport=='football' else row.get('odds',{}).get('hOverUnderValue',0)
                    if sport=='football':point=football_score(mean,ar['footballDistribution']['model'] or {'dispersion':None,'rho':0},selected['market'],selected['option'],line)
                    else:point=basketball_score(mean,covariance,selected['market'],selected['option'],line)
                    e['score']=point['score']
            systems[arm]=list(by.values())
        systems['main']=[{'eventId':str(r['eventId']),'markets':{m:candidate_vector(r,sport,m,('legacy',BASE[sport],0)) for m in GROUPS[sport]},'score':parse_score(r['variants']['legacy']['models'][BASE[sport]])} for r in dayrows]
        measured=own_comparison(systems,dayrows,sport);measured.update(date=day,status='retrospective chronological test; first context collected later');comparisons.append(measured)
    return comparisons


def settle(root,target):
    root=Path(root);book=check_snapshot(root);assert book['targetDate']==target
    data=json.loads((root/'rule-mining-dataset.json').read_text());replay={s:json.loads((root/(s+'-replay.json')).read_text()) for s in BASE}
    report=json.loads((root/'context-learning.json').read_text());daily={'targetDate':target,'snapshotCreatedAt':book['createdAt'],'independentDay':book['independentDay'],
      'all':[],'beforeKickoff':[],'historicalTest':heldout_comparisons(report,data)}
    for sport in BASE:
        rows=[r for r in replay[sport] if r['date']==target];systems=book['systems'][sport]
        daily['all'].append(own_comparison(systems,rows,sport))
        daily['beforeKickoff'].append(own_comparison(systems,rows,sport,True))
    dump(root/'context-evaluation.json',daily)
    def lines(comparisons):
        out=[]
        for c in comparisons:
            for r in c['rows']:
                m=r['measured'];out.append((r['sport'],r['system'],f"İlk %{100*r['fraction']:.0f}",r['plannedCount'],m['count'] if m else 0,
                   f"{m['hits']} / %{100*m['accuracy']:.1f}" if m else '—',f"{m['brier']:.3f}" if m else '—',f"{m['logLoss']:.3f}" if m else '—',f"{m['score']['teamMAE']:.3f}" if m and m['score'] else '—'))
        return out
    headers=['Spor','Sistem','Kapsam','Planlanan','Sonuçlanan N','Doğru / isabet','İkili Brier','Log loss','Skor MAE']
    body='<p>Her sistem kendi en yüksek olasılıklı pazarını ve kendi güven sırasındaki maçlarını seçer. Tüm maçların karşılaştırması ortak tamamlanmış maç kohortundadır; alt kümelerin üyeleri farklı olabilir. Sıralama bitmemiş maçları da içerir. Eksik/live ve push sonuçlar başarı paydasında yoktur. Main ve mevcut model değiştirilmedi.</p>'
    body+='<p>İlk geliştirme: '+DEVELOPMENT+'. Eski günlere sonradan bağlam eklendiğinden geçmiş testler araştırmadır; aynı gün başarısı bağımsız kanıt değildir. Terfi otomatik değildir.</p>'
    body+='<h2>Önceki kronolojik test · araştırma</h2>'+table(headers,lines(daily['historicalTest']))
    body+='<h2>Bugünün dondurulmuş adayları · tüm kayıtlar / keşif</h2>'+table(headers,lines(daily['all']))
    body+='<h2>Maç başlamadan kaydedilen adaylar</h2><p>Bu tablo ilk geliştirme gününde bağımsız doğrulama sayılmaz; sonraki günlerde prospective kanıt birikir.</p>'+table(headers,lines(daily['beforeKickoff']))
    coverage=[(x['sport'],x['date'],x['count'],x['opponentAvailable'],x['leagueAvailable']) for x in report['coverage']]
    gates=[(arm,m['sport'],m['market'],m['contextStatus']['trainingContextCount'],m['contextStatus']['validationContextCount'],m['contextStatus']['status']) for arm,ar in report['arms'].items() for m in ar['models'] if 'contextStatus' in m]
    body+='<h2>Bağlam eğitimi yeterlilik kontrolü</h2><p>En az 30 eğitim ve 10 doğrulama maçında gerçek bağlam özelliği yoksa bu aday eğitilmez; mevcut model aynen kullanılır. Bugünün kapsanması, eski eğitim günlerinin de kapsandığı anlamına gelmez.</p>'+table(['Aday','Spor','Pazar','Eğitim bağlam N','Doğrulama bağlam N','Durum'],gates)
    body+='<h2>Özellik kapsamı</h2>'+table(['Spor','Tarih','Maç','Rakip gücü mevcut','Lig etkisi mevcut'],coverage)
    body+='<h2>Skor dağılımı teşhisi · kronolojik test</h2><p>Futbolda yüksek toplam 4+ gol; basketbolda eğitim toplamlarının %90 kesimini aşma. Aşağıdaki dağılım ölçümü bağımsız skor modelidir; yukarıdaki seçim tablolarında aday skorları kendi tercihlerine koşullanmıştır. Main orijinal skorunu korur.</p>'
    scores=[]
    for arm,ar in report['arms'].items():
        sms=[m for m in ar['models'] if m['market']=='score']
        for m,diag in zip(sms,ar['scores']):
            if diag:scores.append((arm,m['sport'],diag['count'],str(round(diag.get('highTotalThreshold',0),1)),str(diag.get('actualHighCount','—')),str(diag.get('pointHighCount','—')),str(round(diag.get('meanPredictedHighProbability',0),3)) if 'meanPredictedHighProbability' in diag else '—',str(round(diag.get('highTotalBrier',0),3)) if 'highTotalBrier' in diag else '—',str(round(diag.get('testTotalInterval80Coverage',0),3))))
    body+=table(['Aday','Spor','N','Yüksek toplam eşiği','Gerçek yüksek toplam','Bağımsız nokta yüksek toplam','Yüksek toplam olasılığı','Yüksek toplam Brier','Toplam %80 aralık kapsamı'],scores)
    body+='<p>Sezon kimliği sağlayıcıda yoksa uydurulmaz. Lig istatistikleri son 365 günü kullanır; az veri genel spor ortalamasına çekilir. Kimlikler sağlayıcıya göre ayrıdır, kısa ad eşleştirmesi yoktur. Ek veri taraması aynı 90 saniyelik bütçede en fazla 60 eski maç kimliği ve 8 rakip takım / iki aylık endpoint sayfası; 429 bütün ek taramayı durdurur. Eski native geçmiş snapshotları aynen kalır.</p>'
    (root/'context-comparison.html').write_text(page('Rakip gücü ve lig etkisi · ayrı adaylar',body).replace('</style>',REPORT_CSS+'</style>',1),encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','settle']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path);p.add_argument('--target-date',required=True);p.add_argument('--extra-teams',type=int,default=8);a=p.parse_args()
    if not 0<=a.extra_teams<=8:raise ValueError('extra teams must be 0..8')
    if a.mode=='prepare':prepare(a.output,a.previous,a.target_date,a.extra_teams)
    else:settle(a.output,a.target_date)
if __name__=='__main__':main()
