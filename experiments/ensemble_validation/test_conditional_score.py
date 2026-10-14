import copy,math,unittest
from conditional_score import compatible,football_score,basketball_score,basket_covariance

class ConditionalScoreTests(unittest.TestCase):
    def test_all_football_events_are_satisfied_without_changing_model(self):
        m={'dispersion':None,'rho':0};saved=copy.deepcopy(m)
        for market,options in [('MS',[0,1,2]),('BTTS',[0,1]),('OU',[0,1])]:
            for option in options:
                f=football_score([2.3,1.7],m,market,option)
                self.assertTrue(compatible(*f['score'],'football',market,option))
                self.assertGreater(f['probability'],0);self.assertLessEqual(f['conditionalProbability'],1)
                self.assertGreaterEqual(f['conditionalProbability'],f['probability'])
        self.assertEqual(m,saved)
        self.assertIn(0,football_score([2.3,1.7],m,'BTTS',1)['score'])
        self.assertLessEqual(sum(football_score([2.3,1.7],m,'OU',1)['score']),2)
    def test_over_condition_searches_beyond_unconditional_modes(self):
        f=football_score([.05,.05],{'dispersion':10,'rho':0},'OU',0,6.5)
        self.assertGreater(sum(f['score']),6.5)
    def test_basketball_ms_and_totals_are_consistent_without_ties(self):
        for market,option,line in [('MS',0,0),('MS',1,0),('OU',0,180.5),('OU',1,150.5)]:
            f=basketball_score([85,85],[[100,20],[20,80]],market,option,line)
            self.assertTrue(compatible(*f['score'],'basketball',market,option,line));self.assertIsNone(f['probability'])
    def test_covariance_uses_training_residuals_only(self):
        training=[{'date':'2026-10-09','actual':[80+i,70-i],'learned':[80,70]} for i in range(20)]
        r={'models':[{'sport':'basketball','market':'score','validationDate':'2026-10-10','training':{'matches':training},'test':{'matches':[{'actual':[999,999]}]}}]}
        a=basket_covariance(r);r['models'][0]['test']['matches'][0]['actual']=[0,0];self.assertEqual(a,basket_covariance(r))
        r['models'][0]['training']['matches'][0]['date']='2026-10-10'
        with self.assertRaises(AssertionError):basket_covariance(r)
