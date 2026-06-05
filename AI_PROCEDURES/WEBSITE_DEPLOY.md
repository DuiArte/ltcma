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

## Confidentiality discipline (public site)

Same restraint as the portfolio x1.8 scaling (`18_portfolio.py SCALE`). Strategy
cards on both pages route name/description/verdict through `glossary._bt_public()`:
a curated public string per public `key` in `_BT_PUBLIC`, else the `_bt_redact()`
backstop. Re-grep rendered HTML before every push (see "Sanity scan").

1. **No real $ amounts.** Any monetary value goes through `SCALE`; the factor is
   never disclosed on the site and never logged to git in plain text. Prefer
   ratios / % / multiples. (Strategy cards carry no $ — metrics only.)
2. **No real position sizes.** "fixed 1% risk per trade" yes; "long 100k XLK" no.
3. **Performance metrics ARE public** (scale-invariant): Sharpe, Sortino, max DD %,
   Calmar, win rate, CAGR, DSR, PBO. Display them.
4. **Parameters STAY PRIVATE:** specific weights, signal thresholds, lookbacks,
   optimizer/feature-selection choices. Allowed exception: the headline weight
   ratio (e.g. `50/30/20`) — cleared for display.
5. **Feature implementations STAY PRIVATE:** a feature may be NAMED (e.g.
   `meanrev_5d`) with breadth (`8/27 instruments`), OOS Sharpe and PBO; the formula,
   universe list and entry/exit rule stay redacted.
6. **Critical findings ARE publishable** (#9 gating, #10 macro, #11 daily-bar
   single-name): observations, not actionable IP. Publish as research notes.
7. **Failed backtests:** name + thesis + headline verdict + lesson; tested
   parameter values stay private. (Failures remain `public:false` = not on site.)

### What to display vs redact

| Field | Display | Redact |
|---|---|---|
| Sharpe/Sortino/Calmar/DSR/PBO/maxDD%/CAGR/win% | ✅ | |
| Headline weight ratio (`50/30/20`) | ✅ | |
| Verdict (Deployable / Ensemble / Pass / Fail) | ✅ | |
| Date span, # months, OOS window | ✅ | |
| Feature name + breadth (`meanrev_5d`, `8/27`) | ✅ | |
| Critical findings #9/#10/#11 (as notes) | ✅ | |
| Tickers / asset universe (SPY, IEF, XAUUSD…) | | ✅ |
| Entry/exit logic (EMA filters, R-targets, sigma) | | ✅ |
| Parameter values (lookback, threshold, weights≠headline) | | ✅ |
| Feature formula, universe list | | ✅ |
| Real $ / position sizes | | ✅ (scale) |
| Internal paths (`Trading_Index`, `SignalLib`, `/home`, `Downloads`) | | ✅ |

### Sanity scan before commit

`bash scripts/confscan.sh` greps rendered `docs/*.html` + `*.ai.txt` for: unscaled
6-7-digit $; tickers; `param=value` / `sigma` / `EMA` / `R`-targets; internal
paths; real positions. Any hit (other than the allowed `50/30/20`, the viewport
`initial-scale=1`, JS slider vars, and metric-label fragments in `.ai.txt`) →
redact in `_BT_PUBLIC` / `_bt_redact` and rebuild.

## CI failure playbook — `.github/workflows/refresh.yml`

GitHub Actions runs the same daily refresh (cron `0 22 * * 1-5` + manual). The
**host Task Scheduler is primary**; the Action is a redundant cloud rebuild. It
only runs `08_fetch_signals.py` + `17_build_site.py` (deps: `requirements.txt`).

**Where to look** (no `gh` installed; repo is public — use the API):
- Runs: `curl -s "https://api.github.com/repos/DuiArte/ltcma/actions/workflows/refresh.yml/runs?per_page=5"`
- Step timing / which step failed: `.../actions/runs/<id>/jobs` → `jobs[0].steps[]`
  (each has `started_at`/`completed_at`/`conclusion`). Job logs need admin auth (403 public).
- Manual trigger: POST `.../actions/workflows/refresh.yml/dispatches` `{"ref":"main"}`
  with a token (HTTP 204 = accepted). Token via `git credential fill` — never echo it.

**Reproduce a GH-only crash locally** (the runner has neither the private host
strategy repos nor working FRED): run the script through an `os.path.expanduser`
shim that maps `~/LTCMA`→repo and `~`→an empty dir, with `requests.get` monkey-
patched to raise. If it passes locally but fails on CI, the cause is a host-only
path or a blocked endpoint.

**Common failure modes**
- **Multi-hour runtime then exit 1** = a fetch with no/loose timeout hammering a
  blocked endpoint. FRED (`fred.stlouisfed.org`) and Yahoo block cloud IPs. Fix:
  `(connect, read)` tuple timeout, ≤2 attempts, and a wall-clock `FRED_DEADLINE`
  that skips the rest and keeps prior on-disk values. (Fixed 2026-06-04: was 60s×4
  ×25 series ≈ 1h45m.) Backstop: job `timeout-minutes: 15`.
- **~3s crash in `17_build_site.py`** = it imported a host-only artifact. `bt_load()`
  reads `~/{SARS,DUO,MARS,BARS}/...` CSVs that don't exist on CI → `FileNotFoundError`.
  It now falls back to the series already in the public `docs/index.html`
  (`window.BT_DATA`). Never commit private-repo CSVs to fix this — reuse public output.
- **Push fails (non-fast-forward)** = host scheduler pushed during the run. The
  commit step does `git pull --rebase --autostash` first; `concurrency` cancels overlaps.
- **Node 20 deprecation warning** = `actions/checkout@v4`/`setup-python@v5` (Node 20).
  Warning only, not a failure. Deferred: bump to `@v5`/`@v6` when convenient.
