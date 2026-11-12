# Frozen checkpoint settlement recovery
This one-off workflow lives only on experiment/ensemble-market-validation.
It restores the explicitly pinned November 11 full checkpoint and November 12
primary checkpoint, runs only existing finished-result refresh clients and
settlement functions at be2074e5905c6cc52e95985555ed9614010ca9ab, and preserves
all original before-results files, model parameters, serving inputs and datasets
by SHA-256 before/after checks.

No forecast generation, model fit, subgroup mining or historical HTTP scan runs.
No canonical panel HTML, production workflow or Telegram output is written.
Private outputs are limited by a tested path allowlist to:
- deney/reports/YYYY-MM-DD/ report copies and recovery-checkpoint-manifest.json
- deney/current/recovery-checkpoint-manifest.json (pointer only)

The standard deney/current/checkpoint-manifest.json remains the last complete
normal experiment export. Recovery reports must be read from their dated paths.
The recovery manifest separately identifies the successful recovery run/artifact,
the original failed run and encrypted frozen artifact, unchanged snapshot hashes,
the pinned evaluation code and every report copy SHA-256.

November 12 background research was never frozen: only the previously frozen
primary model/price/stability forecasts can be evaluated. Missing research is
not synthesized. November 11 uses its original full frozen research checkpoint.

The encrypted recovery artifacts intentionally use frozen-recovery-YYYY-MM-DD,
not the standard ensemble-market-validation artifact name. Automatic production
orchestration must not mistake a partial recovery checkpoint for its own complete
daily source. No automatic main promotion or publication is enabled.

Do not repeat the request when the dated recovery manifest already identifies
a successful matching recovery run. To inspect settled results, prefer
priced-complete-evaluation.json beforeKickoff first 50%; each system chooses its
own eligible priced market and confidence order. Do not merge this policy with
the older priced/competition/score policies. Missing/live/push outcomes stay
outside the success denominator.
