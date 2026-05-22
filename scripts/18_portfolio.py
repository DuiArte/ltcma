"""Build the GBM stock-portfolio tracker page -> docs/portfolio.html.
Source: 'Copy of Carteras DBE 2.xlsx' sheet 'DBE Acciones' (GBM stock holdings
only -- FX positions and non-GBM bank cash are excluded by design).
A x1.8 scaling constant is applied to share counts so every formula stays
intact (value = shares*price, P/M = value - cost, weights unchanged) while the
displayed magnitudes are not the real amounts. Source Excel is never modified.
A MXN / USD currency toggle converts figures at the latest USDMXN rate.
Refresh: update the Excel, re-run this script.
"""
import os
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from glossary import NAV, ccy_badge

XLSX = "/mnt/c/Users/carlo/Downloads/Copy of Carteras DBE 2.xlsx"
DATA = os.path.expanduser("~/LTCMA/data")
DOCS = os.path.expanduser("~/LTCMA/docs")
SCALE = 1.8                       # holdings scaling constant (obfuscation)
FILTER_ANOMALIES = True           # drop rows with impossible returns (bad data)
INK, BLUE, GOLD, GREEN = "#161616", "#0f62fe", "#b28600", "#198038"
RED, GREY = "#da1e28", "#8d8d8d"

# latest USDMXN rate for the currency toggle
sig = pd.read_csv(f"{DATA}/signals_fred.csv", index_col=0)
RATE = float(pd.to_numeric(sig["USDMXN"], errors="coerce").dropna().iloc[-1])

LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15), dragmode=False,
              margin=dict(l=64, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e0e0e0"), yaxis=dict(gridcolor="#e0e0e0"))

def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False})

# --- number formatting (normalized across the page) ---
def fmt(x, dec=0):
    return f"{x:,.{dec}f}"

def fmts(x, dec=0):                       # signed
    return f"{x:+,.{dec}f}"

def cval(mxn, dec=0, signed=False):
    """A currency-aware figure carrying both MXN and USD, toggled by JS."""
    f = fmts if signed else fmt
    return (f'<span class="cval" data-mxn="{f(mxn, dec)}" '
            f'data-usd="{f(mxn / RATE, dec)}">{f(mxn, dec)}</span>')

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
ts = ts[~ts.index.isin(bad_dates)]
ts["ret"] = ts["value"] / ts["cost"] - 1
dates = ts.index

# ---------- latest snapshot (with LIVE pricing override) ----------
latest = df[df["Fecha"] == df["Fecha"].max()].copy()
asof_excel = df["Fecha"].max().strftime("%d %b %Y")

# Map portfolio tickers to yfinance symbols (US-listed = USD native;
# .MX suffix = BMV-listed, MXN native).
TICKER_MAP = {
    # Priced from the public BMV exchange (SIC), MXN-native — matches how a GBM
    # client actually holds these, eliminating the US-price x FX basis mismatch.
    "AMZN": "AMZN.MX", "BA": "BA.MX", "GLD": "GLD.MX", "GOOGL": "GOOGL.MX",
    "IBM": "IBM.MX", "JPM": "JPM.MX", "MA": "MA.MX", "MELI N": "MELI.MX",
    "META": "META.MX", "MSFT": "MSFT.MX", "QQQ": "QQQ.MX", "SOXX": "SOXX.MX",
    "VGT": "VGT.MX", "VUG": "VUG.MX", "GMEXICO B": "GMEXICOB.MX",
}

# refresh USDMXN to the live rate (falls back to FRED rate if yfinance fails)
try:
    fx_live = float(yf.Ticker("MXN=X").history(period="2d")["Close"].iloc[-1])
except Exception:
    fx_live = RATE
RATE = fx_live          # used by cval() for the MXN/USD toggle

priced_at = None
to_fetch = sorted({TICKER_MAP[t] for t in latest["ticker"] if t in TICKER_MAP})
if to_fetch:
    try:
        ld = yf.download(to_fetch, period="5d", interval="1d",
                         auto_adjust=True, progress=False)["Close"]
        if isinstance(ld, pd.Series):
            ld = ld.to_frame(name=to_fetch[0])
        live_px = {c: float(ld[c].dropna().iloc[-1]) for c in ld.columns
                   if ld[c].dropna().size}
        priced_at = ld.dropna(how="all").index[-1].strftime("%d %b %Y")
        for idx, row in latest.iterrows():
            yt = TICKER_MAP.get(row["ticker"])
            if not yt or yt not in live_px:
                continue
            ccy = "MXN" if yt.endswith(".MX") else "USD"
            new_mxn = live_px[yt] if ccy == "MXN" else live_px[yt] * fx_live
            latest.loc[idx, "Precio mercado"] = new_mxn
        latest["value"] = latest["shares"] * latest["Precio mercado"]
        latest["pm"] = latest["value"] - latest["cost"]
        latest["ret"] = latest["Precio mercado"] / latest["Costo promedio"] - 1
        print(f"  live priced {len(live_px)} holdings @ "
              f"{priced_at} USDMXN {fx_live:.2f}")
    except Exception as e:
        print(f"  live pricing failed: {e} -- using last-snapshot prices")

tot_val = latest["value"].sum()
tot_cost = latest["cost"].sum()
latest["weight"] = latest["value"] / tot_val
latest = latest.sort_values("value", ascending=False)
port_ret = tot_val / tot_cost - 1
asof = priced_at or asof_excel

# Append today's live snapshot to the value time series
if priced_at:
    today_idx = pd.Timestamp(priced_at)
    if today_idx > ts.index[-1]:
        ts.loc[today_idx] = [tot_val, tot_cost, tot_val / tot_cost - 1]
        ts = ts.sort_index()
        dates = ts.index

# ---------- charts ----------
# 1. portfolio value over time (MXN base; USD array embedded for the toggle)
f1 = go.Figure()
f1.add_scatter(x=dates, y=ts["value"], mode="lines+markers", name="Portfolio value",
               line=dict(color=BLUE, width=3), fill="tozeroy",
               fillcolor="rgba(15,98,254,0.08)")
f1.update_layout(title="Portfolio market value over time (scaled)",
                 yaxis_title="MXN value (scaled)", xaxis_title="snapshot date")

# 2. per-holding return vs portfolio (currency-independent)
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

# 3. allocation (currency-independent)
al = latest.sort_values("weight")
f3 = go.Figure(go.Bar(x=al["weight"] * 100, y=al["ticker"], orientation="h",
                      marker_color=BLUE,
                      text=[f"{w*100:.1f}%" for w in al["weight"]],
                      textposition="outside"))
f3.update_layout(title="Current allocation by holding",
                 xaxis_title="% of stock portfolio")

# ---------- holdings table ----------
rows = ""
for _, r in latest.iterrows():
    rc = "pos" if r["ret"] >= 0 else "neg"
    pc = "pos" if r["pm"] >= 0 else "neg"
    rows += (f"<tr><td>{r['ticker']}</td><td>{r['shares']:,.1f}</td>"
             f"<td>{cval(r['Costo promedio'], 2)}</td>"
             f"<td>{cval(r['Precio mercado'], 2)}</td>"
             f"<td>{cval(r['value'])}</td><td>{r['weight']*100:.1f}%</td>"
             f"<td class='{rc}'>{r['ret']*100:+.1f}%</td>"
             f"<td class='{pc}'>{cval(r['pm'], signed=True)}</td></tr>")

# ---------- metrics ----------
SNAP = [("Portfolio Value (scaled)", cval(tot_val)),
        ("Unrealized P / M (scaled)", cval(latest["pm"].sum(), signed=True)),
        ("Holdings", f"{len(latest)}"),
        ("Portfolio Return", f"{port_ret*100:+.1f}%"),
        ("Live Priced", asof),
        ("Cost-Basis Date", asof_excel)]
snap = "".join(
    f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
    for k, v in SNAP)

# ---------- currency-toggle JavaScript ----------
mxn_arr = ",".join(f"{v:.0f}" for v in ts["value"])
usd_arr = ",".join(f"{v/RATE:.0f}" for v in ts["value"])
JS = """
<script>
var PFV={mxn:[__MXN__],usd:[__USD__]};
function setCurrency(c){
  document.querySelectorAll('.cval').forEach(function(e){e.textContent=e.dataset[c];});
  document.querySelectorAll('.ccy-toggle button').forEach(function(b){
    b.classList.toggle('active',b.dataset.cur===c);});
  var lbl=document.getElementById('ccy-label');
  if(lbl) lbl.textContent=c.toUpperCase();
  var d=document.getElementById('pf-value');
  if(d&&window.Plotly){
    Plotly.restyle(d,{y:[PFV[c]]});
    Plotly.relayout(d,{'yaxis.title.text':c.toUpperCase()+' value (scaled)'});
  }
}
document.addEventListener('DOMContentLoaded',function(){setCurrency('mxn');});
</script>
""".replace("__MXN__", mxn_arr).replace("__USD__", usd_arr)

PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"

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
<p class="lede">A live view of the GBM equity book &mdash; every position
measured against its cost basis and against the portfolio as a whole.
Figures convert between Mexican pesos and US dollars at the current rate.</p>
<p class="asof">As of {asof} &middot; GBM equity holdings &middot;
USD/MXN {RATE:.2f}</p>
</div></section>
<main class="container">
<div class="scaled-note"><b>Display note:</b> figures are scaled by a fixed
constant for confidentiality &mdash; magnitudes are illustrative, not the real
amounts; prices, returns and weights are exact. FX positions and non-GBM cash
are excluded; rows with impossible returns (e.g. unadjusted stock splits) are
filtered automatically.</div>
<section class="block"><h2>Snapshot</h2>
<div class="ccy-toggle">
<button data-cur="mxn" class="active" onclick="setCurrency('mxn')">MXN</button>
<button data-cur="usd" onclick="setCurrency('usd')">USD</button></div>
<p class="note">Currency: <b id="ccy-label">MXN</b> &mdash; returns and weights
read the same in either currency. Definitions in the
<a href="glossary.html">Glossary</a>.</p>
<div class="metrics" style="grid-template-columns:repeat(6,1fr)">{snap}</div></section>
<section class="block"><h2>Portfolio Value</h2>
<div class="tile chart"><div class="ch">{div(f1, "pf-value")}</div></div></section>
<section class="block"><h2>Holdings</h2>
<div class="tile" style="padding:0 16px 8px">
<table class="ptable"><thead><tr><th>Holding</th><th>Shares</th>
<th>Avg Cost</th><th>Price</th><th>Value</th><th>Weight</th>
<th>Return</th><th>P/M</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="block"><h2>Portfolio vs Its Holdings</h2>
<div class="grid"><div class="tile chart"><div class="ch">{div(f2, "pf-rel")}</div></div>
<div class="tile chart"><div class="ch">{div(f3, "pf-alloc")}</div></div></div></section>
</main>
<footer class="shell-foot"><div class="container"><p>Figures scaled for
confidentiality. Research and monitoring, not investment advice.</p></div></footer>
{JS}</body></html>"""
open(f"{DOCS}/portfolio.html", "w", encoding="utf-8").write(HTML)
print(f"Portfolio tracker built -> {DOCS}/portfolio.html")
print(f"  {len(latest)} holdings | value(scaled) MXN {tot_val:,.0f} / "
      f"USD {tot_val/RATE:,.0f} | return {port_ret*100:+.1f}% | "
      f"as-of {asof} | USDMXN {RATE:.2f}")
