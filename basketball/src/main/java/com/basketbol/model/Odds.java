package com.basketbol.model;

public class Odds {
	private Double ms1;
	private Double ms2;
	private Double h1Value;
	private Double h2Value;
	private Double h1;
	private Double h2;
	private Double hOverUnderValue;
	private Double over;
	private Double under;
	
	public Odds() {
		
	}

	public Odds(Double ms1, Double ms2, Double h1Value, Double h1, Double h2, Double h2Value, Double under,
			Double hOverUnderValue, Double over) {
		this.ms1 = ms1;
		this.ms2 = ms2;
		this.h1Value = h1Value;
		this.h2Value = h2Value;
		this.h1 = h1;
		this.h2 = h2;
		this.hOverUnderValue = hOverUnderValue;
		this.over = over;
		this.under = under;
	}

	public Double getMs1() {
		return ms1;
	}

	public void setMs1(Double ms1) {
		this.ms1 = ms1;
	}

	public Double getMs2() {
		return ms2;
	}

	public void setMs2(Double ms2) {
		this.ms2 = ms2;
	}

	public Double getH1Value() {
		return h1Value;
	}

	public void setH1Value(Double h1Value) {
		this.h1Value = h1Value;
	}

	public Double getH2Value() {
		return h2Value;
	}

	public void setH2Value(Double h2Value) {
		this.h2Value = h2Value;
	}

	public Double getH1() {
		return h1;
	}

	public void setH1(Double h1) {
		this.h1 = h1;
	}

	public Double getH2() {
		return h2;
	}

	public void setH2(Double h2) {
		this.h2 = h2;
	}

	public Double gethOverUnderValue() {
		return hOverUnderValue;
	}

	public void sethOverUnderValue(Double hOverUnderValue) {
		this.hOverUnderValue = hOverUnderValue;
	}

	public Double getOver() {
		return over;
	}

	public void setOver(Double over) {
		this.over = over;
	}

	public Double getUnder() {
		return under;
	}

	public void setUnder(Double under) {
		this.under = under;
	}

}
