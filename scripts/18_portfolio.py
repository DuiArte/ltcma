"""Build the GBM stock-portfolio tracker page -> docs/portfolio.html.
Source: 'Copy of Carteras DBE 2.xlsx' sheet 'DBE Acciones' (GBM stock holdings
only -- FX positions and non-GBM bank cash are excluded by design).
A x1.8 scaling constant is applied to share counts so every formula stays
intact (value = shares*price, P/M = value - cost, weights unchanged) while the
displayed magnitudes are not the real amounts. Source Excel is never modified.
Refresh: update the Excel, re-run this script.
"""
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from glossary import NAV, ccy_badge

XLSX = "/mnt/c/Users/carlo/Downloads/Copy of Carteras DBE 2.xlsx"
DOCS = os.path.expanduser("~/LTCMA/docs")
SCALE = 1.8                       # holdings scaling constant (obfuscation)
FILTER_ANOMALIES = True           # drop rows with impossible returns (bad data)
INK, BLUE, GOLD, GREEN = "#161616", "#0f62fe", "#b28600", "#198038"
RED, GREY = "#da1e28", "#8d8d8d"

LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15), dragmode=False,
              margin=dict(l=60, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e0e0e0"), yaxis=dict(gridcolor="#e0e0e0"))

def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False})

# ---------- load & clean ----------
df = pd.read_excel(XLSX, "DBE Acciones", header=0)
for c in ["Títulos", "Costo promedio", "Precio mercado"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["Fecha"] = pd.to_datetime(df["Fecha"])
df["ticker"] = df["Emisora/Fondo"].astype(str).str.replace(" *", "", regex=False).str.strip()
df = df.dropna(subset=["Títulos", "Costo promedio", "Precio mercado"])

# x1.8 scaling on share counts -> every downstream formula stays consistent
df["shares"] = df["Títulos"] * SCALE
df["value"] = df["shares"] * df["Precio mercado"]
df["cost"] = df["shares"] * df["Costo promedio"]
df["pm"] = df["value"] - df["cost"]
df["ret"] = df["Precio mercado"] / df["Costo promedio"] - 1

# filter obvious data errors (e.g. unadjusted stock-split rows) by default
bad_dates = set()
if FILTER_ANOMALIES:
    bad = df[(df["ret"] < -0.60) | (df["ret"] > 3.0)]
    for _, b in bad.iterrows():
        print(f"  filtered anomaly: {b['ticker']} {b['Fecha'].date()} "
              f"ret={b['ret']*100:.0f}% (likely unadjusted split)")
    bad_dates = set(bad["Fecha"])
    df = df.drop(bad.index)

# ---------- portfolio value time series ----------
ts = df.groupby("Fecha").agg(value=("value", "sum"), cost=("cost", "sum"))
ts = ts[~ts.index.isin(bad_dates)]      # drop dates left incomplete by the filter
ts["ret"] = ts["value"] / ts["cost"] - 1
dates = ts.index

# ---------- latest snapshot ----------
latest = df[df["Fecha"] == df["Fecha"].max()].copy()
tot_val = latest["value"].sum()
tot_cost = latest["cost"].sum()
latest["weight"] = latest["value"] / tot_val
latest = latest.sort_values("value", ascending=False)
port_ret = tot_val / tot_cost - 1
asof = df["Fecha"].max().strftime("%d %b %Y")

# ---------- charts ----------
# 1. portfolio value over time
f1 = go.Figure()
f1.add_scatter(x=dates, y=ts["value"], mode="lines+markers", name="Portfolio value",
               line=dict(color=BLUE, width=3), fill="tozeroy",
               fillcolor="rgba(15,98,254,0.08)")
f1.update_layout(title="Stock portfolio market value over time (scaled)",
                 yaxis_title="MXN (scaled)", xaxis_title="snapshot date")

# 2. per-holding return vs portfolio (the relative tracker)
lat = latest.sort_values("ret")
colors = [GREEN if r >= 0 else RED for r in lat["ret"]]
f2 = go.Figure(go.Bar(x=lat["ret"] * 100, y=lat["ticker"], orientation="h",
                      marker_color=colors,
                      text=[f"{r*100:+.1f}%" for r in lat["ret"]],
                      textposition="outside"))
f2.add_vline(x=port_ret * 100, line=dict(color=INK, dash="dash"),
             annotation_text=f"portfolio {port_ret*100:+.1f}%")
f2.update_layout(title="Holding return vs the portfolio (dashed = portfolio total)",
                 xaxis_title="return since cost (%)")

# 3. allocation
al = latest.sort_values("weight")
f3 = go.Figure(go.Bar(x=al["weight"] * 100, y=al["ticker"], orientation="h",
                      marker_color=BLUE,
                      text=[f"{w*100:.1f}%" for w in al["weight"]],
                      textposition="outside"))
f3.update_layout(title="Current allocation by holding", xaxis_title="% of stock portfolio")

# ---------- holdings table ----------
rows = ""
for _, r in latest.iterrows():
    rc = "pos" if r["ret"] >= 0 else "neg"
    pc = "pos" if r["pm"] >= 0 else "neg"
    rows += (f"<tr><td>{r['ticker']}</td><td>{r['shares']:,.1f}</td>"
             f"<td>{r['Costo promedio']:,.2f}</td><td>{r['Precio mercado']:,.2f}</td>"
             f"<td>{r['value']:,.0f}</td><td>{r['weight']*100:.1f}%</td>"
             f"<td class='{rc}'>{r['ret']*100:+.1f}%</td>"
             f"<td class='{pc}'>{r['pm']:,.0f}</td></tr>")

# ---------- metrics ----------
SNAP = [("Portfolio Value (scaled)", f"{tot_val:,.0f}"),
        ("Unrealized P / M (scaled)", f"{latest['pm'].sum():+,.0f}"),
        ("Holdings", f"{len(latest)}"),
        ("Portfolio Return", f"{port_ret*100:+.1f}%"),
        ("As of", asof)]
snap = "".join(
    f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
    for k, v in SNAP)

PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
# NAV imported from glossary module

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Portfolio Tracker</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>LTCMA&nbsp;2026</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Stock Portfolio Tracker</h1>
<p class="lede">GBM equity holdings &mdash; tracked against each constituent
position. Sourced from the portfolio workbook; refreshes when it updates.</p>
<p class="asof">As of {asof} &middot; GBM stock holdings only</p>
</div></section>
<main class="container">
<div class="scaled-note"><b>Display note:</b> figures are scaled by a fixed
constant for confidentiality &mdash; magnitudes are illustrative, not the real
amounts; prices, returns and weights are exact. FX positions and non-GBM cash
are excluded. Rows with impossible returns (e.g. unadjusted stock splits) are
filtered out automatically.</div>
<section class="block"><h2>Snapshot</h2>
{ccy_badge("MXN", "GBM brokerage account, valued in Mexican pesos")}
<div class="metrics" style="grid-template-columns:repeat(5,1fr)">{snap}</div></section>
<section class="block"><h2>Portfolio Value</h2>
<div class="tile chart"><div class="ch">{div(f1, "pf-value")}</div></div></section>
<section class="block"><h2>Holdings</h2>
<div class="tile" style="padding:0 16px 8px">
<table class="ptable"><thead><tr><th>Holding</th><th>Shares</th>
<th>Avg Cost</th><th>Price</th><th>Value (scaled)</th><th>Weight</th>
<th>Return</th><th>P/M (scaled)</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="block"><h2>Portfolio vs Its Holdings</h2>
<div class="grid"><div class="tile chart"><div class="ch">{div(f2, "pf-rel")}</div></div>
<div class="tile chart"><div class="ch">{div(f3, "pf-alloc")}</div></div></div></section>
</main>
<footer class="shell-foot"><div class="container"><p>Figures scaled for
confidentiality. Research and monitoring, not investment advice.</p></div></footer>
</body></html>"""
open(f"{DOCS}/portfolio.html", "w", encoding="utf-8").write(HTML)
print(f"Portfolio tracker built -> {DOCS}/portfolio.html")
print(f"  {len(latest)} holdings | value(scaled) {tot_val:,.0f} | "
      f"return {port_ret*100:+.1f}% | as-of {asof} | SCALE={SCALE}")
