import importlib.util,json,tempfile,unittest
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
if __name__=='__main__':unittest.main()
