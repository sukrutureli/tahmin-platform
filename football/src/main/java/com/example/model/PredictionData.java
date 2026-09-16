package com.example.model;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class PredictionData {

	private String homeTeam;
	private String awayTeam;
	private List<String> picks; // Birden fazla tahmin (ör. MS1, ÜST)
	private String score; // "2-1" gibi skor
	private Map<String, String> statuses; // Her pick için durum: "won", "lost", "pending"

	public PredictionData() {

	}

	public PredictionData(String homeTeam, String awayTeam, List<String> picks) {
		this.homeTeam = homeTeam;
		this.awayTeam = awayTeam;
		this.picks = picks;
		this.statuses = new HashMap<String, String>();
		this.score = "-";
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

	public List<String> getPicks() {
		return picks;
	}

	public void setPicks(List<String> picks) {
		this.picks = picks;
	}

	public String getScore() {
		return score;
	}

	public void setScore(String score) {
		this.score = score;
	}

	public Map<String, String> getStatuses() {
		return statuses;
	}

	public void setStatuses(Map<String, String> statuses) {
		this.statuses = statuses;
	}

	@Override
	public String toString() {
		return homeTeam + " vs " + awayTeam + " -> " + picks + " | Score: " + score + " | Status: " + statuses;
	}
}
