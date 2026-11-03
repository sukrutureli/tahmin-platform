import copy,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from competition_blend import history,estimate,freeze,settle,FILE

class CompetitionTests(unittest.TestCase):
    def fixture(self,root):
        rows=[]
        for i in range(1,8):
            for home,away in [('ns:1','ns:3'),('ns:4','ns:2')]:
                rows.append({'key':home+str(i),'sport':'football','date':'2026-10-'+str(20+i),'home':home,'away':away,'homeScore':3,'awayScore':0,'tournamentId':'10'})
        ident={'sport':'football','date':'2026-11-04','eventId':'1','home':'ns:1','away':'ns:2','tournamentId':'10'}
        e={'eventId':'1','time':'20:00','name':'A - B','prospectiveBeforeKickoff':True,'scoreMean':[1.5,1.2],'score':[2,1],'chosen':{'market':'MS','option':0,'confidence':.6,'price':1.8},'markets':{'MS':[.6,.2,.2],'OU':[.55,.45],'BTTS':[.6,.4]}}
        b={'targetDate':'2026-11-04','systems':{'football':{'experiment':[e]},'basketball':{'experiment':[]}}}
        def put(n,v):(root/n).write_text(json.dumps(v))
        put('priced-before-results.json',b);put('context-ledger.json',{'matches':rows,'identities':[ident]});put('live-history-journal.json',[])
        put('stability-model.json',{'payload':{'footballDistribution':{'dispersion':None,'rho':0},'basketballCovariance':[[100,0],[0,100]]}})
        put('football-replay.json',[{'date':'2026-11-04','eventId':'1','realScore':'2-0','odds':{'ms1':1.8,'msX':3.,'ms2':4.,'over25':1.7,'under25':2.,'bttsYes':1.7,'bttsNo':2.}}]);put('basketball-replay.json',[])
        return ident,rows
    def test_competition_and_date_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            ident,rows=self.fixture(Path(td))
            rows+= [dict(rows[0],key='future',date='2026-11-04'),dict(rows[0],key='other-league',tournamentId='99'),dict(rows[0],key='old',date='2025-01-01')]
            chosen=history(rows,ident,'ns:1','football','2026-11-04')
            self.assertEqual(len(chosen),6);self.assertFalse({'future','other-league','old'}&{r['key'] for r in chosen})
            est,counts=estimate(rows,ident,'football','2026-11-04',2.5)
            self.assertEqual(counts,[6,6]);self.assertEqual(est['markets']['MS'],[1,0,0])
            self.assertEqual(estimate(rows,None,'football','2026-11-04',2.5),(None,[0,0]))
    def test_fixed_mix_immutability_and_same_day_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.fixture(root);original={p.name:p.read_bytes() for p in root.iterdir()}
            b=freeze(root,datetime(2026,11,4,8,tzinfo=timezone.utc));e=b['systems']['football']['experiment'][0]
            self.assertEqual(e['sameCompetition']['weight'],.1);self.assertAlmostEqual(e['markets']['MS'][0],.64)
            for probs in e['markets'].values():self.assertAlmostEqual(sum(probs),1)
            snap=(root/FILE).read_bytes();self.assertEqual(freeze(root),b);settle(root);self.assertEqual((root/FILE).read_bytes(),snap)
            for name,data in original.items():self.assertEqual((root/name).read_bytes(),data)
            result=json.loads((root/'competition-evaluation.json').read_text());self.assertTrue(all(r['count']==1 for r in result['beforeKickoff']))
    def test_sparse_missing_and_late(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ident,rows=self.fixture(root)
            ledger=json.loads((root/'context-ledger.json').read_text());ledger['matches']=[r for r in rows if r['date']>='2026-10-25'];(root/'context-ledger.json').write_text(json.dumps(ledger))
            b=freeze(root,datetime(2026,11,4,21,tzinfo=timezone.utc));e=b['systems']['football']['experiment'][0]
            self.assertAlmostEqual(e['sameCompetition']['weight'],.05);self.assertFalse(e['prospectiveBeforeKickoff'])
            settle(root);r=json.loads((root/'competition-evaluation.json').read_text());self.assertTrue(all(x['count']==0 for x in r['beforeKickoff']))
    def test_missing_history_keeps_current_forecast_exactly(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.fixture(root);p=root/'context-ledger.json';ledger=json.loads(p.read_text());ledger['matches']=[];p.write_text(json.dumps(ledger))
            b=freeze(root,datetime(2026,11,4,8,tzinfo=timezone.utc))
            ref=b['systems']['football']['main'][0];e=b['systems']['football']['experiment'][0]
            self.assertEqual(e['sameCompetition']['weight'],0)
            self.assertEqual(e['markets'],ref['markets']);self.assertEqual(e['score'],ref['score']);self.assertEqual(e['chosen'],ref['chosen'])
    def test_basketball_own_line_and_sport_isolation(self):
        ident={'home':'ns:1','away':'ns:2','tournamentId':'10'}
        rows=[{'key':'h','sport':'basketball','date':'2026-11-01','home':'ns:1','away':'ns:3','homeScore':95,'awayScore':80,'tournamentId':'10'},
              {'key':'a','sport':'basketball','date':'2026-11-01','home':'ns:4','away':'ns:2','homeScore':90,'awayScore':75,'tournamentId':'10'}]
        e,n=estimate(rows,ident,'basketball','2026-11-04',170)
        self.assertEqual(n,[1,1]);self.assertEqual(e['markets']['OU'],[.5,.5]);self.assertEqual(e['markets']['MS'],[1,0]);self.assertNotIn('BTTS',e['markets'])
        self.assertEqual(estimate(rows,ident,'football','2026-11-04',2.5)[1],[0,0])
    def test_human_readable_pending_report(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.fixture(root);p=root/'football-replay.json';rows=json.loads(p.read_text());rows[0]['realScore']=None;p.write_text(json.dumps(rows))
            freeze(root,datetime(2026,11,4,8,tzinfo=timezone.utc));settle(root)
            text=(root/'ayni-lig-deneyi.html').read_text()
            self.assertIn('Sonuç bekleniyor',text);self.assertIn('A - B',text);self.assertIn('Mevcut',text);self.assertIn('Lig/kupa',text);self.assertNotIn('None',text)
    def test_no_backfill_before_launch(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.fixture(root);p=root/'priced-before-results.json';b=json.loads(p.read_text());b['targetDate']='2026-11-03';p.write_text(json.dumps(b))
            self.assertIsNone(freeze(root));self.assertFalse((root/FILE).exists());self.assertIsNone(settle(root))

if __name__=='__main__':unittest.main()
