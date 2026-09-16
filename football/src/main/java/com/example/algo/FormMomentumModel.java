package com.example.algo;

import java.util.*;
import com.example.model.*;

public class FormMomentumModel implements BettingAlgorithm {
	@Override
	public String name() {
		return "FormMomentumModel";
	}

	@Override
	public double[] weight() {
		return new double[] { 0.3, 0.0 }; // MS etkisi var, Alt/Üst yok
	}

	@Override
	public PredictionResult predict(Match match, Optional<Odds> oddsOpt) {
		TeamStats h = match.getHomeStats();
		TeamStats a = match.getAwayStats();

		if (h == null || a == null || h.isEmpty() || a.isEmpty())
			return neutralResult(match);

		double homeForm = h.getAvgPointsPerMatch();
		double awayForm = a.getAvgPointsPerMatch();

		// normalize 0–1 arası (puan/maç => 0–3)
		homeForm /= 3.0;
		awayForm /= 3.0;

		double momentum = homeForm - awayForm; // -1 .. +1 arası

		// logit dönüşümüyle MS1 eğilimi
		double k = 3.5; // momentum duyarlılığı
		double pHome = 1.0 / (1.0 + Math.exp(-k * momentum));
		double pAway = 1.0 - pHome;

		// dinamik beraberlik
		double pDraw = 0.25 - 0.15 * Math.abs(pHome - pAway);
		pDraw = Math.max(0.10, Math.min(pDraw, 0.30));

		// normalize
		double sum = pHome + pDraw + pAway;
		pHome /= sum;
		pDraw /= sum;
		pAway /= sum;

		// piyasa karışımı (küçük, 0.1 yeterli)
		if (oddsOpt.isPresent()) {
			Odds odds = oddsOpt.get();
			double sH = 1.0 / odds.getMs1();
			double sD = 1.0 / odds.getMsX();
			double sA = 1.0 / odds.getMs2();
			double R = sH + sD + sA;
			double mH = sH / R, mD = sD / R, mA = sA / R;
			double w = 0.10;
			pHome = (1 - w) * pHome + w * mH;
			pDraw = (1 - w) * pDraw + w * mD;
			pAway = (1 - w) * pAway + w * mA;
		}

		String pick;
		if (pHome > pDraw && pHome > pAway)
			pick = "MS1";
		else if (pAway > pHome && pAway > pDraw)
			pick = "MS2";
		else
			pick = "MS0";

		double conf = Math.max(Math.max(pHome, pDraw), pAway);

		return new PredictionResult(name(), match.getHomeTeam(), match.getAwayTeam(), clamp(pHome), clamp(pDraw),
				clamp(pAway), 0.5, 0.5, pick, conf, "");
	}

	private double clamp(double v) {
		return Math.max(0.01, Math.min(0.99, v));
	}

	private PredictionResult neutralResult(Match m) {
		return new PredictionResult(name(), m.getHomeTeam(), m.getAwayTeam(), 0.33, 0.34, 0.33, 0.50, 0.50, "MSX", 0.33,
				"");
	}
}
