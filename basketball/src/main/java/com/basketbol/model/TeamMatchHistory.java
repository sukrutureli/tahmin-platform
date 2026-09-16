package com.basketbol.model;

import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public class TeamMatchHistory {
	private String teamName;
	private String teamEv;
	private String teamDep;
	private String detailUrl;
	private Odds odds;
	private List<MatchResult> rekabetGecmisi;
	private List<MatchResult> sonMaclarHome;
	private List<MatchResult> sonMaclarAway;

	public TeamMatchHistory() {

	}

	public TeamMatchHistory(String teamName, String teamEv, String teamDep, String detailUrl, Odds odds) {
		this.teamName = teamName;
		this.teamEv = teamEv;
		this.teamDep = teamDep;
		this.setDetailUrl(detailUrl);
		this.rekabetGecmisi = new ArrayList<>();
		this.sonMaclarHome = new ArrayList<>();
		this.sonMaclarAway = new ArrayList<>();
		this.odds = odds;
	}

	// Add methods
	public void addRekabetGecmisiMatch(MatchResult match) {
		rekabetGecmisi.add(match);
	}

	public void addSonMacMatch(MatchResult match, int homeOrAway) {
		if (homeOrAway == 1) {
			sonMaclarHome.add(match);
		} else if (homeOrAway == 2) {
			sonMaclarAway.add(match);
		}
	}

	// Utility methods
	public int getTotalMatches() {
		return rekabetGecmisi.size() + sonMaclarHome.size() + sonMaclarAway.size();
	}

	@JsonIgnore
	public List<MatchResult> getAllMatches() {
		List<MatchResult> allMatches = new ArrayList<>();
		allMatches.addAll(rekabetGecmisi);
		allMatches.addAll(sonMaclarHome);
		allMatches.addAll(sonMaclarAway);
		return allMatches;
	}

	public String getTeamName() {
		return teamName;
	}

	public void setTeamName(String teamName) {
		this.teamName = teamName;
	}

	public String getTeamEv() {
		return teamEv;
	}

	public void setTeamEv(String teamEv) {
		this.teamEv = teamEv;
	}

	public String getTeamDep() {
		return teamDep;
	}

	public void setTeamDep(String teamDep) {
		this.teamDep = teamDep;
	}

	public List<MatchResult> getRekabetGecmisi() {
		return rekabetGecmisi;
	}

	public void setRekabetGecmisi(List<MatchResult> rekabetGecmisi) {
		this.rekabetGecmisi = rekabetGecmisi;
	}

	public List<MatchResult> getSonMaclarHome() {
		return sonMaclarHome;
	}

	public void setSonMaclarHome(List<MatchResult> sonMaclarHome) {
		this.sonMaclarHome = sonMaclarHome;
	}

	public List<MatchResult> getSonMaclarAway() {
		return sonMaclarAway;
	}

	public void setSonMaclarAway(List<MatchResult> sonMaclarAway) {
		this.sonMaclarAway = sonMaclarAway;
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

	public double getMs1() {
		double ms1Rekabet = 0;
		double ms1SonH = 0;
		double ms1SonA = 0;

		for (int i = 0; i < rekabetGecmisi.size(); i++) {
			if (rekabetGecmisi.get(i).getHomeTeam().contains(teamEv) && rekabetGecmisi.get(i).getResult() == "H") {
				ms1Rekabet++;
			} else if (rekabetGecmisi.get(i).getAwayTeam().contains(teamEv)
					&& rekabetGecmisi.get(i).getResult() == "A") {
				ms1Rekabet++;
			}
		}

		for (int i = 0; i < sonMaclarHome.size(); i++) {
			if (sonMaclarHome.get(i).getHomeTeam().contains(teamEv) && sonMaclarHome.get(i).getResult() == "H") {
				ms1SonH++;
			} else if (sonMaclarHome.get(i).getAwayTeam().contains(teamEv) && sonMaclarHome.get(i).getResult() == "A") {
				ms1SonH++;
			}
		}

		for (int i = 0; i < sonMaclarAway.size(); i++) {
			if (sonMaclarAway.get(i).getHomeTeam().contains(teamDep) && sonMaclarAway.get(i).getResult() == "A") {
				ms1SonA++;
			} else if (sonMaclarAway.get(i).getAwayTeam().contains(teamDep)
					&& sonMaclarAway.get(i).getResult() == "H") {
				ms1SonA++;
			}
		}

		if (isInfoEnough()) {
			double result = (ms1Rekabet / rekabetGecmisi.size()) * 0.1;
			result += ((ms1SonH / sonMaclarHome.size()) * 0.45);
			result += ((ms1SonA / sonMaclarAway.size()) * 0.45);

			return result;
		} else if (isInfoEnoughWithoutRekabet()) {
			double result = ((ms1SonH / sonMaclarHome.size()) * 0.5);
			result += ((ms1SonA / sonMaclarAway.size()) * 0.5);

			return result;
		} else {
			return (ms1Rekabet + ms1SonH + ms1SonA) / getTotalMatches();
		}
	}

	public double getMs2() {
		double ms2Rekabet = 0;
		double ms2SonH = 0;
		double ms2SonA = 0;

		for (int i = 0; i < rekabetGecmisi.size(); i++) {
			if (rekabetGecmisi.get(i).getHomeTeam().contains(teamDep) && rekabetGecmisi.get(i).getResult() == "H") {
				ms2Rekabet++;
			} else if (rekabetGecmisi.get(i).getAwayTeam().contains(teamDep)
					&& rekabetGecmisi.get(i).getResult() == "A") {
				ms2Rekabet++;
			}
		}

		for (int i = 0; i < sonMaclarHome.size(); i++) {
			if (sonMaclarHome.get(i).getHomeTeam().contains(teamEv) && sonMaclarHome.get(i).getResult() == "A") {
				ms2SonH++;
			} else if (sonMaclarHome.get(i).getAwayTeam().contains(teamEv) && sonMaclarHome.get(i).getResult() == "H") {
				ms2SonH++;
			}
		}

		for (int i = 0; i < sonMaclarAway.size(); i++) {
			if (sonMaclarAway.get(i).getHomeTeam().contains(teamDep) && sonMaclarAway.get(i).getResult() == "H") {
				ms2SonA++;
			} else if (sonMaclarAway.get(i).getAwayTeam().contains(teamDep)
					&& sonMaclarAway.get(i).getResult() == "A") {
				ms2SonA++;
			}
		}

		if (isInfoEnough()) {
			double result = (ms2Rekabet / rekabetGecmisi.size()) * 0.1;
			result += ((ms2SonH / sonMaclarHome.size()) * 0.45);
			result += ((ms2SonA / sonMaclarAway.size()) * 0.45);

			return result;
		} else if (isInfoEnoughWithoutRekabet()) {
			double result = ((ms2SonH / sonMaclarHome.size()) * 0.5);
			result += ((ms2SonA / sonMaclarAway.size()) * 0.5);

			return result;
		} else {
			return (ms2Rekabet + ms2SonH + ms2SonA) / getTotalMatches();
		}
	}

	public double getUst() {
		double ustRekabet = 0;
		double ustSonH = 0;
		double ustSonA = 0;

		for (int i = 0; i < rekabetGecmisi.size(); i++) {
			if ((rekabetGecmisi.get(i).getHomeScore() + rekabetGecmisi.get(i).getAwayScore()) > odds
					.gethOverUnderValue()) {
				ustRekabet++;
			}
		}

		for (int i = 0; i < sonMaclarHome.size(); i++) {
			if ((sonMaclarHome.get(i).getHomeScore() + sonMaclarHome.get(i).getAwayScore()) > odds
					.gethOverUnderValue()) {
				ustSonH++;
			}
		}

		for (int i = 0; i < sonMaclarAway.size(); i++) {
			if ((sonMaclarAway.get(i).getHomeScore() + sonMaclarAway.get(i).getAwayScore()) > odds
					.gethOverUnderValue()) {
				ustSonA++;
			}
		}

		if (isInfoEnough()) {
			double result = (ustRekabet / rekabetGecmisi.size()) * 0.1;
			result += ((ustSonH / sonMaclarHome.size()) * 0.45);
			result += ((ustSonA / sonMaclarAway.size()) * 0.45);

			return result;
		} else if (isInfoEnoughWithoutRekabet()) {
			double result = ((ustSonH / sonMaclarHome.size()) * 0.5);
			result += ((ustSonA / sonMaclarAway.size()) * 0.5);

			return result;
		} else {
			return (ustRekabet + ustSonH + ustSonA) / getTotalMatches();
		}
	}

	public double getAlt() {
		return 1 - getUst();
	}

	public boolean isInfoEnough() {
		if (sonMaclarHome.size() < 2 || sonMaclarAway.size() < 2 || rekabetGecmisi.size() < 2) {
			return false;
		}

		return true;
	}

	public boolean isInfoEnoughWithoutRekabet() {
		if (sonMaclarHome.size() > 1 && sonMaclarAway.size() > 1 && rekabetGecmisi.size() < 2) {
			return true;
		}

		return false;
	}

	public Match createStats(MatchInfo pMatch) {
		Match currentMatch = new Match(teamEv, teamDep);
		currentMatch.setOdds(pMatch.getOdds());

		BasketballStats homeStats = new BasketballStats(getForAgainstAndTotal(sonMaclarHome, teamEv)[0],
				getForAgainstAndTotal(sonMaclarHome, teamEv)[1], getForAgainstAndTotal(sonMaclarHome, teamEv)[2],
				getForAgainstAndTotal(sonMaclarHome, teamEv)[3]);

		BasketballStats awayStats = new BasketballStats(getForAgainstAndTotal(sonMaclarAway, teamDep)[0],
				getForAgainstAndTotal(sonMaclarAway, teamDep)[1], getForAgainstAndTotal(sonMaclarAway, teamDep)[2],
				getForAgainstAndTotal(sonMaclarAway, teamDep)[3]);

		currentMatch.setHomeStats(homeStats);
		currentMatch.setAwayStats(awayStats);

		currentMatch.setAvgPointsForHome(getForAgainstAndTotal(rekabetGecmisi, teamEv)[0]);
		currentMatch.setAvgPointsForAway(getForAgainstAndTotal(rekabetGecmisi, teamEv)[1]);
		currentMatch.setH2hAvgTotalPoints(getForAgainstAndTotal(rekabetGecmisi, teamEv)[2]);

		return currentMatch;
	}

	public double[] getForAgainstAndTotal(List<MatchResult> macResult, String teamName) {
		double[] points = { 0.0, 0.0, 0.0, 0.0 };

		int size = macResult.size();

		for (int i = 0; i < size; i++) {
			if (macResult.get(i).getHomeTeam().contains(teamName)) {
				points[0] += macResult.get(i).getHomeScore();
				points[1] += macResult.get(i).getAwayScore();
				if (macResult.get(i).getHomeScore() > macResult.get(i).getAwayScore()) {
					points[3] += 2;
				} else {
					points[3] += 1;
				}
			} else if (macResult.get(i).getAwayTeam().contains(teamName)) {
				points[1] += macResult.get(i).getHomeScore();
				points[0] += macResult.get(i).getAwayScore();
				if (macResult.get(i).getHomeScore() < macResult.get(i).getAwayScore()) {
					points[3] += 2;
				} else {
					points[3] += 1;
				}
			}
			points[2] = points[2] + macResult.get(i).getHomeScore() + macResult.get(i).getAwayScore();
		}

		if (size > 0) {
			points[0] /= size;
			points[1] /= size;
			points[2] /= size;
			points[3] /= size;
		}

		return points;
	}

	public String getMax() {
		String maxStr = "";
		double max = 0.0;

		if (getMs1() > max) {
			maxStr = "MS1";
			max = getMs1();
		}
		if (getMs2() > max) {
			maxStr = "MS2";
			max = getMs2();
		}
		if (getAlt() > max) {
			maxStr = "Alt";
			max = getAlt();
		}
		if (getUst() > max) {
			maxStr = "Üst";
			max = getUst();
		}

		return maxStr;
	}

	public String getStyle(String type, Double odd) {
		String color = "background-color:#e8fbe8; border:1px solid #6ecf6e;";

		if (!isInfoEnough() && !isInfoEnoughWithoutRekabet()) {
			return "";
		}
		if (odd > 1.0) {
			if (type.equals(getMax())) {
				return color;
			}
		}

		return "";
	}
}
