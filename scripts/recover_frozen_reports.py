"""One-off settlement of explicitly verified frozen checkpoints; no model fitting."""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
from urllib.request import Request,urlopen
REPO='sukrutureli/tahmin-platform'
DEST='sukrutureli/fathertahmin'
CODE='be2074e5905c6cc52e95985555ed9614010ca9ab'
BRANCH='refs/heads/experiment/ensemble-market-validation'
MODEL='35017ecf9f8992909e2f9090c8aff18c0e3c36d838312cb1202a3107c4cd61cb'
ALLOWED={
 '2026-11-11':('42903532498',13804629578,'frozen-forecasts-2026-11-11','6976ff1c9b912a1ef2bda2d0dbb64d41902ff0e6c19a9affae11a590b75cbd90'),
 '2026-11-12':('43100338146',13891848797,'primary-forecasts-2026-11-12','f70ac56302d89eed0e4016e391c9c63f345f0e36d7645c47b21c90600c016089')}
JSON_REPORTS=['priced-complete-evaluation.json','priced-evaluation.json','daily-evaluation.json','context-evaluation.json','stability-evaluation.json','score-research-evaluation.json','competition-evaluation.json']
HTML_REPORTS=['futbol-yeni.html','basketbol-yeni.html','day-by-day.html']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def api(path,repo=REPO,token=None,method='GET',body=None):
 token=token or os.environ['GH_TOKEN']
 req=Request('https://api.github.com/repos/'+repo+'/'+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'frozen-checkpoint-recovery'})
 with urlopen(req,timeout=50) as r:
  b=r.read();return json.loads(b) if b else None
def source_spec(date,request):
 if date not in ALLOWED:raise ValueError('Unapproved recovery date')
 spec=ALLOWED[date];v=request['sources'][date]
 if (str(v['runId']),int(v['artifactId']),v['artifactName'],v['artifactSha256'])!=spec:raise ValueError('Recovery source changed')
 if request['codeRef']!=CODE or request['previousRunId']!='42920219240' or request['previousArtifactId']!=13812246535:raise ValueError('Recovery parent changed')
 return spec
def verify(date,request):
 if os.environ.get('GITHUB_REF')!=BRANCH:raise ValueError('Recovery branch mismatch')
 run,aid,name,digest=source_spec(date,request)
 r=api('actions/runs/'+run)
 if (r['path']!='.github/workflows/ensemble-market-validation.yml' or r['head_branch']!='main' or r['head_sha']!=CODE or r['status']!='completed' or r['conclusion']!='failure' or r['run_attempt']!=1):raise ValueError('Unverified source run')
 jobs=api('actions/runs/'+run+'/jobs?per_page=100')['jobs']
 primary=next(j for j in jobs if j['name']=='Primary forecast and immediate HTML')
 research=next(j for j in jobs if j['name']=='Background research and outcome reports')
 if primary['conclusion']!='success' or research['conclusion']!='failure':raise ValueError('Unexpected failure stage')
 if date=='2026-11-11' and not any(s['name']=='Save immutable forecasts before HTTP settlement' and s['conclusion']=='success' for s in research['steps']):raise ValueError('Full frozen checkpoint not completed')
 arts=api('actions/runs/'+run+'/artifacts?per_page=100')['artifacts']
 a=next(x for x in arts if x['id']==aid)
 if a['expired'] or a['name']!=name or a.get('digest')!='sha256:'+digest:raise ValueError('Artifact provenance mismatch')
 parent=api('actions/runs/'+request['previousRunId'])
 if parent['conclusion']!='success' or parent['path']!='.github/workflows/ensemble-market-validation.yml' or parent['head_sha']!=CODE:raise ValueError('Unverified preceding journal run')
 pa=api('actions/runs/'+request['previousRunId']+'/artifacts?per_page=100')['artifacts']
 if not any(x['id']==13812246535 and x['name']=='ensemble-market-validation-2026-11-10' and not x['expired'] for x in pa):raise ValueError('Preceding artifact missing')
 with open(os.environ['GITHUB_OUTPUT'],'a') as out:
  out.write('source_run='+run+'\nsource_name='+name+'\n')
def protected(root):
 names=[p for p in root.glob('*.json') if 'before-results' in p.name or p.name.startswith('primary-context-') or p.name in ['stability-model.json','frozen-today-rules.json','outcome-learning.json','score-distribution.json','input-manifest.json','rule-mining-dataset.json']]
 return {p.name:sha(p) for p in names}
def check_lock(root):
 if protected(root)!=read(root/'recovery-lock.json')['hashes']:raise ValueError('Recovery modified immutable forecast/model inputs')
def lock(root,date,request):
 source_spec(date,request)
 if sha(root/'stability-model.json')!=MODEL:raise ValueError('Model hash mismatch')
 for n in ['priced-complete-before-results.json','stability-before-results.json']:
  if read(root/n)['targetDate']!=date:raise ValueError('Frozen target mismatch')
 write(root/'recovery-lock.json',{'targetDate':date,'hashes':protected(root),'source':request['sources'][date],'publishedRef':request['publishedRef']})
def settle(root,previous,date):
 sys.path.insert(0,str(Path('experiments/ensemble_validation').resolve()))
 import locked_stability as locked
 import complete_prices,priced_choices
 locked.settle(root,previous,date,read(Path(locked.__file__).with_name('stability-settings.json')))
 complete_prices.settle(root);priced_choices.settle(root)
 commands=[
  ('before-results-predictions.json',['daybook.py','settle','--output',str(root),'--previous',str(previous)]),
  ('context-before-results.json',['context_experiment.py','settle','--output',str(root),'--target-date',date]),
  ('score-research-before-results.json',['score_research.py','settle','--output',str(root)]),
  ('competition-before-results.json',['competition_blend.py','settle','--output',str(root)])]
 for marker,cmd in commands:
  if (root/marker).exists():subprocess.run([sys.executable,'experiments/ensemble_validation/'+cmd[0],*cmd[1:]],check=True)
 from new_reports import reports
 reports(root)
 check_lock(root)
 provenance=read(root/'recovery-lock.json')
 provenance.update({'immutableForecastsUnchanged':True,'codeRef':CODE,'mode':'Existing frozen forecasts and finished HTTP outcomes only; no fit, forecast generation or history scan','unavailableResearch':[] if (root/'context-before-results.json').exists() else ['Original background research was not frozen; no replacement predictions generated.']})
 write(root/'recovery-provenance.json',provenance)
def report_files(root,date):
 sys.path.insert(0,str(Path('experiments/ensemble_validation').resolve()))
 from private_reports import compact,SNAPSHOTS
 out={}
 for n in JSON_REPORTS:
  p=root/n
  if not p.exists():continue
  v=read(p)
  if v.get('targetDate',v.get('date'))!=date:continue
  out[n]=json.dumps(compact(v),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
 for n in HTML_REPORTS:
  p=root/n
  if p.exists() and n!='day-by-day.html':out[n]=p.read_text()
 # Snapshot membership and raw inputs stay encrypted.
 ix=[]
 for n in SNAPSHOTS:
  p=root/n
  if p.exists():
   v=read(p)
   if v.get('targetDate',v.get('date'))==date:ix.append({'file':n,'sha256':sha(p),**{k:v[k] for k in ['targetDate','date','createdAt','modelSha256'] if k in v}})
 out['recovery-snapshot-index.json']=json.dumps(ix,ensure_ascii=False,separators=(',',':'))+'\n'
 out['recovery-provenance.json']=json.dumps(read(root/'recovery-provenance.json'),ensure_ascii=False,separators=(',',':'))+'\n'
 return out
def validate_paths(paths,date):
 allowed=set(JSON_REPORTS+HTML_REPORTS+['recovery-snapshot-index.json','recovery-provenance.json','recovery-checkpoint-manifest.json'])
 for p in paths:
  if p=='deney/current/recovery-checkpoint-manifest.json':continue
  prefix='deney/reports/'+date+'/'
  if not p.startswith(prefix) or p[len(prefix):] not in allowed:raise ValueError('Forbidden destination path')
def publish(root,date,request):
 check_lock(root);source_spec(date,request);files=report_files(root,date)
 arts=api('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/artifacts?per_page=100')['artifacts']
 name='frozen-recovery-'+date
 a=next(x for x in arts if x['name']==name and not x['expired'])
 manifest={'targetDate':date,'sourceRunId':os.environ['GITHUB_RUN_ID'],'sourceSha':os.environ['GITHUB_SHA'],'sourceWorkflow':'.github/workflows/recover-frozen-reports.yml','sourceArtifact':name,'sourceArtifactId':a['id'],'artifactDigest':a.get('digest'),'artifactUrl':'https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID']+'/artifacts/'+str(a['id']),'frozenSource':request['sources'][date],'codeRef':CODE,'modelSha256':MODEL,'policy':'complete-market-price-v2','immutableForecastsUnchanged':True,'partialResearch':date=='2026-11-12','reports':{n:{'sha256':hashlib.sha256(v.encode()).hexdigest(),'bytes':len(v.encode())} for n,v in files.items()}}
 text=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
 files['recovery-checkpoint-manifest.json']=text
 changes={'deney/reports/'+date+'/'+n:v for n,v in files.items()}
 changes['deney/current/recovery-checkpoint-manifest.json']=text
 validate_paths(changes,date)
 if any(len(v.encode())>2*1024*1024 for v in changes.values()) or sum(len(v.encode()) for v in changes.values())>6*1024*1024:raise ValueError('Report package too large')
 token=os.environ['PRIVATE_REPORT_TOKEN']
 if api('',DEST,token)['private'] is not True:raise ValueError('Destination must remain private')
 for attempt in range(4):
  head=api('git/ref/heads/main',DEST,token)['object']['sha']
  tree=api('git/commits/'+head,DEST,token)['tree']['sha']
  entries=api('git/trees/'+tree+'?recursive=1',DEST,token)
  if entries.get('truncated'):raise ValueError('Incomplete private tree')
  existing={e['path']:e for e in entries['tree']}
  updates=[]
  for p,v in changes.items():
   raw=v.encode();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
   if existing.get(p,{}).get('sha')!=blob:updates.append({'path':p,'mode':'100644','type':'blob','content':v})
  if not updates:return
  validate_paths([x['path'] for x in updates],date)
  nt=api('git/trees',DEST,token,'POST',{'base_tree':tree,'tree':updates})['sha']
  nc=api('git/commits',DEST,token,'POST',{'message':'Recover frozen experiment reports '+date,'tree':nt,'parents':[head]})['sha']
  try:
   api('git/refs/heads/main',DEST,token,'PATCH',{'sha':nc,'force':False});return
  except Exception:
   if attempt==3:raise
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','lock','settle','publish']);p.add_argument('--request',type=Path,required=True);p.add_argument('--date',required=True);p.add_argument('--root',type=Path,default=Path('pipeline-output'));p.add_argument('--previous',type=Path,default=Path('previous'));a=p.parse_args();req=read(a.request)
 source_spec(a.date,req)
 if a.mode=='verify':verify(a.date,req)
 elif a.mode=='lock':lock(a.root,a.date,req)
 elif a.mode=='settle':settle(a.root,a.previous,a.date)
 else:publish(a.root,a.date,req)
if __name__=='__main__':main()
