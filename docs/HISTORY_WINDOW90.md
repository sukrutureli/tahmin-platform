# Ninety-day performance / broad strength input trial

Isolated branch: `experiment/history-window90-2026-11-06`. This does not replace
the earlier 365-day trial, the locked main model, or its immutable forecasts.

Use all obtainable finished team matches in the preceding 90 calendar days,
strictly before target date. There is NO 20/25 row cap and no forced filling of
the window: three available matches means three. Keep the latest six from this
window for form trends and recent-vs-wide differences. Recompute attack/defence,
expected totals, scoring/BTTS/over rates, venue summaries and variance from the
whole available window. Never silently borrow older games for these features.

Opponent-strength inputs deliberately retain up to 365 days with exponential age
decay (football half-life 90 days, basketball 60). No row quota applies to the
opponent-adjusted margin mean. The four alternatives are:

* `window90`: plain 90-day performance, decayed broad strength.
* `recency`: additionally decay performance within 90 days.
* `competition`: weight different/missing historical tournament IDs by 0.25 in
  performance and broad strength. Missing current tournament: no tournament effect.
* `combined`: both performance decay and tournament effects.

All alternatives use the SAME previously fitted, locked heads, preprocessing,
score distribution and complete-market-price-v2 selection. No training/tuning
on today's outcomes. These are input-distribution interventions whose effects
must be measured; neither safety nor improved performance is presumed.

## Source coverage

Pools use all saved HTTP side rows, cumulative identity-safe ledger and original
same-event audits. No new HTTP crawl is performed. Provider match/team identifiers
deduplicate records. Never join team names. Conflicting or year-inferred rows are
excluded. The existing collector may have stopped after a row threshold, so a
90-day window DOES NOT imply 90-day completeness. Report actual row counts and
oldest age for each team. For established team IDs the ledger can supply more
than one event's bounded replay sample. Sources and coverage are frozen before
the experiment; no extra post-outcome history is added in settlement.

Four tests cover 35 available rows (no old cap), latest-six trends, exact 90-day
boundaries, deduplication, sparse windows, competition fallback, strength using
older data, no fitting, original-result exclusion and source/snapshot immutability.

## Execution and settlement

Push `.github/history-window90-request.json` only on the experiment branch to run
`.github/workflows/history-window90-trial.yml`. Freeze pins source run 42120844121,
artifact 13459445956, date 2026-11-06 and verified priced snapshot SHA-256.
On settlement keep freezeSourceRunId fixed to that original source and set
freezeRunId to this trial's original successful run. Restore that exact encrypted
snapshot; use latest successful same-date production Control artifact only for
fresh labels. Do not retrigger production or recalculate predictions.

Each alternative vs current main has own choices and own confidence ranking,
first 50% primary, 25/75/all secondary. Report planned/measured N, hits, binary
Brier/log loss, compatible-score MAE; pending/live/push and no offered choice do
not enter success denominators. Before-kickoff and labels unknown at freeze are
independent; late/already-known records are exploratory. Different freeze times
mean cohorts of this and earlier trials may differ; do not merge them.

Private outputs are `raporlar/2026-11-06/90-gun-gecmis-deneyi.html`,
`deney/reports/2026-11-06/history-window90-evaluation.json` and
`history-window90-checkpoint.json`. SHA-256 hashes are in checkpoint reports.
Full forecasts and eligibility evidence remain encrypted in the workflow artifact.
HTML follows today/yesterday retention. Do not modify canonical production paths,
Daily/Control, Telegram, model weights or automatic promotion. Discuss adoption
with user after day-end comparison; one-day improvement is not general proof.
