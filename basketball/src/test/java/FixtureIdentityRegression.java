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
        if (args.length > 0) integration(matches);
        System.out.println("Fixture identity regression passed: basketball");
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
    }
}
