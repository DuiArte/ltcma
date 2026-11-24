# -*- coding: utf-8 -*-
"""Private inputs: files the site's scripts read that must never sit in this public repo (wave r3s, 2026-11-17).

fx_monthly.csv is a private input of 14_longhistory_regimes.py (13_fx_ingest.py writes it). It lives in PRIVATE_DIR, a
folder outside every git repo and outside OneDrive (Documents/LTCMA_private under Carlos's profile). 13 writes it
there, 14 reads it there, and .gitignore keeps data/fx_monthly.csv out of git, so a stray copy is never committed.

  PRIVATE_DIR          LTCMA_PRIVATE_DATA when it is set (a test points it at a sandbox), else
                       paths.DOCUMENTS / "LTCMA_private"
  path(name)           PRIVATE_DIR / name
  require(name, who)   the path as a str; SystemExit with a clear message when the file is missing
"""
import os
from pathlib import Path

import paths

PRIVATE_DIR = Path(os.environ.get("LTCMA_PRIVATE_DATA") or (paths.DOCUMENTS / "LTCMA_private"))
FX_MONTHLY = "fx_monthly.csv"


def path(name):
    return PRIVATE_DIR / name


def require(name, who):
    """The private input `name` as a path string, or stop `who` with a message that says where it belongs (never
    under data/: that folder is public)."""
    p = path(name)
    if not p.is_file():
        raise SystemExit(
            f"{who}: the private input {p} is missing. It lives only in {PRIVATE_DIR}: restore it there from the "
            f"private backup. Never put it under data/ (that folder is public).")
    return str(p)
