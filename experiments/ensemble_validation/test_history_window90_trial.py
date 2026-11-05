import copy,json,tempfile,unittest
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
import history_window90_trial as trial
import test_history_context_trial as original
from window_features import features,pools,StrengthContext
from priced_choices import read,write

class WindowTests(unittest.TestCase):
    def row(self,days,gf=2,league='10'):
        return {'id':str(days),'date':(date(2026,11,6)-timedelta(days=days)).isoformat(),'for':gf,'against':1,'win':int(gf>1),'draw':int(gf==1),'venue':'home','tournamentId':league}
    def test_uses_more_than_twenty_five_and_separate_last_six(self):
        h=[self.row(i,3 if i<=3 else 2) for i in range(1,36)];a=[dict(r,venue='away',**{'for':1}) for r in h]
        row={'date':'2026-11-06','_window90Rows':[h,a],'odds':{}}
        f,audit=features(row,'football','window90',{'tournamentId':'10'})
        self.assertEqual(audit['historyCounts'],[35,35]);self.assertEqual(audit['shortCounts'],[6,6]);self.assertAlmostEqual(f['homeFor'],73/35)
        self.assertAlmostEqual(f['formTrendDifference'],1.);self.assertEqual(f['wideMinimumCount'],35)
    def test_window_and_dedup_no_forced_fill(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);r=original.TrialTests().fixture(root)
            rs=[self.row(i) for i in range(1,36)]+[self.row(91),self.row(0),self.row(-1)]
            write(root/'live-history-journal.json',[{'targetDate':'2026-11-06','fixtures':[{'sport':'football','eventId':'1','sides':[{'source':'broadage-team-schedule','teamId':'1','rows':rs+rs},{'source':'broadage-team-schedule','teamId':'2','rows':[self.row(2)]}]}]}])
            idx={('football','2026-11-06','1'):{'home':'broadage:1','away':'broadage:2'}}
            bank,meta=pools(root,{'matches':[]},idx,'2026-11-06',read)
            self.assertEqual(list(map(len,bank[('football','2026-11-06','1')])),[35,1])
    def test_organization_missing_is_plain_window_and_strength_keeps_broad_history(self):
        row={'date':'2026-11-06','_window90Rows':[[self.row(10),self.row(20,5,'20')],[self.row(10),self.row(20,1,'20')]],'odds':{}}
        plain,_=features(row,'football','window90',None);org,_=features(row,'football','competition',None)
        self.assertEqual(plain,org)
        org,_=features(row,'football','competition',{'tournamentId':'10'});self.assertNotEqual(org['homeFor'],plain['homeFor'])
        m={'sport':'football','date':self.row(180)['date'],'home':'ns:1','away':'ns:2','homeScore':2,'awayScore':0,'tournamentId':'10'}
        ctx=StrengthContext({'matches':[m]}, {},'10','window90');state=ctx.state('football','2026-11-06')
        self.assertEqual(len(state[0]),1);self.assertAlmostEqual(state[2]['ns:1'],.25)
    def test_real_frozen_heads_read_only_and_original_results_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);original.TrialTests().fixture(root)
            # Inputs older than 90 days cannot be used merely to reach a row quota.
            p=root/'football-replay.json';rows=read(p);rows[0]['realScore']='2-1'
            for side in ('home','away'):
                for r in rows[0]['variants']['six-simple']['audit'][side]['rows']:r['id']=r['date']
            write(p,rows)
            protected={p:p.read_bytes() for p in root.iterdir()};out=root/'trial90'
            with patch('outcome_learning.learn',side_effect=AssertionError('No training')):
                b=trial.freeze(root,out,datetime(2026,11,6,1,tzinfo=timezone.utc))
            self.assertEqual(len(b['systems']['football']),5)
            e=b['systems']['football']['window90'][0];self.assertEqual(e['inputAudit']['historyCounts'],[2,2]);self.assertLessEqual(max(e['inputAudit']['oldestAgeDays']),90)
            snap=(out/trial.FILE).read_bytes();trial.seal_eligibility(root,out);report=trial.settle(root,out)
            self.assertTrue(all(r['count']==0 for block in report['beforeKickoff'].values() for r in block))
            self.assertEqual(trial.freeze(root,out),b);self.assertEqual((out/trial.FILE).read_bytes(),snap)
            for p,data in protected.items():self.assertEqual(p.read_bytes(),data)
            text=(out/'90-gun-gecmis-deneyi.html').read_text();self.assertIn('Geçmiş: 2/2 maç',text)
if __name__=='__main__':unittest.main()
