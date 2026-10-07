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
| **Strategies** | ✅ EMBER vs Static 50/30/20 live paper-track (`28_ember_ensemble.py`) | paper-track ≤5 d (red 10) | 🟢 | — |
| **Backtest reports** (`bt_*.html`) | ❌ static by design — windows end May 2026 | ≤90 d since window end (red 365) unless a live series extends it | 🟡 Buy-the-Dip, Static Diversification, CRT end 2026-05-19/26; Static Drift is carried live | ⚙️ **Automatable, not built:** a daily "replay forward" per public strategy (same rules, new bars) like `28` does for EMBER. Map each to its live series in the rule's `live` block when built. |
| **Full Report** | ❌ hand-written (`report/LTCMA_2026.md`) | archived edition ≤45 d (red 120) | 🟡 served as the dated 2026-08-11 edition (honest; resync owed) | 🧑 **TAB_RESYNC** (decision gate D-20260924-004). Figures are hand-written by design; never auto-regenerated. |
| **Research Notes** | ✅ *partly*: the automated-pipeline row is computed from pipeline v2's verdicts every build; the funnel tiles are derived from the page | newest content ≤60 d (red 120) | 🟢 (pipeline verdict 2026-10-06) | 🧑 **Curated findings/batches** (`FINDINGS` / `BATCHES` in `27_research_notes.py`) need analytic judgement. Pipeline v2's layer 4 decision-maker can *draft* an entry; publishing stays human-approved. ⚠️ Derived "signals tested" tile reads **155** (table sum); the old hand-typed "~181" could not be reproduced from any source — Carlos to confirm or add the missing trials to the table. |
| **Stock Research** + `stock_*.html` | ✅ price, analyst consensus, CFA valuation recomputed from Yahoo daily (`19`, `21`, `25`) | each page's price date ≤7 d (red 30) | 🟡 prices current; linkage flagged | ⚙️ **Earnings dates / catalysts are not on the pages** (Yahoo calendar could supply them — automatable). 🧑 **Coverage decision:** 9 held names have no page (LLY, CCJ, GMEXICOB, HD, COST, WMT, ASTS, UBER, RKLB); AMZN, META, MSFT have pages but are not held. The watchlist is `19_stock_analysis.DEFAULT`; the monitor reports, it does not add or archive. No hand-written thesis exists (it is computed daily), so "thesis stale" has nothing to grade. |
| **Regime Tracker** | ✅ daily inputs, monthly composite (`20_regime_tracker.py`) | newest input ≤5 d (red 10); composite ≤1 month behind | 🟢 NEUTRAL | — (regime change ⇒ WEBSITE_ALERT + toast) |
| **Street LTCMA** (`street-ltcma.html`, added 2026-10-07, decision D14) | ✅ *render* daily (`30_market_intel.py`) · ✅ *content* monthly (`market-intel-monthly`): compiled consensus of all firms, **aggregates only** (n≥5, trimmed mean), downloadable editions in `docs/street-ltcma/` | `ltcma-content-asof` ≤38 d (red 45); data surface `street_ltcma` (monthly_day1) | 🟢 first edition 2026-10-07 | — |
| **Market Intel** (`ltcma-consensus.html`, added 2026-10-07) | ✅ *render* daily (`30_market_intel.py`, render-only) · ✅ *content* monthly, task `market-intel-monthly` (day 1) writes `data/market_intel/consensus_public.json` | `ltcma-content-asof` meta ≤38 d (red 45); data surface `market_intel_consensus` on the new `monthly_day1` cadence (840 h) | 🟢 preliminary edition 2026-10-07; first official run 2026-11-01 | 🧑 optional inbox drops for gated publishers (BlackRock, GMO, GS Research, Morgan Stanley, Horizon) into `Documents\Market_Intel\inbox\`; the page lists which are missing |
| **Projects** | ✅ *the page*: each card shows the repo's real last push (GitHub API, `17`) | last push ≤90 d (red 180 while listed active) | 🟡 all 6 repos last pushed 2026-05-28 / 06-04 | 🧑/⚙️ The **repos themselves** only change when someone pushes. An automated sync per repo (e.g. backtests-archive, ai-procedures-quant) would be a new public publisher — needs Carlos's approval and a sanitizer chokepoint like `daily_advances_digest.py`'s. |
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
