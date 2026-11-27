import com.example.model.*;
import com.example.util.FixtureIdentity;
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
    private static void verifyCompetitionHistory() throws Exception {
        com.fasterxml.jackson.databind.ObjectMapper json = new com.fasterxml.jackson.databind.ObjectMapper();
        com.fasterxml.jackson.databind.node.ObjectNode payload = json.createObjectNode();
        com.fasterxml.jackson.databind.node.ObjectNode league = payload.putArray("ML").addObject();
        league.put("TFT", 2);
        com.fasterxml.jackson.databind.node.ObjectNode group = league.putArray("TT").addObject();
        group.put("FT", 5);
        com.fasterxml.jackson.databind.node.ArrayNode teams = group.putArray("TMS");
        // Provider team order is deliberately reversed; bind by Header TID.
        for (int id : new int[] {2, 1}) {
            com.fasterxml.jackson.databind.node.ObjectNode team = teams.addObject(); team.put("TID", id);
            com.fasterxml.jackson.databind.node.ArrayNode matches = team.putArray("ML");
            for (int i = 0; i < 9; i++) {
                com.fasterxml.jackson.databind.node.ObjectNode row = matches.addObject();
                row.put("POFMD", (25-i) + " Kasım 2026");
                row.putObject("HT").put("N", id == 1 ? "Home" : "Away"); row.putObject("AT").put("N", "Other");
                row.putObject("LG").put("TID", i == 0 ? 999 : 709).put("N", i == 0 ? "Cup" : "Premier Lig");
                com.fasterxml.jackson.databind.node.ObjectNode score = row.putArray("SC").addObject();
                score.put("OBI", 99).put("HTS", id == 1 ? 2 : 1).put("ATS", 0);
            }
        }
        TeamMatchHistory history = new TeamMatchHistory(); history.setTargetTournamentId("709");
        com.fasterxml.jackson.databind.JsonNode header = json.readTree("{\"HT\":[{\"TID\":1}],\"AT\":[{\"TID\":2}]}");
        java.lang.reflect.Method method = com.example.scraper.MatchScraper.class.getDeclaredMethod("appendCompetitionHistory", TeamMatchHistory.class,
                com.fasterxml.jackson.databind.JsonNode.class, com.fasterxml.jackson.databind.JsonNode.class, String.class);
        method.setAccessible(true); method.invoke(new com.example.scraper.MatchScraper(), history, payload, header, "test");
        check("available".equals(history.getCompetitionHistoryStatus()), "dedicated tournament source available");
        check(history.getCompetitionMatchesHome().size() == 6 && history.getCompetitionMatchesAway().size() == 6, "six per side after excluding other tournament");
        check("Home".equals(history.getCompetitionMatchesHome().get(0).getHomeTeam()), "home bound by provider ID");
        check("Away".equals(history.getCompetitionMatchesAway().get(0).getHomeTeam()), "away bound by provider ID");
        check(history.getSonMaclarHome() == null, "general source unchanged");
    }

    public static void main(String[] args) throws Exception {
        verifyCompetitionHistory();
        TeamMatchHistory metadata = new TeamMatchHistory();
        metadata.setTargetTournamentId("709"); metadata.setTargetTournamentName("Premier Lig");
        com.fasterxml.jackson.databind.ObjectMapper metadataJson = new com.fasterxml.jackson.databind.ObjectMapper();
        // Getters unrelated to metadata need populated lists in legacy beans; deserialize the focused projection.
        TeamMatchHistory restored = metadataJson.readValue("{\"targetTournamentId\":\"709\",\"targetTournamentName\":\"Premier Lig\"}", TeamMatchHistory.class);
        check("709".equals(restored.getTargetTournamentId()) && "Premier Lig".equals(restored.getTargetTournamentName()), "fixture tournament metadata survives JSON input");

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
        if (args.length > 0) integration(matches);
        System.out.println("Fixture identity regression passed: football");
    }

    private static void integration(List<MatchInfo> matches) throws Exception {
        // Use reflection so the same regression can run locally without Maven dependencies.
        Class<?> updater = Class.forName("com.example.prediction.PredictionUpdater");
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
    }
}
