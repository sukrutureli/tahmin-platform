# History context input trial, 6 November 2026

This is an isolated one-day prospective input intervention, not a new fitted model.
Production model, forecasts, Daily/Control, Telegram and canonical HTML are read-only.
The experiment branch is `experiment/history-context-2026-11-06`.

## Fixed candidates, chosen before outcomes

Compare current `complete-market-price-v2` frozen main choices with three alternatives:

* `recency`: exponential age weighting, half-life 90 days for football / 60 for basketball; exclude matches older than 365 days.
* `competition`: same provider tournament ID weight 1; different/missing historical tournament weight 0.25. Missing current tournament: exact original forecast fallback.
* `combined`: both interventions.

Recompute compatible short-history features, recent/wide differences, and opponent
rating/adjusted-margin inputs. Rating updates use age/competition weights and
same-historical-day batch updates to avoid intra-day leakage. The frozen model's
preprocessing, feature lists, weights, score distribution and pricing policy stay
unchanged. This is a distribution-shift hypothesis, not established improvement.
It does not claim to account for rotation, lineups or first/second legs.

Only completed history strictly before target date is allowed. Current outcomes
cannot enter feature construction. Original checkpoints are restored from
authenticated encrypted artifacts. No new crawl or fit is necessary. Four tests
cover age/future boundaries, strength updates, source immutability, missing
competition fallback, prospective/late separation and frozen settlement.

## Evaluation

Freeze actual creation time. Each arm and baseline keep only mutually before-kickoff
records for independent evaluation; late records are exploratory. Each system chooses
its own highest offered complete-market probability, ranks its own confidence and
reports first 25/50/75/all. First 50 is primary. Exclude live/missing/push and no
priced choice from measured denominators. Freeze rank membership before outcomes;
report planned and measured counts, hits, binary Brier/log loss, conditional score MAE.
Three candidate comparisons are exploratory and not grounds for automatic promotion.

## Running and evening settlement

Update only `.github/history-context-request.json` on this branch. Push starts
`.github/workflows/history-context-trial.yml`; never dispatch a full production run.
Freeze request pins target date, successful sourceRunId, sourceArtifactId and
pricedSourceSha256 verified against private dated manifest/index. On settlement,
use latest successful same-date production Control source, set `mode=settle`
and `freezeRunId` to this trial's first successful run. It restores that encrypted
trial before labels are read, so no candidate is reforecast or backdated.

Private outputs: `raporlar/2026-11-06/gecmis-baglam-deneyi.html`,
`deney/reports/2026-11-06/history-context-evaluation.json` and checkpoint JSON.
Raw snapshots stay encrypted in `history-context-frozen-2026-11-06` artifact.
Publication happens only after encrypted upload. Existing score/same-competition
summaries are included as separate policies, never merged with the new trial.
HTML is published only for today/yesterday; normal archive retention removes it.
At day end report unresolved matches explicitly; do not declare them settled.
Discuss possible main adoption with user, no automatic merge or model changes.
