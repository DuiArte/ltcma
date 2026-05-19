"""Build the GitHub Pages site — IBM Carbon Design styling, locked (non-draggable)
Plotly charts, fuller layout, live market snapshot, CV section, and the rendered
full report. Output -> docs/ (served by Pages). Re-runnable by a scheduled Action.
"""
import os, shutil
import numpy as np
import pandas as pd
import markdown
import plotly.graph_objects as go
from glossary import GLOSSARY, NAV, ccy_badge

D = os.path.expanduser("~/LTCMA/data")
REP = os.path.expanduser("~/LTCMA/report")
DOCS = os.path.expanduser("~/LTCMA/docs")
os.makedirs(f"{DOCS}/figures", exist_ok=True)

# --- Carbon Design color tokens ---
INK, BLUE, GOLD, GREEN = "#161616", "#0f62fe", "#b28600", "#198038"
RED, GREY, BG = "#da1e28", "#8d8d8d", "#f4f4f4"
ASOF = pd.Timestamp.today().strftime("%d %b %Y")

summ = pd.read_csv(f"{D}/ltcma_summary.csv", index_col=0)
ret = pd.read_csv(f"{D}/ltcma_returns.csv", index_col=0)
corr = pd.read_csv(f"{D}/ltcma_corr_v2.csv", index_col=0)
sig = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)
mcp = pd.read_csv(f"{D}/mc_regime_portfolios.csv", index_col=0)
bt = pd.read_csv(f"{D}/backtest_results.csv")
btb = pd.read_csv(f"{D}/backtest_bond.csv")

LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=12,
                        color=INK),
              title_font=dict(color=INK, size=15, family="IBM Plex Sans"),
              margin=dict(l=58, r=24, t=52, b=46), paper_bgcolor="white",
              plot_bgcolor="white", dragmode=False,
              xaxis=dict(gridcolor="#e0e0e0"), yaxis=dict(gridcolor="#e0e0e0"))

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
y = {t: last[k] / 100 for k, t in TEN.items()}
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
     "and investment-memo documentation for investment committees."),
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
SKILLS = ["Python", "C++ / C#", "MQL5", "SQL", "Power BI / DAX", "ETL pipelines",
          "Risk management", "Monte Carlo", "Backtesting", "Asset allocation",
          "AWS S3", "Financial APIs (IBKR, FxPro, MT5)"]
CERTS = ["CFA — Level I Candidate (exam February 2026)",
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
certs = "".join(f"<li>{c}</li>" for c in CERTS)

INDEX = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LTCMA 2026 — Capital Market Assumptions</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>LTCMA&nbsp;2026</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Long-Term Capital Market Assumptions</h1>
<p class="lede">A proprietary 12-year forward outlook for global asset classes —
building-block expected returns, Ledoit-Wolf risk modelling, and a
regime-switching GPU Monte Carlo engine.</p>
<p class="asof">As of {ASOF} &middot; base currency USD &middot; built on free public data</p>
</div></section>
<main class="container">
<section class="block"><h2>Live Market Snapshot</h2>{ccy_badge("USD")}
<p class="note">Auto-refreshed weekly from public data (FRED, Yahoo Finance,
GPR / EPU uncertainty indices). New to a term? See the
<a href="glossary.html">Glossary</a>.</p>
<div class="metrics" style="grid-template-columns:repeat(4,1fr)">{snap}</div></section>
<section class="block"><h2>Model Output</h2>
{ccy_badge("USD", "all expected returns are in US dollars")}
<p class="note">Each chart below has a plain-language explanation; full
definitions are in the <a href="glossary.html">Glossary</a>.</p>
<div class="grid">{charts}</div></section>
<section class="block"><h2>Full Written Report</h2>
<p>Complete analysis — methodology, macro backdrop, return tables, the
strategic-edge scan, the methodology backtest and limitations.</p>
<a class="btn" href="report.html">Open the full LTCMA report &rarr;</a></section>
<section class="block" id="about"><h2>About — Carlos Alberto Duarte Morales</h2>
<p class="lede2">Financial advisor and systems engineer specialised in
quantitative systems, risk management and data pipelines for financial
applications. Mexico City &middot; CFA Level I Candidate.</p>
<h3>Professional Experience</h3>{exp}
<h3>Credentials &amp; Education</h3><ul class="certs">{certs}</ul>
<h3>Technical Skills</h3><div class="tags">{skills}</div></section>
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
<title>LTCMA 2026 — Full Report</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>LTCMA&nbsp;2026</b></span>{NAV}
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
<title>LTCMA 2026 — Glossary</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>LTCMA&nbsp;2026</b></span>{NAV}
</div></header>
<section class="hero"><div class="container"><h1>Glossary</h1>
<p class="lede">Plain-language explanations of every concept used across this
site — no math, no jargon. If a term on any page is unclear, it is defined here.</p>
</div></section>
<main class="container">{gloss_html}</main>
<footer class="shell-foot"><div class="container"><p>Research, not investment
advice.</p></div></footer></body></html>"""
open(f"{DOCS}/glossary.html", "w", encoding="utf-8").write(GLOSSARY_PAGE)

# ---------- Carbon-style CSS ----------
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'IBM Plex Sans',Segoe UI,sans-serif;color:#161616;
background:#f4f4f4;line-height:1.5;-webkit-font-smoothing:antialiased}
.container{max-width:1312px;margin:0 auto;padding:0 32px}
/* Carbon UI shell header */
.shell{background:#161616;position:sticky;top:0;z-index:50}
.shell-in{max-width:1312px;margin:0 auto;padding:0 32px;height:48px;
display:flex;align-items:center;gap:32px}
.brand{color:#fff;font-size:14px;font-weight:300;letter-spacing:.1px}
.brand b{font-weight:600}
nav{display:flex;gap:0;margin-left:auto}
nav a{color:#c6c6c6;text-decoration:none;font-size:14px;padding:0 16px;
height:48px;display:flex;align-items:center;border-bottom:3px solid transparent}
nav a:hover{color:#fff;background:#262626}
/* hero */
.hero{background:#161616;color:#fff;padding:56px 0 64px}
.hero h1{font-size:42px;font-weight:300;letter-spacing:-.4px;max-width:900px}
.lede{font-size:18px;font-weight:300;color:#c6c6c6;margin-top:16px;max-width:760px}
.asof{font-family:'IBM Plex Mono',monospace;font-size:12px;color:#8d8d8d;margin-top:20px}
/* blocks */
main{padding:48px 0 64px}
.block{margin-bottom:48px}
.block>h2{font-size:13px;font-weight:600;letter-spacing:.32px;text-transform:uppercase;
color:#525252;border-bottom:1px solid #8d8d8d;padding-bottom:8px;margin-bottom:20px}
.note{color:#525252;font-size:13px;margin:-8px 0 18px}
/* metric tiles */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;
background:#e0e0e0;border:1px solid #e0e0e0}
.metric{background:#fff;padding:20px}
.mv{font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:500;color:#0f62fe}
.mk{font-size:12px;color:#525252;margin-top:6px}
.m-stress .mv{color:#da1e28}.m-calm .mv{color:#198038}
/* chart grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.tile{background:#fff;border:1px solid #e0e0e0;padding:8px}
.chart.wide{grid-column:1 / -1}
.ch{width:100%}
/* button */
.btn{display:inline-block;background:#0f62fe;color:#fff;text-decoration:none;
padding:13px 60px 13px 16px;font-size:14px;margin-top:6px}
.btn:hover{background:#0353e9}
/* about / CV */
.lede2{font-size:16px;font-weight:300;color:#393939;max-width:780px;margin-bottom:8px}
.block h3{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.32px;
color:#161616;margin:28px 0 12px}
.role{border-left:3px solid #0f62fe;padding:2px 0 2px 18px;margin-bottom:20px}
.role-h{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
.role-co{font-weight:600;font-size:15px}
.role-d{font-family:'IBM Plex Mono',monospace;font-size:12px;color:#525252}
.role-t{font-size:14px;color:#0f62fe;margin:2px 0 6px}
.role p{font-size:14px;color:#393939;max-width:880px}
.certs{list-style:none;display:flex;flex-direction:column;gap:6px}
.certs li{font-size:14px;padding-left:18px;position:relative}
.certs li:before{content:"";position:absolute;left:0;top:8px;width:8px;height:8px;
background:#0f62fe}
.tags{display:flex;flex-wrap:wrap;gap:8px}
.tag{background:#fff;border:1px solid #8d8d8d;font-size:12px;padding:5px 12px;
font-family:'IBM Plex Mono',monospace}
/* footer */
.shell-foot{background:#161616;color:#8d8d8d;padding:28px 0;font-size:12px}
/* report page */
.report{padding:40px 56px;max-width:none}
.report h1{font-size:30px;font-weight:300;margin:8px 0}
.report h2{font-size:20px;font-weight:600;color:#161616;border-bottom:1px solid #8d8d8d;
padding-bottom:6px;margin:32px 0 14px}
.report h3{font-size:15px;font-weight:600;margin:20px 0 8px;text-transform:none;
letter-spacing:0;color:#161616}
.report p,.report li{font-size:14px;color:#262626;margin:8px 0}
.report table{border-collapse:collapse;width:100%;font-size:12.5px;margin:14px 0}
.report th{background:#161616;color:#fff;padding:8px 10px;text-align:left;font-weight:600}
.report td{border:1px solid #e0e0e0;padding:6px 10px}
.report tr:nth-child(even) td{background:#f4f4f4}
.report img{max-width:100%;margin:14px 0;border:1px solid #e0e0e0}
.report blockquote{border-left:3px solid #0f62fe;background:#fff;margin:12px 0;
padding:10px 16px;color:#393939}
.report code{font-family:'IBM Plex Mono',monospace;background:#e0e0e0;
font-size:90%;padding:1px 5px}
.report pre{background:#161616;color:#f4f4f4;padding:14px;overflow:auto;font-size:12px}
.report pre code{background:none;color:inherit}
/* portfolio table */
.ptable{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}
.ptable th{background:#161616;color:#fff;text-align:right;padding:8px 12px;
font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.3px}
.ptable th:first-child{text-align:left}
.ptable td{border-bottom:1px solid #e0e0e0;padding:8px 12px;text-align:right;
font-family:'IBM Plex Mono',monospace}
.ptable td:first-child{text-align:left;font-family:'IBM Plex Sans',sans-serif;font-weight:600}
.ptable tr:hover td{background:#f4f4f4}
.pos{color:#198038}.neg{color:#da1e28}
.scaled-note{background:#fff;border-left:3px solid #b28600;padding:10px 16px;
font-size:13px;color:#525252;margin-bottom:18px}
/* stock cards */
.scards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
gap:1px;background:#e0e0e0;border:1px solid #e0e0e0}
.scard{background:#fff;padding:22px 20px;text-decoration:none;color:#161616}
.scard:hover{background:#0f62fe;color:#fff}
.sc-t{font-family:'IBM Plex Mono',monospace;font-size:21px;font-weight:600}
.sc-n{font-size:12px;color:#525252;margin-top:4px}
.scard:hover .sc-n{color:#d0dcff}
/* currency badge, chart captions, glossary */
.ccy{display:inline-block;background:#edf5ff;color:#0043ce;border:1px solid #a6c8ff;
font-size:11px;padding:3px 10px;margin:-10px 0 14px;letter-spacing:.2px}
.caption{font-size:13px;color:#525252;padding:2px 12px 10px;margin:0;line-height:1.45}
.note a,.lede a{color:#0f62fe}
.ccy-toggle{display:inline-flex;border:1px solid #0f62fe;margin-bottom:12px}
.ccy-toggle button{background:#fff;color:#0f62fe;border:0;
border-right:1px solid #0f62fe;padding:7px 22px;font-family:inherit;
font-size:13px;font-weight:600;cursor:pointer}
.ccy-toggle button:last-child{border-right:0}
.ccy-toggle button.active{background:#0f62fe;color:#fff}
.gloss{margin:0}
.gloss dt{font-weight:600;font-size:14px;color:#0f62fe;margin-top:16px}
.gloss dd{font-size:14px;color:#393939;margin:3px 0 0;max-width:900px}
@media(max-width:820px){.grid{grid-template-columns:1fr}.hero h1{font-size:30px}
.report{padding:24px}
.metrics{grid-template-columns:repeat(2,1fr)!important}}
"""
open(f"{DOCS}/style.css", "w", encoding="utf-8").write(CSS)
print(f"Carbon site built -> {DOCS}  | regime={regime} | as-of {ASOF}")
print(f"  index.html, report.html, style.css, figures/  ({len(CHARTS)} locked charts)")
