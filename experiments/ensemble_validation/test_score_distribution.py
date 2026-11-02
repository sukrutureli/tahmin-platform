import copy,json,math,tempfile,unittest
from pathlib import Path
from score_distribution import forecast,log_probability,learn,freeze,settle,CANDIDATES

class ScoreDistributionTests(unittest.TestCase):
    def report(self):
        return {'targetDate':'2026-10-13','models':[{'sport':'football','market':'score','model':{'weights':[]},'trainingDates':['2026-10-09'],'forecastTrainingDates':['2026-10-09','2026-10-10','2026-10-11'],
           'validationDate':'2026-10-10','untouchedTestDate':'2026-10-11','validation':{'matches':[{'date':'2026-10-10','learned':[1.8,.8],'actual':[1,0]}]*20},'test':{'matches':[{'date':'2026-10-11','learned':[1.8,.8],'actual':[1,0]}]*20}}]}
    def test_normalized_nonnegative_distributions_and_modes_differ_from_rounding(self):
        for model in CANDIDATES:
            mass=sum(math.exp(log_probability((h,a),[1.8,.8],model)) for h in range(50) for a in range(50))
            self.assertAlmostEqual(mass,1,places=8)
        f=forecast([1.8,.8],{'dispersion':None,'rho':0});self.assertEqual(f['score'],[1,0]);self.assertNotEqual(f['score'],[2,1]);self.assertEqual(len(f['alternatives']),3)
    def test_test_labels_cannot_select_distribution(self):
        a=self.report();b=copy.deepcopy(a)
        for r in b['models'][0]['test']['matches']:r['actual']=[9,9]
        self.assertEqual(learn(a)['model'],learn(b)['model'])
        b['models'][0]['validationDate']='2026-10-13'
        with self.assertRaises(AssertionError):learn(b)
    def test_large_intensities_and_out_of_grid_labels_remain_finite(self):
        for m in CANDIDATES:
            self.assertTrue(math.isfinite(log_probability((19,0),[100,0],m)))
            self.assertGreater(forecast([100,0],m)['probability'],0)
    def test_original_forecast_unchanged_reuse_and_live_exclusion(self):
        with tempfile.TemporaryDirectory() as x:
            a=Path(x)/'a';b=Path(x)/'b';a.mkdir();b.mkdir();book={'targetDate':'2026-10-13','predictions':[{'sport':'football','date':'2026-10-13','eventId':'1','name':'A - B','score':[1.8,.8],'prospectiveBeforeKickoff':True}]}
            for p in [a,b]:
                (p/'learned-before-results.json').write_text(json.dumps(book));(p/'outcome-learning.json').write_text(json.dumps(self.report()))
            raw=(a/'learned-before-results.json').read_bytes();data={'football':[{'date':'2026-10-13','eventId':'1','time':'20:00','realScore':'LIVE 1-0'}]}
            freeze(a,data);freeze(b,data,a);self.assertEqual((a/'score-before-results.json').read_bytes(),(b/'score-before-results.json').read_bytes());self.assertEqual(raw,(a/'learned-before-results.json').read_bytes())
            settle(b,data);r=json.loads((b/'score-distribution-evaluation.json').read_text());self.assertIsNone(r['all']);self.assertIsNone(r['prospective'])
