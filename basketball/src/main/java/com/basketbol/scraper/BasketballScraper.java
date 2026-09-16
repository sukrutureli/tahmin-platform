package com.basketbol.scraper;

import com.basketbol.model.MatchInfo;
import com.basketbol.model.MatchResult;
import com.basketbol.model.Odds;
import com.basketbol.model.TeamMatchHistory;

import org.openqa.selenium.*;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;

public class BasketballScraper {

	private WebDriver driver;
	private JavascriptExecutor js;
	private WebDriverWait wait;

	private static final String BASKETBALL_JSON_URL =
        "https://sukrutureli.github.io/Scraper/output/latestBasketbol.json";

	public BasketballScraper() {
		setupDriver();
	}

	private void setupDriver() {
		System.setProperty("webdriver.chrome.driver", "/usr/bin/chromedriver");
		ChromeOptions options = new ChromeOptions();
		options.addArguments("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
				"--window-size=1920,1080", "--disable-blink-features=AutomationControlled",
				"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)");
		driver = new ChromeDriver(options);
		js = (JavascriptExecutor) driver;
		wait = new WebDriverWait(driver, Duration.ofSeconds(20));
	}

	public List<MatchInfo> fetchMatches() {
    List<MatchInfo> list = new ArrayList<>();

    try {
        System.out.println("🔗 Basketbol JSON açılıyor: " + BASKETBALL_JSON_URL);

        List<Map<String, Object>> rows = downloadBasketballJsonRows();
        System.out.println("🏀 JSON satır sayısı: " + rows.size());

        int index = 0;
        for (Map<String, Object> row : rows) {
            try {
                String name = asString(row.get("name"));
                String href = asString(row.get("url"));
                String time = asString(row.get("time"));

                Odds odds = new Odds(
                        asDouble(row.get("ms1")),
                        asDouble(row.get("ms2")),
                        asDouble(row.get("h1Value")),
                        asDouble(row.get("h1")),
                        asDouble(row.get("h2")),
                        asDouble(row.get("h2Value")),
                        asDouble(row.get("alt")),
                        asDouble(row.get("limit")),
                        asDouble(row.get("ust"))
                );

                list.add(new MatchInfo(name, time, href, odds, index++));
                System.out.println("✅ " + name + " (" + time + ") eklendi. | URL=" + href);

            } catch (Exception e) {
                System.out.println("⚠️ Basket satırı parse edilemedi: " + e.getMessage());
            }
        }

        System.out.println("✅ Toplam basketbol maçı: " + list.size());

    } catch (Exception e) {
        System.out.println("fetchMatches JSON hata: " + e.getMessage());
        e.printStackTrace();
    }

    return list;
}

	private List<Map<String, Object>> downloadBasketballJsonRows() throws Exception {
    HttpURLConnection conn = null;

    try {
        conn = (HttpURLConnection) new URL(BASKETBALL_JSON_URL).openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(30000);
        conn.setRequestProperty("Accept", "application/json");
        conn.setRequestProperty("User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36");

        int status = conn.getResponseCode();
        if (status != 200) {
            throw new RuntimeException("latestBasketbol.json alınamadı. HTTP=" + status);
        }

        ObjectMapper mapper = new ObjectMapper();
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

        try (InputStream is = conn.getInputStream()) {
            return mapper.readValue(is, new TypeReference<List<Map<String, Object>>>() {});
        }

    } finally {
        if (conn != null) {
            conn.disconnect();
        }
    }
}

private String asString(Object value) {
    if (value == null) {
        return "";
    }
    return String.valueOf(value).trim();
}

private double asDouble(Object value) {
    try {
        if (value == null) {
            return 0.0;
        }

        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }

        String s = String.valueOf(value).trim();
        if (s.isEmpty() || s.equals("-")) {
            return 0.0;
        }

        return Double.parseDouble(s.replace(",", "."));
    } catch (Exception e) {
        return 0.0;
    }
}

	// =============================================================
	// GÜNLÜK MAÇLAR
	// =============================================================
	public List<MatchInfo> fetchMatchesSelenium() {
		List<MatchInfo> list = new ArrayList<>();
		try {
			String date = LocalDate.now(ZoneId.of("Europe/Istanbul")).format(DateTimeFormatter.ofPattern("dd.MM.yyyy"));
			String url = "https://www.nesine.com/iddaa/basketbol?et=2&le=1&dt=" + date;

			System.out.println("🔗 URL açılıyor: " + url);
			driver.manage().deleteAllCookies();
			driver.get(url);
			PageWaitUtils.safeWaitForLoad(driver, 25);
			wait.until(ExpectedConditions.presenceOfElementLocated(By.cssSelector("[data-test-id^='r_']")));

			List<Map<String, String>> raw = scrollAndCollectMatchData();
			System.out.println("🏀 Toplam basketbol maçı: " + raw.size());

			int index = 0;
			for (Map<String, String> d : raw) {
				Odds o = new Odds(toDouble(d.get("ms1")), toDouble(d.get("ms2")), toDouble(d.get("h1Value")),
						toDouble(d.get("h1")), toDouble(d.get("h2")), toDouble(d.get("h2Value")),
						toDouble(d.get("alt")), toDouble(d.get("limit")), toDouble(d.get("ust")));
				list.add(new MatchInfo(d.get("name"), d.get("time"), d.get("url"), o, index++));
			}

		} catch (Exception e) {
			System.out.println("fetchMatches hata: " + e.getMessage());
		}
		return list;
	}

	// =============================================================
	// SCROLL VE MAÇLARI TOPLA
	// =============================================================
	private List<Map<String, String>> scrollAndCollectMatchData() throws InterruptedException {
		By eventSelector = By.cssSelector("div[data-test-id^='r_'][data-sport-id='2']");
		Set<String> seen = new HashSet<>();
		List<Map<String, String>> collected = new ArrayList<>();

		int stable = 0, prevCount = 0;
		int maxScroll = 100;
		int scrollAmount = 800;

		while (driver.findElements(eventSelector).isEmpty())
			Thread.sleep(500);
		System.out.println("⏳ Basketbol maçları göründü - scroll başlıyor...");

		for (int i = 0; i < maxScroll; i++) {
			List<WebElement> matches = driver.findElements(eventSelector);

			for (WebElement el : matches) {
				try {
					WebElement nameEl = el.findElement(By.cssSelector("[data-test-id='matchName']"));
					String name = nameEl.getText().trim();
					if (name.isEmpty() || seen.contains(name))
						continue;
					seen.add(name);

					Map<String, String> map = new HashMap<>();
					map.put("name", name);
					map.put("url", nameEl.getAttribute("href"));

					// Saat
					try {
						String time = el.findElement(By.cssSelector("span[data-testid^='time']")).getText().trim();
						map.put("time", time);
					} catch (Exception ex) {
						map.put("time", "-");
					}

					// MBS
					try {
						String mbs = el.findElement(By.cssSelector("[data-test-id='event_mbs'] span")).getText().trim();
						map.put("mbs", mbs);
					} catch (Exception e) {
						map.put("mbs", "-1");
					}

					// MS1 / MS2
					map.put("ms1", getOdd(el, "odd_Maç Sonucu_1"));
					map.put("ms2", getOdd(el, "odd_Maç Sonucu_2"));

					// Handikap (H1/H2)
					map.put("h1Value", getOdd(el, "odd_Handikaplı Maç Sonucu_H1"));
					map.put("h1", getOdd(el, "odd_Handikaplı Maç Sonucu_1"));
					map.put("h2", getOdd(el, "odd_Handikaplı Maç Sonucu_2"));
					map.put("h2Value", getOdd(el, "odd_Handikaplı Maç Sonucu_H2"));

					// Alt / Üst
					map.put("alt", getOdd(el, "odd_Alt/Üst_Alt"));
					map.put("limit", getOdd(el, "odd_Alt/Üst_Limit"));
					map.put("ust", getOdd(el, "odd_Alt/Üst_Üst"));

					collected.add(map);
					System.out.println("✅ " + name + " (" + map.get("time") + ") eklendi.");

				} catch (Exception ignore) {
				}
			}

			if (seen.size() == prevCount)
				stable++;
			else
				stable = 0;
			if (stable >= 10) {
				System.out.println("✅ Scroll tamamlandı (sabitliğe ulaşıldı)");
				break;
			}
			prevCount = seen.size();

			js.executeScript("window.scrollBy(0, " + scrollAmount + ");");
			Thread.sleep(700);
		}

		System.out.println("🧩 TOPLAM BENZERSİZ MAÇ: " + seen.size());
		return collected;
	}

	private String getOdd(WebElement el, String testId) {
		try {
			return el.findElement(By.cssSelector("[data-testid='" + testId + "']")).getText().trim();
		} catch (Exception e) {
			return "-";
		}
	}

	private double toDouble(String s) {
		try {
			if (s == null || s.equals("-") || s.isEmpty())
				return 0.0;
			return Double.parseDouble(s.replace(",", "."));
		} catch (Exception e) {
			return 0.0;
		}
	}

	// =============================================================
	// GEÇMİŞ MAÇLAR (REKABET + SON MAÇLAR)
	// =============================================================
	public TeamMatchHistory scrapeTeamHistory(String detailUrl, String name, Odds odds) {
		if (detailUrl == null || !detailUrl.startsWith("http"))
			return null;

		String[] teams = extractTeamsFromHeader(detailUrl);
		String home = teams[0];
		String away = teams[1];
		String title = teams[2];

		TeamMatchHistory th = new TeamMatchHistory(title, home, away, detailUrl, odds);
		try {
			String summaryUrl = detailUrl + "/ozet";
			driver.get(summaryUrl);
			PageWaitUtils.safeWaitForLoad(driver, 15);
			Thread.sleep(1000);

			// --- REKABET GEÇMİŞİ ---
			try {
				List<WebElement> rows = driver
						.findElements(By.cssSelector("div[data-test-id='CompitionHistoryTableItem']"));
				System.out.println("🔹 Rekabet geçmişi satır sayısı: " + rows.size());

				for (WebElement r : rows) {
					try {
						// 🔹 Tarih
						String date = safeText(r,
								"[data-test-id='CompitionTableItemSeason'], [data-test-id='TableBodyDate']");

						// 🔹 Lig (bazı basket sayfalarında iç span’lar içinde)
						String league = "-";
						try {
							WebElement leagueEl = r.findElement(By.cssSelector(
									"[data-test-id='CompitionTableItemLeague'], [data-test-id='CompitionTableItemTournament'], [data-test-id='CompitionTableItemCompetition'], [data-test-id='TableBodyTournament']"));
							List<WebElement> spans = leagueEl.findElements(By.tagName("span"));
							if (!spans.isEmpty()) {
								StringBuilder sb = new StringBuilder();
								for (WebElement s : spans) {
									String txt = s.getText().trim();
									if (!txt.isEmpty()) {
										if (sb.length() > 0)
											sb.append(" ");
										sb.append(txt);
									}
								}
								league = sb.toString().trim();
							} else {
								league = leagueEl.getText().trim();
							}
						} catch (Exception ignore) {
						}

						String homeTeam = extractTeamName(
								r.findElement(By.cssSelector("div[data-test-id='HomeTeam']")));
						String awayTeam = extractTeamName(
								r.findElement(By.cssSelector("div[data-test-id='AwayTeam']")));
						String score = extractScore(r);
						int[] sc = parseScore(score);

						th.addRekabetGecmisiMatch(
								new MatchResult(homeTeam, awayTeam, sc[0], sc[1], date, league, "rekabet-gecmisi"));
					} catch (Exception ex) {
						System.out.println("⚠️ Rekabet satırı hatası: " + ex.getMessage());
					}
				}
			} catch (Exception e) {
				System.out.println("extractCompetitionHistoryResults hata: " + e.getMessage());
			}

			// --- SON MAÇLAR (Ev / Dep) ---
			try {
				List<WebElement> tables = driver.findElements(By.cssSelector("div[data-test-id^='LastMatchesTable']"));
				for (WebElement table : tables) {
					int currentSide = 0;
					try {
						WebElement titleEl = table
								.findElement(By.cssSelector("h3, [data-test-id='LastMatchesTableTitle']"));
						String titleText = titleEl.getText().toLowerCase(Locale.ROOT);
						if (titleText.contains("ev") || titleText.contains("home"))
							currentSide = 1;
						else if (titleText.contains("deplasman") || titleText.contains("away"))
							currentSide = 2;
					} catch (Exception e) {
						currentSide = (tables.indexOf(table) == 0) ? 1 : 2;
					}

					List<WebElement> rows = table.findElements(By.cssSelector("tbody tr"));
					for (WebElement r : rows) {
						try {
							// 🔹 Lig ve tarih aynı hücrede (ör: <td
							// data-test-id="TableBodyLeague"><span>V-L</span><span>31 Eki</span></td>)
							String league = "-";
							String date = "-";
							try {
								WebElement td = r.findElement(By.cssSelector("td[data-test-id='TableBodyLeague']"));
								List<WebElement> spans = td.findElements(By.tagName("span"));
								if (!spans.isEmpty()) {
									if (spans.size() >= 1)
										league = spans.get(0).getText().trim();
									if (spans.size() >= 2)
										date = spans.get(1).getText().trim();
								} else {
									league = td.getText().trim();
								}
							} catch (Exception ignore) {
							}

							String homeTeam = extractTeamName(
									r.findElement(By.cssSelector("div[data-test-id='HomeTeam']")));
							String awayTeam = extractTeamName(
									r.findElement(By.cssSelector("div[data-test-id='AwayTeam']")));
							String score = extractScore(r);
							int[] sc = parseScore(score);

							th.addSonMacMatch(
									new MatchResult(homeTeam, awayTeam, sc[0], sc[1], date, league, "son-maclari"),
									currentSide);
						} catch (Exception ex) {
							System.out.println("⚠️ Satır hatası: " + ex.getMessage());
						}
					}
				}
			} catch (Exception e) {
				System.out.println("extractMatchResults hata: " + e.getMessage());
			}

			System.out.println("✅ " + title + " için geçmiş verisi: " + th.getRekabetGecmisi().size() + " rekabet, "
					+ th.getSonMaclarHome().size() + "+" + th.getSonMaclarAway().size() + " son maç");
		} catch (Exception e) {
			System.out.println("⚠️ Geçmiş verisi hatası: " + e.getMessage());
		}
		return th;
	}

	private String extractScore(WebElement row) {
		try {
			// 1) Öncelikle normal tablo skor alanlarını ara
			List<WebElement> direct = row
					.findElements(By.cssSelector("[data-test-id='Score'] span, td[data-test-id='Score']"));
			for (WebElement s : direct) {
				String t = s.getText().trim().replaceAll("\\(.*?\\)", "");
				if (t.matches("\\d+\\s*-\\s*\\d+"))
					return t;
			}

			// 2) Eğer bulunamadıysa, buton veya tooltip içindeki skorları ara
			List<WebElement> buttons = row.findElements(By.cssSelector("button[data-test-id='NsnButton'] span"));
			for (WebElement b : buttons) {
				String t = b.getText().trim().replaceAll("\\(.*?\\)", "");
				if (t.matches("\\d+\\s*-\\s*\\d+"))
					return t;
			}

			// 3) Alternatif: direkt <span> içinde "X-Y" formu
			List<WebElement> spans = row.findElements(By.cssSelector("span"));
			for (WebElement s : spans) {
				String t = s.getText().trim().replaceAll("\\(.*?\\)", "");
				if (t.matches("\\d+\\s*-\\s*\\d+"))
					return t;
			}
		} catch (Exception e) {
			// ignore
		}
		return "-";
	}

	private int[] parseScore(String s) {
		try {
			String[] p = s.split("-");
			return new int[] { Integer.parseInt(p[0].trim()), Integer.parseInt(p[1].trim()) };
		} catch (Exception e) {
			return new int[] { -1, -1 };
		}
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

	private String[] extractTeamsFromHeader(String url) {
		String home = "-", away = "-", name = "";
		try {
			driver.get(url);
			PageWaitUtils.waitForPageLoad(driver, 12);
			wait.until(
					ExpectedConditions.visibilityOfElementLocated(By.cssSelector("div[data-test-id='HeaderTeams']")));

			WebElement header = driver.findElement(By.cssSelector("div[data-test-id='HeaderTeams']"));
			List<WebElement> teams = header
					.findElements(By.cssSelector("a[data-test-id='TeamLink'] span[data-test-id='HeaderTeams']"));

			if (teams.size() >= 2) {
				home = teams.get(0).getText().trim();
				away = teams.get(1).getText().trim();
			}
		} catch (Exception e) {
			System.out.println("Takım adları çekilemedi: " + e.getMessage());
		}
		name = home + " - " + away;
		return new String[] { home, away, name };
	}

	public void close() {
		try {
			driver.quit();
		} catch (Exception ignore) {
		}
	}
}

