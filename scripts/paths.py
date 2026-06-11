"""Repo-anchored, OS-aware paths for the LTCMA generators (migration 2026-06-10).

The repo root is ALWAYS resolved from this file's location (scripts/..) — never
from ~/LTCMA. On Windows ~/LTCMA resolves to C:\\Users\\carlo\\LTCMA, a stale
non-git decoy directory (see memory/reference_ltcma_repo_structure.md): writing
there silently builds the wrong site. Anchoring on __file__ makes every script
correct from whichever clone it runs in (Windows native clone, WSL clone, or
the GitHub Actions workspace).

CUSER abstracts Carlos's Windows profile: native C:\\Users\\carlo on Windows,
/mnt/c/Users/carlo under WSL. On the GitHub Actions runner neither exists —
callers already handle missing host files gracefully (fallbacks, warn-and-
continue), so these paths simply not existing there is expected and fine.

Strategy repos (~/SARS, ~/DUO, …), ~/.fred_api_key and ~/capstone live directly
under the user home on BOTH sides, so plain Path.home() keeps working for them.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # the repo checkout
DATA = ROOT / "data"
DOCS = ROOT / "docs"
REPORT = ROOT / "report"

# plain-string forms for scripts that build paths with f"{D}/..."
DATA_S, DOCS_S, REPORT_S = str(DATA), str(DOCS), str(REPORT)

IS_WIN = os.name == "nt"
CUSER = Path("C:/Users/carlo") if IS_WIN else Path("/mnt/c/Users/carlo")
DOWNLOADS = CUSER / "Downloads"
DOCUMENTS = CUSER / "Documents"


def cuser(*parts):
    """str path under Carlos's Windows profile, OS-aware."""
    return str(CUSER.joinpath(*parts))
