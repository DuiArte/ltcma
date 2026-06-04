# WEBSITE_DEPLOY — page visibility rules (Terse)

Source of truth for strategy cards: `Trading_Index/strategies.json` (hub) → repo
fallback `data/backtests_strategies.json`. Both pages read it via
`glossary.bt_catalog()` and render with `glossary.bt_card()` (one card markup,
one CSS block `glossary.BT_CARD_CSS`). A metric lives in exactly one place.

## Visibility rule

- **Backtests** (`backtests.html`, `24_backtests.py`): curated showcase — renders
  `public:true` entries (the winners). Failures stay internal in the JSON, not on
  the public site. Each card cross-links to deployment status on Strategies.
- **Strategies** (`strategies.html`, `23_strategies.py`): the live regime-adaptive
  book (SARS/DUO/MARS/BARS, own return CSVs) **plus** a "Validated Strategy
  Backtests" section rendering the same `public:true` cards, cross-linked to the
  Backtests archive. Flagship (`gfc_test_passed:true`) sorts first.
- **Overlap**: every deployable backtest appears on BOTH pages (Carlos, 2026-06-04
  — "successful strategies in the backtest section as well as the systematic
  strategies section"). Reverse not required: a failed backtest never reaches
  either public page.

## Card metric fallbacks (`glossary._BT_ALT`)

Ensemble entries store headline under richer keys. Card falls back:
`best_raw_sharpe → sharpe`, `pbo → pbo_structural`. Keeps the flagship Static
Drift-Weight 50/30/20 showing Sharpe **1.33** / PBO **0.33** (not `n/a`).

## Build / deploy

Run in WSL (`~/LTCMA`, where the SARS/DUO/MARS/BARS CSVs live):
`cd scripts && python3 24_backtests.py && python3 23_strategies.py`.
Commit + push to `origin/main` (GitHub Pages serves `docs/`). `C:\Users\carlo\
LTCMA-website` is a sibling clone of the same repo (`DuiArte/ltcma`) — pull to
sync. CDN cache ~minutes before live.
