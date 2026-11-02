package com.example.experiment;

import com.example.algo.BettingAlgorithm;
import com.example.algo.FormMomentumModel;
import com.example.model.Match;
import com.example.model.Odds;
import com.example.model.PredictionResult;
import java.util.Optional;

/** Experimental odds guard: an incomplete three-way market has no usable market prior. */
public class ValidOddsFormModel implements BettingAlgorithm {
 private final FormMomentumModel delegate = new FormMomentumModel();
 public String name() { return "ValidOddsFormModel"; }
 public double[] weight() { return delegate.weight(); }
 private boolean valid(double price) { return Double.isFinite(price) && price > 1.0; }
 public PredictionResult predict(Match match, Optional<Odds> odds) {
  Optional<Odds> usable = odds.filter(o -> valid(o.getMs1()) && valid(o.getMsX()) && valid(o.getMs2()));
  return delegate.predict(match, usable);
 }
}
