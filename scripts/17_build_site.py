"""Build the GitHub Pages site — IBM Carbon Design styling, locked (non-draggable)
Plotly charts, fuller layout, live market snapshot, CV section, and the rendered
full report. Output -> docs/ (served by Pages). Re-runnable by a scheduled Action.
"""
import os, shutil, json
import numpy as np
import pandas as pd
import markdown
import plotly.graph_objects as go
from glossary import (GLOSSARY, NAV, ccy_badge, bt_load, bt_common,
                      bt_indicators, bt_g100, BT_JS)

from paths import DATA_S as D, REPORT_S as REP, DOCS_S as DOCS  # repo-anchored (2026-06-10)
os.makedirs(f"{DOCS}/figures", exist_ok=True)

# This is a 100% pre-generated static site (no Liquid/Jekyll content). Disable
# GitHub Pages' server-side Jekyll build via .nojekyll — the legacy branch build
# intermittently failed with "Page build failed"/"Deployment failed, try again
# later." (2026-07-02). .nojekyll makes Pages publish the files verbatim.
open(f"{DOCS}/.nojekyll", "w").close()

# --- Carbon Design color tokens ---
INK, BLUE, GOLD, GREEN = "#111111", "#0a2540", "#6b7280", "#0a5d3a"
RED, GREY, BG = "#7c2d12", "#888888", "#fafafa"
ASOF = pd.Timestamp.today().strftime("%d %b %Y")

summ = pd.read_csv(f"{D}/ltcma_summary.csv", index_col=0)
ret = pd.read_csv(f"{D}/ltcma_returns.csv", index_col=0)
corr = pd.read_csv(f"{D}/ltcma_corr_v2.csv", index_col=0)
sig = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)
mcp = pd.read_csv(f"{D}/mc_regime_portfolios.csv", index_col=0)
bt = pd.read_csv(f"{D}/backtest_results.csv")
btb = pd.read_csv(f"{D}/backtest_bond.csv")

LAYOUT = dict(template="plotly_white",
              font=dict(family="Inter, system-ui, sans-serif", size=12,
                        color=INK),
              title_font=dict(color=INK, size=15, family="Inter"),
              margin=dict(l=58, r=24, t=52, b=46), paper_bgcolor="white",
              plot_bgcolor="white", dragmode=False,
              xaxis=dict(gridcolor="#e5e5e5"), yaxis=dict(gridcolor="#e5e5e5"))

def div(fig, name):
    """Render a locked chart: hover stays, drag/zoom disabled so it can't break."""
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False})

# ---------- live market snapshot ----------
last = sig.ffill().iloc[-1]
gpr = pd.read_excel(f"{D}/signals_gpr_raw.xls")[["month", "GPR"]].set_index("month")["GPR"]
gpr.index = gpr.index + pd.offsets.MonthEnd(0)
epu = sig["EPU_US"].dropna()
epu.index = epu.index + pd.offsets.MonthEnd(0)
epu = epu.groupby(epu.index).last()
win = gpr.index.intersection(epu.index)
win = win[win >= "2000-01-01"]
zc = lambda s: (s - s.loc[win].mean()) / s.loc[win].std()
score = (zc(gpr).loc[win] + zc(epu).loc[win]) / 2
regime = "STRESS" if score.iloc[-1] >= score.quantile(2 / 3) else "CALM"
usdmxn = sig["USDMXN"].dropna().iloc[-1]

SNAP = [("US 10Y Treasury", f"{last['UST_10Y']:.2f}%"),
        ("Fed Funds", f"{last['FedFunds']:.2f}%"),
        ("10Y Breakeven Inflation", f"{last['Breakeven_10Y']:.2f}%"),
        ("VIX", f"{last['VIX']:.1f}"),
        ("Geopolitical Risk (GPR)", f"{gpr.iloc[-1]:.0f}"),
        ("Policy Uncertainty (EPU)", f"{epu.iloc[-1]:.0f}"),
        ("USD / MXN", f"{usdmxn:.2f}"),
        ("Market Regime", regime)]

# ---------- 1. priced-in rate path ----------
TEN = {"UST_3M": .25, "UST_6M": .5, "UST_1Y": 1, "UST_2Y": 2, "UST_3Y": 3,
       "UST_5Y": 5, "UST_7Y": 7, "UST_10Y": 10}
y = {t: last[k] / 100 for k, t in TEN.items() if k in last and pd.notna(last[k])}  # tolerate tenors FRED drops (e.g. UST_6M)
ts = sorted(y)
fwx, fwy = [], []
for a, b in zip(ts[:-1], ts[1:]):
    f = ((1 + y[b]) ** b / (1 + y[a]) ** a) ** (1 / (b - a)) - 1
    fwx.append((a + b) / 2); fwy.append(f * 100)
f1 = go.Figure()
f1.add_scatter(x=ts, y=[y[t] * 100 for t in ts], name="Spot Treasury curve",
               mode="lines+markers", line=dict(color=BLUE, width=3))
f1.add_scatter(x=fwx, y=fwy, name="Implied forward short rate",
               mode="lines+markers", line=dict(color=GOLD, width=2, dash="dash"))
f1.add_hline(y=last["FedFunds"], line=dict(color=RED, dash="dot"),
             annotation_text=f"fed funds {last['FedFunds']:.2f}%")
f1.update_layout(title="Priced-in rate path — the market expects no cuts",
                 xaxis_title="maturity (years)", yaxis_title="rate (%)")

# ---------- 2. risk/return map ----------
cmap = {"Equity": BLUE, "Fixed Income": GOLD, "Real Asset": GREEN}
f2 = go.Figure()
for cls, c in cmap.items():
    s = summ[summ["class"] == cls]
    f2.add_scatter(x=s["vol"] * 100, y=s["ER_lambda0.5"] * 100, mode="markers+text",
                   name=cls, marker=dict(color=c, size=11, line=dict(color="white", width=1)),
                   text=[i.replace("_", " ") for i in s.index], textposition="top center",
                   textfont=dict(size=8.5))
f2.update_layout(title="Risk / return map — 12-year LTCMA (base case)",
                 xaxis_title="volatility (%)", yaxis_title="expected return (%)")

# ---------- 3. valuation dispersion ----------
eq = ret[ret["class"] == "Equity"].sort_values("val_now")
vc = [RED if v > 25 else (GOLD if v > 18 else BLUE) for v in eq["val_now"]]
f3 = go.Figure(go.Bar(x=[i.replace("_", " ") for i in eq.index], y=eq["val_now"],
                      marker_color=vc))
f3.update_layout(title="Valuation dispersion — CAPE / P/E by equity market",
                 yaxis_title="CAPE / trailing P/E")

# ---------- 4. expected return by lambda ----------
eqr = ret[ret["class"] == "Equity"].sort_values("ER_lambda0.5")
f4 = go.Figure()
for lam, c in [("ER_lambda0.0", GREY), ("ER_lambda0.5", BLUE), ("ER_lambda1.0", GOLD)]:
    f4.add_bar(y=[i.replace("_", " ") for i in eqr.index], x=eqr[lam] * 100,
               name=f"lambda={lam[-3:]}", orientation="h", marker_color=c)
f4.update_layout(title="Equity expected return across the valuation-reversion dial",
                 barmode="group", xaxis_title="expected return (%)")

# ---------- 5. correlation heatmap ----------
f5 = go.Figure(go.Heatmap(z=corr.values, x=[c.replace("_", " ") for c in corr.columns],
                          y=[c.replace("_", " ") for c in corr.index],
                          colorscale="RdBu_r", zmid=0, zmin=-1, zmax=1))
f5.update_layout(title="Asset correlation matrix (Ledoit-Wolf shrunk)",
                 height=640, margin=dict(l=130, b=130))

# ---------- 6. regime timeline ----------
f6 = go.Figure()
f6.add_scatter(x=win, y=gpr.loc[win], name="GPR (geopolitical risk)",
               line=dict(color=RED, width=1))
f6.add_scatter(x=win, y=epu.loc[win], name="EPU (policy uncertainty)",
               line=dict(color=BLUE, width=1))
thr = score.quantile(2 / 3)
for d in win[score >= thr]:
    f6.add_vrect(x0=d - pd.offsets.MonthBegin(1), x1=d, fillcolor=GOLD,
                 opacity=0.12, line_width=0)
f6.update_layout(title="News-uncertainty regimes (shaded = stress months)",
                 yaxis_title="index level")

# ---------- 7. Monte Carlo portfolio outcomes ----------
f7 = go.Figure()
for p in mcp.index:
    r = mcp.loc[p]
    f7.add_scatter(x=[r["p5"] * 100, r["p95"] * 100], y=[p, p], mode="lines",
                   line=dict(color=GREY, width=6), showlegend=False)
    f7.add_scatter(x=[r["p50"] * 100], y=[p], mode="markers", showlegend=False,
                   marker=dict(color=BLUE, size=14, line=dict(color="white", width=2)))
f7.update_layout(title="Simulated 12-year annualized return — 5th-95th pct, median",
                 xaxis_title="annualized return (%)")

# ---------- 8. backtest ----------
f8 = go.Figure()
f8.add_scatter(x=bt["pred_l0.5"] * 100, y=bt["realized"] * 100, mode="markers",
               name="equity vintages", marker=dict(color=BLUE, size=7, opacity=.7))
f8.add_scatter(x=btb["start_yield"] * 100, y=btb["realized"] * 100, mode="markers",
               name="bond vintages", marker=dict(color=GOLD, size=7, opacity=.7))
f8.add_scatter(x=[-3, 18], y=[-3, 18], mode="lines", name="perfect forecast",
               line=dict(color=GREY, dash="dash"))
f8.update_layout(title="Backtest — forecast vs realized 10-year return",
                 xaxis_title="forecast (%)", yaxis_title="realized (%)")

CHARTS = [
 ("priced-in", f1, False, "What the bond market expects interest rates to do "
  "over the coming years — right now it is not pricing in rate cuts."),
 ("risk-return", f2, False, "Every asset class plotted by its expected yearly "
  "return against how much its value swings. Higher and to the left is better."),
 ("valuation", f3, False, "How expensive each stock market is today. Taller "
  "bars mean a pricier market with less room to rise."),
 ("lambda", f4, False, "How the expected return shifts depending on how "
  "strongly we assume expensive markets cool back down (the 'lambda' dial)."),
 ("correlation", f5, True, "Which assets move together (red) and which move in "
  "opposite directions (blue). Opposites are what makes diversification work."),
 ("regimes", f6, True, "Two news-based gauges of how tense the world is. "
  "Shaded bands are 'stress' months when markets get jumpier."),
 ("montecarlo", f7, False, "The range of where a 12-year investment could "
  "realistically land — from a bad case (left) to a good case (right)."),
 ("backtest", f8, False, "A check on whether this method's past forecasts came "
  "true. The closer the dots sit to the diagonal line, the better."),
]

# ---------- CV / professional experience ----------
EXPERIENCE = [
    ("FACE — Investment Advisor affiliated with GBM", "Financial Advisor",
     "Jan 2026 – Present",
     "Investment advisory for individual clients across multi-asset strategies "
     "(equities, ETFs, FX, metals) on the GBM platform; model-portfolio "
     "construction and asset-allocation proposals by risk profile; proprietary "
     "quantitative analysis and performance dashboards for investor reporting."),
    ("Private Investment Fund", "Quantitative Analyst", "Nov 2024 – Present",
     "Design and validation of systematic and machine-learning strategies in FX, "
     "metals and equities; risk frameworks (position sizing, drawdown control); "
     "robust backtesting (stress tests, Monte Carlo, anti-overfitting controls) "
     "and investment-memo documentation for investment committees; built an "
     "end-to-end multi-strategy research platform (regime detection via Hidden "
     "Markov Models with hmmlearn, Kalman-filtered expected returns, walk-forward "
     "backtesting and live tracking) with AI-assisted development using Claude Code."),
    ("Hostpal Mexico", "Revenue Manager", "Aug 2023 – Feb 2025",
     "Dynamic pricing and demand-forecasting models for a multi-site portfolio; "
     "KPIs and Power BI dashboards that lifted target-achievement; standardized "
     "reporting and SOPs to scale operations."),
    ("CitiBanamex", "Project Manager", "Aug 2022 – Jun 2023",
     "End-to-end migration of 60 corporate clients (payments, FX accounts, APIs) "
     "with full PMO leadership; backend-architecture recommendations to cut "
     "reconciliation times and operational errors."),
    ("HumanSite", "Software Engineer", "Aug 2021 – Aug 2022",
     "Data pipelines from government APIs (SAT) to executive Power BI dashboards, "
     "with a focus on sensitive data, governance and audit traceability."),
]
SKILLS = ["Python", "C++ / C#", "MQL5", "SQL", "scikit-learn", "hmmlearn", "SciPy",
          "Power BI / DAX", "ETL pipelines", "Hidden Markov Models", "Kalman filters",
          "Risk management", "Monte Carlo", "Backtesting", "Asset allocation",
          "AWS S3", "Financial APIs (IBKR, FxPro, MT5)", "Claude Code (AI-assisted dev)"]
CERTS = ["CFA — Level I Candidate (exam May 2026)",
         "AMIB Figure 3 — current securities-advisory license (renewed Nov 2025)",
         "B.S. Finance — Tecnológico de Monterrey (2019–2021)"]

# ---------- assemble HTML ----------
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"

snap = "".join(
    f'<div class="metric{" m-" + v.lower() if k == "Market Regime" else ""}">'
    f'<div class="mv">{v}</div><div class="mk">{k}</div></div>' for k, v in SNAP)
charts = "".join(
    f'<article class="tile chart{" wide" if wide else ""}">'
    f'<div class="ch">{div(fig, cid)}</div>'
    f'<p class="caption">{cap}</p></article>' for cid, fig, wide, cap in CHARTS)
exp = "".join(
    f'<div class="role"><div class="role-h"><span class="role-co">{co}</span>'
    f'<span class="role-d">{d}</span></div>'
    f'<div class="role-t">{t}</div><p>{desc}</p></div>'
    for co, t, d, desc in EXPERIENCE)
skills = "".join(f'<span class="tag">{s}</span>' for s in SKILLS)
# ---------- Systematic Strategy Backtests (interactive) ----------
import json as _json
_bt = bt_load()
_common, _aligned, _spy = bt_common(_bt)
_DCOLS = ["SARS", "DUO", "MARS", "SP500"]
_DNAMES = {"SARS": _bt["SARS"]["name"], "DUO": _bt["DUO"]["name"],
           "MARS": _bt["MARS"]["name"], "SP500": "S&amp;P 500"}
_DMET = {k: bt_indicators(_bt[k]["s"], _bt[k]["b"], _bt[k]["rf"]) for k in ["SARS", "DUO", "MARS"]}
_DMET["SP500"] = bt_indicators(_spy, _spy, 0.045)

f_strat = go.Figure()
for _k in ["SARS", "DUO", "MARS"]:
    f_strat.add_scatter(x=_common, y=bt_g100(_aligned[_k]), mode="lines",
                        name=_bt[_k]["name"], line=dict(color=_bt[_k]["color"], width=2.2))
f_strat.add_scatter(x=_common, y=bt_g100(_spy), mode="lines", name="S&P 500",
                    line=dict(color=RED, width=1.6, dash="dot"))
f_strat.update_layout(title="Growth of 100 — strategies vs S&P 500 (USD)",
                      yaxis_type="log", legend=dict(orientation="h", y=-0.22), height=380)
_chart = div(f_strat, "dash_eq")

def _dpct(x): return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.1f}%"
def _dnum(x): return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"
_DROWS = [("CAGR (ann.)", "ann_ret", _dpct), ("Ann. volatility", "ann_vol", _dpct),
          ("Sharpe", "sharpe", _dnum), ("Sortino", "sortino", _dnum),
          ("Max drawdown", "max_dd", _dpct), ("Calmar", "calmar", _dnum)]
_dhead = "".join(f"<th>{_DNAMES[k]}</th>" for k in _DCOLS)
_dbody = ""
for _label, _key, _fmt in _DROWS:
    _cells = "".join(f'<td id="d_{k}_{_key}">{_fmt(_DMET[k][_key]) if _DMET[k] else "—"}</td>' for k in _DCOLS)
    _dbody += f"<tr><td>{_label}</td>{_cells}</tr>"
_DWINTXT = {k: f'{_bt[k]["dates"][0][:4]}&ndash;{_bt[k]["dates"][-1][:4]} ({len(_bt[k]["dates"])}m)'
            for k in ["SARS", "DUO", "MARS"]}
_DWINTXT["SP500"] = f'2007&ndash;2026 ({len(_common)}m)'
_dwin = "".join(f'<td id="d_{k}_window">{_DWINTXT[k]}</td>' for k in _DCOLS)
_dbody += f'<tr class="wrow"><td>OOS window</td>{_dwin}</tr>'

_DCTRL = ('<div class="btctl"><div class="btranges">'
          '<button class="btr on" data-bt-range="all" data-bt-group="d">All</button>'
          '<button class="btr" data-bt-range="15" data-bt-group="d">15Y</button>'
          '<button class="btr" data-bt-range="10" data-bt-group="d">10Y</button>'
          '<button class="btr" data-bt-range="5" data-bt-group="d">5Y</button>'
          '<button class="btr" data-bt-range="3" data-bt-group="d">3Y</button>'
          '<button class="btr" data-bt-range="1" data-bt-group="d">1Y</button>'
          '</div><input type="range" id="d-start" class="btslider" aria-label="Backtest start date">'
          '<span id="d-start-lbl" class="btlbl">From &hellip;</span></div>')

_dash_data = dict(_bt)
_dash_data["SP500"] = dict(name="S&P 500", color=RED, rf=0.045, bn="S&P 500",
                           dates=_common, s=_spy, b=_spy)
_dcfg = ('{mode:"own",cellPrefix:"d",group:"d",'
         'cols:["SARS","DUO","MARS","SP500"],'
         'rows:["ann_ret","ann_vol","sharpe","sortino","max_dd","calmar"],'
         'eq:"dash_eq",slider:"d-start",label:"d-start-lbl"}')
_dbt_script = ('<script>window.BT_DATA=' + _json.dumps(_dash_data, separators=(",", ":")) +
               ';window.BT_CFG=' + _dcfg + ';</script>\n<script>' + BT_JS + '</script>')

STRATBT = (
    '<section class="block"><h2>Systematic Strategy Backtests</h2>'
    '<p class="note">Out-of-sample (walk-forward) performance of three proprietary '
    'regime-adaptive strategies versus the S&amp;P 500 &mdash; equity-like returns with a '
    'fraction of the index&rsquo;s drawdown. Drag the slider (or pick a range) to move the '
    'start date: the curve re-bases to 100 and every score recomputes live. Hypothetical '
    'results; the detection-and-optimisation methodology is proprietary. Full indicator set '
    'on the <a href="strategies.html">Strategies</a> page; detail in the '
    '<a href="report.html">report</a> (Section&nbsp;10). The full research record behind '
    'these — including every negative result — is on the '
    '<a href="research.html">Research Notes</a> page.</p>'
    + _DCTRL +
    '<div class="tile chart wide"><div class="ch">' + _chart + '</div></div>'
    '<div class="tile" style="padding:4px 16px 10px;overflow-x:auto">'
    '<table class="ptable"><thead><tr><th>Indicator</th>' + _dhead + '</tr></thead>'
    '<tbody>' + _dbody + '</tbody></table></div>'
    + _dbt_script +
    '</section>')
certs = "".join(f"<li>{c}</li>" for c in CERTS)

# ---------- daily recap (what changed since the previous update) ----------
RECAP_PATH = f"{D}/recap_prev.json"
def _prior(col):
    s = sig[col].dropna()
    return float(s.iloc[-2]) if len(s) > 1 else None
# (label, current value, prior-observation fallback, unit, decimals)
RECAP_SPEC = [
    ("US 10Y",           float(last["UST_10Y"]),      _prior("UST_10Y"),      "%", 2),
    ("Fed Funds",        float(last["FedFunds"]),      _prior("FedFunds"),     "%", 2),
    ("10Y Breakeven",    float(last["Breakeven_10Y"]), _prior("Breakeven_10Y"),"%", 2),
    ("VIX",              float(last["VIX"]),           _prior("VIX"),          "",  1),
    ("HY credit spread", float(last["HY_OAS"]),        _prior("HY_OAS"),       "%", 2),
    ("USD / MXN",        float(usdmxn),                _prior("USDMXN"),       "",  2),
]
try:
    _prev_vals = json.load(open(RECAP_PATH)).get("values", {})
except Exception:
    _prev_vals = {}
recap_tiles = ""
for _lbl, _cur, _seed, _unit, _dec in RECAP_SPEC:
    _base = _prev_vals.get(_lbl, _seed)          # last published value, else prior obs
    _cur_s = f"{_cur:.{_dec}f}{_unit}"
    if _base is None:
        _sub = _lbl
    else:
        _d = _cur - _base
        if abs(_d) < 0.5 * 10 ** (-_dec):
            _sub = f"{_lbl} &middot; <span style='color:{GREY}'>&mdash; flat</span>"
        else:
            _arrow = "&#9650;" if _d > 0 else "&#9660;"   # neutral ▲ / ▼ (no good/bad)
            _sub = (f"{_lbl} &middot; <span style='color:{INK};font-weight:600'>"
                    f"{_arrow} {_d:+.{_dec}f}{_unit}</span>")
    recap_tiles += (f'<div class="metric"><div class="mv">{_cur_s}</div>'
                    f'<div class="mk">{_sub}</div></div>')
json.dump({"date": ASOF, "values": {l: c for l, c, *_ in RECAP_SPEC}},
          open(RECAP_PATH, "w"), indent=2)
RECAP = (
    '<section class="block"><h2>Daily Recap</h2>'
    '<p class="note">Key market levels and how they have moved since the previous '
    'update &mdash; a quick read on what changed. Arrows show direction only, not '
    'good or bad.</p>'
    f'<div class="metrics" style="grid-template-columns:repeat(3,1fr)">{recap_tiles}</div>'
    '</section>')

INDEX = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carlos Duarte — Capital Market Assumptions</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Long-Term Capital Market Assumptions</h1>
<p class="lede">A proprietary 12-year forward outlook for global asset classes —
building-block expected returns, Ledoit-Wolf risk modelling, and a
regime-switching GPU Monte Carlo engine.</p>
<p class="asof">As of {ASOF} &middot; base currency USD &middot; built on free public data</p>
</div></section>
<main class="container">
{RECAP}
<section class="block"><h2>Live Market Snapshot</h2>{ccy_badge("USD")}
<p class="note">Auto-refreshed daily from public data (FRED, Yahoo Finance,
GPR / EPU uncertainty indices). New to a term? See the
<a href="glossary.html">Glossary</a>.</p>
<div class="metrics" style="grid-template-columns:repeat(4,1fr)">{snap}</div></section>
<section class="block"><h2>Model Output</h2>
{ccy_badge("USD", "all expected returns are in US dollars")}
<p class="note">Each chart below has a plain-language explanation; full
definitions are in the <a href="glossary.html">Glossary</a>.</p>
<div class="grid">{charts}</div></section>
{STRATBT}
<section class="block"><h2>Full Written Report</h2>
<p>Complete analysis — methodology, macro backdrop, return tables, the
strategic-edge scan, the methodology backtest and limitations.</p>
<a class="btn" href="report.html">Open the full LTCMA report &rarr;</a></section>
<section class="block" id="about"><h2>About — Carlos Alberto Duarte Morales</h2>
<p class="lede2">Financial advisor and systems engineer specialised in
quantitative systems, risk management and data pipelines for financial
applications. Mexico City &middot; CFA Level I Candidate.</p>
<p class="contact"><a href="mailto:carlosduartem@hotmail.com">carlosduartem@hotmail.com</a> &middot; <a href="tel:+525525111070">+52 55 2511 1070</a></p>
<h3>Professional Experience</h3>{exp}
<h3>Credentials &amp; Education</h3><ul class="certs">{certs}</ul>
<h3>Technical Skills</h3><div class="tags">{skills}</div>
<h3>Open Source</h3>
<p>Open-source: <a href="https://github.com/DuiArte/terse">Terse &mdash; token-efficient LLM language</a> &middot; <a href="https://github.com/DuiArte/ilml">ILML &mdash; a language for AI-to-AI communication</a></p></section>
</main>
<footer class="shell-foot"><div class="container">
<p>Built with free public data and open-source tools. Expected returns are
forward-looking estimates, not guarantees; actual outcomes will differ.
This is research, not investment advice.</p></div></footer>
</body></html>"""
open(f"{DOCS}/index.html", "w", encoding="utf-8").write(INDEX)

# ---------- report.html ----------
for f in os.listdir(f"{REP}/figures"):
    shutil.copy(f"{REP}/figures/{f}", f"{DOCS}/figures/{f}")
body = markdown.markdown(open(f"{REP}/LTCMA_2026.md", encoding="utf-8").read(),
                         extensions=["tables", "fenced_code", "sane_lists"])
REPORT = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carlos Duarte — Full Report</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<main class="container"><article class="tile report">{body}</article></main>
<footer class="shell-foot"><div class="container"><p>Research, not investment
advice.</p></div></footer></body></html>"""
open(f"{DOCS}/report.html", "w", encoding="utf-8").write(REPORT)

# ---------- glossary.html ----------
gloss_html = ""
for cat, items in GLOSSARY.items():
    rows = "".join(f"<dt>{t}</dt><dd>{d}</dd>" for t, d in items)
    gloss_html += (f'<section class="block"><h2>{cat}</h2>'
                   f'<dl class="gloss">{rows}</dl></section>')
GLOSSARY_PAGE = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carlos Duarte — Glossary</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container"><h1>Glossary</h1>
<p class="lede">Plain-language explanations of every concept used across this
site — no math, no jargon. If a term on any page is unclear, it is defined here.</p>
</div></section>
<main class="container">{gloss_html}</main>
<footer class="shell-foot"><div class="container"><p>Research, not investment
advice.</p></div></footer></body></html>"""
open(f"{DOCS}/glossary.html", "w", encoding="utf-8").write(GLOSSARY_PAGE)

# ---------- projects.html (GitHub-style repo cards) ----------
# Each project links to its own repo. Placeholder repos render "Coming soon"
# (faded) until created; the operating edge stays private by design.
_OCTO = ('<svg class="gh-mark" viewBox="0 0 16 16" width="20" height="20" '
         'aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 '
         '3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37'
         '-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 '
         '1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64'
         '-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 '
         '2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 '
         '1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54'
         '.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 '
         '8c0-4.42-3.58-8-8-8Z"></path></svg>')
# (name, repo_handle, url, description, status, live?)
PROJECTS = [
    ("LTCMA Methodology", "DuiArte/ltcma-methodology",
     "https://github.com/DuiArte/ltcma-methodology",
     "Long-term capital market assumptions &mdash; building-block expected returns, "
     "Ledoit-Wolf risk, regime-switching Monte Carlo.", "Research", True),
    ("Static Drift-Weight 50/30/20", "DuiArte/static-drift-weight",
     "https://github.com/DuiArte/static-drift-weight",
     "The deployed core sleeve &mdash; SPY/IEF/GLD drift-weighted, no gating. "
     "Sharpe 1.33, GFC-stress-tested to a sub-10% monthly drawdown.", "Deployed", True),
    ("SignalLib Framework", "DuiArte/signallib-framework",
     "https://github.com/DuiArte/signallib-framework",
     "Signal-discovery rig &mdash; many uncorrelated weak signals over static "
     "weights, with deflated-Sharpe and PBO gates baked in.", "Research", True),
    ("Terse", "DuiArte/terse", "https://github.com/DuiArte/terse",
     "A token-efficient language for compressing instructions and documents "
     "before they reach an LLM.", "Tooling", True),
    ("AI Procedures (Quant)", "DuiArte/ai-procedures-quant",
     "https://github.com/DuiArte/ai-procedures-quant",
     "The runbooks and automated daily-refresh infrastructure that keep this "
     "research lab current.", "Tooling", True),
    ("Backtests Archive", "DuiArte/backtests-archive",
     "https://github.com/DuiArte/backtests-archive",
     "Selected backtest reports &mdash; methodology and headline results; the live "
     "parameters stay private.", "Research", True),
]
_BADGE = {"Deployed": "badge-deployed", "Research": "badge-research", "Tooling": "badge-tooling"}
proj_cards = ""
for name, handle, url, desc, status, live in PROJECTS:
    klass = "proj-card" + ("" if live else " proj-soon")
    badges = f'<span class="pbadge {_BADGE[status]}">{status}</span>'
    if not live:
        badges += '<span class="pbadge badge-soon">Coming soon</span>'
    proj_cards += (
        f'<a class="{klass}" href="{url}" target="_blank" rel="noopener noreferrer">'
        f'<div class="proj-top">{_OCTO}<span class="proj-handle">{handle}</span></div>'
        f'<div class="proj-name">{name}</div>'
        f'<p class="proj-desc">{desc}</p>'
        f'<div class="proj-foot">{badges}'
        f'<span class="proj-cta">View on GitHub &#8599;</span></div></a>')

PROJECTS_PAGE = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carlos Duarte — Projects</title>
<meta name="description" content="A portfolio of quantitative-research projects by Carlos Duarte — methodology, deployed strategies and tooling, each linking to its own GitHub repository.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css">
<style>
.proj-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:1.5rem;margin-top:8px}}
.proj-card{{display:block;background:#fff;border:1px solid #e5e5e5;border-radius:0;
padding:20px 22px;text-decoration:none;color:#111;transition:background .15s ease-out,border-color .15s ease-out}}
.proj-card:hover{{border-color:#d4d4d4;background:rgba(10,37,64,.045)}}
.proj-soon{{opacity:.7}}
.proj-top{{display:flex;align-items:center;gap:8px;color:#111;margin-bottom:10px}}
.gh-mark{{flex:none}}
.proj-handle{{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums;font-size:13px;
color:#0a2540;font-weight:500;word-break:break-all}}
.proj-name{{font-family:'Spectral',Georgia,serif;font-size:18px;font-weight:500;margin-bottom:6px}}
.proj-desc{{font-size:14px;color:#555;margin:0 0 16px;line-height:1.55}}
.proj-foot{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.pbadge{{font-size:10.5px;font-weight:500;padding:3px 9px;border-radius:0;letter-spacing:.06em;text-transform:uppercase;border:1px solid transparent}}
.badge-deployed{{background:none;color:#0a5d3a;border-color:rgba(10,93,58,.35)}}
.badge-research{{background:none;color:#1e3a8a;border-color:rgba(30,58,138,.35)}}
.badge-tooling{{background:none;color:#5b21b6;border-color:rgba(91,33,182,.35)}}
.badge-soon{{background:none;color:#6b7280;border-color:#e5e5e5}}
.proj-cta{{margin-left:auto;font-family:'JetBrains Mono',ui-monospace,monospace;
font-size:12px;font-weight:500;color:#0a2540}}
</style></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container"><h1>Projects</h1>
<p class="lede">A portfolio of related research projects. Each repository holds the
public-facing methodology and selected artifacts &mdash; the operating edge stays
private. Restraint is deliberate: enough to build on, not enough to copy.</p>
</div></section>
<main class="container"><section class="block">
<div class="proj-grid">{proj_cards}</div></section></main>
<footer class="shell-foot"><div class="container"><p>Each link opens the project's
GitHub repository. Research and monitoring, not investment advice.</p></div></footer>
</body></html>"""
open(f"{DOCS}/projects.html", "w", encoding="utf-8").write(PROJECTS_PAGE)

# ---------- Carbon-style CSS ----------
CSS = r"""/* ============================================================================
   Carlos Duarte · Quantitative Research — institutional editorial identity
   Monochrome + single Oxford-blue accent. Serif headings, restrained sans body,
   mono for figures. Hairline borders, no shadows, no gradients. Demure.
   ============================================================================ */
:root{
  --bg:#fafafa; --panel:#ffffff;
  --ink:#111111; --sec:#555555; --muted:#888888;
  --line:#e5e5e5; --line-strong:#d4d4d4;
  --accent:#0a2540; --accent-tint:rgba(10,37,64,.045); --accent-line:rgba(10,37,64,.20);
  --pos:#0a5d3a; --neg:#7c2d12;
  --st-green:#0a5d3a; --st-blue:#1e3a8a; --st-purple:#5b21b6; --st-gray:#6b7280;
  --serif:'Spectral',Charter,"Iowan Old Style",Cambria,Georgia,serif;
  --sans:'Inter',system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --wrap:min(1100px,92vw);
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font-family:var(--sans);font-weight:400;color:var(--ink);background:var(--bg);
  line-height:1.55;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.container{max-width:var(--wrap);margin:0 auto;padding:0 24px}
a{color:var(--accent);transition:color .15s ease-out,background .15s ease-out,border-color .15s ease-out}

/* ---- header / nav ---- */
.shell{background:var(--bg);position:sticky;top:0;z-index:50;border-bottom:1px solid var(--line)}
.shell-in{max-width:var(--wrap);margin:0 auto;padding:0 24px;min-height:60px;
  display:flex;align-items:center;gap:28px;flex-wrap:wrap}
.brand{font-family:var(--serif);color:var(--ink);font-size:17px;font-weight:500;letter-spacing:.03em}
.brand b{font-weight:500}
nav{display:flex;gap:0;margin-left:auto;flex-wrap:wrap}
nav a{color:var(--sec);text-decoration:none;font-size:13px;padding:6px 13px;
  display:flex;align-items:center;border-bottom:2px solid transparent;letter-spacing:.01em}
nav a:hover{color:var(--ink);border-bottom-color:var(--accent-line)}
nav a.active{color:var(--ink);border-bottom-color:var(--accent)}

/* ---- hero (editorial, no gradient/glow) ---- */
.hero{background:var(--bg);color:var(--ink);padding:5rem 0 3.25rem;border-bottom:1px solid var(--line)}
.hero .container{padding:0 24px}
.hero h1{font-family:var(--serif);font-size:clamp(30px,4.4vw,46px);font-weight:500;
  letter-spacing:-.01em;line-height:1.18;max-width:18em}
.lede{font-size:17px;font-weight:400;color:var(--sec);margin-top:1.1rem;max-width:46em;line-height:1.55}
.lede a{color:var(--accent);text-decoration:underline;text-underline-offset:2px}
.asof{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:12px;
  color:var(--muted);margin-top:1.5rem;letter-spacing:.02em}

/* ---- blocks / section headers ---- */
main{padding:4rem 0 5rem}
.block{margin-bottom:4rem}
.block>h2{font-family:var(--serif);font-size:21px;font-weight:500;letter-spacing:0;
  color:var(--ink);padding-bottom:.6rem;margin-bottom:1.4rem;border-bottom:1px solid var(--line);
  line-height:1.25}
.note{color:var(--sec);font-size:14px;margin:-.4rem 0 1.2rem;line-height:1.55;max-width:52em}
.note a{color:var(--accent);text-decoration:underline;text-underline-offset:2px}

/* ---- metric tiles ---- */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1.5rem;
  background:none;border:0;box-shadow:none}
.metric{background:var(--panel);border:1px solid var(--line);padding:1.25rem 1.25rem 1.1rem;
  transition:background .15s ease-out}
.metric:hover{background:var(--accent-tint)}
.mv{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:26px;font-weight:500;
  color:var(--ink);letter-spacing:-.01em;line-height:1.1}
.mk{font-size:11px;color:var(--muted);margin-top:.55rem;letter-spacing:.06em;text-transform:uppercase}
.m-stress .mv{color:var(--neg)}.m-calm .mv{color:var(--pos)}

/* ---- chart grid / tiles ---- */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
.tile{background:var(--panel);border:1px solid var(--line);padding:14px;
  box-shadow:none;transition:background .15s ease-out}
.tile:hover{background:#fff}
.chart.wide{grid-column:1 / -1}
.ch{width:100%}

/* ---- button ---- */
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
  padding:.8rem 1.4rem;font-size:14px;margin-top:.4rem;font-weight:500;
  border:1px solid var(--accent);box-shadow:none;transition:background .15s ease-out}
.btn:hover{background:#0d3055}

/* ---- about / CV ---- */
.lede2{font-size:16px;font-weight:400;color:var(--sec);max-width:48em;margin-bottom:.5rem}
.contact{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:13px;
  color:var(--sec);margin:0 0 .5rem;letter-spacing:.01em}
.contact a{color:var(--accent);text-decoration:none}
.contact a:hover{text-decoration:underline}
.block h3{font-family:var(--serif);font-size:16px;font-weight:500;text-transform:none;
  letter-spacing:0;color:var(--ink);margin:1.9rem 0 .9rem}
.role{border-left:2px solid var(--accent-line);padding:2px 0 2px 18px;margin-bottom:1.4rem}
.role-h{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
.role-co{font-weight:500;font-size:15px}
.role-d{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:12px;color:var(--muted)}
.role-t{font-size:14px;color:var(--accent);margin:2px 0 6px}
.role p{font-size:14px;color:var(--sec);max-width:58em}
.certs{list-style:none;display:flex;flex-direction:column;gap:6px}
.certs li{font-size:14px;padding-left:18px;position:relative;color:var(--sec)}
.certs li:before{content:"";position:absolute;left:0;top:9px;width:5px;height:5px;background:var(--accent)}
.tags{display:flex;flex-wrap:wrap;gap:8px}
.tag{background:var(--panel);border:1px solid var(--line);font-size:12px;padding:6px 13px;
  font-family:var(--mono);color:var(--sec);transition:border-color .15s ease-out,color .15s ease-out}
.tag:hover{border-color:var(--accent-line);color:var(--accent)}

/* ---- footer ---- */
.shell-foot{background:var(--bg);color:var(--muted);padding:2.5rem 0;font-size:.85rem;
  border-top:1px solid var(--line);line-height:1.6}
.shell-foot a{color:var(--accent)}

/* ---- report (editorial long-form) ---- */
.report{padding:3rem 0;max-width:46em;margin:0 auto;box-shadow:none;background:none;border:0}
.report h1{font-family:var(--serif);font-size:34px;font-weight:600;margin:.4rem 0;letter-spacing:-.01em;line-height:1.2}
.report h2{font-family:var(--serif);font-size:23px;font-weight:500;color:var(--ink);
  border-bottom:1px solid var(--line);padding-bottom:.4rem;margin:2.4rem 0 1rem;line-height:1.25}
.report h3{font-family:var(--serif);font-size:17px;font-weight:500;margin:1.6rem 0 .5rem;
  text-transform:none;letter-spacing:0;color:var(--ink)}
.report p,.report li{font-size:15px;color:var(--ink);margin:.6rem 0;line-height:1.65}
.report a{color:var(--accent);text-underline-offset:2px}
.report table{border-collapse:collapse;width:100%;font-size:13px;margin:1.2rem 0;
  font-variant-numeric:tabular-nums}
.report th{background:none;color:var(--muted);padding:8px 10px;text-align:left;font-weight:500;
  font-size:11px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--line-strong)}
.report td{border:0;border-bottom:1px solid var(--line);padding:7px 10px}
.report tr:nth-child(even) td{background:none}
.report img{max-width:100%;margin:1.2rem 0;border:1px solid var(--line)}
.report blockquote{border-left:2px solid var(--accent-line);background:none;margin:1rem 0;
  padding:.5rem 1.1rem;color:var(--sec)}
.report code{font-family:var(--mono);background:#f0f0f0;font-size:90%;padding:1px 5px}
.report pre{background:#f0f0f0;color:var(--ink);padding:14px;overflow:auto;font-size:12px;border:1px solid var(--line)}
.report pre code{background:none;color:inherit}

/* ---- data tables ---- */
.ptable{width:100%;border-collapse:collapse;font-size:13px;margin-top:.4rem;font-variant-numeric:tabular-nums}
.ptable th{background:none;color:var(--muted);text-align:right;padding:9px 12px;
  font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
  border-bottom:1px solid var(--line-strong)}
.ptable th:first-child{text-align:left}
.ptable td{border:0;border-bottom:1px solid var(--line);padding:8px 12px;text-align:right;
  font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink)}
.ptable td:first-child{text-align:left;font-family:var(--sans);font-weight:500}
.ptable tr:hover td{background:var(--accent-tint)}
.ptable tr.grp td{background:none;color:var(--sec);font-weight:500;font-size:10.5px;
  text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--line-strong);padding-top:14px;
  font-family:var(--sans)}
.ptable tr.wrow td{border-top:1px solid var(--line-strong);color:var(--muted);font-size:11px}
.pos{color:var(--pos)}.neg{color:var(--neg)}
.scaled-note{background:none;border-left:2px solid var(--accent-line);padding:.6rem 1rem;
  font-size:13px;color:var(--sec);margin-bottom:1.1rem}

/* ---- interactive backtest control ---- */
.btctl{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:2px 0 16px}
.btranges{display:inline-flex;border:1px solid var(--line-strong)}
.btr{background:var(--panel);color:var(--sec);border:0;border-right:1px solid var(--line-strong);
  padding:6px 14px;font-family:var(--sans);font-size:12.5px;font-weight:500;cursor:pointer;
  transition:background .12s ease-out,color .12s ease-out}
.btr:last-child{border-right:0}
.btr:hover{background:var(--accent-tint)}
.btr.on{background:var(--accent);color:#fff}
.btslider{flex:1 1 180px;min-width:140px;max-width:360px;accent-color:var(--accent);cursor:pointer;height:3px}
.btlbl{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:12px;color:var(--sec);
  white-space:nowrap;min-width:118px}

/* ---- stock cards ---- */
.scards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:1.5rem;
  background:none;border:0;box-shadow:none}
.scard{background:var(--panel);border:1px solid var(--line);padding:1.25rem 1.25rem;
  text-decoration:none;color:var(--ink);transition:background .15s ease-out}
.scard:hover{background:var(--accent-tint)}
.sc-t{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:20px;font-weight:500;color:var(--ink)}
.sc-n{font-size:12px;color:var(--muted);margin-top:4px}
.scard:hover .sc-n{color:var(--sec)}

/* ---- currency badge / captions / glossary ---- */
.ccy{display:inline-block;background:none;color:var(--sec);border:1px solid var(--line);
  font-size:11px;padding:3px 10px;margin:-.4rem 0 1rem;letter-spacing:.02em}
.ccy b{color:var(--accent);font-weight:500}
.caption{font-size:13px;color:var(--muted);padding:4px 2px 10px;margin:0;line-height:1.5}
.ccy-toggle{display:inline-flex;border:1px solid var(--line-strong);margin-bottom:12px}
.ccy-toggle button{background:var(--panel);color:var(--sec);border:0;border-right:1px solid var(--line-strong);
  padding:7px 22px;font-family:var(--sans);font-size:13px;font-weight:500;cursor:pointer;
  transition:background .12s ease-out,color .12s ease-out}
.ccy-toggle button:last-child{border-right:0}
.ccy-toggle button.active{background:var(--accent);color:#fff}
.gloss{margin:0}
.gloss dt{font-family:var(--serif);font-weight:500;font-size:16px;color:var(--ink);margin-top:1.3rem}
.gloss dd{font-size:14px;color:var(--sec);margin:.25rem 0 0;max-width:56em;line-height:1.6}

/* ---- interaction polish (2026-06-10): smooth anchors, scroll-reveal, ---- */
/* ---- sticky table headers, sortable/searchable tables, print          ---- */
html{scroll-behavior:smooth}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
.rv{opacity:0;transform:translateY(6px);transition:opacity .3s ease-out,transform .3s ease-out}
.rv.vis,.vis{opacity:1;transform:none}
.ptable thead th{position:sticky;top:59px;background:var(--panel);z-index:2}
th.sortable{cursor:pointer;user-select:none}
th.sortable:hover{color:var(--ink)}
th.sortable .arr{font-size:9px;color:var(--accent);margin-left:3px}
.tsearch{font:400 13px var(--sans);color:var(--ink);background:var(--panel);
  border:1px solid var(--line-strong);padding:7px 12px;width:230px;max-width:100%;
  margin:2px 0 12px;outline:none}
.tsearch:focus{border-color:var(--accent-line)}
.tsearch::placeholder{color:var(--muted)}
@media print{
  .shell,.shell-foot,.pills,.toc,.btctl,.ccy-toggle,.tsearch{display:none!important}
  body{background:#fff}
  .hero{padding:1rem 0}
  main{padding:1rem 0}
  .tile,.metric,.btcard{border-color:#bbb;break-inside:avoid}
  .block{break-inside:avoid-page;margin-bottom:2rem}
  a{color:#111;text-decoration:none}
  .rv{opacity:1;transform:none}
}

/* ---- responsive ---- */
@media(max-width:820px){
  .grid{grid-template-columns:1fr}
  .metrics{grid-template-columns:repeat(2,1fr)!important}
  .hero{padding:3.5rem 0 2.5rem}
}
@media(max-width:560px){
  .container{padding:0 16px}
  .shell-in{padding:12px 16px;gap:8px;min-height:0}
  .brand{font-size:15px}
  nav{margin-left:0;overflow-x:auto;-webkit-overflow-scrolling:touch;width:100%}
  nav a{padding:6px 9px;font-size:12.5px;white-space:nowrap}
  .hero{padding:3rem 0 2.25rem}
  main{padding:3rem 0}.block{margin-bottom:3rem}
  .metrics{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:1rem}
  .metric{min-width:0;padding:1.1rem .9rem 1rem}.mv{font-size:18px}
  .report table{display:block;overflow-x:auto;white-space:nowrap}
  .ptable{font-size:12px;display:block;overflow-x:auto;white-space:nowrap}
  .ptable th,.ptable td{padding:7px 8px}
  .btslider{max-width:100%;flex-basis:100%}.btlbl{min-width:0}.btctl{gap:9px}
  .role-h{flex-direction:column;gap:2px}
  .btn{padding:.8rem 1.2rem;display:block;text-align:center}
}
"""
open(f"{DOCS}/style.css", "w", encoding="utf-8").write(CSS)
print(f"Carbon site built -> {DOCS}  | regime={regime} | as-of {ASOF}")
print(f"  index.html, report.html, style.css, figures/  ({len(CHARTS)} locked charts)")
