import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date
from context_features import canonical,merge_records,Context,bounded_enrichment,build_ledger,identity_from_page
from context_experiment import own_comparison,prepare,check_snapshot,digest,score_diagnostics,learn_context
from live_history import schedule_row,RateLimitError,dump

class IdentityTests(unittest.TestCase):
 def raw(self):return {'id':77,'date':'10/09/2026 18:00:00','status':{'id':5},'teamType':'away','team':{'id':22,'name':'Short'},'tournament':{'id':8},'season':{'id':99},'scores':{'home':{'ordinary':2,'current':2},'away':{'ordinary':1,'current':1}}}
 def test_provider_ids_and_season_preserved(self):
  row=schedule_row(self.raw(),date(2026,10,11),'football');self.assertEqual((row['opponentId'],row['seasonId']),(22,99))
  own=canonical('football','broadage',11,row,'2026-10-15');other=dict(row,venue='away',opponentId=11,**{'for':1,'against':2,'finalFor':1,'finalAgainst':2})
  opp=canonical('football','broadage',22,other,'2026-10-16');rows,conflicts=merge_records([own,opp]);self.assertEqual(len(rows),1);self.assertEqual(conflicts,[])
  wrong=dict(opp,homeScore=9);self.assertEqual(merge_records([own,wrong])[0],[])
  self.assertIsNone(canonical('football','broadage',11,dict(row,opponentId=None),'2026-10-15'))
  self.assertEqual(len(merge_records([own,dict(own,key='basketball:broadage:broadage:77',sport='basketball')])[0]),2)
 def test_conflict_tombstone_survives_next_day(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);dump(p/'context-ledger.json',{'matches':[],'conflictingMatchKeys':['bad']});dump(p/'live-history.json',{'requests':[]});dump(p/'live-history-journal.json',[])
   out,_=build_ledger(p,p,'2026-10-16');self.assertEqual(out['conflictingMatchKeys'],['bad'])

class TemporalTests(unittest.TestCase):
 def m(self,day,h='broadage:1',a='broadage:2',score=(2,1),key='a'):
  return {'key':key,'sport':'football','namespace':'broadage','date':day,'home':h,'away':a,'homeScore':score[0],'awayScore':score[1],'homeFinal':score[0],'awayFinal':score[1],'tournamentId':'8','firstCollectedAt':'2026-10-15'}
 def test_future_and_same_day_cannot_change_context(self):
  past=self.m('2026-10-10');idx={('football','2026-10-14','9'):{'home':'broadage:1','away':'broadage:2','namespace':'broadage','tournamentId':'8'}}
  r={'date':'2026-10-14','eventId':'9','variants':{},'odds':{}}
  a=Context({'matches':[past]},idx).features(r,'football')
  b=Context({'matches':[past,self.m('2026-10-14',score=(100,0),key='today'),self.m('2026-10-15',score=(0,100),key='future')]},idx).features(r,'football')
  self.assertEqual(a,b);self.assertGreater(a['eloDifference'],0)
 def test_missing_identity_has_no_name_fallback(self):
  c=Context({'matches':[self.m('2026-10-10')]},{})
  self.assertEqual(c.features({'date':'2026-10-14','eventId':'9','name':'Short - Short'},'football'),{})
 def test_sparse_league_shrinks_to_global(self):
  a=self.m('2026-10-10',score=(10,0));b=self.m('2026-10-11',score=(0,0),key='b');b['tournamentId']='99'
  idx={('football','2026-10-14','9'):{'home':'broadage:1','away':'broadage:2','namespace':'broadage','tournamentId':'8'}}
  f=Context({'matches':[a,b]},idx).features({'date':'2026-10-14','eventId':'9','variants':{},'odds':{}},'football')
  self.assertGreater(f['leagueExpectedTotal'],5);self.assertLess(f['leagueExpectedTotal'],10)

class ComparisonTests(unittest.TestCase):
 def entry(self,i,ms,ou):return {'eventId':str(i),'markets':{'MS':ms,'OU':ou},'score':[1,0],'prospectiveBeforeKickoff':True}
 def test_each_system_chooses_own_market(self):
  rows=[{'eventId':'1','realScore':'1-0','odds':{}}]
  a=self.entry(1,[.9,.05,.05],[.4,.6]);b=self.entry(1,[.55,.2,.25],[.95,.05])
  report=own_comparison({'main':[a],'candidate':[b]},rows,'football');allrows={r['system']:r['measured'] for r in report['rows'] if r['fraction']==1}
  self.assertEqual(allrows['main']['hits'],1);self.assertEqual(allrows['candidate']['hits'],0)
 def test_own_subsets_rank_pending_before_measurement(self):
  rows=[{'eventId':'1','realScore':'1-0','odds':{}},{'eventId':'2','realScore':None,'odds':{}},{'eventId':'3','realScore':'1-0','odds':{}},{'eventId':'4','realScore':'1-0','odds':{}}]
  a=[self.entry(1,[.9,.05,.05],[.4,.6]),self.entry(2,[.95,.03,.02],[.4,.6]),self.entry(3,[.7,.2,.1],[.4,.6]),self.entry(4,[.6,.2,.2],[.4,.6])]
  b=copy.deepcopy(a);b[2]['markets']['MS']=[.99,.005,.005]
  r=own_comparison({'a':a,'b':b},rows,'football');half=[x for x in r['rows'] if x['fraction']==.5]
  self.assertEqual(half[0]['eventIds'],['2','1']);self.assertEqual(half[1]['eventIds'],['3','2']);self.assertEqual(half[0]['measured']['count'],1)
 def test_future_test_outcome_cannot_change_ranking(self):
  rows=[{'eventId':'1','realScore':'1-0','odds':{}}];e=self.entry(1,[.9,.05,.05],[.4,.6]);a=own_comparison({'a':[e]},rows,'football');rows[0]['realScore']='0-4';b=own_comparison({'a':[e]},rows,'football')
  self.assertEqual([x['eventIds'] for x in a['rows']],[x['eventIds'] for x in b['rows']]);self.assertNotEqual(a['rows'][0]['measured']['hits'],b['rows'][0]['measured']['hits'])

class SnapshotTests(unittest.TestCase):
 def test_same_day_reuses_snapshot_and_models_without_http_or_training(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);previous=root/'old';out=root/'new';previous.mkdir();out.mkdir()
   names=['context-learning.json','context-ledger.json','context-features.json'];hashes={}
   for n in names:dump(previous/n,{'value':n});hashes[n]=digest(previous/n)
   dump(previous/'context-before-results.json',{'targetDate':'2026-10-15','hashes':hashes});saved=(previous/'context-before-results.json').read_bytes()
   with patch('context_experiment.build_ledger',side_effect=AssertionError('No new context')),patch('context_experiment.learn',side_effect=AssertionError('No fit')):prepare(out,previous,'2026-10-15')
   self.assertEqual((out/'context-before-results.json').read_bytes(),saved)
   (out/names[0]).write_text('{}')
   with self.assertRaisesRegex(ValueError,'changed'):check_snapshot(out)

class BudgetTests(unittest.TestCase):
 def test_429_stops_enrichment_globally(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cache=root/'http-cache/2026-10-15';cache.mkdir(parents=True);(cache/'page.txt').write_text('model.AccountId="abc"; model.SportId=1;')
   dump(root/'live-history.json',{'fixtures':[],'requests':[{'url':'https://x/soccer/widget/team/schedule?teId=1','status':200},{'url':'https://istatistik.nesine.com/p1/1','status':200,'cache':'page.txt'}]})
   class Fake:
    audit=[]
    def __init__(self):self.calls=0
    def get(self,*args):self.calls+=1;raise RateLimitError('429')
   c=Fake();m=TemporalTests().m('2026-10-10');r=bounded_enrichment(root,'2026-10-15',{'matches':[m]},client=c)
   self.assertTrue(r['rateLimited']);self.assertEqual(c.calls,1)


class AvailabilityTests(unittest.TestCase):
 def test_sparse_context_cannot_train_or_replace_baseline(self):
  baseline={'model':{'weights':[[1]]},'forecastModel':{'weights':[[2]]},'trainingDates':['2026-10-10'],'validationDates':['2026-10-11']}
  rows=[{'date':'2026-10-10','eventId':'1','realScore':'2-1','odds':{}},{'date':'2026-10-11','eventId':'2','realScore':'2-1','odds':{}}]
  with patch('context_experiment.learn',side_effect=AssertionError('Insufficient context must not fit')):
   result=learn_context(rows,'football','MS','2026-10-15',lambda r,s:{'eloDifference':.2},['eloDifference'],baseline)
  self.assertEqual(result['forecastModel'],baseline['forecastModel']);self.assertEqual(result['contextStatus']['status'],'fallback-insufficient-context')
 def test_client_deadline_stops_before_network(self):
  from live_history import Client,RequestBudgetError
  with tempfile.TemporaryDirectory() as d,patch('live_history.urllib.request.urlopen',side_effect=AssertionError('No request after deadline')):
   with self.assertRaises(RequestBudgetError):Client(Path(d),deadline=-1).get('https://example.invalid/')


class ScoreDiagnosticsTests(unittest.TestCase):
 def model(self,sport):
  return {'sport':sport,'model':{'present':True},'training':{'matches':[{'actual':[80,75],'learned':[79,74]},{'actual':[90,85],'learned':[88,84]}]},
          'validation':{'matches':[{'actual':[80,81],'learned':[79,80]},{'actual':[70,75],'learned':[72,73]}]},
          'test':{'matches':[{'actual':[100,99],'learned':[81,82]},{'actual':[70,71],'learned':[75,75]}]}}
 def test_basketball_tail_threshold_is_not_fit_on_test_results(self):
  m=self.model('basketball');a=score_diagnostics(m);json.dumps(a,allow_nan=False);m['test']['matches'][0]['actual']=[1000,900];b=score_diagnostics(m)
  self.assertEqual(a['highTotalThreshold'],b['highTotalThreshold']);self.assertEqual(a['validationAbsoluteTotalError80'],b['validationAbsoluteTotalError80'])
  self.assertNotEqual(a['meanScore']['teamMAE'],b['meanScore']['teamMAE'])
 def test_football_high_score_tail_is_probability_not_forced_point(self):
  m=self.model('football');m['test']['matches']=[{'actual':[4,2],'learned':[1.1,1.0]},{'actual':[0,0],'learned':[1.0,1.0]}]
  a=score_diagnostics(m,{'model':{'dispersion':None,'rho':0}})
  self.assertEqual(a['actualHighCount'],1);self.assertEqual(a['pointHighCount'],0);self.assertGreater(a['meanPredictedHighProbability'],0);self.assertLess(a['meanPredictedHighProbability'],1)


class HistoricalIdentityTests(unittest.TestCase):
 def test_exact_event_ids_without_short_name_matching(self):
  page='model.SportId=2; model.HomeTeamId="51"; model.AwayTeamId="52"; model.TournamentId="7";'
  r=identity_from_page(page,{'date':'2026-10-11','eventId':'100','name':'Same - Same'},'basketball','2026-10-15')
  self.assertEqual((r['home'],r['away']),('broadage:51','broadage:52'));self.assertEqual(r['date'],'2026-10-11')
  with self.assertRaisesRegex(ValueError,'sport'):identity_from_page(page,{'date':'2026-10-11','eventId':'100'},'football','2026-10-15')
 def test_missing_or_zero_team_id_rejected(self):
  with self.assertRaises(ValueError):identity_from_page('model.SportId=2; model.HomeTeamId=0; model.AwayTeamId=52;',{'date':'2026-10-11','eventId':'100'},'basketball','2026-10-15')

if __name__=='__main__':unittest.main()
