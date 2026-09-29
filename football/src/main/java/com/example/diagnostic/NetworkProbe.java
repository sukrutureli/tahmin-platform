package com.example.diagnostic;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import org.openqa.selenium.By;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.logging.LogEntry;
import org.openqa.selenium.logging.LogType;
import org.openqa.selenium.logging.LoggingPreferences;
import org.openqa.selenium.support.ui.WebDriverWait;

/**
 * One-match, read-only network probe. No request/response headers, cookies,
 * query values, or response bodies are printed to the Actions log.
 */
public final class NetworkProbe {
    private static final String MATCH_URL = "https://istatistik.nesine.com/3166383/ozet";
    private static final ObjectMapper JSON = new ObjectMapper();

    private NetworkProbe() {}

    public static void main(String[] args) throws Exception {
        LoggingPreferences logging = new LoggingPreferences();
        logging.enable(LogType.PERFORMANCE, Level.ALL);
        ChromeOptions options = new ChromeOptions();
        options.addArguments("--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-gpu", "--window-size=1920,1080");
        options.setCapability("goog:loggingPrefs", logging);

        System.setProperty("webdriver.chrome.driver", "/usr/bin/chromedriver");
        ChromeDriver driver = new ChromeDriver(options);
        try {
            driver.executeCdpCommand("Network.enable", Map.of());
            driver.get(MATCH_URL);
            new WebDriverWait(driver, Duration.ofSeconds(30))
                    .until(d -> !d.findElements(By.cssSelector("[data-test-id='LastMatchesTable']")).isEmpty());
            System.out.println("Visible last-match rows: "
                    + driver.findElements(By.cssSelector("tr[data-test-id='LastMatchesTable']")).size());

            Map<String, String> methods = new HashMap<>();
            Map<String, JsonNode> responses = new LinkedHashMap<>();
            for (LogEntry entry : driver.manage().logs().get(LogType.PERFORMANCE)) {
                JsonNode event = JSON.readTree(entry.getMessage()).path("message");
                String name = event.path("method").asText();
                JsonNode params = event.path("params");
                String requestId = params.path("requestId").asText();
                if ("Network.requestWillBeSent".equals(name)) {
                    methods.put(requestId, params.path("request").path("method").asText());
                } else if ("Network.responseReceived".equals(name)) {
                    String type = params.path("type").asText();
                    if ("XHR".equals(type) || "Fetch".equals(type)) {
                        responses.put(requestId, params.path("response"));
                    }
                }
            }

            System.out.println("XHR/Fetch responses: " + responses.size());
            for (Map.Entry<String, JsonNode> item : responses.entrySet()) {
                JsonNode response = item.getValue();
                String requestId = item.getKey();
                String url = response.path("url").asText();
                System.out.println("REQUEST " + methods.getOrDefault(requestId, "?") + " "
                        + response.path("status").asInt() + " " + safeUrl(url));
                try {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> body = driver.executeCdpCommand(
                            "Network.getResponseBody", Map.of("requestId", requestId));
                    String value = String.valueOf(body.get("body"));
                    JsonNode parsed = JSON.readTree(value);
                    if (parsed.isObject()) {
                        List<String> keys = new ArrayList<>();
                        parsed.fieldNames().forEachRemaining(keys::add);
                        System.out.println("JSON top-level keys: " + keys);
                        if (url.startsWith("https://apistats.nesine.com/")) {
                            describe(parsed.path("d"), "d", 0);
                        }
                    } else if (parsed.isArray()) {
                        System.out.println("JSON array length: " + parsed.size());
                    }
                } catch (Exception ignored) {
                    // A missing or non-JSON body does not affect URL discovery.
                }
            }
        } finally {
            driver.quit();
        }
    }

    private static void describe(JsonNode node, String path, int depth) {
        if (depth > 4 || node.isMissingNode() || node.isNull()) return;
        if (node.isObject()) {
            List<String> keys = new ArrayList<>();
            node.fieldNames().forEachRemaining(keys::add);
            System.out.println("SHAPE " + path + " object keys=" + keys);
            for (String key : keys) describe(node.path(key), path + "." + key, depth + 1);
        } else if (node.isArray()) {
            System.out.println("SHAPE " + path + " array length=" + node.size());
            if (!node.isEmpty()) describe(node.get(0), path + "[0]", depth + 1);
        } else {
            System.out.println("SHAPE " + path + " " + node.getNodeType());
        }
    }

    private static String safeUrl(String raw) {
        try {
            URI uri = URI.create(raw);
            StringBuilder out = new StringBuilder(uri.getScheme() + "://" + uri.getHost());
            out.append(uri.getRawPath());
            String query = uri.getRawQuery();
            if (query != null && !query.isEmpty()) {
                List<String> names = new ArrayList<>();
                for (String pair : query.split("&")) {
                    names.add(pair.split("=", 2)[0]);
                }
                out.append(" ?keys=").append(names);
            }
            return out.toString();
        } catch (Exception e) {
            return "<unparseable URL>";
        }
    }
}
