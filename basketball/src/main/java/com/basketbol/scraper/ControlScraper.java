package com.basketbol.scraper;

import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import com.basketbol.model.MatchInfo;
import com.basketbol.model.RealScores;

import java.time.*;
import java.util.*;

public class ControlScraper {
    private WebDriver driver;
    private WebDriverWait wait;
    private List<RealScores> results;

    public ControlScraper() {
        setupDriver();
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

    // Futboldaki CONTROL ile aynı yaklaşım: MatchInfo'daki her maçın p1 detail sayfasından skoru oku.
    public Map<String, String> fetchFinishedScoresFromDetails(List<RealScores> rsList, List<MatchInfo> matches) {
        Map<String, String> scores = new HashMap<>();
        if (rsList != null && !rsList.isEmpty()) results.addAll(rsList);
        if (matches == null) return scores;

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

                if (scoreboardText == null || !scoreboardText.contains("MS")) {
                    System.out.println("⏳ Basket maç henüz bitmemiş: " + matchName);
                    continue;
                }

                String homeScore = safeText(scoreboard.findElement(By.cssSelector(".broadage-home-team-score")), driver);
                String awayScore = safeText(scoreboard.findElement(By.cssSelector(".broadage-away-team-score")), driver);
                if (!homeScore.matches("\\d+") || !awayScore.matches("\\d+")) {
                    System.out.println("⚠️ Geçersiz basket skor: " + matchName + " | " + homeScore + "-" + awayScore);
                    continue;
                }

                String score = homeScore + "-" + awayScore;
                scores.put(matchName, score);
                String[] teams = matchName.split(" - ", 2);
                if (teams.length == 2) upsertRealScore(teams[0].trim(), teams[1].trim(), score);
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
        try { driver.quit(); } catch (Exception ignore) {}
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
