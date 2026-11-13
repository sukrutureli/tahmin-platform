"""Serve the frozen model before research training; keep provenance in encrypted checkpoints."""
import argparse,copy,json,shutil,tempfile
from datetime import datetime,timezone
from pathlib import Path
from context_features import build_ledger,bounded_enrichment,Context
from mine_rules import merge_dataset
from report import BASE,GROUPS,candidate_vector,parse_score
from prepare import dump
import locked_stability as locked
from priced_choices import freeze as legacy_freeze
from complete_prices import freeze as complete_freeze
from new_reports import reports

def serving_dataset(current,target):
    """Target rows only; cumulative history is assembled in the research job."""
    return merge_dataset({s:[r for r in rows if r['date']==target] for s,rows in current.items()},{},target)

def forecast(root,previous,target,enrich=True):
    root=Path(root);previous=Path(previous)
    config=locked.read(Path(locked.__file__).with_name('stability-settings.json'))
    if (root/locked.SNAPSHOT).exists():
        if locked.read(root/locked.SNAPSHOT)['targetDate']!=target:raise ValueError('Existing primary day mismatch')
        locked.verify_snapshot(root,config);return reports(root)
    current={s:json.loads((root/(s+'-replay.json')).read_text()) for s in BASE}
    # Historical datasets are assembled by mine_rules in the research job.
    # Frozen serving only reads the target day; copying cumulative research JSON
    # here needlessly delays HTML and can exhaust the runner.
    data=serving_dataset(current,target)
    dump(root/'rule-mining-dataset.json',data)
    ledger,index=build_ledger(root,previous,target)
    # Current teams/opponents only. Training-only historical identity reconstruction is research.
    if enrich:
        extra=bounded_enrichment(root,target,ledger,max_teams=8)
        ledger,index=build_ledger(root,previous,target,extra['requests'],extra['identityBindings'])
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
        for name in ['rule-mining-dataset.json','input-manifest.json']:
            if (root/name).exists():shutil.copyfile(root/name,stage/name)
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
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);p.add_argument('--target-date',required=True);a=p.parse_args()
    forecast(a.output,a.previous,a.target_date)
