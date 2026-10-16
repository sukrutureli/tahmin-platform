package com.basketbol.util;

import com.basketbol.model.*;
import java.net.URI;
import java.util.*;
import java.util.regex.*;

/** Keep settlement tied to the Nesine fixture, never to a partial team name. */
public final class FixtureIdentity {
    private FixtureIdentity() {}
    private static final Pattern ID = Pattern.compile("^/(?:p1/)?([0-9]+)(?:/.*)?$");

    public static String eventId(String detailUrl) {
        if (detailUrl == null) return null;
        try {
            URI uri = URI.create(detailUrl);
            if (!"istatistik.nesine.com".equalsIgnoreCase(uri.getHost())) return null;
            Matcher matcher = ID.matcher(uri.getPath());
            return matcher.matches() ? matcher.group(1) : null;
        } catch (IllegalArgumentException ex) { return null; }
    }

    private static String name(String home, String away) {
        return home == null || away == null ? null : home.trim() + " - " + away.trim();
    }

    /** Old JSON has no eventId. Only a single exact full-name fixture can supply it. */
    public static String uniqueId(String name, List<MatchInfo> matches) {
        if (name == null || matches == null) return null;
        MatchInfo found = null;
        for (MatchInfo match : matches) {
            if (match != null && match.getName() != null && name.trim().equals(match.getName().trim())) {
                if (found != null) return null;
                found = match;
            }
        }
        return found == null ? null : eventId(found.getDetailUrl());
    }

    private static int historyIndex(MatchInfo match, List<TeamMatchHistory> histories) {
        String id = match == null ? null : eventId(match.getDetailUrl());
        if (id == null || histories == null) return -1;
        int found = -1;
        for (int i = 0; i < histories.size(); i++) {
            TeamMatchHistory h = histories.get(i);
            if (h != null && id.equals(eventId(h.getDetailUrl()))) {
                if (found >= 0) return -1;
                found = i;
            }
        }
        return found;
    }

    public static TeamMatchHistory historyFor(MatchInfo match, List<TeamMatchHistory> histories) {
        int i = historyIndex(match, histories);
        return i < 0 ? null : histories.get(i);
    }

    /** Results follow successfully created histories, not the unfiltered fixture list. */
    public static PredictionResult resultFor(MatchInfo match, List<TeamMatchHistory> histories,
            List<PredictionResult> results) {
        int i = historyIndex(match, histories);
        if (i < 0 || results == null || results.size() != histories.size()) return null;
        TeamMatchHistory h = histories.get(i);
        PredictionResult p = results.get(i);
        // Refuse stale/misaligned saved arrays; provider names may differ from fixture labels.
        return p != null && h.getTeamEv() != null && h.getTeamDep() != null
                && h.getTeamEv().equals(p.getHomeTeam()) && h.getTeamDep().equals(p.getAwayTeam()) ? p : null;
    }

    public static void bindPredictions(List<PredictionData> data, List<MatchInfo> matches) {
        if (data == null) return;
        for (PredictionData p : data) {
            if (p.getEventId() == null || p.getEventId().isBlank()) {
                p.setEventId(uniqueId(name(p.getHomeTeam(), p.getAwayTeam()), matches));
                if (p.getEventId() == null) {
                    // Do not preserve a legacy score/status whose fixture cannot be established.
                    p.setScore("-");
                    if (p.getStatuses() != null) p.getStatuses().replaceAll((pick, status) -> "pending");
                }
            }
        }
    }

    public static void bindCoupons(List<LastPrediction> data, List<MatchInfo> matches) {
        if (data == null) return;
        for (LastPrediction p : data)
            if (p.getEventId() == null || p.getEventId().isBlank())
                p.setEventId(uniqueId(p.getName(), matches));
    }

    public static void bindScores(List<RealScores> data, List<MatchInfo> matches) {
        if (data == null) return;
        for (RealScores r : data)
            if (r.getEventId() == null || r.getEventId().isBlank())
                r.setEventId(uniqueId(name(r.getHomeTeam(), r.getAwayTeam()), matches));
    }

    public static PredictionData predictionFor(List<PredictionData> data, LastPrediction coupon) {
        if (data == null || coupon == null || coupon.getEventId() == null) return null;
        PredictionData found = null;
        for (PredictionData p : data) {
            if (coupon.getEventId().equals(p.getEventId())) {
                if (found != null) return null;
                found = p;
            }
        }
        return found;
    }

    public static String realScore(List<RealScores> data, MatchInfo match) {
        String id = match == null ? null : eventId(match.getDetailUrl());
        if (data == null || id == null) return " (⏳)";
        RealScores found = null;
        for (RealScores r : data) {
            if (id.equals(r.getEventId())) {
                if (found != null) return " (⏳)";
                found = r;
            }
        }
        return found == null ? " (⏳)" : " (" + found.getScore() + ")";
    }

    public static void recordScore(Map<String, String> scores, List<RealScores> results,
            MatchInfo match, String score) {
        String id = eventId(match.getDetailUrl());
        if (id == null) return;
        scores.put(id, score);
        results.removeIf(r -> id.equals(r.getEventId()));
        String[] teams = match.getName().split(" - ", 2);
        if (teams.length != 2) return;
        RealScores r = new RealScores();
        r.setEventId(id);
        r.setHomeTeam(teams[0].trim());
        r.setAwayTeam(teams[1].trim());
        r.setScore(score);
        results.add(r);
    }
}

