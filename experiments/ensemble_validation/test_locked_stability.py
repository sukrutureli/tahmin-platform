import copy,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from locked_stability import initialize,freeze,settle,validate_model,verify_snapshot,MODEL,SNAPSHOT,signature,code_hashes
from prepare import dump
from report import BASE,GROUPS

C={'version':'opponent-locked-v1','source_date':'2026-10-18','first_forecast_date':'2026-10-19','arm':'opponent','minimum_observed_days':14,'primary_fraction':.5,'fractions':[.25,.5,.75,1.],'automatic_promotion':False}

class LockedStabilityTests(unittest.TestCase):
 def source(self,root):
  models=[]
  for s in BASE:
   for m in list(GROUPS[s])+['score']:
    models.append({'sport':s,'market':m,'forecastTrainingDates':['2026-10-17'],'forecastModel':{'marker':s+':'+m},'training':{'matches':[]},'contextStatus':{'status':'context-candidate'}})
  dump(root/'context-learning.json',{'targetDate':'2026-10-18','arms':{'opponent':{'models':models,'footballDistribution':{'model':{'dispersion':None,'rho':0}}}}})
  dump(root/'context-before-results.json',{'targetDate':'2026-10-18'})
 def day(self,root,day,score='1-0'):
  data={s:[] for s in BASE};systems={s:{'main':[]} for s in BASE};bank=[]
  for s in BASE:
   for i,time in [('1','12:00'),('2','01:00')]:
    row={'date':day,'eventId':i,'name':'A - B','time':time,'realScore':score,'odds':{'hOverUnderValue':160.5}}
    data[s].append(row);systems[s]['main'].append({'eventId':i,'markets':{'MS':[.9,.05,.05] if s=='football' else [.9,.1],'OU':[.6,.4]},'score':[1,0],'prospectiveBeforeKickoff':True})
    bank.append({'sport':s,'date':day,'eventId':i,'values':{'eloDifference':.1}})
  dump(root/'rule-mining-dataset.json',data);dump(root/'context-features.json',{'features':bank})
  dump(root/'context-before-results.json',{'targetDate':day,'systems':systems})
  for s in BASE:dump(root/(s+'-replay.json'),data[s])
 def prediction(self,model,f,market):
  if market=='score':return [2,1] if model['marker'].startswith('football') else [85,80]
  return [.8,.1,.1] if model['marker']=='football:MS' else [.7,.3]
 def test_lock_reuses_parameters_after_source_outcomes_and_training_report_change(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);a=initialize(root,None,C);saved=(root/MODEL).read_bytes()
   dump(root/'context-learning.json',{'targetDate':'2026-10-20','arms':{}})
   b=initialize(root,None,C);self.assertEqual(saved,(root/MODEL).read_bytes());self.assertEqual(a,b)
   b['payload']['models'][0]['forecastModel']['marker']='changed'
   with self.assertRaisesRegex(ValueError,'parameters'):validate_model(b,C)
 def test_no_retroactive_initialization_from_different_day(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);x=json.loads((root/'context-learning.json').read_text());x['targetDate']='2026-10-19';dump(root/'context-learning.json',x)
   with self.assertRaisesRegex(ValueError,'source-day'):initialize(root,None,C)
 def test_current_day_training_and_pipeline_changes_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);x=json.loads((root/'context-learning.json').read_text());x['arms']['opponent']['models'][0]['forecastTrainingDates']=['2026-10-18'];dump(root/'context-learning.json',x)
   with self.assertRaisesRegex(ValueError,'outcomes'):initialize(root,None,C)
   self.source(root);m=initialize(root,None,C);changed=copy.deepcopy(C);changed['primary_fraction']=.25
   with self.assertRaises(ValueError):validate_model(m,changed)
   m['pipelineHashes']['context_features.py']='changed'
   with self.assertRaisesRegex(ValueError,'pipeline'):validate_model(m,C)
 def test_same_day_control_never_repredicts_and_late_samples_excluded(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);initialize(root,None,C);self.day(root,'2026-10-19')
   now=datetime(2026,10,19,0,tzinfo=timezone.utc) # 03:00 Istanbul
   with patch('locked_stability.features',return_value={}),patch('locked_stability.predict',side_effect=self.prediction):
    b=freeze(root,None,'2026-10-19',C,now=now)
   saved=(root/SNAPSHOT).read_bytes();self.assertEqual(b['coverage']['football']['beforeKickoffCount'],1)
   with patch('locked_stability.predict',side_effect=AssertionError('No refit/reforecast')):freeze(root,None,'2026-10-19',C,now=datetime(2026,10,20,tzinfo=timezone.utc))
   self.assertEqual(saved,(root/SNAPSHOT).read_bytes())
   j=settle(root,None,'2026-10-19',C);self.assertEqual(j['summary'][0]['observedDays'],1)
   self.assertEqual(j['days'][0]['beforeKickoff'][0]['sharedForecastCount'],1)
   self.assertFalse(j['summary'][0]['minimumDaysReached'])
   b['systems']['football'][C['version']][0]['markets']['MS'][0]=.99;dump(root/SNAPSHOT,b)
   with self.assertRaisesRegex(ValueError,'snapshot'):verify_snapshot(root,C)
 def test_new_day_uses_identical_model_and_previous_journal_without_duplicate_days(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);a=root/'a';b=root/'b';a.mkdir();b.mkdir();self.source(a);initialize(a,None,C);self.day(a,'2026-10-19')
   with patch('locked_stability.features',return_value={}),patch('locked_stability.predict',side_effect=self.prediction):
    freeze(a,None,'2026-10-19',C,datetime(2026,10,19,0,tzinfo=timezone.utc));settle(a,None,'2026-10-19',C)
    self.day(b,'2026-10-20');freeze(b,a,'2026-10-20',C,datetime(2026,10,20,0,tzinfo=timezone.utc))
   self.assertEqual((a/MODEL).read_bytes(),(b/MODEL).read_bytes())
   j=settle(b,a,'2026-10-20',C);self.assertEqual(len(j['days']),2)
   j=settle(b,b,'2026-10-20',C);self.assertEqual(len(j['days']),2)
   self.assertEqual(j['summary'][0]['observedDays'],2)
 def test_source_day_not_counted_as_independent_day(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.source(root);self.assertIsNone(freeze(root,None,'2026-10-18',C))
   self.assertFalse((root/SNAPSHOT).exists());self.assertEqual(settle(root,None,'2026-10-18',C)['days'],[])
 def test_old_day_control_does_not_require_or_create_new_model(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.assertIsNone(freeze(root,None,'2026-10-17',C));self.assertIsNone(settle(root,None,'2026-10-17',C))
   self.assertFalse((root/MODEL).exists())

if __name__=='__main__':unittest.main()
