package com.basketbol.scraper;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Small, paced client for Nesine's public match statistics API. */
final class HistoryApiClient {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Pattern MATCH_ID = Pattern.compile("^/(?:p1/)?([0-9]+)(?:/.*)?$");
    private static final long MIN_INTERVAL_MS = 500;
    private static long nextRequestAt;

    private HistoryApiClient() {}

    static String matchId(String detailUrl) {
        try {
            URI uri = URI.create(detailUrl);
            if (!"https".equalsIgnoreCase(uri.getScheme())
                    || !"istatistik.nesine.com".equalsIgnoreCase(uri.getHost())) return null;
            Matcher match = MATCH_ID.matcher(uri.getPath());
            return match.matches() ? match.group(1) : null;
        } catch (IllegalArgumentException ex) {
            return null;
        }
    }

    static JsonNode get(String id, String resource) throws IOException, InterruptedException {
        if (!id.matches("[0-9]+")) throw new IOException("Invalid match id");
        String version = "Fixture".equals(resource) ? "v4" : "v3";
        String path = "Summary".equals(resource) ? "Summary?competitionHistoryCount=10" : resource;
        URI uri = URI.create("https://apistats.nesine.com/api/" + version
                + "/HeadToHead/" + id + "/" + path);

        for (int attempt = 0; attempt < 3; attempt++) {
            pace();
            HttpURLConnection connection = (HttpURLConnection) uri.toURL().openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(15000);
            connection.setRequestProperty("Accept", "application/json");
            try {
                int status = connection.getResponseCode();
                if (status == 200) {
                    try (InputStream input = connection.getInputStream()) {
                        JsonNode root = JSON.readTree(input);
                        JsonNode data = root.path("d");
                        if (root.path("sc").asInt() != 200 || !data.isObject()) {
                            throw new IOException("Invalid " + resource + " response for match " + id);
                        }
                        return data;
                    }
                }
                if ((status == 429 || status == 502 || status == 503 || status == 504) && attempt < 2) {
                    long retryMs = Math.max(1000L << attempt, retryAfterMs(connection.getHeaderField("Retry-After")));
                    Thread.sleep(Math.min(retryMs, 30000));
                    continue;
                }
                throw new IOException("Stats API " + resource + " returned HTTP " + status + " for match " + id);
            } finally {
                connection.disconnect();
            }
        }
        throw new IOException("Stats API unavailable for match " + id);
    }

    private static synchronized void pace() throws InterruptedException {
        long now = System.currentTimeMillis();
        long waitMs = nextRequestAt - now;
        if (waitMs > 0) Thread.sleep(waitMs);
        nextRequestAt = System.currentTimeMillis() + MIN_INTERVAL_MS;
    }

    private static long retryAfterMs(String header) {
        if (header == null) return 0;
        try { return Math.max(0, Long.parseLong(header.trim()) * 1000L); }
        catch (NumberFormatException ignored) { return 0; }
    }
}
