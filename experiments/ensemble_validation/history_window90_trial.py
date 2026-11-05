"""One-day input intervention. Frozen heads and production files are read-only."""
import argparse,copy,hashlib,html,json,math
from collections import defaultdict,Counter
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from context_features import Context,fixture_index
from context_experiment import predict
from outcome_learning import features
from report import GROUPS,parse_score
from conditional_score import football_score,basketball_score
from complete_prices import choose,POLICY
from priced_choices import read,write,signature,compare

VERSION='history-window90-v1'
FILE='history-window90-before-results.json'
ARMS={'window90':'90 gün','recency':'90 gün + zaman','competition':'90 gün + organizasyon','combined':'90 gün + ikisi'}
PROTOCOL={'version':VERSION,'halfLifeDays':{'football':90,'basketball':60},'maximumAgeDays':365,
          'differentCompetitionMultiplier':.25,'maximumMatches':None,'performanceWindowDays':90,'strengthWindowDays':365,
          'shortWindow':6,'selectionPolicy':POLICY,'refit':False,'automaticPromotion':False}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def age(day,target):return (date.fromisoformat(target)-date.fromisoformat(day)).days
def weight(r,target,sport,tournament,arm):
    days=age(r['date'],target)
    if days<=0:return 0.
    value=1.
    if arm in ('recency','combined'):
        if days>PROTOCOL['maximumAgeDays']:return 0.
        value=2**(-days/PROTOCOL['halfLifeDays'][sport])
    if arm in ('competition','combined') and tournament:
        value*=1 if str(r.get('tournamentId'))==str(tournament) else .25
    return value
def mean(rows,fn,target,sport,tournament,arm):
    pairs=[(fn(r),weight(r,target,sport,tournament,arm)) for r in rows]
    pairs=[(v,w) for v,w in pairs if v is not None and w>0]
    n=sum(w for v,w in pairs)
    return sum(v*w for v,w in pairs)/n if n else None
def effective(rows,target,sport,tournament,arm):
    ws=[weight(r,target,sport,tournament,arm) for r in rows];total=sum(ws)
    return total*total/sum(w*w for w in ws) if total else 0.

from window_features import features as history_features,pools,StrengthContext

def freeze(root,out,now=None):
    root=Path(root);out=Path(out);out.mkdir(exist_ok=True,parents=True);path=out/FILE
    if path.exists():
        b=read(path)
        if b['snapshotSha256']!=signature({k:v for k,v in b.items() if k!='snapshotSha256'}) or b['protocol']!=PROTOCOL:raise ValueError('Trial snapshot changed')
        if b['sourceSha256']!=digest(root/'priced-complete-before-results.json'):raise ValueError('Wrong frozen source day')
        return b
    now=now or datetime.now(timezone.utc);base=read(root/'priced-complete-before-results.json');target=base['targetDate']
    if now.astimezone(ZoneInfo('Europe/Istanbul')).date().isoformat()!=target:raise ValueError('Freeze only the actual current date')
    locked=read(root/'stability-before-results.json');model=read(root/'stability-model.json')
    if digest(root/'stability-model.json')!=base['modelSha256']:raise ValueError('Model provenance mismatch')
    ledger=read(root/'context-ledger.json');index=fixture_index(read(root/'live-history-journal.json'))
    conflicts={tuple(x) for x in ledger.get('identityConflicts',[])}
    for binding in ledger.get('identities',[]):
        key=(binding['sport'],binding['date'],str(binding['eventId']))
        if key not in conflicts:index.setdefault(key,binding)
    poolbank,poolmeta=pools(root,ledger,index,target,read)
    bankname=locked.get('productionFeaturesFile','context-features.json')
    bank={(x['sport'],x['date'],str(x['eventId'])):x['values'] for x in read(root/bankname)['features']}
    systems={};coverage={}
    for sport in GROUPS:
        replay={str(r['eventId']):r for r in read(root/(sport+'-replay.json')) if r['date']==target}
        heads={m['market']:m['forecastModel'] for m in model['payload']['models'] if m['sport']==sport}
        systems[sport]={'main':copy.deepcopy(base['systems'][sport]['experiment'])};coverage[sport]={}
        for ref in systems[sport]['main']:
            try:before=now<datetime.fromisoformat(target+'T'+ref['time']).replace(tzinfo=ZoneInfo('Europe/Istanbul'))
            except (KeyError,TypeError,ValueError):before=False
            ref['prospectiveBeforeKickoff']=bool(before and ref.get('prospectiveBeforeKickoff'))
        for arm in ARMS:
            entries=[];stats=Counter();contexts={}
            for ref in systems[sport]['main']:
                e=copy.deepcopy(ref);r=copy.deepcopy(replay[str(e['eventId'])]);key=(sport,target,str(e['eventId']));r['_window90Rows']=poolbank[key]
                ident=index.get(key) if key not in conflicts else None;tournament=ident.get('tournamentId') if ident else None
                f=dict(features(r,sport),**bank.get(key,{}));overrides,audit=history_features(r,sport,arm,ident)
                if audit['missingShort']:
                    for name in list(f):
                        if name not in ('marketHome','marketDraw','marketAway','marketOver','marketUnder','marketBtts','marketNoBtts','msOverround','ouOverround','bttsOverround','totalLine') and name not in bank.get(key,{}):f.pop(name)
                for name in ('formTrendDifference','venueMarginDifference','venueExpectedTotal','recentVsWideMarginDifference','wideMinimumCount'):
                    if name not in overrides:f.pop(name,None)
                f.update(overrides)
                ck=tournament,arm
                if ck not in contexts:contexts[ck]=StrengthContext(ledger,index,tournament,arm)
                strength=contexts[ck].features(r,sport)
                from context_features import STRENGTH
                for name in STRENGTH:f.pop(name,None)
                f.update(strength)
                original=dict(features(r,sport),**bank.get(key,{}))
                used={k for head in heads.values() for k in head['transform']['keys']}
                audit['usedFeatureChanges']=sum(f.get(k)!=original.get(k) for k in used)
                e['markets']={m:predict(heads[m],f,m) for m in GROUPS[sport]};e['scoreMean']=predict(heads['score'],f,'score')
                e['chosen']=choose(e,r,sport);c=e['chosen'];e['score']=None
                if c:
                    payload=model['payload'];line=2.5 if sport=='football' else (r.get('odds') or {}).get('hOverUnderValue',0)
                    sc=football_score(e['scoreMean'],payload['footballDistribution'],c['market'],c['option'],line) if sport=='football' else basketball_score(e['scoreMean'],payload['basketballCovariance'],c['market'],c['option'],line)
                    e['score']=sc['score']
                e['inputAudit']=audit;entries.append(e)
                stats['noPerformanceHistory']+=int(audit['missingShort']);stats['overOldQuotaSides']+=sum(n>(20 if sport=='football' else 25) for n in audit['historyCounts']);stats['availableRows']+=sum(audit['historyCounts']);stats['maximumSideRows']=max(stats['maximumSideRows'],max(audit['historyCounts']));stats['changedFeatures']+=int(audit['usedFeatureChanges']>0);stats['missingCompetition']+=int(audit['missingCompetition'])
                stats['changedPick']+=int(tuple((c or {}).get(k) for k in ('market','option'))!=tuple((ref.get('chosen') or {}).get(k) for k in ('market','option')))
            systems[sport][arm]=entries;coverage[sport][arm]=dict(stats,fixtures=len(entries),beforeKickoff=sum(e['prospectiveBeforeKickoff'] for e in entries))
    b={'version':VERSION,'protocol':PROTOCOL,'policy':POLICY,'targetDate':target,'createdAt':now.isoformat(),'previewOnly':False,
       'modelSha256':digest(root/'stability-model.json'),'sourceSha256':digest(root/'priced-complete-before-results.json'),
       'ledgerSha256':digest(root/'context-ledger.json'),'poolCoverage':poolmeta,'systems':systems,'coverage':coverage}
    b['snapshotSha256']=signature(b);write(path,b);return b

def seal_eligibility(origin,out):
    """Deterministic exclusions from the ORIGINAL input artifact, never current labels."""
    origin=Path(origin);out=Path(out);b=read(out/FILE);path=out/'history-window90-eligibility.json'
    if digest(origin/'priced-complete-before-results.json')!=b['sourceSha256']:raise ValueError('Wrong original inputs for eligibility')
    excluded={}
    for sport in GROUPS:
        excluded[sport]=[str(r['eventId']) for r in read(origin/(sport+'-replay.json')) if r['date']==b['targetDate'] and parse_score({'scoreline':r.get('realScore')}) is not None]
    value={'targetDate':b['targetDate'],'sourceSha256':b['sourceSha256'],'knownAtFreeze':excluded,
           'policy':'Exclude outcomes already present in the original frozen source even when kickoff clock disagrees.'}
    if path.exists():
        if read(path)!=value:raise ValueError('Original eligibility evidence changed')
    else:write(path,value)
    return value

def settle(root,out):
    root=Path(root);out=Path(out);b=read(out/FILE)
    if b['snapshotSha256']!=signature({k:v for k,v in b.items() if k!='snapshotSha256'}):raise ValueError('Frozen trial changed')
    report={k:b[k] for k in ('version','protocol','targetDate','createdAt','snapshotSha256','sourceSha256','modelSha256','coverage')}
    eligibility=out/'history-window90-eligibility.json'
    if eligibility.exists():
        evidence=read(eligibility)
        if evidence['sourceSha256']!=b['sourceSha256']:raise ValueError('Eligibility source mismatch')
        report['knownAtFreezeExcluded']={s:len(ids) for s,ids in evidence['knownAtFreeze'].items()}
        b=copy.deepcopy(b)
        for sport,systems in b['systems'].items():
            excluded=set(evidence['knownAtFreeze'][sport])
            for entries in systems.values():
                for e in entries:
                    if str(e['eventId']) in excluded:e['prospectiveBeforeKickoff']=False;e['eligibilityExclusion']='Result already in original source'
    for key,prospective in [('beforeKickoff',True),('allIncludingLate',False)]:
        report[key]={}
        for arm in ARMS:
            pair=dict(b,systems={s:{'main':v['main'],arm:v[arm]} for s,v in b['systems'].items()})
            report[key][arm]=compare(pair,root,prospective)
    write(out/'history-window90-evaluation.json',report);render(root,out,b,report);return report

def render(root,out,b,report):
    esc=lambda x:html.escape(str(x));pct=lambda x:'—' if x is None else f'%{100*x:.1f}'
    metric=lambda x:'—' if x is None else f'{x:.3f}'
    body=f'<h1>90 günlük geçmiş deneyi</h1><p>{esc(b["targetDate"])} · Ana tahminler değişmez.</p><p>Performans: erişilebilen son 90 gün; 20/25 maç sınırı yok. Son 6 maç formu ayrıca korunur. Rakip gücü: daha geniş geçmiş, eskilik etkisi azalarak. Organizasyon adayında farklı organizasyona dörtte bir ağırlık. Tam 90 günlük kapsama garanti değildir.</p><p>Kayıt: {esc(b["createdAt"])} · Ağırlıklar yeniden eğitilmedi. İlk %50 ana ölçü; geç kayıt ayrı tutulur.</p>'
    def pick(e,sport):
        c=e.get('chosen')
        if not c:return 'Tahmin yok'
        return esc(('KG ' if c['market']=='BTTS' else '')+GROUPS[sport][c['market']][c['option']])+f' <b>{pct(c["confidence"])}</b> · {c["price"]:.2f}'
    for sport,label in [('football','Futbol'),('basketball','Basketbol')]:
        body+='<h2>'+label+'</h2><p>Her takımda kullanılan gerçek maç sayısı aşağıda. Eksik süre eski maçlarla doldurulmaz.</p><div class="scroll"><table><tr><th>Aday</th><th>Grup</th><th>Sistem</th><th>Sonuç/seçim</th><th>Doğru</th><th>İsabet</th><th>Brier ↓</th><th>Log loss ↓</th><th>Skor MAE ↓</th></tr>'
        for arm,labelarm in ARMS.items():
            for frac in (.5,.25,.75,1.):
                for row in report['beforeKickoff'][arm]:
                    if row['sport']!=sport or row['fraction']!=frac:continue
                    vals=[labelarm,'İlk %'+str(int(frac*100)) if frac<1 else 'Tümü','Mevcut' if row['system']=='main' else 'Aday',f'{row["count"]}/{row["plannedCount"]}',str(row['hits']) if row['count'] else 'Bekliyor',pct(row['accuracy']),metric(row['brier']),metric(row['logLoss']),metric(row['scoreMAE'])]
                    body+='<tr>'+''.join('<td>'+esc(v)+'</td>' for v in vals)+'</tr>'
        body+='</table></div>'
        base=b['systems'][sport]['main'];banks={a:{e['eventId']:e for e in b['systems'][sport][a]} for a in ARMS}
        replay={str(r['eventId']):r for r in read(Path(root)/(sport+'-replay.json')) if r['date']==b['targetDate']}
        for e in sorted(base,key=lambda x:(-(x.get('chosen') or {}).get('confidence',0),x['eventId'])):
            actual=parse_score({'scoreline':replay[e['eventId']].get('realScore')})
            body+='<article><b>'+esc(e['name'])+'</b><small>'+esc(e.get('time',''))+' · '+('Maç öncesi' if e['prospectiveBeforeKickoff'] else 'Geç kayıt · bağımsız değil')+(' · Sonuç '+esc(actual) if actual else '')+'</small>'
            for arm,name in [('main','Mevcut')]+list(ARMS.items()):
                x=e if arm=='main' else banks[arm][e['eventId']]
                score='—' if x.get('score') is None else '–'.join(map(str,x['score']))
                audit=x.get('inputAudit',{});counts=audit.get('historyCounts');oldest=audit.get('oldestAgeDays');coverage=(' · Geçmiş: '+str(counts[0])+'/'+str(counts[1])+' maç · En eski: '+('—' if oldest[0] is None else str(oldest[0]))+'/'+('—' if oldest[1] is None else str(oldest[1]))+' gün') if counts else ''
                body+='<div class="pick"><span>'+name+'</span><div>'+pick(x,sport)+'<small>Skor '+esc(score+coverage)+'</small></div></div>'
            body+='</article>'
    body+='<p>Oranlar ilk kayıttandır. Canlı/eksik/iade sonuçları başarı paydasına girmez. Bir günlük sonuç karar desteğidir; otomatik model geçişi yapılmaz. Organizasyon kimliği yoksa organizasyon etkisi uygulanmaz; 90 günlük performans hesabı sürer.</p>'
    css='body{font:14px/1.5 system-ui;background:#f3f6fa;color:#18334b;max-width:1000px;margin:auto;padding:14px}h1{font-size:23px}p{font-size:13px;color:#536779}article{background:white;border:1px solid #dae4ee;border-radius:12px;padding:12px;margin:10px 0}small{display:block;color:#667b8d;font-size:11px}.pick{display:grid;grid-template-columns:125px 1fr;padding:7px 0;border-top:1px solid #edf2f6}.pick>span{font-size:12px}.scroll{overflow:auto}table{font-size:11px;background:white;border-collapse:collapse}td,th{padding:7px;border-bottom:1px solid #ddd;white-space:nowrap}'
    (Path(out)/'90-gun-gecmis-deneyi.html').write_text('<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>90 günlük geçmiş deneyi</title><style>'+css+'</style>'+body+'</html>')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['freeze','settle']);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.mode=='freeze':freeze(a.root,a.out);seal_eligibility(a.root,a.out)
    settle(a.root,a.out)
