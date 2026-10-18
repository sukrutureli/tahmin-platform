import json,tempfile,unittest
from pathlib import Path
from control_runtime import configure,select_source,begin,verify,BRANCH

class ControlRuntimeTests(unittest.TestCase):
    def settings(self):return {'target_date':'2026-10-13','published_ref':'a'*40,'previous_run_id':'123','previous_artifact':'ensemble-market-validation-2026-10-12','control_target_date':'2026-10-13'}
    def test_control_request_does_not_turn_next_day_into_control(self):
        c=self.settings();r=configure(c,{},('999','ensemble-market-validation-2026-10-13'));self.assertEqual(r['run_mode'],'control');self.assertEqual(c['previous_run_id'],'123')
        r=configure(c,{'target_date':'2026-10-14'});self.assertEqual(r['run_mode'],'daily')
        with self.assertRaises(ValueError):configure(c,{})
    def test_source_requires_success_branch_workflow_day_and_unexpired_artifact(self):
        runs=[{'id':1,'head_branch':'main','name':'Ensemble Market Validation','conclusion':'success'},{'id':2,'head_branch':BRANCH,'name':'Ensemble Market Validation','conclusion':'failure'},{'id':3,'head_branch':BRANCH,'name':'Ensemble Market Validation','conclusion':'success'}]
        artifacts=lambda i:[{'name':'ensemble-market-validation-2026-10-13','expired':False}]
        self.assertEqual(select_source(runs,'2026-10-13',artifacts),('3','ensemble-market-validation-2026-10-13'));self.assertIsNone(select_source(runs,'2026-10-14',artifacts))
    def test_control_only_copies_same_day_and_detects_any_prediction_rewrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'previous';o=Path(d)/'output';p.mkdir()
            for name in ['before-results-predictions.json','learned-before-results.json']:(p/name).write_text(json.dumps({'targetDate':'2026-10-13','predictions':[]}))
            for name in ['football-replay.json','basketball-replay.json','rule-mining-dataset.json']:(p/name).write_text('[]')
            with self.assertRaises(ValueError):begin(p,o,'2026-10-14','123')
            begin(p,o,'2026-10-13','123');(o/'any-evaluation.json').write_text('{}');verify(o)
            (o/'learned-before-results.json').write_text('{}')
            with self.assertRaises(ValueError):verify(o)

class DispatchInputTests(unittest.TestCase):
    def test_daily_uses_verified_parent_and_published_ref_without_mutating_settings(self):
        c={'target_date':'2026-10-18','published_ref':'a'*40,'previous_run_id':'1','previous_artifact':'ensemble-market-validation-2026-10-17'}
        r=configure(c,{'mode':'daily','target_date':'2026-10-19','published_ref':'b'*40},('2','ensemble-market-validation-2026-10-18'))
        self.assertEqual(r['published_ref'],'b'*40);self.assertEqual(r['previous_run_id'],'2');self.assertEqual(c['published_ref'],'a'*40)

