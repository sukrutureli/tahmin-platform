package com.example.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class TeamStats {

	private String teamName;

	// Takımın genel ortalamaları
	private double avgGF; // ortalama atılan gol
	private double avgGA; // ortalama yenilen gol
	private double rating100; // 0–100 arası güç endeksi

	// Form bilgileri
	private double last5Points; // son 5 maçtan topladığı puan (maks 15)
	private int last5Count; // gerçekten kaç maç oynandı (örneğin 4/5)

	// Rekabet (H2H) bilgileri
	private int h2hWins; // bu rakibe karşı kazanılan maç sayısı
	private int h2hCount; // bu rakibe karşı toplam maç sayısı
	private double h2hWinRate;
	private double avgPointsPerMatch;

	// ----- Constructor -----
	public TeamStats() {
	}

	public TeamStats(String teamName) {
		this.teamName = teamName;
	}

	// ----- Genel Get/Set -----
	public String getTeamName() {
		return teamName == null ? "" : teamName;
	}

	public void setTeamName(String name) {
		this.teamName = name;
	}

	public double getAvgGF() {
		return safe(avgGF);
	}

	public void setAvgGF(double v) {
		this.avgGF = v;
	}

	public double getAvgGA() {
		return safe(avgGA);
	}

	public void setAvgGA(double v) {
		this.avgGA = v;
	}

	public double getRating100() {
		return safe(rating100);
	}

	public void setRating100(double v) {
		this.rating100 = v;
	}

	public double getLast5Points() {
		return safe(last5Points);
	}

	public void setLast5Points(double v) {
		this.last5Points = v;
	}

	public int getLast5Count() {
		// manuel atanmışsa onu döndür, değilse son maç listesinden hesapla
		if (last5Count > 0)
			return last5Count;
		return 0;
	}

	public void setLast5Count(int c) {
		this.last5Count = c;
	}

	public int getH2hWins() {
		return h2hWins;
	}

	public void setH2hWins(int v) {
		this.h2hWins = v;
	}

	public int getH2hCount() {
		return h2hCount;
	}

	public void setH2hCount(int v) {
		this.h2hCount = v;
	}

	// ----- Derived or Safe Methods -----

	public double getH2hWinRate() {
		return h2hWinRate;
	}

	public double getAvgPointsPerMatch() {
		return avgPointsPerMatch;
	}

	/**
	 * Takım verisi eksik veya anlamsız mı? Eğer hem goller hem form hem rating
	 * sıfırsa 'boş' kabul edilir.
	 */
	public boolean isEmpty() {
		boolean noGoals = avgGF == 0 && avgGA == 0;
		boolean noForm = getLast5Count() == 0;
		boolean noRating = rating100 == 0;
		return noGoals && noForm && noRating;
	}

	/**
	 * Takımın ortalama puanını (puan / maç) verir.
	 */
	public void calculateAvgPointsPerMatch() {
		avgPointsPerMatch = safeDiv(last5Points, Math.max(1, getLast5Count()));
	}

	/**
	 * Head-to-head kazanma oranı.
	 */
	public void calculateH2hWinRate() {
		h2hWinRate = safeDiv(h2hWins, Math.max(1, h2hCount));
	}

	/**
	 * NaN / ∞ / negatif değerleri normalize eder
	 */
	private double safe(double v) {
		if (Double.isNaN(v) || Double.isInfinite(v))
			return 0;
		return Math.max(0, v);
	}

	private double safeDiv(double a, double b) {
		return (b == 0) ? 0 : a / b;
	}

	@Override
	public String toString() {
		return String.format("TeamStats[%s | GF=%.2f, GA=%.2f, Rating=%.1f, Form=%.1f/%d, H2H=%d/%d]", getTeamName(),
				getAvgGF(), getAvgGA(), getRating100(), getLast5Points(), getLast5Count(), getH2hWins(), getH2hCount());
	}
}
