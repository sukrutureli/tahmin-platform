package com.example.prediction;

import com.example.model.PredictionData;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class PredictionUpdater {

	private static final ObjectMapper mapper = new ObjectMapper();

	/**
	 * GitHub Pages üzerindeki JSON'u indirir, skorları günceller, güncel
	 * versiyonunu "data/2025-10-16-updated.json" olarak kaydeder.
	 */
	public static List<PredictionData> updateFromGithub(Map<String, String> updatedScores, String prefix) throws IOException {
		String day;
		LocalTime now = LocalTime.now(ZoneId.of("Europe/Istanbul"));
		if (now.isAfter(LocalTime.MIDNIGHT) && now.isBefore(LocalTime.of(6, 0))) {
			day = LocalDate.now(ZoneId.of("Europe/Istanbul")).minusDays(1)
					.format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
		} else {
			day = LocalDate.now(ZoneId.of("Europe/Istanbul")).format(DateTimeFormatter.ofPattern("yyyy-MM-dd"));
		}

		// 🔹 Private repo'dan dosya URL'si (raw)
		String url = "https://raw.githubusercontent.com/sukrutureli/fathertahmin/main/futbol/data/" + prefix + day + ".json";
		System.out.println("📥 JSON indiriliyor: " + url);

		// 🔹 GitHub Personal Access Token (örneğin env değişkeninden)
		String token = System.getenv("GITHUB_TOKEN"); // veya sabit test için: "ghp_XXXXXXXXXXXX"

		if (token == null || token.isEmpty()) {
			throw new RuntimeException("❌ GITHUB_TOKEN environment variable not set!");
		}

		// 🔹 Token ile HTTP isteği yap
		HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
		conn.setRequestMethod("GET");
		conn.setRequestProperty("Authorization", "token " + token);
		conn.setRequestProperty("Accept", "application/vnd.github.v3.raw");

		int status = conn.getResponseCode();
		if (status != 200) {
			throw new IOException("GitHub dosya indirme hatası: HTTP " + status);
		}

		// 🔹 JSON parse et
		List<PredictionData> predictions;
		try (InputStream in = conn.getInputStream()) {
			predictions = mapper.readerForListOf(PredictionData.class).readValue(in);
		}

		// 🔹 Güncelleme işlemleri...
		for (PredictionData p : predictions) {
			String home = p.getHomeTeam();
			String away = p.getAwayTeam();
			String matchedKey = null;
			int count = 0;

			for (String key : updatedScores.keySet()) {
				String[] parts = key.split(" - ");
				if (parts.length == 2) {
					String homeKey = parts[0];
					String awayKey = parts[1];

					if (home.equals(homeKey) && away.equals(awayKey)) {
						matchedKey = key;
						count = 1;
						break;
					}

					if (home.equals(homeKey) || away.equals(awayKey)) {
						matchedKey = key;
						count++;
					}
				}
			}

			if (matchedKey != null && count == 1) {
				String score = updatedScores.get(matchedKey);
				p.setScore(score);
				evaluatePredictions(p, score);
			} else {
				System.out.println("⚠️ Eşleşme bulunamadı: " + p.getHomeTeam() + " - " + p.getAwayTeam());
			}
		}

		// 🔹 Kaydet
		File outDir = new File("public/futbol/data");
		if (!outDir.exists())
			outDir.mkdirs();
		File outFile = new File(outDir, prefix + day + ".json");
		mapper.writerWithDefaultPrettyPrinter().writeValue(outFile, predictions);

		System.out.println("✅ Güncellenmiş dosya: " + outFile.getAbsolutePath());

		return predictions;
	}

	/**
	 * Skora göre "won/lost/pending" durumu belirler
	 */
	private static void evaluatePredictions(PredictionData p, String score) {
		try {
			String[] parts = score.split("-");
			int home = Integer.parseInt(parts[0].trim());
			int away = Integer.parseInt(parts[1].trim());

			for (String pick : p.getPicks()) {
				String result = evaluatePick(pick, home, away);
				p.getStatuses().put(pick, result);
			}

		} catch (Exception e) {
			System.err.println("⚠�? Skor formatı hatalı: " + score);
		}
	}

	private static String evaluatePick(String pick, int home, int away) {
		if (pick.contains("MS1"))
			return home > away ? "won" : "lost";
		if (pick.contains("MS2"))
			return away > home ? "won" : "lost";
		if (pick.contains("MSX"))
			return away == home ? "won" : "lost";

		if (pick.toLowerCase().contains("üst"))
			return (home + away) > 2.5 ? "won" : "lost";
		if (pick.toLowerCase().contains("alt"))
			return (home + away) < 2.5 ? "won" : "lost";

		if (pick.toLowerCase().contains("var"))
			return (home > 0 && away > 0) ? "won" : "lost";
		if (pick.toLowerCase().contains("yok"))
			return (home == 0 || away == 0) ? "won" : "lost";

		return "pending";
	}
}
