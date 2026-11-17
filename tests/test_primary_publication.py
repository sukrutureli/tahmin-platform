import importlib.util,sys,unittest
from unittest.mock import Mock
sys.path.insert(0,'experiments/ensemble_validation');sys.path.insert(0,'scripts')
import publish_primary as pub
import primary_control as control
class PublicationTests(unittest.TestCase):
 def test_uploaded_checkpoint_visibility_is_retried_without_forecast_generation(self):
  source=Mock();source.call.side_effect=[{'artifacts':[]},{'artifacts':[{'id':7,'name':'primary-forecasts-2026-11-17','expired':False}]}];sleep=Mock()
  self.assertEqual(pub.find_checkpoint(source,'5','2026-11-17',sleep=sleep)['id'],7);sleep.assert_called_once_with(2)
 def test_missing_expired_wrong_date_or_ambiguous_checkpoint_fails_closed(self):
  source=Mock();source.call.return_value={'artifacts':[{'name':'primary-forecasts-2026-11-16','expired':False},{'name':'primary-forecasts-2026-11-17','expired':True}]};sleep=Mock()
  with self.assertRaises(RuntimeError):pub.find_checkpoint(source,'5','2026-11-17',attempts=3,sleep=sleep)
  self.assertEqual(source.call.call_count,3);self.assertEqual(sleep.call_count,2)
  source.call.return_value={'artifacts':[{'name':'primary-forecasts-2026-11-17','expired':False}]*2}
  with self.assertRaises(ValueError):pub.find_checkpoint(source,'5','2026-11-17',sleep=sleep)
 def test_recovery_exception_requires_exact_source_and_successful_repair(self):
  source=Mock();source.call.side_effect=[{'head_branch':'main','path':'.github/workflows/recover-primary-publication.yml','head_sha':'a'*40,'conclusion':'success'},{'jobs':[{'name':'Restore and publish preserved primary checkpoint','conclusion':'success'}]}]
  run={'head_sha':'055e438324a31e91754ddaa9b137624026590206','conclusion':'failure'}
  steps=[{'name':n,'conclusion':'success'} for n in ['Run frozen primary model without research training','Save encrypted primary forecasts before background work']]+[{'name':'Publish primary HTML immediately without waiting for research','conclusion':'failure'}]
  jobs=[{'name':'Primary forecast and immediate HTML','conclusion':'failure','steps':steps}];ready={'sourceArtifactId':14274774036,'publicationRecovery':{'rendererSha':'a'*40,'runId':'8'}}
  self.assertTrue(control.verified_publication_recovery(source,'2026-11-17','43960512102',run,jobs,ready))
  self.assertFalse(control.verified_publication_recovery(source,'2026-11-18','43960512102',run,jobs,ready))
  self.assertFalse(control.verified_publication_recovery(source,'2026-11-17','43960512103',run,jobs,ready))
  steps[0]['conclusion']='failure';self.assertFalse(control.verified_publication_recovery(source,'2026-11-17','43960512102',run,jobs,ready))
if __name__=='__main__':unittest.main()
