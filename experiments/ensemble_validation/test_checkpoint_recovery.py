import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from control_runtime import checkpoint_source,configure
class CheckpointRecoveryTests(unittest.TestCase):
 def test_pinned_checkpoint_requires_all_provenance_guards(self):
  original=json.loads((Path(__file__).parent/'source-fixture.json').read_text())
  def check(data):
   def api(path):
    return data['jobs'] if '/jobs?' in path else data['artifacts'] if path.endswith('/artifacts') else data['run']
   with patch('control_runtime.api',side_effect=api):return checkpoint_source('40955966396','2026-10-30')
  self.assertEqual(check(original),('40955966396','frozen-forecasts-2026-10-30'))
  for field,value in [('head_sha','a'*40),('run_attempt',2),('head_branch','main'),('conclusion','success')]:
   d=copy.deepcopy(original);d['run'][field]=value
   with self.assertRaises(ValueError):check(d)
  d=copy.deepcopy(original);d['jobs']['jobs'][0]['steps'][0]['conclusion']='failure'
  with self.assertRaises(ValueError):check(d)
  d=copy.deepcopy(original);d['artifacts']['artifacts'][1]['expired']=True
  with self.assertRaises(ValueError):check(d)
  d=copy.deepcopy(original);d['artifacts']['artifacts'][1]['digest']='wrong'
  with self.assertRaises(ValueError):check(d)
 def test_checkpoint_never_becomes_a_daily_training_source(self):
  c={'target_date':'2026-10-30','published_ref':'a'*40,'previous_run_id':'40955966396','previous_artifact':'frozen-forecasts-2026-10-30'}
  with self.assertRaises(ValueError):configure(c,{'mode':'daily'})
  self.assertEqual(configure(c,{'mode':'control'},('40955966396',c['previous_artifact']))['run_mode'],'control')
