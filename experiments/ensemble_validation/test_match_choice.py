import copy,json,tempfile,unittest
import hashlib
from datetime import datetime,timezone
from pathlib import Path
from match_choice import choices,freeze,settle
import test_selection

class MatchChoiceTests(unittest.TestCase):
    def test_late_fixture_is_visible_but_cannot_change_confidence_subsets_or_success(self):
        b,d=self.sample();b['predictions'][0]['prospectiveBeforeKickoff']=False;b['predictions'][0]['markets']['BTTS']=[.999,.001]
        with tempfile.TemporaryDirectory() as x:
            p=Path(x);(p/'learned-before-results.json').write_text(json.dumps(b));freeze(p,d);settle(p,d)
            saved=json.loads((p/'match-choice-before-results.json').read_text());late=next(e for e in saved['predictions'] if e['eventId']=='0')
            self.assertFalse(late['selected']);self.assertIsNone(late['rank']);self.assertEqual(len(saved['predictions']),5)
            r=json.loads((p/'match-choice-evaluation.json').read_text())['sports'][0]
            self.assertEqual(r['eligibleForecastCount'],4);self.assertEqual(r['all']['count'],4);self.assertEqual([g['plannedCount'] for g in r['confidenceSubsets']],[1,2,3,4])
            text=(p/'best-matches.html').read_text();self.assertEqual(text.count('data-confidence='),5);self.assertIn('Geç tahmin · kapsam dışı',text)
    def sample(self):
        b,d=test_selection.SelectionTests().sample()
        for e in b['predictions']:
            e['markets'].update({'OU':[.2,.8],'BTTS':[.9,.1]});e['baselineMarkets'].update({'OU':[.4,.6],'BTTS':[.8,.2]})
        return b,d
    def test_one_best_market_and_half_matches_ignore_labels_and_scores(self):
        b,d=self.sample();now=datetime(2026,10,13,7,tzinfo=timezone.utc);a=choices(b,d,now)
        self.assertEqual(len(a['predictions']),5);self.assertEqual(sum(e['selected'] for e in a['predictions']),3)
        self.assertTrue(all(e['pick']=='KG Var' for e in a['predictions']));self.assertTrue(all(min(e['score'])>0 for e in a['predictions']))
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
            self.assertEqual([g['plannedCount'] for g in r['sports'][0]['confidenceSubsets']],[2,3,4,5])
            self.assertTrue(all(g['exploratory'] is None for g in r['sports'][0]['confidenceSubsets']))
            text=(c/'best-matches.html').read_text();self.assertEqual(text.count('data-confidence='),5)
            self.assertIn('sort-confidence',text);self.assertIn('Güven sırasına göre alt kümeler',text)

    def test_new_distribution_score_does_not_rewrite_original_or_existing_choice(self):
        b,d=self.sample()
        with tempfile.TemporaryDirectory() as x:
            a=Path(x)/'a';c=Path(x)/'c';a.mkdir();c.mkdir();raw=json.dumps(b).encode()
            for p in [a,c]:(p/'learned-before-results.json').write_bytes(raw)
            candidate={'targetDate':b['targetDate'],'meanForecastSha256':hashlib.sha256(raw).hexdigest(),'predictions':[{'sport':'football','date':b['targetDate'],'eventId':'0','score':[1,0],'probability':.2}]}
            (a/'score-before-results.json').write_text(json.dumps(candidate));freeze(a,d)
            saved=json.loads((a/'match-choice-before-results.json').read_text());e=next(e for e in saved['predictions'] if e['eventId']=='0')
            self.assertGreater(min(e['score']),0);self.assertEqual(e['pick'],'KG Var');self.assertEqual(e['scoreMethod'],'conditional_distribution');self.assertEqual(raw,(a/'learned-before-results.json').read_bytes())
            candidate['predictions'][0]['score']=[9,9];(c/'score-before-results.json').write_text(json.dumps(candidate));freeze(c,d,a)
            self.assertEqual((a/'match-choice-before-results.json').read_bytes(),(c/'match-choice-before-results.json').read_bytes())

