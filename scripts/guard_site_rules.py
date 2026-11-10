"""LTCMA - site rules R1-R7 on the pages the refresh just built (2026-11-10 remake, round 1: P3 / P9).

Runs tools/ds_gate.py's remake rules -- R1 header + reachability, R2 Street held, R3 hero credits, R4 assets /
budgets, R5 no image metadata, R6 the home summary against the pages it restates (vintage-aware), R7 the Research
Library's links, coverage and sources -- right after 31_research_library.py in daily_refresh.ps1. Best-effort:
a failure is logged as a WARN by the refresh (it publishes nothing and never blocks the build); the same rules
run in full with `python tools/ds_gate.py`. Read-only: writes nothing.
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ds_gate", os.path.join(_HERE, "..", "tools", "ds_gate.py"))
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)

if __name__ == "__main__":
    sys.exit(_gate.rules_gate())
