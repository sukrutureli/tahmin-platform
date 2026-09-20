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
        double pH = 0, pD = 0, pA = 0;
        double pO = 0, pB = 0;
        double totalMsWeight = 0, totalGoalWeight = 0;
        double bestScoreWeight = -1;
        String bestScore = "";

        for (BettingAlgorithm model : models) {
            PredictionResult result = model.predict(match, odds);
            if (result == null) continue;

            double msWeight = model.weight()[0];
            double goalWeight = model.weight()[1];
            if (msWeight > 0) {
                pH += msWeight * safe(result.getpHome());
                pD += msWeight * safe(result.getpDraw());
                pA += msWeight * safe(result.getpAway());
                totalMsWeight += msWeight;
            }
            if (goalWeight > 0) {
                pO += goalWeight * safe(result.getpOver25());
                pB += goalWeight * safe(result.getpBttsYes());
                totalGoalWeight += goalWeight;
            }
            // A scoreline is an illustration of the goal model, not independent evidence.
            if (goalWeight > bestScoreWeight && result.getScoreline() != null
                    && !result.getScoreline().isBlank()) {
                bestScoreWeight = goalWeight;
                bestScore = result.getScoreline();
            }
        }

        if (totalMsWeight > 0) {
            pH /= totalMsWeight;
            pD /= totalMsWeight;
            pA /= totalMsWeight;
        } else {
            pH = 0.33;
            pD = 0.34;
            pA = 0.33;
        }
        if (totalGoalWeight > 0) {
            pO /= totalGoalWeight;
            pB /= totalGoalWeight;
        } else {
            pO = 0.50;
            pB = 0.50;
        }

        double msMax = Math.max(pH, Math.max(pD, pA));
        String msPick = msMax == pH ? "MS1" : (msMax == pD ? "MSX" : "MS2");
        double pUnder = 1.0 - pO;
        String ouPick = pO > 0.55 ? "Üst" : (pUnder > 0.55 ? "Alt" : "");
        double pNoBtts = 1.0 - pB;
        String bttsPick = pB > 0.55 ? "Var" : (pNoBtts > 0.55 ? "Yok" : "");

        Map<String, Double> candidates = new LinkedHashMap<>();
        candidates.put(msPick, msMax);
        if (!ouPick.isEmpty()) candidates.put(ouPick, Math.max(pO, pUnder));
        if (!bttsPick.isEmpty()) candidates.put(bttsPick, Math.max(pB, pNoBtts));

        String finalPick = msPick;
        double finalConf = msMax;
        for (Map.Entry<String, Double> candidate : candidates.entrySet()) {
            if (candidate.getValue() > finalConf) {
                finalConf = candidate.getValue();
                finalPick = candidate.getKey();
            }
        }
        finalConf = Math.round(finalConf * 100.0) / 100.0;
        return new PredictionResult(name(), match.getHomeTeam(), match.getAwayTeam(),
                safe(pH), safe(pD), safe(pA), safe(pO), safe(pB), finalPick, finalConf, bestScore);
    }

    private double safe(Double value) {
        if (value == null || !Double.isFinite(value) || value < 0 || value > 1) return 0.33;
        return value;
    }
}
