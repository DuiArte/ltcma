"""Build the GitHub Pages site: interactive Plotly charts, live market
snapshot, and the rendered full report. Output -> docs/ (served by Pages).
Re-runnable: a scheduled GitHub Action refreshes data then re-runs this.
"""
import os, shutil
import numpy as np
import pandas as pd
import markdown
import plotly.graph_objects as go

D = os.path.expanduser("~/LTCMA/data")
REP = os.path.expanduser("~/LTCMA/report")
DOCS = os.path.expanduser("~/LTCMA/docs")
os.makedirs(f"{DOCS}/figures", exist_ok=True)
NAVY, GOLD, RED, GREY = "#1a3a5c", "#c8961e", "#a23b3b", "#8a9099"
ASOF = pd.Timestamp.today().strftime("%d %b %Y")

summ = pd.read_csv(f"{D}/ltcma_summary.csv", index_col=0)
ret = pd.read_csv(f"{D}/ltcma_returns.csv", index_col=0)
corr = pd.read_csv(f"{D}/ltcma_corr_v2.csv", index_col=0)
sig = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)
mcp = pd.read_csv(f"{D}/mc_regime_portfolios.csv", index_col=0)
bt = pd.read_csv(f"{D}/backtest_results.csv")
btb = pd.read_csv(f"{D}/backtest_bond.csv")

LAYOUT = dict(template="plotly_white", font=dict(family="Inter,Segoe UI,sans-serif",
              size=12, color="#1f1f1f"), title_font=dict(color=NAVY, size=15),
              margin=dict(l=55, r=25, t=50, b=45), paper_bgcolor="white")
def div(fig, name):
    fig.update_layout(**LAYOUT)
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False}, div_id=name)

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
fx_x, fx_y = [], []
for a, b in zip(ts[:-1], ts[1:]):
    f = ((1 + y[b]) ** b / (1 + y[a]) ** a) ** (1 / (b - a)) - 1
    fx_x.append((a + b) / 2); fx_y.append(f * 100)
f1 = go.Figure()
f1.add_scatter(x=ts, y=[y[t] * 100 for t in ts], name="Spot Treasury curve",
               mode="lines+markers", line=dict(color=NAVY, width=3))
f1.add_scatter(x=fx_x, y=fx_y, name="Implied forward short rate",
               mode="lines+markers", line=dict(color=GOLD, width=2, dash="dash"))
f1.add_hline(y=last["FedFunds"], line=dict(color=RED, dash="dot"),
             annotation_text=f"fed funds {last['FedFunds']:.2f}%")
f1.update_layout(title="Priced-in rate path — the market expects no cuts",
                 xaxis_title="maturity (years)", yaxis_title="rate (%)")

# ---------- 2. risk/return map ----------
cmap = {"Equity": NAVY, "Fixed Income": GOLD, "Real Asset": RED}
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
vc = [RED if v > 25 else (GOLD if v > 18 else NAVY) for v in eq["val_now"]]
f3 = go.Figure(go.Bar(x=[i.replace("_", " ") for i in eq.index], y=eq["val_now"],
                      marker_color=vc))
f3.update_layout(title="Valuation dispersion — CAPE / P/E by equity market",
                 yaxis_title="CAPE / trailing P/E")

# ---------- 4. expected return by lambda ----------
eqr = ret[ret["class"] == "Equity"].sort_values("ER_lambda0.5")
f4 = go.Figure()
for lam, c in [("ER_lambda0.0", GREY), ("ER_lambda0.5", NAVY), ("ER_lambda1.0", GOLD)]:
    f4.add_bar(y=[i.replace("_", " ") for i in eqr.index], x=eqr[lam] * 100,
               name=f"λ={lam[-3:]}", orientation="h", marker_color=c)
f4.update_layout(title="Equity expected return across the valuation-reversion dial λ",
                 barmode="group", xaxis_title="expected return (%)")

# ---------- 5. correlation heatmap ----------
f5 = go.Figure(go.Heatmap(z=corr.values, x=[c.replace("_", " ") for c in corr.columns],
                          y=[c.replace("_", " ") for c in corr.index],
                          colorscale="RdBu_r", zmid=0, zmin=-1, zmax=1))
f5.update_layout(title="Asset correlation matrix (Ledoit-Wolf shrunk)",
                 height=620, margin=dict(l=120, b=120))

# ---------- 6. regime timeline ----------
f6 = go.Figure()
f6.add_scatter(x=win, y=gpr.loc[win], name="GPR (geopolitical risk)",
               line=dict(color=RED, width=1))
f6.add_scatter(x=win, y=epu.loc[win], name="EPU (policy uncertainty)",
               line=dict(color=NAVY, width=1))
thr = score.quantile(2 / 3)
for d in win[score >= thr]:
    f6.add_vrect(x0=d - pd.offsets.MonthBegin(1), x1=d, fillcolor=GOLD,
                 opacity=0.13, line_width=0)
f6.update_layout(title="News-uncertainty regimes (shaded = stress months)",
                 yaxis_title="index level")

# ---------- 7. Monte Carlo portfolio outcomes ----------
f7 = go.Figure()
for p in mcp.index:
    r = mcp.loc[p]
    f7.add_scatter(x=[r["p5"] * 100, r["p95"] * 100], y=[p, p], mode="lines",
                   line=dict(color=GREY, width=6), showlegend=False)
    f7.add_scatter(x=[r["p50"] * 100], y=[p], mode="markers", showlegend=False,
                   marker=dict(color=NAVY, size=14, line=dict(color="white", width=2)))
f7.update_layout(title="Simulated 12-year annualized return — 5th–95th percentile, median",
                 xaxis_title="annualized return (%)")

# ---------- 8. backtest ----------
f8 = go.Figure()
f8.add_scatter(x=bt["pred_l0.5"] * 100, y=bt["realized"] * 100, mode="markers",
               name="equity vintages", marker=dict(color=NAVY, size=7, opacity=.7))
f8.add_scatter(x=btb["start_yield"] * 100, y=btb["realized"] * 100, mode="markers",
               name="bond vintages", marker=dict(color=GOLD, size=7, opacity=.7))
f8.add_scatter(x=[-3, 18], y=[-3, 18], mode="lines", name="perfect forecast",
               line=dict(color=GREY, dash="dash"))
f8.update_layout(title="Backtest — forecast vs realized 10-year return",
                 xaxis_title="forecast (%)", yaxis_title="realized (%)")

CHARTS = [("priced-in", f1, "What the market expects"),
          ("risk-return", f2, "Expected returns"),
          ("valuation", f3, "Valuation dispersion"),
          ("lambda", f4, "The valuation-reversion dial"),
          ("correlation", f5, "Correlation structure"),
          ("regimes", f6, "News & regime risk"),
          ("montecarlo", f7, "Simulated outcomes"),
          ("backtest", f8, "Methodology backtest")]

# ---------- assemble index.html ----------
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
snap_html = "".join(
    f'<div class="card{" regime-" + v.lower() if k == "Market Regime" else ""}">'
    f'<div class="cv">{v}</div><div class="ck">{k}</div></div>' for k, v in SNAP)
charts_html = "".join(
    f'<section><h2>{title}</h2>{div(fig, cid + "-chart")}</section>'
    for cid, fig, title in CHARTS)

INDEX = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LTCMA 2026 — Long-Term Capital Market Assumptions</title>
<link rel="stylesheet" href="style.css">
<script src="{PLOTLY}"></script></head><body>
<header><div class="wrap">
<h1>Long-Term Capital Market Assumptions</h1>
<p class="sub">A proprietary 12-year forward outlook for global asset classes &middot;
as of {ASOF}</p></div></header>
<main class="wrap">
<section><h2>Live Market Snapshot</h2>
<p class="note">Auto-refreshed weekly from public data (FRED, Yahoo Finance,
GPR/EPU indices).</p>
<div class="cards">{snap_html}</div></section>
{charts_html}
<section><h2>Full Report</h2>
<p>The complete written analysis &mdash; methodology, macro backdrop, return
tables, strategic-edge scan and limitations.</p>
<p><a class="btn" href="report.html">Read the full LTCMA report &rarr;</a></p></section>
</main>
<footer><div class="wrap">
<p>Built with free public data and open-source tools. Expected returns are
forward-looking estimates, not guarantees; actual outcomes will differ. This is
research, not investment advice.</p></div></footer>
</body></html>"""
open(f"{DOCS}/index.html", "w", encoding="utf-8").write(INDEX)

# ---------- report.html ----------
for f in os.listdir(f"{REP}/figures"):
    shutil.copy(f"{REP}/figures/{f}", f"{DOCS}/figures/{f}")
md_txt = open(f"{REP}/LTCMA_2026.md", encoding="utf-8").read()
body = markdown.markdown(md_txt, extensions=["tables", "fenced_code", "sane_lists"])
REPORT = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LTCMA 2026 — Full Report</title>
<link rel="stylesheet" href="style.css"></head><body>
<header><div class="wrap"><h1>LTCMA 2026 — Full Report</h1>
<p class="sub"><a href="index.html">&larr; back to dashboard</a></p></div></header>
<main class="wrap report">{body}</main>
<footer><div class="wrap"><p>Research, not investment advice.</p></div></footer>
</body></html>"""
open(f"{DOCS}/report.html", "w", encoding="utf-8").write(REPORT)

# ---------- style.css ----------
CSS = """
*{box-sizing:border-box}body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;
color:#1f1f1f;background:#f4f6f8;line-height:1.55}
.wrap{max-width:1080px;margin:0 auto;padding:0 22px}
header{background:#1a3a5c;color:#fff;padding:34px 0}
header h1{margin:0;font-size:27px}.sub{color:#cdd8e3;margin:6px 0 0}
header a{color:#e8c87a}
main{padding:30px 0 50px}
section{background:#fff;border-radius:8px;padding:20px 24px;margin:18px 0;
box-shadow:0 1px 4px rgba(0,0,0,.07)}
h2{color:#1a3a5c;border-bottom:2px solid #1a3a5c;padding-bottom:6px;
margin:0 0 14px;font-size:19px}
.note{color:#667;font-size:13px;margin:-4px 0 14px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.card{background:#f4f6f8;border-radius:7px;padding:14px;text-align:center}
.cv{font-size:22px;font-weight:700;color:#1a3a5c}
.ck{font-size:11px;color:#667;text-transform:uppercase;letter-spacing:.4px;margin-top:4px}
.regime-stress .cv{color:#a23b3b}.regime-calm .cv{color:#2e7d4f}
.btn{display:inline-block;background:#1a3a5c;color:#fff;text-decoration:none;
padding:10px 18px;border-radius:6px;font-weight:600}
footer{background:#23272b;color:#aab;padding:22px 0;font-size:12px}
.report{background:#fff;border-radius:8px;padding:30px 40px}
.report table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0}
.report th{background:#1a3a5c;color:#fff;padding:6px 8px;text-align:left}
.report td{border:1px solid #d0d5da;padding:5px 8px}
.report tr:nth-child(even) td{background:#f4f6f8}
.report img{max-width:100%;margin:10px 0}
.report h1{color:#1a3a5c}.report h2,.report h3{color:#1a3a5c}
.report blockquote{border-left:3px solid #1a3a5c;background:#eef2f6;
margin:10px 0;padding:8px 14px;color:#445}
.report code{background:#eef0f2;padding:1px 4px;font-size:90%}
.report pre{background:#f4f5f6;padding:10px;overflow:auto}
"""
open(f"{DOCS}/style.css", "w", encoding="utf-8").write(CSS)
print(f"Site built -> {DOCS}")
print(f"  index.html, report.html, style.css, figures/  | regime={regime}  as-of {ASOF}")
