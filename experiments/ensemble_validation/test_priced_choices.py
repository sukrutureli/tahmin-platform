import unittest,copy,tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from priced_choices import choose,freeze,compare,FILE
class PriceChoiceTests(unittest.TestCase):
 def test_missing_best_price_uses_next_best_available_option(self):
  e={'markets':{'MS':[.8,.1,.1],'OU':[.7,.3],'BTTS':[.65,.35]}}
  r={'odds':{'ms1':None,'over25':1.6,'bttsYes':1.8}}
  c=choose(e,r,'football');self.assertEqual((c['market'],c['option'],c['price']),('OU',0,1.6))
  r['odds']['over25']=None;self.assertEqual(choose(e,r,'football')['market'],'BTTS')
 def test_checks_all_options_not_just_each_markets_favourite(self):
  e={'markets':{'MS':[.5,.3,.2],'OU':[.6,.4]}}
  self.assertEqual(choose(e,{'odds':{'under25':2.1,'msX':2.9}},'football')['option'],1)
  self.assertEqual(choose(e,{'odds':{'under25':2.1,'msX':2.9}},'football')['market'],'OU')
 def test_invalid_prices_and_missing_basketball_line_are_excluded(self):
  for price in [None,0,1,True,'-',float('nan'),float('inf')]:self.assertIsNone(choose({'markets':{'MS':[.8,.2]}},{'odds':{'ms1':price}},'basketball'))
  self.assertIsNone(choose({'markets':{'OU':[.8,.2]}},{'odds':{'over':1.5}},'basketball'))
 def test_freeze_reuses_choice_after_results_and_odds_change(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);systems={}
   for sport in ['football','basketball']:
    e={'eventId':'1','name':'A B','time':'20:00','prospectiveBeforeKickoff':True,'markets':{'MS':[.8,.1,.1] if sport=='football' else [.8,.2]},'scoreMean':[2,1] if sport=='football' else [80,70],'score':[2,1] if sport=='football' else [80,70]}
    systems[sport]={'main':[copy.deepcopy(e)],'v1':[e]}
    (root/(sport+'-replay.json')).write_text(json.dumps([{'date':'2026-10-19','eventId':'1','odds':{'ms1':1.8}}]))
   (root/'stability-before-results.json').write_text(json.dumps({'targetDate':'2026-10-19','version':'v1','systems':systems}))
   (root/'stability-model.json').write_text(json.dumps({'payload':{'footballDistribution':{'dispersion':None,'rho':0},'basketballCovariance':[[100,0],[0,100]]}}))
   b=freeze(root,datetime(2026,10,19,0,tzinfo=timezone.utc));saved=(root/FILE).read_bytes()
   for sport in systems:(root/(sport+'-replay.json')).write_text(json.dumps([{'date':'2026-10-19','eventId':'1','realScore':'2-1','odds':{}}]))
   self.assertEqual(freeze(root),b);self.assertEqual((root/FILE).read_bytes(),saved)
   self.assertEqual(b['systems']['football']['experiment'][0]['chosen']['price'],1.8)
   self.assertGreater(b['systems']['football']['experiment'][0]['score'][0],b['systems']['football']['experiment'][0]['score'][1])
 def test_missing_result_and_no_price_never_count_as_loss(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'football-replay.json').write_text(json.dumps([{'date':'2026-10-19','eventId':'1','realScore':None}]))
   e={'eventId':'1','chosen':{'market':'MS','option':0,'confidence':.7},'prospectiveBeforeKickoff':True,'score':[1,0]}
   b={'targetDate':'2026-10-19','systems':{'football':{'main':[e],'experiment':[e]}}}
   self.assertTrue(all(r['count']==0 for r in compare(b,root,True)))
