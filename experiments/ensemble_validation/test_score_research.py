import json,tempfile,unittest,copy
from pathlib import Path
from datetime import datetime,timezone
from score_research import *
from conditional_score import football_score

class ScoreResearchTests(unittest.TestCase):
    def seed(self,p,day='2026-10-23'):
        model={'payload':{'footballDistribution':{'dispersion':None,'rho':0}}}
        write(p/'stability-model.json',model)
        mean=[1.4,1.1];dist=model['payload']['footballDistribution']
        entry={'eventId':'1','name':'İstanbul - Beşiktaş','time':'20:00','scoreMean':mean,'chosen':{'market':'BTTS','option':0,'confidence':.7,'price':1.5},'score':football_score(mean,dist,'BTTS',0)['score'],'prospectiveBeforeKickoff':True}
        write(p/'priced-before-results.json',{'targetDate':day,'modelSha256':sha(p/'stability-model.json'),'systems':{'football':{'experiment':[entry]}}})
        write(p/'football-replay.json',[{'date':day,'eventId':'1','realScore':None}])
    def test_freeze_control_and_late_records_preserve_all_sources(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.seed(p)
            before={f.name:f.read_bytes() for f in p.iterdir()}
            b=freeze(p,now=datetime(2026,10,23,5,tzinfo=timezone.utc));raw=(p/SNAPSHOT).read_bytes()
            self.assertTrue(b['rows'][0]['beforeKickoff'])
            self.assertEqual(b['version'],VERSION);self.assertIn('validatedDispersion',b['rows'][0]['candidates'])
            for name,data in before.items():self.assertEqual((p/name).read_bytes(),data)
            write(p/'football-replay.json',[{'date':'2026-10-23','eventId':'1','realScore':'4-1'}])
            result=settle(p);self.assertEqual(result['beforeKickoff']['all']['locked']['count'],1)
            self.assertEqual((p/SNAPSHOT).read_bytes(),raw)
            self.assertEqual(freeze(p,now=datetime(2026,10,24,tzinfo=timezone.utc)),b)
            self.assertIn('Futbol Skor Deneyi',(p/'futbol-skor-deneyi.html').read_text())
            self.assertEqual(result['parameters']['trainingCount'],0)
            write(p/'football-replay.json',[{'date':'2026-10-23','eventId':'1','realScore':'1-1'}])
            self.assertEqual(settle(p)['beforeKickoff']['all']['locked']['exactHits'],1)
            # Tampered frozen research is rejected, not silently rebuilt.
            broken=read(p/SNAPSHOT);broken['rows'][0]['mean']=[3,3];write(p/SNAPSHOT,broken)
            with self.assertRaises(ValueError):settle(p)
    def test_future_today_and_late_labels_cannot_train(self):
        r={'date':'2026-10-22','mean':[1.,1.],'distribution':{'dispersion':None,'rho':0},'actual':[3,0],'originalBeforeKickoff':True}
        records=[dict(r,eventId=str(i)) for i in range(30)]
        expected=fit(records,'2026-10-23')
        polluted=records+[dict(r,date='2026-10-23',actual=[50,50])]*100+[dict(r,originalBeforeKickoff=False,actual=[50,50])]*100
        self.assertEqual(expected,fit(polluted,'2026-10-23'))
        self.assertEqual(expected['bias'],[1.,-.5]);self.assertEqual(expected['trainingCount'],30)
        self.assertFalse(fit(records,'2026-10-22')['active'])
    def test_validated_dispersion_uses_prior_results_and_reports_concentration(self):
        records=[{'date':'2026-10-22','eventId':str(i),'mean':[1.2,1.1],'distribution':{'dispersion':None,'rho':0},'actual':[0,0] if i%2 else [3,0],'originalBeforeKickoff':True} for i in range(40)]
        params=fit(records,'2026-10-23');self.assertIn(params['selectedDispersion'],params['dispersionGrid']);self.assertEqual(set(params['dispersionLogLoss']),{'poisson','2','3','5','8','12'})
        row={'mean':[1.4,1.1],'distribution':{'dispersion':None,'rho':0},'chosen':{'market':'MS','option':0}}
        d=diagnostics([dict(row,candidates={c:forecast(row,c,params) for c in CANDIDATES},actual=[2,0])])['validatedDispersion']
        self.assertIn('oneOneRate',d);self.assertIn('uniqueModalScores',d);self.assertIn('topModalRate',d)
    def test_all_choices_compatible_and_top_three_distinct(self):
        for market,options in [('MS',range(3)),('BTTS',range(2)),('OU',range(2))]:
            for i in options:
                row={'mean':[1.4,1.1],'distribution':{'dispersion':None,'rho':-.1},'chosen':{'market':market,'option':i}}
                for c in CANDIDATES:
                    f=forecast(row,c,{'bias':[.2,-.1]})
                    self.assertEqual(len({tuple(x['score']) for x in f['top3']}),3)
                    self.assertTrue(all(compatible(*x['score'],'football',market,i) for x in f['top3']))
                    self.assertTrue(all(0<x['probability']<1 for x in f['top3']))
                    self.assertLessEqual(sum(x['conditionalProbability'] for x in f['top3']),1.0000001)
                    self.assertTrue(0<f['fourPlusProbability']<1)
                self.assertEqual(forecast(row,'locked',{'bias':[0,0]})['score'],football_score(row['mean'],row['distribution'],market,i)['score'])
    def test_missing_labels_excluded_and_incompatible_result_has_finite_loss(self):
        row={'mean':[1.4,1.1],'distribution':{'dispersion':None,'rho':0},'chosen':{'market':'BTTS','option':0}}
        r=dict(row,candidates={c:forecast(row,c,{'bias':[0,0]}) for c in CANDIDATES},actual=[0,0])
        for c in CANDIDATES:
            m=metrics([r,dict(r,actual=None)],c)
            self.assertEqual(m['count'],1);self.assertEqual(m['top3Hits'],0);self.assertTrue(math.isfinite(m['logLoss']))
    def test_before_start_and_late_are_not_independent(self):
        for day,now in [('2026-10-22',datetime(2026,10,22,5,tzinfo=timezone.utc)),('2026-10-23',datetime(2026,10,23,19,tzinfo=timezone.utc))]:
            with tempfile.TemporaryDirectory() as t:
                p=Path(t);self.seed(p,day);b=freeze(p,now=now);self.assertFalse(b['rows'][0]['beforeKickoff'])
    def test_previous_day_results_only_bootstrap_calibration(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.seed(p,'2026-10-22')
            write(p/'football-replay.json',[{'date':'2026-10-22','eventId':'1','realScore':'1-1'}])
            h=history(p,'2026-10-23');self.assertEqual(len(h),1);self.assertEqual(h[0]['actual'],[1,1])
            self.assertEqual(history(p,'2026-10-22'),[])
    def test_old_control_does_not_create_research_predictions(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.seed(p,'2026-10-22');self.assertIsNone(settle(p));self.assertFalse((p/SNAPSHOT).exists())
    def test_existing_v1_snapshot_remains_settleable_without_fourth_candidate(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.seed(p);b=freeze(p,now=datetime(2026,10,23,5,tzinfo=timezone.utc))
            b['version']=LEGACY_VERSION;b.pop('candidates');b.pop('concentrationCandidateFirstIndependentDate')
            for row in b['rows']:row['candidates'].pop('validatedDispersion')
            b['retrospective']['metrics']={subset:{k:v for k,v in values.items() if k in CANDIDATES_V1} for subset,values in b['retrospective']['metrics'].items()}
            b['snapshotSha256']=signature({k:v for k,v in b.items() if k!='snapshotSha256'});write(p/SNAPSHOT,b)
            write(p/'football-replay.json',[{'date':'2026-10-23','eventId':'1','realScore':'1-1'}])
            result=settle(p);self.assertEqual(result['version'],LEGACY_VERSION);self.assertNotIn('validatedDispersion',result['beforeKickoff']['all'])
    def test_control_guard_protects_research_snapshot(self):
        from control_runtime import hashes,verify
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);write(p/SNAPSHOT,{'frozen':True});write(p/'control-lock.json',{'hashes':hashes(p)})
            verify(p);write(p/SNAPSHOT,{'frozen':False})
            with self.assertRaises(ValueError):verify(p)
    def test_private_export_includes_report_but_not_training_data(self):
        from private_reports import collect,publish
        from test_private_reports import FakeApi
        from datetime import date
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            for f in ['daily-evaluation.json','input-manifest.json','context-evaluation.json','stability-journal.json','score-research-evaluation.json']:
                write(p/f,{'date':'2026-10-23'})
            write(p/JOURNAL,{'records':['private-training']});write(p/SNAPSHOT,{'targetDate':'2026-10-23'})
            (p/'futbol-skor-deneyi.html').write_text('<h1>Skor Deneyi</h1>')
            files,_=collect(p);self.assertNotIn(JOURNAL,files);self.assertNotIn(SNAPSHOT,files)
            api=FakeApi();publish(api,files,{'targetDate':'2026-10-23','sourceRunId':'1'},date(2026,10,23))
            paths={x['path'] for x in api.writes[0][2]['tree']}
            self.assertIn('raporlar/2026-10-23/futbol-skor-deneyi.html',paths)
            self.assertIn('deney/reports/2026-10-23/score-research-evaluation.json',paths)

if __name__=='__main__':unittest.main()

