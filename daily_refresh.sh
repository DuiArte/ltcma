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

# Abort if there is uncommitted work under scripts/ or docs/. The auto-commit
# (git add -A) would otherwise sweep in-progress code into a "Daily refresh"
# commit (this happened once, see commit 1c116e1). Commit or stash, then re-run.
DIRTY=$(git status --porcelain -- scripts docs)
if [ -n "$DIRTY" ]; then
  { echo "===== LTCMA daily refresh $(date): ABORTED ====="
    echo "Uncommitted changes under scripts/ or docs/ — skipping so the refresh"
    echo "does not auto-commit in-progress work. Commit or stash these, then re-run:"
    echo "$DIRTY"; } | tee -a "$LOG"
  exit 1
fi

run() { echo "-- $1"; python3 "$1" || echo "   (warn: $1 failed, continuing)"; }

{
  echo "===== LTCMA daily refresh $(date) ====="

  echo "[1/4] refreshing live public data (best-effort)"
  run scripts/08_fetch_signals.py
  run scripts/09_priced_in.py
  run scripts/10_regimes.py
  run scripts/20_regime_tracker.py

  echo "[2/4] rebuilding site + AI copies"
  ( cd scripts && python3 17_build_site.py && python3 23_strategies.py && (python3 18_portfolio.py || echo "   (warn: portfolio tracker)") && python3 22_ai_copies.py && (python3 24_backtests.py || echo "   (warn: backtests page)") )

  echo "[3/4] mirroring backup -> $BACKUP"
  mkdir -p "$BACKUP"
  cp -r docs    "$BACKUP/" 2>/dev/null
  cp -r report  "$BACKUP/" 2>/dev/null
  cp -r data    "$BACKUP/" 2>/dev/null
  cp    README.md requirements.txt "$BACKUP/" 2>/dev/null
  echo "   backup refreshed ($(date))" > "$BACKUP/_last_refresh.txt"

  echo "[4/4] staging git commit"
  git add -A
  if git diff --cached --quiet; then
    echo "   nothing to commit"
  else
    git commit -m "Daily refresh $(date +%Y-%m-%d)" >/dev/null && echo "   committed"
    if [ "$AUTO_PUSH" = "1" ]; then
      git push && echo "   pushed" || echo "   (push failed — check credentials)"
    else
      echo "   push skipped (set AUTO_PUSH=1 to deploy automatically)"
    fi
  fi

  echo "===== done $(date) ====="
} 2>&1 | tee "$LOG"
