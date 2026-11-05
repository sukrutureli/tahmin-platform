import copy,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
import history_context_trial as trial
from complete_prices import choose
from priced_choices import write
class TrialTests(unittest.TestCase):
    def fixture(self,root):
        day='2026-11-06';rows=[]
        for i in range(6):
            rows.append({'date':f'2026-{10-i:02d}-01','for':1+i,'against':1,'win':int(i>0),'draw':int(i==0),'venue':'home','tournamentId':'10' if i%2==0 else '20'})
        r={'sport':'football','date':day,'eventId':'1','name':'A - B','time':'23:59','realScore':None,
           'variants':{'six-simple':{'audit':{'home':{'rows':rows},'away':{'rows':[dict(x,venue='away',**{'for':1}) for x in rows]}}}},
           'odds':{'ms1':1.8,'msX':3.,'ms2':4.,'over25':1.8,'under25':1.8,'bttsYes':1.8,'bttsNo':1.8}}
        heads=[]
        for m,n in [('MS',3),('OU',2),('BTTS',2),('score',2)]:
            heads.append({'sport':'football','market':m,'forecastModel':{'transform':{'keys':['expectedTotal'],'median':[0.],'mean':[0.],'scale':[1.]},'weights':[[1. if j==0 else .5 for j in range(n)],[.1 if j==0 else -.1 for j in range(n)],[0.]*n]}})
        model={'payload':{'models':heads,'footballDistribution':{'dispersion':None,'rho':0},'basketballCovariance':[[100,0],[0,100]]}}
        write(root/'stability-model.json',model);write(root/'context-features.json',{'features':[]})
        e={'eventId':'1','name':'A - B','time':'23:59','prospectiveBeforeKickoff':True,'markets':{'MS':[.6,.2,.2],'OU':[.55,.45],'BTTS':[.6,.4]},'scoreMean':[2,1],'score':[2,1]};e['chosen']=choose(e,r,'football')
        write(root/'priced-complete-before-results.json',{'policy':trial.POLICY,'targetDate':day,'modelSha256':trial.digest(root/'stability-model.json'),'systems':{'football':{'experiment':[e]},'basketball':{'experiment':[]}}})
        write(root/'stability-before-results.json',{})
        write(root/'context-ledger.json',{'matches':[],'identities':[{'sport':'football','date':day,'eventId':'1','home':'ns:1','away':'ns:2','tournamentId':'10'}]})
        write(root/'live-history-journal.json',[]);write(root/'football-replay.json',[r]);write(root/'basketball-replay.json',[])
        return r
    def test_age_competition_and_future_boundaries(self):
        r={'date':'2026-08-08','tournamentId':'10'}
        self.assertAlmostEqual(trial.weight(r,'2026-11-06','football','10','recency'),.5)
        self.assertEqual(trial.weight(dict(r,tournamentId='20'),'2026-11-06','football','10','competition'),.25)
        for d in ('2026-11-06','2026-11-07'):
            self.assertEqual(trial.weight(dict(r,date=d),'2026-11-06','football','10','combined'),0)
        self.assertEqual(trial.weight(dict(r,date='2024-01-01'),'2026-11-06','football','10','recency'),0)
    def test_actual_feature_intervention_immutability_and_late_separation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.fixture(root);original={p:p.read_bytes() for p in root.iterdir()};out=root/'trial'
            with patch('outcome_learning.learn',side_effect=AssertionError('No training')):
                b=trial.freeze(root,out,datetime(2026,11,6,10,tzinfo=timezone.utc))
            self.assertTrue(b['systems']['football']['recency'][0]['inputAudit']['usedFeatureChanges'])
            snap=(out/trial.FILE).read_bytes();self.assertEqual(trial.freeze(root,out),b)
            for p,data in original.items():self.assertEqual(p.read_bytes(),data)
            report=trial.settle(root,out);self.assertTrue(all(x['count']==0 for block in report['beforeKickoff'].values() for x in block))
            rows=json.loads((root/'football-replay.json').read_text());rows[0]['realScore']='2-1';write(root/'football-replay.json',rows)
            report=trial.settle(root,out);self.assertTrue(all(x['count']==1 for x in report['beforeKickoff']['recency'] if x['sport']=='football'))
            self.assertEqual((out/trial.FILE).read_bytes(),snap)
            text=(out/'gecmis-baglam-deneyi.html').read_text();self.assertIn('A - B',text);self.assertNotIn('None',text)
    def test_missing_competition_exact_fallback_and_no_retroactive_freeze(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.fixture(root);write(root/'context-ledger.json',{'matches':[],'identities':[]})
            with self.assertRaises(ValueError):trial.freeze(root,root/'wrong',datetime(2026,11,7,10,tzinfo=timezone.utc))
            p=root/'priced-complete-before-results.json';v=json.loads(p.read_text());v['systems']['football']['experiment'][0]['time']='01:00';write(p,v)
            b=trial.freeze(root,root/'trial',datetime(2026,11,6,20,tzinfo=timezone.utc))
            ref=b['systems']['football']['main'][0];e=b['systems']['football']['competition'][0]
            self.assertEqual(e['chosen'],ref['chosen']);self.assertEqual(e['markets'],ref['markets']);self.assertFalse(e['prospectiveBeforeKickoff'])
    def test_strength_ignores_future_and_decays_old_matches(self):
        r={'sport':'football','date':'2026-08-08','home':'ns:1','away':'ns:2','homeScore':2,'awayScore':0,'tournamentId':'10'}
        ledger={'matches':[r,dict(r,date='2026-11-06',homeScore=0,awayScore=10)]}
        state=trial.WeightedContext(ledger,{},'10','recency').state('football','2026-11-06')
        self.assertEqual(len(state[0]),1);self.assertAlmostEqual(state[2]['ns:1'],.5);self.assertAlmostEqual(state[1]['ns:1'],.0375)
if __name__=='__main__':unittest.main()
