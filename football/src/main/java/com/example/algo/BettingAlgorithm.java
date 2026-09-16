package com.example.algo;

import java.util.Optional;

import com.example.model.Match;
import com.example.model.Odds;
import com.example.model.PredictionResult;

public interface BettingAlgorithm {
	String name();

	double[] weight();

	PredictionResult predict(Match match, Optional<Odds> odds);
}
