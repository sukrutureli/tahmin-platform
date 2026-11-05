"""Private-only orchestration for one isolated history-input trial."""
import argparse,hashlib,json,os,re
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from private_reports import Api,SOURCE,DEST,encoded,compact
from priced_choices import read,write
import history_context_trial as trial

BRANCH='experiment/history-context-2026-11-06'
def verify_source(api,request):
    run=api.call(SOURCE+'/actions/runs/'+str(request['sourceRunId']))
    if run.get('conclusion')!='success' or run.get('path')!='.github/workflows/ensemble-market-validation.yml':raise ValueError('Source must be a successful primary/research checkpoint')
    artifacts=api.call(SOURCE+'/actions/runs/'+str(request['sourceRunId'])+'/artifacts?per_page=100')['artifacts']
    if not any(str(a['id'])==str(request['sourceArtifactId']) and a['name']=='ensemble-market-validation-'+request['targetDate'] and not a['expired'] for a in artifacts):raise ValueError('Missing authenticated source artifact')

def publish(api,root,out,request):
    if api.call(DEST).get('private') is not True:raise ValueError('Private destination required')
    b=read(out/trial.FILE);target=b['targetDate'];today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
    files={'deney/reports/'+target+'/history-context-evaluation.json':(out/'history-context-evaluation.json').read_text()}
    if target in {today.isoformat(),(today-timedelta(days=1)).isoformat()}:
        files['raporlar/'+target+'/gecmis-baglam-deneyi.html']=(out/'gecmis-baglam-deneyi.html').read_text()
    # Copy only pre-existing small summaries; never disclose datasets/forecasts in the public repo.
    others={}
    for name in ['priced-complete-evaluation.json','competition-evaluation.json','score-research-evaluation.json']:
        p=root/name
        if p.exists():others[name]=compact(read(p))
    summary={'targetDate':target,'trialVersion':trial.VERSION,'sourceRunId':request['sourceRunId'],
             'trialRunId':os.environ['GITHUB_RUN_ID'],'freezeRunId':request.get('freezeRunId') or os.environ['GITHUB_RUN_ID'],
             'freezeSourceRunId':request.get('freezeSourceRunId',request['sourceRunId']),
             'snapshotSha256':trial.digest(out/trial.FILE),'modelSha256':b['modelSha256'],
             'otherExperiments':others,'policy':'Policies/cohorts are separate; no automatic promotion; raw snapshots stay encrypted.',
             'reports':{p:{'sha256':hashlib.sha256(v.encode()).hexdigest(),'bytes':len(v.encode())} for p,v in files.items()}}
    files['deney/reports/'+target+'/history-context-checkpoint.json']=encoded(summary)
    for attempt in range(3):
        head=api.call(DEST+'/git/ref/heads/main')['object']['sha'];tree=api.call(DEST+'/git/commits/'+head)['tree']['sha']
        entries=[{'path':p,'mode':'100644','type':'blob','content':v} for p,v in files.items()]
        tree_sha=api.call(DEST+'/git/trees','POST',{'base_tree':tree,'tree':entries})['sha']
        commit=api.call(DEST+'/git/commits','POST',{'message':'Private history context trial '+target,'tree':tree_sha,'parents':[head]})['sha']
        try:api.call(DEST+'/git/refs/heads/main','PATCH',{'sha':commit,'force':False});return
        except RuntimeError:
            if attempt==2:raise

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','run','publish']);a=p.parse_args()
    req=read('.github/history-context-request.json');root=Path('trial-source');out=Path('trial-output')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',req['targetDate']):raise ValueError('Invalid date')
    api=Api(os.environ['GH_TOKEN'])
    if a.mode=='verify':
        verify_source(api,req)
        if req['mode']=='settle':
            run=api.call(SOURCE+'/actions/runs/'+str(req['freezeRunId']))
            if run.get('conclusion')!='success' or run.get('head_branch')!=BRANCH:raise ValueError('Missing successful original frozen trial')
        return
    if a.mode=='run':
        import locked_stability as locked
        locked.verify_snapshot(root,read(Path(locked.__file__).with_name('stability-settings.json')))
        if read(root/'priced-complete-before-results.json')['targetDate']!=req['targetDate']:raise ValueError('Source day mismatch')
        before={name:trial.digest(root/name) for name in ['stability-model.json','stability-before-results.json','priced-before-results.json','priced-complete-before-results.json','competition-before-results.json','score-research-before-results.json'] if (root/name).exists()}
        if req['mode']=='freeze':
            if before['priced-complete-before-results.json']!=req['pricedSourceSha256']:raise ValueError('Source snapshot hash differs from private index')
            trial.freeze(root,out)
        else:
            if not (out/trial.FILE).exists():raise ValueError('Original trial checkpoint required for settlement')
            # The current source can contain refreshed labels, never new candidate forecasts.
            if read(out/trial.FILE)['targetDate']!=req['targetDate']:raise ValueError('Settlement day mismatch')
        trial.seal_eligibility(Path('trial-origin') if Path('trial-origin').exists() else root,out)
        trial.settle(root,out)
        if any(trial.digest(root/name)!=value for name,value in before.items()):raise ValueError('Production forecast/model modified')
        return
    publish(api,root,out,req)
if __name__=='__main__':main()
