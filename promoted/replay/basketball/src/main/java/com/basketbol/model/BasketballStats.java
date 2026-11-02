package com.basketbol.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class BasketballStats {
	private Double avgPointsFor;
	private Double avgPointsAgainst;
	private Double avgTotalPoints;
	private Double ppg;
	
	public BasketballStats() {
		
	}

	public BasketballStats(Double avgPointsFor, Double avgPointsAgainst, Double avgTotalPoints, Double ppg) {
		this.avgPointsFor = avgPointsFor;
		this.avgPointsAgainst = avgPointsAgainst;
		this.avgTotalPoints = avgTotalPoints;
		this.ppg = ppg;
	}

	public Double getAvgPointsFor() {
		return avgPointsFor;
	}

	public void setAvgPointsFor(Double avgPointsFor) {
		this.avgPointsFor = avgPointsFor;
	}

	public Double getAvgPointsAgainst() {
		return avgPointsAgainst;
	}

	public void setAvgPointsAgainst(Double avgPointsAgainst) {
		this.avgPointsAgainst = avgPointsAgainst;
	}

	public Double getAvgTotalPoints() {
		return avgTotalPoints;
	}

	public void setAvgTotalPoints(Double avgTotalPoints) {
		this.avgTotalPoints = avgTotalPoints;
	}

	public Double getPpg() {
		return ppg;
	}

	public boolean isEmpty() {
		boolean noGoals = avgPointsFor == 0 && avgPointsAgainst == 0;
		return noGoals;
	}

}
