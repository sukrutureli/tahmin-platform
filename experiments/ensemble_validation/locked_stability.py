"""Prospective, fixed-weight opponent-strength cohort; never refits a model."""
import argparse,copy,hashlib,html,json,math,shutil
from datetime import datetime,timezone,date
from pathlib import Path
from zoneinfo import ZoneInfo
from context_experiment import predict,choice,own_comparison,table,REPORT_CSS,valid
from outcome_learning import features
from conditional_score import football_score,basketball_score,basket_covariance
from report import BASE,GROUPS,page,wilson
from prepare import dump

MODEL='stability-model.json'
SNAPSHOT='stability-before-results.json'
JOURNAL='stability-journal.json'
PIPELINE=['locked_stability.py','context_experiment.py','context_features.py',
          'outcome_learning.py','conditional_score.py','score_distribution.py',
          'prepare.py','report.py','live_history.py','history_markets.py']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def signature(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def code_hashes():return {n:sha(Path(__file__).parent/n) for n in PIPELINE}

def validate_config(c):
    if c['arm']!='opponent' or c['primary_fraction']!=.5 or c['fractions']!=[.25,.5,.75,1.]:raise ValueError('Unexpected stability protocol')
    if c['automatic_promotion'] or c['minimum_observed_days']<14:raise ValueError('Unsafe stability protocol')
    if date.fromisoformat(c['first_forecast_date'])<=date.fromisoformat(c['source_date']):raise ValueError('Source day is not a prospective test')

def validate_model(model,c):
    validate_config(c)
    if model['protocol']!=c or model['pipelineHashes']!=code_hashes():raise ValueError('Locked protocol/pipeline changed; use a new version, never reset this cohort')
    if model['payloadSha256']!=signature(model['payload']):raise ValueError('Locked fitted parameters changed')
    return model

def initialize(root,previous,c):
    """Copy the exact lock or extract source-day parameters without fitting."""
    root=Path(root);previous=Path(previous) if previous else None;validate_config(c)
    for p in [root/MODEL,previous/MODEL if previous else None]:
        if p and p.exists():
            model=validate_model(read(p),c)
            if p!=root/MODEL:shutil.copyfile(p,root/MODEL)
            return model
    source=root/'context-learning.json';report=read(source)
    if report['targetDate']!=c['source_date']:raise ValueError('Missing frozen source-day stability model; restore its successful artifact')
    arm=report['arms'][c['arm']];models=[]
    for m in arm['models']:
        dates=m.get('forecastTrainingDates',[])
        if not dates or max(dates)>=c['source_date']:raise ValueError('Source-day/current outcomes entered frozen training')
        fitted=m.get('forecastModel')
        if not fitted:raise ValueError('Missing fitted head; cannot silently use a changing baseline')
        models.append({k:copy.deepcopy(m[k]) for k in ['sport','market','forecastModel','forecastTrainingDates','contextStatus'] if k in m})
    expected={(s,m) for s in BASE for m in list(GROUPS[s])+['score']}
    if {(m['sport'],m['market']) for m in models}!=expected:raise ValueError('Incomplete locked heads')
    payload={'models':models,'footballDistribution':copy.deepcopy(arm['footballDistribution']['model']),
             'basketballCovariance':basket_covariance({'models':arm['models']})}
    model={'protocol':c,'lockedAt':datetime.now(timezone.utc).isoformat(),
           'sourceContextSha256':sha(source),'sourceSnapshotSha256':sha(root/'context-before-results.json'),
           'pipelineHashes':code_hashes(),'payload':payload,'payloadSha256':signature(payload),
           'policy':'Fixed weights, preprocessing, feature schema, score distribution/covariance and selection policy. No daily refit; fresh date-causal inputs only. No automatic main/HTML/Telegram promotion.'}
    dump(root/MODEL,model);return model

def verify_snapshot(root,c):
    root=Path(root);model=validate_model(read(root/MODEL),c);book=read(root/SNAPSHOT)
    if book['modelSha256']!=sha(root/MODEL) or book['version']!=c['version']:raise ValueError('Frozen stability model changed')
    expected=book['snapshotSha256'];body={k:v for k,v in book.items() if k!='snapshotSha256'}
    if signature(body)!=expected:raise ValueError('Stability forecast snapshot changed')
    return book

def freeze(root,previous,target,c,now=None):
    root=Path(root);previous=Path(previous) if previous else None;validate_config(c)
    if target<c['source_date']:return None
    model=initialize(root,previous,c)
    for p in [root/SNAPSHOT,previous/SNAPSHOT if previous else None]:
        if p and p.exists() and read(p)['targetDate']==target:
            if p!=root/SNAPSHOT:shutil.copyfile(p,root/SNAPSHOT)
            return verify_snapshot(root,c)
    if target<c['first_forecast_date']:return None
    # Historical runs and a model locked after the fixture day cannot be backdated.
    now=now or datetime.now(timezone.utc)
    if now.astimezone(ZoneInfo('Europe/Istanbul')).date().isoformat()<target:raise ValueError('Cannot issue a future calendar day from unavailable inputs')
    data=read(root/'rule-mining-dataset.json');context=read(root/'context-before-results.json')
    if context['targetDate']!=target:raise ValueError('Context input day mismatch')
    bank={(x['sport'],x['date'],str(x['eventId'])):x['values'] for x in read(root/'context-features.json')['features']}
    payload=model['payload'];systems={};coverage={}
    for sport in BASE:
        heads={m['market']:m for m in payload['models'] if m['sport']==sport};entries=[];missing=0
        for r in data[sport]:
            if r['date']!=target:continue
            f=dict(features(r,sport),**bank.get((sport,target,str(r['eventId'])),{}));missing+=int('eloDifference' not in f)
            markets={m:predict(heads[m]['forecastModel'],f,m) for m in GROUPS[sport]}
            mean=predict(heads['score']['forecastModel'],f,'score')
            if any(not valid(p) or len(p)!=len(GROUPS[sport][m]) for m,p in markets.items()):raise ValueError('Invalid locked probability; do not silently drop fixtures')
            if mean is None or len(mean)!=2 or any(not math.isfinite(x) or x<0 for x in mean):raise ValueError('Invalid locked score')
            try:before=now<datetime.fromisoformat(target+'T'+r['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
            except (ValueError,KeyError,TypeError):before=False
            e={'sport':sport,'date':target,'eventId':str(r['eventId']),'name':r['name'],'time':r.get('time'),
               'markets':markets,'scoreMean':mean,'score':mean,'prospectiveBeforeKickoff':before,
               'opponentAvailable':'eloDifference' in f,'missingFeaturePolicy':'locked training medians and missingness indicators'}
            selected=choice(e,r,sport)
            e['chosen']=selected
            if selected and mean is not None:
                line=2.5 if sport=='football' else r.get('odds',{}).get('hOverUnderValue',0)
                sc=football_score(mean,payload['footballDistribution'] or {'dispersion':None,'rho':0},selected['market'],selected['option'],line) if sport=='football' else basketball_score(mean,payload['basketballCovariance'],selected['market'],selected['option'],line)
                e['score']=sc['score']
            entries.append(e)
        systems[sport]={'main':copy.deepcopy(context['systems'][sport]['main']),c['version']:entries}
        # Pair both systems at the later protocol snapshot, never earlier original times.
        eligible={e['eventId']:e['prospectiveBeforeKickoff'] for e in entries}
        for e in systems[sport]['main']:e['prospectiveBeforeKickoff']=eligible.get(str(e['eventId']),False)
        coverage[sport]={'forecastCount':len(entries),'missingOpponentCount':missing,'beforeKickoffCount':sum(e['prospectiveBeforeKickoff'] for e in entries)}
    manifest=read(root/'input-manifest.json') if (root/'input-manifest.json').exists() else {}
    book={'targetDate':target,'createdAt':now.isoformat(),'version':c['version'],'modelSha256':sha(root/MODEL),
          'contextSnapshotSha256':sha(root/'context-before-results.json'),
          'sourceRefs':{k:manifest.get(k) for k in ['sourceSha','publishedSha','runUrl']},
          'coverage':coverage,'systems':systems,'policy':'Own maximum market per match, own confidence ranking; same-date bytes reused; no current outcomes in forecasts.'}
    book['snapshotSha256']=signature(book);dump(root/SNAPSHOT,book);return verify_snapshot(root,c)

def aggregate(days,sport,system,fraction):
    values=[]
    for day in days:
        block=next((b for b in day['beforeKickoff'] if b['rows'] and b['rows'][0]['sport']==sport),None)
        row=next((r for r in block['rows'] if r['system']==system and r['fraction']==fraction),None) if block else None
        if row and row['measured']:values.append((day['targetDate'],row['measured']))
    n=sum(v['count'] for _,v in values);hits=sum(v['hits'] for _,v in values)
    if not n:return None
    score_n=sum((v.get('score') or {}).get('count',0) for _,v in values)
    return {'observedDays':len(values),'dates':[d for d,_ in values],'count':n,'hits':hits,'accuracy':hits/n,'interval95':wilson(hits,n),
            **{k:sum(v[k]*v['count'] for _,v in values)/n for k in ['brier','logLoss','meanConfidence']},
            'scoreMAE':sum(v['score']['teamMAE']*v['score']['count'] for _,v in values if v.get('score'))/score_n if score_n else None}

def settle(root,previous,target,c):
    root=Path(root);previous=Path(previous) if previous else None;validate_config(c)
    if target<c['source_date']:return None
    validate_model(read(root/MODEL),c)
    old=read(previous/JOURNAL) if previous and (previous/JOURNAL).exists() else {'version':c['version'],'days':[]}
    if old['version']!=c['version']:raise ValueError('Cannot mix stability versions')
    if old.get('modelSha256',sha(root/MODEL))!=sha(root/MODEL):raise ValueError('Cannot mix fitted model versions')
    days={d['targetDate']:d for d in old['days']};book=None
    if target>=c['first_forecast_date']:
        book=verify_snapshot(root,c)
        if book['targetDate']!=target:raise ValueError('Settlement target mismatch')
        daily={'targetDate':target,'createdAt':book['createdAt'],'modelSha256':book['modelSha256'],'beforeKickoff':[],'allIncludingLate':[],'coverage':book['coverage']}
        for sport in BASE:
            rows=[r for r in read(root/(sport+'-replay.json')) if r['date']==target]
            daily['beforeKickoff'].append(own_comparison(book['systems'][sport],rows,sport,True))
            daily['allIncludingLate'].append(own_comparison(book['systems'][sport],rows,sport))
        if target in days and days[target]['modelSha256']!=daily['modelSha256']:raise ValueError('Daily model changed')
        days[target]=daily;dump(root/'stability-evaluation.json',daily)
    ordered=[days[d] for d in sorted(days)];summary=[]
    for sport in BASE:
        for fraction in c['fractions']:
            pair={s:aggregate(ordered,sport,s,fraction) for s in ['main',c['version']]}
            # Observe days only when BOTH systems have a settled sample for this subset.
            common=sorted(set((pair['main'] or {}).get('dates',[]))&set((pair[c['version']] or {}).get('dates',[])))
            selected=[d for d in ordered if d['targetDate'] in common]
            pair={s:aggregate(selected,sport,s,fraction) for s in pair}
            split=len(common)//2;halves=[[d for d in selected if d['targetDate'] in h] for h in [common[:split],common[split:]]]
            win=tie=loss=0
            for day in selected:
                a=aggregate([day],sport,c['version'],fraction);b=aggregate([day],sport,'main',fraction)
                win+=a['accuracy']>b['accuracy'];tie+=a['accuracy']==b['accuracy'];loss+=a['accuracy']<b['accuracy']
            summary.append({'sport':sport,'fraction':fraction,'systems':pair,'observedDays':len(common),'winDays':win,'tieDays':tie,'lossDays':loss,
                            'minimumDaysReached':len(common)>=c['minimum_observed_days'],
                            'chronologicalHalves':[{s:aggregate(h,sport,s,fraction) for s in pair} for h in halves]})
    journal={'version':c['version'],'protocol':c,'modelSha256':sha(root/MODEL),'days':ordered,'summary':summary,
             'status':'No automatic promotion. Fourteen observed days is a minimum, not proof; assess both chronological halves, day variation, N, calibration and score error. Nested confidence cohorts are not independent.'}
    dump(root/JOURNAL,journal);render(root,journal,book);return journal

def render(root,journal,book):
    c=journal['protocol'];rows=[]
    for r in journal['summary']:
        for s,m in r['systems'].items():
            rows.append([r['sport'],f"%{100*r['fraction']:.0f}",s,r['observedDays'],f"{m['hits']}/{m['count']} (%{100*m['accuracy']:.1f})" if m else 'Bekleniyor',f"{m['brier']:.4f}" if m else '—',f"{m['logLoss']:.4f}" if m else '—',f"{m['scoreMAE']:.3f}" if m and m['scoreMAE'] is not None else '—'])
    body=f'<style>{REPORT_CSS}</style><h1>Rakip gücü · sabit model izlemesi</h1><p>Sürüm: {html.escape(c["version"])}. Kaynak model günü: {c["source_date"]}; ilk bağımsız gün: {c["first_forecast_date"]}. Ağırlıklar, dönüşümler ve skor parametreleri sabit. Ana ölçü ilk %50; en az 14 sonuçlanan örnek içeren gün. Otomatik main geçişi yok.</p>'
    body+=table(['Spor','Alt küme','Sistem','Gün','İsabet','İkili Brier','Log loss','Skor MAE'],rows)
    body+='<p>Her sistem her maçta kendi en yüksek olasılıklı pazarını seçer, kendi güven sırasını kullanır. Canlı/eksik/push ve geç kayıtlar ana ölçümden çıkarılır. Gruplar iç içedir. Özet modelin tüm maçlarda ve ilk %25/%50/%75 grubundaki sonucunu ayrı saklar.</p>'
    if book:
        for sport,systems in book['systems'].items():
            rows=[]
            for e in sorted(systems[c['version']],key=lambda e:(e.get('time') or '',e['eventId'])):
                selected=e.get('chosen')
                if not selected:continue
                p,m,i=selected['confidence'],selected['market'],selected['option'];label=GROUPS[sport][m][i]
                rows.append([e.get('time'),e['name'],m+' '+label,f'%{100*p:.1f}','-'.join(str(int(x)) for x in e['score']) if e['score'] else '—','Var' if e['opponentAvailable'] else 'Eksik: sabit imputasyon','Maç öncesi' if e['prospectiveBeforeKickoff'] else 'Geç kayıt'])
            body+='<h2>'+html.escape(sport)+'</h2>'+table(['Saat','Maç','Tek tercih','Güven','Uyumlu skor','Rakip verisi','Kayıt'],rows)
    (root/'stability.html').write_text(page('Sabit rakip gücü modeli',body))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path);p.add_argument('--target-date',required=True);p.add_argument('--settings',type=Path,default=Path(__file__).with_name('stability-settings.json'));a=p.parse_args();c=read(a.settings)
    if a.mode=='freeze':freeze(a.output,a.previous,a.target_date,c)
    else:settle(a.output,a.previous,a.target_date,c)
if __name__=='__main__':main()
