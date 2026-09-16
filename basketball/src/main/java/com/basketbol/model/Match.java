package com.basketbol.model;

public class Match {
	private String homeTeam;
	private String awayTeam;
	private BasketballStats homeStats;
	private BasketballStats awayStats;
	private Odds odds;

	private Double avgPointsForHome;
	private Double avgPointsForAway;
	private Double h2hAvgTotalPoints;
	
	public Match() {
		
	}

	public Match(String homeTeam, String awayTeam) {
		this.homeTeam = homeTeam;
		this.awayTeam = awayTeam;
	}

	public String getHomeTeam() {
		return homeTeam;
	}

	public void setHomeTeam(String homeTeam) {
		this.homeTeam = homeTeam;
	}

	public String getAwayTeam() {
		return awayTeam;
	}

	public void setAwayTeam(String awayTeam) {
		this.awayTeam = awayTeam;
	}

	public BasketballStats getHomeStats() {
		return homeStats;
	}

	public void setHomeStats(BasketballStats homeStats) {
		this.homeStats = homeStats;
	}

	public BasketballStats getAwayStats() {
		return awayStats;
	}

	public void setAwayStats(BasketballStats awayStats) {
		this.awayStats = awayStats;
	}

	public Double getAvgPointsForHome() {
		return avgPointsForHome;
	}

	public void setAvgPointsForHome(Double avgPointsForHome) {
		this.avgPointsForHome = avgPointsForHome;
	}

	public Double getAvgPointsForAway() {
		return avgPointsForAway;
	}

	public void setAvgPointsForAway(Double avgPointsForAway) {
		this.avgPointsForAway = avgPointsForAway;
	}

	public Double getH2hAvgTotalPoints() {
		return h2hAvgTotalPoints;
	}

	public void setH2hAvgTotalPoints(Double h2hAvgTotalPoints) {
		this.h2hAvgTotalPoints = h2hAvgTotalPoints;
	}

	public Odds getOdds() {
		return odds;
	}

	public void setOdds(Odds odds) {
		this.odds = odds;
	}
}
