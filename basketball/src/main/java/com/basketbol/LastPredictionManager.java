package com.basketbol;

import com.basketbol.util.FixtureIdentity;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

import com.basketbol.model.LastPrediction;
import com.basketbol.model.MatchInfo;
import com.basketbol.model.PredictionResult;
import com.basketbol.model.TeamMatchHistory;
import com.basketbol.util.MathUtils;
import com.basketbol.model.PredictionData;

public class LastPredictionManager {
	private List<LastPrediction> lastPrediction;
	private MatchHistoryManager historyManager;
	private List<PredictionResult> predictionResults;
	private List<MatchInfo> matchInfo;
	private List<PredictionData> predictionData;

	public LastPredictionManager(MatchHistoryManager historyManager, List<PredictionResult> predictionResults,
			List<MatchInfo> matchInfo) {
		this.lastPrediction = new ArrayList<LastPrediction>();
		this.historyManager = historyManager;
		this.predictionResults = predictionResults;
		this.matchInfo = matchInfo;
		this.predictionData = new ArrayList<PredictionData>();
	}

	public void fillPredictions() {
		for (MatchInfo info : matchInfo) {
			TeamMatchHistory th = FixtureIdentity.historyFor(info, historyManager.getTeamHistories());
			PredictionResult prediction = FixtureIdentity.resultFor(info, historyManager.getTeamHistories(), predictionResults);
			if (th == null || prediction == null) continue;

			LastPrediction tempLastPrediction = new LastPrediction(info.getName(), info.getTime());

			tempLastPrediction.setEventId(FixtureIdentity.eventId(info.getDetailUrl()));
			tempLastPrediction.setScore(prediction.getScoreline());

			List<String> tahminList = calculatePrediction(th, prediction, info, prediction.getPick());

			for (String s : tahminList) {
				String t = s;
				if (!s.startsWith("MS")) {
					t = info.getOdds().gethOverUnderValue() + " " + s;
				}
				String withOdd = t + getOddsAndPercentage(s, info, prediction);
				tempLastPrediction.getPredictions().add(withOdd);
			}

			if (!tempLastPrediction.getPredictions().isEmpty()) {
				lastPrediction.add(tempLastPrediction);

				String homeTeam = tempLastPrediction.getName().split(" - ", 2)[0].trim();
				String awayTeam = tempLastPrediction.getName().split(" - ", 2)[1].trim();
				PredictionData tempPredictionData = new PredictionData(homeTeam, awayTeam,
						tempLastPrediction.getPredictions());
				tempPredictionData.setEventId(tempLastPrediction.getEventId());
				predictionData.add(tempPredictionData);
				predictionData.get(predictionData.size() - 1).getStatuses()
						.put(tempLastPrediction.getPredictions().get(0), "pending");
			}
		}
	}

	private List<String> calculatePrediction(TeamMatchHistory h, PredictionResult pr, MatchInfo matchInfo,
			String tahmin) {
		String[] tahminler = tahmin.split(" | ");
		List<String> resultList = new ArrayList<String>();

		if (!h.isInfoEnough() && !h.isInfoEnoughWithoutRekabet()) {
			return resultList;
		}
		for (String t : tahminler) {

			if (t.equals("MS1")) {
				if (matchInfo.getOdds().getMs1() > 1.29 && matchInfo.getOdds().getMs1() < 1.9 && h.getMax().equals(t)
						&& isScoreOk(pr.getScoreline(), t, matchInfo)) {
					if (pr.getpHome() > pr.getpAway()) {
						resultList.add(t);
					}
				}
			} else if (t.equals("MS2")) {
				if (matchInfo.getOdds().getMs2() > 1.29 && matchInfo.getOdds().getMs2() < 1.9 && h.getMax().equals(t)
						&& isScoreOk(pr.getScoreline(), t, matchInfo)) {
					if (pr.getpHome() < pr.getpAway()) {
						resultList.add(t);
					}
				}
			} else if (t.equals("Üst")) {
				if (matchInfo.getOdds().getOver() > 1.0 && h.getMax().equals(t)
						&& isScoreOk(pr.getScoreline(), t, matchInfo)) {
					if (pr.getpOver25() > 0.5) {
						resultList.add(t);
					}
				}
			} else if (t.equals("Alt")) {
				if (matchInfo.getOdds().getUnder() > 1.0 && h.getMax().equals(t)
						&& isScoreOk(pr.getScoreline(), t, matchInfo)) {
					if (pr.getpOver25() < 0.5) {
						resultList.add(t);
					}
				}
			}
		}

		return resultList;
	}

	private boolean isScoreOk(String score, String tahmin, MatchInfo match) {
		String[] splitScore = score.split("-");
		int home = Integer.valueOf(splitScore[0].trim());
		int away = Integer.valueOf(splitScore[1].trim());

		if (tahmin.equals("MS1") && home > away) {
			return true;
		} else if (tahmin.equals("MS2") && home < away) {
			return true;
		} else if (tahmin.equals("Alt") && (home + away) < match.getOdds().gethOverUnderValue()) {
			return true;
		} else if (tahmin.equals("Üst") && (home + away) > match.getOdds().gethOverUnderValue()) {
			return true;
		} else {
			return false;
		}
	}

	private String getOddsAndPercentage(String tahmin, MatchInfo match, PredictionResult pr) {
		if (tahmin.equals("MS1")) {
			return String.format(" (%s - %s)", String.valueOf(match.getOdds().getMs1()),
					MathUtils.fmtPct(pr.getpHome()));
		} else if (tahmin.equals("MS2")) {
			return String.format(" (%s - %s)", String.valueOf(match.getOdds().getMs2()),
					MathUtils.fmtPct(pr.getpAway()));
		} else if (tahmin.equals("Alt")) {
			return String.format(" (%s - %s)", String.valueOf(match.getOdds().getUnder()),
					MathUtils.fmtPct(1 - pr.getpOver25()));
		} else if (tahmin.equals("Üst")) {
			return String.format(" (%s - %s)", String.valueOf(match.getOdds().getOver()),
					MathUtils.fmtPct(pr.getpOver25()));
		}
		return null;
	}

	public List<LastPrediction> getLastPrediction() {
		return lastPrediction;
	}

	public List<PredictionData> getPredictionData() {
		return predictionData;
	}
}

