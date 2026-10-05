package com.example.prediction;

import com.example.model.PredictionData;
import com.example.model.MatchInfo;
import com.example.util.FixtureIdentity;
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
