import sys,unittest
sys.path.insert(0,'scripts')
from parallel_experiments import target,source,launch,coordinate
from unittest.mock import patch

class CoordinatorTests(unittest.TestCase):
    def test_control_date_follows_production_istanbul_six_am_boundary(self):
        def r(t,name='Control'):return {'created_at':t,'name':name,'head_branch':'main','conclusion':'success'}
        self.assertEqual(target(r('2026-10-17T23:00:00Z')),('control','2026-10-17'))
        self.assertEqual(target(r('2026-10-18T04:00:00Z')),('control','2026-10-18'))
        self.assertEqual(target(r('2026-10-17T21:00:00Z','Daily Prediction')),('daily','2026-10-18'))
        with self.assertRaises(ValueError):target(dict(r('2026-10-17T21:00:00Z'),head_branch='other'))
    def test_duplicate_production_request_does_not_dispatch_twice(self):
        class Api:
            def __init__(self):self.posts=[]
            def call(self,path,body=None):
                if body:self.posts.append(body)
                return {'workflow_runs':[{'id':9,'display_title':'Ensemble control 2026-10-18 [42]','conclusion':'success'}]}
        a=Api();self.assertEqual(launch(a,'control','2026-10-18','1','a'*40,'42'),9);self.assertFalse(a.posts)
    def test_control_requires_same_date_successful_branch_artifact(self):
        class Api:
            def call(self,p):return {'artifacts':[{'name':'ensemble-market-validation-2026-10-18','expired':False}]}
        r={'id':1,'head_branch':'experiment/ensemble-market-validation','conclusion':'success','name':'Ensemble Market Validation (Artifacts Only)'}
        self.assertEqual(source(Api(),[r],day='2026-10-18'),'1')
        self.assertIsNone(source(Api(),[r],day='2026-10-17'))
        self.assertIsNone(source(Api(),[dict(r,conclusion='failure')],day='2026-10-18'))

class DailySequenceTests(unittest.TestCase):
    def test_previous_control_completes_before_new_daily(self):
        class Api:
            def call(self,path,body=None):
                if path=='actions/runs/42':return {'created_at':'2026-10-18T21:00:00Z','name':'Daily Prediction','head_branch':'main','conclusion':'success'}
                if '/artifacts' in path:return {'artifacts':[{'name':'ensemble-market-validation-2026-10-18','expired':False}]}
                return {'workflow_runs':[{'id':31,'head_branch':'experiment/ensemble-market-validation','conclusion':'success','name':'Ensemble control 2026-10-18 [old]','path':'.github/workflows/ensemble-market-validation.yml'}]}
        class Private:
            def call(self,path):return {'object':{'sha':'a'*40}}
        with patch('parallel_experiments.launch',return_value='32') as launch:
            coordinate(Api(),Private(),'42')
            self.assertEqual(launch.call_count,2)
            self.assertEqual(launch.call_args_list[0].args[1:4],('control','2026-10-18','31'))
            self.assertTrue(launch.call_args_list[0].kwargs['wait'])
            self.assertEqual(launch.call_args_list[1].args[1:4],('daily','2026-10-19','32'))
    def test_completed_daily_is_not_repeated_as_control(self):
        class Api:
            def call(self,path,body=None):
                if path=='actions/runs/42':return {'created_at':'2026-10-18T21:00:00Z','name':'Daily Prediction','head_branch':'main','conclusion':'success'}
                return {'workflow_runs':[{'display_title':'Ensemble daily 2026-10-19 [42]','conclusion':'success'}]}
        class Private:
            def call(self,path):return {'object':{'sha':'a'*40}}
        with patch('parallel_experiments.launch') as launch:
            coordinate(Api(),Private(),'42');launch.assert_not_called()

if __name__=='__main__':unittest.main()

