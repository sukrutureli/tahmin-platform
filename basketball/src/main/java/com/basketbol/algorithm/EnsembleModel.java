package com.basketbol.algorithm;

import com.basketbol.model.*;
import java.util.*;

public class EnsembleModel implements BettingAlgorithm {
	private final List<BettingAlgorithm> models;

	public EnsembleModel(List<BettingAlgorithm> models) {
		this.models = models;
	}

	@Override
	public String name() {
		return "BasketEnsembleModel";
	}

	@Override
	public double weight() {
		return 1.0;
	}

	@Override
	public PredictionResult predict(Match match, Optional<Odds> odds) {
		double pHome = 0, pAway = 0, pOver = 0;
		double totalW = 0;
		double confSum = 0;
		double homeScore = 0;
		double awayScore = 0;

		for (BettingAlgorithm m : models) {
			PredictionResult r = m.predict(match, odds);
			if (r == null)
				continue;
			double w = m.weight();
			pHome += w * safe(r.getpHome());
			pAway += w * safe(r.getpAway());
			pOver += w * safe(r.getpOver25());
			confSum += w * r.getConfidence();

			if (!r.getScoreline().equals("-")) {
				String[] scores = r.getScoreline().split("-");
				homeScore += (w * Integer.valueOf(scores[0]));
				awayScore += (w * Integer.valueOf(scores[1]));
			}

			System.out.println(m.name() + "->" + r.getPick());
			totalW += w;
		}

		if (totalW == 0)
			totalW = 1;
		pHome /= totalW;
		pAway /= totalW;
		pOver /= totalW;
		homeScore /= totalW;
		awayScore /= totalW;
		String score = Math.round(homeScore) + "-" + Math.round(awayScore);

		String msPick = (pHome > 0.55) ? "MS1" : (pAway > 0.55 ? "MS2" : "Yakın");
		String ouPick = (pOver > 0.55) ? "Üst" : (pOver < 0.45 ? "Alt" : "Sınırda");
		double conf = Math.min(1.0, confSum / totalW);

		String finalPick = msPick + " | " + ouPick;

		return new PredictionResult(name(), match.getHomeTeam(), match.getAwayTeam(), pHome, 0, pAway, pOver, 0,
				finalPick, conf, score);
	}

	private double safe(double v) {
		return Double.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0.5;
	}
}
