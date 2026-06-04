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
from glossary import NAV, bt_load, bt_common, bt_indicators, bt_g100, bt_dd, BT_JS

DOCS = os.path.expanduser("~/LTCMA/docs")
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


HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carlos Duarte — Systematic Strategies</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Systematic Strategies</h1>
<p class="lede">Four regime-adaptive strategies, walk-forward out-of-sample, benchmarked
against the S&amp;P 500 (and the IPC for Mexican equity). Equity curves, drawdowns and a
full indicator set. Results only — the detection-and-optimisation methodology is proprietary.</p>
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
</main>
<footer class="shell-foot"><div class="container"><p>Research, not investment advice.
Backtested results are hypothetical and do not represent actual trading.</p></div></footer>
{bt_script}
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
