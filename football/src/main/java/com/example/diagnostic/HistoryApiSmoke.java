package com.example.diagnostic;

import com.example.model.TeamMatchHistory;
import com.example.scraper.MatchScraper;

public final class HistoryApiSmoke {
    public static void main(String[] args) {
        MatchScraper scraper = new MatchScraper();
        try {
            TeamMatchHistory history = scraper.scrapeTeamHistory(
                    "https://istatistik.nesine.com/3166383", "Bulgaristan - Estonya");
            if (history == null || history.getSonMaclarHome().size() != 6
                    || history.getSonMaclarAway().size() != 6) {
                throw new AssertionError("Football history did not match the visible 6+6 rows");
            }
            System.out.println("FOOTBALL HTTP SMOKE OK: " + history.getSonMaclarHome().size()
                    + "+" + history.getSonMaclarAway().size());
        } finally {
            scraper.close();
        }
    }
}
