import copy
import unittest
from datetime import date
from prepare import archived,filtered,weighted_stats
from report import metrics,fit,vector,result,poisson_expectation,candidate_vector

class ValidationTests(unittest.TestCase):
 def test_future_history_excluded_and_duplicates_removed(self):
  rows=[{'id':'x','date':'2026-09-30'},{'id':'x','date':'2026-09-30'},{'id':'y','date':'2026-10-01'}]
  self.assertEqual(filtered(rows,date(2026,10,1),20),[rows[0]])
 def test_unknown_basketball_tie_not_classified_as_loss(self):
  r=archived([{'homeTeam':'A','awayTeam':'B','homeScore':80,'awayScore':80,'matchDate':'30 Eylül 2026'}],'A',date(2026,10,1),'basketball')
  self.assertIsNone(r[0]['win'])
 def test_venue_shrink_uses_team_average_not_global_prior(self):
  rows=[{'id':str(i),'date':'2026-09-30','venue':'away','for':110,'against':100,'win':1,'draw':0,'tournament':'NBA'} for i in range(6)]
  s,a=weighted_stats(rows,date(2026,10,1),'basketball','home',False,True,True)
  self.assertEqual(s['avgPointsFor'],110)
  self.assertEqual(s['avgPointsAgainst'],100)
 def test_probability_metrics_and_option_coverage(self):
  m=metrics([([.8,.2],0),([.3,.7],0)],['H','A'],.75)
  self.assertEqual(m['count'],2);self.assertEqual(m['accuracy'],.5)
  self.assertEqual(m['selectedCount'],1);self.assertEqual(m['selectedAccuracy'],1)
  self.assertEqual(m['options'][1]['predictedCount'],0);self.assertIsNone(m['options'][1]['precision'])
 def test_push_and_absent_basketball_line_excluded(self):
  self.assertIsNone(result({'realScore':'80-80','odds':{'hOverUnderValue':160}},'basketball','OU'))
  self.assertIsNone(result({'realScore':'91-69','odds':{'hOverUnderValue':160}},'basketball','OU'))
  self.assertIsNone(result({'realScore':'91-69','odds':{}},'basketball','OU'))
 def test_fitted_choices_cannot_read_holdout_outcomes(self):
  prediction={'pHome':.6,'pDraw':.2,'pAway':.2,'pOver25':.6,'pBttsYes':.6}
  rows=[{'date':d,'realScore':'2-1','variants':{'legacy':{'models':{'EnsembleModel':prediction}}},'odds':{}} for d in ['2026-09-29','2026-09-30'] for i in range(20)]
  a=fit(rows,'football','MS');b=fit(copy.deepcopy(rows),'football','MS')
  self.assertEqual(a['candidate'],b['candidate']);self.assertEqual(a['threshold'],b['threshold'])
  self.assertLessEqual(a['candidate'][2],.5)
 def test_incomplete_model_cannot_win_by_dropping_bad_predictions(self):
  base={'pHome':.6,'pDraw':.2,'pAway':.2}
  perfect={'pHome':.99,'pDraw':.005,'pAway':.005}
  rows=[{'date':d,'realScore':'2-1','variants':{'legacy':{'models':{'EnsembleModel':base,'ValidOddsFormModel':perfect}}},'odds':{}} for d in ['2026-09-29','2026-09-30'] for i in range(20)]
  rows[0]['variants']['legacy']['models']['ValidOddsFormModel']={'pHome':'NaN','pDraw':.2,'pAway':.2}
  self.assertIsNone(candidate_vector(rows[0],'football','MS',('legacy','ValidOddsFormModel',.5)))
  fitted=fit(rows,'football','MS')
  self.assertEqual(fitted['candidate'],['legacy','EnsembleModel',0])
  self.assertEqual(len(fitted['excludedCandidates']),2)
  self.assertEqual(fitted['excludedCandidates'][0]['validSettledCount'],39)
 def test_poisson_expectation_tracks_attack_and_defence(self):
  h={'avgGF':2,'avgGA':1,'avgPointsPerMatch':1,'rating100':50};a={'avgGF':1,'avgGA':1,'avgPointsPerMatch':1,'rating100':50}
  home,away=poisson_expectation({'homeStats':h,'awayStats':a})
  self.assertAlmostEqual(home,1.1*(.55*2+.45*1));self.assertAlmostEqual(away,1)
 def test_invalid_probabilities_fail_instead_of_silently_clamping(self):
  with self.assertRaises(ValueError):vector({'pHome':float('nan'),'pAway':.5},'basketball','MS')

if __name__=='__main__':unittest.main()
