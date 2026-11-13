"""Serve the frozen model before research training; keep provenance in encrypted checkpoints."""
import argparse,copy,json,shutil,tempfile
from datetime import datetime,timezone
from pathlib import Path
from context_features_fast import build_ledger,bounded_enrichment,Context
from mine_rules import merge_dataset
from report import BASE,GROUPS,candidate_vector,parse_score
from prepare import dump
import locked_stability as locked
from priced_choices import freeze as legacy_freeze
from complete_prices import freeze as complete_freeze
from new_reports import reports

def forecast(root,previous,target,enrich=True):
    root=Path(root);previous=Path(previous)
    config=locked.read(Path(locked.__file__).with_name('stability-settings.json'))
    if (root/locked.SNAPSHOT).exists():
        if locked.read(root/locked.SNAPSHOT)['targetDate']!=target:raise ValueError('Existing primary day mismatch')
        locked.verify_snapshot(root,config);return reports(root)
    # Serving needs only target-day replay rows; research retains full history separately.
    current={s:[r for r in json.loads((root/(s+'-replay.json')).read_text()) if r['date']==target] for s in BASE}
    data=merge_dataset(current,{},target)
    dump(root/'primary-serving-dataset.json',data)
    dump(root/'rule-mining-dataset.json',data)
    ledger=json.loads((root/'context-ledger.json').read_text())
    from context_features_fast import fixture_index
    index=fixture_index(json.loads((root/'live-history-journal.json').read_text()))
    for binding in ledger.get('identities',[]):
        key=(binding['sport'],binding['date'],str(binding['eventId']))
        if list(key) not in ledger.get('identityConflicts',[]):index.setdefault(key,binding)
    ctx=Context(ledger,index);bank=[];systems={}
    now=datetime.now(timezone.utc).isoformat()
    for sport in BASE:
        entries=[]
        for r in data[sport]:
            if r['date']!=target:continue
            bank.append({'sport':sport,'date':target,'eventId':str(r['eventId']),'values':ctx.features(r,sport)})
            markets={m:candidate_vector(r,sport,m,('legacy',BASE[sport],0)) for m in GROUPS[sport]}
            entries.append({'sport':sport,'date':target,'eventId':str(r['eventId']),'name':r['name'],'time':r.get('time'),
                            'markets':{m:p for m,p in markets.items() if p is not None},
                            'score':parse_score(r['variants']['legacy']['models'][BASE[sport]]),'prospectiveBeforeKickoff':True})
        systems[sport]={'main':entries}
    context={'targetDate':target,'createdAt':now,'systems':systems,'policy':'Baseline inputs for frozen-model serving; no training or result refresh.'}
    featurebook={'targetDate':target,'features':bank}
    for name,value in [('primary-context-before-results.json',context),('primary-context-features.json',featurebook),('primary-context-ledger.json',ledger)]:dump(root/name,value)
    # Use the original hash-locked inference function, with explicitly retained serving inputs.
    with tempfile.TemporaryDirectory(dir=root) as td:
        stage=Path(td)
        shutil.copyfile(root/'primary-serving-dataset.json',stage/'rule-mining-dataset.json')
        if (root/'input-manifest.json').exists():shutil.copyfile(root/'input-manifest.json',stage/'input-manifest.json')
        dump(stage/'context-before-results.json',context);dump(stage/'context-features.json',featurebook)
        book=locked.freeze(stage,previous,target,config)
        book['productionContextFile']='primary-context-before-results.json'
        book['productionFeaturesFile']='primary-context-features.json'
        book['snapshotSha256']=locked.signature({k:v for k,v in book.items() if k!='snapshotSha256'})
        dump(root/locked.SNAPSHOT,book);shutil.copyfile(stage/locked.MODEL,root/locked.MODEL)
    locked.verify_snapshot(root,config)
    legacy_freeze(root);complete_freeze(root)
    return reports(root)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['ledger','enrich','freeze']);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);p.add_argument('--target-date',required=True);a=p.parse_args()
    if a.mode=='ledger':build_ledger(a.output,a.previous,a.target_date)
    elif a.mode=='enrich':
        ledger=json.loads((a.output/'context-ledger.json').read_text())
        extra=bounded_enrichment(a.output,a.target_date,ledger,max_teams=8)
        build_ledger(a.output,a.previous,a.target_date,extra['requests'],extra['identityBindings'])
    else:forecast(a.output,a.previous,a.target_date)
