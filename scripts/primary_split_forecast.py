"""Split the existing primary serving path and index immutable cache files once."""
import argparse,json,math,shutil,tempfile,urllib.parse
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
from context_features import canonical,merge_records,fixture_index,bounded_enrichment,Context
from mine_rules import merge_dataset
from report import BASE,GROUPS,candidate_vector,parse_score
from prepare import dump
import locked_stability as locked
from priced_choices import freeze as legacy_freeze
from complete_prices import freeze as complete_freeze
from new_reports import reports

def read(p): return json.loads(Path(p).read_text())

def dataset(root,previous,target):
    current={s:read(root/(s+'-replay.json')) for s in BASE}
    prior=previous/'rule-mining-dataset.json'
    data=merge_dataset(current,read(prior) if prior.exists() else {},target)
    dump(root/'rule-mining-dataset.json',data)
    return data

def cache_index(root):
    """Match Path.glob's HTTP-before-context precedence without repeated directory scans."""
    result={}
    for pattern in ('http-cache/*/*','context-http-cache/*/*'):
        for path in Path(root).glob(pattern):
            result.setdefault(path.name,path)
    return result

def cache_records_indexed(index,request_rows,target,collected):
    found=[];validated=set();payloads=[];rejected=0
    for req in request_rows:
        url=urllib.parse.urlsplit(req.get('url',''))
        if not url.path.endswith('/widget/team/schedule') or req.get('status')!=200 or not req.get('cache'):continue
        sport='football' if url.path.startswith('/soccer/') else 'basketball' if url.path.startswith('/basketball/') else None
        own=str(urllib.parse.parse_qs(url.query).get('teId',[None])[0])
        if not sport or not own.isdigit() or int(own)<=0:continue
        path=index.get(req['cache'])
        if not path:continue
        data=read(path).get('data',{});raw_mid=data.get('metaData',{}).get('team',{}).get('id')
        mid=str(raw_mid) if isinstance(raw_mid,(str,int)) and str(raw_mid).isdigit() and int(raw_mid)>0 else None
        if mid and mid!=own:rejected+=1;continue
        if mid==own:validated.add((sport,own))
        payloads.append((sport,own,data))
    from live_history import flatten,schedule_row
    for sport,own,data in payloads:
        if (sport,own) not in validated:rejected+=1;continue
        for raw in flatten(data.get('initialData')):
            row=schedule_row(raw,date.fromisoformat(target),sport)
            if not row:continue
            item=canonical(sport,'broadage',own,row,collected)
            if item:found.append(item)
    return found,rejected

def ledger_part(root,target,part,parts):
    root=Path(root);live=read(root/'live-history.json');requests=live.get('requests',[])
    subset=[request for i,request in enumerate(requests) if i%parts==part]
    records,rejected=cache_records_indexed(cache_index(root),subset,target,live.get('completedAt') or datetime.now(timezone.utc).isoformat())
    dump(root/f'ledger-part-{part}.json',{'part':part,'parts':parts,'records':records,'rejected':rejected})

def build_ledger_from_parts(root,previous,target,parts):
    root=Path(root);previous=Path(previous) if previous else root
    old=previous/'context-ledger.json';prior=read(old) if old.exists() else {};records=list(prior.get('matches',[]))
    journal=read(root/'live-history-journal.json');rejected=0
    partitioned=[]
    for part in range(parts):
        book=read(root/f'ledger-part-{part}.json')
        if book.get('part')!=part or book.get('parts')!=parts:raise ValueError('Ledger partition mismatch')
        partitioned.extend((record,part) for record in book['records']);rejected+=book['rejected']
    # Restore original request order across round-robin partitions.
    records += [record for record,part in sorted(partitioned,key=lambda item:(item[0].get('firstCollectedAt',''),item[0]['key'],item[1]))]
    for day in journal:
        for fixture in day.get('fixtures',[]):
            for side in fixture.get('sides',[]):
                ns='broadage' if side.get('source')=='broadage-team-schedule' else 'nesine' if side.get('source')=='nesine-summary-general-and-venue' else None
                if not ns:continue
                for row in side.get('rows',[]):
                    if row.get('date','9999')>=day['targetDate']:continue
                    item=canonical(fixture['sport'],ns,side.get('teamId'),row,fixture.get('collectedAt',''))
                    if item:records.append(item)
    records,conflicts=merge_records(records);conflicts=sorted(set(conflicts)|set(prior.get('conflictingMatchKeys',[])));records=[r for r in records if r['key'] not in conflicts]
    match_index=fixture_index(journal);bindings={};identity_conflicts=list(prior.get('identityConflicts',[]))
    for binding in prior.get('identities',[]):
        key=(binding['sport'],binding['date'],str(binding['eventId']))
        if list(key) in identity_conflicts:continue
        current=match_index.get(key) or bindings.get(key)
        if current and any(current.get(k)!=binding.get(k) for k in ['home','away','namespace','tournamentId']):identity_conflicts.append(list(key));continue
        bindings.setdefault(key,binding)
    for key,binding in bindings.items():
        if list(key) not in identity_conflicts:match_index.setdefault(key,binding)
    out={'identities':[b for k,b in bindings.items() if list(k) not in identity_conflicts],'identityConflicts':identity_conflicts,'createdAt':datetime.now(timezone.utc).isoformat(),'targetDate':target,'matches':records,'conflictingMatchKeys':conflicts,'rejectedCacheIdentities':rejected,'seasonPolicy':'Provider season ID if supplied; otherwise explicit missing. League features use trailing 365 days, no guessed season.','policy':'IDs only; exact sport/provider namespaces; one row per finished match; all feature outcomes strictly before fixture day. Backfilled historical features are retrospective.'}
    dump(root/'context-ledger.json',out);return out,match_index

def extend_ledger(root,target,extra_requests,extra_bindings):
    root=Path(root);base=read(root/'context-ledger.json')
    if base.get('targetDate')!=target:raise ValueError('Ledger target changed')
    extra,rejected=cache_records_indexed(cache_index(root),list(extra_requests),target,datetime.now(timezone.utc).isoformat())
    records,conflicts=merge_records(list(base['matches'])+extra)
    conflicts=sorted(set(conflicts)|set(base.get('conflictingMatchKeys',[])));records=[r for r in records if r['key'] not in conflicts]
    journal=read(root/'live-history-journal.json');match_index=fixture_index(journal);bindings={};identity_conflicts=list(base.get('identityConflicts',[]))
    for binding in list(base.get('identities',[]))+list(extra_bindings):
        key=(binding['sport'],binding['date'],str(binding['eventId']))
        if list(key) in identity_conflicts:continue
        current=match_index.get(key) or bindings.get(key)
        if current and any(current.get(k)!=binding.get(k) for k in ['home','away','namespace','tournamentId']):identity_conflicts.append(list(key));continue
        bindings.setdefault(key,binding)
    for key,binding in bindings.items():
        if list(key) not in identity_conflicts:match_index.setdefault(key,binding)
    base.update({'identities':[b for k,b in bindings.items() if list(k) not in identity_conflicts],'identityConflicts':identity_conflicts,'createdAt':datetime.now(timezone.utc).isoformat(),'matches':records,'conflictingMatchKeys':conflicts,'rejectedCacheIdentities':base.get('rejectedCacheIdentities',0)+rejected})
    dump(root/'context-ledger.json',base);return base,match_index

def ledger_final(root,previous,target,parts):
    dataset(root,previous,target);build_ledger_from_parts(root,previous,target,parts)

def enrich(root,previous,target):
    ledger=read(root/'context-ledger.json')
    if ledger.get('targetDate')!=target: raise ValueError('Ledger target changed')
    return bounded_enrichment(root,target,ledger,max_teams=8)

def freeze(root,previous,target):
    config=locked.read(Path(locked.__file__).with_name('stability-settings.json'))
    if (root/locked.SNAPSHOT).exists():
        if locked.read(root/locked.SNAPSHOT)['targetDate']!=target: raise ValueError('Existing primary day mismatch')
        locked.verify_snapshot(root,config); return reports(root)
    data=dataset(root,previous,target);extra=read(root/'context-enrichment.json')
    if extra.get('targetDate')!=target or extra.get('maxTeams')!=8 or extra.get('maxSeconds')!=90:raise ValueError('Enrichment boundary changed')
    ledger,index=extend_ledger(root,target,extra['requests'],extra['identityBindings'])
    ctx=Context(ledger,index);bank=[];systems={};now=datetime.now(timezone.utc).isoformat()
    for sport in BASE:
        entries=[]
        for row in data[sport]:
            if row['date']!=target:continue
            bank.append({'sport':sport,'date':target,'eventId':str(row['eventId']),'values':ctx.features(row,sport)})
            markets={m:candidate_vector(row,sport,m,('legacy',BASE[sport],0)) for m in GROUPS[sport]}
            entries.append({'sport':sport,'date':target,'eventId':str(row['eventId']),'name':row['name'],'time':row.get('time'),'markets':{m:p for m,p in markets.items() if p is not None},'score':parse_score(row['variants']['legacy']['models'][BASE[sport]]),'prospectiveBeforeKickoff':True})
        systems[sport]={'main':entries}
    context={'targetDate':target,'createdAt':now,'systems':systems,'policy':'Baseline inputs for frozen-model serving; no training or result refresh.'};featurebook={'targetDate':target,'features':bank}
    for name,value in [('primary-context-before-results.json',context),('primary-context-features.json',featurebook),('primary-context-ledger.json',ledger)]:dump(root/name,value)
    with tempfile.TemporaryDirectory(dir=root) as td:
        stage=Path(td)
        for name in ['rule-mining-dataset.json','input-manifest.json']:
            if (root/name).exists():shutil.copyfile(root/name,stage/name)
        dump(stage/'context-before-results.json',context);dump(stage/'context-features.json',featurebook)
        book=locked.freeze(stage,previous,target,config);book['productionContextFile']='primary-context-before-results.json';book['productionFeaturesFile']='primary-context-features.json';book['snapshotSha256']=locked.signature({k:v for k,v in book.items() if k!='snapshotSha256'});dump(root/locked.SNAPSHOT,book);shutil.copyfile(stage/locked.MODEL,root/locked.MODEL)
    locked.verify_snapshot(root,config);legacy_freeze(root);complete_freeze(root);return reports(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['ledger-part','ledger-final','enrich','freeze']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);p.add_argument('--target-date',required=True);p.add_argument('--part',type=int);p.add_argument('--parts',type=int,default=4);a=p.parse_args()
    if a.mode=='ledger-part':ledger_part(a.output,a.target_date,a.part,a.parts)
    elif a.mode=='ledger-final':ledger_final(a.output,a.previous,a.target_date,a.parts)
    elif a.mode=='enrich':enrich(a.output,a.previous,a.target_date)
    else:freeze(a.output,a.previous,a.target_date)
