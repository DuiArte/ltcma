"""Build the GBM stock-portfolio tracker page -> docs/portfolio.html.
Source: 'Copy of Carteras DBE 2.xlsx' sheet 'DBE Acciones' (GBM stock holdings
only -- FX positions and non-GBM bank cash are excluded by design).
A x1.8 scaling constant is applied to share counts so every formula stays
intact (value = shares*price, P/M = value - cost, weights unchanged) while the
displayed magnitudes are not the real amounts. Source Excel is never modified.
A MXN / USD currency toggle converts figures at the latest USDMXN rate.
Refresh: update the Excel, re-run this script.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from glossary import NAV, ccy_badge

FXA = "/mnt/c/Users/carlo/Downloads/fx_attribution_2026-05-26/code"
sys.path.insert(0, FXA)
import make_section as ms

XLSX = "/mnt/c/Users/carlo/Downloads/Copy of Carteras DBE 2.xlsx"
DATA = os.path.expanduser("~/LTCMA/data")
DOCS = os.path.expanduser("~/LTCMA/docs")
SCALE = 1.8                       # holdings scaling constant (obfuscation)
FILTER_ANOMALIES = True           # drop rows with impossible returns (bad data)
INK, BLUE, GOLD, GREEN = "#111111", "#0a2540", "#6b7280", "#0a5d3a"
RED, GREY = "#7c2d12", "#888888"

# latest USDMXN rate for the currency toggle
sig = pd.read_csv(f"{DATA}/signals_fred.csv", index_col=0)
RATE = float(pd.to_numeric(sig["USDMXN"], errors="coerce").dropna().iloc[-1])

LAYOUT = dict(template="plotly_white",
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=15), dragmode=False,
              margin=dict(l=64, r=24, t=52, b=46),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e5e5e5"), yaxis=dict(gridcolor="#e5e5e5"))

def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False, "responsive": True})

# --- number formatting (normalized across the page) ---
def fmt(x, dec=0):
    return f"{x:,.{dec}f}"

def fmt_sh(x):                            # share counts: always integer display
    """Share count: always rounded to a whole share for display. The underlying
    JSON DATA blob keeps full precision; only the rendered string rounds."""
    return f"{round(x):,d}"

def fmts(x, dec=0):                       # signed
    return f"{x:+,.{dec}f}"

def cval(mxn, dec=0, signed=False):
    """A currency-aware figure carrying both MXN and USD, toggled by JS."""
    f = fmts if signed else fmt
    return (f'<span class="cval" data-mxn="{f(mxn, dec)}" '
            f'data-usd="{f(mxn / RATE, dec)}">{f(mxn, dec)}</span>')

# Map portfolio tickers to yfinance symbols — BMV (.MX) listings, MXN-native.
TICKER_MAP = {
    "AMZN": "AMZN.MX", "BA": "BA.MX", "GLD": "GLD.MX", "GOOGL": "GOOGL.MX",
    "IBM": "IBM.MX", "JPM": "JPM.MX", "MA": "MA.MX", "MELI N": "MELI.MX",
    "META": "META.MX", "MSFT": "MSFT.MX", "QQQ": "QQQ.MX", "SOXX": "SOXX.MX",
    "VGT": "VGT.MX", "VUG": "VUG.MX", "GMEXICO B": "GMEXICOB.MX",
    "LMT": "LMT.MX", "AMAT": "AMAT.MX", "MCHI": "MCHI.MX",
    "ASTS": "ASTS.MX", "XLE": "XLE.MX",
    # "CCJ N" has no Yahoo .MX listing -> priced from the broker column (fallback below)
}

# ---------- broker source of truth: GBM "Detalle de Portafolio" export ----------
# Carlos's authoritative position file in Downloads. Supersedes the (stale) Excel
# for the *current* snapshot: real share counts, broker cost basis, and the GBMF2
# cash sleeve. Sections are single-column header rows; the equity book = "Mercado
# de Capitales Nacional" + "Mercado de Capitales Global (SIC)". The "GBMF2 BM" line
# under "Fondos de Inversion Deuda" is the equity-sleeve cash (Rule 3 — settled MXN
# parks here between trades; it is the cash account for the equity book).
import csv as _csv, re as _re2, glob as _g2
def _bmoney(x):
    s = _re2.sub(r"[^0-9.\-]", "", str(x)); return float(s) if s else 0.0
def load_broker_snapshot():
    def _ts(p):                                          # the 13-digit Unix-ms stamp, ignoring " (1)" etc.
        m = _re2.search(r"(\d{13})", os.path.basename(p))
        return int(m.group(1)) if m else 0
    files = sorted(_g2.glob("/mnt/c/Users/carlo/Downloads/GBM_Homebroker_Detalle_de_Portafolio_*.csv"), key=_ts)
    if not files:
        return None, None, None
    path = files[-1]
    ms_ts = _ts(path)
    snap_date = pd.to_datetime(ms_ts, unit="ms") if ms_ts else pd.Timestamp.today()
    sect = None; eq = []; cash = None
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for parts in _csv.reader(fh):
            if not parts:
                continue
            if len(parts) == 1:                         # section header row
                sect = parts[0].strip(); continue
            if parts[0].strip() == "Emisora/Fondo":     # column header row
                continue
            name = parts[0].replace("*", "").strip()
            if sect in ("Mercado de Capitales Nacional", "Mercado de Capitales Global (SIC)"):
                eq.append({"ticker": name, "Títulos": _bmoney(parts[1]),
                           "Costo promedio": _bmoney(parts[2]),
                           "Precio mercado": _bmoney(parts[3]),
                           "valor_broker": _bmoney(parts[5]), "imp_cto_broker": _bmoney(parts[9])})
            elif name == "GBMF2 BM":
                cash = _bmoney(parts[5])                # Valor mercado of the cash sleeve
    return pd.DataFrame(eq), cash, snap_date

# ---------- load & clean ----------
df = pd.read_excel(XLSX, "DBE Acciones", header=0)
for c in ["Títulos", "Costo promedio", "Precio mercado"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["Fecha"] = pd.to_datetime(df["Fecha"])
df["ticker"] = df["Emisora/Fondo"].astype(str).str.replace(" *", "", regex=False).str.strip()
df = df.dropna(subset=["Títulos", "Costo promedio", "Precio mercado"])
df["px_excel"] = df["Precio mercado"].astype(float)  # raw Excel MXN price, kept for the Yahoo-unpriceable fallback

# ---------- Yahoo-sourced market prices (historical + live) ----------
# Every (date, holding) market price comes from Yahoo Finance via the BMV (.MX)
# listing; the Excel supplies only share counts and cost basis. Falls back to the
# Excel price for any ticker Yahoo can't price.
_lo = (df["Fecha"].min() - pd.Timedelta(days=70)).strftime("%Y-%m-%d")  # cover exec blotter
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

# ---------- daily portfolio value (Excel positions = truth, Yahoo prices) ----------
# Positions come from the Excel snapshots (the source of truth) forward-filled to
# daily; sells are inferred where a position drops between snapshots. The series is
# back-extended to the first stock execution via the GBM blotter (reverse-walked
# from the first snapshot). Each day is priced from Yahoo (BMV .MX) and the cost
# basis uses the Excel average cost.
import glob as _glob
_MES = dict(ene=1, feb=2, mar=3, abr=4, may=5, jun=6, jul=7, ago=8, sep=9, oct=10, nov=11, dic=12)
def _money(x):
    import re as _re
    s = _re.sub(r"[^0-9.\-]", "", str(x)); return float(s) if s else 0.0

# parse stock executions (buys/sells) from the Liquidacion blotter CSVs
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

# Excel snapshots: positions + per-snapshot average cost (both truth)
import glob as _glob
BASELINE = 10_000_000.0          # starting capital (MXN)
_snap = df.pivot_table(index="Fecha", columns="ticker", values="Títulos", aggfunc="sum").fillna(0.0).sort_index()
_csnap = df.pivot_table(index="Fecha", columns="ticker", values="Costo promedio", aggfunc="last").sort_index()
_first = _snap.index.min()
_daily = pd.date_range(_first.normalize(), pd.Timestamp.today().normalize(), freq="D")
_pos = _snap.reindex(_daily).ffill().fillna(0.0)         # positions truth; sells = drops
_acd = _csnap.reindex(_daily).ffill()                    # avg cost as-of each date (truth)
_px  = _hist.reindex(_daily).ffill() if "_hist" in dir() else pd.DataFrame(index=_daily)
_epx = df.pivot_table(index="Fecha", columns="ticker", values="px_excel", aggfunc="last").reindex(_daily).ffill()  # Excel MXN price fallback (e.g. CCJ N)

# trade markers from the consolidated, de-duplicated blotter (operation dates).
# Built by make_blotter.py from the full GBM export universe; aggregated to one
# marker per day+side, with the hover listing the tickers traded that day.
_td = pd.DataFrame(columns=["date", "side", "shares", "text"])
try:
    _bl = pd.read_csv(f"{DATA}/blotter_clean.csv", parse_dates=["date"])
    _bl = _bl[_bl["date"] >= _first]                     # only within the curve window
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
print(f"  trade markers: {len(_td)} day-events from blotter_clean.csv")

# daily market value and invested cost (scaled), then unrealized P&L
_mv = pd.Series(0.0, index=_daily)
_ic = pd.Series(0.0, index=_daily)
for _tk in _pos.columns:
    _yt = TICKER_MAP.get(_tk)
    if _yt and _yt in _px.columns:
        _mv += _pos[_tk] * SCALE * _px[_yt].ffill().fillna(0.0)
    elif _tk in _epx.columns:
        _mv += _pos[_tk] * SCALE * _epx[_tk].fillna(0.0)        # Yahoo-unpriceable -> Excel price
    if _tk in _acd.columns:
        _ic += _pos[_tk] * SCALE * _acd[_tk].ffill().fillna(0.0)
_unreal = _mv - _ic

# realized P&L: positions dropping between snapshots, valued at Yahoo on the drop date
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

equity = _mv                              # market value (mark-to-market)
balance = _ic                             # cost basis (capital invested)
ts = pd.DataFrame({"value": equity, "equity": equity, "balance": balance})
ts = ts[ts["equity"] > 0]
dates = ts.index
print(f"  equity/balance: {len(ts)} days | baseline {BASELINE:,.0f} | "
      f"equity {equity.iloc[-1]:,.0f} balance {balance.iloc[-1]:,.0f}")

# ---------- latest snapshot: BROKER source of truth (with LIVE pricing override) ----------
# The current holdings, cost basis, and cash come from the GBM "Detalle de
# Portafolio" export (authoritative), NOT the stale Excel. The Excel still drives
# the historical curve above; the broker file drives every headline KPI and the
# holdings table so the numbers match the account exactly.
_bdf, BROKER_CASH, _bsnap = load_broker_snapshot()
if _bdf is None or _bdf.empty:
    raise SystemExit("FATAL: no GBM Detalle de Portafolio CSV found in Downloads — cannot build canonical snapshot")
latest = _bdf.copy()
latest["shares"] = latest["Títulos"] * SCALE
latest["cost"] = latest["shares"] * latest["Costo promedio"]
latest["value"] = latest["shares"] * latest["Precio mercado"]   # broker mark; live-overridden below
latest["pm"] = latest["value"] - latest["cost"]
latest["ret"] = latest["Precio mercado"] / latest["Costo promedio"] - 1
latest["px_excel"] = latest["Precio mercado"].astype(float)     # broker price = Yahoo-unpriceable fallback
asof_excel = _bsnap.strftime("%Y-%m-%d")
print(f"  broker snapshot: {len(latest)} equity positions @ {asof_excel} | GBMF2 cash {BROKER_CASH:,.2f}")

# (TICKER_MAP defined above — BMV .MX listings)

# refresh USDMXN to the live rate (falls back to FRED rate if yfinance fails)
try:
    fx_live = float(yf.Ticker("MXN=X").history(period="2d")["Close"].iloc[-1])
except Exception:
    fx_live = RATE
RATE = fx_live          # used by cval() for the MXN/USD toggle

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
        priced_at = ld.dropna(how="all").index[-1].strftime("%Y-%m-%d")
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

# ---------- FX attribution: refresh x_now + per-ticker unrealized buckets ----------
# Cached realized lots (from 2026-05-26 GBM snapshot) are kept as-is; unrealized
# buckets are recomputed against today's USD prices + live USDMXN. Tickers may
# lag the latest portfolio by N days when positions change.
ATTR = json.loads((Path(FXA) / "_cache" / "attribution_data.json").read_text())
try:
    ATTR_DATE = pd.to_datetime(priced_at).strftime("%Y-%m-%d")
except Exception:
    ATTR_DATE = pd.Timestamp.today().strftime("%Y-%m-%d")
ATTR["x_now"] = float(fx_live)
ATTR["as_of"] = ATTR_DATE

POS_KEY = {"GMEXICOB": "GMEXICO B", "CCJ": "CCJ N", "MELI": "MELI N"}
for r in ATTR["rows"]:
    pos_tk = POS_KEY.get(r["ticker"], r["ticker"])
    u = r["unrealized"]
    if r["native"]:
        new_mxn_px = live_px.get(TICKER_MAP.get(pos_tk, ""))
        if new_mxn_px:
            u["stock"] = r["shares"] * new_mxn_px - u["mxn_cost"]
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
    if not x_buy or mxn_cost == 0:
        continue
    usd_cost = mxn_cost / x_buy
    usd_val_now = r["shares"] * new_usd_px
    u["x_val"] = float(fx_live)
    u["stock"] = x_buy * (usd_val_now - usd_cost)
    u["fx"] = usd_cost * (fx_live - x_buy)
    u["interaction"] = (usd_val_now - usd_cost) * (fx_live - x_buy)
    u["pnl"] = u["stock"] + u["fx"] + u["interaction"]

fxa_section = ms.build_section(ATTR, scale=SCALE, prefix="fxa", theme="light",
                               title="FX Attribution")
# Workaround for upstream make_section.py bug: its CSS template runs
# .replace("@P", prefix) before .replace("@PANEL", ...)/("@POS", ...), so
# those two tokens get mangled to "fxaANEL" / "fxaOS". Patch them post-hoc.
fxa_section = (fxa_section.replace("background:fxaANEL", "background:#fff")
                          .replace("color:fxaOS", "color:#0a5d3a"))
assert fxa_section.startswith('<section id="fxa-root">'), "FXA section malformed"
assert "fxaANEL" not in fxa_section and "fxaOS" not in fxa_section

# ---------- canonical equity-book accounting (recycled $10M base + GBMF2 cash sleeve) ----------
# Source of truth: the broker "Detalle de Portafolio" snapshot (positions + cost
# basis + GBMF2 cash), re-priced live from Yahoo. The book is measured against a
# fixed $10M MXN base with capital recycled through it (Rule 1).
#
#   Total value    = equity market value + GBMF2 cash sleeve       (Rule 3)
#   Unrealized P/L = market value - broker cost basis              (live mark)
#   Realized  P/L  = (cost basis + cash) - $10M base               (capital recovered
#                                                                    beyond the base)
#   Total Return   = (Total value - base) / base
#
# This decomposition is BLOTTER-FREE on purpose. The previous model defined
# realized = (snapshot cost basis) - (blotter net-invested), which fabricated
# profit whenever the broker's shares disagreed with the blotter — e.g. XLE
# (105 sh, zero recorded trades) booked its entire cost basis as "realized"
# (the XLE anti-pattern, Rule 2). Undocumented adds are buys: they raise cost
# basis only, never P/L.
CAPITAL = BASELINE * SCALE                          # 10M real x1.8 = 18M (scaled display)
GBMF2_CASH = (BROKER_CASH or 0.0) * SCALE           # equity-sleeve cash, scaled to match
_unr_now   = float(tot_val - tot_cost)              # unrealized = MV - cost basis
_real_now  = float(tot_cost + GBMF2_CASH - CAPITAL) # realized = (cost + cash) - base
_total_now = float(tot_val + GBMF2_CASH)            # total value = MV + cash sleeve
_idle_now  = GBMF2_CASH
print(f"  CANONICAL capital {CAPITAL:,.0f} | cost {tot_cost:,.0f} | cash {GBMF2_CASH:,.0f} | "
      f"MV {tot_val:,.0f} | realized {_real_now:,.0f} | unrealized {_unr_now:,.0f} | "
      f"total {_total_now:,.0f} | return {(_total_now/CAPITAL-1)*100:+.2f}%")

# historical curve: keep the blotter-driven daily SHAPE, but pin the live endpoint
# to the canonical realized/total so the chart agrees with the headline KPI.
try:
    _blf = pd.read_csv(f"{DATA}/blotter_clean.csv", parse_dates=["date"])
    _blf["flow"] = _blf["shares"] * _blf["price"] * _blf["side"].map({"buy": 1.0, "sell": -1.0})
    _ninv = (_blf.groupby("date")["flow"].sum().sort_index().cumsum() * SCALE)
    _ninv = _ninv.reindex(ts.index, method="ffill").fillna(0.0)
except Exception as _e:
    print(f"  capital model: blotter unavailable ({_e})"); _ninv = pd.Series(0.0, index=ts.index)
_real_raw = ts["balance"] - _ninv                   # blotter-residual realized — SHAPE only
_pin = _real_now - float(_real_raw.iloc[-1])        # shift the whole series so endpoint = canonical
_real_series = _real_raw + _pin
_unr_series = (ts["equity"] - ts["balance"]).astype(float)
_unr_series.iloc[-1] = _unr_now                     # canonical unrealized at the live point
ts["realized_pool"] = CAPITAL + _real_series
ts["total"] = ts["realized_pool"] + _unr_series
ts.iloc[-1, ts.columns.get_loc("total")] = _total_now
ts.iloc[-1, ts.columns.get_loc("realized_pool")] = CAPITAL + _real_now
dates = ts.index

# ---------- charts ----------
# 1. total value (holdings + recycled cash) vs the fixed capital pool
f1 = go.Figure()
f1.add_scatter(x=dates, y=ts["total"], mode="lines", name="Total value (realized + unrealized)",
               line=dict(color=BLUE, width=2.6))
f1.add_scatter(x=dates, y=ts["realized_pool"], mode="lines", name="Capital + realized (locked in)",
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
                   marker=dict(color=_col, symbol=_sym, size=9, line=dict(width=1, color="white")),
                   text=_txt, hoverinfo="text")
f1.add_hline(y=CAPITAL, line=dict(color=INK, width=1, dash="dot"),
             annotation_text="Capital (10M, recycled)", annotation_position="bottom right")
f1.update_layout(title="Total value \u2014 realized (locked in) + unrealized vs 10M capital (daily, scaled)",
                 yaxis_title="MXN (scaled)", xaxis_title="date",
                 legend=dict(orientation="h", y=-0.18))

# 2. per-holding return vs portfolio (currency-independent)
lat = latest.sort_values("ret")
colors = [GREEN if r >= 0 else RED for r in lat["ret"]]
f2 = go.Figure(go.Bar(x=lat["ret"] * 100, y=lat["ticker"], orientation="h",
                      marker_color=colors,
                      text=[f"{r*100:+.2f}%" for r in lat["ret"]],
                      textposition="outside"))
f2.add_vline(x=port_ret * 100, line=dict(color=INK, dash="dash"),
             annotation_text=f"portfolio {port_ret*100:+.2f}%")
f2.update_layout(title="Holding return vs the portfolio (dashed = portfolio total)",
                 xaxis_title="return since cost (%)")

# 3. allocation (currency-independent)
al = latest.sort_values("weight")
f3 = go.Figure(go.Bar(x=al["weight"] * 100, y=al["ticker"], orientation="h",
                      marker_color=BLUE,
                      text=[f"{w*100:.2f}%" for w in al["weight"]],
                      textposition="outside"))
f3.update_layout(title="Current allocation by holding",
                 xaxis_title="% of stock portfolio")

# ---------- holdings table ----------
rows = ""
for _, r in latest.iterrows():
    rc = "pos" if r["ret"] >= 0 else "neg"
    pc = "pos" if r["pm"] >= 0 else "neg"
    rows += (f"<tr><td>{r['ticker']}</td><td>{fmt_sh(r['shares'])}</td>"
             f"<td>{cval(r['Costo promedio'], 2)}</td>"
             f"<td>{cval(r['Precio mercado'], 2)}</td>"
             f"<td>{cval(r['value'])}</td><td>{r['weight']*100:.2f}%</td>"
             f"<td class='{rc}'>{r['ret']*100:+.2f}%</td>"
             f"<td class='{pc}'>{cval(r['pm'], signed=True)}</td></tr>")

# ---------- metrics (recycled capital; realized & unrealized kept separate) ----------
_pnl_now = _real_now + _unr_now
SNAP = [("Total Value", cval(_total_now)),
        ("Realized P / L", cval(_real_now, signed=True)),
        ("Unrealized P / L", cval(_unr_now, signed=True)),
        ("Total P / L", cval(_pnl_now, signed=True)),
        ("Total Return", f"{(_total_now/CAPITAL-1)*100:+.2f}%"),
        ("Live Priced", asof)]
snap = "".join(
    f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
    for k, v in SNAP)

# ---------- currency-toggle JavaScript ----------
def _arr(s): return ",".join(f"{v:.0f}" for v in s)
def _mk_y(side):
    _s = _td[_td["side"] == side] if len(_td) else _td
    _o = []
    for _d in (_s["date"] if len(_s) else []):
        _ss = ts["total"][ts.index <= _d]
        _o.append(float(_ss.iloc[-1]) if len(_ss) else 0.0)
    return _o
_totm = _arr(ts["total"]); _totu = _arr(ts["total"] / RATE)
_ream = _arr(ts["realized_pool"]); _reau = _arr(ts["realized_pool"] / RATE)
_by = _mk_y("buy"); _sy = _mk_y("sell")
_bym = ",".join(f"{v:.0f}" for v in _by); _byu = ",".join(f"{v/RATE:.0f}" for v in _by)
_sym2 = ",".join(f"{v:.0f}" for v in _sy); _syu = ",".join(f"{v/RATE:.0f}" for v in _sy)
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
    Plotly.relayout(d,{'yaxis.title.text':c.toUpperCase()+' (scaled)'});
  }
  var fxBtn=document.querySelector('#fxa-ccy button[data-v="'+c.toUpperCase()+'"]');
  if(fxBtn) fxBtn.click();
}
document.addEventListener('DOMContentLoaded',function(){setCurrency('mxn');});
</script>
""".replace("__TOTM__", _totm).replace("__TOTU__", _totu).replace("__REAM__", _ream).replace("__REAU__", _reau).replace("__BYM__", _bym).replace("__BYU__", _byu).replace("__SYM__", _sym2).replace("__SYU__", _syu)

PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Portfolio Tracker</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Stock Portfolio Tracker</h1>
<p class="lede">A live view of the GBM equity book &mdash; every position
measured against its cost basis and against the portfolio as a whole.
Figures convert between Mexican pesos and US dollars at the current rate.</p>
<p class="asof">As of {asof} &middot; GBM equity holdings &middot;
USD/MXN {RATE:.4f}</p>
</div></section>
<main class="container">
<div class="scaled-note"><b>Display note:</b> figures are scaled by a fixed
constant for confidentiality &mdash; magnitudes are illustrative, not the real
amounts; prices, returns and weights are exact. Positions, cost basis and the
GBMF2 cash sleeve come from the broker statement (source of truth), re-priced
live. <b>Accounting:</b> the equity book is measured against a fixed $10M&nbsp;MXN
base (recycled capital); Total&nbsp;Value = holdings market value + GBMF2 cash
sleeve; Unrealized&nbsp;P/L = market value &minus; cost basis; Realized&nbsp;P/L =
(cost basis + cash) &minus; base. Undocumented share adds are treated as buys
(they raise cost basis, never P/L). FX positions and non-GBM bank cash are
excluded.</div>
<section class="block"><h2>Snapshot</h2>
<div class="ccy-toggle">
<button data-cur="mxn" class="active" onclick="setCurrency('mxn')">MXN</button>
<button data-cur="usd" onclick="setCurrency('usd')">USD</button></div>
<p class="note">Currency: <b id="ccy-label">MXN</b> &mdash; returns and weights
read the same in either currency. Total Return is measured against the recycled
$10M&nbsp;MXN base and includes the GBMF2 cash sleeve ({cval(GBMF2_CASH)}).
Definitions in the <a href="glossary.html">Glossary</a>.</p>
<div class="metrics" style="grid-template-columns:repeat(6,1fr)">{snap}</div></section>
<section class="block"><h2>Total Value vs Capital</h2>
<div class="tile chart"><div class="ch">{div(f1, "pf-value")}</div></div></section>
{fxa_section}
<script>(function(){{var b=document.getElementById('fxa-ccy');
if(b&&b.parentElement)b.parentElement.style.display='none';}})();</script>
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
