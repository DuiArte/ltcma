# WEBSITE_DEPLOY — page visibility rules (Terse)

Source of truth for strategy cards: `Trading_Index/strategies.json` (hub) → repo
fallback `data/backtests_strategies.json`. Read via `glossary.bt_catalog()`,
rendered with `glossary.bt_card()` (one card markup, one CSS block
`glossary.BT_CARD_CSS`). A metric lives in exactly one place.

## Page inventory (2026-06-04 — two merges, N→N-2)

Two structural merges (Carlos: "merge the backtest and the strategies windows,
also merge the stock picks and stock signals"):
- **`backtests.html` → MERGED into `strategies.html`.** `24_backtests.py` now writes
  a meta-refresh redirect (`→ strategies.html#backtests`) and still renders the
  per-strategy `bt_<key>.html` report pages + syncs the JSON fallback.
- **`signals.html` → MERGED into `stocks.html`.** `21_stock_signals.py` now writes a
  meta-refresh redirect (`→ stocks.html#signals`). The macro-β / FOMC content moved
  into `25_stock_picks.py`.
- Nav (`glossary.NAV`) dropped "Backtests" and "Stock Signals"; "Stock Analysis"
  renamed "Stock Research". Live page count 11 → 9.

## Visibility rule (post-merge)

- **Strategies** (`strategies.html`, `23_strategies.py`): the live regime-adaptive
  book (SARS/DUO/MARS/BARS, own return CSVs) **plus** one merged feed rendering
  **every** catalog entry as a status-tagged card with client-side filter pills
  (All · Deployed · Research (passed) · Failed/archived) and the critical-findings
  research notes (#9/#10/#11). Status: green badge → Deployed (flagship
  `gfc_test_passed` first), yellow → Research/ensemble, red → Failed/archived with
  the **lesson learned shown** (Carlos, 2026-06-04 — failures now surface, reversing
  the prior "failures off-site" choice). Confidentiality preserved: any **non-public**
  entry has its raw thesis replaced by a generic line (parameters/universe stay
  private, rule 4/7); name + verdict + lesson route through `_bt_public`/`_bt_redact`.
- **Stocks** (`stocks.html`, `25_stock_picks.py`): composite-picker-led research page
  (see methodology below) + the former signals macro-β/FOMC tables + per-company CFA
  report links. `19_stock_analysis.py` still builds the `stock_<TICKER>.html` pages
  and runs first in the daily chain; `25_stock_picks.py` runs after it and owns
  `stocks.html`.

## Composite picker methodology (`picker.py` + `25_stock_picks.py`)

Reproducible from public data + this formula (no model judgement on which names):
1. **Universe** = macro-signal coverage set (40 names carrying BOTH fundamental and
   signal variables): `stock_sensitivities.parquet` ∩ live yfinance fundamentals.
2. **Variables** (every numeric var from both pipelines): fundamentals — ROE, gross/
   net margin, FCF yield, margin-of-safety, Buffett score, rev/EPS growth, low-
   leverage `1/(1+D/E)`, 12-1 momentum; signals — earnings yield `1/PE`, fwd earnings
   yield, β to rates/dollar/CAD, macro R².
3. **z-score** each var cross-sectionally; missing → 0 (neutral).
4. **Weights** = each var's Pearson corr with realised forward returns (mean post-FOMC
   5-day drift per ticker from `stock_fomc_reaction.parquet`), normalised so Σ|w|=1;
   **corr sign sets direction** — nothing hand-picked. Equal-weight fallback if the
   forward-return history is absent (documented on the build).
5. **Composite** = Σ w_v·z_v. Rank desc; **top 20 = picks**. Buy candidate = composite>0.
6. **Confidentiality:** weight VALUES stay in `picker.py`, never rendered (rule 4). The
   page shows the ranked result + each pick's variable contributions (direction +
   relative bar) + a deterministic 1-line commentary. Picker output is PUBLIC research
   over the full investable universe (not Carlos's positions).
- **Validation (each build prints):** sector distribution of top-20, single-variable
  variance share (flag if >80%), and overlap vs a naive 12-1-momentum baseline.

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
