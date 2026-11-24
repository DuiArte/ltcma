# Who writes to the public site — every source, audited 2026-10-06

GitHub Pages publishes `docs/` on `origin/main` (`github.com/DuiArte/ltcma`) verbatim.
Anything that commits to that branch can change the live site. This list exists because
stale clones and duplicate jobs have **resurrected deleted content** before (the retired
Snapshot block on `portfolio.html`; the Jun-18..23 refresh rebase trap). Before adding a
job, script or clone that writes here, check this list — and add yourself to it.

## ✅ Legitimate writers (the only five that push)

| Source | Trigger | What it pushes |
|---|---|---|
| `daily_refresh.ps1` (this repo) | Task Scheduler `daily-website-refresh` | all generated `docs/` + `data/`; runs `scripts/*.py`, load-bearing guards (`guard_decimals`, `guard_no_snapshot`, `guard_vendor_names` since wave r3s), then `git commit` + `git push origin main` |
| `weekly_model_rebuild.ps1` (this repo) | Task Scheduler `weekly-model-rebuild` (Sun 22:00) | model outputs 01-04 + risk/MC; step 3c (wave 14) rebuilds the stock picker's PRIVATE capstone inputs in `~\capstone\data\analytics\` with `scripts/capstone_inputs_refresh.py` (outside the repo, never committed; skipped under -BuildOnly); shares the `Global\LTCMA_REPO_LOCK` mutex with the daily job |
| `C:\Users\carlo\Scripts\market_intel_monthly.ps1` (Market Intel Track A, added 2026-10-07) | Task Scheduler `market-intel-monthly` (Mon–Fri 07:00 since 2026-11-10; was day 1, 07:00): checks the publishers every weekday and commits **only on a new publisher edition** (a day with nothing new: no LLM call, no commit) | **only** `data/market_intel/consensus_public.json` + `docs/ltcma-consensus.html` (and, since 2026-10-07, the Street LTCMA: `data/market_intel/street_ltcma_{public,editions}.json`, `docs/street-ltcma.html`, `docs/street-ltcma/street_ltcma_<date>_<hash>.{csv,xlsx}` downloadable editions — **held** since the C-20261007-02 take-down, `street.hold` in `config_a.yaml`), via `git commit --only` on those of its paths that exist, under the same `Global\LTCMA_REPO_LOCK` mutex, after `git pull --ff-only`. The daily refresh re-renders the same page from the same JSON (`scripts/30_market_intel.py`, render-only), so both writers emit the same bytes for a given JSON. Builds privately in `Documents\Market_Intel` first. Docs: `Documents\AI_PROCEDURES\MARKET_INTEL_SPEC.md`, `MARKET_INTEL_MONTHLY.md`. |
| `C:\Users\carlo\Scripts\market_intel_weekly.ps1` (Market Intel Track B, added 2026-10-22) | Task Scheduler `market-intel-weekly` (Mon–Fri 08:00 since 2026-11-10; was Mon 08:00): commits **only when a new filing arrived** (no lock, no commit otherwise) | **only** `data/market_intel/congress_public.json` + `docs/congressional-activity.html` (House PTRs from the Clerk + Senate rows from the open mirror), `git commit --only`, under the lock, after `git pull --ff-only`. Docs: `MARKET_INTEL_WEEKLY.md` |
| `C:\Users\carlo\Scripts\market_intel_daily.ps1` (Fed path, added 2026-10-22) | Task Scheduler `market-intel-daily` (Mon-Fri 16:45) | **only** `data/market_intel/fed_path_public.json` + `docs/ltcma-consensus.html` (same generator as the daily refresh, so the same bytes), `git commit --only`, under the lock. Publish failure = alert, never fails its collectors |

`daily_refresh.ps1` also runs `scripts/34_site_freshness.py` (2026-10-07), which writes
exactly one extra file, `docs/internal/freshness.html`, from pipeline v2 layer 7's content audit.

It also runs `scripts/31_research_library.py` (2026-11-10, the Research Library tab behind the header's
"Research" corner), which writes exactly `docs/research-library.html` + `docs/research-library.ai.txt`: an
index of every research item the other generators publish (built from the same data, every link checked against
the pages) and the sources behind the public pages. Render-only, no network. Right after it the refresh runs
`scripts/guard_site_rules.py` (ds_gate R1-R12 on the built pages; writes nothing; R2 also reads every public file under `docs/` and `data/` for the retail-broker / trading-platform names (wave r3s, `scripts/vendor_names.py`); R12 = Congress grouped by filing, the Stock Research phone cards and the fitted Pick Tracker, and the r3 CSS fixes in style.css (sticky table heads, the printed footer, the phone Research menu, with its rules in theme.css, the one-row phone header with the theme control below 360 px; browser half: `tools/layout_browser_check.js`), the Composite Picks pills' `aria-pressed`, the stock pages' justified-P/E n/m clause against their payout and the offset of every "in cash, by choice" note on the portfolio page (the entries and the decisions chart); R11 = the "On this page" bar and note(); R8 = no headline figure shown twice on a page, `scripts/fig_repeats.py`; R9 = dark mode, `tools/theme_gate.py`; R10 = the share head (with its script and the card's alt text), 404 / sitemap / robots, the Plotly bundle, one Fed vintage on the whole page, the Congress money format). Dark mode (2026-11-10 wave r2) adds one generated file, `docs/_design_system/theme.css`, written by 17 with tokens.css / base.css (`design_system.emit()`); every public generator passes its page through `design_system.themed()`. The deploy's page transformation ships with the sources (`tools/deploy_docs_r2.py`, `tools/theme_transform.py`, the header / head strings in `tools/theme_kit/`): it writes the generated commit of that wave and is the rollback's reverse step (`--reverse`), so neither depends on a local folder. The image heroes (2026-11-10) are
emitted by `scripts/design_system.py` `emit_assets()` from the committed `assets/img/` into `docs/assets/img/`,
byte-identical, by every generator whose page shows one (17, 18, 19, 20, 25, 30, 31; wave r3: one photograph
per page, `design_system.PAGE_HEROES`), so a single job's render (e.g. the 07:00 consensus job running 30 alone)
never leaves a page without its image.
Wave r3 (2026-11-10) adds generated files written by 17 on every build through `design_system.emit_share()`:
`docs/404.html` (GitHub Pages serves it for any missing path), `docs/sitemap.xml`, `docs/robots.txt`, and the share
images (`favicon.svg`, `favicon_32.png`, `apple_touch_180.png`, `og_<tab>.png`) copied byte-identically from the
committed `assets/img/` into `docs/assets/img/` (the same mechanism as the heroes). Every page's head (title, share
meta, favicon, the Plotly bundle) is `design_system.site_head()`, run inside `themed()`; so is the long pages'
sticky "On this page" bar (`design_system.otp_insert`). The r3 deploy's generated commit is written by
`tools/deploy_docs_r3.py` (shipped with the sources; `--reverse` is the rollback's step): it also puts each page's
photograph on the committed pages (`design_system.hero_retrofit`), publishes the new photographs and removes the
retired ones' files from `docs/assets/img/`.

It also runs `scripts/35_bt_replay.py` (2026-10-07), which writes only `data/bt_replay/<key>.json`
(the out-of-sample replays of the public backtests, rendered by `24_backtests.py` on `bt_*.html`
and by `23_strategies.py` on the cards). It imports the private engines at runtime from the
workspaces the hub names and writes no parameters, engine code or trade tapes; host-only (it
skips, leaving the committed files, wherever the private code or the network is missing).

`scripts/25_stock_picks.py` (step 3, since 2026-11-04 `de3fbd2`, the Pick Tracker) also writes
`data/picks_history.csv` (one row per name per NYSE session, session-dated, public values; 14 columns since
wave 14: `on_list`, `list_rule`, `macro_through` appended) and
`data/picks_splits.json`; both are committed by the refresh's `git add docs data`. Its SEC Form 4 cache
lives in `.cache/sec_form4/` (git-ignored, never committed). Since wave 14 also `.cache/insider_px/` (past
Yahoo closes for the insider records; git-ignored). Procedure: `Documents\AI_PROCEDURES\
STOCK_PICKS_TRACKER.md`.

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
  tiles or the Realized/Combined paragraph, or loses the MXN/USD toggle (since 2026-11-10 the page-wide sticky
  switch right before Performance: every figure and every chart follows it, one currency at a time).
- `scripts/guard_vendor_names.py` (wave r3s) — load-bearing in `daily_refresh.ps1`, right after
  `guard_no_snapshot`; fails the run (before commit) if any public file under `docs/` or `data/` names the retail
  broker, its trading platform, the platform's vendor, scripting language or servers, or if a PDF / unknown binary
  file there cannot be read (public = what `git add docs data` would commit: ignored files are not read). A name
  joined to other letters or digits counts too, and so does a long name in any spelling but the brand's own
  (spaced, dashed, other capitals), and so do the platform's short name outside the skills list and the server
  names, its scripting language in any form but its own capitals with a version in one piece (no version, a
  plural, a separator, other capitals) and a file kind with its dot anywhere but right after a file name in the
  list's spelling (alone, or in other capitals); the short name and the language are also ordinary acronyms
  elsewhere. The scrub rewrites none of these, so the guard fails until the text or a phrase rule is fixed. The
  scrub and the scan live in `scripts/vendor_names.py`
  (`python scripts/vendor_names.py --selftest`; `--scan` = the guard). The term list is PRIVATE: it is not in
  this repo, it is read at run time from `Documents\LTCMA_private\vendor_terms.txt` (or the folder
  `LTCMA_PRIVATE_DATA` names) and `--terms` checks it. Without it the guard, R2, confscan and every generator
  that scrubs stop (fail closed; in the refresh, 17_build_site.py stops first). Never copy it into a repo, a
  commit message or a page.
- If the live site shows content a commit removed: check `git log origin/main -- docs/<page>`
  for the author/message of the last write (the WSL job's commits read
  `Portfolio tracker update YYYY-MM-DD_HH:MM`), then GitHub Pages caching (deploy takes
  ~1 min; fetch with a cache-busting `?n=` query).

## Rules for every writer, human or agent (2026-10-07)

Binding site conventions (benchmarks read YTD, money-weighted return = exact IRR, derived
counters, backtest replay labelling, privacy) and the reason for each live in
`C:\Users\carlo\Documents\AI_PROCEDURES\WEBSITE_AGENT_RULES.md`. They are Carlos's decisions:
implement them, don't re-litigate them. The operational minimum:

- **The clone is shared.** Two agents worked in it, uncommitted, at the same time on 10-07.
  - Run `git status` before every commit.
  - Stage only your own paths (`git add <paths>`, never `-A` / `.`).
  - Never commit `docs/` generated while someone else's source edits are uncommitted: their
    nav change gets baked into your pages.
- **Clean before 16:31.** A dirty file outside `docs/`/`data/` makes the daily refresh refuse to run.
- ⛔ **History was rewritten on 2026-10-07** to purge a private file that had been committed
  under `data/`.
  - Every commit SHA older than `8806382` changed.
  - Never `git push --all` or `--tags` from this clone: local refs still hold the old history.
  - Any future rewrite needs Carlos's explicit OK. Take `Global\LTCMA_REPO_LOCK`, abort if
    origin moved or the tree is dirty, rewrite `main` only, then push with
    `--force-with-lease=main:<old-sha>`.
  - **Pending (2026-10-07):** purge commit `e971777`. It added the leaked first Street LTCMA
    version: 9-decimal means, sd, downloads (Market Intel correction C-20261007-02).
    - Carlos approved the purge, but Claude Code's auto-mode classifier blocks agents from
      rewriting history.
    - Strip only that commit's 5 Street blobs (a commit-targeted filter), so later commits keep
      their trees.
    - Then ask GitHub Support to drop cached views of the old SHA.
- **Never write private data under this repo.** That means real or unscaled figures, broker
  exports, trade blotters and private code. Private outputs go to
  `Documents\CarlosDuarteWebsite\real_numbers\`. `.gitignore` blocks `*blotter*.csv`.
- **Private ledgers publish counts only.** Don't name private code bases in page text
  (confscan flags them).
- **The retail broker and its trading platform in general words** (wave r3s, Carlos, 2026-11-17).
  - Public files describe the retail broker whose price data some backtests used, its trading platform, the
    platform's vendor, its scripting language and its servers in general words: "a retail broker", "a retail
    trading platform", "retail-broker M5 data".
  - Keep it true: never name another vendor in its place, never suggest exchange data.
  - Generators call `vendor_names.scrub` on text they did not write (glossary `_bt_redact` /
    `bt_scrub_vendor`, 17, 22, 24). Site-authored text is written neutral in the source.
  - `guard_vendor_names.py` (load-bearing), ds_gate R2 and confscan's last section fail on a slip.
- **New tab:** a generator in `scripts/` run by `daily_refresh.ps1`, a manifest entry with a
  `content_rule`, and a row in this file. The Market Intel and Street LTCMA tabs followed it on
  10-07.
