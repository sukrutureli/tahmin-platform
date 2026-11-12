"""Refresh canonical mobile HTML from frozen primary forecasts and CONTROL results."""
import argparse,base64,hashlib,json,os,re,sys
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/ensemble_validation'))
from private_reports import Api,SOURCE,DEST
MODEL='35017ecf9f8992909e2f9090c8aff18c0e3c36d838312cb1202a3107c4cd61cb'
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def file_json(api,path):
 v=api.call(DEST+'/contents/'+path)
 return json.loads(base64.b64decode(v['content']))
def target(run,explicit=None):
 if explicit:
  if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',explicit):raise ValueError('Invalid control date')
  return explicit
 dt=datetime.fromisoformat(run['created_at'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Istanbul'))
 return (dt.date()-timedelta(days=int(dt.hour<6))).isoformat()
def verify_control(run,jobs):
 if run.get('path')!='.github/workflows/control.yml' or run.get('head_branch')!='main' or run.get('status')!='completed':raise ValueError('Untrusted CONTROL source')
 if run.get('head_repository',{}).get('full_name')!=SOURCE:raise ValueError('Foreign CONTROL source')
 for name in ['Football CONTROL','Basketball CONTROL']:
  if not any(j['name']==name and j['conclusion']=='success' for j in jobs):raise ValueError('CONTROL sport results incomplete')
def resolve(source,private,control_id,explicit=None):
 run=source.call(SOURCE+'/actions/runs/'+control_id)
 jobs=source.call(SOURCE+'/actions/runs/'+control_id+'/jobs?per_page=100')['jobs'];verify_control(run,jobs)
 day=target(run,explicit);today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
 if day not in {today.isoformat(),(today-timedelta(days=1)).isoformat()}:raise ValueError('Control date outside panel retention')
 arts=source.call(SOURCE+'/actions/runs/'+control_id+'/artifacts?per_page=100')['artifacts']
 for name in ['football-control-public','basketball-control-public']:
  if not any(a['name']==name and not a.get('expired') for a in arts):raise ValueError('CONTROL result artifact unavailable')
 ready=file_json(private,'raporlar/'+day+'/primary-ready.json')
 if ready.get('targetDate')!=day or ready.get('policy')!='complete-market-price-v2' or ready.get('modelSha256')!=MODEL:raise ValueError('Primary forecast identity mismatch')
 origin=str(ready['sourceRunId']);r=source.call(SOURCE+'/actions/runs/'+origin)
 if r.get('head_branch')!='main' or r.get('path')!='.github/workflows/ensemble-market-validation.yml':raise ValueError('Untrusted primary source')
 js=source.call(SOURCE+'/actions/runs/'+origin+'/jobs?per_page=100')['jobs']
 if not any(j['name']=='Primary forecast and immediate HTML' and j['conclusion']=='success' for j in js):raise ValueError('Primary forecast job was not successful')
 aa=source.call(SOURCE+'/actions/runs/'+origin+'/artifacts?per_page=100')['artifacts']
 checkpoint=next((a for a in aa if a['id']==ready['sourceArtifactId'] and a['name']=='primary-forecasts-'+day and not a.get('expired')),None)
 if not checkpoint:raise ValueError('Verified primary checkpoint unavailable')
 return {'targetDate':day,'controlRunId':control_id,'origin':ready,'checkpoint':{'runId':origin,'name':checkpoint['name'],'id':checkpoint['id'],'digest':checkpoint.get('digest')}}
def protected(root):
 return {p.name:digest(p) for p in root.glob('*.json') if 'before-results' in p.name or p.name.startswith('primary-context-') or p.name in ['stability-model.json','input-manifest.json','rule-mining-dataset.json']}
def results_file(root,folder,day):
 p=root/folder/'data'/('RealScores-'+day+'.json')
 if not p.is_file() or p.is_symlink():raise ValueError('Exact-dated CONTROL results missing')
 return p
def apply_results(rows,scores,day):
 mapped={}
 for item in scores:
  score=item.get('score','');eid=str(item.get('eventId',''))
  if not eid or not re.fullmatch(r'\d+\s*-\s*\d+',score):continue
  h,a=map(int,re.split(r'\s*-\s*',score))
  if max(h,a)>500:raise ValueError('Invalid final score')
  normalized=f'{h}-{a}'
  if eid in mapped and mapped[eid]!=normalized:raise ValueError('Conflicting final scores')
  mapped[eid]=normalized
 count=0
 for row in rows:
  if row.get('date')!=day:continue
  eid=str(row.get('eventId',''))
  if eid in mapped:
   row['realScore']=mapped[eid];row['resultSource']='live HTTP finished scoreboard';count+=1
 return count
def render(root,control_football,control_basketball,plan):
 day=plan['targetDate'];before=protected(root)
 if digest(root/'stability-model.json')!=plan['origin']['modelSha256']:raise ValueError('Frozen model mismatch')
 import locked_stability as locked
 config=read(Path(locked.__file__).with_name('stability-settings.json'))
 book=locked.verify_snapshot(root,config)
 if book['targetDate']!=day:raise ValueError('Frozen day mismatch')
 counts={};input_hashes={}
 for sport,folder,source_root in [('football','futbol',control_football),('basketball','basketbol',control_basketball)]:
  path=results_file(source_root,folder,day);input_hashes[sport]=digest(path)
  replay=root/(sport+'-replay.json');rows=read(replay)
  counts[sport]=apply_results(rows,read(path),day);write(replay,rows)
 from complete_prices import settle
 evaluation=settle(root)
 if evaluation['snapshotSha256']!=plan['origin']['pricedSnapshotSha256']:raise ValueError('Frozen selections changed')
 from new_reports import reports
 manifest=reports(root)
 if protected(root)!=before:raise ValueError('CONTROL modified frozen forecast/model inputs')
 return manifest,{'controlResultRows':counts,'resultFileSha256':input_hashes,'immutableForecastsUnchanged':True,'protectedSha256':before}
def publish(private,root,plan,manifest,proof,renderer_sha,today=None):
 from publish_primary import prepare
 files,checked=prepare(root,plan['targetDate'])
 day=plan['targetDate'];today=today or datetime.now(ZoneInfo('Europe/Istanbul')).date()
 if day not in {today.isoformat(),(today-timedelta(days=1)).isoformat()}:raise ValueError('Panel retention changed')
 prefix='raporlar/'+day+'/'
 if set(files)!={'futbol.html','basketbol.html'}:raise ValueError('Unexpected canonical outputs')
 for attempt in range(4):
  if private.call(DEST).get('private') is not True:raise ValueError('Panel repository must remain private')
  head=private.call(DEST+'/git/ref/heads/main')['object']['sha'];tree=private.call(DEST+'/git/commits/'+head)['tree']['sha']
  entries=private.call(DEST+'/git/trees/'+tree+'?recursive=1')
  if entries.get('truncated'):raise ValueError('Incomplete output tree')
  existing={x['path']:x for x in entries['tree']}
  ready=file_json(private,prefix+'primary-ready.json')
  if (ready['sourceRunId'],ready['snapshotSha256'],ready['pricedSnapshotSha256'])!=(plan['origin']['sourceRunId'],plan['origin']['snapshotSha256'],plan['origin']['pricedSnapshotSha256']):raise ValueError('Primary forecast changed during CONTROL')
  if prefix+'primary-control.json' in existing:
   old=file_json(private,prefix+'primary-control.json')
   if int(old['controlRunId'])>int(plan['controlRunId']):return False
   if old['controlRunId']==plan['controlRunId'] and old.get('rendererSha')==renderer_sha:return False
  stamp={'targetDate':day,'controlRunId':plan['controlRunId'],'rendererSha':renderer_sha,'workflowRunId':os.environ.get('GITHUB_RUN_ID'),'updatedAt':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'sourceRunId':plan['origin']['sourceRunId'],'sourceArtifactId':plan['origin']['sourceArtifactId'],'modelSha256':manifest['modelSha256'],'pricedSnapshotSha256':manifest['pricedSnapshotSha256'],'reports':manifest['reports'],**proof}
  output={prefix+n:s for n,s in files.items()};output[prefix+'primary-control.json']=json.dumps(stamp,ensure_ascii=False,separators=(',',':'))+'\n'
  if any(p not in {prefix+'futbol.html',prefix+'basketbol.html',prefix+'primary-control.json'} for p in output):raise ValueError('Canonical path violation')
  updates=[]
  for path,text in output.items():
   b=text.encode();blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
   if existing.get(path,{}).get('sha')!=blob:updates.append({'path':path,'mode':'100644','type':'blob','content':text})
  if not updates:return False
  nt=private.call(DEST+'/git/trees','POST',{'base_tree':tree,'tree':updates})['sha']
  nc=private.call(DEST+'/git/commits','POST',{'message':'Refresh primary HTML from CONTROL '+plan['controlRunId']+' ('+day+')','tree':nt,'parents':[head]})['sha']
  try:private.call(DEST+'/git/refs/heads/main','PATCH',{'sha':nc,'force':False});return True
  except RuntimeError:
   if attempt==3:raise
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['resolve','render']);p.add_argument('--control-run');p.add_argument('--date');a=p.parse_args()
 source=Api(os.environ['GH_TOKEN']);private=Api(os.environ['PRIVATE_REPORT_TOKEN'])
 if a.mode=='resolve':
  if not a.control_run or not a.control_run.isdigit():raise ValueError('Invalid CONTROL id')
  plan=resolve(source,private,a.control_run,a.date);write('primary-control-plan.json',plan)
  with open(os.environ['GITHUB_OUTPUT'],'a') as out:
   out.write('control_run='+plan['controlRunId']+'\ndate='+plan['targetDate']+'\norigin_run='+plan['checkpoint']['runId']+'\norigin_name='+plan['checkpoint']['name']+'\n')
 else:
  plan=read('primary-control-plan.json');root=Path('pipeline-output')
  manifest,proof=render(root,Path('control-football'),Path('control-basketball'),plan)
  changed=publish(private,root,plan,manifest,proof,os.environ['GITHUB_SHA'])
  print('Primary CONTROL HTML '+('updated' if changed else 'already current')+'; frozen forecasts preserved.')
if __name__=='__main__':main()
