#!/bin/bash
# ============================================================================
# LTCMA daily refresh routine
#   1. refresh live public data (best-effort; failures don't abort)
#   2. rebuild the site + low-token AI copies
#   3. mirror a backup to C:\Users\carlo\Documents\CarlosDuarteWebsite
#   4. commit and push the daily refresh (set AUTO_PUSH=0 to stage only)
# Scheduled daily via Windows Task Scheduler -> wsl bash -lc this script.
# ============================================================================
export PATH=/home/carlos/.local/bin:$PATH
REPO=/home/carlos/LTCMA
BACKUP=/mnt/c/Users/carlo/Documents/CarlosDuarteWebsite
AUTO_PUSH=${AUTO_PUSH:-1}

cd "$REPO" || exit 1
mkdir -p logs
LOG="logs/daily_$(date +%Y-%m-%d).log"

# --- Stay in sync with origin so the build always reflects the latest data. ---
# Drift between this WSL build clone and origin was the root cause of the
# "regime tracker stuck on May 2026" wiring gap (audit 2026-06-03): the host
# scheduler only rebuilt 2 pages and this clone never re-pulled, so everything
# else froze at whenever a human last ran the script.
#
# AUTO_PUSH=1  (standalone autonomous mode): this clone commits + pushes, so we
#   keep the original guard — abort on uncommitted scripts/docs work rather than
#   sweep in-progress code into a "Daily refresh" commit (see commit 1c116e1).
# AUTO_PUSH=0  (host-wrapper / build-only mode): the native Windows clone owns
#   git; docs/ + data/ here are throwaway build artifacts, so discard last run's
#   output to let the rebase fast-forward cleanly.
if [ "$AUTO_PUSH" = "1" ]; then
  DIRTY=$(git status --porcelain -- scripts docs)
  if [ -n "$DIRTY" ]; then
    { echo "===== LTCMA daily refresh $(date): ABORTED ====="
      echo "Uncommitted changes under scripts/ or docs/ — skipping so the refresh"
      echo "does not auto-commit in-progress work. Commit or stash these, then re-run:"
      echo "$DIRTY"; } | tee -a "$LOG"
    exit 1
  fi
else
  git checkout -- docs data report 2>/dev/null || true
fi
git pull --rebase origin main 2>&1 | tee -a "$LOG" || echo "(warn: pull --rebase failed; building on local HEAD)" | tee -a "$LOG"

run() { echo "-- $1"; python3 "$1" || echo "   (warn: $1 failed, continuing)"; }

{
  echo "===== LTCMA daily refresh $(date) ====="

  echo "[1/4] refreshing live public data (best-effort)"
  run scripts/08_fetch_signals.py
  run scripts/09_priced_in.py
  run scripts/10_regimes.py
  run scripts/20_regime_tracker.py
  run scripts/19_stock_analysis.py

  echo "[2/4] rebuilding site + AI copies"
  ( cd scripts && python3 17_build_site.py && python3 23_strategies.py && (python3 27_research_notes.py || echo "   (warn: research notes page)") && (python3 25_stock_picks.py || echo "   (warn: stock picks page)") && (python3 21_stock_signals.py || echo "   (warn: signals redirect)") && (python3 18_portfolio.py || echo "   (warn: portfolio tracker)") && (python3 26_real_numbers_refresh.py || echo "   (warn: real_numbers refresh)") && python3 22_ai_copies.py && (python3 24_backtests.py || echo "   (warn: backtests page)") )

  echo "[3/4] mirroring backup -> $BACKUP"
  mkdir -p "$BACKUP"
  cp -r docs    "$BACKUP/" 2>/dev/null
  cp -r report  "$BACKUP/" 2>/dev/null
  cp -r data    "$BACKUP/" 2>/dev/null
  cp    README.md requirements.txt "$BACKUP/" 2>/dev/null
  echo "   backup refreshed ($(date))" > "$BACKUP/_last_refresh.txt"

  echo "[4/4] git"
  if [ "$AUTO_PUSH" = "1" ]; then
    git add -A
    if git diff --cached --quiet; then
      echo "   nothing to commit"
    else
      git commit -m "Daily refresh $(date +%Y-%m-%d)" >/dev/null && echo "   committed"
      git push && echo "   pushed" || echo "   (push failed — check credentials)"
    fi
  else
    echo "   build-only mode (AUTO_PUSH=0): not committing here — the host wrapper"
    echo "   (daily_website_refresh.ps1) copies docs/ + data/ into the native clone"
    echo "   and commits/pushes from there (single source of truth)."
  fi

  echo "===== done $(date) ====="
} 2>&1 | tee "$LOG"
