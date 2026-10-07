# -*- coding: utf-8 -*-
"""LTCMA - Step 34: site freshness dashboard (docs/internal/freshness.html, unlinked).

One look tells Carlos whether any tab is stale - by what the page SAYS, not by when it was
rendered. This script does not audit anything itself: it runs pipeline v2 layer 7 (the one
content auditor; SLAs = `content_rule` entries in Trading_Index\\pipeline\\content\\
refresh_manifest.json, extractors = scripts/content_age.py) and renders its verdict.

Why it runs here, inside daily_refresh.ps1, and not only at layer 7's own 09:30 slot:
docs/ is machine-owned (`git clean -fd docs` every run), so a page exists only if a generator
emits it during the refresh; and auditing right after the generators means today's rebuild is
what gets graded (a regime change is caught the same afternoon). Layer 7 is read-only against
the repo; this script writes exactly one file.

Public-safe by construction: it renders the content findings (written public-safe in
content_age.py) and grades - never layer 7's free-text notes, which name host paths. Unlinked
is not private: nothing here may be confidential.

Host-only inputs (layer 7 lives in C:\\Users\\carlo\\Scripts): elsewhere it skips cleanly and
the committed page stays, carrying its own "generated" stamp so its age is visible.
"""
import html
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from design_system import CSS_LINKS
from paths import DOCS, cuser

LAYER7 = Path(cuser("Scripts", "pipeline_v2", "layer7_content_refresh.py"))
STATUS = Path(cuser("Trading_Index", "pipeline", "content", "_content_status.json"))
OUT = Path(DOCS) / "internal" / "freshness.html"

TABS = {  # surface id -> (tab name on the site, page)
    "index": ("Dashboard", "index.html"), "report": ("Full Report", "report.html"),
    "portfolio": ("Portfolio", "portfolio.html"), "strategies": ("Strategies", "strategies.html"),
    "backtest_pages": ("Backtest reports", "strategies.html"),
    "research": ("Research Notes", "research.html"), "stocks": ("Stock Research", "stocks.html"),
    "stock_pages": ("Stock pages", "stocks.html"), "regime": ("Regime Tracker", "regime.html"),
    "projects": ("Projects", "projects.html"), "glossary": ("Glossary", "glossary.html"),
    "stubs": ("Redirect stubs", None),
}
GRADE_CLS = {"GREEN": "g", "AMBER": "a", "RED": "r", "INFO": "i"}
GRADE_TXT = {"GREEN": "Current", "AMBER": "Behind", "RED": "Stale", "INFO": "Info"}


def run_layer7():
    if not LAYER7.exists():
        return False, "layer 7 not present on this host"
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    out = subprocess.run([sys.executable, str(LAYER7), "--quiet"], capture_output=True,
                         text=True, env=env, timeout=600)
    return out.returncode == 0, (out.stdout or out.stderr or "").strip().splitlines()[-1:]


def esc(s):
    return html.escape(str(s), quote=False)


def chip(g):
    return f'<span class="chip {GRADE_CLS.get(g, "i")}">{GRADE_TXT.get(g, g)}</span>'


def main():
    ok, tail = run_layer7()
    if not STATUS.exists():
        print(f"  freshness: skipped ({tail}) - committed page kept")
        return 0
    st = json.load(open(STATUS, encoding="utf-8"))
    gen = datetime.fromisoformat(st["updated"])
    rows, debts = [], set(st.get("requires_manual_update") or [])
    order = {"RED": 0, "AMBER": 1, "GREEN": 2, "INFO": 3}
    surf = sorted(st["surfaces"], key=lambda r: (order.get(r["grade"], 9), r["id"]))
    for r in surf:
        name, page = TABS.get(r["id"], (r["id"], None))
        c = r.get("content") or {}
        f = c.get("findings") or []
        shown = [t for g, t in f if g in ("RED", "AMBER")] or [t for g, t in f][:1]
        if not c:
            shown = ["on cadence" if r.get("render_grade", r["grade"]) == "GREEN"
                     else "rendered late - see the build log"]
        if r["id"] in debts:
            shown.append("hand-written: owed a manual resync")
        link = f'<a href="../{page}">{esc(name)}</a>' if page else esc(name)
        # Status = layer 7's overall grade (render + content + manual debts); Content = the
        # content-age grade alone. One column per question - a report that rendered fine but
        # owes a resync must not read "content stale" or "build stale".
        rows.append(
            f'<tr><td class="tab">{link}</td><td>{chip(r["grade"])}</td>'
            f'<td>{chip(c["grade"]) if c else "&ndash;"}</td>'
            f'<td class="m">{esc(c["content_asof"]) if c.get("content_asof") else "&ndash;"}</td>'
            f'<td class="m n">{"" if c.get("age_days") is None else c["age_days"]}</td>'
            f'<td class="why">{"<br>".join(esc(x) for x in shown[:4])}</td></tr>')
    n = {g: sum(1 for r in st["surfaces"] if r["grade"] == g) for g in ("GREEN", "AMBER", "RED")}
    ev = [e for e in (st.get("events") or [])]
    ev_html = ("".join(f'<li><span class="m">{esc(e["ts"][:16].replace("T", " "))}</span> &middot; '
                       f'{esc(e["type"].replace("_", " "))}: <b>{esc(e.get("from"))} &rarr; '
                       f'{esc(e.get("to"))}</b></li>' for e in ev)
               or "<li>No regime change in the last 7 days.</li>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Site Freshness</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
{CSS_LINKS.replace('href="', 'href="../')}<link rel="stylesheet" href="../style.css">
<style>
.wrap{{max-width:1080px;margin:0 auto;padding:28px 16px 48px}}
.sum{{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 22px}}
.sum div{{border:1px solid #e5e5e5;background:#fff;padding:10px 16px;min-width:0}}
.sum b{{font-family:'JetBrains Mono',monospace;font-size:20px;margin-right:6px}}
.tbl{{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid #e5e5e5;background:#fff;min-width:0}}
table.fr{{border-collapse:collapse;width:100%;min-width:720px;font-size:13.5px}}
.fr th{{text-align:left;font-weight:500;color:#555;border-bottom:1px solid #d4d4d4;padding:9px 10px;white-space:nowrap}}
.fr td{{border-bottom:1px solid #eee;padding:9px 10px;vertical-align:top}}
.fr td.tab{{white-space:nowrap;font-weight:500}}
.fr td.why{{color:#444;line-height:1.5}}
.m{{font-family:'JetBrains Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums;font-size:12.5px}}
.n{{text-align:right}}
.chip{{display:inline-block;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border:1px solid;white-space:nowrap}}
.chip.g{{color:#0a5d3a;border-color:rgba(10,93,58,.35)}}
.chip.a{{color:#8a5a00;border-color:rgba(138,90,0,.4)}}
.chip.r{{color:#7c2d12;border-color:rgba(124,45,18,.45)}}
.chip.i{{color:#6b7280;border-color:#e5e5e5}}
.note{{color:#555;font-size:13.5px;line-height:1.6;max-width:62em}}
ul.ev{{font-size:13.5px;color:#333;line-height:1.7;padding-left:18px}}
</style></head>
<body><main class="wrap">
<p class="note"><a href="../index.html">&larr; Back to the site</a></p>
<h1 style="margin:.2em 0 .1em">Site freshness</h1>
<p class="asof">As of {gen.strftime('%d %b %Y')} &middot; audited {gen.strftime('%H:%M')} CDMX &middot; internal status page, not linked from the site</p>
<p class="note">Every tab is re-rendered each weekday, so a fresh &ldquo;As of&rdquo; stamp
proves nothing about what a page says. <b>Content</b> grades the newest dated content on
each page against its own service level: a research batch, a project&rsquo;s last push, the
end of a backtest, the newest regime input. <b>Status</b> adds whether the page was
regenerated on schedule and any hand-written update it is owed. <i>Behind</i> needs
attention; <i>Stale</i> needs action.</p>
<div class="sum"><div><b>{n['GREEN']}</b>current</div><div><b>{n['AMBER']}</b>behind</div><div><b>{n['RED']}</b>stale</div></div>
<div class="tbl"><table class="fr"><thead><tr><th>Tab</th><th>Status</th><th>Content</th>
<th>Newest content</th><th style="text-align:right">Age (days)</th><th>What it says</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2 style="margin-top:2rem">Regime changes</h2>
<ul class="ev">{ev_html}</ul>
<p class="note">Service levels live in the content manifest and are audited daily before
publication; a stale tab or a regime change also raises a desktop alert. This page is
regenerated with the site.</p>
</main></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"  freshness: {n['GREEN']} current / {n['AMBER']} behind / {n['RED']} stale "
          f"-> {OUT} (layer 7 {'ok' if ok else 'rc!=0'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
