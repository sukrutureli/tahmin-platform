package com.basketbol.scraper;

import com.basketbol.util.FixtureIdentity;

import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import com.basketbol.model.MatchInfo;
import com.basketbol.model.RealScores;

import java.time.*;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class ControlScraper {
    public Map<String, String> fetchFinishedScoresFromDetails(List<RealScores> rsList, List<MatchInfo> matches) {
        Map<String, String> scores = new HashMap<>();
        if (rsList != null && !rsList.isEmpty()) results.addAll(rsList);
        if (matches == null) return scores;
        FixtureIdentity.bindScores(results, matches);
        ResultApiClient client = new ResultApiClient();
        int successfulChecks = 0;
        int failedChecks = 0;
        for (MatchInfo match : matches) {
            if (match == null || match.getName() == null || !match.hasDetailUrl()) continue;
            String name = match.getName().trim();
            try {
                String score = client.finishedScore(match.getDetailUrl(), 2);
                successfulChecks++;
                if (score == null) {
                    System.out.println("⏳ HTTP maç henüz bitmemiş: " + name);
                    continue;
                }
                FixtureIdentity.recordScore(scores, results, match, score);
                System.out.println("✅ HTTP CONTROL " + name + " → " + score);
            } catch (HistoryApiClient.RateLimitException ex) {
                throw ex;
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("HTTP control interrupted", ex);
            } catch (java.io.IOException ex) {
                failedChecks++;
                System.out.println("⚠️ HTTP skor alınamadı: " + name + " | " + ex.getMessage());
            }
        }
        if (successfulChecks == 0 && failedChecks > 0) {
            throw new IllegalStateException("All HTTP scoreboard checks failed; preserving published control data");
        }
        System.out.println("HTTP bitmiş toplam maç: " + scores.size());
        return scores;
    }


    private WebDriver driver;
    private WebDriverWait wait;
    private List<RealScores> results;

    private static final Pattern REGULAR_SCORE_PATTERN = Pattern.compile("(\\d+)\\s*MS\\s*(\\d+)");
    private static final Pattern OVERTIME_SCORE_PATTERN = Pattern.compile("(\\d+)\\s*UZ\\s*(\\d+)");

    public ControlScraper() {
        results = new ArrayList<>();
    }

    private void setupDriver() {
        System.setProperty("webdriver.chrome.driver", "/usr/bin/chromedriver");
        ChromeOptions options = new ChromeOptions();
        options.addArguments("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                "--window-size=1920,1080", "--disable-blink-features=AutomationControlled", "--disable-cache", "--incognito");
        driver = new ChromeDriver(options);
        wait = new WebDriverWait(driver, Duration.ofSeconds(15));
    }

    // MatchInfo'daki her maçın p1 detail sayfasından skoru oku.
    // Basketbol p1 scoreboard'unda skorlar ayrı football CSS class'larında olmayabiliyor;
    // bitmiş maç formatı scoreboard text içinde "homeScore MS awayScore" olarak geliyor.
    public Map<String, String> fetchFinishedScoresFromDetailsSelenium(List<RealScores> rsList, List<MatchInfo> matches) {
        if (driver == null) setupDriver();
        Map<String, String> scores = new HashMap<>();
        if (rsList != null && !rsList.isEmpty()) results.addAll(rsList);
        if (matches == null) return scores;
        FixtureIdentity.bindScores(results, matches);

        System.out.println("🔎 Basket detail skor kontrol edilecek toplam maç: " + matches.size());
        for (MatchInfo matchInfo : matches) {
            if (matchInfo == null || matchInfo.getName() == null) continue;
            String matchName = matchInfo.getName().trim();
            if (!matchInfo.hasDetailUrl()) {
                System.out.println("⚠️ Basket detail URL bulunamadı: " + matchName);
                continue;
            }

            try {
                String url = toAlternativeDetailUrl(matchInfo.getDetailUrl());
                System.out.println("🔎 Basket skor kontrol: " + matchName + " | " + url);
                driver.get(url);
                waitForPageLoad(driver, 15);

                WebElement scoreboard = wait.until(ExpectedConditions.presenceOfElementLocated(
                        By.cssSelector(".broadage-score-container")));
                String scoreboardText = safeText(scoreboard, driver);
                System.out.println("📋 BASKET SCOREBOARD: " + matchName + " | " + scoreboardText);

                if (scoreboardText == null || (!scoreboardText.contains("MS") && !scoreboardText.contains("UZ"))) {
                    System.out.println("⏳ Basket maç henüz bitmemiş: " + matchName);
                    continue;
                }

                // Basketbol bahisleri uzatma dahil nihai skorla sonuçlandığı için UZ varsa onu tercih et.
                Matcher scoreMatcher = scoreboardText.contains("UZ")
                        ? OVERTIME_SCORE_PATTERN.matcher(scoreboardText)
                        : REGULAR_SCORE_PATTERN.matcher(scoreboardText);
                if (!scoreMatcher.find()) {
                    System.out.println("⚠️ Basket MS/UZ bulundu ama skor parse edilemedi: " + matchName + " | " + scoreboardText);
                    continue;
                }

                String homeScore = scoreMatcher.group(1);
                String awayScore = scoreMatcher.group(2);
                String score = homeScore + "-" + awayScore;
                FixtureIdentity.recordScore(scores, results, matchInfo, score);
                System.out.println("✅ BASKET DETAIL " + matchName + " → " + score);
            } catch (TimeoutException e) {
                System.out.println("⚠️ Basket detail skor alanı bulunamadı: " + matchName);
            } catch (Exception e) {
                System.out.println("⚠️ Basket detail skor hatası: " + matchName + " | " + e.getMessage());
            }
        }
        System.out.println("🏀 Detail URL'den bitmiş toplam basket maç: " + scores.size());
        return scores;
    }

    private String toAlternativeDetailUrl(String detailUrl) {
        if (detailUrl == null || detailUrl.isBlank()) return detailUrl;
        if (detailUrl.contains("istatistik.nesine.com/p1/")) return detailUrl;
        return detailUrl.replace("istatistik.nesine.com/", "istatistik.nesine.com/p1/");
    }

    private void upsertRealScore(String home, String away, String score) {
        for (RealScores rs : results) {
            if (Objects.equals(rs.getHomeTeam(), home) && Objects.equals(rs.getAwayTeam(), away)) {
                rs.setScore(score);
                return;
            }
        }
        RealScores rs = new RealScores();
        rs.setHomeTeam(home);
        rs.setAwayTeam(away);
        rs.setScore(score);
        results.add(rs);
    }

    public void close() {
        try { if (driver != null) driver.quit(); } catch (Exception ignore) {}
    }

    private String safeText(WebElement el, WebDriver driver) {
        try {
            String text = el.getAttribute("textContent");
            if (text == null || text.trim().isEmpty()) text = el.getText();
            return text == null ? "-" : text.trim();
        } catch (Exception e) {
            try {
                return ((JavascriptExecutor) driver)
                        .executeScript("return arguments[0].innerText || arguments[0].textContent;", el)
                        .toString().trim();
            } catch (Exception inner) {
                return "-";
            }
        }
    }

    public void waitForPageLoad(WebDriver driver, int timeoutSeconds) {
        new WebDriverWait(driver, Duration.ofSeconds(timeoutSeconds))
                .until(webDriver -> ((JavascriptExecutor) webDriver).executeScript("return document.readyState").equals("complete"));
    }

    public List<RealScores> getResults() {
        return results;
    }
}
