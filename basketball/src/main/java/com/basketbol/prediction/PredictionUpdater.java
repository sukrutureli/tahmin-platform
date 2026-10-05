package com.basketbol.prediction;

import com.basketbol.model.PredictionData;
import com.basketbol.model.MatchInfo;
import com.basketbol.util.FixtureIdentity;
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
	public static List<PredictionData> updateFromGithub(Map<String, String> updatedScores,
			String prefix, List<MatchInfo> matches, String day) throws IOException {
		// 🔹 Private repo'dan dosya URL'si (raw)
		String url = "https://raw.githubusercontent.com/sukrutureli/fathertahmin/main/basketbol/data/" + prefix + day + ".json";
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

		return update(predictions, updatedScores, matches, prefix, day);
    }

    public static List<PredictionData> update(List<PredictionData> predictions,
            Map<String, String> updatedScores, List<MatchInfo> matches, String prefix, String day) throws IOException {
        FixtureIdentity.bindPredictions(predictions, matches);
        for (PredictionData p : predictions) {
            String score = p.getEventId() == null ? null : updatedScores.get(p.getEventId());
            if (score != null) {
                p.setScore(score);
                evaluatePredictions(p, score);
            }
        }

		// 🔹 Kaydet
		File outDir = new File("public/basketbol/data");
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
				String result = evaluatePickBasketbol(pick, home, away);
				p.getStatuses().put(pick, result);
			}

		} catch (Exception e) {
			System.err.println("⚠�? Skor formatı hatalı: " + score);
		}
	}

	private static String evaluatePickBasketbol(String pick, int home, int away) {
		String[] splitPick = pick.split(" ");
		Double barem = null;
		if (Character.isDigit(pick.charAt(0))) {
			barem = Double.valueOf(splitPick[0].replace(",", "."));
		}

		if (pick.contains("MS1"))
			return home > away ? "won" : "lost";
		if (pick.contains("MS2"))
			return away > home ? "won" : "lost";

		if (pick.toLowerCase().contains("üst"))
			return (home + away) > barem ? "won" : "lost";
		if (pick.toLowerCase().contains("alt"))
			return (home + away) < barem ? "won" : "lost";

		return "pending";
	}
}
