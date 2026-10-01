import copy
import unittest
from datetime import date
from prepare import archived,filtered,weighted_stats
from report import metrics,fit,vector,result,poisson_expectation,candidate_vector,evaluate,derive_today_rules

class ValidationTests(unittest.TestCase):
 def test_future_history_excluded_and_duplicates_removed(self):
  rows=[{'id':'x','date':'2026-09-30'},{'id':'x','date':'2026-09-30'},{'id':'y','date':'2026-10-01'}]
  self.assertEqual(filtered(rows,date(2026,10,1),20),[rows[0]])
 def test_yearless_archive_dates_roll_backward_without_including_today(self):
  def row(d):return {'homeTeam':'A','awayTeam':'B','homeScore':1,'awayScore':0,'matchDate':d}
  rows=archived([row('2 Oca'),row('1 Oca'),row('30 Ara'),row('15 Ağu')],'A',date(2026,1,2),'football')
  self.assertEqual([r['date'] for r in rows],['2026-01-01','2025-12-30','2025-08-15'])
  self.assertTrue(all(r['dateInferred'] for r in rows))
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
  prediction={'pHome':.6,'pDraw':.2,'pAway':.2,'pOver25':.6,'pBttsYes':.6,'scoreline':'2-1'}
  stats={'avgGF':1.5,'avgGA':1,'avgPointsPerMatch':1,'rating100':50}
  entry={'models':{'EnsembleModel':prediction},'match':{'homeStats':stats,'awayStats':stats}}
  rows=[{'eventId':str(i)+d,'date':d,'role':'training','realScore':'2-1','published':prediction,'variants':{'legacy':entry},'odds':{}} for d in ['2026-09-29','2026-09-30'] for i in range(20)]
  held=copy.deepcopy(rows[0]);held.update(date='2026-10-01',role='holdout',realScore='2-1');rows.append(held)
  first=evaluate({'football':rows})
  rows[-1]['realScore']='0-9'
  second=evaluate({'football':rows})
  self.assertEqual(first['recommendations'],second['recommendations'])
  self.assertEqual([m['training'] for m in first['markets']],[m['training'] for m in second['markets']])
  self.assertNotEqual(first['markets'][0]['holdout']['accuracy'],second['markets'][0]['holdout']['accuracy'])
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
 def test_today_rule_cannot_trade_lower_hit_rate_for_lower_log_loss(self):
  base={'pHome':.99,'pAway':.01,'pOver25':.5}
  alternative={'pHome':.4,'pAway':.6,'pOver25':.5}
  rows=[{'role':'holdout','realScore':score,'odds':{'hOverUnderValue':160},'variants':{'legacy':{'models':{'BasketEnsembleModel':base}},'wide-balanced':{'models':{'BasketEnsembleModel':alternative}}}} for score in ('91-81','89-81','80-90')]
  rules=derive_today_rules(rows,'basketball')['markets']['MS']
  self.assertLess(rules['leaderboard'][0]['metrics']['accuracy'],rules['baseline']['accuracy'])
  self.assertGreaterEqual(rules['rule']['metrics']['accuracy'],rules['baseline']['accuracy'])
 def test_poisson_expectation_tracks_attack_and_defence(self):
  h={'avgGF':2,'avgGA':1,'avgPointsPerMatch':1,'rating100':50};a={'avgGF':1,'avgGA':1,'avgPointsPerMatch':1,'rating100':50}
  home,away=poisson_expectation({'homeStats':h,'awayStats':a})
  self.assertAlmostEqual(home,1.1*(.55*2+.45*1));self.assertAlmostEqual(away,1)
 def test_invalid_probabilities_fail_instead_of_silently_clamping(self):
  with self.assertRaises(ValueError):vector({'pHome':float('nan'),'pAway':.5},'basketball','MS')

if __name__=='__main__':unittest.main()
