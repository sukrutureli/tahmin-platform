import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('recovery',str(Path(__file__).with_name('recover_frozen_reports.py')))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RecoveryTests(unittest.TestCase):
 def test_only_private_report_paths(self):
  m.validate_paths(['deney/reports/2026-11-11/priced-complete-evaluation.json','deney/current/recovery-checkpoint-manifest.json'],'2026-11-11')
  for p in ['raporlar/2026-11-11/futbol.html','.github/workflows/control.yml','deney/current/checkpoint-manifest.json','deney/reports/2026-11-12/priced-complete-evaluation.json','deney/reports/2026-11-11/../../futbol.html']:
   with self.assertRaises(ValueError):m.validate_paths([p],'2026-11-11')
 def test_changed_frozen_forecast_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'priced-complete-before-results.json').write_text('{"choice":"old"}')
   m.write(root/'recovery-lock.json',{'hashes':m.protected(root)})
   m.check_lock(root)
   (root/'priced-complete-before-results.json').write_text('{"choice":"new"}')
   with self.assertRaises(ValueError):m.check_lock(root)
 def test_unapproved_source_rejected(self):
  req={'sources':{},'codeRef':m.CODE,'previousRunId':'42920219240','previousArtifactId':13812246535}
  for date,s in m.ALLOWED.items():
   req['sources'][date]={'runId':s[0],'artifactId':s[1],'artifactName':s[2],'artifactSha256':s[3]}
   self.assertEqual(m.source_spec(date,req),s)
   bad=copy.deepcopy(req);bad['sources'][date]['artifactId']+=1
   with self.assertRaises(ValueError):m.source_spec(date,bad)
  with self.assertRaises(ValueError):m.source_spec('2026-11-13',req)
if __name__=='__main__':unittest.main()
