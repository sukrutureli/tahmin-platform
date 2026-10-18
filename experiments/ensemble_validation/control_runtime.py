"""Resolve experiment-only control runs and prove frozen forecasts were not changed."""
import argparse,hashlib,json,os,re,shutil
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

BRANCH='experiment/ensemble-market-validation'
PROTECTED=['priced-before-results.json','before-results-predictions.json','conditional-before-results.json','mined-before-results.json','learned-before-results.json','selection-before-results.json','match-choice-before-results.json','score-before-results.json','frozen-today-rules.json','outcome-learning.json','score-distribution.json','input-manifest.json']

def api(path):
    req=Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urlopen(req,timeout=40) as r:return json.load(r)

def select_source(runs,target,artifacts):
    name='ensemble-market-validation-'+target
    for r in runs:
        if r.get('head_branch')!=BRANCH or r.get('conclusion')!='success' or not (r.get('path')=='.github/workflows/ensemble-market-validation.yml' or (not r.get('path') and r.get('name','').startswith('Ensemble Market Validation'))):continue
        if any(a['name']==name and not a.get('expired') for a in artifacts(r['id'])):return str(r['id']),name
    return None

def configure(c,inputs,source=None):
    c=dict(c);target=inputs.get('target_date') or c['target_date'];date.fromisoformat(target);c['target_date']=target
    mode=inputs.get('mode') or ('control' if c.get('control_target_date')==target else 'daily')
    if mode not in ('daily','control'):raise ValueError('Invalid experiment mode')
    c['run_mode']=mode
    if inputs.get('published_ref'):c['published_ref']=inputs['published_ref']
    if mode=='control':
        if not source:raise ValueError('No successful frozen artifact for '+target+'; run daily predictions first')
        c['previous_run_id'],c['previous_artifact']=source
    if mode=='daily' and source:c['previous_run_id'],c['previous_artifact']=source
    assert re.fullmatch('[0-9a-f]{40}',c['published_ref']) and str(c['previous_run_id']).isdigit()
    assert re.fullmatch('ensemble-market-validation-[0-9-]+',c['previous_artifact'])
    return c

def hashes(root):return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in PROTECTED if (root/name).exists()}

def begin(previous,output,target,source_run):
    for name in ['before-results-predictions.json','learned-before-results.json']:
        path=previous/name
        if not path.exists() or json.loads(path.read_text()).get('targetDate')!=target:raise ValueError('Missing/mismatched frozen forecasts: '+name)
    for name in ['football-replay.json','basketball-replay.json','rule-mining-dataset.json']:
        if not (previous/name).exists():raise ValueError('Incomplete control artifact: '+name)
    shutil.copytree(previous,output,dirs_exist_ok=True)
    lock={'targetDate':target,'sourceRunId':str(source_run),'startedAt':datetime.now(timezone.utc).isoformat(),'hashes':hashes(output)}
    (output/'control-lock.json').write_text(json.dumps(lock,indent=2))

def verify(output):
    lock=json.loads((output/'control-lock.json').read_text());after=hashes(output)
    # Installing the separately versioned priced layer on an older artifact may add it once.
    # Existing priced snapshots remain byte-protected on every subsequent control.
    if 'priced-before-results.json' not in lock['hashes']:after.pop('priced-before-results.json',None)
    if after!=lock['hashes']:raise ValueError('Control changed frozen forecasts or fitted model files')
    lock.update({'completedAt':datetime.now(timezone.utc).isoformat(),'snapshotHashesUnchanged':True,'controlCodeSha':os.environ.get('GITHUB_SHA'),'mode':'HTTP results and settlement only; no prediction/model refit'})
    (output/'control-provenance.json').write_text(json.dumps(lock,indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['config','begin','verify']);p.add_argument('--settings',type=Path);p.add_argument('--previous',type=Path);p.add_argument('--output',type=Path);p.add_argument('--target-date');p.add_argument('--source-run');a=p.parse_args()
    if a.mode=='config':
        c=json.loads(a.settings.read_text());inputs={'mode':os.environ.get('INPUT_MODE',''),'target_date':os.environ.get('INPUT_TARGET_DATE',''),'published_ref':os.environ.get('INPUT_PUBLISHED_REF','')};target=inputs['target_date'] or c['target_date'];mode=inputs['mode'] or ('control' if c.get('control_target_date')==target else 'daily');source=None
        if mode=='control':
            run=os.environ.get('INPUT_SOURCE_RUN','')
            if run:
                if not run.isdigit():raise ValueError('Invalid source run')
                source=select_source([api('actions/runs/'+run)],target,lambda i:api(f'actions/runs/{i}/artifacts')['artifacts'])
            else:
                for page in range(1,4):
                    runs=api(f'actions/runs?branch=experiment%2Fensemble-market-validation&status=success&per_page=30&page={page}')['workflow_runs']
                    source=select_source(runs,target,lambda i:api(f'actions/runs/{i}/artifacts')['artifacts'])
                    if source:break
        if mode=='daily' and os.environ.get('INPUT_SOURCE_RUN'):
            run=os.environ['INPUT_SOURCE_RUN']
            if not run.isdigit():raise ValueError('Invalid daily source run')
            source_run=api('actions/runs/'+run)
            available=api(f'actions/runs/{run}/artifacts')['artifacts']
            candidates=sorted([x['name'] for x in available if x['name'].startswith('ensemble-market-validation-') and re.fullmatch(r'ensemble-market-validation-\d{4}-\d{2}-\d{2}',x['name']) and x['name'][-10:]<target and not x.get('expired')],reverse=True)
            if source_run.get('head_branch')!=BRANCH or source_run.get('conclusion')!='success' or source_run.get('path')!='.github/workflows/ensemble-market-validation.yml' or not candidates:raise ValueError('No verified earlier-day daily source')
            source=(run,candidates[0])
        resolved=configure(c,inputs,source)
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:
            for k in ['target_date','published_ref','previous_run_id','previous_artifact','run_mode']:f.write(f'{k}={resolved[k]}\n')
    elif a.mode=='begin':begin(a.previous,a.output,a.target_date,a.source_run)
    else:verify(a.output)
if __name__=='__main__':main()

