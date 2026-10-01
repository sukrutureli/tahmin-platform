import copy
import unittest
from datetime import date

import compare as model


class ExperimentTests(unittest.TestCase):
    cutoff = date(2026, 10, 1)

    def row(self, **overrides):
        row = {"id":"one","date":"2026-09-20","venue":"home","for":90,"against":80,
               "finalFor":90,"finalAgainst":80,"win":1,"draw":0,"tournament":"LNB",
               "tournamentId":1,"opponent":"Other","source":"test"}
        row.update(overrides)
        return row

    def schedule(self, **overrides):
        row={"id":10,"date":"09/20/2026 12:00:00","teamType":"away",
             "team":{"name":"Opponent"},"tournament":{"id":1,"name":"League"},
             "status":{"id":9},"scores":{"home":{"ordinary":80,"current":91},
                                            "away":{"ordinary":80,"current":88}}}
        row.update(overrides)
        return row

    def test_overtime_win_uses_final_regulation_stats_remain_tied(self):
        parsed=model.schedule_row(self.schedule(),self.cutoff,"basketball")
        self.assertEqual((parsed["venue"],parsed["for"],parsed["against"],parsed["win"]),("home",80,80,1))
        self.assertEqual(parsed["finalFor"],91)

    def test_overtime_without_regulation_is_excluded(self):
        row=self.schedule(scores={"home":{"current":91},"away":{"current":88}})
        self.assertIsNone(model.schedule_row(row,self.cutoff,"basketball"))

    def test_unfinished_future_and_same_day_excluded(self):
        for row in (self.schedule(status={"id":2}),self.schedule(date="10/02/2026 12:00:00"),self.schedule(date="10/01/2026 00:01:00")):
            self.assertIsNone(model.schedule_row(row,self.cutoff,"basketball"))

    def test_opponent_orientation(self):
        row=model.schedule_row(self.schedule(teamType="home"),self.cutoff,"basketball")
        self.assertEqual((row["venue"],row["for"],row["finalFor"],row["win"]),("away",80,88,0))

    def test_archived_tie_not_loss(self):
        rows=model.archived_rows([{"homeTeam":"A","awayTeam":"B","homeScore":80,"awayScore":80,"matchDate":"20 Eylül 2026"}],"A",self.cutoff,"basketball")
        self.assertIsNone(rows[0]["win"])
        st=model.stats(rows,self.cutoff,"basketball","home")
        self.assertEqual(st["unknownFinalCount"],1)
        self.assertEqual(st["form"],0.5)

    def test_no_duplicate_inflation(self):
        st=model.stats([self.row(),self.row()],self.cutoff,"basketball","home")
        self.assertEqual(st["count"],1)
        self.assertAlmostEqual(st["effectiveCount"],1)

    def test_stale_and_friendly_downweighted(self):
        recent=self.row()
        stale=self.row(date="2025-01-01")
        friendly=self.row(tournament="Kulüp Hazırlık Maçları")
        self.assertLess(model.weight(stale,self.cutoff,"basketball"),model.weight(recent,self.cutoff,"basketball"))
        self.assertAlmostEqual(model.weight(friendly,self.cutoff,"basketball")/model.weight(recent,self.cutoff,"basketball"),0.25)

    def test_sample_reliability_not_saturated_at_five(self):
        rows=[self.row(id=str(i),date=f"2026-09-{29-i:02}") for i in range(20)]
        five=model.stats(rows[:5],self.cutoff,"basketball","home")
        twenty=model.stats(rows,self.cutoff,"basketball","home")
        self.assertGreater(twenty["quality"],five["quality"])

    def test_venue_sample_balanced_and_shrunk(self):
        rows=[self.row(id=str(i),venue="away",date=f"2026-09-{29-i:02}") for i in range(20)]
        rows += [self.row(id="home"+str(i),date=f"2026-08-{25-i:02}") for i in range(8)]
        selected=model.balanced_sample(rows,20)
        self.assertEqual(len(selected),20)
        self.assertEqual(sum(r["venue"]=="home" for r in selected),4)
        st=model.stats([self.row(**{"for":200,"against":50})],self.cutoff,"basketball","home")
        self.assertGreater(st["for"],80)
        self.assertLess(st["for"],200)

    def test_invalid_odds_and_empty_history_are_finite(self):
        self.assertIsNone(model.devig([0,1.5]))
        h={"teamEv":"A","teamDep":"B","rekabetGecmisi":[]}
        for sport in ("football","basketball"):
            p=model.predict(h,{},[],[],self.cutoff,sport)
            self.assertEqual(p["selections"],[])
            self.assertAlmostEqual(sum(p["probabilities"][k] for k in ("MS1","MS2")+( ("MSX",) if sport=="football" else ())),1)

    def test_markets_selected_independently_without_score_veto(self):
        picked=model.select({"MS1":0.7,"MS2":0.3,"Üst":0.75,"Alt":0.25},
                            {"MS1":1.7,"MS2":2,"Üst":1.6,"Alt":2},80,20,["MS1","MS2"])
        self.assertEqual([r["market"] for r in picked],["MS1","Üst"])
        self.assertEqual(model.select({"MS1":0.7,"MS2":0.3},{"MS1":1.1,"MS2":4},80,20,["MS1","MS2"]),[])

    def test_poisson_probability_mass(self):
        for home,away in ((0.15,0.15),(6,6),(2,1)):
            ms,over,btts=model.poisson_probabilities(home,away)
            self.assertAlmostEqual(sum(ms),1)
            self.assertTrue(all(0<=p<=1 for p in ms+[over,btts]))

    def test_saved_score_outcomes_and_push_exclusion(self):
        row={"sport":"basketball","new":{"line":160}}
        outcomes=model.outcomes({"score":"91-69"},row)
        self.assertEqual(outcomes["MS1"],1)
        self.assertNotIn("Üst",outcomes)

    def test_summary_union_deduplicates_and_preserves_overtime_result(self):
        match={"MID":77,"POFMD":"20 Eylül 2026","HT":{"TID":1,"N":"A"},"AT":{"TID":2,"N":"B"},
               "LG":{"TID":3,"N":"League"},"SC":[{"OBI":45,"HTS":80,"ATS":80},{"OBI":1000,"HTS":91,"ATS":88}]}
        future=copy.deepcopy(match);future.update({"MID":78,"POFMD":"1 Ekim 2026"})
        groups=[{"FT":ft,"TMS":[{"TID":tid,"ML":[match,future]} for tid in (1,2)]} for ft in (5,2)]
        class FakeClient:
            def get(self,url):
                return {"d":{"SID":2,"HT":[{"TID":1}],"AT":[{"TID":2}]}} if url.endswith("Header") else {"d":{"SLM":{"ML":[{"TT":groups}]}}}
        result=model.Collector(FakeClient()).summary_fallback({"detailUrl":"https://istatistik.nesine.com/123"},self.cutoff,"basketball")
        self.assertEqual([len(r["rows"]) for r in result],[1,1])
        self.assertEqual([r["rows"][0]["win"] for r in result],[1,0])
        self.assertEqual(result[0]["rows"][0]["for"],80)


if __name__=="__main__":
    unittest.main()
