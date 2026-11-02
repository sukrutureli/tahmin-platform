package com.basketbol.scraper;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.basketbol.model.MatchInfo;
import com.basketbol.model.RealScores;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public final class ResultApiSmoke {
    private static final ObjectMapper JSON = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    private static void expect(String expected, String raw, int sport) throws Exception {
        String actual = ResultApiClient.parseFinishedScore(JSON.readTree(raw), sport);
        if (!Objects.equals(expected, actual)) throw new AssertionError("Expected " + expected + ", got " + actual);
    }

    public static void main(String[] args) throws Exception {
        int sport = 2;
        String body = "\"homeTeam\":{\"score\":{\"ordinary\":78,\"current\":91}},"
                + "\"awayTeam\":{\"score\":{\"ordinary\":78,\"current\":82}}";
        expect(sport == 1 ? "78-78" : "91-82", "{\"status\":{\"id\":9}," + body + "}", sport);
        expect("0-1", "{\"status\":{\"id\":5},\"homeTeam\":{\"score\":{\"ordinary\":0,\"current\":0}},"
                + "\"awayTeam\":{\"score\":{\"ordinary\":1,\"current\":1}}}", sport);
        for (int state : new int[] {1,2,3,4,6,7,8,10,12,13,14,15,21,22,23,24,31,32,33,71,72,999}) {
            expect(null, "{\"status\":{\"id\":" + state + "}," + body + "}", sport);
        }
        try {
            ResultApiClient.parseFinishedScore(JSON.readTree("{\"status\":{\"id\":5}}"), sport);
            throw new AssertionError("Missing final scores accepted");
        } catch (java.io.IOException expected) { }
        MatchInfo[] matches = JSON.readValue(Path.of(args[0]).toFile(), MatchInfo[].class);
        RealScores[] saved = JSON.readValue(Path.of(args[1]).toFile(), RealScores[].class);
        ControlScraper scraper = new ControlScraper();
        long started = System.nanoTime();
        Map<String,String> actual;
        try {
            actual = scraper.fetchFinishedScoresFromDetails(Collections.emptyList(), Arrays.asList(matches));
        } finally { scraper.close(); }
        int compared = 0;
        List<String> differences = new ArrayList<>();
        for (RealScores score : saved) {
            String name = score.getHomeTeam() + " - " + score.getAwayTeam();
            compared++;
            if (!Objects.equals(score.getScore(), actual.get(name))) {
                differences.add(name + ": Selenium=" + score.getScore() + ", HTTP=" + actual.get(name));
            }
        }
        System.out.println("HTTP control compared=" + compared + ", fetched=" + actual.size()
                + ", mismatches=" + differences.size() + ", seconds=" + (System.nanoTime()-started)/1_000_000_000.0);
        differences.forEach(System.out::println);
        Files.writeString(Path.of("http-control-results.json"), JSON.writerWithDefaultPrettyPrinter().writeValueAsString(actual));
        if (!differences.isEmpty()) throw new AssertionError("HTTP control does not match saved results");
    }
}
