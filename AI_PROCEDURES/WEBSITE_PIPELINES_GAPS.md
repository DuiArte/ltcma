# Site tabs — what refreshes itself, what is monitored, what still needs a human

Written 2026-10-07 after Carlos noticed tabs that *looked* current (fresh "As of" stamp every
day) over content that was months old. Status board: **`docs/internal/freshness.html`**
(unlinked; https://duiarte.github.io/ltcma/internal/freshness.html).

## How freshness is enforced now (one manifest, one engine)

| Piece | Where | Role |
|---|---|---|
| SLAs | `Trading_Index\pipeline\content\refresh_manifest.json` → `content_rule` per tab | Declares what "current" means per tab (`amber_days` / `red_days`). **This is the site SLA file** — there is deliberately no separate `site_sla.yaml`. |
| Extractors | `scripts/content_age.py` | Reads the age of what each page SAYS (newest batch, price date, regime input, repo push, backtest end). Read-only. |
| Auditor | `Scripts\pipeline_v2\layer7_content_refresh.py` | Grades render age **and** content age. Runs 09:30 (task `Pipeline V2 Content`) and again inside `daily_refresh.ps1`. Writes `CONTENT_STATUS.md` / `_content_status.json`. |
| Dashboard | `scripts/34_site_freshness.py` (step in `daily_refresh.ps1`) | Emits `docs/internal/freshness.html` from layer 7's verdict. |
| Alert (layer 1) | `C:\Users\carlo\Scripts\logs\WEBSITE_ALERT.txt` | Raised on actionable RED content or a regime change; cleared automatically. `website_refresh_watchdog.ps1` folds it into `REFRESH_ALERT.txt`. Regime changes also raise a **desktop toast**. |
| Re-run (layer 2) | watchdog `-Remediate` / layer 7 `--remediate` | Re-fires `daily-website-refresh` only when a page was not *rendered* on time. Content age is never "remediated" by a re-render — a refresh cannot write a research batch or push a repo. |

## Tab by tab (status at 2026-10-07)

| Tab | Refreshes itself (daily) | Content SLA | Today | Missing pipeline / human input |
|---|---|---|---|---|
| **Dashboard** (`index.html`) | ✅ signals, priced-in, regime tile, portfolio card (`17_build_site.py`) | book date ≤4 d (red 7) | 🟢 | — |
| **Portfolio** | ✅ prices + FX daily (`18_portfolio.py`, `29_peak_rollforward.py`) | Performance date ≤4 d (red 7) | 🟢 | 🧑 **New trades need the broker exports** dropped into the archive; `29` refuses to roll forward over new fills until the walk is re-run. |
| **Strategies** | ✅ EMBER live paper-track vs a fixed 50/30/20 SPY/IEF/GLD *reference basket* (`28_ember_ensemble.py`, which applies stock splits since 10-07; the basket is an asset-class stand-in, **not** the Static Drift-Weight 50/30/20 strategy) · one out-of-sample-replay line per public backtest card (`23`, from `data/bt_replay/`) | paper-track ≤5 d (red 10) | 🟢 | — |
| **Backtest reports** (`bt_*.html`) | ✅ since 2026-10-07: an **out-of-sample replay** from each backtest's end, recomputed daily by `35_bt_replay.py` (frozen private engines on fresh public prices, seam-checked against the frozen results on every run) → `data/bt_replay/<key>.json` → chart + paragraph on the page (`24`). Buy-the-Dip = the deployed SPY/QQQ/EFA blend; Static Diversification = the weekly config behind the published numbers; Static Drift 50/30/20 = sleeve C replayed with the *operated* GLD>EMA200 rule. **CRT is frozen by decision** (FxPro M5 branch closed, 1H/4H/1D-only rule, Findings #24/#52) and the page says so. Never label a replay "live". | replay ≤5 d (red 10) via the rule's `live` block; CRT is INFO via its `frozen` block | 🟡 until the manifest `live` + `frozen` entries land (then 🟢) | 🧑 apply the `live` / `frozen` entries in `refresh_manifest.json` → `backtest_pages.content_rule` |
| **Full Report** | ❌ hand-written (`report/LTCMA_2026.md`) | archived edition ≤45 d (red 120) | 🟡 served as the dated 2026-08-11 edition (honest; resync owed) | 🧑 **TAB_RESYNC** (decision gate D-20260924-004). Figures are hand-written by design; never auto-regenerated. |
| **Research Notes** | ✅ *partly*: the automated-pipeline row is computed from pipeline v2's verdicts every build; the funnel tiles are derived from the page | newest content ≤60 d (red 120) | 🟢 (pipeline verdict 2026-10-06) | 🧑 **Curated findings/batches** (`FINDINGS` / `BATCHES` in `27_research_notes.py`) need analytic judgement. Pipeline v2's layer 4 decision-maker can *draft* an entry; publishing stays human-approved. ✅ **"Signals & strategies tested" is derived from a private ledger** of every documented campaign (Carlos, 10-07: "busca en la documentación todas las estrategias"): 300 on 10-07, published as counts only (`data/research_tally.json`); Hunt Loop and pipeline-engine counts are live. 🧑 A new numbered Finding must be classified in the ledger (test vs audit) — until then the page carries `ltcma-tally-unclassified` and the monitor is amber. |
| **Stock Research** + `stock_*.html` | ✅ price, analyst consensus, CFA valuation recomputed from Yahoo daily (`19`, `21`, `25`) | each page's price date ≤7 d (red 30) | 🟢 | ⚙️ **Earnings dates / catalysts are not on the pages** (Yahoo calendar could supply them — automatable). The page set is a research **watchlist** (`19_stock_analysis.DEFAULT`), **independent of the portfolio by design** (Carlos, 10-07: "los holdings son algo aparte") — no holdings linkage is graded. No hand-written thesis exists (it is computed daily), so "thesis stale" has nothing to grade. |
| **Regime Tracker** | ✅ daily inputs, monthly composite (`20_regime_tracker.py`) | newest input ≤5 d (red 10); composite ≤1 month behind | 🟢 NEUTRAL | — (regime change ⇒ WEBSITE_ALERT + toast) |
| **Street LTCMA** (`street-ltcma.html`, added 2026-10-07, decision D14) | ✅ *render* daily (`30_market_intel.py`, skipped while its JSON is absent) · ✅ *content* monthly (`market-intel-monthly`): compiled consensus, **aggregates only** under a disclosure gate (gated firms left out; n≥5; 0 or ≥3 review firms; attacker LP), content-addressed downloads in `docs/street-ltcma/` | `ltcma-content-asof` ≤38 d (red 45); data surface `street_ltcma` (monthly_day1) — **both parked under `_suspended`** in the manifest while the page is down | ⛔ **DOWN since 2026-10-07 11:43**. The first edition leaked restricted firms' figures (Market Intel correction C-20261007-02). Held by `street.hold` in `Trading_Index\market_intel\config_a.yaml`. The nav tab hides itself (`glossary.py`). | 🧑 Carlos: purge the leaked commit `e971777` from history (approved; the auto-mode classifier blocked Claude), then lift the hold |
| **Market Intel** (`ltcma-consensus.html`, added 2026-10-07) | ✅ *render* daily (`30_market_intel.py`, render-only) · ✅ *content* monthly, task `market-intel-monthly` (day 1) writes `data/market_intel/consensus_public.json` | `ltcma-content-asof` meta ≤38 d (red 45); data surface `market_intel_consensus` on the new `monthly_day1` cadence (840 h) | 🟢 preliminary edition 2026-10-07; first official run 2026-11-01 | 🧑 optional inbox drops for gated publishers (BlackRock, GMO, GS Research, Morgan Stanley, Horizon) into `Documents\Market_Intel\inbox\`; the page lists which are missing |
| **Projects** | ✅ *the page*: each card shows the repo's real last push (GitHub API, `17`) | last push ≤90 d (red 180 while listed active) | 🟡 5 repos pushed 2026-10-09; Terse last pushed 2026-05-28 | ✅ **Sync built and pushed 2026-10-09** (`Scripts\projects_sync\run_projects_sync.ps1 -Push`; task not registered yet): regenerate the repos that have a public source (methodology, static-drift-weight, backtests-archive) ONLY from outputs already public on this site, through a hardened fail-closed leak gate, pushing only when content actually changes (no heartbeat commits — freshness is graded on `pushed_at`). Repos with no public source (signallib-framework, ai-procedures-quant, terse) change only when their owner changes them. |
| **Glossary** | static by design | — | 🟢 | — |

Legend: ✅ automatic · ⚙️ automatable, not built yet · 🧑 needs a human decision or input.

## Adding a tab (any session, any agent)

1. Generator in `scripts/`, called by `daily_refresh.ps1` — the only publisher (`docs/` is
   `git clean -fd`'d every run; anything not generator-emitted vanishes).
2. Entry in `refresh_manifest.json` with `kind` / `cadence` / `generators` **and a
   `content_rule`** — a tab without one can look current forever.
3. Row in `AI_PROCEDURES/WEBSITE_PUSH_SOURCES.md`.
4. If the page stamps its newest content as `<meta name="ltcma-content-asof">`, the generic
   `meta_asof` extractor grades it with no new code.
