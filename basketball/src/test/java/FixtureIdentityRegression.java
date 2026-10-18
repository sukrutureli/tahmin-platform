import com.basketbol.model.*;
import com.basketbol.util.FixtureIdentity;
import java.util.*;

public final class FixtureIdentityRegression {
    private static void check(boolean valid, String label) {
        if (!valid) throw new AssertionError(label);
    }
    private static MatchInfo match(String name, String id) {
        return new MatchInfo(name, "20:00", "https://istatistik.nesine.com/" + id + "/ozet", null, 0);
    }
    private static PredictionData prediction(String home, String away, String id) {
        PredictionData p = new PredictionData(home, away, new ArrayList<>(List.of("MS1")));
        p.setEventId(id); p.getStatuses().put("MS1", "pending"); return p;
    }
    public static void main(String[] args) throws Exception {
        check("123".equals(FixtureIdentity.eventId("https://istatistik.nesine.com/p1/123/ozet?x=1")), "p1 id");
        check("123".equals(FixtureIdentity.eventId("https://istatistik.nesine.com/123")), "normal id");
        check(FixtureIdentity.eventId("https://other.com/123/ozet") == null, "wrong host");
        check(FixtureIdentity.eventId("broken url") == null, "invalid URL");
        MatchInfo senior = match("United - City", "101");
        MatchInfo youth = match("United - City", "102");
        List<MatchInfo> matches = List.of(senior, youth);
        Map<String,String> scores = new HashMap<>();
        List<RealScores> results = new ArrayList<>();
        FixtureIdentity.recordScore(scores, results, senior, "2-0");
        FixtureIdentity.recordScore(scores, results, youth, "0-3");
        check(scores.size() == 2 && results.size() == 2, "identical names remain separate");
        check(" (2-0)".equals(FixtureIdentity.realScore(results, senior)), "senior display");
        check(" (0-3)".equals(FixtureIdentity.realScore(results, youth)), "youth display");
        FixtureIdentity.recordScore(scores, results, senior, "3-0");
        check(results.size() == 2 && " (0-3)".equals(FixtureIdentity.realScore(results, youth)), "id-specific upsert");

        PredictionData legacy = prediction("United", "City", null);
        legacy.setScore("9-0"); legacy.getStatuses().put("MS1","won");
        FixtureIdentity.bindPredictions(List.of(legacy), matches);
        check(legacy.getEventId() == null && "-".equals(legacy.getScore())
            && "pending".equals(legacy.getStatuses().get("MS1")), "ambiguous legacy stays pending");
        FixtureIdentity.bindPredictions(List.of(legacy), List.of(senior));
        check("101".equals(legacy.getEventId()), "unique exact legacy migration");
        PredictionData partial = prediction("United", "Other", null);
        FixtureIdentity.bindPredictions(List.of(partial), List.of(senior));
        check(partial.getEventId() == null, "one-team match rejected");
        PredictionData suffixed = prediction("United (U21)", "City (U21)", null);
        FixtureIdentity.bindPredictions(List.of(suffixed), List.of(senior));
        check(suffixed.getEventId() == null, "U21 suffix never stripped");
        PredictionData missing = prediction("United", "City", "999");
        FixtureIdentity.bindPredictions(List.of(missing), List.of(senior));
        check("999".equals(missing.getEventId()) && !scores.containsKey(missing.getEventId()), "known id never falls back to name");
        PredictionData p1 = prediction("United", "City", "101");
        PredictionData p2 = prediction("United", "City", "102");
        LastPrediction coupon = new LastPrediction("United - City", "20:00");
        coupon.setEventId("102");
        check(FixtureIdentity.predictionFor(List.of(p2,p1),coupon) == p2, "coupon order independent");
        coupon.setEventId(null);
        FixtureIdentity.bindCoupons(List.of(coupon), matches);
        check(FixtureIdentity.predictionFor(List.of(p1,p2),coupon) == null, "ambiguous coupon no guess");
        RealScores old = new RealScores();
        old.setHomeTeam("United");old.setAwayTeam("City");old.setScore("4-0");
        FixtureIdentity.bindScores(List.of(old), matches);
        check(" (⏳)".equals(FixtureIdentity.realScore(List.of(old), youth)), "ambiguous legacy result ignored");
        FixtureIdentity.bindScores(List.of(old), List.of(senior));
        check(" (4-0)".equals(FixtureIdentity.realScore(List.of(old), senior)), "old result unique migration");
        reportGaps();
        if (args.length > 0) integration(matches);
        System.out.println("Fixture identity regression passed: basketball");
    }

    private static void reportGaps() throws Exception {
        List<MatchInfo> fixtures = new ArrayList<>();
        com.basketbol.MatchHistoryManager manager = new com.basketbol.MatchHistoryManager();
        List<PredictionResult> forecasts = new ArrayList<>();
        for (int i = 0; i < 56; i++) {
            Odds odds = new Odds(1.5, 2.0, -5.5, 1.5, 1.5, 5.5, 1.5, 200.5, 1.5);
            odds.setMbs(i % 3 + 1);
            MatchInfo fixture = new MatchInfo("Home " + i + " - Away " + i, "20:00",
                    "https://istatistik.nesine.com/" + (5000+i) + "/ozet", odds, i);
            fixtures.add(fixture);
            if (i == 17) continue; // Failed history in the middle, not only a missing final item.
            String home = "Provider home " + i, away = "Provider away " + i;
            TeamMatchHistory h = new TeamMatchHistory(fixture.getName(), home, away, fixture.getDetailUrl(), odds);
            for (int j = 0; j < 2; j++) {
                h.addSonMacMatch(new MatchResult(home, "Opponent", 90, 70, "2026-10-01", "League", "son-maclar"), 1);
                h.addSonMacMatch(new MatchResult(away, "Opponent", 70, 90, "2026-10-01", "League", "son-maclar"), 2);
            }
            manager.addTeamHistory(h);
            forecasts.add(new PredictionResult("regression", home, away, .9, 0, .1, .2, 0,
                    "MS1", .9, (90+i) + "-70"));
        }
        check(FixtureIdentity.historyFor(fixtures.get(17), manager.getTeamHistories()) == null, "missing history stays missing");
        check(FixtureIdentity.resultFor(fixtures.get(55), manager.getTeamHistories(), forecasts) == forecasts.get(54), "last forecast survives compact list");
        check(FixtureIdentity.resultFor(fixtures.get(18), manager.getTeamHistories(), forecasts) == forecasts.get(17), "gap does not shift forecast");
        check(FixtureIdentity.resultFor(fixtures.get(18), manager.getTeamHistories(), forecasts.subList(0,54)) == null, "unequal saved arrays not guessed");
        List<PredictionResult> swapped = new ArrayList<>(forecasts);
        Collections.swap(swapped, 17, 18);
        check(FixtureIdentity.resultFor(fixtures.get(18), manager.getTeamHistories(), swapped) == null, "wrong team pair rejected");
        List<TeamMatchHistory> duplicates = new ArrayList<>(manager.getTeamHistories());
        duplicates.add(duplicates.get(17));
        check(FixtureIdentity.historyFor(fixtures.get(18), duplicates) == null, "duplicate fixture histories rejected");
        MatchInfo noUrl = new MatchInfo("No detail available", "20:00", null, fixtures.get(0).getOdds(), 56);
        fixtures.add(0, noUrl);
        // Match labels can coincide; fixture IDs, rather than labels or positions, must decide.
        fixtures.get(20).setName(fixtures.get(19).getName());
        com.basketbol.LastPredictionManager coupons = new com.basketbol.LastPredictionManager(manager, forecasts, fixtures);
        coupons.fillPredictions();
        check(coupons.getLastPrediction().size() == 55, "coupons contain only successful histories");
        check(coupons.getLastPrediction().stream().noneMatch(c -> "5017".equals(c.getEventId())), "failed fixture gets no borrowed coupon");
        LastPrediction after = coupons.getLastPrediction().stream().filter(c -> "5018".equals(c.getEventId())).findFirst().orElseThrow();
        check("108-70".equals(after.getScore()), "coupon after gap has own score");
        String outputName = "fixture-gap-regression.html";
        java.nio.file.Path output = java.nio.file.Path.of("public/basketbol", outputName);
        try {
            com.basketbol.html.CombinedHtmlReportGenerator.generateCombinedHtml(coupons.getLastPrediction(), fixtures,
                    manager, List.of(), forecasts, coupons.getPredictionData(), outputName, "2026-10-16", null);
            String report = java.nio.file.Files.readString(output);
            String[] cards = report.split("<div class='match(?: insufficient)?'>");
            check(cards.length-1 == 57, "all fixtures rendered including unavailable history and URL");
            check(cards[1].contains("Bu maç için geçmiş veri bulunamadı"), "no-URL card rendered");
            check(cards[19].contains("Bu maç için geçmiş veri bulunamadı"), "missing middle card rendered without forecast");
            check(cards[20].contains("108-70"), "report after gap has own score");
            check(cards[20].contains("MBS: 1"), "report MBS follows fixture odds");
            check(cards[57].contains("MBS: 2"), "last fixture MBS preserved");
            check(report.contains("class='coupon-mbs'>MBS: 1</span>"), "coupon table includes MBS");
            check(cards[57].contains("145-70"), "last fixture rendered correctly");
            // Same saved histories are valid for a control render even when MatchInfo order changes.
            Collections.reverse(fixtures);
            com.basketbol.LastPredictionManager control = new com.basketbol.LastPredictionManager(manager, forecasts, fixtures);
            control.fillPredictions();
            check(control.getLastPrediction().get(0).getEventId().equals("5055"), "control restored by fixture ID");
            check(control.getLastPrediction().get(0).getScore().equals("145-70"), "control score order independent");
        } finally { java.nio.file.Files.deleteIfExists(output); }
    }

    private static void integration(List<MatchInfo> matches) throws Exception {
        // Use reflection so the same regression can run locally without Maven dependencies.
        Class<?> updater = Class.forName("com.basketbol.prediction.PredictionUpdater");
        var update = updater.getMethod("update", List.class, Map.class, List.class, String.class, String.class);
        PredictionData home = prediction("United","City","101");
        PredictionData away = prediction("United","City","102");
        PredictionData live = prediction("United","City","103");
        update.invoke(null, List.of(home, away, live),
            Map.of("101","2-0","102","0-3","United - City","9-0"), matches, "regression-", "fixture");
        check("won".equals(home.getStatuses().get("MS1")), "correct home settlement");
        check("lost".equals(away.getStatuses().get("MS1")), "correct away settlement");
        check("pending".equals(live.getStatuses().get("MS1")) && "-".equals(live.getScore()), "live not settled via names");
        Class<?> mapperType = Class.forName("com.fasterxml.jackson.databind.ObjectMapper");
        Object mapper = mapperType.getConstructor().newInstance();
        String json = (String) mapperType.getMethod("writeValueAsString",Object.class).invoke(mapper, home);
        PredictionData roundtrip = (PredictionData) mapperType.getMethod("readValue",String.class,Class.class)
            .invoke(mapper,json,PredictionData.class);
        check("101".equals(roundtrip.getEventId()), "eventId JSON roundtrip");
        PredictionData old = (PredictionData) mapperType.getMethod("readValue",String.class,Class.class)
            .invoke(mapper,"{\"homeTeam\":\"Legacy\",\"awayTeam\":\"Opponent\",\"picks\":[]}",PredictionData.class);
        check(old.getEventId() == null, "old JSON readable");

        var parseMbs = com.basketbol.scraper.BasketballScraper.class.getDeclaredMethod("parseMbs", Object.class);
        parseMbs.setAccessible(true);
        check(Integer.valueOf(3).equals(parseMbs.invoke(null, 3)), "numeric MBS preserved");
        check(Integer.valueOf(2).equals(parseMbs.invoke(null, "2")), "string MBS preserved");
        for (Object invalid : new Object[] { null, "", "-", 0, -1, 1.5, Double.NaN, Double.POSITIVE_INFINITY, true }) {
            check(parseMbs.invoke(null, invalid) == null, "unknown MBS is not invented");
        }
        Odds withMbs = new Odds(1.5, 2.0, -5.5, 1.5, 1.5, 5.5, 1.5, 200.5, 1.5);
        withMbs.setMbs((Integer) parseMbs.invoke(null, "3"));
        MatchInfo fixture = new MatchInfo("Home - Away", "20:00", "https://istatistik.nesine.com/123", withMbs, 0);
        String fixtureJson = (String) mapperType.getMethod("writeValueAsString", Object.class).invoke(mapper, fixture);
        MatchInfo restored = (MatchInfo) mapperType.getMethod("readValue", String.class, Class.class).invoke(mapper, fixtureJson, MatchInfo.class);
        check(Integer.valueOf(3).equals(restored.getMbs()), "MatchInfo MBS JSON roundtrip");
        check(Integer.valueOf(3).equals(restored.getOdds().getMbs()), "Odds MBS JSON roundtrip");
        check(Double.valueOf(200.5).equals(restored.getOdds().gethOverUnderValue()), "MBS does not shift total line");
        MatchInfo oldFixture = (MatchInfo) mapperType.getMethod("readValue", String.class, Class.class)
                .invoke(mapper, "{\"name\":\"Legacy\",\"odds\":{\"ms1\":1.5,\"ms2\":2.0}}", MatchInfo.class);
        check(oldFixture.getMbs() == null && oldFixture.getOdds().getMbs() == null, "old MBS-free JSON readable");

    }
}

