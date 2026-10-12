import copy
import unittest
from unittest.mock import patch
from mine_rules import mine,predictors,merge_dataset

class RuleMiningTests(unittest.TestCase):
    def dataset(self):
        rows=[]
        for date,n in [('2026-09-29',50),('2026-09-30',50),('2026-10-10',20),('2026-10-11',20),('2026-10-12',20)]:
            for x,z in [(0,0),(0,1),(1,0),(1,1)]:
                for i in range(n):
                    rows.append({'date':date,'eventId':f'{x}-{z}-{i}','name':'A - B','realScore':'90-80' if x==z==1 else '80-90','f':{'x':x+.01*i/n,'z':z+.01*i/n},
                      'variants':{'legacy':{'models':{'BasketEnsembleModel':{'pHome':.4,'pAway':.6}}}}})
        return rows

    def test_two_conditions_find_interaction_and_test_cannot_select_rule(self):
        rows=self.dataset()
        with patch('mine_rules.predictors',side_effect=lambda r,s:r['f']):
            first=mine(rows,'basketball','MS','2026-10-12')
            chosen=first['rules'][0]['candidate']
            self.assertIsNotNone(chosen)
            self.assertEqual(len(chosen['conditions']),2)
            changed=copy.deepcopy(rows)
            for r in changed:
                if r['date']>='2026-10-11':r['realScore']='80-90'
            second=mine(changed,'basketball','MS','2026-10-12')
        self.assertEqual(chosen,second['rules'][0]['candidate'])
        self.assertGreater(first['rules'][0]['test']['gainHits'],0)
        self.assertLess(second['rules'][0]['test']['gainHits'],0)

    def test_predictors_ignore_labels_and_reject_same_day_history(self):
        h=[{'date':'2026-10-09','venue':'home','for':2,'against':0,'win':1}]*6
        a=[{'date':'2026-10-08','venue':'away','for':0,'against':1,'win':0}]*6
        r={'date':'2026-10-11','realScore':'2-0','variants':{'six-simple':{'audit':{'home':{'rows':h},'away':{'rows':a}}}}}
        before=predictors(r,'football');r['realScore']='0-9'
        self.assertEqual(before,predictors(r,'football'))
        r['variants']['six-simple']['audit']['home']['rows'][0]['date']='2026-10-11'
        with self.assertRaisesRegex(ValueError,'Future history'):predictors(r,'football')

    def test_merge_preserves_pruned_old_dates_and_unique_identity(self):
        a={'date':'2026-10-10','eventId':'1','realScore':'1-0'}
        b=dict(a,realScore='2-0');future=dict(a,date='2026-10-13')
        m=merge_dataset({'football':[b,future]},{'football':[a]},'2026-10-12')
        self.assertEqual(m['football'],[b])

    def test_shadow_snapshot_is_immutable_and_live_results_excluded(self):
        import json,tempfile
        from pathlib import Path
        from mine_rules import freeze_snapshot,settle_snapshot
        row={'date':'2030-10-12','eventId':'1','name':'A - B','time':'23:59','realScore':'LIVE 90-80','f':{'x':1},'odds':{'hOverUnderValue':165},
             'variants':{'legacy':{'models':{'BasketEnsembleModel':{'pHome':.4,'pAway':.6,'pOver25':.6,'scoreline':'81-80'}}}}}
        rule={'conditions':[{'feature':'x','cut':.5,'below':False}],'probabilities':[.8,.2],'validationDeltaLogLoss':-.1}
        report={'targetDate':row['date'],'markets':[{'sport':'basketball','market':'MS','rules':[{'option':'MS1','candidate':rule}]},
                 {'sport':'basketball','market':'OU','rules':[]}]}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);first=root/'first';first.mkdir();second=root/'second';second.mkdir()
            with patch('mine_rules.predictors',side_effect=lambda r,s:r['f']):
                freeze_snapshot(first,{'basketball':[row]},report)
                saved=(first/'mined-before-results.json').read_bytes()
                book=json.loads(saved);self.assertEqual(book['predictions'][0]['score'],'81-80')
                self.assertEqual(book['predictions'][0]['markets']['MS']['probabilities'],[.8,.2])
                row['variants']['legacy']['models']['BasketEnsembleModel']['pHome']=.9
                row['variants']['legacy']['models']['BasketEnsembleModel']['pAway']=.1
                freeze_snapshot(second,{'basketball':[row]},report,first)
            self.assertEqual(saved,(second/'mined-before-results.json').read_bytes())
            settle_snapshot(second,{'basketball':[row]},row['date'])
            e=json.loads((second/'mined-daily-evaluation.json').read_text())
            ms=next(x for x in e['markets'] if x['sport']=='basketball' and x['market']=='MS')
            self.assertIsNone(ms['all']['rule'])
            row['realScore']='90-80';settle_snapshot(second,{'basketball':[row]},row['date'])
            e=json.loads((second/'mined-daily-evaluation.json').read_text())
            ms=next(x for x in e['markets'] if x['sport']=='basketball' and x['market']=='MS')
            self.assertEqual(ms['all']['baseline']['accuracy'],0)
            self.assertEqual(ms['all']['rule']['accuracy'],1)
