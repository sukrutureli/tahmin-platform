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
            (o/'priced-before-results.json').write_text('{}');verify(o)
            (p/'priced-before-results.json').write_text('{}');begin(p,o,'2026-10-13','123')
            (o/'priced-before-results.json').write_text('{"changed":true}')
            with self.assertRaises(ValueError):verify(o)
            (o/'priced-before-results.json').write_text('{}')
            (o/'learned-before-results.json').write_text('{}')
            with self.assertRaises(ValueError):verify(o)

class DispatchInputTests(unittest.TestCase):
    def test_daily_uses_verified_parent_and_published_ref_without_mutating_settings(self):
        c={'target_date':'2026-10-18','published_ref':'a'*40,'previous_run_id':'1','previous_artifact':'ensemble-market-validation-2026-10-17'}
        r=configure(c,{'mode':'daily','target_date':'2026-10-19','published_ref':'b'*40},('2','ensemble-market-validation-2026-10-18'))
        self.assertEqual(r['published_ref'],'b'*40);self.assertEqual(r['previous_run_id'],'2');self.assertEqual(c['published_ref'],'a'*40)


class RecoverySourceTests(unittest.TestCase):
    def test_recovery_requires_verified_export_and_exact_artifact(self):
        from unittest.mock import patch
        from control_runtime import recovered_source
        run={'head_branch':BRANCH,'path':'.github/workflows/ensemble-market-validation.yml','head_sha':'66c9642a31f744afa00a448ff666c4fdeeb9e56a','status':'completed','conclusion':'failure','run_attempt':1}
        names=['Freeze choices with available initial prices before results','Freeze separate score research candidates (daily only)','Verify provenance and history boundaries','Show initial odds and MBS in prediction HTML','Run ./.github/actions/private-upload','Save bounded reports to private repository']
        steps=[{'name':n,'number':i,'conclusion':'success' if i<5 else 'failure'} for i,n in enumerate(names)]
        export={'conclusion':'success','head_sha':'d4205538faab9c126ccca49c9f9d816a0458094f','path':'.github/workflows/export-private-experiment-reports.yml'}
        artifact={'id':12535836798,'name':'ensemble-market-validation-2026-10-24','expired':False}
        def api(path):
            if '/jobs?' in path:return {'total_count':1,'jobs':[{'steps':steps}]}
            if path.endswith('/artifacts'):return {'artifacts':[artifact]}
            if path.endswith('40075531544'):return export
            return run
        with patch('control_runtime.api',side_effect=api):
            self.assertEqual(recovered_source('40026399108','2026-10-24'),('40026399108',artifact['name']))
            export['conclusion']='failure'
            with self.assertRaises(ValueError):recovered_source('40026399108','2026-10-24')
            export['conclusion']='success';artifact['expired']=True
            with self.assertRaises(ValueError):recovered_source('40026399108','2026-10-24')
