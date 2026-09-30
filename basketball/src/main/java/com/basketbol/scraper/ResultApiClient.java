package com.basketbol.scraper;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Reads the same Broadage match-header resource used by Nesine's p1 scoreboard. */
public final class ResultApiClient {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Pattern MATCH_ID = Pattern.compile("model\\.MatchId\\s*=\\s*([0-9]+)");
    private static final Pattern SPORT_ID = Pattern.compile("model\\.SportId\\s*=\\s*([0-9]+)");
    private static final Pattern ACCOUNT_ID = Pattern.compile("model\\.AccountId\\s*=\\s*[\"']([a-fA-F0-9-]+)[\"']");
    private static long nextRequestAt;
    private static long blockedUntil;
    private final Map<String, String> accountHosts = new HashMap<>();

    public String finishedScore(String detailUrl, int sportId) throws IOException, InterruptedException {
        String code = HistoryApiClient.matchId(detailUrl);
        if (code == null) throw new IOException("Invalid Nesine detail URL");
        String html = request(URI.create("https://istatistik.nesine.com/p1/" + code), null);
        String matchId = extract(MATCH_ID, html, "match id");
        if (!Integer.toString(sportId).equals(extract(SPORT_ID, html, "sport id"))) {
            throw new IOException("Unexpected scoreboard sport");
        }
        String account = extract(ACCOUNT_ID, html, "account id");
        String host = accountHosts.get(account);
        if (host == null) {
            JsonNode config = JSON.readTree(request(
                    URI.create("https://cdn-saas.broadage.com/config/config.json"), null));
            String prefix = config.path("accountMap").path(account.toUpperCase(Locale.ROOT)).asText("");
            if (!prefix.matches("[0-9]+")) throw new IOException("Scoreboard account host missing");
            host = prefix + ".rsc.cdn77.org";
            accountHosts.put(account, host);
        }
        String sport = sportId == 1 ? "soccer" : sportId == 2 ? "basketball" : null;
        if (sport == null) throw new IOException("Unsupported scoreboard sport");
        String options = URLEncoder.encode("{\"lang\":\"tr-TR\",\"timeZone\":3}", StandardCharsets.UTF_8);
        JsonNode root = JSON.readTree(request(URI.create("https://" + host + "/" + sport
                + "/widget/match/header?mId=" + matchId + "&options=" + options), account));
        JsonNode match = root.path("data").path("initialData");
        if (root.path("status").asInt(-1) != 1 || !match.isObject()
                || !matchId.equals(match.path("id").asText())) {
            throw new IOException("Invalid scoreboard response for " + code);
        }
        return parseFinishedScore(match, sportId);
    }

    static String parseFinishedScore(JsonNode match, int sportId) throws IOException {
        JsonNode state = match.path("status").path("id");
        if (!state.isIntegralNumber()) throw new IOException("Scoreboard status missing");
        int status = state.asInt();
        // Exclude live, scheduled, suspended, cancelled and postponed matches.
        if (status != 5 && status != 9 && status != 11) return null;
        if (sportId != 1 && sportId != 2) throw new IOException("Unsupported scoreboard sport");
        if (sportId == 2 && status == 11) throw new IOException("Invalid basketball penalty status");
        // Football markets use 90 minutes; basketball settlement includes completed overtime.
        String field = sportId == 1 ? "ordinary" : "current";
        JsonNode home = match.path("homeTeam").path("score").path(field);
        JsonNode away = match.path("awayTeam").path("score").path(field);
        if (!home.isIntegralNumber() || !away.isIntegralNumber()
                || !home.canConvertToInt() || !away.canConvertToInt()
                || home.asInt() < 0 || away.asInt() < 0) {
            throw new IOException("Finished scoreboard has no valid " + field + " score");
        }
        if (sportId == 2 && home.asInt() == away.asInt()) {
            throw new IOException("Basketball final score is tied; settlement is unavailable");
        }
        return home.asInt() + "-" + away.asInt();
    }

    private static String extract(Pattern pattern, String text, String label) throws IOException {
        Matcher matcher = pattern.matcher(text);
        if (!matcher.find()) throw new IOException("p1 scoreboard " + label + " missing");
        return matcher.group(1);
    }

    private static String request(URI uri, String account) throws IOException, InterruptedException {
        if (System.currentTimeMillis() < blockedUntil) {
            throw new HistoryApiClient.RateLimitException("Scoreboard API cooldown in effect");
        }
        for (int attempt = 0; attempt < 3; attempt++) {
            pace();
            HttpURLConnection connection = (HttpURLConnection) uri.toURL().openConnection();
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(15000);
            connection.setRequestProperty("Accept", account == null ? "*/*" : "application/json");
            connection.setRequestProperty("User-Agent", "Mozilla/5.0");
            connection.setRequestProperty("Referer", "https://istatistik.nesine.com/");
            if (account != null) {
                connection.setRequestProperty("x-brdg", account);
                connection.setRequestProperty("Origin", "https://istatistik.nesine.com");
            }
            try {
                int status = connection.getResponseCode();
                if (status == 200) {
                    try (InputStream input = connection.getInputStream()) {
                        return new String(input.readAllBytes(), StandardCharsets.UTF_8);
                    }
                }
                if (status == 429) {
                    long delay = Math.max(1000L << attempt, retryAfter(connection.getHeaderField("Retry-After")));
                    if (attempt < 2 && delay <= 30000) {
                        Thread.sleep(delay);
                        continue;
                    }
                    blockedUntil = System.currentTimeMillis() + Math.max(120000, delay);
                    throw new HistoryApiClient.RateLimitException("Scoreboard rate limit reached; stopping control");
                }
                if (status >= 500 && attempt < 2) {
                    Thread.sleep(1000L << attempt);
                    continue;
                }
                throw new IOException("Scoreboard returned HTTP " + status + " from " + uri.getHost());
            } catch (java.net.SocketTimeoutException | java.net.ConnectException ex) {
                if (attempt == 2) throw ex;
                Thread.sleep(1000L << attempt);
            } finally {
                connection.disconnect();
            }
        }
        throw new IOException("Scoreboard request failed");
    }

    private static synchronized void pace() throws InterruptedException {
        long delay = nextRequestAt - System.currentTimeMillis();
        if (delay > 0) Thread.sleep(delay);
        nextRequestAt = System.currentTimeMillis() + 500;
    }

    private static long retryAfter(String header) {
        if (header == null) return 0;
        try { return Math.max(0, Long.parseLong(header.trim()) * 1000L); }
        catch (NumberFormatException ex) {
            try {
                Instant time = ZonedDateTime.parse(header, DateTimeFormatter.RFC_1123_DATE_TIME).toInstant();
                return Math.max(0, Duration.between(Instant.now(), time).toMillis());
            } catch (Exception ignored) { return 0; }
        }
    }
}
