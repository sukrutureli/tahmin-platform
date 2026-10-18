"""Trusted main-only orchestration; all modelling remains on the experiment branch."""
import argparse,json,os,time,re,urllib.request,urllib.error
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

REPO='sukrutureli/tahmin-platform'
BRANCH='experiment/ensemble-market-validation'
WF='ensemble-market-validation.yml'

class Api:
    def __init__(self,token,repo=REPO):self.token=token;self.repo=repo
    def call(self,path,body=None):
        req=urllib.request.Request('https://api.github.com/repos/'+self.repo+'/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'parallel-experiment-coordinator'})
        try:
            with urllib.request.urlopen(req,timeout=40) as r:
                b=r.read();return json.loads(b) if b else None
        except urllib.error.HTTPError as e:raise RuntimeError('GitHub orchestration HTTP '+str(e.code)) from None

def target(run):
    if run.get('head_branch')!='main' or run.get('conclusion')!='success' or run.get('name') not in ['Daily Prediction','Control']:
        raise ValueError('Only successful production main runs may trigger shadow reports')
    dt=datetime.fromisoformat(run['created_at'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Istanbul'))
    control=run['name']=='Control'
    day=dt.date()-timedelta(days=1 if control and dt.hour<6 else 0)
    return ('control' if control else 'daily'),day.isoformat()

def runs(api):
    out=[]
    for page in range(1,5):
        values=api.call('actions/runs?branch=experiment%2Fensemble-market-validation&per_page=100&page='+str(page))['workflow_runs'];out.extend(values)
        if len(values)<100:break
    return out

def source(api,records,day=None,before=None):
    for r in records:
        if r.get('head_branch')!=BRANCH or r.get('conclusion')!='success' or not (r.get('path')=='.github/workflows/ensemble-market-validation.yml' or (not r.get('path') and r.get('name','').startswith('Ensemble Market Validation'))):continue
        artifacts=api.call('actions/runs/'+str(r['id'])+'/artifacts?per_page=100')['artifacts']
        for a in artifacts:
            name=a['name'];d=name.removeprefix('ensemble-market-validation-')
            if name!='ensemble-market-validation-'+d or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',d) or a.get('expired'):continue
            if (day and d==day) or (before and d<before):return str(r['id'])
    return None

def launch(api,mode,day,source_run,published,key,wait=False):
    title=f'Ensemble {mode} {day} [{key}]'
    existing=next((r for r in runs(api) if r.get('display_title')==title),None)
    if existing:
        if existing['conclusion'] not in (None,'success'):raise ValueError('Existing shadow run failed; inspect it instead of duplicating forecasts')
        run_id=existing['id']
        print('Shadow request already exists:',run_id)
    else:
        api.call('actions/workflows/'+WF+'/dispatches',{'ref':BRANCH,'inputs':{'mode':mode,'target_date':day,'source_run_id':source_run,'published_ref':published,'production_run_id':key}})
        run_id=None;print('Dispatched shadow',mode,day)
    if not wait:return run_id
    deadline=time.monotonic()+60*60
    while time.monotonic()<deadline:
        if run_id is None:
            found=next((r for r in runs(api) if r.get('display_title')==title),None)
            if found:run_id=found['id']
        else:
            r=api.call('actions/runs/'+str(run_id))
            if r['status']=='completed':
                if r['conclusion']!='success':raise ValueError('Previous-day shadow control failed')
                return str(run_id)
        time.sleep(15)
    raise TimeoutError('Previous-day shadow control did not finish within budget')

def coordinate(api,private,production_id):
    production=api.call('actions/runs/'+str(production_id));mode,day=target(production)
    published=private.call('git/ref/heads/main')['object']['sha']
    records=runs(api)
    titles={f'Ensemble {m} {day} [{production_id}]' for m in ['daily','control']}
    existing=next((r for r in records if r.get('display_title') in titles),None)
    if existing:
        if existing.get('conclusion') not in (None,'success'):raise ValueError('Existing shadow request failed; do not duplicate it')
        print('Production request already handled:',production_id);return
    current=source(api,records,day=day)
    if current:
        launch(api,'control',day,current,published,str(production_id));return
    if mode=='control':
        print('No saved shadow forecast for this control date; waiting for its daily run:',day);return
    # Never start a second daily while an earlier one for this date is running.
    if any(r.get('status') in ('queued','in_progress','waiting','pending') and r.get('display_title','').startswith('Ensemble daily '+day+' [') for r in records):
        print('Shadow daily already running for',day);return
    previous_day=(datetime.fromisoformat(day).date()-timedelta(days=1)).isoformat()
    previous=source(api,records,day=previous_day)
    if previous:
        previous=launch(api,'control',previous_day,previous,published,str(production_id)+'-previous',wait=True)
    else:previous=source(api,records,before=day)
    if not previous:raise ValueError('No verified earlier successful artifact; cannot invent the model/history seed')
    launch(api,'daily',day,previous,published,str(production_id))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--production-run',required=True);a=p.parse_args()
    if not a.production_run.isdigit():raise ValueError('Invalid production run ID')
    coordinate(Api(os.environ['GH_TOKEN']),Api(os.environ['FATHER_READ_TOKEN'],'sukrutureli/fathertahmin'),a.production_run)
