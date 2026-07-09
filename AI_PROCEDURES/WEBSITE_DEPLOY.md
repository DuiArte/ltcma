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

## Portfolio equity curve methodology (`18_portfolio.py` → `docs/portfolio.html`)

The Total-value curve MUST be flow-immune. Construct it as
`total = CAPITAL + (MV − cost) + realized`, all from the Excel snapshot spine
(positions + avg cost) priced on Yahoo (BMV `.MX`). A buy and an *undocumented
add* both raise MV and cost equally, so they cancel — capital moving between the
GBMF2 cash sleeve and equities never reads as performance. Realized P/L = snapshot
position-drops valued at Yahoo. **Never** derive the cash sleeve from a blotter
residual (`blotter_clean.csv`): broker shares with no recorded trade (the XLE
anti-pattern) then move MV without the offset → phantom ±20–45% day swings
(the "−20% drawdown then spontaneous recovery" bug, fixed 2026-06-05).

Two daily price hygiene steps feed the curve (snapshot-row anomaly filtering is
NOT enough — it never touches the daily price series that draws the line):
- **De-spike** isolated bad prints (one-day spike/dip that reverts → carry prior).
- **Split reconciliation:** a BMV split re-bases the Yahoo price on the split day
  but the snapshot share count only catches up at the next snapshot (VGT 8:1,
  VUG 6:1: price 04-20 vs shares 04-24) → MV craters ~8× then snaps back. Detect
  the split from the **avg-cost** series (re-bases only at a split, not at a sell),
  confirm via a matching price re-basing, then put price/shares/avg-cost on one
  continuous basis. Keying off share counts is wrong — a half-position sell looks
  like a 1:2 split.

Endpoint is pinned to the canonical broker KPIs so the chart == the headline.
Sanity gate: max single-day curve move should be low single digits (≈3%), not 40%.

## Realized P&L ledger (`18_portfolio.py` → "Realized P&L Since Inception")

Source: the GBM *Historial de Transacciones* CSV exports in
`Documents/GBM_Account_Archive/transactions_historial/`.

**GBM exports overlap and contradict each other.** The same fills reappear under
shifted value dates: the 24-Apr batch is re-exported as a "27-Apr" batch in
`...1779481549357`, and the 12-Jun AMAT fill appears in three files. A
`glob` + union of `*.csv` therefore **double-counts and silently inflates realized
P&L**. Do not "just point it at the newest export."

- **Canonical calendar = `...1779481238707`.** It dates the SOXX fills 29-Apr,
  agreeing with the authoritative window file
  (`..._2026-04-28_to_2026-06-15.csv`), where `...549357` says 30-Apr. The offline
  cost-basis dashboard independently dates the batch 24-Apr. Newest ≠ correct.
- **Each export owns a disjoint calendar slice** (`_SELL_SRC`, `_BUY_SRC`). Two
  guards abort the build: a fill claimed by >1 export, and the same
  ticker/shares/price on two dates ≤5 days apart (a shifted re-export). Verified
  by reintroducing `...549357` — it catches all 7 duplicate pairs.
- **`_lbuys` must span the Feb/Mar exports.** `_xbuy()` needs buy lots at-or-before
  each sale to derive purchase FX. With only the window file it found none — for
  the April sales *and* for SOXX's already-counted 29-Apr sale — and silently fell
  back to `fx_live` (today's rate). That is why the realized FX leg once read
  −4,162. A missing lot is silent, not an error.
- **VGT/VUG are excluded from the 24-Apr batch.** Their 6:1 split re-based shares
  on that exact date, so cost basis is ambiguous there. Carlos's call; the page
  note states it.

Known divergence: site realized values run slightly above the offline engine on
every ticker (AMAT +304 MXN, identical before and after the ledger merge) — the
site uses broker-snapshot average cost at-or-before each sale, the offline uses a
running moving average. Share counts match exactly on all non-split tickers. The
code comment claiming the page "matches the offline dashboard" is stale intent.

## Return banners (Realized / Unrealized / Combined)

Each leg is measured against **the cost basis it earned on** — realized against the
cost of shares sold, unrealized against the cost still held. That makes Combined the
cost-weighted blend of the other two rather than an unrelated third number, and an
`assert` enforces the identity at build time:

```
combined = w·realized + (1−w)·unrealized,   w = sold_cost / (sold_cost + held_cost)
```

Ratios are **scale-invariant** — `SCALE` cancels — so the banners publish the real
returns even though the peso tiles beside them are scaled. Stock + FX contribution
still sum to the unrealized leg. Both rows use `.metrics`, so the existing ≤820px /
≤560px breakpoints apply; no bespoke CSS.

## Build / deploy

Windows-native since 2026-06-10. **This clone (`C:\Users\carlo\LTCMA-website`) is
canonical** — build, commit and push happen here. Never `~/LTCMA`; WSL is retired
and a second clone reintroduces the divergence bugs the migration removed.

Full refresh: `.\daily_refresh.ps1` in the repo root (Task Scheduler job
`daily-website-refresh`, 16:31 Mon–Fri; `-DryRun` / `-BuildOnly` flags; ~110 s;
logs in `C:\Users\carlo\Scripts\logs\`). Single page: `python scripts/18_portfolio.py`.
Push to `origin/main` (GitHub Pages serves `docs/`). CDN cache ~1–2 min before live.

## Confidentiality discipline (public site)

Same restraint as the portfolio x1.8 scaling (`18_portfolio.py SCALE`). Strategy
cards on both pages route name/description/verdict through `glossary._bt_public()`:
a curated public string per public `key` in `_BT_PUBLIC`, else the `_bt_redact()`
backstop. Re-grep rendered HTML before every push (see "Sanity scan").

1. **No real $ amounts.** Any monetary value goes through `SCALE`; the factor is
   never disclosed on the site. Prefer ratios / % / multiples. (Strategy cards
   carry no $ — metrics only.)

   ⚠️ **Scaling is a deterrent, not a security boundary.** This repo is public and
   `SCALE` lives in the tracked source, so the older claim that the factor is "never
   logged to git in plain text" does not hold. Treat the scaling as friction against
   casual reading — **never publish a number whose exposure would actually matter.**
   Assume scaled peso figures are effectively public. Closing this properly means
   moving `SCALE` out of the tracked tree (env var / untracked config, next to
   `paths.py`) or publishing only ratios and percentages. Open decision; see the
   private notes rather than restating specifics here.

   The page must never *name* the factor, and no doc in this repo should spell out
   how to undo it. Say "scaled by a fixed constant". A guard in `18_portfolio.py`
   fails the build if the rendered HTML names the factor.
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

**`confscan.sh` does not scan `portfolio.html`.** It never has. Do not read a
clean confscan as "the portfolio page is clean" — that page is covered only by
the in-script guards described below.

### Build-time guards in `18_portfolio.py`

All five abort the build rather than publish. They print one line each on a good
run; **if a refresh log is missing these lines, the page was written by an older
script and must be rebuilt.**

| Guard | Fails when | Line printed |
|---|---|---|
| scale-factor assert | `SCALE` differs from the expected constant | `confidentiality guard OK …` |
| raw-value scan | any raw `_ragg` amount appears as a `data-s` | ” |
| factor-disclosure scan | the rendered HTML names the scale factor | ” |
| ledger double-count | one fill claimed by >1 export | `ledger: N sell fills …` |
| shifted re-export | same ticker/shares/price on two dates ≤5 days apart | ” |
| banner blend identity | `combined ≠ w·realized + (1−w)·unrealized` | `returns: …` |

Verify a guard by breaking it, not by reading it: change `SCALE`, or add
`...549357` back to `_SELL_SRC`. Both abort before the write.

### Verify on the deployed bytes

Pages can serve a stale commit while the local file looks correct. `curl` the live
URL and diff sort attributes against their cells:

```bash
curl -s "https://duiarte.github.io/ltcma/portfolio.html?cb=$RANDOM" -o /tmp/live.html
# every numeric data-s must equal its rendered cell; any constant ratio between the
# two means the sort key is carrying the unscaled value
```

Screenshots of `portfolio.html` time out (five inline Plotly charts). Verify layout
with computed styles via the browser tools instead.

### Failure mode: scaled cell, unscaled attribute (2026-07-09)

`portfolio.html` published the real book for three weeks (`c5ae501`, 2026-06-15
→ `eb2b196`, 2026-07-09). The Realized P&L table rendered every cell as
`value * SCALE` but wrote the **raw** ledger amount into the `data-s` sort
attribute:

```python
# the bug: display scaled, sort key raw
f"<td data-s='{a['total']:.2f}'>{cval(a['total']*SCALE, signed=True)}</td>"
```

Four rows x (shares, stock P&L, FX P&L, total) = 16 real MXN figures, visible in
View Source. Nothing rendered looked wrong, so eyeballing the page could never
have caught it. Every *other* table on the page pre-scales its values and reuses
the scaled number for both the attribute and the cell — which is why only this
one diverged.

Rules that follow:

1. **Scale once, at the source.** A value enters the template already scaled;
   the template never multiplies. If you write `*SCALE` inside an f-string, the
   sibling attribute in that same f-string is probably still raw.
2. **Attributes are public.** `data-s`, `data-mxn`, `title`, `aria-label`,
   embedded JSON and Plotly `customdata` are as public as the visible text.
   "It's only for sorting" is not a confidentiality argument.
3. **The guard is in `18_portfolio.py`, not confscan.** Immediately before the
   write it asserts `SCALE == 1.8` and fails the build if any raw `_ragg` amount
   appears as a `data-s` value. It prints
   `confidentiality guard OK | scale factor x1.8 | N realized rows checked` on
   every run — if that line is missing from a refresh log, the page was written
   by an older script and must be rebuilt.
4. **Verify on the deployed bytes, not the working tree.** `curl` the live URL
   and diff the sort attributes against their cells; Pages can serve a stale
   commit while the local file looks correct.

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

## Pages deploy playbook — `pages build and deployment` (distinct from refresh.yml)

This is GitHub's **built-in** Pages workflow (event `dynamic`, NOT in `.github/`),
auto-triggered on every push because Pages source = *Deploy from a branch*
(`build_type: legacy`, `main` `/docs`). It is separate from `refresh.yml`: `refresh.yml`
commits the rebuilt site, then this workflow builds+deploys it. A green `refresh.yml`
push can still fail here.

**Where to look** (no `gh`; token via `git credential fill` — never echo it):
- `curl -s -H "Authorization: Bearer $TOKEN" .../actions/runs?per_page=8` → filter
  `name == "pages build and deployment"`; the **deploy** job is the one that fails.
- Authoritative legacy build status: `.../pages/builds?per_page=6` (status + `error.message`)
  and `.../pages` (`status: built|errored`). Job logs: `.../actions/jobs/<id>/logs`.

**Failure mode — Jekyll "Page build failed." / "Deployment failed, try again later." (2026-07-02).**
- **Symptom.** `build` job green, `deploy` job red in ~10s: `##[error]Deployment failed,
  try again later.` `/pages/builds` shows `errored — "Page build failed."`; `/pages`
  status `errored`. Built clean through 07-01, then failed every push on 07-02
  (commits `f1b7547`, `34d3bbe`) — persistent, not a one-off.
- **Cause.** `build_type: legacy` runs a **server-side Jekyll pass** over `/docs`. This
  site is 100% pre-generated static HTML/PNG (no Liquid, no `_config.yml`, no layouts),
  so Jekyll is pure overhead and an unstable failure surface. The 07-02 diff was pure
  numeric data (no new files/Liquid/dup-names/symlinks) — the content was fine; GitHub's
  Jekyll backend was the problem.
- **Fix shipped 2026-07-02 (`3d49500`).** Added **`docs/.nojekyll`** so Pages skips
  Jekyll and publishes files verbatim; `17_build_site.py` re-creates it on every build
  (line ~15). Result: `deploy` green, `/pages` status `built`, site HTTP 200.
- **Remember.** For any pre-generated static Pages site, ship `.nojekyll` from day one.
  If it recurs despite `.nojekyll`, next escalation is switching Pages source to
  *GitHub Actions* (`build_type: workflow`) with an explicit `upload-pages-artifact` +
  `deploy-pages` workflow, which removes the legacy Jekyll path entirely.
