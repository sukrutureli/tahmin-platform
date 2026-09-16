package com.example.model;

public class Match {
	private String homeTeam;
	private String awayTeam;
	private TeamStats homeStats;
	private TeamStats awayStats;
	private Odds odds; // soccerstats’tan gelmez; sonra Nesine/Mackolik ile besleriz
	
	public Match() {
		
	}

	public Match(String homeTeam, String awayTeam) {
		this.homeTeam = homeTeam;
		this.awayTeam = awayTeam;
	}

	// --- getters / setters ---
	public String getHomeTeam() {
		return homeTeam;
	}

	public String getAwayTeam() {
		return awayTeam;
	}

	public TeamStats getHomeStats() {
		return homeStats;
	}

	public void setHomeStats(TeamStats homeStats) {
		this.homeStats = homeStats;
	}

	public TeamStats getAwayStats() {
		return awayStats;
	}

	public void setAwayStats(TeamStats awayStats) {
		this.awayStats = awayStats;
	}

	public Odds getOdds() {
		return odds;
	}

	public void setOdds(Odds odds) {
		this.odds = odds;
	}

	@Override
	public String toString() {
		return homeTeam + " - " + awayTeam + " -> \n" + homeStats.toString() + "\n" + awayStats.toString();
	}

}
