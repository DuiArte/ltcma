"""Merged Stocks page (docs/stocks.html) — combines the former Stock Analysis and
Stock Signals pages into one, led by a reproducible COMPOSITE PICKER.

Sections, in order:
  1. Composite Picks — every numeric variable from BOTH pipelines (CFA/Buffett
     fundamentals + macro-signal sensitivities), z-scored, weighted by each
     variable's correlation with realised forward returns, ranked. Top 20 = picks.
     Status pills: All / Buy candidates / Watch list.
  2. Macro Factor Signals — the former signals.html content (β to rates/dollar/CAD,
     post-FOMC drift) for the same universe.
  3. Per-company CFA reports — links to the stock_<TICKER>.html tool pages.

Picker internals (the variable WEIGHTS) stay in picker.py and are never rendered;
the cards show the ranked result + each pick's variable contributions only.

Wave 13 (2026-11-04): a Pick Tracker (tenure, since-entry return vs SPY and the universe, exit
estimate, price targets, earnings / analyst / insider / congress overlays) right after Composite
Picks, and a Track Record section. They are built by picks_history / picks_overlays / picks_tracker
inside _tracker_extras(), which NEVER raises: any failure there leaves the core page exactly as it
was, shows "not available today (data gap)" in place of the section and writes one alert line
(YAHOO_ALERT.txt via yahoo_session.alert, tagged as a site gap). The history row is dated by the
NYSE session whose closes it holds (picks_history.price_session), not by the build day. The overlays never change
the composite, the ranks or the weights. stocks.ai.txt keeps its first 4 header lines and its
rank|ticker|sector|price|composite|dominant_var columns; tracker fields are appended at the END.

Wave 14 (2026-11-04, Carlos's written OKs: hysteresis at the rank-20 cut; refresh the frozen capstone macro
inputs; insider name + role + own record). The PUBLISHED list (★, the "Picks" pill, the stocks.ai.txt pick
lines, the Pick Tracker) uses a TWO-SIDED band at the cut (main-session design choice within that OK):
a name already on the list stays while it ranks <= 25; a name off the list ranked <= 15 always enters
(displacing the worst-ranked pick); the remaining places go to the best-ranked names; always 20 names
(picks_history.membership, from the last recorded session before this build's own). If the stored list is
missing or unusable the page publishes the plain top 20 and says so. ai.txt header line 3 names the rule
("rule=band15_25") and, appended (round 3), the dated method changes from the stored history
(picks_tracker.ai_method_tail); its other lines and columns are unchanged. The composite, the ranks and the weights are
byte-identical: only membership changes. The insider detail shows each insider's own past record
(insider_record). XOM's insiders are read from both of its SEC CIKs (insider_form4.PREDECESSOR_CIK).
Macro inputs: capstone_inputs_refresh.py rebuilds the two private parquets every Sunday (weekly_model_rebuild.ps1);
_macro_guard() states their dates in the hero line ("macro inputs: prices through ..., betas through ...") and
alerts when they are older than MACRO_STALE_DAYS. Each history row records the inputs' data-through date
(macro_through), so the Track Record dates the end of the frozen-input period from the history itself. The
signals section names the series' sources only from a trusted sidecar (neutral wording without one).
"""
import os, json, sys, traceback
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from glossary import NAV, ccy_badge
from design_system import CSS_LINKS, axis_formats, assert_no_entities
import picker

from paths import DOCS_S as DOCS  # repo-anchored (2026-06-10)
ANA = picker.ANA
INK, BLUE, GOLD, GREEN, RED, GREY = "#111111", "#0a2540", "#6b7280", "#0a5d3a", "#7c2d12", "#888888"
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">')
SECTOR_C = {
    "Technology": "#0a2540", "Consumer Cyclical": "#6b7280",
    "Communication Services": "#8a3ffc", "Healthcare": "#0a5d3a",
    "Financial Services": "#009d9a", "Consumer Defensive": "#fa4d56",
    "Energy": "#7c2d12", "Industrials": "#555555",
}
# Chart chrome follows the site design system: Inter for labels, JetBrains Mono for
# every NUMBER. "IBM Plex Sans" is NOT in the FONTS <link> above -- asking for it is a
# silent fallback to the generic sans, not an error. See WEBSITE_STYLE_GUIDE.md.
SANS = "Inter, system-ui, -apple-system, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
LAYOUT = dict(template="plotly_white", dragmode=False,
              font=dict(family=SANS, size=12, color=INK),
              title_font=dict(color=INK, size=14, family=SANS),
              margin=dict(l=55, r=20, t=46, b=42),
              paper_bgcolor="white", plot_bgcolor="white",
              hoverlabel=dict(font=dict(family=MONO, size=11, color=INK),
                              bgcolor="rgba(255,255,255,.97)",
                              bordercolor="#d4d4d4", align="left"),
              xaxis=dict(gridcolor="#e5e5e5", tickfont=dict(family=MONO, size=11)),
              yaxis=dict(gridcolor="#e5e5e5", tickfont=dict(family=MONO, size=11)))


def div(fig, name):
    fig = axis_formats(assert_no_entities(fig))
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False,
                               "responsive": True})


# ---------------------------------------------------------------- commentary
# Deterministic, template-driven 1-liner from the dominant signed contributors.
# No model judgement — fully reproducible from the contribution vector.
_POS = {
    "roe": "high quality (ROE)", "gross_marg": "fat gross margins",
    "fcf_yield": "strong free-cash-flow yield", "net_marg": "wide net margins",
    "mos": "a positive margin of safety", "buffett": "a high quality score",
    "rev_growth": "fast revenue growth", "eps_growth": "fast earnings growth",
    "inv_de": "a clean balance sheet", "mom_12_1": "price momentum",
    "inv_pe": "a cheap earnings multiple", "inv_fwd_pe": "a cheap forward multiple",
    "beta_rates": "rate-tailwind positioning", "beta_dxy": "dollar-tailwind positioning",
    "beta_cad": "favourable cross-FX beta", "r2": "high macro explainability",
}
_NEG = {
    "roe": "weak ROE", "gross_marg": "thin gross margins",
    "fcf_yield": "low cash yield", "net_marg": "thin net margins",
    "mos": "a stretched valuation", "buffett": "a low quality score",
    "rev_growth": "slow revenue growth", "eps_growth": "slow earnings growth",
    "inv_de": "elevated leverage", "mom_12_1": "weak momentum",
    "inv_pe": "a rich earnings multiple", "inv_fwd_pe": "a rich forward multiple",
    "beta_rates": "rate-headwind exposure", "beta_dxy": "dollar-headwind exposure",
    "beta_cad": "adverse cross-FX beta", "r2": "noisy macro fit",
}


def commentary(cs):
    pos = cs[cs > 0].sort_values(ascending=False)
    neg = cs[cs < 0].sort_values()
    parts = []
    if len(pos):
        lead = [_POS[k] for k in pos.index[:2]]
        parts.append("Driven by " + " and ".join(lead))
    if len(neg):
        parts.append("offset by " + _NEG[neg.index[0]])
    return ("; ".join(parts) + ".") if parts else "Balanced across signals."


def chips(cs, n=5):
    """Top-n contributors by |magnitude| as +/- chips — direction + relative
    bar, NO weight values (confidentiality)."""
    top = cs.reindex(cs.abs().sort_values(ascending=False).index)[:n]
    mx = cs.abs().max() or 1.0
    out = ""
    for k, v in top.items():
        cls = "cpos" if v >= 0 else "cneg"
        w = max(8, int(round(abs(v) / mx * 46)))
        out += (f'<span class="chip {cls}" title="{picker.FLABEL[k]} '
                f'({"+" if v>=0 else "-"})"><span class="chip-b" style="width:{w}px"></span>'
                f'{picker.FLABEL[k]}</span>')
    return out


def picks_section(df, meta, mem=None):
    """mem = the published list (wave 14: picks_history.membership); None = the plain top 20."""
    contrib = meta["contrib"]
    members = set((mem or {}).get("members") or [tk for tk, r in df.iterrows() if int(r["rank"]) <= 20])
    rows = ""
    for tk, r in df.iterrows():
        cs = contrib.loc[tk]
        rank = int(r["rank"])
        is_pick = tk in members
        status = "buy" if r["composite"] > 0 else "watch"
        sec = str(r["sector"]) or "—"
        color = SECTOR_C.get(sec, GREY)
        comp_cls = "pos" if r["composite"] >= 0 else "neg"
        title = ("Pick (kept by the band: already on the list, still ranked 25 or better)" if rank > 20
                 else "Pick")
        star = f' <span class="pick-star" title="{title}">★</span>' if is_pick else ""
        rows += (
            f'<tr data-status="{status}" data-pick="{1 if is_pick else 0}">'
            f'<td class="rk">{rank}</td>'
            f'<td><b>{tk}</b>{star}<br><span class="tn">{str(r["name"])[:30]}</span></td>'
            f'<td><span class="sec" style="background:{color}">{sec.replace(" Services","")}</span></td>'
            f'<td class="num">${r["price"]:,.2f}</td>'
            f'<td class="num {comp_cls}"><b>{r["composite"]:+.2f}</b></td>'
            f'<td class="chips">{chips(cs)}</td>'
            f'<td class="cmt">{commentary(cs)}</td></tr>')
    n_buy = int((df["composite"] > 0).sum())
    note = ("equal-weight z-score (no forward-return history)" if meta["equal_weight_fallback"]
            else "weighted by each variable's correlation with realised forward returns")
    m = mem or {}
    if m.get("rule", "").startswith("band"):
        kept = [tk for tk in (m.get("kept_by_band") or [])]
        forced, disp = list(m.get("forced") or []), list(m.get("displaced") or [])
        rule = (" The 20 picks (★) follow a two-sided band at the rank-20 cut: a name already on the list stays "
                "while it ranks 25th or better; a name off the list enters as soon as it ranks 15th or better "
                "(it takes the place of the worst-ranked pick); any other free place goes to the best-ranked name "
                "off the list. So a pick can rank 21-25, and a name ranked 16-20 can wait off the list."
                + (f" Today {', '.join(kept)} {'is' if len(kept) == 1 else 'are'} kept by the band." if kept else "")
                + (f" Today {', '.join(forced)} entered by ranking 15th or better"
                   + (f", in place of {', '.join(disp)}." if disp else ".") if forced else ""))
    elif m.get("rule") == "top20_fallback":
        rule = (" The 20 picks (★) are today the plain top 20: the band that keeps names already on the "
                f"list could not be applied ({_page_safe(m.get('why') or 'no usable previous list')}).")
    else:
        rule = " Tickers are ranked; the top 20 (★) are the picks."
    return f"""<section class="block" id="picks">
<h2>Composite Picks</h2>
<p class="note">Every numeric variable from <b>both</b> stock pipelines — CFA/Buffett
fundamentals (ROE, margins, FCF yield, margin of safety, growth, leverage, 12-1
momentum) and macro-signal sensitivities (earnings yield, β to rates / dollar / CAD,
macro R²) — is z-scored across the {meta['n_universe']}-name universe, then combined
into one composite score per ticker, {note}. The variable <i>direction</i> is set by
that correlation, not hand-picked. Tickers are ranked by composite.{rule}
Each row shows the variables that contributed most (direction + relative size); the
underlying weights are proprietary. Educational research on the public universe — not
advice, and not a statement of any holding.</p>
<div class="pills" data-group="picks">
  <button class="pill on" data-f="all">All ({meta['n_universe']})</button>
  <button class="pill" data-f="buy">Buy candidates ({n_buy})</button>
  <button class="pill" data-f="watch">Watch list ({meta['n_universe']-n_buy})</button>
  <button class="pill" data-f="pick">Picks (★)</button>
</div>
<div class="tile" style="padding:0 14px 8px;overflow-x:auto">
<table class="ptable picks"><thead><tr>
<th>#</th><th>Ticker</th><th>Sector</th><th>Price</th><th>Composite</th>
<th>Top contributing variables</th><th>Commentary</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="note" style="font-size:11.5px">Forward-return proxy for the weight
derivation: mean realised 5-trading-day return after each FOMC decision per ticker
(the available forward-return history; {meta['target_coverage']}/40 names covered).
Composite weights are derived, not chosen, and recomputed on every build.</p>
</section>"""


def signals_section(macro=None):
    """macro = _macro_inputs(): its pre_listing field (from the sidecar) says whether FOMC meetings before a
    stock's first trading day were dropped (wave 14) or measured from that first day (the old producer)."""
    sens = pd.read_parquet(f"{ANA}/stock_sensitivities.parquet").copy()
    fomc = pd.read_parquet(f"{ANA}/stock_fomc_reaction.parquet")
    sens["abs_rates"] = sens["beta_rates"].abs()
    sens = sens.sort_values("abs_rates", ascending=False)
    sens["sector_short"] = sens["sector"].fillna("Other").str.replace(" Services", "")

    def cell_beta(beta, t):
        cls = "pos" if beta > 0 else ("neg" if beta < 0 else "")
        bold = "font-weight:600" if abs(t) > 2 else ""
        return (f'<td class="num {cls}" style="{bold}">{beta:+.2f}'
                f'<br><span class="tn">t={t:+.1f}</span></td>')

    sens_rows = ""
    for _, r in sens.iterrows():
        color = SECTOR_C.get(r["sector"], GREY)
        sens_rows += (
            f'<tr><td>{r["ticker"]}</td>'
            f'<td><span class="sec" style="background:{color}">{r["sector_short"]}</span></td>'
            f'<td class="num">${r["marketcap_B"]:,.0f}B</td>'
            f'<td class="num">{r["pe"]:,.1f}</td><td class="num">{r["fwd_pe"]:,.1f}</td>'
            f'{cell_beta(r["beta_rates"], r["t_rates"])}'
            f'{cell_beta(r["beta_dxy"], r["t_dxy"])}'
            f'{cell_beta(r["beta_cad"], r["t_cad"])}'
            f'<td class="num">{r["r2"]*100:.1f}%</td></tr>')

    f1 = go.Figure()
    for sec, g in sens.groupby("sector"):
        f1.add_scatter(x=g["beta_rates"], y=g["beta_dxy"], mode="markers+text",
                       text=g["ticker"], textposition="top center", textfont=dict(size=9),
                       marker=dict(color=SECTOR_C.get(sec, GREY), size=12,
                                   line=dict(color="white", width=1)), name=sec)
    f1.add_hline(y=0, line=dict(color=GREY, width=0.5))
    f1.add_vline(x=0, line=dict(color=GREY, width=0.5))
    f1.update_layout(title="Macro factor exposures — β to 10Y rates vs β to dollar (DXY)",
                     xaxis_title="β to 10Y yield change (per 1pp)",
                     yaxis_title="β to DXY % change", legend=dict(orientation="h", y=-0.18))

    pivot = fomc.groupby(["ticker", "decision"])["fwd5"].mean().unstack("decision")
    counts = fomc.groupby(["ticker", "decision"])["fomc"].count().unstack("decision")
    overall = fomc.groupby("ticker")["fwd5"].mean().sort_values(ascending=False)
    pivot = pivot.reindex(overall.index); counts = counts.reindex(overall.index)
    fomc_rows = ""
    for tk in pivot.index:
        cells = []
        for dec in ["Cut", "Hold", "Hike"]:
            if dec in pivot.columns and not pd.isna(pivot.loc[tk, dec]):
                v = pivot.loc[tk, dec]; n = int(counts.loc[tk, dec])
                cls = "pos" if v >= 0 else "neg"
                cells.append(f'<td class="num {cls}">{v*100:+.2f}%<br><span class="tn">n={n}</span></td>')
            else:
                cells.append('<td class="num" style="color:#888">—</td>')
        o = overall[tk]; cls_o = "pos" if o >= 0 else "neg"
        cells.append(f'<td class="num {cls_o}" style="font-weight:600">{o*100:+.2f}%</td>')
        fomc_rows += f"<tr><td>{tk}</td>{''.join(cells)}</tr>"

    pre = ("A meeting before a stock's first trading day is not counted, so n differs across names."
           if (macro or {}).get("pre_listing") == "dropped" else
           "For a stock that listed after a meeting, that meeting is measured from its first trading day.")
    # round 3 (L5): the sources are named only from a trusted sidecar (capstone_inputs_refresh.py wrote these very
    # files); restored old files or a missing sidecar get the neutral wording, which stays true for any producer
    m = macro or {}
    if m.get("basis") == "data through":
        cad = {"yahoo": "USD/CAD (Yahoo CAD=X)", "fred": "USD/CAD (FRED DEXCAUS)"}.get(m.get("cad_source"), "USD/CAD")
        from datetime import date as _date
        since = f" since {_date.fromisoformat(m['span_from']).strftime('%B %Y')}" if m.get("span_from") else ""
        srcs = (f"The betas are regressions of daily price returns{since} on daily changes in the 10-year Treasury "
                f"yield (FRED DGS10), the dollar index (Yahoo DX-Y.NYB) and {cad}; the FOMC decision labels come "
                f"from the effective fed funds rate (FRED).")
    else:
        srcs = ("The betas are regressions of daily price returns on daily changes in the 10-year Treasury yield, "
                "the dollar index and USD/CAD (the line under the page title dates the files).")
    return f"""<section class="block" id="signals">
<h2>Macro Factor Signals</h2>
<p class="note">The former Stock Signals page, folded in here: each name's macro
factor exposures (β to the 10-year yield, the dollar, USDCAD) and its post-FOMC
drift. These same variables feed the composite above. Bold β cells have a
t-statistic above 2 (significant). {srcs} {pre} Definitions in the
<a href="glossary.html">Glossary</a>.</p>
<div class="tile chart"><div class="ch">{div(f1, "sens-scatter")}</div></div>
<h3>Sensitivities (sorted by |β to rates|)</h3>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto;margin-bottom:18px">
<table class="ptable"><thead><tr>
<th>Ticker</th><th>Sector</th><th>Mkt Cap</th><th>P/E</th><th>Fwd P/E</th>
<th>β rates</th><th>β DXY</th><th>β USDCAD</th><th>R²</th></tr></thead>
<tbody>{sens_rows}</tbody></table></div>
<h3>Post-FOMC reaction (avg 5-day forward return by decision)</h3>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable"><thead><tr>
<th>Ticker</th><th>Cut</th><th>Hold</th><th>Hike</th><th>Overall</th></tr></thead>
<tbody>{fomc_rows}</tbody></table></div>
</section>""", len(sens), int(pivot.shape[0])


def companies_section():
    import glob
    existing = sorted(os.path.basename(f)[6:-5] for f in glob.glob(f"{DOCS}/stock_*.html"))
    cards = "".join(
        f'<a class="scard" href="stock_{tk}.html"><div class="sc-t">{tk}</div>'
        f'<div class="sc-n">CFA report &rarr;</div></a>' for tk in existing)
    return f"""<section class="block" id="companies">
<h2>Per-company CFA reports</h2>
<p class="note">Full CFA-framework equity analysis (profitability, DuPont,
financial health, relative &amp; absolute valuation) for the analyzed names. The
Buffett-style value screen over the full S&amp;P 500 remains available via the
per-company tool.</p>
<div class="scards">{cards}</div></section>"""


PAGE_CSS = r"""
.pills{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 18px}
.pill{font:500 12px 'Inter',sans-serif;letter-spacing:.02em;color:#0a2540;background:#fff;
border:1px solid #d4d4d4;padding:6px 14px;cursor:pointer;border-radius:0;transition:all .12s}
.pill:hover{background:rgba(10,37,64,.05)}
.pill.on{background:#0a2540;color:#fff;border-color:#0a2540}
table.picks td.rk{font-family:'JetBrains Mono',monospace;color:#888;text-align:right;width:30px}
table.picks .tn{font-size:11px;color:#888}
.num{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;text-align:right}
.sec{color:#fff;padding:2px 8px;font-size:11px;font-family:'Inter',sans-serif;white-space:nowrap}
.pick-star{color:#0a5d3a}
td.chips{min-width:230px}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;color:#333;
background:#f4f4f4;padding:2px 7px;margin:2px 3px 2px 0;white-space:nowrap}
.chip-b{display:inline-block;height:7px;border-radius:0}
.chip.cpos .chip-b{background:#0a5d3a}.chip.cneg .chip-b{background:#7c2d12}
.chip.cneg{color:#7c2d12}
td.cmt{font-size:12px;color:#444;line-height:1.45;min-width:240px}
"""

FILTER_JS = r"""<script>
document.querySelectorAll('.pills').forEach(function(grp){
  grp.querySelectorAll('.pill').forEach(function(b){
    b.addEventListener('click',function(){
      grp.querySelectorAll('.pill').forEach(function(x){x.classList.remove('on');});
      b.classList.add('on');var f=b.getAttribute('data-f');
      document.querySelectorAll('table.picks tbody tr').forEach(function(tr){
        var show=(f==='all')||(f==='pick'&&tr.getAttribute('data-pick')==='1')||
                 (tr.getAttribute('data-status')===f);
        tr.style.display=show?'':'none';
      });
    });
  });
});
</script>"""


def _keep_committed_page():
    """picker could not rebuild the picks (Yahoo block, < 90% fundamentals, outage). Earlier in
    the same refresh 19_stock_analysis.py may already have rewritten docs/stocks.html with its
    own landing page, so "not writing" is not enough to keep the committed picks page: restore
    it from HEAD (2026-10-23). Nothing is fetched; a git failure leaves the file as it is."""
    import subprocess
    from paths import ROOT
    # Only ever against THIS checkout (wave 13): a copy without its own .git (a staging mirror) restores
    # nothing, and GIT_CEILING_DIRECTORIES stops git from walking up into any parent repository.
    if not (ROOT / ".git").exists():
        print(f"stocks.html: {ROOT} is not a git checkout; committed copy not restored")
        return
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(ROOT.parent))
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "checkout", "HEAD", "--", "docs/stocks.html"],
                           capture_output=True, text=True, timeout=60, env=env)
        print("stocks.html: committed copy kept" if r.returncode == 0 else
              f"stocks.html: could not restore the committed copy ({r.stderr.strip()[:200]})")
    except Exception as e:                                              # noqa: BLE001
        print(f"stocks.html: could not restore the committed copy ({e})")


def _unavailable(title, sid, why):
    return (f'<section class="block" id="{sid}"><h2>{title}</h2><p class="note"><i>'
            f'not available today (data gap)</i>. The composite picks above are complete; this section '
            f'could not be built ({why}). The cause is recorded in the refresh alerts.</p></section>')


def _alert(msg):
    """A tracker failure must not be silent: the refresh logs a best-effort step's output only when it exits
    non-zero, and _tracker_extras never raises. YAHOO_ALERT.txt is the line the refresh and the watchdog
    surface (yahoo_session.alert); the message says it is a site gap, not a Yahoo transport problem."""
    line = f"stocks tracker: {msg} (site data gap, not a Yahoo transport issue)"
    try:
        import yahoo_session as ys
        ys.alert(line)
    except Exception:                                                   # noqa: BLE001
        print("!! " + line, file=sys.stderr, flush=True)


def _now():
    """The build time (aware). A function so an offline test can pin it."""
    from datetime import datetime
    return datetime.now().astimezone()


def _page_safe(s):
    """Visible wording from a reason string: HTML-escaped, no local path, no number with 3+ decimals."""
    import html as _h
    import re as _re
    s = _re.sub(r"[A-Za-z]:[\\/][^\s;,)]*|/(?:home|mnt|Users|tmp)/[^\s;,)]*", "[path]", str(s or ""))
    s = _re.sub(r"\d+\.\d{3,}", lambda m: m.group(0).split(".")[0], s)
    return _h.escape(s[:160], quote=True)


def _plain_list(df):
    return [str(tk) for tk, r in df.iterrows() if int(r["rank"]) <= 20]


def _membership(df, now, log=print):
    """(stored history or None, today's published list). Wave 14: two-sided band at the cut, stay while rank
    <= 25, enter at rank <= 15 (picks_history.membership). NEVER raises: if the history cannot be read the page
    publishes the plain top 20, says so, and one alert line is written. Ranks / composites / weights are not
    touched."""
    try:
        import picks_history as ph
        hist = ph.ensure(log=log)
        sess = ph.price_session(now)[0]
        mem = ph.membership(hist, df, sess)
        if mem["rule"] == ph.RULE_FALLBACK:
            log(f"picks list: band not applied ({mem['why']}); plain top 20 published")
            _alert(f"list band not applied ({mem['why']}); plain top 20 published")
        else:
            log(f"picks list: {mem['rule']} on the {mem['prev_session']} list; entered {mem['entered']} "
                f"(by rank <= 15: {mem.get('forced')}), left {mem['left']} (displaced: {mem.get('displaced')}), "
                f"kept by the band {mem['kept_by_band']}")
        return hist, mem
    except Exception as e:                                              # noqa: BLE001
        log("picks list: membership failed:\n" + traceback.format_exc(limit=4))
        _alert(f"list membership failed ({type(e).__name__}); plain top 20 published")
        return None, {"members": _plain_list(df), "rule": "top20_fallback", "prev_session": None,
                      "why": f"history unavailable ({type(e).__name__})", "kept_by_band": [], "entered": [],
                      "left": [], "displaced": [], "forced": [], "stay": 25, "enter": 15}


# Freshness budget of the capstone macro inputs (wave 14; main-session decision C5 = 14 days, round 3). The weekly
# run (Sunday 22:00, weekly_model_rebuild.ps1) takes prices through the Friday before it, so on a weekday they are
# 3-7 days old. After ONE missed or refused Sunday they are 10-14 days old Monday-Friday: with 14 one missed Sunday
# never reads stale; two missed Sundays (17-21 days) read stale all week. Over budget: one alert line per build +
# "(stale: N days old)" on the page. Env LTCMA_MACRO_STALE_DAYS overrides.
MACRO_STALE_DAYS = int(os.environ.get("LTCMA_MACRO_STALE_DAYS", "14"))
MACRO_META = "capstone_inputs_meta.json"
MACRO_SIDECAR_TOL_S = 86400        # the sidecar must describe THIS parquet: |file time - built_at| <= 1 day


def _macro_inputs():
    """Dates of the capstone macro inputs the composite reads, so the page states them only while true.
    Prefers the sidecar written by capstone_inputs_refresh.py: data_through = the last session in its prices;
    betas_through = the last session that enters the regressions (USD/CAD is shifted one bar, so it is the
    session before). The sidecar is used only when the parquet's file time is within a day of the sidecar's
    built_at (either direction: a parquet rebuilt by something else, or old files restored under a left-over
    sidecar, both fall back). Fallback: the parquet's file date (CDMX), basis "file date"."""
    from datetime import datetime, date
    try:
        t = datetime.fromtimestamp(os.path.getmtime(f"{ANA}/stock_sensitivities.parquet"))
    except OSError:
        return None
    try:
        with open(f"{ANA}/{MACRO_META}", encoding="utf-8") as fh:
            m = json.load(fh)
        d = date.fromisoformat(str(m["data_through"]))
        built = datetime.fromisoformat(str(m["built_at"]))
        built = built.astimezone().replace(tzinfo=None) if built.tzinfo else built
        if abs((t - built).total_seconds()) <= MACRO_SIDECAR_TOL_S:
            span = m.get("regression_span") or [None, None]
            bt = date.fromisoformat(str(span[1])).isoformat() if span and span[-1] else None
            sf = date.fromisoformat(str(span[0])).isoformat() if span and span[0] else None
            return {"date": d.isoformat(), "betas_through": bt, "age_days": (datetime.now().date() - d).days,
                    "basis": "data through", "pre_listing": str(m.get("pre_listing") or ""),
                    "cad_source": str(m.get("cad_source") or ""), "span_from": sf}
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        pass
    return {"date": t.date().isoformat(), "betas_through": None, "age_days": (datetime.now() - t).days,
            "basis": "file date", "pre_listing": "", "cad_source": "", "span_from": None}


def _dmy(iso):
    from datetime import date
    return date.fromisoformat(str(iso)[:10]).strftime("%d %b %Y")


def _macro_guard(mi):
    """(html fragment for the as-of line, stale?) and one alert line when the inputs are over budget or unreadable.
    Says "prices through" and "betas through" separately (the regressions end one session earlier: USD/CAD is
    shifted one bar). The words are "through", never "as of", so guard_freshness does not grade them as a stamp.
    Never raises: the guard reports, it does not block the page (the picks are still the picker's output)."""
    try:
        if mi is None:
            _alert("macro inputs (betas, P/E, FOMC drift) unreadable: no stock_sensitivities.parquet date")
            return "", True
        if mi.get("basis") == "data through":
            txt = f" &middot; macro inputs: prices through {_dmy(mi['date'])}"
            if mi.get("betas_through") and mi["betas_through"] != mi["date"]:
                txt += f", betas through {_dmy(mi['betas_through'])}"
        else:
            txt = f" &middot; macro inputs: file dated {_dmy(mi['date'])}"
        if mi["age_days"] > MACRO_STALE_DAYS:
            _alert(f"macro inputs (betas, P/E, FOMC drift) are {mi['age_days']} days old ({mi['basis']} {mi['date']}; "
                   f"budget {MACRO_STALE_DAYS} d): the weekly capstone_inputs_refresh.py did not run or refused; "
                   f"the composite ranks on stale inputs")
            return txt + f" (stale: {mi['age_days']} days old)", True
        return txt, False
    except Exception as e:                                              # noqa: BLE001
        print(f"macro guard failed ({type(e).__name__}: {e})", file=sys.stderr)
        return "", True


def _tracker_extras(df, meta, now, log=print, hist=None, mem=None, macro=None):
    """Pick Tracker + Track Record + overlays (wave 13). NEVER raises and never touches df: a failure here
    leaves the core page as it was (and writes one alert line). Returns html parts and the extra stocks.ai.txt
    fields. `now` = the build time; the history records the session whose closes the prices are.
    hist / mem (wave 14) = the stored history and today's published list from _membership(); the row records
    the published membership (on_list, list_rule) next to the raw rank, and macro = _macro_inputs() (the row
    records the inputs' data-through date, so the frozen-input period and the method change are dated from the
    history itself on every later build)."""
    out = {"tracker": _unavailable("Pick Tracker", "tracker", "history unavailable"), "record": "",
           "method": "", "ai": {}, "ok": False}
    mem = mem or {"members": _plain_list(df), "rule": "top20"}
    try:
        import picks_history as ph
        hist = ph.ensure(log=log) if hist is None else hist
        mt = macro["date"] if (macro and macro.get("basis") == "data through") else None
        hist, rec = ph.add_build(hist, df, now, members=mem["members"], rule=mem["rule"], macro_through=mt)
        log(f"picks_history: session {rec['session']} ({rec['basis']}, tier {rec['tier']}): "
            f"{'recorded' if rec['recorded'] else 'not recorded: ' + rec['why']}")
        if rec["recorded"]:
            try:
                ph.save(hist)                    # data/picks_history.csv (public; no weights)
            except OSError as e:
                log(f"picks_history: could not write {ph.HIST} ({e}); tracker built from memory")
                _alert(f"history not saved ({type(e).__name__})")
        try:
            splits = ph.update_splits(df, rec["session"], first_date=str(hist["snapshot_date"].min()))
        except Exception as e:                                          # noqa: BLE001
            log(f"picks_history: splits not updated ({type(e).__name__}: {e})")
            splits = ph.load_splits()
        last_split = ph.last_split_info(df, rec["session"])
    except Exception as e:                                              # noqa: BLE001
        log("picks tracker: history failed:\n" + traceback.format_exc(limit=4))
        _alert(f"history failed ({type(e).__name__}); Pick Tracker shown as a data gap")
        out["tracker"] = _unavailable("Pick Tracker", "tracker", f"history: {type(e).__name__}")
        return out
    try:
        import picks_overlays as po
        ov = po.build(df, log=log, sec_budget=int(os.environ.get("LTCMA_SEC_BUDGET", "160")),
                      sec_max_xml=int(os.environ.get("LTCMA_SEC_MAX_XML", "120")),
                      offline=os.environ.get("LTCMA_OVERLAYS_OFFLINE") == "1",
                      spy_start=str(hist["snapshot_date"].min()), now=now, picks=mem["members"], hist=hist,
                      splits=splits, last_split=last_split)
    except Exception as e:                                              # noqa: BLE001
        log("picks overlays failed:\n" + traceback.format_exc(limit=4))
        _alert(f"overlays failed ({type(e).__name__}); overlay cells shown as data gaps")
        ov = {"by_ticker": {}, "spy": None, "meta": {"gaps": [("overlays", f"{type(e).__name__}")]}}
    try:
        import picks_tracker as pt
        p = ph.Panel(hist, splits, last_split)
        ex = pt.exit_model(p)
        rows, cut = pt.tracker_rows(p, ex, ov.get("spy"))
        tr = pt.track_record(p, ov.get("spy"))
        fig = pt.record_figure(tr)
        chart = div(fig, "track-record-chart") if fig is not None else ""
        gl = [f"{k}: {w}" for k, w in (ov.get("meta") or {}).get("gaps", [])]
        mi = pt.method_info(p, mem=mem, rec=rec, macro=macro)        # wave 14: method changes, dated
        tr["method"] = mi
        m2 = {"dates": p.dates, "today": rec["session"], "gap_lines": gl, "record": rec, "list": mem,
              "band_since": mi["band_since"], "method": mi}
        out.update(tracker=pt.tracker_section(rows, ov.get("by_ticker") or {}, ex, cut, m2),
                   record=pt.record_section(tr, chart, macro=macro),
                   method=pt.methodology_html(mi["band_since"], mi),
                   ai=pt.ai_fields(rows, ov.get("by_ticker") or {}), ok=True, css=pt.TRACKER_CSS,
                   js=pt.TRACKER_JS, ai3=pt.ai_method_tail(mi, ex))
        log(f"picks tracker: {len(p.dates)} rankings, {len(rows)} rows, exit model on "
            f"{ex.get('n_transitions', 0)} moves, splits applied {p.applied}, price breaks {len(p.breaks)}, "
            f"split-like jumps ruled out by Yahoo {[(j['ticker'], j['to']) for j in p.real_jumps]}, "
            f"partial days {p.partial}")
    except Exception as e:                                              # noqa: BLE001
        log("picks tracker failed:\n" + traceback.format_exc(limit=6))
        _alert(f"tracker failed ({type(e).__name__}); Pick Tracker shown as a data gap")
        out["tracker"] = _unavailable("Pick Tracker", "tracker", f"{type(e).__name__}")
    return out


def main():
    try:
        df, weights, meta = picker.build_universe()
    except Exception:
        _keep_committed_page()
        raise                                    # non-zero exit: the refresh log shows why
    macro = _macro_inputs()
    sig_html, n_sens, n_fomc = signals_section(macro)
    now = _now()                                 # the history dates the row by the session its closes are
    asof = now.strftime("%d %b %Y")              # same local day as pd.Timestamp.today(); one clock for the page
    macro_txt, macro_stale = _macro_guard(macro)                # wave 14 freshness guard (alerts when over budget)
    print(f"macro inputs: {macro_txt.replace('&middot;', '').replace('macro inputs:', '').strip() or 'unknown'}"
          f"{' -- STALE, alert written' if macro_stale else ''}", flush=True)
    try:
        import picks_tracker as _pt
        ai_head5 = _pt.AI_HEADER5
    except Exception:                                                   # noqa: BLE001
        ai_head5 = None
    _log = lambda m: print(m, flush=True)                               # noqa: E731
    hist, mem = _membership(df, now, log=_log)   # wave 14: the published list (two-sided band); df is not touched
    extra = _tracker_extras(df, meta, now, log=_log, hist=hist, mem=mem, macro=macro)

    body = f"""<section class="hero"><div class="container">
<h1>Stock Research</h1>
<p class="lede">Picks, analysis and signals in one place. A reproducible composite
picker reads <b>every variable</b> from the fundamental and macro-signal pipelines,
z-scores and combines them, and ranks the {meta['n_universe']}-name research universe.</p>
<p class="asof">As of {asof} &middot; {meta['n_universe']} names &middot; data: Yahoo Finance (prices, fundamentals, dollar index, USD/CAD) + FRED (10-year yield, fed funds){macro_txt}</p>
</div></section>
<main class="container">
{ccy_badge("USD", "figures in US dollars; ratios are currency-neutral")}
{picks_section(df, meta, mem)}
{extra["tracker"]}
{extra["record"]}
{sig_html}
{companies_section()}
<section class="block"><h2>Methodology &amp; limitations</h2>
<div class="bt-method2">
<p><b>Composite.</b> For each ticker in the union of the two pipelines, collect every
numeric variable, z-score it cross-sectionally (missing → 0), and form a weighted sum.
Weights = each variable's Pearson correlation with realised forward returns; the sign
of that correlation sets the variable's direction. Normalised so the absolute weights
sum to 1. Rank by composite. The 20 picks follow a two-sided band at the rank-20 cut: a
name already on the list stays while it ranks 25th or better, a name off the list enters
once it ranks 15th or better (displacing the worst-ranked pick), and any other free place
goes to the best-ranked name off the list. The band changes only membership, never the
composite or the ranks.</p>
<p><b>Forward-return proxy.</b> The only realised forward-return history available
across the universe is the post-FOMC 5-day drift, so weights are derived from each
variable's cross-sectional correlation with the mean post-FOMC 5-day return. This is a
genuine realised-return signal but a narrow one; a broader forward-return panel would
sharpen the weights. If that history were absent the picker falls back to equal-weight
z-scores (documented on the build).</p>
<p><b>Universe.</b> The composite runs on the names that carry <i>both</i> fundamental
and macro-signal variables (the macro-signal coverage set). The broader S&amp;P 500
Buffett value screen stays available via the per-company tool.</p>
{extra["method"]}
<p><b>Not advice.</b> Educational research over a public universe. Free Yahoo Finance
fundamentals are approximate; past forward-return relationships do not guarantee
future returns.</p></div></section>
</main>"""

    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Carlos Duarte — Stock Research</title>'
            f'<meta name="ltcma-picks-rule" content="{_page_safe(mem.get("rule") or "top20")}">{FONTS}'
            f'{CSS_LINKS}<link rel="stylesheet" href="style.css"><style>{PAGE_CSS}{extra.get("css", "")}</style>'
            f'<script src="{PLOTLY}"></script></head><body>'
            f'<header class="shell"><div class="shell-in">'
            f'<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b>'
            f'</span>{NAV}</div></header>{body}'
            f'<footer class="shell-foot"><div class="container"><p>Composite picker '
            f'and CFA-framework analysis on free public data. Educational research, '
            f'not investment advice.</p></div></footer>{FILTER_JS}{extra.get("js", "")}</body></html>')
    open(f"{DOCS}/stocks.html", "w", encoding="utf-8").write(html)

    # low-token AI copy + reproducibility dump (weights stay OUT of the public copy)
    # wave 14: the pick lines are the PUBLISHED list (rank order), which may include a name ranked 21-25
    members = set(mem["members"])
    top = df.loc[[tk for tk in df.index if tk in members]]
    contrib = meta["contrib"]
    if str(mem.get("rule", "")).startswith("band"):
        rule3 = (f"picks=20 names, rule={mem['rule']}: a listed name stays while rank<=25; an unlisted name "
                 f"enters at rank<=15 (displacing the worst-ranked pick); other free places go to the "
                 f"best-ranked unlisted names")
    else:
        rule3 = (f"picks=20 names, rule={mem.get('rule') or 'top20'}: the plain top 20"
                 + (" (band not applied today)" if mem.get("rule") == "top20_fallback" else ""))
    # round 3 (L0): the method changes, dated from the stored history (band_since / macro_through), the same data
    # the page uses; "" when the tracker could not be built (then nothing is claimed). Never "rule=" again here.
    rule3 += extra.get("ai3") or ""
    ai = ["STOCK COMPOSITE PICKS — AI COPY (low-token)",
          f"asof={asof}; universe={meta['n_universe']}; target=mean post-FOMC fwd5; "
          f"coverage={meta['target_coverage']}/40; fallback={meta['equal_weight_fallback']}",
          f"composite=sum(corr-derived-weight*zscore); weights private; {rule3}",
          "fields: rank|ticker|sector|price|composite|dominant_var"]
    if ai_head5:                                 # line 5 (wave 13): the appended tracker columns
        ai.append(ai_head5)
    for tk, r in top.iterrows():
        dom = contrib.loc[tk].abs().idxmax()
        tail = extra["ai"].get(tk) or (["na"] * 8 if ai_head5 else [])
        ai.append(f"{int(r['rank'])}|{tk}|{r['sector']}|{r['price']:.2f}|"
                  f"{r['composite']:+.3f}|{picker.FLABEL[dom]}" + "".join("|" + str(x) for x in tail))
    open(f"{DOCS}/stocks.ai.txt", "w", encoding="utf-8").write("\n".join(ai) + "\n")

    print(f"stocks.html built: {meta['n_universe']} names, "
          f"{int((df['composite']>0).sum())} buy candidates, "
          f"signals {n_sens} sens / {n_fomc} FOMC")
    # sanity summary to stdout (for the build log / report)
    cv = contrib.var(ddof=0); share = (cv / cv.sum()).sort_values(ascending=False)
    base = df.sort_values("mom_12_1", ascending=False).head(20).index
    overlap = len(set(base) & set(top.index))
    print(f"  list rule: {mem.get('rule')}; kept by the band: {mem.get('kept_by_band')}")
    print(f"  sectors(picks): {top['sector'].value_counts().to_dict()}")
    print(f"  max var share: {share.iloc[0]*100:.1f}% ({share.index[0]})")
    print(f"  vs naive-momentum overlap: {overlap}/20")


if __name__ == "__main__":
    main()
