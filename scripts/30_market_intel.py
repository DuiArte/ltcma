"""LTCMA — Step 30: Market Intel consensus page (docs/ltcma-consensus.html).

Renders the monthly "consensus of the Street" from data/market_intel/consensus_public.json,
which is produced OFF this repo by the Market Intel pipeline (Trading_Index/market_intel,
task market-intel-monthly) and is already publish-safe: numbers only from publishers whose
material may be republished, everything else as qualitative stances (SPEC 4.6).
This step only renders, so it is safe in the daily chain (keeps NAV/design current).
Pure HTML/CSS (no Plotly): the range bars are CSS, so the chart guards have nothing to read.
Docs: Documents/AI_PROCEDURES/MARKET_INTEL_SPEC.md, MARKET_INTEL_MONTHLY.md.
"""
import html
import json
import os
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from glossary import NAV
from design_system import CSS_LINKS
from paths import DATA, DOCS

SRC = os.path.join(DATA, "market_intel", "consensus_public.json")
OUT = os.path.join(DOCS, "ltcma-consensus.html")
ARROW = {"up": ("&#9650;", "up"), "down": ("&#9660;", "dn"), "flat": ("&#9632;", "fl")}
STANCE = {"overweight": "up", "underweight": "down", "neutral": "flat"}
CONV = {"high": "H", "medium": "M", "low": "L"}

CSS = """
.toc{display:flex;flex-wrap:wrap;gap:0;border:1px solid #d4d4d4;margin:0 0 1.6rem;width:fit-content;max-width:100%}
.toc a{font:500 12.5px 'Inter',sans-serif;color:#555;text-decoration:none;padding:8px 16px;
border-right:1px solid #d4d4d4;letter-spacing:.01em;transition:background .12s,color .12s}
.toc a:last-child{border-right:0}
.toc a:hover{background:rgba(10,37,64,.05);color:#111}
@media(max-width:560px){.toc{width:100%}.toc a{flex:1 1 auto;text-align:center;padding:8px 8px}}
.mi-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.mi{border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums;min-width:100%}
.mi th,.mi td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:center;white-space:nowrap}
.mi th{font-weight:500;color:var(--sec);font-size:11px;letter-spacing:.02em;vertical-align:bottom}
.mi th.pub{writing-mode:vertical-rl;transform:rotate(180deg);height:92px;text-align:left;padding:6px 4px}
.mi td.a,.mi th.a{text-align:left;position:sticky;left:0;background:var(--panel);z-index:1;min-width:150px}
.mi tr.g td{background:#f4f4f2;font-weight:600;text-align:left;color:var(--ink,#111);font-size:11.5px;letter-spacing:.04em;text-transform:uppercase}
.mi td.cons{min-width:150px}
.mi td.v{font-family:var(--mono)}
.mi td.x{color:var(--muted);font-style:italic}
.mi td.q{color:var(--muted)}
.ar.up{color:#0f766e}.ar.dn{color:#7c2d12}.ar.fl{color:#9aa5b1}
.cv{font-size:9.5px;color:var(--muted);margin-left:1px}
.rb{position:relative;height:10px;background:#eef0f2;margin:3px 0 0;border-radius:2px}
.rb i{position:absolute;top:0;height:10px;background:#c7d3df}
.rb b{position:absolute;top:-2px;width:2px;height:14px;background:#0a2540}
.rb s{position:absolute;top:-3px;width:8px;height:8px;margin-left:-4px;border:2px solid #0f766e;background:#fff;transform:rotate(45deg);text-decoration:none}
.cn{font-family:var(--mono);font-size:12px}
.legend{font-size:12px;color:var(--sec);margin:.6rem 0 0;line-height:1.7}
.legend .rb{display:inline-block;width:60px;vertical-align:middle;margin:0 4px}
.dv{border:1px solid var(--line);background:var(--panel);padding:14px 16px;margin:0 0 14px}
.dv h3{font-size:15px;margin:0 0 4px}
.dv .meta{font-size:11.5px;color:var(--muted);font-family:var(--mono);margin-bottom:8px}
.dv .sides{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.dv .side{border-left:3px solid #c7d3df;padding-left:10px;font-size:13.5px;line-height:1.5}
.dv .side.bull{border-color:#0f766e}.dv .side.bear{border-color:#7c2d12}
.dv .who{font-size:11.5px;color:var(--sec);font-weight:600;margin-bottom:3px}
.dv .data{font-size:12.5px;color:var(--sec);margin-top:5px}
.dv .watch{font-size:13px;margin-top:9px;color:var(--sec)}
.odds{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.odd{border:1px solid var(--line);background:var(--panel);padding:12px 14px}
.odd h4{margin:0 0 6px;font-size:13.5px}
.odd .ven{font-size:11px;color:var(--muted);margin:6px 0 2px;text-transform:uppercase;letter-spacing:.05em}
.odd .row{display:flex;justify-content:space-between;font-size:13px;gap:8px}
.odd .row span:last-child{font-family:var(--mono)}
.odd .bar{height:4px;background:#eef0f2;margin:1px 0 4px}.odd .bar i{display:block;height:4px;background:#5b7c99}
.sumlist li{margin:0 0 .55rem;line-height:1.55;max-width:60em}
.badge{display:inline-block;font-size:10.5px;font-family:var(--mono);padding:1px 6px;border:1px solid var(--line);color:var(--sec);margin-left:6px;vertical-align:middle}
.prelim{border:1px solid #c7d3df;background:#f5f8fb;padding:10px 14px;font-size:13.5px;margin:0 0 1.2rem;max-width:60em}
@media (max-width:700px){.dv .sides{grid-template-columns:1fr}.mi th.pub{height:80px}}
"""


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def pct(x, nd=1):
    """Decimal half-up (8.95 -> 9.0, 8.05 -> 8.1). Plain f"{x:.1f}" rounds the binary float, so 8.95
    printed 8.9 while 8.05 printed 8.1 (claims audit 2026-10-07). The summary text uses the same rule."""
    if x is None:
        return ""
    return str(Decimal(str(x)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))


def range_bar(st, carlos, lo_ax, hi_ax):
    if not st or not st.get("n"):
        return ""
    span = (hi_ax - lo_ax) or 1.0

    def x(v):
        return max(0.0, min(100.0, (v - lo_ax) / span * 100))
    bar = (f'<div class="rb" title="public range {pct(st["min"])}-{pct(st["max"])}%, IQR {pct(st["q25"])}-{pct(st["q75"])}%, '
           f'median {pct(st["median"])}%"><i style="left:{x(st["min"]):.1f}%;width:{max(x(st["max"]) - x(st["min"]), 0.8):.1f}%;opacity:.45"></i>'
           f'<i style="left:{x(st["q25"]):.1f}%;width:{max(x(st["q75"]) - x(st["q25"]), 0.8):.1f}%"></i>'
           f'<b style="left:{x(st["median"]):.1f}%"></b>')
    if carlos is not None:
        bar += f'<s style="left:{x(carlos):.1f}%" title="this site\'s LTCMA {pct(carlos)}%"></s>'
    return bar + "</div>"


def main():
    if not os.path.exists(SRC):
        print("market intel: no consensus_public.json yet - page not built")
        return
    d = json.load(open(SRC, encoding="utf-8"))
    pubs = d["publishers"]
    num_pubs = [p for p in pubs if p["numbers_shown"] and p.get("n_forecasts")]
    qual_pubs = [p for p in pubs if p not in num_pubs]
    # count FIRMS, not documents (Schroders has a 10y and a 30y document; BlackRock = CMA data + BII
    # weekly). C-20261007-01: the hero said "21 asset managers" for 21 documents from 19 firms.
    firm = lambda p: p.get("firm") or p["publisher"]
    n_docs, n_firms = len(pubs), len({firm(p) for p in pubs})
    # what is ACTUALLY rendered per document (labels must not promise views that are not on the grid)
    has_num = {pid for row in d["matrix"].values() for pid, c in row.items() if "v" in c}
    has_arrow = {pid for row in d["matrix"].values() for pid, c in row.items() if c.get("stance")}
    f_num = {firm(p) for p in pubs if p["id"] in has_num}
    f_view = {firm(p) for p in pubs if p["id"] in has_arrow} - f_num
    f_stance = {firm(p) for p in pubs} - f_num - f_view
    n_firms_num, n_firms_view, n_firms_stance = len(f_num), len(f_view), len(f_stance)
    cols = sorted(num_pubs, key=lambda p: p["short"]) + sorted(qual_pubs, key=lambda p: p["short"])
    carlos = {r["asset"]: r["carlos"] for r in d["diff_carlos"]["rows"]}
    allv = [st[k] for st in d["stats"].values() if st.get("n") for k in ("min", "max")] + list(carlos.values())
    lo_ax, hi_ax = (min(allv) - 0.5, max(allv) + 0.5) if allv else (0, 10)
    run = date.fromisoformat(d["run_date"])
    asof = run.strftime("%d %b %Y")
    official = date.fromisoformat(d["first_official"]).strftime("%-d %b %Y") if os.name != "nt" else \
        date.fromisoformat(d["first_official"]).strftime("%d %b %Y").lstrip("0")

    # ---- summary
    summary = "".join(f"<li>{e(b)}</li>" for b in d.get("summary", []))

    # ---- prediction markets
    odds_html = ""
    pm = d.get("prediction") or {}
    for t in pm.get("topics", []):
        if not t.get("venues"):
            continue
        inner = ""
        for v in t["venues"]:
            inner += (f'<div class="ven">{e(v["venue"])} &middot; <a href="{e(v["url"])}" rel="noopener">market</a> '
                      f'&middot; volume ${v["volume"]:,.0f}</div>')
            for o in v["outcomes"][:4]:
                # Decimal half-up on the probability itself (0.0045 -> 0.5%, not the binary-float 0.4%)
                p = Decimal(str(o["prob"])) * 100
                shown = p.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                inner += (f'<div class="row"><span>{e(o["outcome"])}</span><span>{shown}%</span></div>'
                          f'<div class="bar"><i style="width:{float(shown):.1f}%"></i></div>')
        odds_html += f'<div class="odd"><h4>{e(t["label"])}</h4>{inner}</div>'
    taken = (pm.get("taken_at") or "")[:16].replace("T", " ")

    # ---- matrix
    head = "".join(f'<th class="pub" title="{e(p["publisher"])} — {e(p["product"])}">{e(p["short"])}'
                   f'{"" if p["numbers_shown"] else " *"}</th>' for p in cols)
    rows = ""
    for gname, keys in d["groups"]:
        body = ""
        for k in keys:
            row = d["matrix"].get(k, {})
            st = d["stats"].get(k, {})
            if not row and not st.get("n"):
                continue
            cons = ""
            if st.get("n"):
                cons = (f'<span class="cn">{pct(st["median"])}%</span> <span class="cv">IQR {st["iqr_bp"]}bp &middot; n={st["n"]}</span>'
                        + range_bar(st, carlos.get(k), lo_ax, hi_ax))
            else:
                t = st.get("tally", {})
                if any(t.values()):
                    cons = f'<span class="cv">stances: &#9650;{t.get("up", 0)} &#9632;{t.get("flat", 0)} &#9660;{t.get("down", 0)}</span>'
            cells = ""
            for p in cols:
                c = row.get(p["id"])
                if not c:
                    cells += "<td></td>"
                    continue
                tip = e(c.get("why") or "")
                if "v" in c:
                    meta = []
                    if c.get("hz"):
                        meta.append(f'{c["hz"]:g}y')
                    meta.append(c.get("ccy") or "ccy n/a")
                    meta.append(c.get("basis") or "")
                    if c.get("comp"):
                        meta.append(c["comp"])
                    if c.get("label"):
                        meta.insert(0, c["label"])
                    meta += c.get("flags") or []
                    if c.get("page"):
                        meta.append(f'p.{c["page"]}')
                    title = e(" · ".join(x for x in meta if x)) + (" — " + tip if tip else "")
                    arrow = ""
                    if c.get("stance"):
                        a, cls = ARROW[STANCE[c["stance"]]]
                        arrow = f' <span class="ar {cls}">{a}</span><span class="cv">{CONV.get(c.get("conv"), "")}</span>'
                    cls = "v" if c.get("in_stats") else "v x"
                    cells += f'<td class="{cls}" title="{title}">{pct(c["v"])}{arrow}</td>'
                elif c.get("stance"):
                    a, cls = ARROW[STANCE[c["stance"]]]
                    hover = f'{e(c["stance"])}, {e(c.get("conv"))} conviction' + (f" — {tip}" if tip else "")
                    cells += (f'<td class="q" title="{hover}">'
                              f'<span class="ar {cls}">{a}</span><span class="cv">{CONV.get(c.get("conv"), "")}</span></td>')
                else:
                    cells += "<td></td>"
            body += f'<tr><td class="a">{e(d["labels"].get(k, k))}</td><td class="cons">{cons}</td>{cells}</tr>'
        if body:
            rows += f'<tr class="g"><td class="a">{e(gname)}</td><td colspan="{len(cols) + 1}"></td></tr>' + body

    # ---- divergences
    divs = ""
    for x in d.get("divergences", []):
        if not x.get("headline"):
            continue
        b, br = x.get("bull") or {}, x.get("bear") or {}
        hl = x["headline"]
        # strip a repeated asset label only when the WHOLE label leads the headline (a first-word rule
        # turned "US IG: five neutrals" into "IG: five neutrals" - numbers verifier 2026-10-07)
        for pre in (x["label"], x["label"].split(" (")[0]):
            if hl.lower().startswith(pre.lower() + ":") or hl.lower().startswith(pre.lower() + " "):
                hl = hl[len(pre):].lstrip(" :—-").strip()
                hl = hl[:1].upper() + hl[1:]
                break
        x = {**x, "headline": hl}
        meta = (f'{e(x["type"])} divergence &middot; public IQR {x["iqr_bp"]}bp, n={x["n"]} &middot; stances '
                f'&#9650;{x["tally"]["up"]} &#9632;{x["tally"]["flat"]} &#9660;{x["tally"]["down"]}') if x.get("n") else \
               (f'{e(x["type"])} divergence &middot; stances &#9650;{x["tally"]["up"]} &#9632;{x["tally"]["flat"]} &#9660;{x["tally"]["down"]}')
        divs += (f'<div class="dv"><h3>{e(x["label"])} — {e(x["headline"])}</h3><div class="meta">{meta}</div>'
                 f'<div class="sides"><div class="side bull"><div class="who">Higher-return / positive side: {e(", ".join(b.get("publishers", [])))}</div>'
                 f'{e(b.get("argument"))}<div class="data">Leans on: {e(b.get("data_used"))}</div></div>'
                 f'<div class="side bear"><div class="who">Lower-return / negative side: {e(", ".join(br.get("publishers", [])))}</div>'
                 f'{e(br.get("argument"))}<div class="data">Leans on: {e(br.get("data_used"))}</div></div></div>'
                 f'<div class="watch"><b>What would settle it:</b> {e(x.get("what_to_watch"))}</div></div>')
    if not divs:
        divs = '<p class="note">No row crossed the divergence rule this month.</p>'

    # ---- vs this site's LTCMA
    car_rows = ""
    for r in d["diff_carlos"]["rows"]:
        if r.get("gap_bp") is None:
            car_rows += (f'<tr><td style="text-align:left">{e(r["label"])}</td><td>{pct(r["carlos"])}%</td>'
                         f'<td colspan="4" style="color:var(--muted)">no public estimate this month</td></tr>')
            continue
        side = {"above": "this site above the band", "below": "this site below the band", "inside": "inside"}[r["carlos_side"]]
        band = f'{pct(r["band"][0])}-{pct(r["band"][1])}%'
        car_rows += (f'<tr><td style="text-align:left">{e(r["label"])}</td><td>{pct(r["carlos"])}%</td>'
                     f'<td>{pct(r["public_median"])}%</td><td>{r["gap_bp"]:+d}</td><td>{band}</td>'
                     f'<td style="text-align:left">{side} (n={r["public_n"]})</td></tr>')

    # ---- changes vs last month
    dp = d.get("diff_prior") or {}
    if not dp.get("available"):
        changes = f'<p class="note">{e(dp.get("note") or "First edition.")} The first official monthly comparison will appear here after the {official} run.</p>'
    else:
        ch = "".join(f'<tr><td style="text-align:left">{e(r["label"])}</td><td>{pct(r.get("median_prior"))}%</td>'
                     f'<td>{pct(r["median_now"])}%</td><td>{r.get("delta_bp", 0):+d}</td></tr>' for r in dp.get("assets", [])[:15])
        changes = (f'<p class="note">Versus the {e(dp["prior_month"])} edition. New editions this month: '
                   f'{e(", ".join(dp.get("new_editions", [])) or "none")}.</p>'
                   f'<div class="tile" style="overflow-x:auto"><table class="ptable"><thead><tr><th style="text-align:left">Asset class</th>'
                   f'<th>Prior median</th><th>Now</th><th>Change (bp)</th></tr></thead><tbody>{ch}</tbody></table></div>')

    # ---- regimes
    by_id = {p["id"]: p for p in pubs}
    dup = {n for n in [p["publisher"] for p in pubs] if [q["publisher"] for q in pubs].count(n) > 1}

    def reg_row(r):
        p = by_id.get(r.get("id"), {})
        name = p.get("short") if r["publisher"] in dup else r["publisher"]     # "Schroders 10y" vs "Schroders 30y"
        if r.get("restricted"):          # stance only; the publisher's own text is not republished
            orig = (f'<a href="{e(p["url"])}" rel="noopener">see the original</a>' if p.get("url") else "see the original")
            call = f'<span style="color:var(--muted)">not republished &mdash; {orig}</span>'
            risks = ""
        else:
            call, risks = e(r.get("summary")), e("; ".join(x for x in r.get("risks", []) if x))
        return (f'<tr><td style="text-align:left">{e(name)}</td><td>{e(r.get("risk_stance"))}</td>'
                f'<td style="text-align:left;white-space:normal">{e(r.get("cycle_phase") or "—")}</td>'
                f'<td style="text-align:left;white-space:normal;min-width:260px">{call}</td>'
                f'<td style="text-align:left;white-space:normal;min-width:200px">{risks}</td></tr>')
    reg = "".join(reg_row(r) for r in d.get("regimes", []))

    # ---- sources
    def shown_label(p):
        # from what the grid ACTUALLY shows (verifier 2026-10-07: "numbers + views" was printed for
        # publishers with no arrows on the page)
        parts = (["numbers"] if p["id"] in has_num else []) + (["stated views"] if p["id"] in has_arrow else [])
        label = " + ".join(parts) if parts else "regime stance only"
        return label + ("" if p["numbers_shown"] else " *")

    src_rows = ""
    for p in sorted(pubs, key=lambda p: p["publisher"]):
        link = f'<a href="{e(p["url"])}" rel="noopener">original</a>' if p.get("url") else ""
        hz = f'{p["horizon"]:g}y' if isinstance(p.get("horizon"), (int, float)) else "—"
        src_rows += (f'<tr><td style="text-align:left">{e(p["publisher"])}</td><td style="text-align:left;white-space:normal">{e(p["product"])}</td>'
                     f'<td style="text-align:left;white-space:normal">{e(p.get("edition"))}</td><td>{hz}</td><td>{e(p.get("basis") or "—")}</td>'
                     f'<td>{shown_label(p)}</td><td>{link}</td></tr>')
    pending = ", ".join(d.get("inbox_pending", []))
    prelim = ""
    if d.get("edition") == "preliminary":
        prelim = (f'<div class="prelim"><b>Preliminary edition.</b> Built from {n_docs} documents by {n_firms} firms that are '
                  f'reachable today; the first official monthly run is {official}. Still to come through the manual '
                  f'channel: {e(pending)}.</div>')

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="ltcma-content-asof" content="{d['run_date']}">
<title>Carlos Duarte — Market Intel: Street consensus</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
{CSS_LINKS}<link rel="stylesheet" href="style.css"><style>{CSS}</style></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Market Intel — what the Street expects</h1>
<p class="lede">Long-run expected returns and outlooks from {n_firms} asset managers and banks ({n_docs} documents), put on one
grid in US dollars (nominal) and set against this site's own capital market assumptions. Where the
publishers disagree, both sides of the argument are laid out with the evidence each one leans on.
Prediction-market odds for the macro calls are shown alongside.</p>
<p class="asof">Consensus as of {asof} &middot; {"preliminary edition" if d.get("edition") == "preliminary" else "monthly edition"} &middot; {n_firms_num} firms with numbers shown, {n_firms_view} with stated views only, {n_firms_stance} with a regime stance only</p>
</div></section>
<main class="container">
<div class="toc"><a href="#summary">Summary</a><a href="#odds">Market-implied odds</a><a href="#matrix">The grid</a>
<a href="#divergences">Divergences</a><a href="#vs-ltcma">vs this site's LTCMA</a><a href="#changes">Changes</a>
<a href="#regimes">Regime calls</a><a href="#sources">Sources &amp; method</a></div>
{prelim}
<section class="block" id="summary"><h2>Summary</h2><ul class="sumlist">{summary}</ul></section>

<section class="block" id="odds"><h2>Market-implied odds</h2>
<p class="note">Prices on Kalshi and Polymarket, read from their public market data (snapshot {e(taken)} CDMX).
A price of 0.83 means the market pays out as if the event were 83% likely. Thin markets are skipped.</p>
<div class="odds">{odds_html or '<p class="note">No snapshot available.</p>'}</div></section>

<section class="block" id="matrix"><h2>The grid — expected annual return, % nominal</h2>
<p class="note">Each publisher's long-horizon forecast for the asset class (the horizon closest to 12 years when several
are given). <b>Consensus</b> is the median of the publishers shown with numbers, in USD only; the bar spans their range,
the dark box their middle half, the tick the median and the diamond this site's LTCMA. Hover a cell for horizon,
currency and source page. Arrows are the publisher's own stated view: &#9650; overweight / positive, &#9632; neutral,
&#9660; underweight / negative, with conviction H/M/L. Grey italics = shown but excluded from the consensus
(not in USD, or an arithmetic mean with no volatility to convert it).
* = numbers not republished here; only the publisher's stated views are shown.</p>
<div class="tile mi-wrap"><table class="mi"><thead><tr><th class="a">Asset class</th><th>Consensus</th>{head}</tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="legend">Range bar: <span class="rb" style="display:inline-block"><i style="left:5%;width:90%;opacity:.45"></i><i style="left:30%;width:40%"></i><b style="left:50%"></b><s style="left:80%"></s></span>
light = full range, dark = middle half, tick = median, diamond = this site.</p></section>

<section class="block" id="divergences"><h2>Material divergences</h2>
<p class="note">Rows where the publishers materially disagree: {e(d.get("divergence_rule"))}. Arguments are
paraphrased from the publishers' own documents.</p>{divs}</section>

<section class="block" id="vs-ltcma"><h2>Versus this site's LTCMA</h2>
<p class="note">This site's headline expected return (12-year horizon, blend &lambda;=0.5; model version
{e(d["diff_carlos"].get("model_built"))}, captured at the consensus run) against the public median. The comparison is a cross-check: no
publisher number is ever an input to this site's model. Band = middle half of the public estimates
(full range when fewer than four). Gap (bp) = public median minus this site, computed from unrounded
values (so it can differ slightly from the rounded percentages shown); positive means this site is below
the median.</p>
<div class="tile" style="overflow-x:auto"><table class="ptable"><thead><tr><th style="text-align:left">Asset class</th>
<th>This site</th><th>Public median</th><th>Gap (bp)</th><th>Band</th><th style="text-align:left">Position</th></tr></thead>
<tbody>{car_rows}</tbody></table></div></section>

<section class="block" id="changes"><h2>What changed since last month</h2>{changes}</section>

<section class="block" id="regimes"><h2>Regime calls and risks</h2>
<p class="note">Each publisher's read of the cycle and the risks it flags, paraphrased.</p>
<div class="tile" style="overflow-x:auto"><table class="ptable"><thead><tr><th style="text-align:left">Publisher</th><th>Risk stance</th>
<th style="text-align:left">Cycle</th><th style="text-align:left">Call</th><th style="text-align:left">Key risks</th></tr></thead><tbody>{reg}</tbody></table></div></section>

<section class="block" id="sources"><h2>Sources &amp; method</h2>
<div class="tile" style="overflow-x:auto"><table class="ptable"><thead><tr><th style="text-align:left">Publisher</th><th style="text-align:left">Document</th>
<th style="text-align:left">Edition</th><th>Horizon</th><th>Basis</th><th>Shown</th><th></th></tr></thead><tbody>{src_rows}</tbody></table></div>
<p class="note" style="margin-top:1rem"><b>Method.</b> Documents are collected monthly from the publishers' public pages.
Each one is read into a fixed schema by a language model that must quote every number verbatim. A number that cannot be found in the
document text is dropped. Ranges become midpoints. Real forecasts become nominal using the publisher's own inflation assumption.
Arithmetic averages become geometric with the publisher's own volatility (g = a &minus; &sigma;&sup2;/2), so every figure compounds the same way.
Proxies are tagged on hover (e.g. a Eurozone index in the Europe row, a total-market index in US large cap).
Horizons and currencies are never adjusted: they are labelled, and non-USD figures stay out of the consensus. Only publishers whose
material may be republished appear with numbers; the rest appear as their stated views, with a link to the original.
Prediction-market odds are read-only public prices. Figures are the publishers' own estimates, not this site's, and nothing
here is investment advice.</p></section>
</main>
<footer class="shell-foot"><div class="container"><p>Third-party forecasts are attributed to their publishers and
linked to the originals. Not investment advice.</p></div></footer>
</body></html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"ltcma-consensus.html built ({len(pubs)} publishers, {len(d['matrix'])} rows, {len(d.get('divergences', []))} divergences)")
    render_street()


# ---- Street LTCMA page (decision D14, Carlos 2026-10-07) -------------------------------------
STREET_SRC = os.path.join(DATA, "market_intel", "street_ltcma_public.json")
STREET_IDX = os.path.join(DATA, "market_intel", "street_ltcma_editions.json")
STREET_OUT = os.path.join(DOCS, "street-ltcma.html")


def render_street():
    """Compiled consensus of every firm with numbers, AGGREGATES ONLY: trimmed mean at 0.1, firm count
    and list; rows withheld unless no single firm's figure can be narrowed from them (disclosure gate,
    correction C-20261007-02: no dispersion, no unrounded gap). Built off-repo by
    Trading_Index/market_intel (export_street_ltcma.py -> publish_street_ltcma.py); render-only here."""
    if not os.path.exists(STREET_SRC):
        print("street LTCMA: no street_ltcma_public.json yet - page not built")
        return
    s = json.load(open(STREET_SRC, encoding="utf-8"))
    idx = json.load(open(STREET_IDX, encoding="utf-8")) if os.path.exists(STREET_IDX) else {"editions": []}
    ed = date.fromisoformat(s["edition_date"])
    asof = ed.strftime("%d %b %Y")
    rows_html = ""
    for r in s["rows"]:
        site = pct(r.get("site_ltcma")) + "%" if r.get("site_ltcma") is not None else "—"
        star = " &#9733;" if r.get("in_site_ltcma") else ""
        if r["published"]:
            gap = f'{r["gap_bp"]:+d}' if r.get("gap_bp") is not None else "—"
            firms = e(", ".join(r["firms"]))
            rows_html += (f'<tr><td style="text-align:left">{e(r["label"])}{star}</td>'
                          f'<td><b>{pct(r["street_ltcma"])}%</b></td><td>{r["n_firms"]}</td>'
                          f'<td>{site}</td><td>{gap}</td>'
                          f'<td style="text-align:left;white-space:normal;min-width:240px;font-size:12px;color:var(--sec)">{firms}</td></tr>')
        else:
            rows_html += (f'<tr style="color:var(--muted)"><td style="text-align:left">{e(r["label"])}{star}</td>'
                          f'<td colspan="2" style="font-style:italic">withheld (see Method)</td><td>{site}</td><td>—</td><td></td></tr>')
    eds = ""
    for x in idx.get("editions", []):
        dd = date.fromisoformat(x["date"]).strftime("%d %b %Y")
        tag = "preliminary" if x.get("edition") == "preliminary" else "monthly"
        eds += (f'<tr><td style="text-align:left">{dd}</td><td>{tag}</td><td>{x["rows_published"]}</td>'
                f'<td>{x["firms"]}</td><td><a href="{e(x["csv"])}" download>CSV</a></td>'
                f'<td><a href="{e(x["xlsx"])}" download>XLSX</a></td></tr>')
    n_pub = sum(1 for r in s["rows"] if r["published"])
    n_site = sum(1 for r in s["rows"] if r["published"] and r.get("in_site_ltcma"))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="ltcma-content-asof" content="{s['edition_date']}">
<title>Carlos Duarte — Street LTCMA</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
{CSS_LINKS}<link rel="stylesheet" href="style.css"><style>{CSS}</style></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Street LTCMA — the compiled consensus</h1>
<p class="lede">One set of long-run capital market assumptions compiled from {s['n_firms_total']} asset managers and banks,
in the same asset classes as this site's own LTCMA. Each figure is a consensus across firms, never a single
firm's forecast. This site's model is shown next to it as a cross-check, and every monthly edition stays
available for download below.</p>
<p class="asof">Street consensus as of {asof} &middot; {"preliminary edition" if s.get("edition") == "preliminary" else "monthly edition"} &middot; {n_pub} asset classes published ({n_site} of this site's 24)</p>
</div></section>
<main class="container">
<div class="toc"><a href="#table">The Street LTCMA</a><a href="#editions">Editions &amp; downloads</a><a href="#method">Method</a></div>

<section class="block" id="table"><h2>Expected annual return, % nominal (USD)</h2>
<p class="note"><b>Street LTCMA</b> = trimmed mean across firms (the single highest and lowest estimates are dropped),
rounded to 0.1. <b>Gap</b> = Street minus this site's LTCMA, both as shown, in bp (positive: this site is below
the Street). &#9733; = an asset class of this site's LTCMA. A withheld row does not meet the publication rule
(see Method). Firm-by-firm figures are on the <a href="ltcma-consensus.html">Market Intel</a> grid for the firms
whose material may be republished.</p>
<div class="tile" style="overflow-x:auto"><table class="ptable"><thead><tr><th style="text-align:left">Asset class</th>
<th>Street LTCMA</th><th>Firms</th><th>This site's LTCMA</th><th>Gap (bp)</th>
<th style="text-align:left">Contributing firms</th></tr></thead><tbody>{rows_html}</tbody></table></div></section>

<section class="block" id="editions"><h2>Editions &amp; downloads</h2>
<p class="note">Every published edition is kept. Each file holds the aggregates exactly as shown above
(no individual firm's figures).</p>
<div class="tile" style="overflow-x:auto"><table class="ptable"><thead><tr><th style="text-align:left">Edition</th>
<th>Type</th><th>Asset classes</th><th>Firms</th><th>CSV</th><th>Excel</th></tr></thead><tbody>{eds}</tbody></table></div></section>

<section class="block" id="method"><h2>Method</h2>
<p class="note">Each firm's long-run expected returns are read from its own published capital market assumptions
(collected monthly). Every number is quoted verbatim from the source and machine-checked against the
document. Figures are put on one basis: US dollars, nominal, geometric (compound). Real forecasts are made
nominal with the firm's own inflation assumption, and arithmetic averages are converted with the firm's own
volatility. Each firm counts once per asset class, using the horizon closest to 12 years; non-USD figures are left out.
A trimmed mean is used rather than a median so that no single firm's number can be read off the table; for the
same reason no minimum, maximum, quartile or spread is shown, and every figure is rounded to 0.1.
Some contributing firms do not permit their figures to be republished individually; they appear here only
inside these aggregates. A row is therefore published only when at least 5 firms give a figure, either none or
at least 3 of them are such firms, and an automated check confirms that none of their figures can be narrowed
to within &plusmn;0.5 percentage points from everything published on this site, earlier editions included.
Other rows are withheld. Firms whose material is not for public distribution are left out entirely. This
consensus is a cross-check: it is never an input to this site's LTCMA model. Not investment advice.</p></section>
</main>
<footer class="shell-foot"><div class="container"><p>Aggregated from the published capital market assumptions of the
firms listed. Not investment advice.</p></div></footer>
</body></html>"""
    with open(STREET_OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"street-ltcma.html built ({n_pub} rows, {len(idx.get('editions', []))} edition(s))")


if __name__ == "__main__":
    main()
