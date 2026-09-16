# Migration sources

Initial consolidation is intentionally conservative. Existing sport-specific and scraping behavior is copied without refactoring.

- `football/` source: `sukrutureli/futboltahmin`, branch `codex-improvements`
- `basketball/` source: `sukrutureli/basketboltahmin`, branch `ortaklama`
- `scraper/` source: `sukrutureli/Scraper`, branch `main`
- Published output remains in `sukrutureli/fathertahmin` during the first migration stage.

No Java `common` module is introduced in v1. Scrapers, CONTROL logic, algorithms and sport-specific models remain separate.
