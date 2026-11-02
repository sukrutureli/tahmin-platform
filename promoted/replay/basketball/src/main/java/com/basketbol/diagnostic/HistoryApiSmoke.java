package com.basketbol.diagnostic;

import com.basketbol.model.TeamMatchHistory;
import com.basketbol.model.MatchResult;
import com.basketbol.scraper.BasketballScraper;

public final class HistoryApiSmoke {
    public static void main(String[] args) {
        BasketballScraper scraper = new BasketballScraper();
        try {
            TeamMatchHistory history = scraper.scrapeTeamHistory(
                    "https://istatistik.nesine.com/3226161",
                    "Leones Quilpue - CD Universidad De Concepcion", null);
            if (history == null || history.getRekabetGecmisi().size() != 6
                    || history.getSonMaclarHome().size() != 6
                    || history.getSonMaclarAway().size() != 6) {
                throw new AssertionError("Basketball history count mismatch");
            }
            boolean overtimeFinalFound = false;
            for (MatchResult match : history.getSonMaclarAway()) {
                if (match.getHomeScore() == 96 && match.getAwayScore() == 97) {
                    overtimeFinalFound = true;
                }
            }
            if (!overtimeFinalFound) throw new AssertionError("Overtime final score was lost");
            System.out.println("BASKETBALL HTTP SMOKE OK: " + history.getRekabetGecmisi().size()
                    + " H2H, " + history.getSonMaclarHome().size()
                    + "+" + history.getSonMaclarAway().size());
        } finally {
            scraper.close();
        }
    }
}
