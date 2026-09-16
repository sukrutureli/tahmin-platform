package com.basketbol.model;

import com.fasterxml.jackson.annotation.JsonIgnore;

public class MatchResult {
	private String homeTeam;
	private String awayTeam;
	private int homeScore;
	private int awayScore;
	private String matchDate;
	private String tournament;
	private String matchType; // "rekabet-gecmisi" veya "son-maclar"
	
	public MatchResult() {
		
	}

	public MatchResult(String homeTeam, String awayTeam, int homeScore, int awayScore, String matchDate,
			String tournament, String matchType) {
		this.homeTeam = homeTeam;
		this.awayTeam = awayTeam;
		this.homeScore = homeScore;
		this.awayScore = awayScore;
		this.matchDate = matchDate;
		this.tournament = tournament;
		this.matchType = matchType;
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

	public int getHomeScore() {
		return homeScore;
	}

	public void setHomeScore(int homeScore) {
		this.homeScore = homeScore;
	}

	public int getAwayScore() {
		return awayScore;
	}

	public void setAwayScore(int awayScore) {
		this.awayScore = awayScore;
	}

	public String getMatchDate() {
		return matchDate;
	}

	public void setMatchDate(String matchDate) {
		this.matchDate = matchDate;
	}

	public String getTournament() {
		return tournament;
	}

	public void setTournament(String tournament) {
		this.tournament = tournament;
	}

	public String getMatchType() {
		return matchType;
	}

	public void setMatchType(String matchType) {
		this.matchType = matchType;
	}

	@JsonIgnore
	public String getResult() {
		if (homeScore > awayScore)
			return "H"; // Home win
		if (awayScore > homeScore)
			return "A"; // Away win
		return "D"; // Draw
	}

	@JsonIgnore
	public String getScoreString() {
		return homeScore + "-" + awayScore;
	}
}
