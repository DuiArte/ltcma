#!/bin/bash
# ============================================================================
# Portfolio tracker update routine
#   Reads the GBM holdings Excel, re-prices every holding from Yahoo Finance
#   (BMV .MX listings), rebuilds docs/portfolio.html, mirrors the backup, and
#   commits. Run ON-DEMAND right after you input new holdings into the Excel,
#   or let the weekday after-close schedule run it automatically.
#
#   Excel input : C:\Users\carlo\Downloads\Copy of Carteras DBE 2.xlsx
#                 (update this file with new trades/holdings; the routine reads it)
#   Deploy      : commits locally; set AUTO_PUSH=1 to also push to the live site.
# ============================================================================
export PATH=/home/carlos/.local/bin:$PATH
REPO=/home/carlos/LTCMA
BACKUP=/mnt/c/Users/carlo/Documents/CarlosDuarteWebsite
XLSX="/mnt/c/Users/carlo/Downloads/Copy of Carteras DBE 2.xlsx"
AUTO_PUSH=${AUTO_PUSH:-0}

cd "$REPO" || exit 1
mkdir -p logs
LOG="logs/portfolio_$(date +%Y-%m-%d).log"

# Abort if there is uncommitted work under scripts/ or docs/, so a scheduled run
# never sweeps in-progress code into an auto-commit. Commit or stash, then re-run.
DIRTY=$(git status --porcelain -- scripts docs)
if [ -n "$DIRTY" ]; then
  { echo "===== portfolio update $(date): ABORTED ====="
    echo "Uncommitted changes under scripts/ or docs/ — skipping. Commit or stash,"
    echo "then re-run:"
    echo "$DIRTY"; } | tee -a "$LOG"
  exit 1
fi

{
  echo "===== portfolio update $(date) ====="
  if [ ! -f "$XLSX" ]; then
    echo "  ! holdings Excel not found at: $XLSX"
    echo "    update that file and re-run; aborting."
    exit 1
  fi
  echo "  holdings source: $XLSX (modified $(date -r "$XLSX" '+%Y-%m-%d %H:%M' 2>/dev/null))"

  # rebuild the tracker (reads Excel -> Yahoo BMV prices -> portfolio.html)
  ( cd scripts && python3 18_portfolio.py )

  # mirror backup
  mkdir -p "$BACKUP/docs"
  cp docs/portfolio.html "$BACKUP/docs/" 2>/dev/null && echo "  backup refreshed"

  # commit if changed
  git add docs/portfolio.html
  if git diff --cached --quiet; then
    echo "  no change to commit"
  else
    git commit -m "Portfolio tracker update $(date +%Y-%m-%d_%H:%M)" >/dev/null && echo "  committed"
    if [ "$AUTO_PUSH" = "1" ]; then
      git push && echo "  pushed (live)" || echo "  (push failed — check credentials)"
    else
      echo "  push skipped (run 'git push' to deploy, or set AUTO_PUSH=1)"
    fi
  fi
  echo "===== done $(date) ====="
} 2>&1 | tee "$LOG"
