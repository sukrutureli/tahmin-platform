package com.example.algo;

import java.util.*;
import com.example.model.*;

public class EnsembleModel implements BettingAlgorithm {
	private final List<BettingAlgorithm> models;

	public EnsembleModel(List<BettingAlgorithm> models) {
		this.models = models;
	}

	@Override
	public String name() {
		return "EnsembleModel";
	}

	public double[] weight() {
		return new double[] { 1.0, 1.0 };
	}

	@Override
	public PredictionResult predict(Match match, Optional<Odds> odds) {
		double pH = 0, pD = 0, pA = 0; // Maç sonucu
		double pO = 0, pB = 0; // Üst ve BTTS
		double totW = 0;
		double totWOUBtts = 0;

		String bestScore = "";

		for (BettingAlgorithm m : models) {
			PredictionResult r = m.predict(match, odds);
			if (r == null)
				continue;

			double w1 = m.weight()[0];
			double w2 = m.weight()[1];

			pH += w1 * safe(r.getpHome());
			pD += w1 * safe(r.getpDraw());
			pA += w1 * safe(r.getpAway());
			pO += w2 * safe(r.getpOver25());
			pB += w2 * safe(r.getpBttsYes());

			totW += w1;
			totWOUBtts += w2;

			// skor doluysa ve model ağır basıyorsa onu referans al
			if (r.getScoreline() != null && !r.getScoreline().isBlank()) {
				bestScore = r.getScoreline();
			}
		}

		if (totW == 0)
			totW = 1;
		pH /= totW;
		pD /= totW;
		pA /= totW;
		pO /= totWOUBtts;
		pB /= totWOUBtts;

		// --- 1️⃣ Maç Sonucu Olasılığı ---
		double msMax = Math.max(pH, Math.max(pD, pA));
		String msPick = (msMax == pH) ? "MS1" : (msMax == pD ? "MSX" : "MS2");

		// --- 2️⃣ Alt/Üst Olasılığı ---
		double pUnder = 1.0 - pO;
		String ouPick = (pO > 0.55) ? "Üst" : (pUnder > 0.55 ? "Alt" : "");

		// --- 3️⃣ Var/Yok Olasılığı ---
		double pNoBtts = 1.0 - pB;
		String bttsPick = (pB > 0.55) ? "Var" : (pNoBtts > 0.55 ? "Yok" : "");

		// --- 4️⃣ En güçlü olasılığı seç (dinamik strateji) ---
		Map<String, Double> candidates = new LinkedHashMap<>();
		candidates.put(msPick, msMax);
		if (!ouPick.isEmpty())
			candidates.put(ouPick, Math.max(pO, pUnder));
		if (!bttsPick.isEmpty())
			candidates.put(bttsPick, Math.max(pB, pNoBtts));

		String finalPick = msPick;
		double finalConf = msMax;

		for (Map.Entry<String, Double> e : candidates.entrySet()) {
			if (e.getValue() > finalConf) {
				finalConf = e.getValue();
				finalPick = e.getKey();
			}
		}

		finalConf = Math.round(finalConf * 100.0) / 100.0;

		return new PredictionResult(name(), match.getHomeTeam(), match.getAwayTeam(), safe(pH), safe(pD), safe(pA),
				safe(pO), safe(pB), finalPick, finalConf, bestScore);
	}

	private double safe(Double v) {
		if (v == null || Double.isNaN(v) || v < 0 || v > 1)
			return 0.33;
		return v;
	}
}
