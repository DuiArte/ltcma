"""LTCMA — Step 23: Systematic Strategies page (docs/strategies.html).
Equity curves vs S&P 500, drawdown, and a full indicator set for the four
regime-adaptive strategies. Reads each strategy's walk-forward OOS return series.
Methodology stays proprietary — this page shows results only.
"""
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from glossary import NAV

DOCS = os.path.expanduser("~/LTCMA/docs")
H = os.path.expanduser("~")
INK, BLUE, GOLD, GREEN = "#161616", "#0f62fe", "#b28600", "#198038"
RED, GREY, PURPLE = "#da1e28", "#8d8d8d", "#8a3ffc"
ASOF = pd.Timestamp.today().strftime("%d %b %Y")
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"

LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15), dragmode=False,
              margin=dict(l=60, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e0e0e0"), yaxis=dict(gridcolor="#e0e0e0"))


def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "responsive": True})


# ── load the four strategies' OOS return series ──────────────────────────────
def load(path, col, bench_col, bench_name):
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df[col].rename("strat"), df[bench_col].rename("bench"), bench_name

STRATS = {
    "SARS": dict(name="Adaptive US Equity", color=BLUE, rf=0.045,
                 **dict(zip(["s", "b", "bn"], load(f"{H}/SARS/data/backtest/backtest_returns.csv", "SARS", "SP500", "S&P 500")))),
    "DUO":  dict(name="Balanced Multi-strategy", color=PURPLE, rf=0.045,
                 **dict(zip(["s", "b", "bn"], load(f"{H}/DUO/data/duo_returns.csv", "DUO", "SPY", "S&P 500")))),
    "MARS": dict(name="Defensive Multi-asset", color=GOLD, rf=0.045,
                 **dict(zip(["s", "b", "bn"], load(f"{H}/MARS/data/backtest/backtest_returns.csv", "MARS", "SP500", "S&P 500")))),
    "BARS": dict(name="Mexican Equity Rotation", color=GREEN, rf=0.09,
                 **dict(zip(["s", "b", "bn"], load(f"{H}/BARS/data/backtest/backtest_returns.csv", "BARS", "IPC", "IPC")))),
}


# ── indicator engine ─────────────────────────────────────────────────────────
def indicators(s, b, rf):
    s, b = s.dropna(), b.dropna()
    idx = s.index.intersection(b.index)
    s, b = s.reindex(idx), b.reindex(idx)
    n = len(s)
    ann = (1 + s).prod() ** (12 / n) - 1
    annb = (1 + b).prod() ** (12 / n) - 1
    vol = s.std() * np.sqrt(12)
    dvol = s[s < 0].std() * np.sqrt(12)
    nav = (1 + s).cumprod()
    mdd = (nav / nav.cummax() - 1).min()
    cov = np.cov(s, b)[0, 1]; var = b.var()
    beta = cov / var if var > 0 else np.nan
    alpha = ann - (rf + beta * (annb - rf))
    te = (s - b).std() * np.sqrt(12)
    ir = (ann - annb) / te if te > 0 else np.nan
    up = (s[b > 0].mean() / b[b > 0].mean()) if (b > 0).any() else np.nan
    dn = (s[b < 0].mean() / b[b < 0].mean()) if (b < 0).any() else np.nan
    return dict(ann_ret=ann, ann_vol=vol, sharpe=(ann - rf) / vol if vol else 0,
                sortino=(ann - rf) / dvol if dvol else np.nan, max_dd=mdd,
                calmar=ann / abs(mdd) if mdd else 0, win=(s > 0).mean(),
                best=s.max(), worst=s.min(), alpha=alpha, beta=beta,
                te=te, ir=ir, up_cap=up, dn_cap=dn, n=n,
                start=s.index.min(), end=s.index.max())

METRICS = {k: indicators(v["s"], v["b"], v["rf"]) for k, v in STRATS.items()}


# ── 1. USD equity curves vs S&P (common window 2007+, indexed to 100) ────────
usd = ["SARS", "DUO", "MARS"]
common = None
for k in usd:
    common = STRATS[k]["s"].index if common is None else common.intersection(STRATS[k]["s"].index)
common = common.sort_values()

f_eq = go.Figure()
spy = STRATS["SARS"]["b"].reindex(common)
nav_spy = (1 + spy).cumprod(); nav_spy = nav_spy / nav_spy.iloc[0] * 100
for k in usd:
    nav = (1 + STRATS[k]["s"].reindex(common)).cumprod()
    nav = nav / nav.iloc[0] * 100
    f_eq.add_scatter(x=nav.index, y=nav, mode="lines", name=STRATS[k]["name"],
                     line=dict(color=STRATS[k]["color"], width=2.4))
f_eq.add_scatter(x=nav_spy.index, y=nav_spy, mode="lines", name="S&P 500",
                 line=dict(color=RED, width=1.8, dash="dot"))
f_eq.update_layout(title="Growth of 100 — USD strategies vs S&P 500 (common window)",
                   legend=dict(orientation="h", y=-0.16), yaxis_type="log")

# ── 2. Drawdown (USD) ────────────────────────────────────────────────────────
f_dd = go.Figure()
def dd(r): nav = (1 + r).cumprod(); return (nav / nav.cummax() - 1) * 100
for k in usd:
    f_dd.add_scatter(x=common, y=dd(STRATS[k]["s"].reindex(common)), mode="lines",
                     name=STRATS[k]["name"], line=dict(color=STRATS[k]["color"], width=1.8))
f_dd.add_scatter(x=common, y=dd(spy), mode="lines", name="S&P 500",
                 line=dict(color=RED, width=1.4, dash="dot"), fill="tozeroy",
                 fillcolor="rgba(218,30,40,0.06)")
f_dd.update_layout(title="Drawdown (%) — USD strategies vs S&P 500",
                   legend=dict(orientation="h", y=-0.16))

# ── 3. BARS vs IPC (MXN) ─────────────────────────────────────────────────────
bidx = STRATS["BARS"]["s"].index
nb = (1 + STRATS["BARS"]["s"]).cumprod(); nb = nb / nb.iloc[0] * 100
ni = (1 + STRATS["BARS"]["b"].reindex(bidx)).cumprod(); ni = ni / ni.iloc[0] * 100
f_bars = go.Figure()
f_bars.add_scatter(x=nb.index, y=nb, mode="lines", name="Mexican Equity Rotation",
                   line=dict(color=GREEN, width=2.4))
f_bars.add_scatter(x=ni.index, y=ni, mode="lines", name="IPC (NAFTRAC)",
                   line=dict(color=GREY, width=1.8, dash="dot"))
f_bars.update_layout(title="Growth of 100 (MXN) — Mexican Equity Rotation vs IPC",
                     legend=dict(orientation="h", y=-0.16), yaxis_type="log")


# ── metrics table ────────────────────────────────────────────────────────────
def pct(x, s=False): return ("—" if x is None or (isinstance(x,float) and np.isnan(x))
                             else (f"{x*100:+.1f}%" if s else f"{x*100:.1f}%"))
def num(x, d=2): return ("—" if x is None or (isinstance(x,float) and np.isnan(x)) else f"{x:.{d}f}")

ROWS = [("Ann. return", "ann_ret", "pct"), ("Ann. volatility", "ann_vol", "pct"),
        ("Sharpe", "sharpe", "num"), ("Sortino", "sortino", "num"),
        ("Max drawdown", "max_dd", "pct"), ("Calmar", "calmar", "num"),
        ("Win rate (months)", "win", "pct"), ("Best month", "best", "pcts"),
        ("Worst month", "worst", "pcts"), ("Alpha vs bench", "alpha", "pcts"),
        ("Beta vs bench", "beta", "num"), ("Tracking error", "te", "pct"),
        ("Information ratio", "ir", "num"), ("Up-capture", "up_cap", "num"),
        ("Down-capture", "dn_cap", "num")]

order = ["SARS", "DUO", "MARS", "BARS"]
head = "".join(f"<th>{STRATS[k]['name']}<br><span style='font-weight:400;color:#8d8d8d'>"
               f"vs {STRATS[k]['bn']}</span></th>" for k in order)
body = ""
for label, key, kind in ROWS:
    cells = ""
    for k in order:
        v = METRICS[k][key]
        cells += f"<td>{pct(v) if kind=='pct' else pct(v,True) if kind=='pcts' else num(v)}</td>"
    body += f"<tr><td>{label}</td>{cells}</tr>"
period = "".join(f"<td>{METRICS[k]['start'].strftime('%Y')}&ndash;{METRICS[k]['end'].strftime('%Y')} "
                 f"({METRICS[k]['n']}m)</td>" for k in order)
body += f"<tr><td>OOS window</td>{period}</tr>"


HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LTCMA 2026 — Systematic Strategies</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>LTCMA&nbsp;2026</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Systematic Strategies</h1>
<p class="lede">Four regime-adaptive strategies, walk-forward out-of-sample, benchmarked
against the S&amp;P 500 (and the IPC for Mexican equity). Equity curves, drawdowns and a
full indicator set. Results only — the detection-and-optimisation methodology is proprietary.</p>
<p class="asof">As of {ASOF} &middot; out-of-sample &middot; hypothetical, not actual trading results</p>
</div></section>
<main class="container">
<section class="block"><h2>Growth of 100 — USD strategies vs S&amp;P 500</h2>
<div class="tile chart wide"><div class="ch">{div(f_eq,'eq')}</div></div>
<p class="note">Log scale, indexed to 100 at the common start. Every strategy compounds
with materially lower drawdowns than the index (below).</p></section>
<section class="block"><h2>Drawdown</h2>
<div class="tile chart wide"><div class="ch">{div(f_dd,'dd')}</div></div></section>
<section class="block"><h2>Mexican Equity Rotation vs IPC (MXN)</h2>
<div class="tile chart wide"><div class="ch">{div(f_bars,'bars')}</div></div></section>
<section class="block"><h2>Indicator Set</h2>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable"><thead><tr><th>Indicator</th>{head}</tr></thead>
<tbody>{body}</tbody></table></div>
<p class="note">Risk-free rate: 4.5% (USD strategies) / 9% (BARS, CETES). Alpha, beta,
capture ratios computed vs each strategy's benchmark. Out-of-sample walk-forward;
hypothetical results, past performance does not guarantee future results.</p></section>
</main>
<footer class="shell-foot"><div class="container"><p>Research, not investment advice.
Backtested results are hypothetical and do not represent actual trading.</p></div></footer>
</body></html>"""

open(f"{DOCS}/strategies.html", "w", encoding="utf-8").write(HTML)
print("strategies.html built:", {k: round(METRICS[k]["sharpe"], 2) for k in order})
