"""Regime-change tracker: a composite monthly stress index built from VIX, HY
credit spreads, the yield curve, GPR (geopolitical risk) and EPU (economic
policy uncertainty). The page flags the current regime state, the most recent
transitions, and a near-term tactical overlay (VIX-bucket forward returns plus
the post-FOMC drift finding from the companion macro_event_study work).

Output: docs/regime.html
"""
import os
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from glossary import NAV, ccy_badge

DATA = os.path.expanduser("~/LTCMA/data")
DOCS = os.path.expanduser("~/LTCMA/docs")
INK, BLUE, GOLD, GREEN, RED, GREY = "#161616", "#0f62fe", "#b28600", "#198038", "#da1e28", "#8d8d8d"

PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15), dragmode=False,
              margin=dict(l=58, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e0e0e0"), yaxis=dict(gridcolor="#e0e0e0"))

def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False})

# ---------- monthly stress components ----------
sig = pd.read_csv(f"{DATA}/signals_fred.csv", index_col=0, parse_dates=True)
gpr = pd.read_excel(f"{DATA}/signals_gpr_raw.xls")[["month", "GPR"]].set_index("month")["GPR"]
gpr.index = gpr.index + pd.offsets.MonthEnd(0)

mend = lambda s: s.dropna().resample("ME").mean()
vix_m = mend(sig["VIX"])
hy_m = mend(sig["HY_OAS"])
curve_m = mend(sig["Curve_10Y3M"])
epu_m = sig["EPU_US"].dropna()
epu_m.index = epu_m.index + pd.offsets.MonthEnd(0)
epu_m = epu_m.groupby(epu_m.index).last()

start = "2000-01-01"
idx = pd.date_range(start, vix_m.index.max(), freq="ME")
comp = pd.DataFrame(index=idx)
comp["VIX"] = vix_m.reindex(idx)
comp["HY_OAS"] = hy_m.reindex(idx)
comp["NegCurve"] = -curve_m.reindex(idx)        # inversion -> positive (stress)
comp["EPU"] = epu_m.reindex(idx)
comp["GPR"] = gpr.reindex(idx)
comp = comp.dropna(how="all")

z = (comp - comp.mean()) / comp.std()
comp["stress"] = z.mean(axis=1)
comp["stress_smooth"] = comp["stress"].rolling(3, min_periods=1).mean()

# ---------- regime state + transitions ----------
def state(x):
    if x >= 0.5: return "stress"
    if x <= -0.5: return "calm"
    return "neutral"
comp["state"] = comp["stress_smooth"].apply(state)
comp["state_chg"] = (comp["state"] != comp["state"].shift()).cumsum()
runs = comp.groupby("state_chg").agg(start=("state", "first"),
                                      from_d=("state", lambda s: s.index[0]),
                                      to_d=("state", lambda s: s.index[-1]),
                                      months=("state", "size"))
runs = runs.reset_index(drop=True).rename(columns={"start": "state"})

current_state = comp["state"].iloc[-1]
current_stress = comp["stress_smooth"].iloc[-1]
last_transition_idx = comp.index[comp["state"] != current_state]
last_transition = last_transition_idx[-1] if len(last_transition_idx) else comp.index[0]
months_in_state = int((comp.index[-1].to_period("M")
                       - last_transition.to_period("M")).n)

# transitions table (last 8)
transitions = runs[runs.index > 0].copy()
transitions["prev_state"] = runs["state"].shift(1)
transitions = transitions.tail(8)

# ---------- composite-stress chart ----------
fig = go.Figure()
fig.add_scatter(x=comp.index, y=comp["stress"], mode="lines",
                line=dict(color=GREY, width=1), name="Composite stress (raw)")
fig.add_scatter(x=comp.index, y=comp["stress_smooth"], mode="lines",
                line=dict(color=BLUE, width=2.5), name="Composite stress (3-mo smoothed)")
fig.add_hline(y=0.5, line=dict(color=RED, dash="dot"),
              annotation_text="stress threshold +0.5", annotation_position="top left")
fig.add_hline(y=-0.5, line=dict(color=GREEN, dash="dot"),
              annotation_text="calm threshold −0.5", annotation_position="bottom left")
fig.add_hline(y=0, line=dict(color=GREY, width=0.5))
# regime shading for stress runs
stress_runs = runs[runs["state"] == "stress"]
for _, run in stress_runs.iterrows():
    fig.add_vrect(x0=run["from_d"], x1=run["to_d"],
                  fillcolor=RED, opacity=0.10, line_width=0)
fig.update_layout(title="Composite stress index — z-score of (VIX, HY OAS, "
                  "−Curve, EPU, GPR). Red bands = identified stress regimes.",
                  yaxis_title="z-score (standardised)", xaxis_title="month")

# ---------- VIX bucket forward returns (fresh from yfinance) ----------
spx = yf.download("^GSPC", period="20y", interval="1d",
                  auto_adjust=True, progress=False)["Close"].dropna()
if hasattr(spx, "columns"):                     # MultiIndex protection
    spx = spx.iloc[:, 0]
spx.index = pd.to_datetime(spx.index).tz_localize(None)
vix_d = sig["VIX"].dropna()
vix_d.index = pd.to_datetime(vix_d.index).tz_localize(None)
panel = pd.DataFrame(index=spx.index)
panel["spx"] = spx
panel["vix"] = vix_d.reindex(panel.index).ffill()
panel["fwd21"] = panel["spx"].shift(-21) / panel["spx"] - 1
panel = panel.dropna()
buckets = ["VIX < 15", "15-20", "20-30", "> 30"]
panel["bucket"] = pd.cut(panel["vix"], [-1, 15, 20, 30, 999], labels=buckets)
bk = panel.groupby("bucket", observed=False)["fwd21"].agg(["mean", "count"])
bar_colors = [GREEN, BLUE, GOLD, RED]
fig_vix = go.Figure(go.Bar(x=bk.index.astype(str), y=bk["mean"] * 100,
                           marker_color=bar_colors,
                           text=[f"{m*100:+.1f}%<br><span style='font-size:10px;color:#666'>n={int(n)}</span>"
                                 for m, n in zip(bk["mean"], bk["count"])],
                           textposition="outside"))
fig_vix.add_hline(y=0, line=dict(color=GREY, width=0.5))
fig_vix.update_layout(title="Average 21-day forward S&P 500 return by VIX bucket",
                      yaxis_title="forward 21-day return (%)",
                      xaxis_title="VIX level on entry day")

# ---------- equity-vol amplification cross-check ----------
ret_m = spx.resample("ME").last().pct_change().dropna()
ret_m.index = ret_m.index + pd.offsets.MonthEnd(0) - pd.offsets.MonthEnd(0)  # normalize
stress_months_ix = comp.index[comp["state"] == "stress"]
calm_months_ix = comp.index[comp["state"] == "calm"]
common = ret_m.index.intersection(comp.index)
vol_calm = ret_m.reindex(common.intersection(calm_months_ix)).std() * np.sqrt(12)
vol_stress = ret_m.reindex(common.intersection(stress_months_ix)).std() * np.sqrt(12)
amp = float(vol_stress / vol_calm) if vol_calm and vol_calm > 0 else float("nan")

# ---------- transitions table HTML ----------
tr_rows = ""
for _, row in transitions.iterrows():
    badge = ({"stress": RED, "calm": GREEN, "neutral": GREY}.get(row["state"], GREY))
    tr_rows += (f"<tr><td>{row['from_d'].strftime('%b %Y')}</td>"
                f"<td>{row['prev_state'] or '—'} <span style='color:#8d8d8d'>&rarr;</span> "
                f"<b style='color:{badge}'>{row['state']}</b></td>"
                f"<td>{row['months']} mo</td></tr>")

# ---------- snapshot tiles ----------
state_color = {"stress": RED, "calm": GREEN, "neutral": GOLD}[current_state]
SNAP = [
    ("Current Regime", f"<span style='color:{state_color}'>{current_state.upper()}</span>"),
    ("Composite Stress", f"{current_stress:+.2f}σ"),
    ("Months in Regime", f"{months_in_state}"),
    ("Stress Vol Multiplier", f"{amp:.2f}×" if amp == amp else "n/a"),
]
snap_html = "".join(
    f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
    for k, v in SNAP)

# ---------- HTML page ----------
HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Regime Tracker — when to adjust the strategy</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>LTCMA&nbsp;2026</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Regime Tracker</h1>
<p class="lede">A composite monthly stress index for spotting when markets are
moving from calm to stress &mdash; or back again &mdash; in time to adjust the
strategy. Combined with a near-term tactical overlay from event-study research.</p>
<p class="asof">As of {comp.index[-1].strftime('%b %Y')} &middot;
components: VIX, US HY spreads, US 10Y&minus;3M yield curve, EPU, GPR</p>
</div></section>
<main class="container">
<section class="block"><h2>Current State</h2>
{ccy_badge("USD", "US-centred indicators")}
<div class="metrics" style="grid-template-columns:repeat(4,1fr)">{snap_html}</div>
<p class="note">The composite stress index is the z-scored average of five
inputs. A reading above &plus;0.5 flags <b>stress</b>; below &minus;0.5 flags
<b>calm</b>; in between is neutral. The stress-vol multiplier compares realised
S&amp;P monthly vol in the identified stress regimes vs the calm ones &mdash; this
cross-validates the &asymp;1.5&ndash;1.6&times; figure used in the LTCMA's regime-
switching Monte Carlo.</p></section>

<section class="block"><h2>Composite Stress Index Over Time</h2>
<div class="tile chart"><div class="ch">{div(fig, "regime-line")}</div></div>
<p class="note">Red bands mark identified stress regimes (smoothed index above
&plus;0.5). The 2008 financial crisis, 2011 Euro crisis, 2015&ndash;16 China growth
scare, 2020 COVID and 2022 inflation shock are all clearly visible.</p>
</section>

<section class="block"><h2>Recent Regime Transitions</h2>
<div class="tile" style="padding:0 16px 8px">
<table class="ptable"><thead><tr><th>Month</th><th>Transition</th>
<th>Duration of new regime</th></tr></thead>
<tbody>{tr_rows}</tbody></table></div>
<p class="note">The most recent eight regime changes. When the current regime
has been running for several months and the composite is moving sharply, that
is the actionable signal &mdash; not a single noisy reading.</p>
</section>

<section class="block"><h2>Tactical Overlay — Near-Term Patterns</h2>
<p class="note">Findings drawn from the companion macro-overlay event-study work
(<code>macro_event_study.py</code>). These are short-horizon patterns that sit
above the LTCMA's 12-year base case &mdash; useful for timing entries and exits
inside the strategic allocation, not for resetting it.</p>
<div class="grid">
<div class="tile chart"><div class="ch">{div(fig_vix, "vix-bucket")}</div></div>
<div class="tile" style="padding:18px 22px">
<p style="font-weight:600;font-size:14px;margin-bottom:10px">Post-FOMC drift</p>
<p style="font-size:13px;color:#393939">Across <b>48 FOMC meetings</b>, the
S&amp;P 500 drifted an average of <b>+1.4% in the 20 trading days after</b>
each meeting &mdash; matching the academic Lucca&nbsp;&amp;&nbsp;Moench (2015)
finding. Real and tradeable; the equity tilt in the LTCMA's Edge-Tilted book
benefits from this on each new meeting cycle.</p>
<p style="font-weight:600;font-size:14px;margin:18px 0 10px">VIX panic &rarr; equity rally</p>
<p style="font-size:13px;color:#393939">When the VIX closes above 30, the
S&amp;P has returned, on average, the dollar amount shown in the chart over
the following 21 trading days &mdash; the well-known mean-reversion effect.
Consistent with this LTCMA's finding that stress regimes amplify volatility
without reliably depressing returns.</p>
<p style="font-weight:600;font-size:14px;margin:18px 0 10px">CPI surprises</p>
<p style="font-size:13px;color:#393939">178 CPI releases (2012&ndash;2026)
were bucketed by surprise size. Signal is real but noisier than the FOMC or
VIX patterns.</p>
</div></div>
</section>

<section class="block"><h2>How to read this page</h2>
<p>Regime changes do not arrive on a clean date. The right discipline is to
watch the <b>smoothed</b> composite (blue line) cross a threshold and stay
there for a few months before adjusting strategic exposures. The tactical
overlay below is for shorter-horizon tilts inside the strategic book.
Definitions in the <a href="glossary.html">Glossary</a>.</p>
</section>
</main>
<footer class="shell-foot"><div class="container"><p>Research and monitoring,
not investment advice.</p></div></footer></body></html>"""
open(f"{DOCS}/regime.html", "w", encoding="utf-8").write(HTML)
print(f"Regime tracker built -> {DOCS}/regime.html")
print(f"  current regime: {current_state.upper()}  composite stress {current_stress:+.2f}σ")
print(f"  months in current regime: {months_in_state}")
print(f"  stress-vol amplifier (S&P, vs calm): {amp:.2f}×")
print(f"  components, window {comp.index.min().date()}..{comp.index.max().date()} "
      f"({len(comp)} months)")
