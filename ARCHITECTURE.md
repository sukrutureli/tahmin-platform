# tahmin-platform architecture

## Migration phase (current)

The existing production repositories remain untouched and continue to own production schedules, publishing and Telegram delivery.

`tahmin-platform` is introduced in parallel:

```text
scraper
   |
   +--> football -----+
   |                  +--> parity artifacts
   +--> basketball ---+
```

CONTROL is also centralized but initially manual-only:

```text
football CONTROL -----+
                      +--> parity artifacts
basketball CONTROL ---+
```

## Directory ownership

- `scraper/`: copied from `Scraper/main`; no scraper refactor.
- `football/`: copied from `futboltahmin/codex-improvements`; includes the latest CONTROL/detail-score work.
- `basketball/`: copied from `basketboltahmin/ortaklama`.
- `.github/workflows/`: central orchestration.

There is deliberately no `common` Java module in v1. Similar-looking scraper/model/report code remains sport-specific unless a later line-by-line comparison proves it is safe to share.

## Safety during parity testing

- Daily and CONTROL schedules in this repository are disabled.
- New workflows do not push to `fathertahmin`.
- New workflows do not send Telegram messages.
- Existing repositories are not modified or disabled.
- Generated scraper history/output is not copied into source control during initial import.

## Activation after parity

After generated JSON/HTML is verified against the existing pipeline, enable central schedules and add one publish step to `fathertahmin`, followed by Telegram delivery. Only then disable the old schedules. Keep the old repositories available for rollback until the new pipeline has been stable.
