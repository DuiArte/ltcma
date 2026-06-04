"""Stock Signals — per-stock macro factor exposures (β to 10Y rates, DXY,
USDCAD) and post-FOMC reaction patterns for a curated 40-name universe.

Consumes pre-computed analytics from the companion capstone workflow:
  /home/carlos/capstone/data/analytics/stock_sensitivities.parquet
  /home/carlos/capstone/data/analytics/stock_fomc_reaction.parquet

Output: docs/signals.html
"""
import os
import pandas as pd
import plotly.graph_objects as go
from glossary import NAV

DOCS = os.path.expanduser("~/LTCMA/docs")
ANA = "/home/carlos/capstone/data/analytics"
INK, BLUE, GOLD, GREEN = "#111111", "#0a2540", "#6b7280", "#0a5d3a"
RED, GREY = "#7c2d12", "#888888"

SECTOR_C = {
    "Technology": "#0a2540",
    "Consumer Cyclical": "#6b7280",
    "Communication Services": "#8a3ffc",
    "Healthcare": "#0a5d3a",
    "Financial Services": "#009d9a",
    "Consumer Defensive": "#fa4d56",
    "Energy": "#7c2d12",
    "Industrials": "#555555",
}

PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
LAYOUT = dict(template="plotly_white", dragmode=False,
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15),
              margin=dict(l=58, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e5e5e5"), yaxis=dict(gridcolor="#e5e5e5"))

def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False})

# ---------- load analytics ----------
sens = pd.read_parquet(f"{ANA}/stock_sensitivities.parquet")
fomc = pd.read_parquet(f"{ANA}/stock_fomc_reaction.parquet")

sens = sens.copy()
sens["abs_rates"] = sens["beta_rates"].abs()
sens = sens.sort_values("abs_rates", ascending=False)
sens["sector_short"] = sens["sector"].fillna("Other").str.replace(" Services", "")

def cell_beta(beta, t):
    cls = "pos" if beta > 0 else ("neg" if beta < 0 else "")
    bold = "font-weight:600" if abs(t) > 2 else ""
    return (f'<td class="{cls}" style="{bold}">{beta:+.3f}'
            f'<br><span style="color:#888888;font-size:11px">t={t:+.1f}</span></td>')

# ---------- sensitivities table ----------
sens_rows = ""
for _, r in sens.iterrows():
    color = SECTOR_C.get(r["sector"], GREY)
    sens_rows += (
        f'<tr><td>{r["ticker"]}</td>'
        f'<td><span style="background:{color};color:white;padding:2px 8px;'
        f'font-size:11px;font-family:IBM Plex Sans">{r["sector_short"]}</span></td>'
        f'<td>${r["marketcap_B"]:,.0f}B</td>'
        f'<td>{r["pe"]:,.1f}</td>'
        f'<td>{r["fwd_pe"]:,.1f}</td>'
        f'{cell_beta(r["beta_rates"], r["t_rates"])}'
        f'{cell_beta(r["beta_dxy"], r["t_dxy"])}'
        f'{cell_beta(r["beta_cad"], r["t_cad"])}'
        f'<td>{r["r2"]*100:.1f}%</td></tr>'
    )

# ---------- scatter: β_rates vs β_DXY ----------
f1 = go.Figure()
for sec, group in sens.groupby("sector"):
    color = SECTOR_C.get(sec, GREY)
    f1.add_scatter(x=group["beta_rates"], y=group["beta_dxy"], mode="markers+text",
                   text=group["ticker"], textposition="top center",
                   textfont=dict(size=9),
                   marker=dict(color=color, size=12, line=dict(color="white", width=1)),
                   name=sec)
f1.add_hline(y=0, line=dict(color=GREY, width=0.5))
f1.add_vline(x=0, line=dict(color=GREY, width=0.5))
f1.update_layout(title="Macro factor exposures — β to 10Y rates vs β to dollar (DXY)",
                 xaxis_title="β to 10Y yield change (per 1pp)",
                 yaxis_title="β to DXY % change",
                 legend=dict(orientation="h", y=-0.18))

# ---------- FOMC reaction summary table ----------
pivot = fomc.groupby(["ticker", "decision"])["fwd5"].mean().unstack("decision")
counts = fomc.groupby(["ticker", "decision"])["fomc"].count().unstack("decision")
overall = fomc.groupby("ticker")["fwd5"].mean().sort_values(ascending=False)
pivot = pivot.reindex(overall.index)
counts = counts.reindex(overall.index)

fomc_rows = ""
for tk in pivot.index:
    cells = []
    for dec in ["Cut", "Hold", "Hike"]:
        if dec in pivot.columns and not pd.isna(pivot.loc[tk, dec]):
            v = pivot.loc[tk, dec]
            n = int(counts.loc[tk, dec])
            cls = "pos" if v >= 0 else "neg"
            cells.append(f'<td class="{cls}">{v*100:+.2f}%'
                         f'<br><span style="color:#888888;font-size:11px">n={n}</span></td>')
        else:
            cells.append('<td style="color:#888888">—</td>')
    o = overall[tk]
    cls_o = "pos" if o >= 0 else "neg"
    cells.append(f'<td class="{cls_o}" style="font-weight:600">{o*100:+.2f}%</td>')
    fomc_rows += f"<tr><td>{tk}</td>{''.join(cells)}</tr>"

# ---------- assemble HTML ----------
asof = pd.Timestamp.today().strftime("%d %b %Y")
HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Signals — macro sensitivities & FOMC reactions</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Stock Signals</h1>
<p class="lede">Per-stock macro factor exposures and post-FOMC reaction
patterns for a curated 40-name universe &mdash; the overlay equity research
uses to separate genuine fundamentals from rate and dollar beta.</p>
<p class="asof">As of {asof} &middot; 40 tickers &middot; window: 2018&ndash;2026 daily</p>
</div></section>
<main class="container">

<section class="block"><h2>Why This Matters</h2>
<p class="note">A stock's price reflects more than its earnings &mdash; it
also moves with macro factors (rates, the dollar). Knowing each holding's
exposure helps separate <i>fundamental</i> moves from <i>macro</i> beta and
avoid mistaking a rate move for stock-specific news. The post-FOMC reaction
table is the <a href="regime.html">Lucca&nbsp;&amp;&nbsp;Moench drift</a> applied
stock by stock. Definitions in the <a href="glossary.html">Glossary</a>.</p>
</section>

<section class="block"><h2>Macro Factor Exposures (β scatter)</h2>
<div class="tile chart"><div class="ch">{div(f1, "sens-scatter")}</div></div>
<p class="note">Names with <b>negative β to rates</b> and <b>positive β to
DXY</b> trade like long-duration assets &mdash; they fall when yields rise and
benefit from dollar strength. Software and high-multiple growth typically
cluster in that quadrant. Energy and financials usually sit on the opposite
side.</p>
</section>

<section class="block"><h2>Sensitivities Table</h2>
<p class="note">Sorted by |β to rates|. Bold cells have t-statistic above 2
(statistically significant). β rates is per a 1-percentage-point change in
the US 10-year yield; β DXY is per a 1% dollar move.</p>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable"><thead><tr>
<th>Ticker</th><th>Sector</th><th>Mkt Cap</th><th>P/E</th><th>Fwd P/E</th>
<th>β rates</th><th>β DXY</th><th>β USDCAD</th><th>R²</th></tr></thead>
<tbody>{sens_rows}</tbody></table></div>
</section>

<section class="block"><h2>Post-FOMC Reaction by Decision (5-day forward return)</h2>
<p class="note">Average 5-day forward return after each FOMC meeting, by
decision. Sorted by overall average (most positive on top). This is the
Lucca&ndash;Moench post-FOMC drift split out per stock &mdash; rate-sensitive
names tend to drift positively after Holds and Cuts.</p>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable"><thead><tr>
<th>Ticker</th><th>Cut</th><th>Hold</th><th>Hike</th><th>Overall</th>
</tr></thead><tbody>{fomc_rows}</tbody></table></div>
</section>

<section class="block"><h2>Methodology &amp; References</h2>
<h3>Macro β regression</h3>
<p style="font-size:14px;color:#262626">For each ticker, daily log returns
over 2018&ndash;2026 are regressed on (i) the daily change in the US 10-year
Treasury yield (FRED DGS10); (ii) the daily % change in the dollar index
(yfinance DX-Y.NYB); (iii) the daily % change in USDCAD. Reported β is the
OLS univariate coefficient; the t-statistic indicates statistical
significance.</p>
<h3>Post-FOMC drift</h3>
<p style="font-size:14px;color:#262626">Forward 5-day returns are computed
for each FOMC meeting and averaged per ticker per decision (Cut / Hold /
Hike). The pattern follows Lucca, D.&nbsp;O., &amp; Moench, E. (2015). The
Pre-FOMC Announcement Drift. <i>Journal of Finance, 70</i>(1), 329&ndash;371.</p>
<h3>Companion insider-trading research (cited, not displayed here)</h3>
<p style="font-size:14px;color:#262626">Lakonishok, J., &amp; Lee, I. (2001).
Are insider trades informative? <i>Review of Financial Studies, 14</i>(1),
79&ndash;111.<br>Cohen, L., Malloy, C., &amp; Pomorski, L. (2012). Decoding
inside information. <i>Journal of Finance, 67</i>(3), 1009&ndash;1043.</p>
<h3>Data sources</h3>
<p style="font-size:14px;color:#262626">Prices &mdash; Yahoo Finance.
Macro &mdash; Federal Reserve Bank of St. Louis (FRED). FOMC calendar
&mdash; Federal Reserve. Pre-computed analytics produced by the companion
<code>build_stock_sensitivities.py</code> pipeline.</p>
</section>

</main>
<footer class="shell-foot"><div class="container"><p>Research and monitoring,
not investment advice.</p></div></footer></body></html>"""

open(f"{DOCS}/signals.html", "w", encoding="utf-8").write(HTML)
print(f"Stock signals page built -> {DOCS}/signals.html")
print(f"  {len(sens)} tickers in sensitivities table")
print(f"  {len(pivot)} tickers in FOMC reaction table")
top_neg = sens.sort_values("beta_rates").head(3)["ticker"].tolist()
top_pos = sens.sort_values("beta_rates", ascending=False).head(3)["ticker"].tolist()
print(f"  most rate-NEGATIVE: {top_neg}")
print(f"  most rate-POSITIVE: {top_pos}")
