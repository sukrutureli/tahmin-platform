package com.example.scraper;

import com.example.PageWaitUtils;
import com.example.model.MatchInfo;
import com.example.model.MatchResult;
import com.example.model.Odds;
import com.example.model.TeamMatchHistory;
import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class MatchScraper {

    private WebDriver driver;
    private JavascriptExecutor js;
    private WebDriverWait wait;

    private static final String DAILY_JSON_URL =
        "https://sukrutureli.github.io/Scraper/output/latest.json";

    public MatchScraper() {
        // HTTP prediction flow does not initialize a browser.
    }

    // =============================================================
    // WEBDRIVER AYARI
    // =============================================================
    private void setupDriver() {
        ChromeOptions options = new ChromeOptions();
        options.addArguments(
                "--headless=new",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1920,1080",
                "--disable-blink-features=AutomationControlled",
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"
        );

        ChromeDriver chromeDriver = new ChromeDriver(options);
        driver = chromeDriver;
        js = (JavascriptExecutor) driver;
        wait = new WebDriverWait(driver, Duration.ofSeconds(20));
    }

    public List<MatchInfo> fetchMatches() {
    List<MatchInfo> list = new ArrayList<>();

    try {
        System.out.println("🔗 JSON açılıyor: " + DAILY_JSON_URL);

        HttpURLConnection conn = (HttpURLConnection) new URL(DAILY_JSON_URL).openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(30000);
        conn.setRequestProperty("Accept", "application/json");
        conn.setRequestProperty("User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36");

        int status = conn.getResponseCode();
        if (status != 200) {
            throw new RuntimeException("latest.json alınamadı. HTTP=" + status);
        }

        ObjectMapper mapper = new ObjectMapper();
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

        List<Map<String, Object>> rows;
        try (InputStream is = conn.getInputStream()) {
            rows = mapper.readValue(is, new TypeReference<List<Map<String, Object>>>() {});
        }

        System.out.println("✅ JSON satır sayısı: " + rows.size());

        int index = 0;
        for (Map<String, Object> row : rows) {
            try {
                String name = asString(row.get("name"));
                String href = asString(row.get("url"));
                String time = asString(row.get("time"));

                Odds odds = new Odds(
                        asDouble(row.get("ms1")),
                        asDouble(row.get("ms0")),
                        asDouble(row.get("ms2")),
                        asDouble(row.get("ust")),
                        asDouble(row.get("alt")),
                        asDouble(row.get("var")),
                        asDouble(row.get("yok")),
                        asInt(row.get("mbs"), -1)
                );

                MatchInfo matchInfo = new MatchInfo(name, time, href, odds, index++);
                list.add(matchInfo);

                System.out.println("✅ " + name + " (" + time + ") eklendi. | URL=" + href);
            } catch (Exception e) {
                System.out.println("⚠️ Satır parse edilemedi: " + e.getMessage());
            }
        }

        System.out.println("✅ Toplam maç: " + list.size());

    } catch (Exception e) {
        System.out.println("fetchMatches JSON hata: " + e.getMessage());
        e.printStackTrace();
    }

    return list;
}

    private String asString(Object value) {
    if (value == null) return "";
    return String.valueOf(value).trim();
}

private double asDouble(Object value) {
    try {
        if (value == null) return 0.0;
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        String s = String.valueOf(value).trim();
        if (s.isEmpty() || s.equals("-")) return 0.0;
        return Double.parseDouble(s.replace(",", "."));
    } catch (Exception e) {
        return 0.0;
    }
}

private int asInt(Object value, int defaultValue) {
    try {
        if (value == null) return defaultValue;
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        String s = String.valueOf(value).trim();
        if (s.isEmpty()) return defaultValue;
        return Integer.parseInt(s);
    } catch (Exception e) {
        return defaultValue;
    }
}

    // =============================================================
    // GÜNLÜK MAÇLARI ÇEK
    // =============================================================
    public List<MatchInfo> fetchMatchesSelenium() {
        if (driver == null) setupDriver();
        List<MatchInfo> list = new ArrayList<>();
        try {
            String date = LocalDate.now(ZoneId.of("Europe/Istanbul"))
                    .format(DateTimeFormatter.ofPattern("dd.MM.yyyy"));

            // le=1 KORUNDU
            String url = "https://www.nesine.com/iddaa?et=1&le=1&bt=1&dt=" + date;

            System.out.println("🔗 URL açılıyor: " + url);
            driver.manage().deleteAllCookies();
            driver.get(url);
            PageWaitUtils.safeWaitForLoad(driver, 25);

            wait.until(ExpectedConditions.presenceOfElementLocated(
                    By.cssSelector("[data-test-id^='r_'], a[data-test-id='matchName']")));

            expandAllSectionsIfPossible();

            List<Map<String, String>> rawData = scrollAndCollectMatchData();

            System.out.println("✅ Toplam benzersiz maç: " + rawData.size());

            int index = 0;
            for (Map<String, String> data : rawData) {
                try {
                    String name = data.getOrDefault("name", "-");
                    String href = data.getOrDefault("url", "-");
                    String time = data.getOrDefault("time", "-");

                    Odds odds = new Odds(
                            toDouble(data.get("ms1")),
                            toDouble(data.get("ms0")),
                            toDouble(data.get("ms2")),
                            toDouble(data.get("ust")),
                            toDouble(data.get("alt")),
                            toDouble(data.get("var")),
                            toDouble(data.get("yok")),
                            Integer.parseInt(data.getOrDefault("mbs", "-1"))
                    );

                    list.add(new MatchInfo(name, time, href, odds, index++));
                } catch (Exception e) {
                    System.out.println("⚠️ MatchInfo oluşturulamadı: " + e.getMessage());
                }
            }

        } catch (Exception e) {
            System.out.println("fetchMatches hata: " + e.getMessage());
        }
        return list;
    }

    // =============================================================
    // MAÇ SATIRLARINI DOM'DAN TOPLA
    // =============================================================
    private List<Map<String, String>> scrollAndCollectMatchData() throws InterruptedException {
        By matchLinkSelector = By.cssSelector("a[data-test-id='matchName']");
        Set<String> seen = new HashSet<>();
        List<Map<String, String>> collected = new ArrayList<>();

        int stable = 0;
        int maxScroll = 300;
        int prevSeen = 0;

        long startTime = System.currentTimeMillis();
        long maxWaitTime = 420000;

        WebElement scrollContainer = findScrollableContainer();

        int waitTry = 0;
        while (driver.findElements(matchLinkSelector).isEmpty() && waitTry < 30) {
            Thread.sleep(500);
            waitTry++;
        }

        System.out.println("⏳ Match linkleri algılandı (" + waitTry + "sn sonra) - scroll başlıyor...");

        for (int i = 0; i < maxScroll; i++) {
            if (System.currentTimeMillis() - startTime > maxWaitTime) {
                System.out.println("⏰ Max süre doldu");
                break;
            }

            List<WebElement> links = driver.findElements(matchLinkSelector);

            for (WebElement link : links) {
                try {
                    String name = link.getText().trim();
                    String href = Optional.ofNullable(link.getAttribute("href")).orElse("").trim();

                    if (name.isEmpty()) continue;

                    // SADECE gerçek detail URL'si olanlar
                    if (!isRealDetailUrl(href)) {
                        continue;
                    }

                    WebElement card = findMatchCard(link);

                    String time = "-";
                    try {
                        time = card.findElement(By.cssSelector("span[data-testid^='time']")).getText().trim();
                    } catch (Exception ignore) {
                    }

                    String uniqueKey = href + "|" + time;
                    if (seen.contains(uniqueKey)) continue;
                    seen.add(uniqueKey);

                    Map<String, String> map = new HashMap<>();
                    map.put("name", name);
                    map.put("url", href);
                    map.put("time", time);

                    try {
                        WebElement mbsEl = card.findElement(By.cssSelector("[data-test-id='event_mbs'] span"));
                        map.put("mbs", mbsEl.getText().trim());
                    } catch (Exception ex) {
                        map.put("mbs", "-1");
                    }

                    map.put("ms1", getOdd(card, "odd_Maç Sonucu_1"));
                    map.put("ms0", getOdd(card, "odd_Maç Sonucu_X"));
                    map.put("ms2", getOdd(card, "odd_Maç Sonucu_2"));
                    map.put("alt", getOdd(card, "odd_2,5 Gol_Alt"));
                    map.put("ust", getOdd(card, "odd_2,5 Gol_Üst"));
                    map.put("var", getOdd(card, "odd_Karş. Gol_Var"));
                    map.put("yok", getOdd(card, "odd_Karş. Gol_Yok"));

                    collected.add(map);
                    System.out.println("✅ " + name + " (" + time + ") eklendi. | URL=" + href);
                } catch (Exception ex) {
                    System.out.println("⚠️ Kart parse edilemedi: " + ex.getMessage());
                }
            }

            int now = seen.size();
            if (now > prevSeen) {
                stable = 0;
                System.out.println("  ✓ URL'li maç sayısı: " + now + " (+yeni " + (now - prevSeen) + ")");
            } else {
                stable++;
                System.out.println("  ⚠️ Stabilite sayacı: " + stable + "/20 (toplam URL'li: " + now + ")");
            }
            prevSeen = now;

            if (i % 5 == 0) {
                debugSelectorCounts();
            }

            if (stable >= 20) {
                System.out.println("✅ Scroll tamamlandı");
                break;
            }

            clickLoadMoreIfExists();

            List<WebElement> currentLinks = driver.findElements(matchLinkSelector);
            if (!currentLinks.isEmpty()) {
                try {
                    WebElement last = currentLinks.get(currentLinks.size() - 1);
                    js.executeScript("arguments[0].scrollIntoView({block:'center'});", last);
                    Thread.sleep(400);
                    last.sendKeys(Keys.PAGE_DOWN);
                    Thread.sleep(400);
                } catch (Exception e) {
                    js.executeScript("arguments[0].scrollTop = arguments[0].scrollTop + 2400;", scrollContainer);
                }
            } else {
                js.executeScript("arguments[0].scrollTop = arguments[0].scrollTop + 2400;", scrollContainer);
            }

            Thread.sleep(2500);
        }

        System.out.println("🧩 TOPLAM URL'Lİ MAÇ: " + seen.size());
        return collected;
    }

    private boolean isRealDetailUrl(String href) {
        if (href == null || href.isBlank()) return false;
        if (!href.startsWith("http")) return false;

        String h = href.toLowerCase(Locale.ROOT);

        return h.contains("istatistik.nesine.com")
                || h.contains("/ozet")
                || h.contains("/detay")
                || h.contains("/mac/")
                || h.contains("/match/");
    }

    private String getOdd(WebElement matchEl, String testId) {
        try {
            return matchEl.findElement(By.cssSelector("button[data-testid='" + testId + "']")).getText().trim();
        } catch (Exception e) {
            return "-";
        }
    }

    private double toDouble(String s) {
        try {
            if (s == null || s.equals("-") || s.isEmpty()) return 0.0;
            return Double.parseDouble(s.replace(",", "."));
        } catch (Exception e) {
            return 0.0;
        }
    }

    // =============================================================
    // GEÇMİŞ MAÇLAR
    // =============================================================
    public TeamMatchHistory scrapeTeamHistory(String detailUrl, String name) {
        String id = HistoryApiClient.matchId(detailUrl);
        if (id == null) {
            System.out.println("⚠️ Geçersiz istatistik URL: " + detailUrl);
            return null;
        }
        try {
            com.fasterxml.jackson.databind.JsonNode header = HistoryApiClient.get(id, "Header");
            if (header.path("SID").asInt(-1) != 1) {
                throw new java.io.IOException("Unexpected sport for match " + id);
            }
            String home = teamName(header.path("HT").path(0));
            String away = teamName(header.path("AT").path(0));
            if (home.equals("-") || away.equals("-")) {
                throw new java.io.IOException("Team names missing for match " + id);
            }
            TeamMatchHistory history = new TeamMatchHistory(home + " - " + away, home, away, detailUrl);
            com.fasterxml.jackson.databind.JsonNode summary = HistoryApiClient.get(id, "Summary");
            String summaryUrl = detailUrl.replaceAll("/+$", "") + "/ozet";
            appendHistory(history, selectGroup(summary.path("SCH"), 1), "rekabet-gecmisi", 0, summaryUrl);
            com.fasterxml.jackson.databind.JsonNode last = selectGroup(summary.path("SLM"), 5);
            if (last.path("TMS").isArray()) {
                com.fasterxml.jackson.databind.JsonNode teams = last.path("TMS");
                if (teams.size() > 0) appendMatches(history, teams.get(0).path("ML"), "son-maclari", 1, summaryUrl);
                if (teams.size() > 1) appendMatches(history, teams.get(1).path("ML"), "son-maclari", 2, summaryUrl);
            }
            System.out.println("✅ " + home + " - " + away + ": "
                    + history.getRekabetGecmisi().size() + " rekabet, "
                    + history.getSonMaclarHome().size() + "+" + history.getSonMaclarAway().size() + " son maç (HTTP)");
            return history;
        } catch (Exception e) {
            System.out.println("⚠️ " + id + " geçmiş API hatası: " + e.getMessage());
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            if (e instanceof HistoryApiClient.RateLimitException) throw (HistoryApiClient.RateLimitException) e;
            return null;
        }
    }

    private com.fasterxml.jackson.databind.JsonNode selectGroup(com.fasterxml.jackson.databind.JsonNode group, int type) {
        for (com.fasterxml.jackson.databind.JsonNode league : group.path("ML")) {
            for (com.fasterxml.jackson.databind.JsonNode item : league.path("TT")) {
                if (item.path("FT").asInt(-1) == type) return item;
            }
        }
        return com.fasterxml.jackson.databind.node.MissingNode.getInstance();
    }

    private void appendHistory(TeamMatchHistory history, com.fasterxml.jackson.databind.JsonNode group,
            String type, int side, String summaryUrl) {
        for (com.fasterxml.jackson.databind.JsonNode team : group.path("TMS")) {
            appendMatches(history, team.path("ML"), type, side, summaryUrl);
        }
    }

    private void appendMatches(TeamMatchHistory history, com.fasterxml.jackson.databind.JsonNode matches,
            String type, int side, String summaryUrl) {
        for (com.fasterxml.jackson.databind.JsonNode row : matches) {
            int[] score = finalScore(row.path("SC"));
            if (score == null) continue;
            String homeTeam = teamName(row.path("HT"));
            String awayTeam = teamName(row.path("AT"));
            // A missing opponent label must not discard an otherwise valid historical score.
            String date = row.path("POFMD").asText("-");
            String league = row.path("LG").path("N").asText("-");
            MatchResult match = new MatchResult(homeTeam, awayTeam, score[0], score[1], date, league, type, summaryUrl);
            if (side == 0) history.addRekabetGecmisiMatch(match);
            else history.addSonMacMatch(match, side);
        }
    }

    private String teamName(com.fasterxml.jackson.databind.JsonNode team) {
        String value = team.path("N").asText("").trim();
        if (value.isEmpty()) value = team.path("NS").asText("").trim();
        return value.isEmpty() ? "-" : value;
    }

    private int[] finalScore(com.fasterxml.jackson.databind.JsonNode scores) {
        int[] result = null;
        int latest = -1;
        for (com.fasterxml.jackson.databind.JsonNode score : scores) {
            int order = score.path("OBI").asInt(-1);
            // Football final: 99; basketball regulation: 45, overtime final: 1000.
            if ((order == 99 || order == 45 || order == 1000) && order > latest
                    && score.path("HTS").canConvertToInt() && score.path("ATS").canConvertToInt()) {
                result = new int[] {score.path("HTS").asInt(), score.path("ATS").asInt()};
                latest = order;
            }
        }
        return result;
    }

    private String extractScore(WebElement row) {
        try {
            List<WebElement> direct = row.findElements(By.cssSelector("[data-test-id='Score'] span, td[data-test-id='Score']"));
            for (WebElement s : direct) {
                String t = s.getText().trim().replaceAll("\\(.*?\\)", "");
                if (t.matches("\\d+\\s*-\\s*\\d+")) return t;
            }

            List<WebElement> buttons = row.findElements(By.cssSelector("button[data-test-id='NsnButton'] span"));
            for (WebElement b : buttons) {
                String t = b.getText().trim().replaceAll("\\(.*?\\)", "");
                if (t.matches("\\d+\\s*-\\s*\\d+")) return t;
            }

            List<WebElement> spans = row.findElements(By.cssSelector("span"));
            for (WebElement s : spans) {
                String t = s.getText().trim().replaceAll("\\(.*?\\)", "");
                if (t.matches("\\d+\\s*-\\s*\\d+")) return t;
            }
        } catch (Exception ignore) {
        }
        return "-";
    }

    private int[] parseScore(String s) {
        try {
            String[] p = s.split("-");
            return new int[]{Integer.parseInt(p[0].trim()), Integer.parseInt(p[1].trim())};
        } catch (Exception e) {
            return new int[]{-1, -1};
        }
    }

    private String[] extractTeamsFromHeader(String url) {
        String home = "-", away = "-", name = "";
        try {
            driver.get(url);
            PageWaitUtils.waitForPageLoad(driver, 12);
            wait.until(ExpectedConditions.visibilityOfElementLocated(By.cssSelector("div[data-test-id='HeaderTeams']")));

            WebElement header = driver.findElement(By.cssSelector("div[data-test-id='HeaderTeams']"));
            List<WebElement> teams = header.findElements(
                    By.cssSelector("a[data-test-id='TeamLink'] span[data-test-id='HeaderTeams']"));

            if (teams.size() >= 2) {
                home = teams.get(0).getText().trim();
                away = teams.get(1).getText().trim();
            }
        } catch (Exception e) {
            System.out.println("Takım adları çekilemedi: " + e.getMessage());
        }
        name = home + " - " + away;
        return new String[]{home, away, name};
    }

    private String extractTeamName(WebElement el) {
        try {
            return el.getText().trim();
        } catch (Exception e) {
            return "-";
        }
    }

    private String safeText(WebElement parent, String css) {
        try {
            WebElement el = parent.findElement(By.cssSelector(css));
            String t = el.getText().trim();
            return t.isEmpty() ? "-" : t;
        } catch (Exception e) {
            return "-";
        }
    }

    public void close() {
        try {
            if (driver != null) driver.quit();
        } catch (Exception ignore) {
        }
    }

    // =============================================================
    // DOM YARDIMCILARI
    // =============================================================
    private WebElement findScrollableContainer() {
        List<By> candidates = Arrays.asList(
                By.cssSelector("div[class*='scroll']"),
                By.cssSelector("div[class*='content']"),
                By.cssSelector("main"),
                By.cssSelector("body")
        );

        for (By by : candidates) {
            try {
                List<WebElement> els = driver.findElements(by);
                for (WebElement el : els) {
                    Object shObj = js.executeScript("return arguments[0].scrollHeight;", el);
                    Object chObj = js.executeScript("return arguments[0].clientHeight;", el);

                    long sh = shObj instanceof Number ? ((Number) shObj).longValue() : -1L;
                    long ch = chObj instanceof Number ? ((Number) chObj).longValue() : -1L;

                    if (sh > ch + 200) {
                        System.out.println("✅ Scroll container bulundu: " + by);
                        return el;
                    }
                }
            } catch (Exception ignore) {
            }
        }

        System.out.println("⚠️ Özel scroll container bulunamadı, body kullanılacak");
        return driver.findElement(By.tagName("body"));
    }

    private void clickLoadMoreIfExists() {
        List<By> buttons = Arrays.asList(
                By.xpath("//button[contains(., 'Daha Fazla')]"),
                By.xpath("//button[contains(., 'Daha fazla')]"),
                By.xpath("//button[contains(., 'Tümünü Göster')]"),
                By.cssSelector("button[data-test-id*='load'], button[data-testid*='load']")
        );

        for (By by : buttons) {
            try {
                List<WebElement> els = driver.findElements(by);
                for (WebElement btn : els) {
                    if (btn.isDisplayed() && btn.isEnabled()) {
                        js.executeScript("arguments[0].click();", btn);
                        System.out.println("➕ Daha fazla butonuna tıklandı");
                        Thread.sleep(1200);
                        return;
                    }
                }
            } catch (Exception ignore) {
            }
        }
    }

    private void expandAllSectionsIfPossible() {
        List<By> candidates = Arrays.asList(
                By.cssSelector("button[aria-expanded='false']"),
                By.cssSelector("[data-test-id*='accordion'] button"),
                By.cssSelector("[data-testid*='accordion'] button"),
                By.xpath("//button[contains(@aria-label,'aç')]"),
                By.xpath("//button[contains(., 'Daha Fazla')]"),
                By.xpath("//button[contains(., 'Tümünü Göster')]")
        );

        int clicked = 0;

        for (By by : candidates) {
            try {
                List<WebElement> elements = driver.findElements(by);
                for (WebElement el : elements) {
                    try {
                        if (el.isDisplayed() && el.isEnabled()) {
                            js.executeScript("arguments[0].click();", el);
                            clicked++;
                            Thread.sleep(500);
                        }
                    } catch (Exception ignore) {
                    }
                }
            } catch (Exception ignore) {
            }
        }

        System.out.println("📂 Açılabilen bölüm/buton sayısı: " + clicked);
    }

    private WebElement findMatchCard(WebElement matchLink) {
        try {
            return (WebElement) js.executeScript("""
                let el = arguments[0];
                while (el) {
                    if (el.matches && (
                            el.matches("div[data-test-id^='r_']") ||
                            el.querySelector("[data-test-id='event_mbs']") ||
                            el.querySelector("button[data-testid*='odd_']")
                    )) {
                        return el;
                    }
                    el = el.parentElement;
                }
                return arguments[0].parentElement;
            """, matchLink);
        } catch (Exception e) {
            return matchLink;
        }
    }

    private void debugSelectorCounts() {
        System.out.println("DEBUG row[data-sport-id=1]: " +
                driver.findElements(By.cssSelector("div[data-test-id^='r_'][data-sport-id='1']")).size());

        System.out.println("DEBUG any row[data-test-id^=r_]: " +
                driver.findElements(By.cssSelector("[data-test-id^='r_']")).size());

        System.out.println("DEBUG matchName links: " +
                driver.findElements(By.cssSelector("a[data-test-id='matchName']")).size());

        System.out.println("DEBUG all matchName elems: " +
                driver.findElements(By.cssSelector("[data-test-id='matchName']")).size());

        int realUrlCount = 0;
        List<WebElement> links = driver.findElements(By.cssSelector("a[data-test-id='matchName']"));
        for (WebElement link : links) {
            try {
                String href = Optional.ofNullable(link.getAttribute("href")).orElse("");
                if (isRealDetailUrl(href)) {
                    realUrlCount++;
                }
            } catch (Exception ignore) {
            }
        }

        System.out.println("DEBUG real detail url count: " + realUrlCount);
    }
}
