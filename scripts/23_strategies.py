"""LTCMA — Step 23: Systematic Strategies page (docs/strategies.html).
Interactive growth-of-100 curves vs S&P 500, drawdown, and a full professional
indicator set for the four regime-adaptive strategies. A start-date control lets
the reader re-base every curve and recompute every indicator from any month
("kill the starting point"). Methodology stays proprietary — results only.
"""
import os
import json
import numpy as np
import plotly.graph_objects as go
from glossary import (NAV, bt_load, bt_common, bt_indicators, bt_g100, bt_dd, BT_JS,
                      bt_catalog, bt_card, BT_CARD_CSS, _bt_redact)

from paths import DOCS_S as DOCS  # repo-anchored (2026-06-10)
import pandas as pd
INK, BLUE, GOLD, GREEN = "#111111", "#0a2540", "#6b7280", "#0a5d3a"
RED, GREY, PURPLE = "#7c2d12", "#888888", "#8a3ffc"
ASOF = pd.Timestamp.today().strftime("%d %b %Y")
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"

LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15), dragmode=False,
              margin=dict(l=60, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e5e5e5"), yaxis=dict(gridcolor="#e5e5e5"))


def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "responsive": True})


# ── load the four strategies' OOS return series (shared loader) ──────────────
data = bt_load()
order = ["SARS", "DUO", "MARS", "BARS"]
usd = ["SARS", "DUO", "MARS"]
common, aligned, spy = bt_common(data)

# ── 1. USD equity curves vs S&P (common window, indexed to 100) ──────────────
f_eq = go.Figure()
for k in usd:
    f_eq.add_scatter(x=common, y=bt_g100(aligned[k]), mode="lines", name=data[k]["name"],
                     line=dict(color=data[k]["color"], width=2.4))
f_eq.add_scatter(x=common, y=bt_g100(spy), mode="lines", name="S&P 500",
                 line=dict(color=RED, width=1.8, dash="dot"))
f_eq.update_layout(title="Growth of 100 — USD strategies vs S&P 500",
                   legend=dict(orientation="h", y=-0.16), yaxis_type="log")

# ── 2. Drawdown (USD) ────────────────────────────────────────────────────────
f_dd = go.Figure()
for k in usd:
    f_dd.add_scatter(x=common, y=bt_dd(aligned[k]), mode="lines",
                     name=data[k]["name"], line=dict(color=data[k]["color"], width=1.8))
f_dd.add_scatter(x=common, y=bt_dd(spy), mode="lines", name="S&P 500",
                 line=dict(color=RED, width=1.4, dash="dot"), fill="tozeroy",
                 fillcolor="rgba(218,30,40,0.06)")
f_dd.update_layout(title="Drawdown (%) — USD strategies vs S&P 500",
                   legend=dict(orientation="h", y=-0.16))

# ── 3. BARS vs IPC (MXN) ─────────────────────────────────────────────────────
bd = data["BARS"]
f_bars = go.Figure()
f_bars.add_scatter(x=bd["dates"], y=bt_g100(bd["s"]), mode="lines", name="Mexican Equity Rotation",
                   line=dict(color=GREEN, width=2.4))
f_bars.add_scatter(x=bd["dates"], y=bt_g100(bd["b"]), mode="lines", name="IPC (NAFTRAC)",
                   line=dict(color=GREY, width=1.8, dash="dot"))
f_bars.update_layout(title="Growth of 100 (MXN) — Mexican Equity Rotation vs IPC",
                     legend=dict(orientation="h", y=-0.16), yaxis_type="log")


# ── indicator table (initial values over each strategy's full window) ────────
METRICS = {k: bt_indicators(data[k]["s"], data[k]["b"], data[k]["rf"]) for k in order}


def _nan(x):
    return x is None or (isinstance(x, (float, np.floating)) and np.isnan(x))
def f_pct(x):  return "—" if _nan(x) else f"{x*100:.1f}%"
def f_pcts(x): return "—" if _nan(x) else f"{x*100:+.1f}%"
def f_num(x, d=2): return "—" if _nan(x) else f"{x:.{d}f}"
def f_ulc(x):  return "—" if _nan(x) else f"{x:.1f}%"
def f_ldd(x):  return "—" if _nan(x) else f"{int(round(x))} m"
FMTP = {"ann_ret": f_pct, "ann_vol": f_pct, "max_dd": f_pct, "win": f_pct, "te": f_pct,
        "var95": f_pct, "cvar95": f_pct, "best": f_pcts, "worst": f_pcts, "alpha": f_pcts,
        "sharpe": f_num, "sortino": f_num, "calmar": f_num, "beta": f_num, "ir": f_num,
        "up_cap": f_num, "dn_cap": f_num, "omega": f_num, "gtp": f_num, "recov": f_num,
        "skew": f_num, "kurt": f_num, "tail": f_num, "ulcer": f_ulc, "longdd": f_ldd}

GROUPS = [
    ("Return &amp; growth", [("CAGR (annualised)", "ann_ret"), ("Ann. volatility", "ann_vol"),
                         ("Best month", "best"), ("Worst month", "worst")]),
    ("Risk-adjusted", [("Sharpe", "sharpe"), ("Sortino", "sortino"), ("Calmar", "calmar"),
                       ("Omega (&gt;0)", "omega"), ("Gain-to-pain", "gtp"), ("Recovery factor", "recov")]),
    ("Drawdown &amp; tail risk", [("Max drawdown", "max_dd"), ("Longest drawdown", "longdd"),
                                  ("Ulcer index", "ulcer"), ("Monthly VaR 95%", "var95"),
                                  ("Monthly CVaR 95%", "cvar95"), ("Tail ratio", "tail")]),
    ("Distribution", [("Win rate (months)", "win"), ("Skew", "skew"), ("Excess kurtosis", "kurt")]),
    ("Versus benchmark", [("Alpha (ann.)", "alpha"), ("Beta", "beta"), ("Tracking error", "te"),
                          ("Information ratio", "ir"), ("Up-capture", "up_cap"), ("Down-capture", "dn_cap")]),
]
ROWKEYS = [key for _, items in GROUPS for _, key in items]

head = "".join(f"<th>{data[k]['name']}<br><span style='font-weight:400;color:#888888'>"
               f"vs {data[k]['bn']}</span></th>" for k in order)
body = ""
for gname, items in GROUPS:
    body += f'<tr class="grp"><td>{gname}</td>' + "".join("<td></td>" for _ in order) + "</tr>"
    for label, key in items:
        cells = "".join(f'<td id="m_{k}_{key}">{FMTP[key](METRICS[k][key]) if METRICS[k] else "—"}</td>'
                        for k in order)
        body += f"<tr><td>{label}</td>{cells}</tr>"
wins = "".join(f'<td id="m_{k}_window">{data[k]["dates"][0][:4]}&ndash;{data[k]["dates"][-1][:4]} '
               f'({len(data[k]["dates"])}m)</td>' for k in order)
body += f'<tr class="wrow"><td>OOS window</td>{wins}</tr>'

# ── interactive start-date control ───────────────────────────────────────────
CTRL = ('<div class="btctl">'
        '<div class="btranges">'
        '<button class="btr on" data-bt-range="all" data-bt-group="s">All</button>'
        '<button class="btr" data-bt-range="15" data-bt-group="s">15Y</button>'
        '<button class="btr" data-bt-range="10" data-bt-group="s">10Y</button>'
        '<button class="btr" data-bt-range="5" data-bt-group="s">5Y</button>'
        '<button class="btr" data-bt-range="3" data-bt-group="s">3Y</button>'
        '<button class="btr" data-bt-range="1" data-bt-group="s">1Y</button>'
        '</div>'
        '<input type="range" id="s-start" class="btslider" aria-label="Backtest start date">'
        '<span id="s-start-lbl" class="btlbl">From …</span>'
        '</div>')

cfg = ('{mode:"own",cellPrefix:"m",group:"s",'
       'cols:["SARS","DUO","MARS","BARS"],'
       'rows:' + json.dumps(ROWKEYS, separators=(",", ":")) + ','
       'eq:"eq",dd:"dd",bars:"bars",slider:"s-start",label:"s-start-lbl"}')
bt_script = ('<script>window.BT_DATA=' + json.dumps(data, separators=(",", ":")) +
             ';window.BT_CFG=' + cfg + ';</script>\n<script>' + BT_JS + '</script>')


# ── merged backtest + strategies feed (backtests.html folded in here) ─────────
# Carlos (2026-06-04): merge the Backtests and Strategies pages into one. Every
# strategy in the canonical catalog renders here as a status-tagged card —
# deployed/deployable (green), research-passed/ensemble (blue), failed/archived
# (gray, lesson visible). Status filter pills are client-side. Failed cards still
# route name/thesis/verdict/lesson through the confidentiality filter (bt_card →
# _bt_public/_bt_redact), so parameters/tickers/universe stay redacted (rule 7).
_cat = bt_catalog()
_strats = _cat.get("strategies", [])
_rank = {"green": 0, "yellow": 1, "red": 2}


def _status(s):
    """Map a catalog entry to (key, pill-label) for the merged feed."""
    if s.get("badge") == "green":
        return "deployed", ("Deployed · GFC-tested" if s.get("gfc_test_passed")
                            else "Deployable")
    if s.get("badge") == "yellow":
        return "research", "Research · ensemble"
    return "archived", "Failed / archived"


def _lesson(s):
    """Short lesson line for archived/failed cards (redacted backstop applies)."""
    txt = s.get("failure_reason") or s.get("verdict_line") or ""
    txt = txt.split(". ")[0].strip()
    return (txt[:240] + "…") if len(txt) > 240 else txt


_order = sorted(_strats, key=lambda s: (
    {"deployed": 0, "research": 1, "archived": 2}[_status(s)[0]],
    0 if s.get("gfc_test_passed") else 1, _rank.get(s.get("badge"), 3),
    s.get("short_name", "")))

import copy as _copy
_bt_cards = ""
for s in _order:
    st, label = _status(s)
    rl = (s.get("report_html") or f"bt_{s['key']}.html") if s.get("public") else None
    if not s.get("public"):
        # Only the curated public:true entries have a vetted public thesis. For every
        # other entry (non-public research + failures) the raw thesis enumerates exact
        # parameter sets / asset universes (rule 4/7) — replace it with a safe generic
        # line so no parameter values reach the public card. Metrics + redacted verdict
        # + lesson still render.
        s = _copy.deepcopy(s)
        s["what_it_tests"] = ("Research backtest — thesis, parameters and asset "
                              "universe held internal. The headline verdict and lesson "
                              "are shown.")
    if st == "deployed":
        xref = ('<b>Flagship deployable strategy</b> — a validated building block of the '
                'live regime-adaptive book above.' if s.get("gfc_test_passed")
                else 'Deployable building block behind the live book above.')
    elif st == "research":
        xref = 'Ensemble component — used as one signal inside the live book.'
    else:
        les = _lesson(s)
        xref = (f'<b>Lesson learned:</b> {_bt_redact(les)}' if les
                else 'Archived — no deployable edge.')
    card = bt_card(s, rl, xref)
    card = card.replace('<article class="btcard ',
                        f'<article data-status="{st}" class="btcard st-{st} ', 1)
    _bt_cards += card

# ── critical findings as research-note cards (publishable per WEBSITE_DEPLOY #6) ─
_FINDINGS = [
    ("#9", "External regime-gating harms self-defended sleeves",
     "When a sleeve already carries an internal trend/regime filter, layering an "
     "external regime-conditional weight that down-weights it in stress is "
     "architecturally inverted — it pulls weight away precisely when the internal "
     "filter is doing the most defending. The ungated allocation strictly "
     "dominated the gated one in an extended GFC analog (passing the sub-10% "
     "drawdown bar where the gated version failed). Generalizes the signal-level "
     "double-gating result to the portfolio-weighting level."),
    ("#10", "Macro state shows no usable directional form on this data",
     "A single risk-on/off macro orientation cannot fit a heterogeneous cross-"
     "section (the same state implies opposite correct signs across instruments), "
     "and as a conditioner it adds no information either. Across eight macro / "
     "cross-asset features none cleared the discovery bar — macro variables are "
     "conditioner axes, not standalone signals, and conditioning also fails."),
    ("#11", "At daily-bar granularity, 5-day mean-reversion is the lone single-name edge",
     "Three independent new weak-signal families (cross-sectional rank momentum, "
     "calendar/seasonal, daily-bar microstructure) were tested for a broadly-"
     "replicating edge uncorrelated to the known mean-reversion survivor. None "
     "passed: the genuinely-new axes have no edge, and the only edge-ish streams "
     "are mean-reversion re-expressed. The honest reading: this dataset + daily "
     "horizon are exhausted for single-name directional alpha — the next move is a "
     "horizon change (intraday), not another feature batch."),
]
_find_cards = ""
for num, title, txt in _FINDINGS:
    _find_cards += (
        f'<article data-status="research" class="btcard st-research note-card">'
        f'<div class="bt-head"><span class="bt-badge note-badge">Research note {num}</span></div>'
        f'<h3 class="bt-name">{title}</h3>'
        f'<p class="bt-tests">{txt}</p>'
        f'<div class="bt-foot"><span class="bt-span">Critical finding — observation, '
        f'not actionable IP</span></div></article>')

_PILLS = (
    '<div class="pills" data-group="strat">'
    '<button class="pill on" data-f="all">All</button>'
    '<button class="pill" data-f="deployed">Deployed</button>'
    '<button class="pill" data-f="research">Research (passed)</button>'
    '<button class="pill" data-f="archived">Failed / archived</button>'
    '</div>')

BT_SECTION = (
    '<section class="block" id="backtests"><h2>Strategy Backtests &amp; Research</h2>'
    '<p class="note">Every completed strategy backtest, run under one fixed protocol '
    '(smart-search &rarr; walk-forward &rarr; deflated Sharpe &rarr; Monte Carlo &rarr; '
    'held-out window &rarr; S&amp;P&nbsp;500 gate &rarr; sub-10% drawdown bar), folded in '
    'with the research notes. The flagship <b>Static Drift-Weight 50/30/20</b> '
    '(Sharpe&nbsp;1.33, GFC-tested) leads. <span style="color:#0a5d3a;font-weight:600">'
    'Green</span> = deployed/deployable, <span style="color:#0a2540;font-weight:600">'
    'blue</span> = research-passed ensemble component, <span style="color:#9ca3af;'
    'font-weight:600">gray</span> = failed/archived with the lesson learned shown. '
    'Performance metrics are real and scale-invariant; parameters, asset universes and '
    'entry/exit rules are redacted for confidentiality. The full research record — '
    '18 findings across 14 discovery batches, negative results included — is published '
    'on the <a href="research.html">Research Notes</a> page.</p>'
    f'{_PILLS}'
    f'<div class="btgrid">{_bt_cards}{_find_cards}</div></section>')

# ── Multi-Level Rotation Family showcase (Findings #29-#34) ──────────────────
# Editorial, public-safe narrative of the 2026 rotation wave. No tickers, no
# parameters, no internal paths (confscan-clean): describes universes generically
# and quotes only scale-invariant metrics (Sharpe, selection lifts, correlation)
# and unscaled percentages. The deploy decision is unchanged — strategies.json
# is the source of truth for what is live; this is process documentation.
ROTATION_SECTION = (
    '<section class="block" id="rotation-family"><h2>Multi-Level Rotation Family — A Process Showcase (2026)</h2>'
    '<p class="note">Through the first half of 2026 the research book ran a disciplined wave of '
    '<b>multi-level rotation</b> strategies — each stacking a macro <i>regime</i> layer (which sets '
    'the risk posture) on a <i>selection</i> layer (which assets to hold). Across <b>30 backtest '
    'batches</b> the wave produced exactly one deployed flagship, one paper-track candidate, four '
    'conditional results, and one outright kill. The kills are shown on purpose: a research process '
    'is only as trustworthy as the ideas it is willing to throw away.</p>'
    '<h3 style="font-family:Spectral,Georgia,serif;font-weight:500;color:#111;margin:22px 0 8px">'
    'The decisive test — de-risk vs. selection</h3>'
    '<p class="note">Every rotation is decomposed into three return streams on one common window: the '
    '<b>full</b> strategy, the regime <b>de-risk overlay alone</b> (applied to the plain benchmark, no '
    'asset-picking), and the <b>selection layer alone</b> (the asset book with no de-risking). If the '
    'de-risk overlay alone matches the full strategy, the asset-picking is <i>decorative</i> — the edge '
    'is simply volatility reduction, which a vol-targeted index delivers for free. A genuine multi-level '
    'edge requires <i>both</i> layers to add separable value <i>and</i> compound. This one test is what '
    'separates an honest result from a flattering one, and it is run before any verdict is written.</p>'
    '<h3 style="font-family:Spectral,Georgia,serif;font-weight:500;color:#111;margin:22px 0 8px">'
    'The selection-edge spectrum</h3>'
    '<p class="note">Run across five asset classes with the same harness, the test returned five '
    'different answers — proof it discriminates rather than rubber-stamping. The value the '
    '<i>selection</i> layer adds on top of the de-risk overlay, in Sharpe units:</p>'
    '<div class="tile" style="padding:0 16px 8px;overflow-x:auto">'
    '<table class="ptable"><thead><tr><th style="text-align:left">Rotation universe</th>'
    '<th>Selection edge<br><span style="font-weight:400;color:#888888">(Sharpe, on top of de-risk)</span></th>'
    '<th>Verdict</th></tr></thead><tbody>'
    '<tr><td style="text-align:left">Emerging-market country rotation</td><td>+0.28</td>'
    '<td><span style="color:#0a2540;font-weight:600">Paper-track candidate</span></td></tr>'
    '<tr><td style="text-align:left">Mexican equity rotation</td><td>+0.24</td>'
    '<td><span style="color:#0a2540;font-weight:600">Currency-contingent</span></td></tr>'
    '<tr><td style="text-align:left">US factor rotation</td><td>+0.04</td>'
    '<td><span style="color:#6b7280;font-weight:600">Not additive</span></td></tr>'
    '<tr><td style="text-align:left">US sector rotation</td><td>&asymp;0</td>'
    '<td><span style="color:#6b7280;font-weight:600">De-risk in disguise</span></td></tr>'
    '<tr><td style="text-align:left">G10 FX carry</td><td>&minus;0.07</td>'
    '<td><span style="color:#7c2d12;font-weight:600">Killed</span></td></tr>'
    '</tbody></table></div>'
    '<p class="note">The lesson: <b>the asset class decides whether selection has standalone edge.</b> '
    'Emerging-market country momentum and Mexican size/liquidity dispersion are real, separable premia; '
    'US cross-sectional sector and factor momentum are not — there the "rotation" is just a regime '
    'de-risk sleeve in a different costume. In the carry case the premium <i>is</i> crash-risk '
    'compensation, so a crash-dodging regime gate strips out the very months the selection was being '
    'paid for — the two layers price the same risk and cannot compound, and the de-risk overlay alone '
    'beat the full strategy. That result was retired, not deployed.</p>'
    '<h3 style="font-family:Spectral,Georgia,serif;font-weight:500;color:#111;margin:22px 0 8px">'
    'Two rules the wave hardened</h3>'
    '<p class="note"><b>Additivity (correlation).</b> A new rotation sleeve earns a slot only if it '
    'beats the deployed book by a clear margin <i>or</i> is genuinely uncorrelated to it. The factor '
    'and sector rotations turned out <b>0.76 correlated to each other</b> despite holding completely '
    'different universes — proof both are driven by the shared de-risk overlay, not their distinct '
    'asset picks. Anything above 0.70 to an existing de-risk sleeve is not a new sleeve; it is a second '
    'copy of one you already own.</p>'
    '<p class="note"><b>Home-currency truth.</b> A single-country book must be judged in the currency '
    'the investor actually holds. The Mexican rotation is a Sharpe-1.13 capital preserver in pesos but '
    'falls to Sharpe 0.42 for a dollar investor once the peso\'s structural depreciation is paid — so '
    'the hoped-for cross-currency diversification was a headwind, not a benefit. Cross-currency exposure '
    'is empirical, never assumed.</p>'
    '<p class="note">Net result through 30 batches: the deployed flagship — <b>Static Drift-Weight '
    '50/30/20</b> (Sharpe 1.33, GFC-tested) — was not displaced by any rotation. The strongest newcomer '
    'is held as an uncorrelated paper-track candidate, not a capital allocation. Discipline over a '
    'flattering headline.</p>'
    '</section>')

STRAT_CSS = r"""
.pills{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 22px}
.pill{font:500 12px 'Inter',sans-serif;letter-spacing:.02em;color:#0a2540;background:#fff;
border:1px solid #d4d4d4;padding:6px 14px;cursor:pointer;transition:all .12s}
.pill:hover{background:rgba(10,37,64,.05)}
.pill.on{background:#0a2540;color:#fff;border-color:#0a2540}
.btcard.st-deployed{border-top-color:#0a5d3a}
.btcard.st-research{border-top-color:#0a2540}
.btcard.st-archived{border-top-color:#9ca3af;background:#fcfcfc}
.btcard.st-archived .bt-name{color:#555}
.note-card{border-top-color:#0a2540}
.note-badge{background:#0a2540}
"""

# ── drawdown-episode explorer (client-side, linked to the window control) ────
# Computes the deepest peak→trough→recovery episodes per strategy inside the
# chosen start window, renders them as a table, and zooms the charts to an
# episode on click. Rebuilds whenever the shared window control changes.
EPISODE_JS = r"""<script>
(function(){
  if(!window.BT_DATA)return;
  var D=window.BT_DATA,ORDER=["SARS","DUO","MARS","BARS"];
  function navc(a){var o=[],p=1,i;for(i=0;i<a.length;i++){p*=(1+a[i]);o.push(p);}return o;}
  function episodes(dates,rets){
    var n=navc(rets),eps=[],i;
    var pk=-1e18,pkI=0,inDD=false,minV=0,minI=0;
    for(i=0;i<n.length;i++){
      if(n[i]>=pk){
        if(inDD){eps.push({p:pkI,t:minI,r:i,d:minV/pk-1});inDD=false;}
        pk=n[i];pkI=i;
      }else{
        if(!inDD){inDD=true;minV=n[i];minI=i;}
        else if(n[i]<minV){minV=n[i];minI=i;}
      }
    }
    if(inDD)eps.push({p:pkI,t:minI,r:null,d:minV/pk-1});
    eps.sort(function(a,b){return a.d-b.d;});
    return eps.slice(0,3);
  }
  function axisUnion(){var set={};ORDER.forEach(function(k){if(D[k])D[k].dates.forEach(function(d){set[d]=1;});});
    var ax=Object.keys(set);ax.sort();return ax;}
  var AXIS=axisUnion();
  function fmtM(d){return d?d.slice(0,7):"—";}
  function render(start){
    var tb=document.getElementById('dd-ep-body');if(!tb)return;
    var html="";
    ORDER.forEach(function(k){
      if(!D[k])return;
      var i0=0,ds=D[k].dates;while(i0<ds.length&&ds[i0]<start)i0++;
      var sub=ds.slice(i0),rs=D[k].s.slice(i0);
      if(sub.length<6)return;
      var eps=episodes(sub,rs);
      eps.forEach(function(e,j){
        var down=e.t-e.p,rec=e.r===null?"ongoing":fmtM(sub[e.r]);
        html+='<tr class="ep-row" data-k="'+k+'" data-p="'+sub[e.p]+'" data-r="'+(e.r===null?sub[sub.length-1]:sub[e.r])+'">'
          +(j===0?'<td style="white-space:nowrap"><span style="display:inline-block;width:8px;height:8px;background:'+D[k].color+';margin-right:7px"></span>'+D[k].name+'</td>':'<td></td>')
          +'<td>'+fmtM(sub[e.p])+'</td><td>'+fmtM(sub[e.t])+'</td>'
          +'<td class="neg">'+(e.d*100).toFixed(1)+'%</td>'
          +'<td>'+down+' m</td><td>'+rec+'</td></tr>';
      });
    });
    tb.innerHTML=html||'<tr><td colspan="6" style="text-align:left;color:#888">Window too short for episode analysis.</td></tr>';
    tb.querySelectorAll('.ep-row').forEach(function(r){
      r.style.cursor='pointer';
      r.addEventListener('click',function(){
        if(!window.Plotly)return;
        var k=r.getAttribute('data-k'),x0=r.getAttribute('data-p'),x1=r.getAttribute('data-r');
        var upd={'xaxis.range':[x0,x1]};
        if(k==='BARS'){if(document.getElementById('bars'))Plotly.relayout('bars',upd);}
        else{['eq','dd'].forEach(function(id){if(document.getElementById(id))Plotly.relayout(id,upd);});}
        r.style.background='rgba(10,37,64,.07)';
        setTimeout(function(){r.style.background='';},600);
      });
    });
  }
  function currentStart(){
    var sl=document.getElementById('s-start');
    if(sl&&sl.max&&AXIS.length)return AXIS[Math.min(+sl.value,AXIS.length-1)]||AXIS[0];
    return AXIS[0];
  }
  function refresh(){render(currentStart());}
  function init(){
    refresh();
    var sl=document.getElementById('s-start');
    if(sl)sl.addEventListener('input',refresh);
    document.querySelectorAll("[data-bt-range][data-bt-group='s']").forEach(function(b){
      b.addEventListener('click',function(){setTimeout(refresh,0);});});
  }
  if(document.readyState!=='loading')init();else document.addEventListener('DOMContentLoaded',init);
})();
</script>"""

STRAT_FILTER_JS = r"""<script>
document.querySelectorAll('.pills').forEach(function(grp){
  grp.querySelectorAll('.pill').forEach(function(b){
    b.addEventListener('click',function(){
      grp.querySelectorAll('.pill').forEach(function(x){x.classList.remove('on');});
      b.classList.add('on');var f=b.getAttribute('data-f');
      document.querySelectorAll('.btgrid .btcard').forEach(function(c){
        c.style.display=(f==='all'||c.getAttribute('data-status')===f)?'':'none';
      });
    });
  });
});
</script>"""

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carlos Duarte — Systematic Strategies</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><style>{BT_CARD_CSS}{STRAT_CSS}</style><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Systematic Strategies</h1>
<p class="lede">Four regime-adaptive strategies, walk-forward out-of-sample, benchmarked
against the S&amp;P 500 (and the IPC for Mexican equity). Equity curves, drawdowns and a
full indicator set. Results only — the detection-and-optimisation methodology is proprietary.
Every validated and archived backtest behind these building blocks is catalogued below
(the former Backtests page, now merged in) with status filters.</p>
<p class="asof">As of {ASOF} &middot; out-of-sample &middot; hypothetical, not actual trading results</p>
</div></section>
<main class="container">
<section class="block"><h2>Backtest Window</h2>
<p class="note">Drag the slider (or pick a range) to move the start date — every curve
re-bases to 100 and every indicator recomputes from the month you choose. The USD
comparison chart begins Jan&nbsp;2007 (the first month all three USD strategies coexist);
earlier starts only extend the longer-history columns in the indicator table below.</p>
{CTRL}</section>
<section class="block"><h2>Growth of 100 — USD strategies vs S&amp;P 500</h2>
<div class="tile chart wide"><div class="ch">{div(f_eq,'eq')}</div></div>
<p class="note">Log scale, indexed to 100 at the chosen start. Every strategy compounds
with materially lower drawdowns than the index (below).</p></section>
<section class="block"><h2>Drawdown</h2>
<div class="tile chart wide"><div class="ch">{div(f_dd,'dd')}</div></div></section>
<section class="block"><h2>Drawdown Episodes</h2>
<p class="note">The three deepest peak-to-recovery episodes per strategy inside
the chosen window. Click a row to zoom the charts to that episode; pick any
range button above to reset the view.</p>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable" id="dd-ep"><thead><tr><th style="text-align:left">Strategy</th>
<th>Peak</th><th>Trough</th><th>Depth</th><th>To trough</th><th>Recovered</th></tr></thead>
<tbody id="dd-ep-body"></tbody></table></div></section>
<section class="block"><h2>Mexican Equity Rotation vs IPC (MXN)</h2>
<div class="tile chart wide"><div class="ch">{div(f_bars,'bars')}</div></div></section>
<section class="block"><h2>Indicator Set</h2>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable"><thead><tr><th>Indicator</th>{head}</tr></thead>
<tbody>{body}</tbody></table></div>
<p class="note">Risk-free rate: 4.5% (USD strategies) / 9% (BARS, CETES). Alpha, beta,
capture ratios computed vs each strategy's benchmark; VaR/CVaR are monthly at 95%;
skew and excess kurtosis are population moments. Out-of-sample walk-forward;
hypothetical results, past performance does not guarantee future results.</p></section>
{ROTATION_SECTION}
{BT_SECTION}
</main>
<footer class="shell-foot"><div class="container"><p>Research, not investment advice.
Backtested results are hypothetical and do not represent actual trading.</p></div></footer>
{bt_script}
{EPISODE_JS}
{STRAT_FILTER_JS}
</body></html>"""

open(f"{DOCS}/strategies.html", "w", encoding="utf-8").write(HTML)


# ── low-token AI companion (standing rule: every human output gets an AI copy) ─
def ai_row(k):
    m = METRICS[k]
    if not m:
        return f"{k}|{data[k]['name']}|n/a"
    g = lambda key, p=1, sign=False: ("nan" if _nan(m[key]) else
        (f"{m[key]*100:{'+' if sign else ''}.{p}f}%" if key in
         ("ann_ret", "ann_vol", "max_dd", "win", "te", "var95", "cvar95", "best", "worst", "alpha")
         else f"{m[key]:.2f}"))
    w = f"{data[k]['dates'][0][:7]}..{data[k]['dates'][-1][:7]}({m['n']}m)"
    return ("|".join([k, data[k]["name"], "vs " + data[k]["bn"], w,
            "CAGR=" + g("ann_ret"), "vol=" + g("ann_vol"), "Sharpe=" + g("sharpe"),
            "Sortino=" + g("sortino"), "MaxDD=" + g("max_dd"), "Calmar=" + g("calmar"),
            "Omega=" + g("omega"), "GtP=" + g("gtp"), "Recov=" + g("recov"),
            "Ulcer=" + f"{m['ulcer']:.1f}%", "VaR95=" + g("var95"), "CVaR95=" + g("cvar95"),
            "Tail=" + g("tail"), "Win=" + g("win"), "Skew=" + g("skew"), "Kurt=" + g("kurt"),
            "Alpha=" + g("alpha", sign=True), "Beta=" + g("beta"), "TE=" + g("te"),
            "IR=" + g("ir"), "UpCap=" + g("up_cap"), "DnCap=" + g("dn_cap"),
            "LongestDD=" + f"{int(m['longdd'])}m"]))

ai = ["LTCMA SYSTEMATIC STRATEGIES — AI COPY (low-token)",
      f"asof={ASOF}; freq=monthly; OOS walk-forward; hypothetical, not actual trading",
      "names public-safe (no mechanism exposed); rf USD=4.5% BARS=9%",
      "interactive: site lets reader re-base start date; values below = full window",
      "fields: code|name|bench|window|metrics..."]
ai += [ai_row(k) for k in order]
open(f"{DOCS}/strategies.ai.txt", "w", encoding="utf-8").write("\n".join(ai) + "\n")

print("strategies.html built:", {k: (round(METRICS[k]["sharpe"], 2) if METRICS[k] else None) for k in order})
print("strategies.ai.txt written")
