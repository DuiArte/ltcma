"""Refresh real_numbers/portfolio.html and Portfolio_REAL_standalone.html with
TODAY's prices and USDMXN. Same portfolio data and computations as
18_portfolio.py but with SCALE=1.0 (real, un-scaled) and PRIVATE labels; also
re-injects the FX-attribution section with today's x_now (per-ticker unrealized
buckets recomputed from today's USD prices; realized lots unchanged).

Outputs:
  /mnt/c/Users/carlo/Documents/CarlosDuarteWebsite/real_numbers/portfolio.html
  /mnt/c/Users/carlo/Documents/CarlosDuarteWebsite/real_numbers/Portfolio_REAL_standalone.html

Source positions/cost basis: Copy of Carteras DBE 2.xlsx sheet 'DBE Acciones'.
Source prices: yfinance (BMV .MX listings + USDMXN=X).
"""
import glob as _glob
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

FXA = "/mnt/c/Users/carlo/Downloads/fx_attribution_2026-05-26/code"
sys.path.insert(0, FXA)
import make_section as ms

XLSX = "/mnt/c/Users/carlo/Downloads/Copy of Carteras DBE 2.xlsx"
DATA = os.path.expanduser("~/LTCMA/data")
REAL = Path("/mnt/c/Users/carlo/Documents/CarlosDuarteWebsite/real_numbers")
CSS = (REAL / "style.css").read_text(encoding="utf-8")

SCALE = 1.0
FILTER_ANOMALIES = True
INK, BLUE, GOLD, GREEN = "#111111", "#0a2540", "#6b7280", "#0a5d3a"
RED, GREY = "#7c2d12", "#888888"

sig = pd.read_csv(f"{DATA}/signals_fred.csv", index_col=0)
RATE = float(pd.to_numeric(sig["USDMXN"], errors="coerce").dropna().iloc[-1])

LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15), dragmode=False,
              margin=dict(l=64, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e5e5e5"), yaxis=dict(gridcolor="#e5e5e5"))


def divhtml(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False,
                               "responsive": True})


def fmt(x, dec=0):
    return f"{x:,.{dec}f}"


def fmts(x, dec=0):
    return f"{x:+,.{dec}f}"


def cval(mxn, dec=0, signed=False):
    f = fmts if signed else fmt
    return (f'<span class="cval" data-mxn="{f(mxn, dec)}" '
            f'data-usd="{f(mxn / RATE, dec)}">{f(mxn, dec)}</span>')


TICKER_MAP = {
    "AMZN": "AMZN.MX", "BA": "BA.MX", "GLD": "GLD.MX", "GOOGL": "GOOGL.MX",
    "IBM": "IBM.MX", "JPM": "JPM.MX", "MA": "MA.MX", "MELI N": "MELI.MX",
    "META": "META.MX", "MSFT": "MSFT.MX", "QQQ": "QQQ.MX", "SOXX": "SOXX.MX",
    "VGT": "VGT.MX", "VUG": "VUG.MX", "GMEXICO B": "GMEXICOB.MX",
    "LMT": "LMT.MX", "AMAT": "AMAT.MX", "MCHI": "MCHI.MX",
}

# ---------- load & clean (same logic as 18_portfolio.py) ----------
df = pd.read_excel(XLSX, "DBE Acciones", header=0)
for c in ["Títulos", "Costo promedio", "Precio mercado"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["Fecha"] = pd.to_datetime(df["Fecha"])
df["ticker"] = df["Emisora/Fondo"].astype(str).str.replace(" *", "", regex=False).str.strip()
df = df.dropna(subset=["Títulos", "Costo promedio", "Precio mercado"])
df["px_excel"] = df["Precio mercado"].astype(float)

_lo = (df["Fecha"].min() - pd.Timedelta(days=70)).strftime("%Y-%m-%d")
_syms = sorted({TICKER_MAP[t] for t in df["ticker"].unique() if t in TICKER_MAP})
try:
    _hist = yf.download(_syms, start=_lo, interval="1d",
                        auto_adjust=True, progress=False)["Close"]
    if isinstance(_hist, pd.Series):
        _hist = _hist.to_frame(name=_syms[0])
    if getattr(_hist.index, "tz", None) is not None:
        _hist.index = _hist.index.tz_localize(None)
    _hist = _hist.sort_index().ffill()

    def _asof_px(row):
        yt = TICKER_MAP.get(row["ticker"])
        if yt and yt in _hist.columns:
            s = _hist[yt].dropna()
            s = s[s.index <= row["Fecha"]]
            if len(s):
                return float(s.iloc[-1])
        return row["Precio mercado"]
    df["Precio mercado"] = df.apply(_asof_px, axis=1)
    print(f"  historical prices from Yahoo: {len(_syms)} tickers since {_lo}")
except Exception as e:
    print(f"  Yahoo historical pricing failed ({e}) -- using Excel prices")
    _hist = pd.DataFrame()

df["shares"] = df["Títulos"] * SCALE
df["value"] = df["shares"] * df["Precio mercado"]
df["cost"] = df["shares"] * df["Costo promedio"]
df["pm"] = df["value"] - df["cost"]
df["ret"] = df["Precio mercado"] / df["Costo promedio"] - 1

bad_dates = set()
if FILTER_ANOMALIES:
    bad = df[(df["ret"] < -0.60) | (df["ret"] > 3.0)]
    for _, b in bad.iterrows():
        print(f"  filtered anomaly: {b['ticker']} {b['Fecha'].date()} "
              f"ret={b['ret']*100:.0f}% (likely unadjusted split)")
    bad_dates = set(bad["Fecha"])
    df = df.drop(bad.index)

_MES = dict(ene=1, feb=2, mar=3, abr=4, may=5, jun=6, jul=7, ago=8, sep=9, oct=10, nov=11, dic=12)


def _money(x):
    s = re.sub(r"[^0-9.\-]", "", str(x))
    return float(s) if s else 0.0


_exrows = []
for _f in sorted(_glob.glob("/mnt/c/Users/carlo/Downloads/GBM Transacciones Liquidacion*.csv")):
    try:
        _e = pd.read_csv(_f, dtype=str, keep_default_na=False)
        for _, _r in _e.iterrows():
            _d = str(_r.get("Descripción", ""))
            if "Acciones" not in _d:
                continue
            _t = str(_r["Emisora"]).replace(" *", "").strip()
            _p = str(_r["Fecha"]).split("/")
            _dt = pd.Timestamp(int(_p[2]), _MES[_p[1].lower()[:3]], int(_p[0]))
            _sh = _money(_r["Títulos"])
            _exrows.append((_t, _dt, _sh if "Compra" in _d else -_sh))
    except Exception:
        pass
_ex = pd.DataFrame(_exrows, columns=["ticker", "date", "sh"])

BASELINE = 10_000_000.0
_snap = df.pivot_table(index="Fecha", columns="ticker", values="Títulos", aggfunc="sum").fillna(0.0).sort_index()
_csnap = df.pivot_table(index="Fecha", columns="ticker", values="Costo promedio", aggfunc="last").sort_index()
_first = _snap.index.min()
_daily = pd.date_range(_first.normalize(), pd.Timestamp.today().normalize(), freq="D")
_pos = _snap.reindex(_daily).ffill().fillna(0.0)
_acd = _csnap.reindex(_daily).ffill()
_px = _hist.reindex(_daily).ffill() if len(_hist) else pd.DataFrame(index=_daily)
_epx = df.pivot_table(index="Fecha", columns="ticker", values="px_excel", aggfunc="last").reindex(_daily).ffill()

_td = pd.DataFrame(columns=["date", "side", "shares", "text"])
try:
    _bl = pd.read_csv(f"{DATA}/blotter_clean.csv", parse_dates=["date"])
    _bl = _bl[_bl["date"] >= _first]
    _rows = []
    for (_d, _sd), _g in _bl.groupby(["date", "side"]):
        _per = _g.groupby("ticker")["shares"].sum().sort_values(ascending=False)
        _sg = "+" if _sd == "buy" else "-"
        _lst = ", ".join(f"{_t} {_sg}{int(abs(_sh))}" for _t, _sh in _per.items())
        _rows.append(dict(date=_d, side=_sd, shares=float(_g["shares"].sum()),
                          text=f"{_d.strftime('%d %b %Y')} - {_sd.title()}: {_lst}"))
    _td = pd.DataFrame(_rows)
except Exception as _e:
    print(f"  blotter markers unavailable: {_e}")

_mv = pd.Series(0.0, index=_daily)
_ic = pd.Series(0.0, index=_daily)
for _tk in _pos.columns:
    _yt = TICKER_MAP.get(_tk)
    if _yt and _yt in _px.columns:
        _mv += _pos[_tk] * SCALE * _px[_yt].ffill().fillna(0.0)
    elif _tk in _epx.columns:
        _mv += _pos[_tk] * SCALE * _epx[_tk].fillna(0.0)
    if _tk in _acd.columns:
        _ic += _pos[_tk] * SCALE * _acd[_tk].ffill().fillna(0.0)
_unreal = _mv - _ic

_realized = pd.Series(0.0, index=_snap.index)
_sn = list(_snap.index)
for _i in range(1, len(_sn)):
    _d1 = _sn[_i]
    for _tk in _snap.columns:
        _drop = float(_snap.loc[_sn[_i-1], _tk] - _snap.loc[_d1, _tk])
        if _drop > 0:
            _yt = TICKER_MAP.get(_tk)
            if _yt and _yt in _px.columns and _d1 in _px.index and pd.notna(_px.loc[_d1, _yt]):
                _spx = float(_px.loc[_d1, _yt])
            elif _tk in _epx.columns and _d1 in _epx.index and pd.notna(_epx.loc[_d1, _tk]):
                _spx = float(_epx.loc[_d1, _tk])
            else:
                _spx = 0.0
            _avc = float(_acd.loc[_d1, _tk]) if (_tk in _acd.columns and pd.notna(_acd.loc[_d1, _tk])) else 0.0
            _realized.loc[_d1] += _drop * SCALE * (_spx - _avc)
_cumreal = _realized.cumsum().reindex(_daily).ffill().fillna(0.0)

equity = _mv
balance = _ic
ts = pd.DataFrame({"value": equity, "equity": equity, "balance": balance})
ts = ts[ts["equity"] > 0]
dates = ts.index

latest = df[df["Fecha"] == df["Fecha"].max()].copy()
asof_excel = df["Fecha"].max().strftime("%d %b %Y")

try:
    fx_live = float(yf.Ticker("MXN=X").history(period="2d")["Close"].iloc[-1])
except Exception:
    fx_live = RATE
RATE = fx_live

priced_at = None
live_px = {}
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
            new_mxn = live_px[yt]   # .MX listings are MXN-quoted
            latest.loc[idx, "Precio mercado"] = new_mxn
        latest["value"] = latest["shares"] * latest["Precio mercado"]
        latest["pm"] = latest["value"] - latest["cost"]
        latest["ret"] = latest["Precio mercado"] / latest["Costo promedio"] - 1
        print(f"  live priced {len(live_px)} holdings @ {priced_at} USDMXN {fx_live:.4f}")
    except Exception as e:
        print(f"  live pricing failed: {e} -- using last-snapshot prices")

tot_val = latest["value"].sum()
tot_cost = latest["cost"].sum()
latest["weight"] = latest["value"] / tot_val
latest = latest.sort_values("value", ascending=False)
port_ret = tot_val / tot_cost - 1
asof = priced_at or asof_excel

if priced_at and len(ts):
    _ul = tot_val - tot_cost
    ts.iloc[-1, ts.columns.get_loc("equity")] = float(ts.iloc[-1]["balance"]) + _ul
    ts.iloc[-1, ts.columns.get_loc("value")] = float(ts.iloc[-1]["equity"])
    dates = ts.index

CAPITAL = BASELINE * SCALE
try:
    _blf = pd.read_csv(f"{DATA}/blotter_clean.csv", parse_dates=["date"])
    _blf["flow"] = _blf["shares"] * _blf["price"] * _blf["side"].map({"buy": 1.0, "sell": -1.0})
    _ninv = (_blf.groupby("date")["flow"].sum().sort_index().cumsum() * SCALE)
    _ninv = _ninv.reindex(ts.index, method="ffill").fillna(0.0)
except Exception as _e:
    print(f"  capital model: blotter unavailable ({_e})")
    _ninv = pd.Series(0.0, index=ts.index)
_idle = CAPITAL - _ninv
_real = ts["balance"] - _ninv
_unr = ts["equity"] - ts["balance"]
ts["realized_pool"] = CAPITAL + _real
ts["total"] = ts["realized_pool"] + _unr
_total_now = float(ts["total"].iloc[-1])
_idle_now = float(_idle.iloc[-1])
_real_now = float(_real.iloc[-1])
_unr_now = float(_unr.iloc[-1])
print(f"  capital {CAPITAL:,.0f} | realized {_real_now:,.0f} | unrealized {_unr_now:,.0f} | "
      f"total {_total_now:,.0f} | return {(_total_now/CAPITAL-1)*100:+.1f}%")

# ---------- charts ----------
f1 = go.Figure()
f1.add_scatter(x=dates, y=ts["total"], mode="lines",
               name="Total value (realized + unrealized)",
               line=dict(color=BLUE, width=2.6))
f1.add_scatter(x=dates, y=ts["realized_pool"], mode="lines",
               name="Capital + realized (locked in)",
               line=dict(color=GREEN, width=1.6, dash="dot"))


def _eq_at(_dt):
    _s = ts["total"][ts.index <= _dt]
    return float(_s.iloc[-1]) if len(_s) else None


for _side, _col, _sym in [("buy", GREEN, "triangle-up"), ("sell", RED, "triangle-down")]:
    _s = _td[_td["side"] == _side] if len(_td) else _td
    _x = list(_s["date"]) if len(_s) else []
    _y = [_eq_at(_d) for _d in _x]
    _txt = list(_s["text"]) if len(_s) else []
    f1.add_scatter(x=_x, y=_y, mode="markers", name=f"{_side.title()}s",
                   marker=dict(color=_col, symbol=_sym, size=9,
                               line=dict(width=1, color="white")),
                   text=_txt, hoverinfo="text")
f1.add_hline(y=CAPITAL, line=dict(color=INK, width=1, dash="dot"),
             annotation_text="Capital (10M, recycled)",
             annotation_position="bottom right")
f1.update_layout(title="Total value — realized (locked in) + unrealized vs 10M capital (daily, real)",
                 yaxis_title="MXN (real)", xaxis_title="date",
                 legend=dict(orientation="h", y=-0.18))

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

al = latest.sort_values("weight")
f3 = go.Figure(go.Bar(x=al["weight"] * 100, y=al["ticker"], orientation="h",
                      marker_color=BLUE,
                      text=[f"{w*100:.1f}%" for w in al["weight"]],
                      textposition="outside"))
f3.update_layout(title="Current allocation by holding",
                 xaxis_title="% of stock portfolio")

# Holdings table is now rendered by the FX-attribution fragment further down,
# with realized | unrealized | total cols + Mode toggle (Normal / FX Impact).

# ---------- metrics ----------
_pnl_now = _real_now + _unr_now
SNAP = [("Total Value", cval(_total_now)),
        ("Realized P / L", cval(_real_now, signed=True)),
        ("Unrealized P / L", cval(_unr_now, signed=True)),
        ("Total P / L", cval(_pnl_now, signed=True)),
        ("Total Return", f"{(_total_now/CAPITAL-1)*100:+.1f}%"),
        ("Live Priced", asof)]
snap = "".join(
    f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
    for k, v in SNAP)


# ---------- currency-toggle JavaScript ----------
def _arr(s):
    return ",".join(f"{v:.0f}" for v in s)


def _mk_y(side):
    _s = _td[_td["side"] == side] if len(_td) else _td
    _o = []
    for _d in (_s["date"] if len(_s) else []):
        _ss = ts["total"][ts.index <= _d]
        _o.append(float(_ss.iloc[-1]) if len(_ss) else 0.0)
    return _o


_totm = _arr(ts["total"])
_totu = _arr(ts["total"] / RATE)
_ream = _arr(ts["realized_pool"])
_reau = _arr(ts["realized_pool"] / RATE)
_by = _mk_y("buy")
_sy = _mk_y("sell")
_bym = ",".join(f"{v:.0f}" for v in _by)
_byu = ",".join(f"{v/RATE:.0f}" for v in _by)
_sym2 = ",".join(f"{v:.0f}" for v in _sy)
_syu = ",".join(f"{v/RATE:.0f}" for v in _sy)
JS = """
<script>
var TOT={mxn:[__TOTM__],usd:[__TOTU__]},REAL={mxn:[__REAM__],usd:[__REAU__]};
var BUY={mxn:[__BYM__],usd:[__BYU__]},SEL={mxn:[__SYM__],usd:[__SYU__]};
function setCurrency(c){
  document.querySelectorAll('.cval').forEach(function(e){e.textContent=e.dataset[c];});
  document.querySelectorAll('.ccy-toggle button').forEach(function(b){
    b.classList.toggle('active',b.dataset.cur===c);});
  var lbl=document.getElementById('ccy-label');
  if(lbl) lbl.textContent=c.toUpperCase();
  var d=document.getElementById('pf-value');
  if(d&&window.Plotly){
    Plotly.restyle(d,{y:[TOT[c],REAL[c],BUY[c],SEL[c]]},[0,1,2,3]);
    Plotly.relayout(d,{'yaxis.title.text':c.toUpperCase()+' (real)'});
  }
  var fxBtn=document.querySelector('#fxa-ccy button[data-v="'+c.toUpperCase()+'"]');
  if(fxBtn) fxBtn.click();
}
document.addEventListener('DOMContentLoaded',function(){setCurrency('mxn');});
</script>
""".replace("__TOTM__", _totm).replace("__TOTU__", _totu) \
   .replace("__REAM__", _ream).replace("__REAU__", _reau) \
   .replace("__BYM__", _bym).replace("__BYU__", _byu) \
   .replace("__SYM__", _sym2).replace("__SYU__", _syu)

# ---------- FX attribution: refresh x_now + per-ticker unrealized buckets ----------
ATTR = json.loads((Path(FXA) / "_cache" / "attribution_data.json").read_text())
try:
    ATTR_DATE = pd.to_datetime(priced_at).strftime("%Y-%m-%d")
except Exception:
    ATTR_DATE = pd.Timestamp.today().strftime("%Y-%m-%d")

ATTR["x_now"] = float(fx_live)
ATTR["as_of"] = ATTR_DATE

POS_KEY = {"GMEXICOB": "GMEXICO B", "CCJ": "CCJ N", "MELI": "MELI N"}
for r in ATTR["rows"]:
    tk = r["ticker"]
    pos_tk = POS_KEY.get(tk, tk)
    u = r["unrealized"]
    if r["native"]:
        new_mxn_px = live_px.get(TICKER_MAP.get(pos_tk, ""))
        if new_mxn_px:
            curr_mxn_val = r["shares"] * new_mxn_px
            u["stock"] = curr_mxn_val - u["mxn_cost"]
            u["pnl"] = u["stock"]
            u["x_val"] = 1.0
        continue
    yfs = TICKER_MAP.get(pos_tk)
    if yfs is None:
        continue
    new_mxn_px = live_px.get(yfs)
    if new_mxn_px is None:
        continue
    new_usd_px = new_mxn_px / fx_live
    x_buy = u.get("x_buy")
    mxn_cost = u.get("mxn_cost") or 0.0
    if x_buy is None or x_buy == 0 or mxn_cost == 0:
        continue
    usd_cost = mxn_cost / x_buy
    usd_val_now = r["shares"] * new_usd_px
    u["x_val"] = float(fx_live)
    u["stock"] = x_buy * (usd_val_now - usd_cost)
    u["fx"] = usd_cost * (fx_live - x_buy)
    u["interaction"] = (usd_val_now - usd_cost) * (fx_live - x_buy)
    u["pnl"] = u["stock"] + u["fx"] + u["interaction"]
# realized buckets unchanged: those sells happened at the historical X_sell.

section = ms.build_section(ATTR, scale=1.0, prefix="fxa", theme="light",
                           title="Holdings")
assert section.startswith('<section id="fxa-root">'), "FXA section malformed"
assert section.rstrip().endswith("</section>"), "FXA section not closed"

# ---------- assemble pages ----------
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"

NAV_PORTFOLIO = ('<nav><a href="index.html">Dashboard</a>'
                 '<a href="report.html">Full Report</a>'
                 '<a href="portfolio.html">Portfolio</a>'
                 '<a href="strategies.html">Strategies</a>'
                 '<a href="stocks.html">Stock Analysis</a>'
                 '<a href="signals.html">Stock Signals</a>'
                 '<a href="regime.html">Regime Tracker</a>'
                 '<a href="glossary.html">Glossary</a>'
                 '<a href="index.html#about">About</a></nav>')

NAV_STANDALONE = ('<nav><a href="#">Dashboard</a><a href="#">Full Report</a>'
                  '<a href="#">Portfolio</a><a href="#">Strategies</a>'
                  '<a href="#">Stock Analysis</a><a href="#">Stock Signals</a>'
                  '<a href="#">Regime Tracker</a><a href="#">Glossary</a>'
                  '<a href="#">About</a></nav>')

GLOSS_PORTFOLIO = '<a href="glossary.html">Glossary</a>'
GLOSS_STANDALONE = '<a href="#">Glossary</a>'

f1_div = divhtml(f1, "pf-value")
f2_div = divhtml(f2, "pf-rel")
f3_div = divhtml(f3, "pf-alloc")

body_template = (
    '<body><header class="shell"><div class="shell-in">'
    '<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>__NAV__'
    "</div></header>\n"
    '<section class="hero"><div class="container">'
    "<h1>Stock Portfolio Tracker</h1>"
    '<p class="lede">A live view of the GBM equity book &mdash; every position '
    "measured against its cost basis and against the portfolio as a whole. "
    "Figures convert between Mexican pesos and US dollars at the current rate.</p>"
    f'<p class="asof">As of {asof} &middot; GBM equity holdings &middot; '
    f"USD/MXN {RATE:.2f}</p>"
    "</div></section>\n"
    '<main class="container">'
    '<div class="scaled-note"><b>PRIVATE copy &mdash; real (un-scaled) amounts.</b> '
    "Do not publish this file. Prices, returns and weights are exact. FX positions "
    "and non-GBM cash are excluded; rows with impossible returns (e.g. unadjusted "
    "stock splits) are filtered automatically.</div>\n"
    '<section class="block"><h2>Snapshot</h2>'
    '<div class="ccy-toggle">'
    '<button data-cur="mxn" class="active" onclick="setCurrency(\'mxn\')">MXN</button>'
    '<button data-cur="usd" onclick="setCurrency(\'usd\')">USD</button></div>'
    '<p class="note">Currency: <b id="ccy-label">MXN</b> &mdash; returns and '
    "weights read the same in either currency. Definitions in the __GLOSS__.</p>"
    f'<div class="metrics" style="grid-template-columns:repeat(6,1fr)">{snap}</div>'
    "</section>\n"
    '<section class="block"><h2>Total Value vs Capital</h2>'
    f'<div class="tile chart"><div class="ch">{f1_div}</div></div></section>\n'
    f"{section}\n"
    "<script>(function(){var b=document.getElementById('fxa-ccy');"
    "if(b&&b.parentElement)b.parentElement.style.display='none';})();</script>\n"
    '<section class="block"><h2>Portfolio vs Its Holdings</h2>'
    f'<div class="grid"><div class="tile chart"><div class="ch">{f2_div}</div></div>'
    f'<div class="tile chart"><div class="ch">{f3_div}</div></div></div></section>\n'
    "</main>\n"
    '<footer class="shell-foot"><div class="container">'
    "<p>Figures scaled for confidentiality. Research and monitoring, "
    "not investment advice.</p></div></footer>\n"
    f"{JS}</body></html>"
)

# portfolio.html (linked stylesheet, real nav)
HEAD_LINKED = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    "<title>Stock Portfolio Tracker — Real Figures (PRIVATE)</title>\n"
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&"
    'display=swap">\n'
    f'<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script>'
    "</head>\n"
)
portfolio_html = HEAD_LINKED + (body_template
                                .replace("__NAV__", NAV_PORTFOLIO)
                                .replace("__GLOSS__", GLOSS_PORTFOLIO))
(REAL / "portfolio.html").write_text(portfolio_html, encoding="utf-8")

# Portfolio_REAL_standalone.html (inline CSS, # nav)
HEAD_INLINE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    "<title>Stock Portfolio Tracker — Real Figures (PRIVATE)</title>\n"
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&"
    'display=swap">\n'
    f"<style>\n{CSS}\n</style>"
    f'<script src="{PLOTLY}"></script></head>\n'
)
standalone_html = HEAD_INLINE + (body_template
                                 .replace("__NAV__", NAV_STANDALONE)
                                 .replace("__GLOSS__", GLOSS_STANDALONE))
(REAL / "Portfolio_REAL_standalone.html").write_text(standalone_html, encoding="utf-8")

# ---------- summary ----------
print(f"asof {asof} | USDMXN {RATE:.4f}")
print(f"TOT (MXN) {_total_now:,.0f} | Realized {_real_now:+,.0f} | "
      f"Unrealized {_unr_now:+,.0f} | TOTAL P/L {_pnl_now:+,.0f}")
print(f"TOT (USD) {_total_now/RATE:,.0f} | Realized {_real_now/RATE:+,.0f} | "
      f"Unrealized {_unr_now/RATE:+,.0f} | TOTAL P/L {_pnl_now/RATE:+,.0f}")
print(f"holdings: {len(latest)}")
print(f"wrote {REAL / 'portfolio.html'}")
print(f"wrote {REAL / 'Portfolio_REAL_standalone.html'}")
