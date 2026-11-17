"""One-date repair: publish original frozen forecasts with existing CONTROL labels."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments/ensemble_validation'))
from private_reports import Api,SOURCE,DEST
import primary_control as control
from publish_primary import prepare,publish
DAY='2026-11-17';ORIGIN='43960512102';AID=14274774036
DIGEST='sha256:b33bae6c2e33ba03ac4850e1718366fa072c68abbb753433097704077e580bc6'
CONTROL='44120894257'
def verify(source):
 r=source.call(SOURCE+'/actions/runs/'+ORIGIN)
 if (r['head_sha'],r['head_branch'],r['path'],r['status'],r['conclusion'],r['run_attempt'])!=('055e438324a31e91754ddaa9b137624026590206','main','.github/workflows/ensemble-market-validation.yml','completed','failure',1):raise ValueError('Untrusted frozen source')
 jobs=source.call(SOURCE+'/actions/runs/'+ORIGIN+'/jobs?per_page=100')['jobs'];j=next(x for x in jobs if x['name']=='Primary forecast and immediate HTML')
 steps=j.get('steps',[])
 if j['conclusion']!='failure' or [s['name'] for s in steps if s['conclusion']=='failure']!=['Publish primary HTML immediately without waiting for research']:raise ValueError('Unexpected source failure')
 for n in ['Run frozen primary model without research training','Save encrypted primary forecasts before background work']:
  if not any(s['name']==n and s['conclusion']=='success' for s in steps):raise ValueError('Original forecast was not frozen')
 arts=source.call(SOURCE+'/actions/runs/'+ORIGIN+'/artifacts?per_page=100')['artifacts']
 if not any(a['id']==AID and a['name']=='primary-forecasts-'+DAY and a.get('digest')==DIGEST and not a['expired'] for a in arts):raise ValueError('Frozen checkpoint mismatch')
 cr=source.call(SOURCE+'/actions/runs/'+CONTROL);cj=source.call(SOURCE+'/actions/runs/'+CONTROL+'/jobs?per_page=100')['jobs'];control.verify_control(cr,cj)
 if control.target(cr)!=DAY:raise ValueError('Wrong CONTROL date')
 ca=source.call(SOURCE+'/actions/runs/'+CONTROL+'/artifacts?per_page=100')['artifacts']
 for aid,name,digest in [(14345262047,'football-control-public','sha256:83082f2de171bdfed8e0d3d316eb54aa072a61355f5265acaf03bc086c8bb24a'),(14345651115,'basketball-control-public','sha256:115562c8453cded037469d183c2768c567b0e42a3e93440c851be4bb3a7af3a9')]:
  if not any(a['id']==aid and a['name']==name and a.get('digest')==digest and not a['expired'] for a in ca):raise ValueError('CONTROL artifact mismatch')
def render(private):
 root=Path('pipeline-output');before=control.protected(root)
 if control.digest(root/'stability-model.json')!=control.MODEL:raise ValueError('Frozen model mismatch')
 from new_reports import reports
 manifest=reports(root)
 if control.protected(root)!=before:raise ValueError('Renderer changed forecasts')
 files,manifest=prepare(root,DAY)
 marker={'runId':os.environ['GITHUB_RUN_ID'],'rendererSha':os.environ['GITHUB_SHA'],'sourceArtifactDigest':DIGEST,'mode':'Original forecasts restored; no refitting or history collection'}
 publish(private,files,manifest,ORIGIN,AID,recovery=marker)
 ready=control.file_json(private,'raporlar/'+DAY+'/primary-ready.json')
 if (str(ready['sourceRunId']),ready['sourceArtifactId'],ready['snapshotSha256'],ready['pricedSnapshotSha256'])!=(ORIGIN,AID,manifest['snapshotSha256'],manifest['pricedSnapshotSha256']):raise ValueError('Existing primary identity changed')
 plan={'targetDate':DAY,'controlRunId':CONTROL,'origin':ready}
 result,proof=control.render(root,Path('control-football'),Path('control-basketball'),plan)
 if control.protected(root)!=before:raise ValueError('Recovery changed frozen inputs')
 control.publish(private,root,plan,result,proof,os.environ['GITHUB_SHA'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','render']);a=p.parse_args()
 if os.environ.get('GITHUB_REF')!='refs/heads/main':raise ValueError('Main recovery branch required')
 source=Api(os.environ['GH_TOKEN']);verify(source)
 if a.mode=='render':render(Api(os.environ['PRIVATE_REPORT_TOKEN']))
