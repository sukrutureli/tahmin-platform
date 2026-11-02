import copy, unittest
from datetime import datetime, timezone
from conditional_rules import features, apply, freeze, settle

def fixture(day='2026-10-06', role='holdout'):
    p={'pHome':.6,'pDraw':.2,'pAway':.2,'pOver25':.6,'pBttsYes':.6}
    f={'totalMean':3,'totalVariance':2,'goalsFor':1.5,'goalsAgainst':1.5,'count':6,
       'bttsRate':.6,'blankRate':.2,'over25Rate':.6}
    return {'date':day,'role':role,'eventId':'1','name':'A - B','time':'20:00','odds':{},
            'variants':{'legacy':{'models':{'EnsembleModel':p}},
                        'six-balanced':{'marketFeatureAudit':{'home':f,'away':f}}},
            'realScore':None}

class ConditionalRulesTest(unittest.TestCase):
    def test_features_ignore_results_and_basketball_excludes_goal_frequencies(self):
        r=fixture();f=features(r,'football');r['realScore']='9-9'
        self.assertEqual(f,features(r,'football'))
        self.assertNotIn('maximumBlankRate',features(r,'basketball'))
        self.assertNotIn('meanOverRate',features(r,'basketball'))
    def test_probability_and_missing_feature_fallback(self):
        p=[.9,.1];rule={'feature':'totalSigma','cut':12,'below':True,'target':[.4,.6],'blend':.5}
        self.assertEqual(p,apply(rule,p,{}))
        out=apply(rule,p,{'totalSigma':10})
        self.assertAlmostEqual(sum(out),1);self.assertTrue(all(0<=x<=1 for x in out))
    def test_current_labels_cannot_change_frozen_forecasts(self):
        r=fixture();now=datetime(2026,10,6,7,tzinfo=timezone.utc)
        b=freeze({'football':[r]},now=now)
        r['realScore']='0-8'
        self.assertEqual(b,freeze({'football':[r]},now=now))
        self.assertIs(b,freeze({'football':[r]},previous=b,now=now))
    def test_rules_carried_without_refitting_and_live_excluded(self):
        r=fixture();b=freeze({'football':[r]},now=datetime(2026,10,6,7,tzinfo=timezone.utc))
        nxt=fixture('2026-10-07');n=freeze({'football':[nxt]},previous=b)
        self.assertEqual(b['rules'],n['rules']);self.assertEqual(b['rulesFrozenOn'],n['rulesFrozenOn'])
        ev=settle(b,{'football':[r]})
        self.assertTrue(all(x['baseline'] is None for x in ev['markets']))
        r['realScore']='2-0';ev=settle(b,{'football':[r]})
        self.assertEqual(1,ev['markets'][0]['baseline']['count'])

if __name__=='__main__':unittest.main()
