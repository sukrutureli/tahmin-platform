package com.basketbol.algorithm;

import com.basketbol.model.*;
import java.util.Optional;

/**
 * Geliştirilmiş HeuristicPredictor (basketbol): - Tempo + barem farkına göre
 * normalize edilmiş tahmin - Sigmoid/logit dönüşümüyle kalibre edilmiş MS
 * olasılıkları - Barem merkezli Over/Under olasılığı - Dinamik ev avantajı (lig
 * ortalamasına göre) - Ligsiz, açıklanabilir model
 */
public class HeuristicPredictor implements BettingAlgorithm {

	@Override
	public String name() {
		return "HeuristicPredictor";
	}

	@Override
	public double weight() {
		return 0.5; // diğer modelle eşit ağırlık
	}

	@Override
	public PredictionResult predict(Match match, Optional<Odds> oddsOpt) {
		BasketballStats h = match.getHomeStats();
		BasketballStats a = match.getAwayStats();

		if (h == null || a == null || h.isEmpty() || a.isEmpty())
			return neutralResult(match);

		// --- 1. Barem bilgisi (varsa) ---
		double barem = -1.0;
		if (oddsOpt.isPresent()) {
			Odds o = oddsOpt.get();
			if (o.gethOverUnderValue() > 0)
				barem = o.gethOverUnderValue();
		}

		// --- 2. Ortalama hücum/savunma verimliliği ---
		double offHome = h.getAvgPointsFor();
		double defHome = h.getAvgPointsAgainst();
		double offAway = a.getAvgPointsFor();
		double defAway = a.getAvgPointsAgainst();

		// --- 3. Beklenen skorlar ---
		double forWeight = 0.6, againstWeight = 0.4;
		double homeAdv = 3.5 + 0.05 * (offHome - defHome); // dinamik ev avantajı

		double expectedHome = (forWeight * offHome) + (againstWeight * defAway) + homeAdv;
		double expectedAway = (forWeight * offAway) + (againstWeight * defHome);
		double diff = expectedHome - expectedAway;
		double total = expectedHome + expectedAway;

		// --- 4. Olasılıklar (sigmoid/logit ile kalibrasyon) ---
		double k = 0.20; // eğim katsayısı (daha yüksek = daha keskin)
		double pHome = 1.0 / (1.0 + Math.exp(-k * diff));
		double pAway = 1.0 - pHome;

		// normalize (yakın farklarda 0.55 civarı)
		pHome = clamp(pHome, 0.05, 0.95);
		pAway = 1.0 - pHome;

		// --- 5. Over/Under olasılığı (barem farkına göre sigmoid) ---
		double pOver = 0.5;
		if (barem > 0) {
			double delta = total - barem;
			pOver = 1.0 / (1.0 + Math.exp(-delta / 10.0)); // barem farkına duyarlı
		}

		// --- 6. Tahmin etiketleri ---
		String msPick = (diff > 2.5) ? "MS1" : (diff < -2.5 ? "MS2" : "Yakın");
		String ouPick;
		if (barem < 0)
			ouPick = "-";
		else
			ouPick = (pOver > 0.55) ? "Üst" : (pOver < 0.45 ? "Alt" : "Sınırda");

		String finalPick = msPick + " | " + ouPick;

		// --- 7. Skor tahmini (beklenen skorları yuvarla) ---
		String score = String.format("%d-%d", Math.round(expectedHome), Math.round(expectedAway));

		// --- 8. Güven oranı ---
		double confidence = clamp(0.55 + Math.abs(diff) / 25.0, 0.55, 0.95);

		return new PredictionResult(name(), match.getHomeTeam(), match.getAwayTeam(), pHome, 0.0, pAway, pOver, 0.0,
				finalPick, confidence, score);
	}

	private static double clamp(double v, double lo, double hi) {
		return Math.max(lo, Math.min(hi, v));
	}

	private PredictionResult neutralResult(Match m) {
		return new PredictionResult(name(), m.getHomeTeam(), m.getAwayTeam(), 0.5, 0.0, 0.5, 0.5, 0.0, "-", 0.5, "-");
	}
}
