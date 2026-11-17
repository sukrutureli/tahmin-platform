import json,sys,unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock,patch
import yaml
sys.path.insert(0,'experiments/ensemble_validation')
import publish_primary as p
class ResilienceTests(unittest.TestCase):
 def test_upload_receipt_does_not_query_delayed_artifact_index(self):
  source=Mock();source.call.side_effect=AssertionError('The index is not ready')
  self.assertEqual(p.checkpoint_receipt(source,'run','2026-11-17','123','a'*64),{'id':123,'digest':'sha256:'+'a'*64})
  source.call.assert_not_called()
 def test_incomplete_or_invalid_upload_receipt_cannot_use_another_checkpoint(self):
  source=Mock()
  for aid,digest in [('123',None),(None,'a'*64),('0','a'*64),('123','not-a-digest')]:
   with self.assertRaises(ValueError):p.checkpoint_receipt(source,'run','2026-11-17',aid,digest)
  source.call.assert_not_called()
 def test_temporary_network_or_service_failure_retries_same_saved_inputs(self):
  files={'futbol.html':'saved'};manifest={'targetDate':'2026-11-17'};sleep=Mock()
  with patch.object(p,'publish',side_effect=[TimeoutError(),RuntimeError('GitHub request failed with HTTP 503'),True]) as publish:
   self.assertTrue(p.publish_with_retry(None,files,manifest,'run',123,sleep=sleep))
   self.assertEqual(publish.call_count,3)
   self.assertTrue(all(c.args[1] is files and c.args[2] is manifest and c.args[4]==123 for c in publish.call_args_list))
 def test_retry_is_bounded_and_permission_or_integrity_errors_are_not_retried(self):
  for error in [ValueError('HTML digest mismatch'),RuntimeError('GitHub request failed with HTTP 403')]:
   with patch.object(p,'publish',side_effect=error) as publish:
    with self.assertRaises(type(error)):p.publish_with_retry(None,{}, {},'run',123,sleep=Mock())
    self.assertEqual(publish.call_count,1)
  with patch.object(p,'publish',side_effect=TimeoutError()) as publish:
   with self.assertRaises(RuntimeError):p.publish_with_retry(None,{}, {},'run',123,attempts=3,sleep=Mock())
   self.assertEqual(publish.call_count,3)
 def test_lost_success_does_not_replace_existing_forecast_or_create_second_commit(self):
  class Api:
   def __init__(self):self.ready=False;self.commits=0
   def call(self,path,method='GET',body=None):
    if path==p.DEST:return {'private':True}
    if '/git/ref/' in path:return {'object':{'sha':'head'}}
    if '/git/commits/' in path:return {'tree':{'sha':'tree'}}
    if '/git/trees/' in path:return {'tree':[{'path':'raporlar/2026-11-17/primary-ready.json'}] if self.ready else []}
    if path.endswith('/git/trees'):return {'sha':'newtree'}
    if path.endswith('/git/commits'):self.commits+=1;return {'sha':'newcommit'}
    if '/git/refs/' in path:self.ready=True;raise TimeoutError('Response lost after successful push')
    raise AssertionError(path)
  api=Api();manifest={'targetDate':'2026-11-17','modelSha256':'m','snapshotSha256':'s','pricedSnapshotSha256':'p','selectionPolicy':'complete-market-price-v2','reports':{}}
  self.assertFalse(p.publish_with_retry(api,{'futbol.html':'original'},manifest,'run',123,today=date(2026,11,17),sleep=Mock()))
  self.assertEqual(api.commits,1)
 def test_workflow_passes_authenticated_upload_id_and_digest_to_publisher(self):
  workflow=yaml.safe_load(Path('.github/workflows/ensemble-market-validation.yml').read_text())
  steps=workflow['jobs']['primary']['steps'];upload=next(s for s in steps if s.get('id')=='primary_checkpoint')
  self.assertEqual(upload['uses'],'./.github/actions/private-upload')
  publish=next(s for s in steps if s.get('name')=='Publish primary HTML immediately without waiting for research')
  self.assertEqual(publish['env']['PRIMARY_ARTIFACT_ID'],'${{ steps.primary_checkpoint.outputs.artifact-id }}')
  self.assertEqual(publish['env']['PRIMARY_ARTIFACT_DIGEST'],'${{ steps.primary_checkpoint.outputs.artifact-digest }}')
  self.assertIn('--artifact-id "$PRIMARY_ARTIFACT_ID"',publish['run']);self.assertIn('--artifact-digest "$PRIMARY_ARTIFACT_DIGEST"',publish['run'])
  action=yaml.safe_load(Path('.github/actions/private-upload/action.yml').read_text())
  self.assertEqual(action['outputs']['artifact-id']['value'],'${{ steps.upload.outputs.artifact-id }}')
  self.assertTrue(any(s.get('id')=='upload' and s['uses']=='actions/upload-artifact@v4' for s in action['runs']['steps']))
if __name__=='__main__':unittest.main()
