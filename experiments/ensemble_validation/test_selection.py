import copy,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from selection import select,freeze,settle

class SelectionTests(unittest.TestCase):
    def sample(self):
        es=[{'sport':'football','date':'2026-10-13','eventId':str(i),'name':'A - B','prospectiveBeforeKickoff':True,'markets':{'MS':p},'baselineMarkets':{'MS':[.5,.2,.3]},'score':[2,1],'baselineScore':[1,1]} for i,p in enumerate([[.8,.1,.1],[.4,.2,.4],[.65,.2,.15],[.4,.2,.4],[.6,.2,.2]])]
        book={'targetDate':'2026-10-13','createdAt':'2026-10-13T06:00:00+00:00','predictions':es}
        data={'football':[{'date':e['date'],'eventId':e['eventId'],'time':'23:00','realScore':'2-0'} for e in es],'basketball':[]};return book,data
    def test_half_ranking_ignores_outcomes_and_has_deterministic_ties(self):
        b,d=self.sample();b['predictions'][2]['markets']['MS']=[.4,.2,.4];b['predictions'][4]['markets']['MS']=[.4,.2,.4]
        now=datetime(2026,10,13,7,tzinfo=timezone.utc);a=select(b,d,now);self.assertEqual([x['eventId'] for x in a['groups'][0]['entries']],['0','1','2'])
        for r in d['football']:r['realScore']='0-9'
        b['predictions'].reverse();self.assertEqual(a,select(b,d,now))
    def test_late_selection_is_separate_from_forecast_timing(self):
        b,d=self.sample();a=select(b,d,datetime(2026,10,14,7,tzinfo=timezone.utc));self.assertTrue(all(not e['selectionBeforeKickoff'] for e in a['groups'][0]['entries']))
        b['predictions'][0]['prospectiveBeforeKickoff']=False;a=select(b,d);self.assertEqual(a['groups'][0]['eligibleCount'],4)
    def test_snapshot_reused_and_missing_live_outcomes_excluded(self):
        b,d=self.sample()
        with tempfile.TemporaryDirectory() as x:
            a=Path(x)/'a';c=Path(x)/'c';a.mkdir();c.mkdir()
            for p in [a,c]:(p/'learned-before-results.json').write_text(json.dumps(b))
            freeze(a,d);freeze(c,d,a);self.assertEqual((a/'selection-before-results.json').read_bytes(),(c/'selection-before-results.json').read_bytes())
            for r in d['football']:r['realScore']='LIVE 1-0'
            settle(c,d);r=json.loads((c/'selection-evaluation.json').read_text());self.assertIsNone(r['groups'][0]['selectedExploratory']['learned']);self.assertIsNone(r['groups'][0]['selectedProspective']['learned'])
            b['predictions'][0]['markets']['MS']=[.1,.1,.8];(c/'learned-before-results.json').write_text(json.dumps(b))
            with self.assertRaises(AssertionError):freeze(c,d,a)
