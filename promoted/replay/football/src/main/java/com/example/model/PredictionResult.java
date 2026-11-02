package com.example.model;

public class PredictionResult {
	private String algorithm;
	private String homeTeam;
	private String awayTeam;

	private double pHome;
	private double pDraw;
	private double pAway;

	private double pOver25;
	private double pBttsYes;

	private String pick; // "MS1", "MS2", "X", "ALT", "UST", "VAR", "YOK" vb.
	private double confidence; // 0-1
	private String scoreline; // en olası skor (ör. 2-1)

	public PredictionResult() {

	}

	public PredictionResult(String algorithm, String homeTeam, String awayTeam, double pHome, double pDraw,
			double pAway, double pOver25, double pBttsYes, String pick, double confidence, String scoreline) {
		this.algorithm = algorithm;
		this.homeTeam = homeTeam;
		this.awayTeam = awayTeam;
		this.pHome = pHome;
		this.pDraw = pDraw;
		this.pAway = pAway;
		this.pOver25 = pOver25;
		this.pBttsYes = pBttsYes;
		this.pick = pick;
		this.confidence = confidence;
		this.scoreline = scoreline;
	}

	public String getAlgorithm() {
		return algorithm;
	}

	public String getHomeTeam() {
		return homeTeam;
	}

	public String getAwayTeam() {
		return awayTeam;
	}

	public double getpHome() {
		return pHome;
	}

	public double getpDraw() {
		return pDraw;
	}

	public double getpAway() {
		return pAway;
	}

	public double getpOver25() {
		return pOver25;
	}

	public double getpBttsYes() {
		return pBttsYes;
	}

	public String getPick() {
		return pick;
	}

	public double getConfidence() {
		return confidence;
	}

	public String getScoreline() {
		return scoreline;
	}

	public PredictionResult withAlgorithm(String algo) {
		return new PredictionResult(algo, homeTeam, awayTeam, pHome, pDraw, pAway, pOver25, pBttsYes, pick, confidence,
				scoreline);
	}
}
