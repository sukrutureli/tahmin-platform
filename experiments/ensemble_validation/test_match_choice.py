import copy,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from match_choice import choices,freeze,settle
import test_selection

class MatchChoiceTests(unittest.TestCase):
    def sample(self):
        b,d=test_selection.SelectionTests().sample()
        for e in b['predictions']:
            e['markets'].update({'OU':[.2,.8],'BTTS':[.9,.1]});e['baselineMarkets'].update({'OU':[.4,.6],'BTTS':[.8,.2]})
        return b,d
    def test_one_best_market_and_half_matches_ignore_labels_and_scores(self):
        b,d=self.sample();now=datetime(2026,10,13,7,tzinfo=timezone.utc);a=choices(b,d,now)
        self.assertEqual(len(a['predictions']),5);self.assertEqual(sum(e['selected'] for e in a['predictions']),3)
        self.assertTrue(all(e['pick']=='KG Var' for e in a['predictions']));self.assertTrue(all(e['scoreline']=='2-1' for e in a['predictions']))
        for r in d['football']:r['realScore']='0-9'
        self.assertEqual(a,choices(b,d,now))
        for e in b['predictions']:e['score']=[100,100]
        c=choices(b,d,now);self.assertEqual([e['pick'] for e in a['predictions']],[e['pick'] for e in c['predictions']])
    def test_total_line_and_late_selection(self):
        b,d=self.sample()
        for e in b['predictions']:e['markets']['OU']=[.99,.01]
        a=choices(b,d,datetime(2026,10,14,7,tzinfo=timezone.utc));self.assertTrue(all(e['pick']=='2.5 Üst' and not e['selectionBeforeKickoff'] for e in a['predictions']))
    def test_reuse_and_live_exclusion(self):
        b,d=self.sample()
        with tempfile.TemporaryDirectory() as x:
            a=Path(x)/'a';c=Path(x)/'c';a.mkdir();c.mkdir()
            for p in [a,c]:(p/'learned-before-results.json').write_text(json.dumps(b))
            freeze(a,d);freeze(c,d,a);self.assertEqual((a/'match-choice-before-results.json').read_bytes(),(c/'match-choice-before-results.json').read_bytes())
            for r in d['football']:r['realScore']='LIVE 1-0'
            settle(c,d);r=json.loads((c/'match-choice-evaluation.json').read_text());self.assertIsNone(r['sports'][0]['selectedExploratory'])
