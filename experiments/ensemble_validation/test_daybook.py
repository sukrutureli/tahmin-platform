import copy
import unittest
from daybook import freeze,settle
from history_markets import enrich

class DailyExperimentTests(unittest.TestCase):
 def fixture(self):
  rows=[{'date':'2026-09-30','for':1,'against':0,'tournament':'League'} for _ in range(6)]
  base={'pHome':.6,'pDraw':.2,'pAway':.2,'pOver25':.6,'pBttsYes':.6,'scoreline':'1-0'}
  return {'football':[{'date':'2026-10-01','role':'holdout','eventId':'x','name':'A - B','time':'23:59','realScore':'1-0','odds':{},'variants':{'legacy':{'models':{'EnsembleModel':base}},'six-balanced':{'models':{'EnsembleModel':base},'audit':{'home':{'rows':rows},'away':{'rows':rows}}}}}]}
 def test_feature_models_cannot_read_current_outcome(self):
  a=self.fixture();b=copy.deepcopy(a);b['football'][0]['realScore']='9-9'
  enrich(a['football'],'football');enrich(b['football'],'football')
  self.assertEqual(a['football'][0]['variants'],b['football'][0]['variants'])
 def test_future_history_rejected(self):
  data=self.fixture();data['football'][0]['variants']['six-balanced']['audit']['home']['rows'][0]['date']='2026-10-01'
  with self.assertRaises(ValueError):enrich(data['football'],'football')
 def test_goal_frequencies_distinguish_clean_sheet_history(self):
  data=self.fixture();enrich(data['football'],'football')
  p=data['football'][0]['variants']['six-balanced']['models']['HistoryBttsModel']['pBttsYes']
  self.assertLess(p,.5)
 def test_same_day_rule_cannot_be_independent_validation(self):
  b=freeze(self.fixture(),{'derivedFromDate':'2026-10-01','validFromDate':'2026-10-02','rules':{}})
  self.assertFalse(b['independentRuleAvailable'])
  self.assertEqual(b['predictions'][0]['markets']['MS']['candidate'],['legacy','EnsembleModel',0])
 def test_btts_dependence_candidate_is_bounded_and_uses_joint_history(self):
  data=self.fixture()
  rows=data['football'][0]['variants']['six-balanced']['audit']['home']['rows']
  for i,r in enumerate(rows):r.update({'for':2 if i%2 else 0,'against':2 if i%2 else 0})
  enrich(data['football'],'football')
  entry=data['football'][0]['variants']['six-balanced']
  self.assertGreater(entry['marketFeatureAudit']['bttsDependenceCorrection'],1)
  self.assertGreater(entry['models']['HistoryCoupledBttsModel']['pBttsYes'],entry['models']['HistoryBttsModel']['pBttsYes'])
  self.assertTrue(0<=entry['models']['HistoryCoupledBttsModel']['pBttsYes']<=1)
 def test_settlement_uses_saved_probabilities_even_when_models_change(self):
  data=self.fixture();book=freeze(data,{})
  data['football'][0]['variants']['legacy']['models']['EnsembleModel']['pHome']=.01
  data['football'][0]['variants']['legacy']['models']['EnsembleModel']['pAway']=.99
  summary,journal=settle(book,data)
  self.assertEqual(summary['markets'][0]['frozenRule']['accuracy'],1)
  self.assertNotIn('realScore',book['predictions'][0])
 def test_earlier_day_rule_validation_can_report_a_loss(self):
  data=self.fixture();old={'derivedFromDate':'2026-09-30','validFromDate':'2026-10-01','rules':{}}
  book=freeze(data,old);data['football'][0]['realScore']='0-2'
  summary,journal=settle(book,data)
  self.assertTrue(summary['independentRuleAvailable'])
  self.assertEqual(summary['markets'][0]['frozenRule']['accuracy'],0)

if __name__=='__main__':unittest.main()
