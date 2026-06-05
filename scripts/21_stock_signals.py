"""Stock Signals — MERGED into the Stocks page (Carlos, 2026-06-04).

The macro factor exposures (β to rates / dollar / CAD) and post-FOMC reaction
tables that used to live on signals.html now render inside docs/stocks.html via
25_stock_picks.py (the "Macro Factor Signals" section), and those same variables
feed the composite picker. This script now writes a meta-refresh redirect so any
existing links to signals.html keep working.
"""
import os

DOCS = os.path.expanduser("~/LTCMA/docs")
REDIRECT = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta http-equiv="refresh" content="0; url=stocks.html#signals">'
    '<link rel="canonical" href="stocks.html">'
    '<title>Stock Signals have moved to Stock Research</title>'
    '<meta name="robots" content="noindex"></head><body>'
    '<p style="font-family:sans-serif;margin:3rem">Stock Signals has merged into '
    '<a href="stocks.html#signals">Stock Research</a>. Redirecting…</p>'
    '</body></html>')

if __name__ == "__main__":
    open(f"{DOCS}/signals.html", "w", encoding="utf-8").write(REDIRECT)
    print("signals.html -> redirect to stocks.html#signals")
