package com.basketbol;

import com.basketbol.scraper.BasketballScraper;
import com.basketbol.scraper.ControlScraper;
import com.basketbol.algorithm.*;
import com.basketbol.html.CombinedHtmlReportGenerator;
import com.basketbol.model.*;
import com.basketbol.prediction.JsonReader;
import com.basketbol.prediction.JsonStorage;
import com.basketbol.prediction.PredictionUpdater;
import java.io.IOException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class Application {

	public static void main(String[] args) throws IOException {
		ZoneId istanbulZone = ZoneId.of("Europe/Istanbul");

		String mode = args.length > 0 ? args[0].toLowerCase() : "basketbol";
		System.out.println("Çalışma modu: " + mode.toUpperCase());

		switch (mode) {
		case "basketbol":
			runBasketballPrediction();
			break;
		case "kontrol":
			runKontrol();
			break;
		default:
			System.out.println("⚠️ Geçersiz argüman: " + mode);
			System.out.println("Kullanım: java -jar prediction.jar [basketbol | kontrol]");
			break;
		}

		System.out.println("\nTamamlandı: " + LocalDateTime.now(istanbulZone));
	}

	private static void runBasketballPrediction() {
		BasketballScraper scraper = null;
		MatchHistoryManager historyManager = new MatchHistoryManager();
		List<MatchInfo> matches = null;
		List<Match> matchStats = new ArrayList<>();
		List<PredictionResult> results = new ArrayList<>();
		ZoneId istanbulZone = ZoneId.of("Europe/Istanbul");

		try {
			System.out.println("=== 🏀 Basketbol Scraper Başlatılıyor ===");
			System.out.println("Zaman: " + LocalDateTime.now(istanbulZone));

			scraper = new BasketballScraper();

			System.out.println("\n1️⃣ Ana sayfa maçları çekiliyor...");
			matches = scraper.fetchMatches();
			System.out.println("Ana sayfadan " + matches.size() + " maç çekildi");

			for (int i = 0; i < matches.size(); i++) {
				MatchInfo match = matches.get(i);

				if (match.hasDetailUrl()) {
					System.out.println("Geçmiş çekiliyor " + (i + 1) + "/" + matches.size() + ": " + match.getName());
					try {
						String url = match.getDetailUrl();
						if (url == null || !url.startsWith("http")) {
							System.out.println("⚠️ Geçersiz URL: " + url);
							continue;
						}

						TeamMatchHistory teamHistory = scraper.scrapeTeamHistory(url, match.getName(), match.getOdds());
						if (teamHistory != null) {
							historyManager.addTeamHistory(teamHistory);
							matchStats.add(teamHistory.createStats(match));
						} else {
							System.out.println("⚠️ Veri yok veya boş döndü: " + match.getName());
						}

						Thread.sleep(1500);
						if ((i + 1) % 5 == 0)
							System.gc();

					} catch (Exception e) {
						System.out.println("Geçmiş çekme hatası: " + e.getMessage());
					}
				}

				if ((i + 1) % 20 == 0) {
					System.out.println("İşlendi: " + (i + 1) + "/" + matches.size());
				}
			}

			// 🔹 Tahmin algoritmaları
			BettingAlgorithm formMomentum = new FormMomentumModel();
			BettingAlgorithm heuristic = new HeuristicPredictor();
			EnsembleModel ensemble = new EnsembleModel(List.of(formMomentum, heuristic));

			for (Match m : matchStats) {
				results.add(ensemble.predict(m, Optional.ofNullable(m.getOdds())));
			}

			// 🔹 Tahminlerin son halini oluştur
			LastPredictionManager lastPredictionManager = new LastPredictionManager(historyManager, results, matches);
			lastPredictionManager.fillPredictions();

			// 🔹 Birleşik HTML raporu oluştur
			CombinedHtmlReportGenerator.generateCombinedHtml(lastPredictionManager.getLastPrediction(), matches,
					historyManager, matchStats, results, lastPredictionManager.getPredictionData(), "basketbol.html",
					getStringDay(false), null);
			System.out.println("✅ basketbol.html oluşturuldu (birleşik rapor).");

			// 🔹 JSON çıktılarını kaydet
			JsonStorage.save("basketbol", "PredictionData", getStringDay(false),
					lastPredictionManager.getPredictionData());
			JsonStorage.save("basketbol", "LastPrediction", getStringDay(false),
					lastPredictionManager.getLastPrediction());
			JsonStorage.save("basketbol", "MatchInfo", getStringDay(false), matches);
			JsonStorage.save("basketbol", "TeamMatchHistory", getStringDay(false), historyManager.getTeamHistories());
			JsonStorage.save("basketbol", "Match", getStringDay(false), matchStats);
			JsonStorage.save("basketbol", "PredictionResult", getStringDay(false), results);

		} catch (Exception e) {
			System.out.println("GENEL HATA: " + e.getMessage());
			e.printStackTrace();
		} finally {
			if (scraper != null)
				scraper.close();
		}
	}

	private static void runKontrol() throws IOException {
		ControlScraper scraper = null;
		MatchHistoryManager historyManager = new MatchHistoryManager();
		List<MatchInfo> matches = JsonReader.readFromGithub("basketbol", "MatchInfo", JsonReader.getToday(),
				MatchInfo.class);
		List<Match> matchStats = JsonReader.readFromGithub("basketbol", "Match", JsonReader.getToday(), Match.class);
		ZoneId istanbulZone = ZoneId.of("Europe/Istanbul");
		List<PredictionResult> results = JsonReader.readFromGithub("basketbol", "PredictionResult",
				JsonReader.getToday(), PredictionResult.class);

		List<TeamMatchHistory> teamHistoryList = JsonReader.readFromGithub("basketbol", "TeamMatchHistory",
				JsonReader.getToday(), TeamMatchHistory.class);

		List<RealScores> rsList = JsonReader.readFromGithub("basketbol", "RealScores", JsonReader.getToday(),
				RealScores.class);

		try {
			System.out.println("Zaman: " + LocalDateTime.now(istanbulZone));

			// Scraper'ı başlat
			scraper = new ControlScraper();

			Map<String, String> updatedScores = scraper.fetchFinishedScoresBasket(rsList);

			List<PredictionData> predictions = PredictionUpdater.updateFromGithub(updatedScores, "PredictionData-");

			for (int i = 0; i < matches.size(); i++) {
				MatchInfo match = matches.get(i);

				// Detay URL'si varsa geçmiş verilerini çek
				if (match.hasDetailUrl()) {
					System.out.println("Geçmiş çekiliyor " + (i + 1) + "/" + matches.size() + ": " + match.getName());

					historyManager.addTeamHistory(teamHistoryList.get(i));

				}
			}

			LastPredictionManager lastPredictionManager = new LastPredictionManager(historyManager, results, matches);
			lastPredictionManager.fillPredictions();

			CombinedHtmlReportGenerator.generateCombinedHtml(lastPredictionManager.getLastPrediction(), matches,
					historyManager, matchStats, results, predictions, "basketbol.html", getStringDay(true),
					scraper.getResults());
			System.out.println("basketbol.html oluşturuldu.");

			// JsonStorage.save("basketbol", "PredictionData",
			// lastPredictionManager.getPredictionData());
			JsonStorage.save("basketbol", "RealScores", JsonReader.getToday(), scraper.getResults());

		} catch (Exception e) {
			System.out.println("GENEL HATA: " + e.getMessage());
			e.printStackTrace();
		} finally {
			if (scraper != null) {
				scraper.close();
			}
		}
	}

	public static String getStringDay(boolean minusDay) {
		LocalTime now = LocalTime.now(ZoneId.of("Europe/Istanbul"));
		String day = LocalDate.now(ZoneId.of("Europe/Istanbul")).format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));

		if (minusDay) {
			if (now.isAfter(LocalTime.MIDNIGHT) && now.isBefore(LocalTime.of(6, 0))) {
				day = LocalDate.now(ZoneId.of("Europe/Istanbul")).minusDays(1)
						.format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
			} else {
				day = LocalDate.now(ZoneId.of("Europe/Istanbul")).format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
			}
		}

		return day;
	}
}
