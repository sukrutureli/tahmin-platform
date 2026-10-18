package com.basketbol.model;

public class MatchInfo {
	private String name;
	private String time;
	private String detailUrl;
	private Odds odds;
	private int index;
	private Integer mbs;
	
	public MatchInfo() {
		
	}

	public MatchInfo(String name, String time, String detailUrl, Odds odds, int index) {
		this.setName(name);
		this.time = time;
		this.detailUrl = detailUrl;
		this.odds = odds;
		this.mbs = odds == null ? null : odds.getMbs();
		this.index = index;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public String getTime() {
		return time;
	}

	public void setTime(String time) {
		this.time = time;
	}

	public String getDetailUrl() {
		return detailUrl;
	}

	public void setDetailUrl(String detailUrl) {
		this.detailUrl = detailUrl;
	}

	public Odds getOdds() {
		return odds;
	}

	public void setOdds(Odds odds) {
		this.odds = odds;
	}

	public int getIndex() {
		return index;
	}

	public void setIndex(int index) {
		this.index = index;
	}


	public Integer getMbs() {
		return mbs != null ? mbs : odds == null ? null : odds.getMbs();
	}

	public void setMbs(Integer mbs) {
		this.mbs = mbs != null && mbs > 0 ? mbs : null;
	}

	public boolean hasDetailUrl() {
		return detailUrl != null && !detailUrl.isEmpty() && detailUrl.contains("istatistik.nesine.com");
	}

}
