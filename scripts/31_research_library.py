"""LTCMA - Step 31: the Research Library (docs/research-library.html + research-library.ai.txt), 2026-11-10.

Carlos (written, 2026-11-10 ~01:20): "pon la parte de research en un rincon que se pueda explorar mejor. El
fundamento de todo esto, las fuentes". The header's Research corner (glossary.NAV) opens on every page; this
is its hub: (a) how the site is built in three lines, (b) a searchable, filterable index of EVERY research
item already published, generated from the same data the research pages are built from (scripts/research_index.py),
and (c) #sources: every external source behind a public page, each verified against a public generator.

Runs in daily_refresh.ps1 AFTER 24_backtests.py (it indexes the pages 17/23/27/19/24 publish, and checks every
link against them) and before 34_site_freshness.py. Best-effort: an item whose page or anchor is missing, or a
source whose evidence no longer holds, is LEFT OUT and printed as WARN -- the page never links to a missing
anchor. Round 1 (P3): the page is still written, and the script then EXITS 2 so the refresh logs the problem
("31_research_library.py failed (continuing)" + the WARN lines); guard_site_rules.py (ds_gate R1-R7) runs right
after it. Render-only: no network, writes docs/ only.
"""
import sys
import html
import json
import os
import re
from collections import Counter
from datetime import date

import research_index as ri
from design_system import CSS_LINKS, hero, credits_footer
from design_system import themed   # 2026-11-10 wave r2: dark mode (head boot + colour tokens)
from glossary import NAV
from paths import DATA, DOCS

OUT = os.path.join(str(DOCS), "research-library.html")
AI_OUT = os.path.join(str(DOCS), "research-library.ai.txt")
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600'
         '&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">')
e = lambda s: html.escape(str(s if s is not None else ""), quote=True)

CSS = """
.found{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));counter-reset:f}
.found .xcard{position:relative}
.found .links{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13.5px}
.found .links a{font-weight:500}
.libctl{display:none;flex-direction:column;gap:12px;margin:0 0 18px;padding:16px;border:1px solid var(--line);
  border-radius:16px;background:var(--panel)}
.js .libctl{display:flex}
.libctl .row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.libctl input[type=search]{flex:1 1 260px;min-width:0;min-height:44px;padding:0 14px;border:1px solid var(--line-strong);
  border-radius:12px;font:400 15px var(--sans);color:var(--ink);background:var(--bg)}
.libctl select{min-height:44px;padding:0 10px;border:1px solid var(--line-strong);border-radius:12px;font:400 14px var(--sans);
  background:var(--panel);color:var(--ink)}
.libctl .g{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.libctl .g>span{font-size:11.5px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:var(--sec);min-width:5.6em}
.libctl .cnt{font:400 13px var(--mono);color:var(--sec)}
.libctl .chipbtn small{font:400 11px var(--mono);color:inherit;opacity:.7;margin-left:6px}
.libctl .chipbtn.zero{opacity:.45}
.lib-empty{margin:4px 0 16px;padding:16px;border:1px dashed var(--line-strong);border-radius:14px;color:var(--sec);
  display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.lib-empty[hidden]{display:none}
/* phones: each filter group is ONE scrolling row (the 28 chips took 933 px before the first item) */
@media(max-width:640px){
  .libctl{padding:12px;gap:10px}
  .libctl .g{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin:0 -12px;padding:0 12px 2px;
    -webkit-mask-image:linear-gradient(to right,#000 calc(100% - 24px),transparent);
            mask-image:linear-gradient(to right,#000 calc(100% - 24px),transparent)}
  .libctl .g::-webkit-scrollbar{display:none}
  .libctl .g>span{flex:none;min-width:0;margin-right:2px}
  .libctl .g .chipbtn{flex:0 0 auto}
}
.lib-list{list-style:none;margin:0;padding:0;display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(min(330px,100%),1fr))}
.lib-item{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;display:flex;
  flex-direction:column;gap:6px;min-width:0}
.lib-item[hidden]{display:none}
.li-top{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:12px;color:var(--sec)}
.li-type{font-weight:500;letter-spacing:.06em;text-transform:uppercase;font-size:11px;color:var(--amber)}
.li-date{font-family:var(--mono)}
.li-out{border:1px solid var(--line);border-radius:999px;padding:1px 9px;font-size:11.5px;color:var(--ink);background:var(--chip)}
.li-title{font-family:var(--serif);font-size:17px;line-height:1.3;color:var(--ink);text-decoration:none;font-weight:500}
.li-title:hover{color:var(--accent);text-decoration:underline;text-underline-offset:2px}
.li-sum{margin:0;font-size:13.5px;color:var(--sec);line-height:1.5}
.li-meta{display:flex;flex-wrap:wrap;gap:4px 8px;font-size:12px;color:var(--muted);margin-top:auto}
.li-meta .tp{border:1px solid var(--line);border-radius:999px;padding:0 8px}
.li-meta a{color:var(--sec)}
.srcs{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(min(360px,100%),1fr))}
.src-card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;display:flex;flex-direction:column;gap:8px;min-width:0}
.src-card h3{margin:0;font:500 17px/1.3 var(--serif)}
.src-card h3 a{color:var(--ink);text-decoration:none}
.src-card h3 a:hover{color:var(--accent);text-decoration:underline}
.src-card p{margin:0;font-size:13.5px;color:var(--sec);line-height:1.5}
.src-card dl{margin:0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;font-size:12.5px}
.src-card dt{color:var(--muted);font-weight:500}
.src-card dd{margin:0;color:var(--ink);overflow-wrap:anywhere}
.src-card .ids{font:400 11.5px/1.6 var(--mono);color:var(--sec);overflow-wrap:anywhere}
.refs{margin:.4rem 0 0 1.2rem;font-size:13.5px;color:var(--sec);line-height:1.55}
.refs li{margin:.35rem 0;overflow-wrap:anywhere}
"""

JS = r"""<script>(function(){var L=document.getElementById('lib-list');if(!L)return;
var items=[].slice.call(L.children),q=document.getElementById('lib-q'),cnt=document.getElementById('lib-count'),
srt=document.getElementById('lib-sort'),emp=document.getElementById('lib-empty'),on={type:{},topic:{},outcome:{}},
chips=[].slice.call(document.querySelectorAll('.libctl [data-g]'));
function vals(li,g){return g==='topic'?(li.getAttribute('data-topics')||'').split('|'):[li.getAttribute('data-'+g)];}
// skip = a group left out of the test: a chip's count is what it would show inside the other active filters
function match(li,skip){var t=(q.value||'').trim().toLowerCase();if(t){var ws=t.split(/\s+/);
 for(var i=0;i<ws.length;i++)if(li.getAttribute('data-q').indexOf(ws[i])<0)return false;}
 for(var g in on){if(g===skip)continue;var ks=Object.keys(on[g]).filter(function(k){return on[g][k];});if(!ks.length)continue;
  var v=vals(li,g);if(!ks.some(function(k){return v.indexOf(k)>=0;}))return false;}return true;}
function apply(){var n=0;items.forEach(function(li){var m=match(li);li.hidden=!m;if(m)n++;});
 cnt.textContent='Showing '+n+' of '+items.length;if(emp)emp.hidden=n>0;
 chips.forEach(function(b){var g=b.getAttribute('data-g'),v=b.getAttribute('data-v'),
  c=items.filter(function(li){return vals(li,g).indexOf(v)>=0&&match(li,g);}).length;
  var sm=b.querySelector('small');if(sm)sm.textContent=c;b.classList.toggle('zero',c===0);
  b.setAttribute('aria-label',v+', '+c+(c===1?' item':' items'));});}
function sort(){var k=srt.value;items.sort(function(a,b){var da=a.getAttribute('data-date')||'',db=b.getAttribute('data-date')||'';
 if(k==='title')return a.getAttribute('data-title').localeCompare(b.getAttribute('data-title'));
 if(k==='type')return (+a.getAttribute('data-tord')-(+b.getAttribute('data-tord')))||db.localeCompare(da);
 if(!da||!db)return da?-1:(db?1:0);return k==='old'?da.localeCompare(db):db.localeCompare(da);});
 items.forEach(function(li){L.appendChild(li);});}
[].forEach.call(document.querySelectorAll('.libctl [data-g]'),function(b){b.addEventListener('click',function(){
 var g=b.getAttribute('data-g'),v=b.getAttribute('data-v');on[g][v]=!on[g][v];b.setAttribute('aria-pressed',on[g][v]?'true':'false');apply();});});
q.addEventListener('input',apply);srt.addEventListener('change',function(){sort();apply();});
function reset(){q.value='';on={type:{},topic:{},outcome:{}};
 chips.forEach(function(b){b.setAttribute('aria-pressed','false');});apply();}
document.getElementById('lib-reset').addEventListener('click',reset);
var er=document.getElementById('lib-empty-reset');if(er)er.addEventListener('click',function(){reset();q.focus();});
try{var u=new URLSearchParams(location.search).get('q');if(u)q.value=u;}catch(_e){}
sort();apply();})();</script>"""


def chip_group(g, label, counts):
    b = "".join(f'<button type="button" class="chipbtn" data-g="{g}" data-v="{e(k)}" aria-pressed="false" '
                f'aria-label="{e(k)}, {n} item{"" if n == 1 else "s"}">{e(k)}<small aria-hidden="true">{n}</small></button>'
                for k, n in counts)
    return f'<div class="g" role="group" aria-label="Filter by {label.lower()}"><span>{label}</span>{b}</div>'


def item_html(it):
    tord = ri.TYPE_ORDER.index(it["type"]) if it["type"] in ri.TYPE_ORDER else 99
    q = " ".join([it["title"], it["summary"], it["type"], it["outcome"], it["page"], " ".join(it["topics"])]).lower()
    out = f'<span class="li-out">{e(it["outcome"])}</span>' if it["outcome"] else ""
    ext = (f' &middot; <a href="{e(it["external"])}" rel="noopener">repository &#8599;</a>' if it["external"] else "")
    tps = "".join(f'<span class="tp">{e(t)}</span>' for t in it["topics"])
    return (f'<li class="lib-item" id="i-{e(it["id"])}" data-type="{e(it["type"])}" data-topics="{e("|".join(it["topics"]))}" '
            f'data-outcome="{e(it["outcome"])}" data-date="{e(it["date"])}" data-title="{e(it["title"].lower())}" '
            f'data-tord="{tord}" data-q="{e(q)}">'
            f'<div class="li-top"><span class="li-type">{e(it["type"])}</span>'
            f'<span class="li-date">{e(it["date_label"])}</span>{out}</div>'
            f'<a class="li-title" href="{e(it["href"])}">{e(it["title"])}</a>'
            + (f'<p class="li-sum">{e(it["summary"])}</p>' if it["summary"] else "")
            + f'<div class="li-meta"><span>{e(it["page"])}</span>{tps}{ext}</div></li>')


def source_html(s, extra=""):
    key, name, provides, pages, cadence, link, terms, _ev = s
    pg = ", ".join(f'<a href="{e(h)}">{e(t)}</a>' for h, t in pages if os.path.exists(os.path.join(str(DOCS), h.split("#")[0]))
                   or h.split("#")[0] == "research-library.html")
    rel = ' rel="noopener"' if link.startswith(("http://", "https://")) else ""
    return (f'<article class="src-card" id="src-{e(key)}"><h3><a href="{e(link)}"{rel}>{e(name)}</a></h3>'
            f'<p>{e(provides)}</p><dl><dt>Used on</dt><dd>{pg}</dd><dt>Updated</dt><dd>{e(cadence)}</dd>'
            f'<dt>Terms</dt><dd>{e(terms)}</dd></dl>{extra}</article>')


def main():
    items = ri.build_items()
    probs = ri.check_items(items)
    bad_ids = {p.split(":")[0] for p in probs if ":" in p}
    keep = [it for it in items if it["id"] not in bad_ids]
    for p in probs:
        print(f"  WARN research library: {p}" + (" -- item left out" if p.split(":")[0] in bad_ids else ""))
    src_checked = ri.check_sources()
    srcs = []
    n_src_bad = 0
    for s, ok, why in src_checked:
        if ok:
            srcs.append(s)
        else:
            n_src_bad += 1
            print(f"  WARN research library: source {s[0]} left out ({why})")

    n = len(keep)
    # the page's content date = its newest RESEARCH RESULT: findings, discovery batches (the automated pipeline's
    # row included, by its last month) and backtests. Not the projects' last pushes (projects-sync pushes them on
    # weekdays, a heartbeat: P8 / HON-4), not the report edition, not page renders.
    res = [it for it in keep if it["date"] and it["type"] in ("Finding", "Research batch", "Backtest")]
    top = max(res, key=lambda it: it["date"]) if res else None
    newest = top["date"] if top else date.today().isoformat()
    newest_label = ("" if not top else (date.fromisoformat(newest).strftime("%b %Y") if top["type"] == "Research batch"
                                        else ri.nice(newest)))
    by_type = Counter(it["type"] for it in keep)
    tested, tally_asof = ri.tally()
    n_find, n_batch, n_bt = by_type.get("Finding", 0), by_type.get("Research batch", 0), by_type.get("Backtest", 0)
    n_rep = sum(1 for it in keep if it["type"] == "Backtest" and it["href"].startswith("bt_"))
    n_proj = by_type.get("Project", 0)
    try:
        n_proj_all = len(ri.literal("17_build_site.py", "PROJECTS"))
    except (KeyError, OSError, ValueError, SyntaxError):
        n_proj_all = n_proj
    proj_txt = (f"{n_proj} public projects" if n_proj == n_proj_all else
                f"{n_proj} of the {n_proj_all} public projects (all {n_proj_all} are on the Projects page)")
    try:
        import pandas as pd
        n_assets = len(pd.read_csv(os.path.join(str(DATA), "ltcma_summary.csv"), index_col=0))
    except Exception:  # noqa: BLE001
        n_assets = None
    rt = ri.report_target()

    # ---- (a) how the site is built, in three lines
    found = (
        '<div class="found">'
        f'<div class="xcard"><p class="xk"><i>1</i>The foundation: the model</p>'
        + (f'<span class="xbig">{n_assets} asset classes</span>' if n_assets else "")
        + '<p class="xh">A 12-year capital market model: building-block expected returns, a shrunk risk model and a '
          'regime-switching Monte Carlo.</p>'
          f'<div class="links"><a href="{e(rt)}">Full Report</a><a href="index.html#model">Model output on the Dashboard</a></div></div>'
        f'<div class="xcard"><p class="xk"><i>2</i>Research tested against it</p>'
        + (f'<span class="xbig">{tested} signals and strategies tested</span>' if tested else "")
        + f'<p class="xh">{n_find} findings, {n_batch} discovery batches, {n_bt} backtests ({n_rep} with full reports) and '
          f'{proj_txt}, negative results included.</p>'
          '<div class="links"><a href="research.html">Research Notes</a><a href="strategies.html">Strategies</a>'
          '<a href="projects.html">Projects</a></div></div>'
        '<div class="xcard"><p class="xk"><i>3</i>The live surfaces</p><span class="xbig">Every weekday</span>'
        '<p class="xh">What the model and the research feed today: the portfolio, the market and policy signals, '
        'the stock research.</p><div class="links"><a href="index.html">Dashboard</a><a href="portfolio.html">Portfolio</a>'
        '<a href="ltcma-consensus.html">Market Intel</a><a href="congressional-activity.html">Congress</a>'
        '<a href="stocks.html">Stock Research</a><a href="regime.html">Regime Tracker</a></div></div></div>'
        + (f'<p class="note" style="margin-top:1rem">Signals and strategies tested = the public, counts-only tally on '
           f'Research Notes (counted {e(ri.nice(tally_asof))}); the ledger behind it stays private.</p>'
           if tested and tally_asof else ""))

    # ---- (b) the index
    types = sorted(by_type.items(), key=lambda kv: ri.TYPE_ORDER.index(kv[0]) if kv[0] in ri.TYPE_ORDER else 99)
    tops = Counter(t for it in keep for t in it["topics"])
    topics = [(lab, tops[lab]) for lab, _rx in ri.TOPICS if tops.get(lab)]
    outs = sorted(Counter(it["outcome"] for it in keep if it["outcome"]).items(), key=lambda kv: (-kv[1], kv[0]))
    ctl = ('<div class="libctl" role="search" aria-label="Search and filter the research index">'
           '<div class="row"><label for="lib-q" class="sr-only" style="position:absolute;left:-9999px">Search</label>'
           '<input id="lib-q" type="search" placeholder="Search titles and summaries (e.g. gold, momentum, Sharpe)" autocomplete="off">'
           '<select id="lib-sort" aria-label="Sort"><option value="type">By type</option><option value="new">Newest first</option>'
           '<option value="old">Oldest first</option><option value="title">Title A&ndash;Z</option></select>'
           '<button type="button" class="chipbtn" id="lib-reset">Clear</button>'
           f'<span class="cnt" id="lib-count" aria-live="polite">Showing {n} of {n}</span></div>'
           + chip_group("type", "Type", types) + chip_group("topic", "Topic", topics)
           + chip_group("outcome", "Outcome", outs) + '</div>'
           '<p class="lib-empty" id="lib-empty" hidden>No items match this search and these filters. '
           '<button type="button" class="chipbtn" id="lib-empty-reset">Clear the search and filters</button></p>')
    # by type, newest first inside a type, then title: the same order the page's "By type" sort restores
    order = sorted(keep, key=lambda it: it["date"] or "", reverse=True)     # stable: ties keep the source order
    order = sorted(order, key=lambda it: ri.TYPE_ORDER.index(it["type"]) if it["type"] in ri.TYPE_ORDER else 99)
    lst = '<ol class="lib-list" id="lib-list">' + "".join(item_html(it) for it in order) + "</ol>"

    # ---- (c) sources
    cards = ""
    pubs = None
    for s in srcs:
        extra = ""
        if s[0] == "fred":
            ids = ri.fred_series()
            extra = (f'<p class="ids">Series read (daily and monthly): {e(", ".join(ids))}</p>' if ids else "")
        if s[0] == "cma":
            d = ri._consensus()
            if d:
                from design_system import cma_firms
                pubs = cma_firms(d["publishers"])
                extra = (f'<p class="ids">{len(pubs)} firms, {len(d["publishers"])} documents: {e(", ".join(pubs))}. '
                         'Every document, its edition and a link: <a href="ltcma-consensus.html#sources">Market Intel, '
                         'Sources &amp; method</a>.</p>')
        cards += source_html(s, extra)
    refs = ri.references()
    ref_html = "".join(f'<li>{e(t)}' + (f' <a href="{e(u)}" rel="noopener">{e(u)}</a>' if u else "") + "</li>"
                       for t, u in refs)

    inner = (f'<p class="kicker">Research corner</p><h1>Research Library</h1>'
             '<p class="lede">The foundation of this site in one place: the 12-year model, every research note, '
             'backtest and project behind it (negative results included), and the sources every public page is '
             'built from.</p><div class="cta"><a class="btn" href="#library">Explore the index</a>'
             '<a class="btn btn-ghost" href="#sources">See the sources</a></div>'
             f'<p class="asof">{n} items indexed &middot; newest finding, batch or backtest: {e(newest_label)} &middot; '
             f'{len(srcs)} sources &middot; rebuilt every weekday</p>')

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="ltcma-content-asof" content="{newest}">
<title>Carlos Duarte — Research Library</title>
<meta name="description" content="Search every research note, backtest, project and report section published on this site, and see the data sources behind every public page.">
{FONTS}
{CSS_LINKS}<link rel="stylesheet" href="style.css"><style>{CSS}</style></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
{hero("cliffs_detail", inner, str(DOCS), pos="center 45%")}
<main class="container">
<section class="block" id="foundation"><p class="kicker">How this site is built</p><h2>The foundation, in three lines</h2>
{found}</section>
<section class="block" id="library"><p class="kicker">Explore</p><h2>Every research item, in one index</h2>
<p class="note">Everything the research pages publish, generated from the same data they are built from: the Full
Report's sections, the research findings and discovery batches, every backtest in the strategy catalogue, the public
projects and the stock research pages. Search, filter by type, topic and outcome, and sort. Topic tags are assigned by
keyword. Without JavaScript the full list is shown.</p>
{ctl}{lst}</section>
<section class="block" id="sources"><p class="kicker">The foundation: sources</p><h2>Sources behind the public pages</h2>
<p class="note">Every external data source and publisher that feeds a public page, what it provides, where it is used,
how often it is read and its terms. Each one is checked against the code that reads it on every build. The
portfolio's own broker records and the private research projects are inputs, not public sources, and are not listed
(the Portfolio page explains what it shows and how it is scaled).</p>
<div class="srcs">{cards}</div>
<h3 style="margin-top:2rem">Works the Full Report cites</h3>
<p class="note">From the report's references (section 11.3), as published; broker market data is left out here.</p>
<ol class="refs">{ref_html}</ol></section>
<section class="block" id="method"><h2>How this index is built</h2>
<p class="note">Built on every weekday refresh by a script that reads the same structures the research pages are rendered
from, never a hand-typed list. An item whose link or anchor no longer resolves is left out and the refresh log says
so; the site's rule check then confirms every published research page is listed. Private ledgers appear as counts
only. Research and education, not investment advice; backtests are
hypothetical.</p></section>
</main>
<footer class="shell-foot"><div class="container"><p>Research and education, not investment advice. Backtests are
hypothetical.</p>{credits_footer("cliffs_detail")}</div></footer>
{JS}
</body></html>"""
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(themed(page, "research-library.html"))

    ai = [f"RESEARCH LIBRARY (research-library.html) -- {n} items, newest finding / batch / backtest {newest}; "
          f"{len(srcs)} sources",
          "ITEMS: type | date | title | outcome | link"]
    ai += [f"{it['type']} | {it['date'] or '-'} | {it['title']} | {it['outcome'] or '-'} | {it['href']}" for it in order]
    ai += ["", "SOURCES: name | provides | used on | updated | link"]
    ai += [f"{s[1]} | {s[2]} | {', '.join(t for _h, t in s[3])} | {s[4]} | {s[5]}" for s in srcs]
    ai += ["", "REPORT REFERENCES"] + [f"{t} {u}".strip() for t, u in refs]
    with open(AI_OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(ai) + "\n")
    print(f"research-library.html built: {n} items ({', '.join(f'{k} {v}' for k, v in types)}), "
          f"{len(srcs)}/{len(src_checked)} sources, {len(refs)} report references, {len(probs)} problem(s)")
    if probs or n_src_bad:
        # the page is written WITHOUT the bad items; the non-zero exit makes the refresh log it (best-effort step)
        print(f"  WARN research library: {len(probs)} index problem(s), {n_src_bad} source(s) left out -- exit 2")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
