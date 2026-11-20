import copy,importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('recovery',str(Path(__file__).with_name('recover_frozen_reports.py')))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RecoveryTests(unittest.TestCase):
 def request(self):
  return {'codeRef':m.CODE,'previousRunId':'44470729009','previousArtifactId':14503948600,'previousArtifact':'frozen-recovery-2026-11-19','sources':{d:{'runId':v[0],'artifactId':v[1],'artifactName':v[2],'artifactSha256':v[3]} for d,v in m.ALLOWED.items()}}
 def test_only_private_report_paths(self):
  for day in m.ALLOWED:
   m.validate_paths(['deney/reports/'+day+'/priced-complete-evaluation.json','deney/current/recovery-checkpoint-manifest.json'],day)
   for path in ['raporlar/'+day+'/futbol.html','.github/workflows/control.yml','deney/current/checkpoint-manifest.json','deney/reports/'+day+'/../../futbol.html']:
    with self.assertRaises(ValueError):m.validate_paths([path],day)
 def test_frozen_change_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'priced-complete-before-results.json').write_text('old');m.write(root/'recovery-lock.json',{'hashes':m.protected(root)});m.check_lock(root)
   (root/'priced-complete-before-results.json').write_text('new')
   with self.assertRaises(ValueError):m.check_lock(root)
 def test_source_and_parent_tamper_rejected(self):
  req=self.request()
  for day in m.ALLOWED:
   self.assertEqual(m.source_spec(day,req),m.ALLOWED[day])
   bad=copy.deepcopy(req);bad['sources'][day]['artifactId']+=1
   with self.assertRaises(ValueError):m.source_spec(day,bad)
   bad=copy.deepcopy(req);bad['previousArtifactId']+=1
   with self.assertRaises(ValueError):m.source_spec(day,bad)
 def research_failure_jobs(self):
  return [{'name':m.EXPECTED['2026-11-20'][4],'conclusion':'success','steps':[]},{'name':'Background research and outcome reports','conclusion':'failure','steps':[{'name':'Discover and freeze two-condition history rules (shadow only)','conclusion':'failure'}]}]
 def test_primary_failure_or_unexpected_research_failure_rejected(self):
  jobs=self.research_failure_jobs();m.verify_source_jobs('2026-11-20',jobs)
  bad=copy.deepcopy(jobs);bad[0]['conclusion']='failure'
  with self.assertRaises(ValueError):m.verify_source_jobs('2026-11-20',bad)
  bad=copy.deepcopy(jobs);bad[1]['steps'][0]['name']='Other failure'
  with self.assertRaises(ValueError):m.verify_source_jobs('2026-11-20',bad)
 def test_verified_download_outputs_are_separate_lines(self):
  req=self.request()
  for day,spec in m.ALLOWED.items():
   run,aid,name,digest=spec
   def fake(path):
    if path=='actions/runs/999':return {'head_sha':'current','path':'.github/workflows/recover-frozen-reports.yml','head_branch':'experiment/ensemble-market-validation'}
    if path=='actions/runs/999/jobs?per_page=100':return {'jobs':[{'name':'Settle frozen 2026-11-19','conclusion':'success'}]}
    if path=='actions/runs/999/artifacts?per_page=100':return {'artifacts':[{'name':'frozen-recovery-2026-11-19','expired':False,'digest':'sha256:'+'a'*64}]}
    if path.endswith('/jobs?per_page=100'):
     jobs=[{'name':m.EXPECTED[day][4],'conclusion':'success'}]
     if day=='2026-11-20':jobs=self.research_failure_jobs()
     return {'jobs':jobs}
    if path.endswith('/artifacts?per_page=100'):
     v=m.ALLOWED['2026-11-19'] if '/44470729009/' in path else spec
     return {'artifacts':[{'id':v[1],'name':v[2],'digest':'sha256:'+v[3],'expired':False}]}
    e=m.EXPECTED['2026-11-19'] if path.endswith('/44470729009') else m.EXPECTED[day]
    return dict(zip(['head_sha','path','head_branch','conclusion'],e[:4]),status='completed',run_attempt=1)
   with tempfile.TemporaryDirectory() as td:
    output=Path(td)/'outputs'
    with patch.dict(os.environ,{'GITHUB_REF':m.BRANCH,'GITHUB_OUTPUT':str(output),'GITHUB_RUN_ID':'999','GITHUB_SHA':'current'}),patch.object(m,'api',side_effect=fake):m.verify(day,req)
    self.assertEqual(output.read_text().splitlines(),['source_run='+run,'source_name='+name,'resume=false','previous_run='+('999' if day=='2026-11-20' else req['previousRunId']),'previous_name=frozen-recovery-2026-11-19'])
if __name__=='__main__':unittest.main()





