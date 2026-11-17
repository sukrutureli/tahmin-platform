"""Publish only ready primary HTML, backed by an encrypted forecast checkpoint."""
import argparse,hashlib,json,os,re,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from private_reports import Api,SOURCE,DEST

def prepare(root,target):
    root=Path(root);manifest=json.loads((root/'new-report-manifest.json').read_text())
    if manifest['targetDate']!=target or manifest['selectionPolicy']!='complete-market-price-v2':raise ValueError('Primary identity mismatch')
    if manifest['modelSha256']!=hashlib.sha256((root/'stability-model.json').read_bytes()).hexdigest():raise ValueError('Model hash mismatch')
    files={}
    for sport in ('futbol','basketbol'):
        data=(root/(sport+'-yeni.html')).read_bytes()
        if len(data)>4*1024*1024 or hashlib.sha256(data).hexdigest()!=manifest['reports'][sport]['sha256']:raise ValueError('Primary HTML digest mismatch')
        files[sport+'.html']=data.decode()
    return files,manifest

def find_checkpoint(source,run_id,target,attempts=6,sleep=time.sleep):
    """The run-artifact index can lag a successful upload; wait, never refreeze."""
    for attempt in range(attempts):
        artifacts=source.call(SOURCE+'/actions/runs/'+run_id+'/artifacts?per_page=100')['artifacts']
        matches=[a for a in artifacts if a['name']=='primary-forecasts-'+target and not a.get('expired')]
        if len(matches)>1:raise ValueError('Ambiguous primary forecast checkpoint')
        if matches:return matches[0]
        if attempt+1<attempts:sleep(min(2**(attempt+1),30))
    raise RuntimeError('Encrypted primary checkpoint is not yet visible; retry publication without regenerating forecasts')

def publish(api,files,manifest,run_id,artifact_id,today=None,recovery=None):
    target=manifest['targetDate'];today=today or datetime.now(ZoneInfo('Europe/Istanbul')).date()
    if target not in {today.isoformat(),(today-timedelta(days=1)).isoformat()}:raise ValueError('Primary date outside retention')
    ready={'targetDate':target,'sourceRunId':run_id,'sourceArtifactId':artifact_id,'modelSha256':manifest['modelSha256'],
           'snapshotSha256':manifest['snapshotSha256'],'pricedSnapshotSha256':manifest['pricedSnapshotSha256'],'policy':manifest['selectionPolicy'],
           'stage':'Forecast ready; research and fresh outcome settlement may still be running','reports':manifest['reports']}
    if recovery:ready['publicationRecovery']=recovery
    prefix='raporlar/'+target+'/'
    for attempt in range(3):
        if api.call(DEST).get('private') is not True:raise ValueError('Primary output destination must be private')
        head=api.call(DEST+'/git/ref/heads/main')['object']['sha'];tree=api.call(DEST+'/git/commits/'+head)['tree']['sha']
        entries=api.call(DEST+'/git/trees/'+tree+'?recursive=1')
        if entries.get('truncated'):raise ValueError('Incomplete primary output tree')
        # An existing final/report or ready forecast is never replaced with a second daily prediction.
        if any(x['path'] in (prefix+'primary-ready.json','deney/reports/'+target+'/checkpoint-manifest.json') for x in entries['tree']):return False
        output=dict(files);output['primary-ready.json']=json.dumps(ready,ensure_ascii=False)+'\n'
        updates=[{'path':prefix+n,'type':'blob','mode':'100644','content':s} for n,s in output.items()]
        newtree=api.call(DEST+'/git/trees','POST',{'base_tree':tree,'tree':updates})['sha']
        commit=api.call(DEST+'/git/commits','POST',{'message':'Primary forecast HTML ready '+target,'tree':newtree,'parents':[head]})['sha']
        try:api.call(DEST+'/git/refs/heads/main','PATCH',{'sha':commit,'force':False});return True
        except RuntimeError:
            if attempt==2:raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--target-date',required=True);a=p.parse_args()
    run_id=os.environ['GITHUB_RUN_ID'];source=Api(os.environ['REPORT_SOURCE_TOKEN']);run=source.call(SOURCE+'/actions/runs/'+run_id)
    if run.get('head_branch')!='main' or run.get('path')!='.github/workflows/ensemble-market-validation.yml' or run.get('status')!='in_progress':raise ValueError('Untrusted primary run')
    checkpoint=find_checkpoint(source,run_id,a.target_date)
    files,manifest=prepare(a.output,a.target_date)
    publish(Api(os.environ['PRIVATE_REPORT_TOKEN']),files,manifest,run_id,checkpoint['id'])

