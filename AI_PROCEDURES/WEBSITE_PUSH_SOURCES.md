# Who writes to the public site — every source, audited 2026-10-06

GitHub Pages publishes `docs/` on `origin/main` (`github.com/DuiArte/ltcma`) verbatim.
Anything that commits to that branch can change the live site. This list exists because
stale clones and duplicate jobs have **resurrected deleted content** before (the retired
Snapshot block on `portfolio.html`; the Jun-18..23 refresh rebase trap). Before adding a
job, script or clone that writes here, check this list — and add yourself to it.

## ✅ Legitimate writers (the only three that push)

| Source | Trigger | What it pushes |
|---|---|---|
| `daily_refresh.ps1` (this repo) | Task Scheduler `daily-website-refresh` | all generated `docs/` + `data/`; runs `scripts/*.py`, load-bearing guards (`guard_decimals`, `guard_no_snapshot`), then `git commit` + `git push origin main` |
| `weekly_model_rebuild.ps1` (this repo) | Task Scheduler `weekly-model-rebuild` (Sun 22:00) | model outputs 01-04 + risk/MC; shares the `Global\LTCMA_REPO_LOCK` mutex with the daily job |
| `C:\Users\carlo\Scripts\market_intel_monthly.ps1` (Market Intel Track A, added 2026-10-07) | Task Scheduler `market-intel-monthly` (day 1, 07:00) | **only** `data/market_intel/consensus_public.json` + `docs/ltcma-consensus.html` (and, since 2026-10-07, the Street LTCMA: `data/market_intel/street_ltcma_{public,editions}.json`, `docs/street-ltcma.html`, `docs/street-ltcma/` downloadable editions), via `git commit --only` on those paths, under the same `Global\LTCMA_REPO_LOCK` mutex, after `git pull --ff-only`. The daily refresh re-renders the same page from the same JSON (`scripts/30_market_intel.py`, render-only), so both writers emit the same bytes for a given JSON. Builds privately in `Documents\Market_Intel` first. Docs: `Documents\AI_PROCEDURES\MARKET_INTEL_SPEC.md`, `MARKET_INTEL_MONTHLY.md`. |

`daily_refresh.ps1` also runs `scripts/34_site_freshness.py` (2026-10-07), which writes
exactly one extra file, `docs/internal/freshness.html`, from pipeline v2 layer 7's content audit.

Both build from **this clone's `scripts/`** after pulling origin, so a change merged to
`scripts/` is what they publish. There is no other generator, template, include or
partial: `docs/*.html` are emitted whole by Python (`17_build_site.py`, `18_portfolio.py`,
`19`–`25`, `27`…). `portfolio.html` is written by `18_portfolio.py` alone.

## Indirect / non-pushing (safe, listed so nobody re-audits them)

| Source | What it does |
|---|---|
| `C:\Users\carlo\Scripts\website_refresh_watchdog.ps1 -Remediate` (`daily-website-refresh-watchdog`) | read-only health check of the live site; on "never ran / failed" it re-invokes `daily_refresh.ps1` once (only when the repo is idle). Never edits or reverts `docs/` itself |
| `C:\Users\carlo\Scripts\daily_website_refresh.ps1` | deprecated shim; forwards to `daily_refresh.ps1` |
| `C:\Users\carlo\Scripts\daily_real_numbers_refresh.ps1` / `scripts\26_real_numbers_refresh.py` | writes the PRIVATE un-scaled copy to `Documents\CarlosDuarteWebsite\real_numbers\` — never `docs/`, never git. (It still has its own "Snapshot" block; that is the private file, out of scope for the public guard) |
| `C:\Users\carlo\Scripts\data_freshness_check.ps1`, `daily_advances_digest.py`, `portfolio_actions.py`, `real_income_generator.py`, `build_realized_ledger.py` | read the repo / `data/`, write alerts or private outputs elsewhere; no commit, no push |
| `Documents\CarlosDuarteWebsite` | **not a git repo** — a mirror *target* (`daily_refresh.ps1` copies `docs/` + `data/` into it). Nothing syncs from it back to the repo |
| `C:\Users\carlo\Scripts\pipeline_v2\layer7_content_refresh.py` (task `Pipeline V2 Content`, 09:30; also called by step 34) + `scripts/content_age.py` | content-age auditor: grades what each tab SAYS against `content_rule` in `Trading_Index\pipeline\content\refresh_manifest.json`; writes `CONTENT_STATUS.md` and `Scripts\logs\WEBSITE_ALERT.txt`. Read-only against the repo. See `WEBSITE_PIPELINES_GAPS.md` |
| `.github/workflows/refresh.yml` | **manual only** (`workflow_dispatch`, cron removed 2026-08-11). It cannot build `portfolio.html` on the runner (no private book) |
| Pipeline V2 (`Scripts\pipeline_v2\orchestrator.ps1`), `Strategy Hunt Loop` | do not reference the site repo |

## ⛔ Retired — must stay off

| Source | Status |
|---|---|
| Task `Portfolio Tracker Update` → `wsl.exe … /home/carlos/LTCMA/update_portfolio.sh` | **Disabled 2026-10-06.** Weekdays 16:30, rebuilt `portfolio.html` from the WSL clone and `git push`ed. That clone froze at `c98c236` (2026-09-21), diverged 30/22 from origin, and its page still carried the Snapshot block. Its pushes had been rejected non-fast-forward since `fed03cd` (2026-08-05) — one `git pull` there would have republished a stale page every weekday. It also overwrites `Documents\CarlosDuarteWebsite\docs\portfolio.html` with that stale page. Do not re-enable; delete when Carlos confirms. |
| Task `LTCMA Daily Refresh` → WSL `daily_refresh.sh` | Disabled since the 2026-06-10 Windows-native migration |
| `~/LTCMA` (WSL clone) | Retired. Never build, commit or push from it |

## Guards that catch a resurrection

- `scripts/guard_no_snapshot.py` — load-bearing in `daily_refresh.ps1`; fails the run
  (before commit) if `portfolio.html` regains the Snapshot `<h2>`, any of the 8 retired
  tiles or the Realized/Combined paragraph, or loses the MXN/USD toggle from Performance.
- If the live site shows content a commit removed: check `git log origin/main -- docs/<page>`
  for the author/message of the last write (the WSL job's commits read
  `Portfolio tracker update YYYY-MM-DD_HH:MM`), then GitHub Pages caching (deploy takes
  ~1 min; fetch with a cache-busting `?n=` query).
