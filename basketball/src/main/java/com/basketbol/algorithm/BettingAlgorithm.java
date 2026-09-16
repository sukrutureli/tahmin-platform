package com.basketbol.algorithm;

import java.util.Optional;

import com.basketbol.model.Match;
import com.basketbol.model.Odds;
import com.basketbol.model.PredictionResult;

public interface BettingAlgorithm {
	String name();

	double weight();

	PredictionResult predict(Match match, Optional<Odds> odds);
}
