package com.basketbol.algorithm;

import com.basketbol.model.*;
import java.util.Optional;

/**
 * Geliştirilmiş FormMomentumModel (basketbol): - Momentum farkı ve form
 * kombinasyonu (sigmoid ile normalize) - Barem farkına göre kalibre Over/Under
 * olasılığı - Dinamik ev avantajı ve confidence hesaplama - Ligsiz, turnuva
 * bağımsız, stabil model
 */
public class FormMomentumModel implements BettingAlgorithm {

	@Override
	public String name() {
		return "FormMomentumModel";
	}

	@Override
	public double weight() {
		return 0.5; // HeuristicPredictor ile eşit
	}

	@Override
	public PredictionResult predict(Match match, Optional<Odds> oddsOpt) {
		BasketballStats h = match.getHomeStats();
		BasketballStats a = match.getAwayStats();

		if (h == null || a == null || h.isEmpty() || a.isEmpty())
			return neutral(match);

		// --- 1. Barem bilgisi (varsa) ---
		double barem = -1.0;
		if (oddsOpt.isPresent()) {
			Odds o = oddsOpt.get();
			if (o.gethOverUnderValue() > 0)
				barem = o.gethOverUnderValue();
		}

		// --- 2. Momentum ve hücum farkı ---
		double formMomentum = (h.getPpg() - a.getPpg());
		double offDiff = (h.getAvgPointsFor() - a.getAvgPointsFor());
		double defDiff = (a.getAvgPointsAgainst() - h.getAvgPointsAgainst());

		// normalize: momentum ve hücum farkını ±1 bandına sıkıştır
		double momentum = Math.tanh(formMomentum / 10.0);
		double powerDiff = Math.tanh((offDiff + defDiff) / 15.0);

		// --- 3. Ev avantajı ve fark ---
		double homeAdv = 3.5; // sabit ev bonusu
		double diff = (momentum * 6.0) + (powerDiff * 8.0) + homeAdv;
		double total = 0.5 * (h.getAvgPointsFor() + a.getAvgPointsFor())
				+ 0.5 * (h.getAvgPointsAgainst() + a.getAvgPointsAgainst());

		// --- 4. Logit kalibrasyonu (farkı olasılığa çevir) ---
		double k = 0.20;
		double pHome = 1.0 / (1.0 + Math.exp(-k * diff));
		pHome = clamp(pHome, 0.05, 0.95);
		double pAway = 1.0 - pHome;

		// --- 5. Over/Under olasılığı (barem farkına göre sigmoid) ---
		double pOver = 0.5;
		if (barem > 0) {
			double delta = total - barem;
			pOver = 1.0 / (1.0 + Math.exp(-delta / 8.0));
		}

		// --- 6. Tahminler ---
		String msPick = (diff > 2.5) ? "MS1" : (diff < -2.5 ? "MS2" : "Yakın");
		String ouPick;
		if (barem < 0)
			ouPick = "-";
		else
			ouPick = (pOver > 0.55) ? "Üst" : (pOver < 0.45 ? "Alt" : "Sınırda");

		String finalPick = msPick + " | " + ouPick;

		// --- 7. Güven oranı ---
		double confidence = clamp(0.55 + Math.abs(diff) / 25.0, 0.55, 0.95);

		// --- 8. Tahmini skor (beklenen sayılardan) ---
		double expectedHome = total / 2.0 + diff / 2.0;
		double expectedAway = total / 2.0 - diff / 2.0;
		String score = String.format("%d-%d", Math.round(expectedHome), Math.round(expectedAway));

		return new PredictionResult(name(), match.getHomeTeam(), match.getAwayTeam(), pHome, 0.0, pAway, pOver, 0.0,
				finalPick, confidence, score);
	}

	private double clamp(double v, double lo, double hi) {
		return Math.max(lo, Math.min(hi, v));
	}

	private PredictionResult neutral(Match m) {
		return new PredictionResult(name(), m.getHomeTeam(), m.getAwayTeam(), 0.5, 0.0, 0.5, 0.5, 0.0, "-", 0.5, "-");
	}
}
