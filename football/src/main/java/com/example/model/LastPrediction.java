package com.example.model;

import java.util.ArrayList;
import java.util.List;

public class LastPrediction {
	private String name;
	private String time;
	private List<String> predictions;
	private String score;
	private int mbs;
	
	public LastPrediction() {
		
	}

	public LastPrediction(String name, String time) {
		this.name = name;
		this.time = time;
		this.predictions = new ArrayList<String>();
	}

	public List<String> getPredictions() {
		return predictions;
	}

	public void setPredictions(List<String> predictions) {
		this.predictions = predictions;
	}

	public String preditionsToString() {
		String result = "";

		for (String s : predictions) {
			if (result.equals("")) {
				result += s;
			} else {
				result += " | " + s;
			}
		}

		return result;
	}

	public String getName() {
		return name;
	}

	public String getTime() {
		return time;
	}

	public String getScore() {
		return score;
	}

	public void setScore(String score) {
		this.score = score;
	}

	public int getMbs() {
		return mbs;
	}

	public void setMbs(int mbs) {
		this.mbs = mbs;
	}
}
