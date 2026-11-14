import importlib.util,json,tempfile,unittest,os
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('recovery',str(Path(__file__).with_name('recover_frozen_reports.py')))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RecoveryTests(unittest.TestCase):
 def test_only_private_report_paths(self):
  for day in ['2026-11-13','2026-11-14']:
   m.validate_paths(['deney/reports/'+day+'/priced-complete-evaluation.json','deney/current/recovery-checkpoint-manifest.json'],day)
   for path in ['raporlar/'+day+'/futbol.html','.github/workflows/control.yml','deney/current/checkpoint-manifest.json','deney/reports/'+day+'/../../futbol.html']:
    with self.assertRaises(ValueError):m.validate_paths([path],day)
 def test_frozen_change_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'priced-complete-before-results.json').write_text('old')
   m.write(root/'recovery-lock.json',{'hashes':m.protected(root)});m.check_lock(root)
   (root/'priced-complete-before-results.json').write_text('new')
   with self.assertRaises(ValueError):m.check_lock(root)
 def test_source_tamper_rejected(self):
  req={'sources':{},'codeRef':m.CODE,'previousRunId':'42920219240','previousArtifactId':13812246535}
  for day,s in m.ALLOWED.items():
   req['sources'][day]={'runId':s[0],'artifactId':s[1],'artifactName':s[2],'artifactSha256':s[3]}
   self.assertEqual(m.source_spec(day,req),s)
   req['sources'][day]['artifactId']+=1
   with self.assertRaises(ValueError):m.source_spec(day,req)
 def test_verified_download_outputs_are_separate_lines(self):
  day='2026-11-13';run,aid,name,digest=m.ALLOWED[day]
  request={'codeRef':m.CODE,'previousRunId':'42920219240','previousArtifactId':13812246535,'sources':{day:{'runId':run,'artifactId':aid,'artifactName':name,'artifactSha256':digest}}}
  def fake(path):
   if path=='actions/runs/'+run:return {'head_sha':'0239f0b4fdb0898f1e1a268765a834e15972c407','path':'.github/workflows/recover-primary-2026-11-13.yml','head_branch':'experiment/ensemble-market-validation','conclusion':'success','status':'completed','run_attempt':1}
   if path.endswith(run+'/jobs?per_page=100'):return {'jobs':[{'name':'Freeze primary forecasts and publish HTML','conclusion':'success'}]}
   if path.endswith(run+'/artifacts?per_page=100'):return {'artifacts':[{'id':aid,'name':name,'digest':'sha256:'+digest,'expired':False}]}
   if path=='actions/runs/42920219240':return {'conclusion':'success','path':'.github/workflows/ensemble-market-validation.yml','head_sha':m.CODE}
   return {'artifacts':[{'id':13812246535,'name':'ensemble-market-validation-2026-11-10','digest':'sha256:05622f4adf8ad7c8383627c88a434d15eed6f8dd9314ae6faa0992864194387c','expired':False}]}
  with tempfile.TemporaryDirectory() as td:
   output=Path(td)/'outputs'
   with patch.dict(os.environ,{'GITHUB_REF':m.BRANCH,'GITHUB_OUTPUT':str(output)}),patch.object(m,'api',side_effect=fake):m.verify(day,request)
   self.assertEqual(output.read_text().splitlines(),['source_run='+run,'source_name='+name,'resume=false'])
if __name__=='__main__':unittest.main()
