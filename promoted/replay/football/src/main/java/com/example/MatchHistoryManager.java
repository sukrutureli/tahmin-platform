package com.example;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import com.example.model.MatchResult;
import com.example.model.TeamMatchHistory;

public class MatchHistoryManager {
	private List<TeamMatchHistory> teamHistories;
	private LocalDateTime createdAt;

	public MatchHistoryManager() {
		this.teamHistories = new ArrayList<>();
		this.createdAt = LocalDateTime.now();
	}

	public void addTeamHistory(TeamMatchHistory teamHistory) {
		teamHistories.add(teamHistory);
	}

	public List<TeamMatchHistory> getTeamHistories() {
		return teamHistories;
	}

	public TeamMatchHistory getTeamHistory(String teamName) {
		return teamHistories.stream().filter(th -> th.getTeamName().equals(teamName)).findFirst().orElse(null);
	}

	public int getTotalTeams() {
		return teamHistories.size();
	}

	public int getTotalMatches() {
		return teamHistories.stream().mapToInt(TeamMatchHistory::getTotalMatches).sum();
	}

	public List<MatchResult> getAllMatches() {
		List<MatchResult> allMatches = new ArrayList<>();
		for (TeamMatchHistory teamHistory : teamHistories) {
			allMatches.addAll(teamHistory.getAllMatches());
		}
		return allMatches;
	}

	// CSV export için
	public String toCsvString() {
		StringBuilder csv = new StringBuilder();
		csv.append("HomeTeam,AwayTeam,HomeScore,AwayScore,MatchDate,Tournament,MatchType,Result\n");

		for (MatchResult match : getAllMatches()) {
			csv.append(String.format("%s,%s,%d,%d,%s,%s,%s,%s\n", match.getHomeTeam(), match.getAwayTeam(),
					match.getHomeScore(), match.getAwayScore(), match.getMatchDate(), match.getTournament(),
					match.getMatchType(), match.getResult()));
		}

		return csv.toString();
	}

	@Override
	public String toString() {
		return String.format("MatchHistoryManager: %d takım, %d maç (Oluşturma: %s)", getTotalTeams(),
				getTotalMatches(), createdAt);
	}
}
