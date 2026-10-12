import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from live_history import collect_day, schedule_row

class LiveHistoryTests(unittest.TestCase):
    def row(self, state=5):
        return {'id':77,'date':'10/09/2026 21:30:00','status':{'id':state},
                'teamType':'away','team':{'name':'Opponent'},
                'scores':{'home':{'ordinary':80,'current':90},'away':{'ordinary':80,'current':85}}}

    def test_utc_to_istanbul_and_no_same_day_or_live(self):
        self.assertIsNone(schedule_row(self.row(),date(2026,10,10),'basketball'))
        self.assertIsNone(schedule_row(self.row(2),date(2026,10,11),'basketball'))
        r=schedule_row(self.row(9),date(2026,10,11),'basketball')
        self.assertEqual((r['date'],r['venue'],r['for'],r['against'],r['win']),('2026-10-10','home',80,80,1))

    def test_overtime_without_regulation_excluded(self):
        r=self.row(9)
        del r['scores']['home']['ordinary']
        self.assertIsNone(schedule_row(r,date(2026,10,11),'basketball'))

    def test_same_day_snapshot_reused_without_http(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);previous=root/'previous';previous.mkdir()
            saved={'targetDate':'2026-10-11','fixtures':[],'errors':[{'reason':'gap preserved'}]}
            (previous/'live-history.json').write_text(json.dumps(saved))
            with patch('live_history.Client.get',side_effect=AssertionError('No HTTP on settled day')):
                self.assertEqual(collect_day(root/'absent',previous,root/'out','2026-10-11'),saved)

class LivePreparationTests(unittest.TestCase):
    def test_exact_fixture_and_day_live_history_with_future_filter(self):
        from prepare import assemble, dump
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'published';data=source/'futbol/data';ref=root/'ref';out=root/'out'
            target='2026-10-11'
            dump(ref/'predictions.json',[])
            dump(data/f'MatchInfo-{target}.json',[{'detailUrl':'https://istatistik.nesine.com/123','name':'A - B','time':'18:00','odds':{}}])
            dump(data/f'TeamMatchHistory-{target}.json',[{'originalMatchUrl':'https://istatistik.nesine.com/123','teamEv':'A','teamDep':'B'}])
            base={'homeTeam':'A','awayTeam':'B','odds':{},'homeStats':{},'awayStats':{}}
            dump(data/f'Match-{target}.json',[base]);dump(data/f'PredictionResult-{target}.json',[base])
            row={'id':'old','date':'2026-10-09','venue':'home','for':1,'against':0,'win':1,'draw':0,'tournament':''}
            future=dict(row,id='future',date=target)
            fixture={'sport':'football','eventId':'123','teams':['A','B'],'sides':[{'rows':[row,future]},{'rows':[row,future]}],'collectedAt':'2026-10-11T11:00:00Z','beforeKickoff':True}
            live=root/'live.json';dump(live,[{'targetDate':target,'fixtures':[fixture]}])
            rows=assemble([source],ref,out,target,live)['football']
            self.assertTrue(rows[0]['wideAvailable'])
            self.assertEqual(rows[0]['variants']['wide-balanced']['audit']['home']['count'],1)
            dump(live,[{'targetDate':'2026-10-10','fixtures':[fixture]}])
            self.assertFalse(assemble([source],ref,out,target,live)['football'][0]['wideAvailable'])
            fixture['teams']=['U21 A','B'];dump(live,[{'targetDate':target,'fixtures':[fixture]}])
            with self.assertRaisesRegex(ValueError,'identity mismatch'):
                assemble([source],ref,out,target,live)

class CollectionBudgetTests(unittest.TestCase):
    def test_football_budget_cannot_starve_basketball(self):
        from prepare import dump
        clock=[0]
        def fake_collect(info,history,cutoff,sport):
            clock[0]+=1.1
            return [{'rows':[]},{'rows':[]}]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for folder,ids in [('futbol',['1','2']),('basketbol',['3'])]:
                dump(root/folder/'data/MatchInfo-2026-10-12.json',[{'detailUrl':'https://istatistik.nesine.com/'+i,'time':'23:59'} for i in ids])
                dump(root/folder/'data/TeamMatchHistory-2026-10-12.json',[{'originalMatchUrl':'https://istatistik.nesine.com/'+i,'teamEv':'A','teamDep':'B'} for i in ids])
            with patch('live_history.time.monotonic',side_effect=lambda:clock[0]), patch('live_history.Collector.collect',side_effect=fake_collect):
                s=collect_day(root,root/'previous',root/'out','2026-10-12',max_seconds=2)
            self.assertEqual([r['sport'] for r in s['fixtures']],['football','basketball'])
            self.assertTrue(s['stoppedEarly'])
            self.assertFalse(s['rateLimited'])
            self.assertEqual(s['errors'][0]['eventId'],'2')
