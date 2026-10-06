# -*- coding: utf-8 -*-
"""Guard: the retired "Snapshot" block must never come back to portfolio.html.

Carlos removed it 2026-10-06 (commits 6ae3189, 68904ff): its 8 cost-basis tiles
(Market Value / Cost Basis / P&L / Stock + FX contribution / Realized / Unrealized /
Combined return) restated the Performance panel on a different denominator and read
as contradicting it. This repo has a history of stale clones and duplicate jobs
resurrecting deleted content (the WSL `Portfolio Tracker Update` job pushed from a
clone whose portfolio.html still had the block), so the deletion is enforced here.

Matches the TILE MARKUP (`<div class="mk">label</div>`) and the `<h2>`, never bare
words: "FX contribution" legitimately appears in the FX Attribution JS text, and a
guard that fires on prose gets disabled the first week.

Also asserts the opposite direction: the MXN/USD toggle must still exist, at the top
of the Performance section -- Carlos asked for it kept, and it drives every `.cval`.

Exit 1 (load-bearing in daily_refresh.ps1) on any hit -- the refresh fails before it
commits, so a reintroduced Snapshot never reaches GitHub Pages.
Optional arg: path to the HTML to check (default docs/portfolio.html).
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "portfolio.html")

BANNED_TILES = ["Total Market Value", "Total Cost Basis", "Total P&amp;L Since Inception",
                "Total P&L Since Inception", "Stock contribution", "FX contribution",
                "Realized return", "Unrealized return", "Combined return",
                "Total Value"]                       # 26_real_numbers' private variant
MK = re.compile(r'<div class="mk">\s*([^<]+?)\s*</div>', re.I)
H2 = re.compile(r"<h2[^>]*>\s*([^<]*?Snapshot[^<]*?)\s*</h2>", re.I)
PERF = re.compile(r"<h2[^>]*>\s*Performance\s*</h2>(.*?)<h2", re.S | re.I)

html = open(PAGE, encoding="utf-8").read()
bad = []
for h in H2.findall(html):
    bad.append(f"<h2>{h}</h2>")
banned = {b.lower() for b in BANNED_TILES}
for lbl in MK.findall(html):
    if lbl.lower() in banned:
        bad.append(f'tile "{lbl}"')
if "Combined weights the two by their cost bases" in html or \
        re.search(r"<b>Combined</b>\s*weights", html):
    bad.append("Snapshot explanatory paragraph (Realized/Unrealized/Combined)")

perf = PERF.search(html)
if not perf:
    bad.append("Performance section not found")
elif 'class="ccy-toggle"' not in perf.group(1) or "setCurrency('usd')" not in perf.group(1):
    bad.append("MXN/USD toggle missing from the Performance section (must be kept)")

if bad:
    print(f"FAIL guard_no_snapshot: {os.path.basename(PAGE)} -- the retired Snapshot block "
          "is back (or the toggle is gone). See AI_PROCEDURES\\WEBSITE_PUSH_SOURCES.md for "
          "every job that writes this page.")
    for b in bad:
        print(f"  - {b}")
    sys.exit(1)
print(f"OK guard_no_snapshot: no Snapshot block in {os.path.basename(PAGE)}; "
      "MXN/USD toggle present in Performance")
