import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import user_rules as r

DAY = '2026-11-27'
IDENT = {'home':'n:1','away':'n:2','namespace':'n','tournamentId':'10'}
ODDS = {'ms1':1.5,'msX':3.,'ms2':2.,'over25':1.8,'under25':1.8,'bttsYes':1.8,'bttsNo':1.8,'over':1.8,'under':1.8,'hOverUnderValue':160.5}


def match(key, team, gf, ga, day, opponent=None, tournament='10', sport='football'):
    return {'key':str(key),'sport':sport,'namespace':'n','date':day,'home':team,'away':opponent or 'n:x'+str(key),
            'homeScore':gf,'awayScore':ga,'homeFinal':gf,'awayFinal':ga,'tournamentId':tournament}


def row(sport='football'):
    return {'eventId':'123','date':DAY,'time':'23:00','name':'Home - Away','odds':copy.deepcopy(ODDS),'realScore':None,'sport':sport}


def example():
    # User's screenshots: the away team's scores are relative to that team.
    records=[]
    for t, scores in [('n:1',[(1,1),(2,2),(2,3),(4,0)]),('n:2',[(1,1),(6,0),(1,1),(1,2)])]:
        for i,(a,b) in enumerate(scores):records.append(match(t+str(i),t,a,b,f'2026-11-{25-i:02d}'))
    return records


class RulesTests(unittest.TestCase):
    def test_ten_percent_recency_and_probability_mass(self):
        def histories(newest_wins):
            scores=[(2,0)]*3+[(0,2)]*3
            if not newest_wins:scores.reverse()
            out=[]
            for t in ('n:1','n:2'):
                for j,(a,b) in enumerate(scores):
                    if t=='n:2':a,b=b,a # Away losses support MS1.
                    out.append(match(t+str(j),t,a,b,f'2026-11-{25-j:02d}'))
            return out
        for recent,p in [(True,.5214285714285715),(False,.4785714285714286)]:
            e=r.calculate(row(),'football',histories(recent),IDENT)
            self.assertAlmostEqual(e['markets']['MS'][0],p)
            for probabilities in e['markets'].values():self.assertAlmostEqual(sum(probabilities),1)
        # Fewer samples do not receive extra team influence just because weights differ.
        data=[match(str(j),'n:1',2,0,f'2026-11-{25-j:02d}') for j in range(6)]
        data += [match('away','n:2',2,0,'2026-11-25')]
        e=r.calculate(row(),'football',data,IDENT)
        self.assertAlmostEqual(e['markets']['MS'][0],6/7)

    def test_legacy_rules_snapshot_still_verifies_without_refreeze(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/r.MODEL).write_text(r.LEGACY_MODEL_TEXT)
            book={'policy':r.LEGACY_POLICY,'targetDate':DAY,'modelSha256':r.POLICY_HASHES[r.LEGACY_POLICY],'inputHashes':{},'systems':{}}
            book['snapshotSha256']=r.signature(book);r.write(root/r.FILE,book)
            self.assertEqual(r.verify(root),book)
            self.assertEqual(r.freeze(root,DAY),book)
    def test_percentile_boundaries_include_whole_tied_group(self):
        es=[{'eventId':str(i),'chosen':{'confidence':p}} for i,p in enumerate([.9,.8,.8,.7,.7,.7,.6])]
        self.assertEqual(len(r.tied_prefix(es,.25)),3)
        self.assertEqual(len(r.tied_prefix(es,.5)),6)
        self.assertEqual(len(r.tied_prefix(es,1)),7)
        self.assertEqual(r.tied_positions(es),{'0':0,'1':1,'2':1,'3':3,'4':3,'5':3,'6':6})
        self.assertEqual(r.tied_prefix([], .5),[])
        # Equality is not inferred from the one-decimal display percentage.
        close=[{'eventId':'a','chosen':{'confidence':.70004}},{'eventId':'b','chosen':{'confidence':.7}}]
        self.assertEqual(len(r.tied_prefix(close,.5)),1)
        self.assertEqual(len(r.tied_prefix([{'eventId':str(i),'chosen':{'confidence':.625}} for i in range(5)],.25)),5)
    def test_screenshot_fractions_and_contrarian_selection(self):
        e=r.calculate(row(),'football',example(),IDENT)
        for actual,expected in zip(e['markets']['MS'],[.235,.515,.25]):self.assertAlmostEqual(actual,expected)
        self.assertEqual(e['markets']['OU'],[.6125,.3875])
        for actual,expected in zip(e['markets']['BTTS'],[.755,.245]):self.assertAlmostEqual(actual,expected)
        self.assertEqual(e['calculation']['markets']['OU'][0]['teamNumerators'],[3,2])
        self.assertEqual(e['calculation']['markets']['OU'][0]['plainProbability'],.625)
        self.assertEqual((e['chosen']['market'],e['chosen']['option']),('OU',0))
        self.assertEqual([(c['supportHits'],c['supportCount']) for c in e['calculation']['topTwo']],[(2,2),(0,2)])

    def test_h2h_orientation_and_80_20(self):
        records=example()+[match('h2h','n:2',0,1,'2025-01-01',opponent='n:1',tournament='99')]
        e=r.calculate(row(),'football',records,IDENT)
        self.assertAlmostEqual(e['markets']['MS'][0],.235*.8+.2)
        self.assertAlmostEqual(e['markets']['OU'][0],.6125*.8)
        self.assertAlmostEqual(e['markets']['BTTS'][0],.755*.8)
        self.assertEqual(e['calculation']['h2hCount'],1)

    def test_same_competition_before_six_cap_and_individual_general_fallback(self):
        records=[match(i,'n:1',2,0,f'2026-11-{25-i:02d}') for i in range(8)]
        records+=[match('a','n:2',0,2,'2026-11-25',tournament='99'),match('b','n:1',0,8,'2026-11-26',tournament='99')]
        e=r.calculate(row(),'football',records,IDENT)
        self.assertEqual(e['calculation']['teamCounts'],{'home':6,'away':1})
        self.assertEqual(e['markets']['MS'],[1,0,0])
        self.assertIn('Genel',e['calculation']['teamScopes']['away'])
        records += [match('future','n:1',0,9,DAY),match('future2','n:2',9,0,'2026-11-28')]
        self.assertEqual(r.calculate(row(),'football',records,IDENT),e)

    def test_selection_support_and_tie_table(self):
        def c(p,h,n):return {'confidence':p,'supportHits':h,'supportCount':n}
        for x,y,expected in [(c(.8,2,3),c(.7,1,3),1),(c(.8,3,3),c(.7,3,3),1),
                             (c(.8,2,3),c(.7,2,3),0),(c(.8,2,2),c(.7,2,2),1),
                             (c(.8,1,2),c(.7,1,2),0),(c(.8,0,2),c(.7,0,2),0),
                             (c(.8,1,1),c(.7,1,1),1),(c(.8,0,0),c(.7,0,0),0),
                             (c(.8,1,3),c(.7,1,2),0)]:
            with self.subTest(x=x,y=y):self.assertIs(r.select([x,y])[0],[x,y][expected])

    def test_identical_top_two_selects_both(self):
        records=[match('h','n:1',2,0,'2026-11-25'),match('a','n:2',0,2,'2026-11-25')]
        e=r.calculate(row(),'football',records,IDENT)
        self.assertEqual(len(e['choices']),2)
        self.assertEqual({(v['market'],v['option']) for v in e['choices']},{('MS',0),('OU',1)})
        self.assertEqual([v['confidence'] for v in e['choices']],[1,1])

    def test_opposite_equal_markets_are_skipped_and_all_equal_means_no_pick(self):
        records=[]
        for t,scores in [('n:1',[(2,0),(0,2),(3,2),(2,3)]),('n:2',[(3,2),(2,3),(2,0),(0,2)])]:
            records.extend(match(t+str(i),t,*v,f'2026-11-{25-i:02d}') for i,v in enumerate(scores))
        e=r.calculate(row(),'football',records,IDENT)
        self.assertIsNone(e['chosen']);self.assertEqual(e['choices'],[])
        self.assertEqual(set(e['calculation']['skippedMarkets']),{'MS','OU','BTTS'})
        # Two ambiguous markets leave the third as the direct source of choice.
        records[0].update(homeScore=3,awayScore=0,homeFinal=3,awayFinal=0)
        e=r.calculate(row(),'football',records,IDENT)
        self.assertEqual(e['chosen']['market'],'OU')
        self.assertEqual(set(e['calculation']['skippedMarkets']),{'MS','BTTS'})

    def test_fixture_scoped_raw_h2h_is_used_even_outside_wide_window(self):
        x=row();x['userRuleHistory']={'teamEv':'Home','teamDep':'Away',
            'sonMaclarHome':[{'homeTeam':'Home','awayTeam':'Other','homeScore':2,'awayScore':0,'matchDate':'25 Kasım 2026'}],
            'sonMaclarAway':[{'homeTeam':'Away','awayTeam':'Other','homeScore':0,'awayScore':2,'matchDate':'25 Kasım 2026'}],
            'rekabetGecmisi':[{'homeTeam':'Away','awayTeam':'Home','homeScore':0,'awayScore':2,'matchDate':'15 Ekim 2023'}]}
        e=r.calculate(x,'football',[],None)
        self.assertEqual(e['calculation']['h2hCount'],1)
        self.assertEqual(e['markets']['MS'],[1,0,0])
        self.assertEqual(e['chosen']['supportCount'],3)
        self.assertIn('Genel',e['calculation']['teamScopes']['home'])

    def test_odds_missing_prices_and_no_data(self):
        for bad in (None,0,1,float('inf'),True):
            x=row();x['odds']['over25']=bad
            e=r.calculate(x,'football',example(),IDENT)
            self.assertNotEqual(e['chosen']['market'],'OU')
        x=row();x['odds']={}
        self.assertIsNone(r.calculate(x,'football',example(),IDENT)['chosen'])
        self.assertIsNone(r.calculate(row(),'football',[],IDENT)['chosen'])
        self.assertIsNone(r.calculate(row(),'football',example(),None)['chosen'])

    def test_basketball_current_line_overtime_and_push(self):
        records=[match('h','n:1',80,80,'2026-11-25',sport='basketball'),match('a','n:2',70,80,'2026-11-25',sport='basketball')]
        records[0].update(homeFinal=90,awayFinal=85)
        x=row('basketball');x['odds']['hOverUnderValue']=175
        e=r.calculate(x,'basketball',records,IDENT)
        self.assertEqual(e['markets']['MS'],[1,0])
        self.assertNotIn('OU',e['markets'])  # home observation is a push, not an under/loss
        x['odds']['hOverUnderValue']=160.5
        e=r.calculate(x,'basketball',records,IDENT)
        self.assertEqual(e['markets']['OU'],[.5,.5])
        self.assertNotIn('BTTS',e['markets'])

    def test_freeze_control_html_and_immutable_same_day(self):
        from new_reports import reports
        from publish_primary import prepare
        from primary_forecast import forecast
        import sys
        sys.path.insert(0,'scripts')
        from primary_control import render
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);root=p/'out';root.mkdir()
            for sport in ('football','basketball'):r.write(root/(sport+'-replay.json'),[row(sport)])
            records=example()+[match('bh','n:1',80,60,'2026-11-25',sport='basketball'),match('ba','n:2',60,80,'2026-11-25',sport='basketball')]
            ids={(sport,DAY,'123'):IDENT for sport in ('football','basketball')}
            b=r.freeze(root,DAY,{'matches':records},ids,datetime(2026,11,26,tzinfo=timezone.utc))
            original=(root/r.FILE).read_bytes()
            manifest=reports(root);prepare(root,DAY)
            doc=(root/'futbol-yeni.html').read_text()
            self.assertIn('Hesap detayı',doc);self.assertIn('(3 + 2) / 8 = %62.50',doc)
            self.assertIn('× 0.9',doc);self.assertIn('× 0.1',doc)
            self.assertNotIn('Skor tahmini',doc);self.assertNotIn('Tam skor olasılığı',doc)
            self.assertIn('Gerçek skor',doc);self.assertIn('grid-column:1/-1!important',doc)
            self.assertIn('data-confidence="0.6125"',doc)
            # Existing snapshot skips history access and inference entirely.
            with patch('primary_forecast.build_ledger',side_effect=AssertionError('No refreeze')):
                forecast(root,root,DAY)
            for sport,folder in [('football','futbol'),('basketball','basketbol')]:
                directory=p/sport/folder/'data';directory.mkdir(parents=True)
                r.write(directory/('RealScores-'+DAY+'.json'),[{'eventId':'123','score':'2-1' if sport=='football' else '90-80'}])
            plan={'targetDate':DAY,'origin':{'policy':r.POLICY,'modelSha256':r.MODEL_HASH,'pricedSnapshotSha256':b['snapshotSha256']}}
            new_manifest,proof=render(root,p/'football',p/'basketball',plan)
            self.assertTrue(proof['immutableForecastsUnchanged'])
            self.assertEqual(original,(root/r.FILE).read_bytes())
            self.assertIn('2-1',(root/'futbol-yeni.html').read_text())
            self.assertEqual(new_manifest['pricedSnapshotSha256'],manifest['pricedSnapshotSha256'])
            report=r.read(root/'user-rules-evaluation.json')
            self.assertEqual(report['sports']['football'][0]['hits'],1)
            r.write(root/'user-rules-identities-before-results.json',[])
            with self.assertRaises(ValueError):r.verify(root)

    def test_new_daily_pipeline_does_not_run_old_model_or_train(self):
        from primary_forecast import forecast
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for sport in ('football','basketball'):r.write(root/(sport+'-replay.json'),[row(sport)])
            ids={(sport,DAY,'123'):IDENT for sport in ('football','basketball')}
            with patch('primary_forecast.build_ledger',return_value=({'matches':example()},ids)), \
                 patch('locked_stability.freeze',side_effect=AssertionError('No old model')), \
                 patch('outcome_learning.learn',side_effect=AssertionError('No training')):
                manifest=forecast(root,root,DAY,enrich=False)
            self.assertEqual(manifest['selectionPolicy'],r.POLICY)
            self.assertFalse((root/'stability-before-results.json').exists())

    def test_dual_choice_results_and_client_javascript(self):
        import html,re,subprocess
        from new_reports import reports
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            x=row();x['realScore']='2-1'
            r.write(root/'football-replay.json',[x]);r.write(root/'basketball-replay.json',[])
            records=[match('h','n:1',2,0,'2026-11-25'),match('a','n:2',0,2,'2026-11-25')]
            r.freeze(root,DAY,{'matches':records},{('football',DAY,'123'):IDENT},datetime(2026,11,26,tzinfo=timezone.utc))
            reports(root);doc=(root/'futbol-yeni.html').read_text()
            counts=json.loads(html.unescape(re.search('data-choices="([^"]+)"',doc)[1]))
            self.assertEqual((counts['won'],counts['lost']),(1,1))
            self.assertEqual(doc.count('market-option chosen'),2)
            self.assertIn('MS1: ✅ Tuttu<br>Alt: ❌ Yattı',doc)
            self.assertIn('MS1 · %100.00<br>Alt · %100.00',doc)
            self.assertIn('data-match-outcome="partial"',doc)
            self.assertIn('1 kısmi tuttu',doc)
            self.assertIn('İsabet (maç) %0.0',doc)
            report=r.read(root/'user-rules-evaluation.json')['sports']['football'][0]
            self.assertEqual((report['count'],report['hits'],report['plannedCount']),(2,1,1))
            script='\n'.join(re.findall(r'<script>(.*?)</script>',doc,re.S))
            checked=subprocess.run(['node','-e','new Function(require("fs").readFileSync(0,"utf8"))'],input=script,text=True,capture_output=True)
            self.assertEqual(checked.returncode,0,checked.stderr)

    def test_match_summary_categories_do_not_double_count_selections(self):
        from new_reports import match_outcome,match_summary,MATCH_SUMMARY_SCRIPT
        import subprocess
        for counts,expected in [({'won':2},'won'),({'won':1,'lost':1},'partial'),({'lost':2},'lost'),
                                 ({'won':1,'pending':1},'pending'),({'lost':1,'unverified':1},'unverified'),({'no-choice':1},'no-choice')]:
            self.assertEqual(match_outcome(counts),expected)
        script="const summary={textContent:''};const document={getElementById:()=>summary};"+MATCH_SUMMARY_SCRIPT+"updateSummary(['won','partial','lost','pending'].map(matchOutcome=>({dataset:{matchOutcome}})));console.log(summary.textContent);"
        value=subprocess.run(['node','-e',script],text=True,capture_output=True,check=True).stdout
        self.assertIn('4 maç · 3 sonuçlandı · 1 tuttu · 1 kısmi tuttu · 1 yattı · 1 bekliyor',value)
        self.assertIn('%33,3',value)


if __name__=='__main__':unittest.main()
