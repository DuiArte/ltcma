"""Build the GBM stock-portfolio tracker page -> docs/portfolio.html.

Source: 'Copy of Carteras DBE 2.xlsx' sheet 'DBE Acciones' (GBM stock holdings
only -- FX positions and non-GBM bank cash are excluded by design). Source Excel
is never modified. A MXN / USD currency toggle converts at the latest USDMXN rate.
Refresh: update the Excel, re-run this script.

CONFIDENTIALITY MODEL
    SCALE is applied to SHARE COUNTS, once, at the source (see `latest["shares"]`).
    Every downstream formula then stays internally consistent -- value = shares*price,
    P/L = value - cost, weights and percentages unchanged -- while the displayed peso
    magnitudes are not the real amounts.

    What is public and exact, by design: per-share prices, % returns, weights.
    What is scaled: every peso aggregate (cost, market value, P/L).

    Two rules follow, both enforced by the guard block just before the write:
      1. Scale ONCE, at the source. Never `*SCALE` inside an f-string -- the sibling
         attribute in that same f-string will still be raw. That exact mistake put the
         real book in the `data-s` sort attributes for three weeks (c5ae501 -> eb2b196).
         Attributes (`data-s`, `data-mxn`, title, embedded JSON) are public surface.
      2. Never name the factor on the page -- that hands the reader the inverse. Write
         "scaled by a fixed constant".
    NOTE: this repo is public, so `SCALE` is readable in source regardless. The scaling
    deters casual reading; it is not a security boundary. Do not publish anything whose
    exposure would actually matter.

COST BASIS AND REALIZED P&L -- the private ledger sidecar is authoritative
    `real_numbers/realized_ledger_*.json` (never committed) carries a moving-average,
    ALL-IN (fee-inclusive), split-adjusted walk of every fill, reconciled to the broker's
    own `Imp X Cto` to the cent. The build FAILS if it is absent: the in-script
    approximations it replaced were materially wrong, and shipping those silently is
    worse than not building.

    Cost basis is all-in everywhere -- realized and unrealized share one convention. The
    broker's `Costo promedio` is gross of fees and understates the outlay. Held cost is
    per-ticker over the 22 OPEN positions (not the 9 realized rows -- AMAT closed out).
    Assert on the full-precision values; the 2-dp figures sum a cent high.

    Realized rows are split SEGMENTS, not tickers: a pre-split fill cannot share a
    per-share average with post-split ones. Interaction folds into Stock, so Stock + FX
    == Total and (AvgSell - AvgCost) x Shares reproduces it. Both are asserted.

CROSS-CHECK MERGE (`_SELL_SRC` / `_BUY_SRC`)
    An independent merge of the raw GBM "Historial de Transacciones" exports. It is NOT
    the source of any published number -- it exists so two separate merges of the same
    CSVs must agree on the fill set, and as a freshness canary against the sidecar's
    `as_of`. Neither merge is trustworthy alone; the agreement is.

    GBM re-exports the same fills under shifted value dates, so exports OVERLAP and
    CONTRADICT each other -- a glob+union silently double-counts. Each export owns a
    disjoint calendar slice. Genuine same-second partial fills exist, so no tuple-dedup
    is safe. Guards abort on a fill claimed twice, on the same ticker/shares/price two
    dates <=5 days apart, and on any fill-count disagreement with the sidecar.

RETURN BANNERS
    Realized / Unrealized / Combined, each against the cost basis it earned on. That
    makes Combined the cost-weighted blend of the other two; an assert enforces it.
    Ratios are scale-invariant, so these publish the REAL returns.
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

import paths
FXA = paths.cuser("Downloads", "fx_attribution_2026-05-26", "code")  # lot-history DATA cache only
# (legacy fxa_section/make_section renderer removed 2026-06-15: the FX Attribution
#  panel is now rebuilt inline from the same cost-basis source as the holdings table.)

XLSX = paths.cuser("Downloads", "Copy of Carteras DBE 2.xlsx")
DATA = paths.DATA_S
DOCS = paths.DOCS_S
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
# Snapshot search spans BOTH the raw Downloads drop AND the canonical archive
# (Rule 4: Documents\GBM_Account_Archive\portfolio_snapshots is where ingested
# snapshots live; new ones may exist ONLY there). Bug fixed 2026-06-10: globbing
# Downloads alone left the live site marking Jun-1 positions while Jun-3/Jun-5
# snapshots sat in the archive (stale shares, missing buys).
_SNAP_DIRS = (paths.cuser("Downloads"),
              paths.cuser("Documents", "GBM_Account_Archive", "portfolio_snapshots"))
def load_broker_snapshot():
    def _ts(p):                                          # the 13-digit Unix-ms stamp, ignoring " (1)" etc.
        m = _re2.search(r"(\d{13})", os.path.basename(p))
        return int(m.group(1)) if m else 0
    files = []
    for d in _SNAP_DIRS:
        files += _g2.glob(d + "/GBM_Homebroker_Detalle_de_Portafolio_*.csv")
    # ms-stamped originals only: the archive's date-alias copies (_morning/_close)
    # duplicate ms-stamped files, and only the ms stamp orders reliably.
    files = sorted({f for f in files if _ts(f)}, key=_ts)
    if not files:
        return None, None, None

    def _parse(path):
        sect = None; eq = []; cash = None; efec24 = 0.0
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for parts in _csv.reader(fh):
                if not parts:
                    continue
                if len(parts) == 1:                     # section header row
                    sect = parts[0].strip(); continue
                if parts[0].strip() == "Emisora/Fondo":  # column header row
                    continue
                name = parts[0].replace("*", "").strip()
                if sect in ("Mercado de Capitales Nacional", "Mercado de Capitales Global (SIC)"):
                    eq.append({"ticker": name, "Títulos": _bmoney(parts[1]),
                               "Costo promedio": _bmoney(parts[2]),
                               "Precio mercado": _bmoney(parts[3]),
                               "valor_broker": _bmoney(parts[5]), "imp_cto_broker": _bmoney(parts[9])})
                elif name == "GBMF2 BM":
                    cash = _bmoney(parts[5])            # Valor mercado of the cash sleeve
                elif name.upper().startswith("EFEC") and "24" in name:
                    efec24 = _bmoney(parts[5])          # T+1 settlement lag (negative = unsettled buys)
        return eq, cash, efec24

    # newest-first; accept the first snapshot that actually carries equity rows
    # (funds/cash-only exports must not blank the holdings table)
    for path in reversed(files):
        try:
            eq, cash, efec24 = _parse(path)
        except OSError:
            continue
        if eq:
            snap_date = pd.to_datetime(_ts(path), unit="ms")
            return pd.DataFrame(eq), cash, efec24, snap_date
    return None, None, 0.0, None

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
for _f in sorted(_glob.glob(paths.cuser("Downloads") + "/GBM Transacciones Liquidacion*.csv")):
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
# screen the DAILY price series for isolated bad prints (e.g. the unadjusted split
# ticks VGT/VUG 2026-04-21, ret -86%/-82%) that the snapshot-row anomaly filter does
# NOT reach: a one-day spike/dip that reverts is replaced with the prior valid price,
# so it can never inject a phantom dip-and-recover into the equity curve. A genuine
# split or trend shifts the level permanently (the next day does NOT revert) and is
# left untouched.
def _despike(s, tol=0.35):
    v = s.astype(float).copy(); prev = v.shift(1); nxt = v.shift(-1)
    isolated = ((v - prev) * (v - nxt)) > 0                  # local extremum (above/below both)
    bad = isolated & ((v / prev - 1).abs() > tol) & ((v / nxt - 1).abs() > tol)
    v[bad.fillna(False)] = float("nan")
    return v.ffill()
if not _px.empty:
    _px = _px.apply(_despike).ffill()

# split reconciliation: a BMV (.MX) split re-bases the Yahoo price on the split day,
# but the Excel snapshot share count only catches up at the NEXT snapshot (e.g. VGT 8:1
# and VUG 6:1: price re-based 2026-04-20, shares not until 04-24). In that gap the curve
# multiplied pre-split shares by post-split prices and the MV cratered ~8x then snapped
# back. Put price, shares and avg-cost on one continuous (post-split) basis -- but ONLY
# when a price re-basing is CONFIRMED by a matching reciprocal share jump, so a genuine
# one-day crash (price down, shares unchanged) is left completely alone.
def _cumfac(s, lo=0.55, hi=1.80):
    v = s.astype(float); fac = [1.0] * len(v); f = 1.0
    for i in range(len(v) - 1, 0, -1):
        a, b = v.iloc[i - 1], v.iloc[i]
        if pd.notna(a) and pd.notna(b) and a > 0 and b > 0:
            r = b / a
            if r < lo or r > hi:
                f *= r
        fac[i - 1] = f
    return pd.Series(fac, index=v.index)
for _tk in _pos.columns:
    _yt = TICKER_MAP.get(_tk)
    if not (_yt and _yt in _px.columns) or _tk not in _acd.columns:
        continue
    # The split signal is the AVERAGE COST series: it only re-bases at a split (a sell
    # leaves avg cost unchanged; a buy nudges it). Share counts are NOT a reliable signal
    # -- a routine half-position sell (816->416) looks just like a 1:2 split. Confirm the
    # split by requiring the Yahoo PRICE to re-base by the SAME factor (a genuine crash
    # moves price but not avg cost, so price/cost factors disagree -> left untouched).
    _af = _cumfac(_acd[_tk]); _pf = _cumfac(_px[_yt])
    _af0, _pf0 = float(_af.iloc[0]), float(_pf.iloc[0])
    if abs(_af0 - 1) > 0.1 and abs(_pf0 - 1) > 0.1 and abs(_pf0 / _af0 - 1) < 0.15:
        _px[_yt]  = _px[_yt]  * _pf      # prices -> continuous post-split basis
        _acd[_tk] = _acd[_tk] * _af      # avg cost -> continuous post-split basis
        _pos[_tk] = _pos[_tk] / _af      # shares move inverse to avg cost (cost invariant)
        print(f"  split-reconciled {_tk}: factor x{_af0:.4f} (price x{_pf0:.4f})")

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
_bdf, BROKER_CASH, BROKER_EFEC24, _bsnap = load_broker_snapshot()

# ---------- external-flow adjustment for the $10M-recycled-base KPIs ----------
# Standing rule (jun03_to_jun05.md, Rules 1-6): deposits into the GBMF2 cash
# sleeve are CAPITAL ADDITIONS, never P&L. The raw F2 balance after the
# 2026-06-05 +$19M external deposit would otherwise read as fabricated
# "realized" in  realized = cost + cash - base.  The recycled-book cash is:
#   F2 balance + EFEC 24HRS (T+1 settlement lag, negative = buys not yet
#   drawn from F2) - cumulative external deposits dated <= snapshot date.
# Ledger lives OUTSIDE this public repo (real peso amounts are private).
# Whether the $10M base itself should grow by these deposits is an open
# Carlos decision; until then external flows are excluded, not re-based.
_EXT_FLOWS = paths.cuser("Documents", "CarlosDuarteWebsite", "real_numbers", "external_flows.json")
_ext_dep = 0.0
try:
    _ef = json.loads(Path(_EXT_FLOWS).read_text())
    for _f in _ef.get("flows", []):
        if _bsnap is None or pd.to_datetime(_f["date"]) <= _bsnap:
            _ext_dep += float(_f["amount_mxn"])
    if _ext_dep:
        print(f"  external-flows ledger: excluding {_ext_dep:,.2f} MXN of deposits "
              f"from the recycled cash sleeve ({len(_ef.get('flows', []))} entries)")
except FileNotFoundError:
    print(f"  (warn: no external-flows ledger at {_EXT_FLOWS} — raw F2 balance feeds KPIs; "
          f"a deposit would read as fake realized P/L)")
except Exception as _efe:
    print(f"  (warn: external-flows ledger unreadable ({_efe}) — raw F2 balance feeds KPIs)")
BROKER_CASH_RECYCLED = (BROKER_CASH or 0.0) + (BROKER_EFEC24 or 0.0) - _ext_dep
if _bdf is None or _bdf.empty:
    raise SystemExit("FATAL: no GBM Detalle de Portafolio CSV found in Downloads — cannot build canonical snapshot")
# ---------- private ledger sidecar: realized P&L + all-in held cost basis ----------
# Never committed (CarlosDuarteWebsite is not a git tree). Fail rather than fall back:
# the in-script approximations it replaces are materially wrong, and silently shipping
# them is worse than not building. Realized-side checks live with the realized section.
import glob as _rg
import re as _re_tk
def _norm_ticker(n):
    """Broker name -> ledger key: 'MELI N' -> MELI, 'GMEXICO B' -> GMEXICOB."""
    return _re_tk.sub(r"\s+[*N]$", "", str(n).strip()).replace(" ", "")
_RLDIR = paths.cuser("Documents", "CarlosDuarteWebsite", "real_numbers")
_rlf = sorted(_rg.glob(os.path.join(_RLDIR, "realized_ledger_*.json")))
if not _rlf:
    raise SystemExit(f"realized ledger sidecar missing under {_RLDIR} -- refusing to "
                     "publish the approximate snapshot-basis figures")
_rl = json.loads(Path(_rlf[-1]).read_text(encoding="utf-8"))

latest = _bdf.copy()
latest["shares"] = latest["Títulos"] * SCALE

# Cost basis is ALL-IN (includes buy-side commission + tax). The broker's `Costo
# promedio` is gross of fees, so shares x Costo promedio understates what was actually
# paid. Assert on the full-precision values: the 2-dp per-ticker figures sum a cent high.
_held = _rl["per_ticker_held_allin_cost_mxn"]
assert abs(sum(_held.values()) - _rl["equity_allin_cost_basis_mxn_exact"]) < 1e-6, \
    "held all-in cost does not sum to the sidecar total"
if not (len(_held) == _rl["held_positions_count"] == len(latest)):
    raise SystemExit(f"held positions disagree: sidecar {len(_held)} / "
                     f"declared {_rl['held_positions_count']} / snapshot {len(latest)}")
_kmap = latest["ticker"].map(_norm_ticker)
_miss, _extra = sorted(set(_kmap) - set(_held)), sorted(set(_held) - set(_kmap))
if _miss or _extra:
    raise SystemExit(f"held-cost ticker mismatch -- snapshot-only {_miss}, sidecar-only {_extra}")
latest["cost"] = _kmap.map(_held).astype(float) * SCALE
# Keep the rendered identity Cost = Avg Cost x Shares by carrying the per-share all-in.
latest["Costo promedio"] = latest["cost"] / latest["shares"]
print(f"  held cost: all-in basis from sidecar ({len(_held)} positions), "
      f"buy fees {_rl['held_cost_checks']['sum_buy_fees']:,.2f} over broker gross")

latest["value"] = latest["shares"] * latest["Precio mercado"]   # broker mark; live-overridden below
latest["pm"] = latest["value"] - latest["cost"]
latest["ret"] = latest["pm"] / latest["cost"]
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
        latest["ret"] = latest["pm"] / latest["cost"]
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

# ---------- reconcile FX-attribution rows against the live broker snapshot ----------
# attribution_data.json is frozen at its build date and only carries the tickers held
# then. Holdings, by contrast, is rebuilt live from the latest GBM "Detalle de
# Portafolio", so a position opened after the cache was built (e.g. ASTS) silently
# never reaches this panel, and share-count changes (e.g. GOOGL/MSFT adds) go stale.
# Rather than hand-maintain a ticker list, derive inclusion dynamically: every holding
# in the broker snapshot gets an attribution row, with shares + open MXN cost taken
# straight from the broker file. Tickers with no cached lot history inherit the
# portfolio-blended buy-FX (the same proxy run_attribution.py uses for no-tx names).
# The per-row recompute loop below then fills the USD/FX/interaction buckets live.
INV_POS = {v: k for k, v in POS_KEY.items()}           # broker name -> cache ticker
PORT_XBUY = float(ATTR.get("port_xbuy") or fx_live)
_attr_by_tk = {r["ticker"]: r for r in ATTR["rows"]}
for _, b in _bdf.iterrows():
    bname = str(b["ticker"]).strip()                   # e.g. "ASTS", "GOOGL", "GMEXICO B"
    if bname not in TICKER_MAP:
        continue                                       # unmapped/cash sleeve — can't price
    ctk = INV_POS.get(bname, bname)                    # cache-style ticker, e.g. "GMEXICOB"
    shares_raw = float(b["Títulos"])
    mxn_cost_raw = float(b["imp_cto_broker"])          # Imp X Cto. = Títulos x Costo promedio
    native = ctk == "GMEXICOB"                          # only GMEXICO B is peso-native (no FX leg)
    row = _attr_by_tk.get(ctk)
    if row is None:                                    # position opened after the cache was built
        row = dict(ticker=ctk, shares=shares_raw, method="approx_no_tx",
                   native=native, approx=True,
                   realized=dict(stock=0.0, fx=0.0, interaction=0.0, pnl=0.0,
                                 mxn_cost=0.0, x_buy=None, x_val=None),
                   unrealized=dict(stock=0.0, fx=0.0, interaction=0.0, pnl=0.0,
                                   mxn_cost=mxn_cost_raw,
                                   x_buy=(1.0 if native else PORT_XBUY),
                                   x_val=float(fx_live)))
        ATTR["rows"].append(row)
        _attr_by_tk[ctk] = row
        print(f"  FXA: added missing holding {ctk} "
              f"({shares_raw:g} sh, MXN cost {mxn_cost_raw:,.0f})")
    elif abs(float(row.get("shares") or 0.0) - shares_raw) > 1e-6:   # share count drifted
        print(f"  FXA: refreshed {ctk} shares {row['shares']:g} -> {shares_raw:g}")
        row["shares"] = shares_raw
        row["unrealized"]["mxn_cost"] = mxn_cost_raw

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

# ---------- per-holding Stock/FX decomposition for the cost-basis table ----------
# Reuse the canonical FX-attribution unrealized buckets (Stock + FX + Interaction,
# computed above) as the holdings table's Stock/FX columns. Interaction is folded
# into Stock (the table shows two legs + total, matching the offline dashboard).
# ATTR values are REAL (unscaled); the holdings table is x1.8-scaled, so each leg
# is scaled here. Stock+FX reconciles exactly to each row's P/M.
DECOMP = {}
for r in ATTR["rows"]:
    btk = POS_KEY.get(r["ticker"], r["ticker"])          # cache ticker -> broker name
    u = r["unrealized"]
    DECOMP[btk] = dict(fx=float(u.get("fx") or 0.0) * SCALE,
                       inter=float(u.get("interaction") or 0.0) * SCALE,
                       native=bool(r.get("native")), approx=bool(r.get("approx")))

# FX is the canonical decomposed leg (from the attribution buckets); Stock is the
# residual Total − FX, so each row and the total reconcile to the cent (absorbs the
# tiny Imp×Cto vs shares×avg-cost broker rounding into Stock, where it is negligible).
fx_tot = sum(d["fx"] for tk, d in DECOMP.items()
             if not d["native"] and tk in set(latest["ticker"]))
stock_tot = float(tot_val - tot_cost) - fx_tot
stock_pct = stock_tot / tot_cost * 100.0 if tot_cost else 0.0
fx_pct    = fx_tot / tot_cost * 100.0 if tot_cost else 0.0
print(f"  decomposition: stock {stock_tot:,.0f} ({stock_pct:+.2f}%) | "
      f"fx {fx_tot:,.0f} ({fx_pct:+.2f}%) | reconcile {stock_tot+fx_tot:,.0f} vs P/L {tot_val-tot_cost:,.0f}")

# ---------- FX Attribution panel: rebuilt from the SAME source as the holdings table ----------
# The legacy ms.build_section() renderer was scrapped (2026-06-15 coherence fix): it
# carried its own Realized/Unrealized + "Normal/FX-Impact" framing, a frozen lot cache,
# and a separate currency toggle that fought the new cost-basis model. This panel is
# the canonical 3-way split (Stock + FX + Interaction) of the SAME unrealized P/L shown
# in the Holdings table, so it reconciles to the cent and uses the page's cval() MXN/USD
# toggle and x1.8 scaling uniformly. Stock = Total − FX − Interaction (residual absorbs
# the negligible Imp×Cto-vs-shares×avg-cost broker rounding).
def _cl(v): return "pos" if v >= 0 else "neg"
def build_fxa():
    body = ""
    T_st = T_fx = T_in = 0.0
    for _, r in latest.iterrows():
        tk = r["ticker"]; total = float(r["pm"]); cost = float(r["cost"]) or 1.0
        d = DECOMP.get(tk); is_usd = bool(d) and not d["native"]
        fx = d["fx"] if is_usd else 0.0
        inter = d["inter"] if is_usd else 0.0
        stock = total - fx - inter
        T_st += stock; T_fx += fx; T_in += inter
        appx = " <span class='muted' title='purchase FX estimated (no trade ledger)'>&asymp;</span>" if (d and d.get("approx")) else ""
        em = "<span class='muted'>&mdash;</span>"
        fxc  = f"<span class='{_cl(fx)}'>{cval(fx, signed=True)}</span>" if is_usd else em
        inc  = f"<span class='{_cl(inter)}'>{cval(inter, signed=True)}</span>" if is_usd else em
        body += (f"<tr><td data-s='{tk}'>{tk}{appx}</td>"
                 f"<td data-s='{stock:.2f}' class='n {_cl(stock)}'>{cval(stock, signed=True)}</td>"
                 f"<td data-s='{fx:.2f}' class='n'>{fxc}</td>"
                 f"<td data-s='{inter:.2f}' class='n'>{inc}</td>"
                 f"<td data-s='{total:.2f}' class='n {_cl(total)}'>{cval(total, signed=True)}</td>"
                 f"<td data-s='{total/cost:.6f}' class='n {_cl(total)}'>{total/cost*100:+.2f}%</td></tr>")
    g_tot = T_st + T_fx + T_in
    foot = (f"<tr class='fxa-tot'><td>Portfolio (unrealized)</td>"
            f"<td class='n {_cl(T_st)}'>{cval(T_st, signed=True)}</td>"
            f"<td class='n {_cl(T_fx)}'>{cval(T_fx, signed=True)}</td>"
            f"<td class='n {_cl(T_in)}'>{cval(T_in, signed=True)}</td>"
            f"<td class='n {_cl(g_tot)}'>{cval(g_tot, signed=True)}</td>"
            f"<td class='n {_cl(g_tot)}'>{g_tot/tot_cost*100:+.2f}%</td></tr>")
    return f"""<section class="block" id="fxa-root"><h2>FX Attribution</h2>
<style>#fxa-root table.ptable .n{{text-align:right;font-variant-numeric:tabular-nums}}
#fxa-root tr.fxa-tot td{{font-weight:700;border-top:2px solid #d8d5cf;background:#fbfaf8}}</style>
<p class="note">For each US-dollar holding the unrealized peso P/L splits into
<b>Stock</b> (US price move at the buy-date exchange rate), <b>FX</b> (the peso's
move on the original cost) and a small <b>Interaction</b> cross term. The three sum
exactly to Total = market value &minus; cost &mdash; the same Total (and the same
FX) as the Holdings table, which folds Interaction into its Stock column. Peso-native
holdings (GMEXICO&nbsp;B) carry no FX leg. Values follow the currency toggle and are
scaled; percentages are exact.
<span class="muted">&asymp; = purchase FX estimated (no trade ticket).</span></p>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto;-webkit-overflow-scrolling:touch">
<table class="ptable" style="min-width:560px"><thead><tr>
<th>Holding</th><th>Stock P/L</th><th>FX P/L</th><th>Interaction</th><th>Total P/L</th><th>Return</th>
</tr></thead><tbody>{body}{foot}</tbody></table></div>
<p class="note" style="margin-top:.8rem">Net FX impact this period: <b>{cval(T_fx, signed=True)}</b>
MXN ({T_fx/tot_cost*100:+.2f}% of cost) &mdash; a stronger peso is a drag on dollar holdings.</p>
</section>"""
fxa_section = build_fxa()

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
# RETIRED 2026-06-15 (Carlos pivot). Everything from here through the sidecar block is
# computed and then THROWN AWAY by the "curve re-frame" below, which reassigns
# ts["total"] / ts["realized_pool"] to market value / cost basis. None of it reaches the
# page. Kept only so the recycled-base curve can be revived.
#
# It is also WRONG, and it prints numbers alarming enough to send a reader chasing a bug
# that does not exist on the site (it did exactly that, 2026-07-09). Two defects:
#   1. BROKER_CASH_RECYCLED = F2 + EFEC24 - deposits assumes the deposit still SITS in
#      F2. The 2026-06-05 external deposit was redeployed into GBMGUBL/GBMDOL, so
#      subtracting it removes the money twice -> the cash sleeve goes NEGATIVE, and
#      _real_now then reads as a large phantom "realized loss".
#   2. tot_cost is shares x `Costo promedio`, which is GROSS of fees. The identity
#      realized = cost + cash - base needs the ALL-IN cost basis.
# Before reviving, take both from the private ledger sidecar (realized_ledger_*.json:
# `cash_recycled_mxn`, `equity_allin_cost_basis_mxn`), whose flow-immune definition never
# touches F2 at all:  cash = BASELINE - all_in_buys + net_sells.
GBMF2_CASH = BROKER_CASH_RECYCLED * SCALE           # equity-sleeve cash, scaled to match
_unr_now   = float(tot_val - tot_cost)              # unrealized = MV - cost basis
_real_now  = float(tot_cost + GBMF2_CASH - CAPITAL) # BROKEN (see above) -- unused
_total_now = float(tot_val + GBMF2_CASH)            # BROKEN (see above) -- unused
_idle_now  = GBMF2_CASH
print(f"  [retired base-curve block, not published] cost {tot_cost:,.0f} | "
      f"MV {tot_val:,.0f} | unrealized {_unr_now:,.0f}"
      + ("  ** cash sleeve negative: F2-minus-deposits is broken, see comment **"
         if BROKER_CASH_RECYCLED < 0 else ""))

# historical curve: BLOTTER-FREE, flow-immune decomposition (fixes the XLE anti-pattern).
# The recycled-$10M base splits into deployed cost basis + idle GBMF2 cash, so the cash
# sleeve at any date is the residual  cash_t = CAPITAL - cost_basis_t. Total book value is
# therefore  equity MV + cash sleeve = CAPITAL + (MV - cost) + realized.  A buy (cost up,
# MV up) and an UNDOCUMENTED add (cost up, MV up) both net to ZERO on the total line, so
# reallocations between the cash and equity sleeves no longer read as +/-20-40% phantom
# "performance" swings. Realized P/L is the snapshot position-drops valued at Yahoo
# (_cumreal), NEVER the blotter: it was the blotter-vs-snapshot disagreement (shares the
# broker holds with no recorded trade) that injected the spurious jumps into the old curve.
# The endpoint is pinned to the canonical broker KPIs so the chart matches the headline.
_unr_series  = _unreal.reindex(ts.index).ffill().fillna(0.0).astype(float)    # MV - cost basis, daily
_real_series = _cumreal.reindex(ts.index).ffill().fillna(0.0).astype(float)   # realized from snapshot drops
_unr_series.iloc[-1]  = _unr_now                    # canonical unrealized at the live point
_real_series.iloc[-1] = _real_now                   # canonical realized   at the live point
ts["realized_pool"] = CAPITAL + _real_series        # capital + locked-in realized
ts["total"] = ts["realized_pool"] + _unr_series     # total book value (flow-immune)
dates = ts.index

# ---------- authoritative offline sidecar override (broker-book curve) ----------
# The private clean-rebuilder (real_curve_generator.py) emits a per-date JSON sidecar
# carrying the LEDGER-reconciled, flow-immune equity-only curve of the REAL broker book
# (equity_only_mxn = base + realized_pnl_cum + unrealized_pnl). When that sidecar is
# present, it REPLACES the Excel/Yahoo-derived curve above so the public chart matches
# the offline Portfolio_REAL_equity_only curve to the cent, re-scaled by the same x1.8
# obfuscation constant used everywhere else on this page. Falls back GRACEFULLY to the
# computed curve if the sidecar is absent or unreadable (the daily refresh never breaks).
# The headline KPI tiles stay live-broker-priced (untouched) — the snapshot-spine curve
# and the daily KPI carry an inherent ~2pt price-source gap by design.
_SIDECAR = paths.cuser("Documents", "CarlosDuarteWebsite", "real_numbers", "real_curve_series.json")
try:
    _sc = json.loads(Path(_SIDECAR).read_text())
    _scpts = _sc.get("points", [])
    if _scpts:
        _base = float(_sc.get("base_mxn", BASELINE))
        _sidx = pd.to_datetime([p["date"] for p in _scpts])
        _stot = pd.Series([float(p["equity_only_mxn"]) for p in _scpts], index=_sidx).sort_index()
        _srea = pd.Series([_base + float(p["realized_pnl_cum"]) for p in _scpts], index=_sidx).sort_index()
        # forward-fill each snapshot value across the daily grid, back-fill the head, scale x1.8
        ts["total"] = (_stot.reindex(ts.index, method="ffill").bfill() * SCALE)
        ts["realized_pool"] = (_srea.reindex(ts.index, method="ffill").bfill() * SCALE)
        print(f"  curve: read offline sidecar (as_of {_sc.get('as_of')}, {len(_scpts)} pts) "
              f"-> DISCARDED by the curve re-frame below (retired 2026-06-15)")
    else:
        print("  curve: sidecar present but has no points -> keeping computed curve")
except FileNotFoundError:
    print(f"  curve: no sidecar ({_SIDECAR}) -> keeping computed (Excel/Yahoo) curve")
except Exception as _scerr:
    print(f"  curve: sidecar read failed ({_scerr}) -> keeping computed curve")

# ---------- curve re-frame: Market Value vs Cost Basis (no fixed base) ----------
# Carlos pivot 2026-06-15: drop the $10M/$18M recycled-base curve entirely. The two
# lines are now the daily equity market value and the daily invested cost basis; the
# gap between them is unrealized P&L. This overrides the base/sidecar series computed
# upstream (left in place but unused) so the chart matches the cost-basis headline.
ts["total"] = ts["equity"].astype(float)        # market value (mark-to-market)
ts["realized_pool"] = ts["balance"].astype(float)  # cost basis (capital invested)
dates = ts.index

# ---------- charts ----------
# 1. market value vs cost basis (gap = unrealized P&L)
f1 = go.Figure()
f1.add_scatter(x=dates, y=ts["total"], mode="lines", name="Market value",
               line=dict(color=BLUE, width=2.6))
f1.add_scatter(x=dates, y=ts["realized_pool"], mode="lines", name="Cost basis",
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
f1.update_layout(title="Market value vs cost basis \u2014 gap is unrealized P&L (daily, scaled)",
                 yaxis_title="MXN (scaled)", xaxis_title="date",
                 hovermode="x unified",
                 legend=dict(orientation="h", y=-0.18))
f1.update_traces(hovertemplate="%{y:,.0f}<extra>%{fullData.name}</extra>",
                 selector=dict(mode="lines"))

# 1b. drawdown from the running peak (%) \u2014 currency-independent, range-linked
_pk = ts["total"].cummax()
_ddpct = (ts["total"] / _pk - 1.0) * 100.0
f1b = go.Figure()
f1b.add_scatter(x=dates, y=_ddpct, mode="lines", name="Drawdown",
                line=dict(color=RED, width=1.6), fill="tozeroy",
                fillcolor="rgba(124,45,18,0.07)",
                hovertemplate="%{x|%d %b %Y} \u00b7 %{y:.2f}%<extra></extra>")
f1b.update_layout(title="Drawdown from peak (%)", yaxis_title="%",
                  height=235, showlegend=False)

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
    _d = DECOMP.get(r["ticker"])
    _is_usd = bool(_d) and not _d["native"]
    _fx_v = _d["fx"] if _is_usd else 0.0
    _stock_v = float(r["pm"]) - _fx_v                       # Stock = Total − FX (reconciles per row)
    _sc = "pos" if _stock_v >= 0 else "neg"
    if _is_usd:
        _fxc = "pos" if _d["fx"] >= 0 else "neg"
        _fx_cell = f"<span class='{_fxc}'>{cval(_d['fx'], signed=True)}</span>"
        _fx_sort = f"{_d['fx']:.2f}"
        _approx = " <span class='muted' title='purchase FX estimated (no trade ledger)'>&asymp;</span>" if _d["approx"] else ""
    else:
        _fx_cell = "<span class='muted'>&mdash;</span>"; _fx_sort = "0"; _approx = ""
    # data-s = raw sort keys (currency-independent), read by the sort/filter JS
    rows += (f"<tr><td data-s='{r['ticker']}'>{r['ticker']}{_approx}</td>"
             f"<td data-s='{r['shares']:.4f}'>{fmt_sh(r['shares'])}</td>"
             f"<td data-s='{r['Costo promedio']:.6f}'>{cval(r['Costo promedio'], 2)}</td>"
             f"<td data-s='{r['Precio mercado']:.6f}'>{cval(r['Precio mercado'], 2)}</td>"
             f"<td data-s='{r['cost']:.2f}'>{cval(r['cost'])}</td>"
             f"<td data-s='{r['value']:.2f}'>{cval(r['value'])}</td>"
             f"<td data-s='{_stock_v:.2f}' class='{_sc}'>{cval(_stock_v, signed=True)}</td>"
             f"<td data-s='{_fx_sort}'>{_fx_cell}</td>"
             f"<td data-s='{r['pm']:.2f}' class='{pc}'>{cval(r['pm'], signed=True)}</td>"
             f"<td data-s='{r['ret']:.6f}' class='{rc}'>{r['ret']*100:+.2f}%</td></tr>")

# ---------- realized P&L since inception (ledger-based, date-aware, FX-decomposed) ----------
# Ported from the offline cost-basis dashboard so the public page's realized figures
# match it and reconcile with the unrealized decomposition above. Source: the GBM
# "Historial de Transacciones" ledger + dated broker snapshots in the archive.
#
# GBM re-exports the same fills under shifted value dates, so the ledger is assembled
# from named exports with explicit non-overlapping roles -- never glob+union, which
# double-counts. The 24-Apr batch appears again as a "27-Apr" batch in export
# ...549357, and 12-Jun AMAT appears in three files. Export ...238707 is the canonical
# calendar: it dates the SOXX fills 29-Apr, matching the authoritative window file,
# where ...549357 says 30-Apr.
#
# VGT/VUG are held out of the 24-Apr batch: their 6:1 split re-based shares on exactly
# that date (price 04-20), so cost basis there is ambiguous. The other names in the
# batch have no split and a clean 04-24 broker snapshot to price against.
_ARCH  = paths.cuser("Documents", "GBM_Account_Archive")
_HISTD = os.path.join(_ARCH, "transactions_historial")
_HISTF = os.path.join(_HISTD, "GBM_Historial_Transacciones_2026-04-28_to_2026-06-15.csv")
_APRF  = os.path.join(_HISTD, "GBM_Homebroker_Historial_de_Transacciones_1779481238707.csv")
_JUNF  = os.path.join(_HISTD, "GBM_Homebroker_Historial_de_Transacciones_JUN_2026.csv")
_FEBF  = os.path.join(_HISTD, "GBM_Homebroker_Historial_de_Transacciones_1774471069759.csv")
_MARF  = os.path.join(_HISTD, "GBM_Homebroker_Historial_de_Transacciones_1774471093585.csv")
_APR_NO_SPLIT = {"MSFT", "AMZN", "GOOGL", "QQQ"}   # 24-Apr batch, ex-VGT/VUG
_D = lambda y,m,d: pd.Timestamp(y,m,d)
_RMON  = {"ene":1,"feb":2,"mar":3,"abr":4,"may":5,"jun":6,"jul":7,"ago":8,"sep":9,
          "oct":10,"nov":11,"dic":12,"jan":1,"apr":4,"aug":8,"dec":12}
def _rnum(s):
    s = str(s).replace("$","").replace(",","").replace("(","-").replace(")","").strip()
    try: return float(s)
    except ValueError: return 0.0
def _rdate(s):
    s = str(s).strip().lower()
    try:
        if "/" in s: d,m,y = s.split("/"); return pd.Timestamp(int(y), _RMON.get(m[:3],1), int(d))
        if "-" in s: d,m,y = s.split("-"); yr=int(y); yr=yr+2000 if yr<100 else yr; return pd.Timestamp(yr, _RMON.get(m[:3],1), int(d))
    except Exception: return None
    return None
_rtk = _norm_ticker            # ledger key normalisation, shared with the holdings snapshot
def _rsnapdate(p):
    import re as _re3
    m = _re3.search(r"(\d{13})", os.path.basename(p))
    return pd.Timestamp(int(m.group(1)), unit="ms") if m else None
_rcost = {}
for _sp in _rg.glob(os.path.join(_ARCH, "portfolio_snapshots", "GBM_Homebroker_Detalle_de_Portafolio_*.csv")):
    _sd = _rsnapdate(_sp)
    if _sd is None: continue
    try:
        _sect = None
        with open(_sp, encoding="utf-8-sig", errors="replace") as _fh:
            for _row in _csv.reader(_fh):
                if not _row: continue
                h = _row[0].strip()
                if h in ("Mercado de Capitales Nacional", "Mercado de Capitales Global (SIC)"):
                    _sect = "eq"; continue
                if len(_row) == 1: _sect = None; continue
                if _sect == "eq" and h not in ("Emisora/Fondo", "") and len(_row) >= 3:
                    _c = _rnum(_row[2])
                    if _c > 0: _rcost.setdefault(_rtk(h), []).append((_sd, _c))
    except OSError:
        continue
for _t in _rcost: _rcost[_t].sort()
def _costasof(t, when):
    lst = _rcost.get(t)
    if not lst: return None
    best = None
    for d,c in lst:
        if d <= when: best = c
        else: break
    return best if best is not None else lst[0][1]
try:
    _fxh = yf.Ticker("MXN=X").history(start="2026-03-15", end="2026-06-16", auto_adjust=False)
    _fxpts = sorted((d.date(), float(c)) for d,c in zip(_fxh.index, _fxh["Close"]))
except Exception:
    _fxpts = []
def _fxat(dt):
    day = dt.date() if hasattr(dt, "date") else dt
    if not _fxpts: return fx_live
    v = _fxpts[0][1]
    for d,c in _fxpts:
        if d <= day: v = c
        else: break
    return v
def _ledger_rows(path):
    """Yield (kind, ticker, date, shares, price) for one export; [] if unreadable."""
    try:
        with open(path, encoding="utf-8-sig") as _fh:
            for _row in _csv.reader(_fh):
                if not _row or len(_row) < 12 or _row[0].strip() == "Emisora": continue
                d = _rdate(_row[1])
                if d is None: continue
                if "Compra de Acciones" in _row[3]:
                    yield ("buy", _rtk(_row[0]), d, _rnum(_row[4]), _rnum(_row[5]))
                elif "Venta de Acciones" in _row[3]:
                    yield ("sell", _rtk(_row[0]), d, _rnum(_row[4]), _rnum(_row[5]))
    except OSError:
        return

# Each (export, kind) owns a disjoint slice of the calendar. Anything outside its slice
# is another export's responsibility, so no fill is counted twice.
_SELL_SRC = [
    (_MARF,  lambda t, d: d <  _D(2026,4,24)),                                  # 17-Mar VGT (pre-spine)
    (_APRF,  lambda t, d: _D(2026,4,24) <= d < _D(2026,4,29)),                  # 24-Apr batch
    (_HISTF, lambda t, d: d >= _D(2026,4,29)),                                  # 04-29 .. 06-12 core
    (_JUNF,  lambda t, d: d >  _D(2026,6,15)),                                  # 18-Jun batch
]
_BUY_SRC = [                                                                    # _xbuy weighting only
    (_FEBF,  lambda t, d: d <  _D(2026,3,1)),
    (_MARF,  lambda t, d: _D(2026,3,1)  <= d < _D(2026,3,24)),
    (_APRF,  lambda t, d: _D(2026,3,24) <= d < _D(2026,4,28)),
    (_HISTF, lambda t, d: _D(2026,4,28) <= d <= _D(2026,6,9)),
    (_JUNF,  lambda t, d: d >  _D(2026,6,9)),
]
_lbuys, _lsells, _prov = {}, [], {}
for _src, _keep in _BUY_SRC:
    for _k, _t, _d, _sh, _px in _ledger_rows(_src):
        if _k == "buy" and _keep(_t, _d):
            _lbuys.setdefault(_t, []).append((_d, _sh))
for _src, _keep in _SELL_SRC:
    for _k, _t, _d, _sh, _px in _ledger_rows(_src):
        if _k != "sell" or not _keep(_t, _d): continue
        _lsells.append({"t": _t, "d": _d, "sh": _sh, "px": _px})
        _prov.setdefault((_t, _d, _sh, _px), []).append(os.path.basename(_src))

# A fill reachable from two exports means the slices overlap -> realized P&L inflates
# silently. Same trade on two nearby dates means a shifted re-export slipped through.
_dupe = {k: v for k, v in _prov.items() if len(set(v)) > 1}
if _dupe:
    raise SystemExit("LEDGER GUARD: fill claimed by >1 export -> " + repr(_dupe))
_shift = [(a, b) for a in _prov for b in _prov
          if a < b and a[0] == b[0] and a[2] == b[2] and a[3] == b[3]
          and 0 < abs((a[1] - b[1]).days) <= 5]
if _shift:
    raise SystemExit("LEDGER GUARD: same ticker/shares/price on two nearby dates "
                     f"(shifted re-export?) -> {_shift}")
print(f"  ledger: {len(_lsells)} sell fills from {len(_SELL_SRC)} exports, "
      f"{sum(len(v) for v in _lbuys.values())} buy fills from {len(_BUY_SRC)}")
def _xbuy(t, upto):
    lots = [(d,s) for d,s in _lbuys.get(t, []) if d <= upto]
    tot = sum(s for _,s in lots)
    return (sum(s*_fxat(d) for d,s in lots)/tot) if tot > 0 else fx_live
_ragg = {}
for _s in _lsells:
    _cb = _costasof(_s["t"], _s["d"]) or _s["px"]
    _xb = _xbuy(_s["t"], _s["d"]); _xs = _fxat(_s["d"])
    _pbuy = _cb/_xb if _xb else 0.0; _psell = _s["px"]/_xs if _xs else 0.0
    _S = _s["sh"]; _dP = _psell - _pbuy
    _st = _S*_dP*_xb + _S*_dP*(_xs-_xb); _fx = _S*_pbuy*(_xs-_xb); _tt = (_s["px"]-_cb)*_S
    _a = _ragg.setdefault(_s["t"], {"sh":0.0,"proceeds":0.0,"cost":0.0,"stock":0.0,"fx":0.0,"total":0.0})
    _a["sh"]+=_S; _a["proceeds"]+=_s["px"]*_S; _a["cost"]+=_cb*_S
    _a["stock"]+=_st; _a["fx"]+=_fx; _a["total"]+=_tt
# ---------- realized P&L: the private ledger sidecar is authoritative ----------
# _ragg above is NOT the source. It prices each sale at the broker snapshot's
# `Costo promedio` at-or-before the sale date, which is fee-exclusive AND stale (it
# ignores buys between that snapshot and the fill), and it never deducts sell-side
# fees. Measured against the reconciled inception-to-date walk it overstated realized
# P&L by ~10%. It survives only as an INDEPENDENT CROSS-CHECK of the sidecar's fill
# set: two separate merges of the same broker exports must agree on which fills exist.
#
# The sidecar (loaded above) carries the moving-average, all-in, split-adjusted walk
# reconciled to the broker's own `Imp X Cto` to the cent.
_segs = _rl["per_ticker_split_segments"]

# Freshness canary. Our own merge sees the raw exports; if it knows of a sell the
# sidecar's as_of predates, the sidecar's realized total is stale and must be rebuilt.
_asof = pd.Timestamp(_rl["as_of"])
_lastsell = max((s["d"] for s in _lsells), default=None)
if _lastsell is not None and _lastsell > _asof:
    raise SystemExit(f"realized sidecar STALE: ledger has a sell on {_lastsell.date()}, "
                     f"after sidecar as_of {_asof.date()} -- regenerate it")
if len(_lsells) != _rl.get("fill_count"):
    raise SystemExit(f"realized fill-set mismatch: our merge sees {len(_lsells)} sell fills, "
                     f"sidecar walked {_rl.get('fill_count')} -- the two disagree on the ledger")

# Legs and per-share identities. `interaction` is folded into Stock (the table has no
# third column), so Stock + FX must sum to Total, and (AvgSell - AvgCost) x Shares too.
for _t, _d in _segs.items():
    assert abs(_d["realized_stock_incl_interaction"] + _d["realized_fx"]
               - _d["realized_mxn"]) < 0.05, f"realized legs do not sum for {_t}"
    assert abs((_d["avg_sell_net"] - _d["avg_cost_allin"]) * _d["shares_sold"]
               - _d["realized_mxn"]) < 1.0, f"avg-price identity fails for {_t}"
REAL_TOTAL = sum(_d["realized_mxn"] for _d in _segs.values())
REAL_FX    = sum(_d["realized_fx"] for _d in _segs.values())
REAL_STOCK = REAL_TOTAL - REAL_FX
assert abs(REAL_TOTAL - _rl["equity_realized_mxn"]) < 0.05, "segments do not sum to the ledger total"

# Rows are split SEGMENTS, not tickers: VGT's 2026-03-17 fill is in pre-split units and
# folding it into the post-split total makes Avg Sell / Avg Cost meaningless.
_RROWS = sorted(({"t": _t, "sh": _d["shares_sold"], "avg_sell": _d["avg_sell_net"],
                  "avg_cost": _d["avg_cost_allin"], "stock": _d["realized_stock_incl_interaction"],
                  "fx": _d["realized_fx"], "total": _d["realized_mxn"]}
                 for _t, _d in _segs.items()), key=lambda r: -r["total"])
print(f"  realized (sidecar {os.path.basename(_rlf[-1])}, as_of {_asof.date()}): "
      f"total {REAL_TOTAL:,.0f} stock {REAL_STOCK:,.0f} fx {REAL_FX:,.0f} | "
      f"{len(_RROWS)} rows | fill set agrees with our merge ({len(_lsells)})")

def _realized_row(r):
    # Scale once, here, so the data-s sort key and the rendered cell are the same scaled
    # number -- they must never diverge, or the sort attribute republishes the real book.
    # Avg sell/cost are per-share prices: exact by design, like every price on the page.
    sh, stock, fx, total = r["sh"]*SCALE, r["stock"]*SCALE, r["fx"]*SCALE, r["total"]*SCALE
    return (f"<tr><td data-s='{r['t']}'>{r['t']}</td>"
            f"<td data-s='{sh:.2f}'>{fmt_sh(sh)}</td>"
            f"<td data-s='{r['avg_sell']:.4f}'>{cval(r['avg_sell'], 2)}</td>"
            f"<td data-s='{r['avg_cost']:.4f}'>{cval(r['avg_cost'], 2)}</td>"
            f"<td data-s='{stock:.2f}' class='{_cl(stock)}'>{cval(stock, signed=True)}</td>"
            f"<td data-s='{fx:.2f}' class='{_cl(fx)}'>{cval(fx, signed=True)}</td>"
            f"<td data-s='{total:.2f}' class='{_cl(total)}'>{cval(total, signed=True)}</td></tr>")
realized_rows = "".join(_realized_row(r) for r in _RROWS) or "<tr><td colspan='7' style='text-align:center;color:var(--muted);padding:16px'>No realized stock sales.</td></tr>"
realized_foot = (f"<tr class='h-total'><td>TOTAL</td><td></td><td></td><td></td>"
    f"<td class='{_cl(REAL_STOCK)}'>{cval(REAL_STOCK*SCALE, signed=True)}</td>"
    f"<td class='{_cl(REAL_FX)}'>{cval(REAL_FX*SCALE, signed=True)}</td>"
    f"<td class='{_cl(REAL_TOTAL)}'>{cval(REAL_TOTAL*SCALE, signed=True)}</td></tr>")
realized_section = f"""<section class="block"><h2>Realized P&amp;L Since Inception</h2>
<p class="note">Every closed sale since inception, walked fill by fill against a
moving-average cost basis that includes commissions and taxes; proceeds are net of
fees. Stock and FX are the same decomposition as the unrealized panel, with the small
cross term folded into Stock, so the two legs sum to Total and
(Avg&nbsp;Sell &minus; Avg&nbsp;Cost) &times; Shares reproduces it. VGT appears twice:
its March sale predates the 8:1 split, and pre- and post-split units cannot share a
per-share average. Dollar values are scaled and follow the currency toggle;
percentages and per-share prices are exact.</p>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto;-webkit-overflow-scrolling:touch">
<table class="ptable" style="min-width:560px"><thead><tr>
<th>Ticker</th><th>Shares Sold</th><th>Avg Sell</th><th>Avg Cost</th>
<th>Realized Stock</th><th>Realized FX</th><th>Total</th></tr></thead>
<tbody>{realized_rows}</tbody><tfoot>{realized_foot}</tfoot></table></div></section>"""

# ---------- metrics (cost-basis return + Stock/FX + realized since inception) ----------
_pnl_now = float(tot_val - tot_cost)                       # unrealized P/L (scaled MXN)
_since_incep = REAL_TOTAL * SCALE + _pnl_now               # realized + unrealized (scaled MXN)
SNAP = [("Total Market Value", cval(tot_val)),
        ("Total Cost Basis", cval(tot_cost)),
        ("Total P&amp;L Since Inception", cval(_since_incep, signed=True)),
        ("Stock contribution", f"{stock_pct:+.2f}%"),
        ("FX contribution", f"{fx_pct:+.2f}%")]
snap = "".join(
    f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
    for k, v in SNAP)

# ---------- return banners: realized / unrealized / combined ----------
# Every ratio here is scale-invariant -- SCALE cancels -- so these are the REAL returns
# even though the $ tiles above are scaled. Each leg is measured against the cost basis
# it earned on, which makes Combined the cost-weighted blend of the other two rather
# than an unrelated third number. ("Return on Cost" was the unrealized leg under a
# vaguer name; it lives here now.)
_real_cost = sum(r["avg_cost"]*r["sh"] for r in _RROWS) * SCALE  # all-in cost of shares sold
_real_pnl  = REAL_TOTAL * SCALE
_ret_real  = (_real_pnl / _real_cost) if _real_cost else 0.0
_ret_unr   = port_ret                                          # unrealized / held cost
_comb_cost = _real_cost + tot_cost
_ret_comb  = ((_real_pnl + _pnl_now) / _comb_cost) if _comb_cost else 0.0
if _comb_cost:                                                 # blend identity must hold
    _w = _real_cost / _comb_cost
    assert abs(_ret_comb - (_w*_ret_real + (1-_w)*_ret_unr)) < 1e-9, "return banners disagree"
print(f"  returns: realized {_ret_real*100:+.2f}% (cost {_real_cost/SCALE:,.0f}) | "
      f"unrealized {_ret_unr*100:+.2f}% (cost {tot_cost/SCALE:,.0f}) | "
      f"combined {_ret_comb*100:+.2f}%")
BANNERS = [("Realized return", _ret_real), ("Unrealized return", _ret_unr),
           ("Combined return", _ret_comb)]
banners = "".join(
    f'<div class="metric {"m-calm" if v >= 0 else "m-stress"}">'
    f'<div class="mv">{v*100:+.2f}%</div><div class="mk">{k}</div></div>'
    for k, v in BANNERS)
# holdings TOTAL row (placed in <tfoot> so the sort/filter JS leaves it pinned)
holdings_total = (f"<tr class='h-total'><td>TOTAL</td><td></td><td></td><td></td>"
    f"<td class='n'>{cval(tot_cost)}</td><td class='n'>{cval(tot_val)}</td>"
    f"<td class='n {_cl(stock_tot)}'>{cval(stock_tot, signed=True)}</td>"
    f"<td class='n {_cl(fx_tot)}'>{cval(fx_tot, signed=True)}</td>"
    f"<td class='n {_cl(_pnl_now)}'>{cval(_pnl_now, signed=True)}</td>"
    f"<td class='n {_cl(port_ret)}'>{port_ret*100:+.2f}%</td></tr>")

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
_pfd = ",".join(f'"{d.strftime("%Y-%m-%d")}"' for d in ts.index)
JS = """
<script>
var TOT={mxn:[__TOTM__],usd:[__TOTU__]},REAL={mxn:[__REAM__],usd:[__REAU__]};
var BUY={mxn:[__BYM__],usd:[__BYU__]},SEL={mxn:[__SYM__],usd:[__SYU__]};
var PFD=[__PFD__],CUR='mxn',PF_CAP=__CAP__,PF_RATE=__RATE__,PF_RANGE='all';
function applyRange(m){
  PF_RANGE=m;
  var d=document.getElementById('pf-value'),dd=document.getElementById('pf-dd');
  if(!d||!window.Plotly||!PFD.length)return;
  var i0=0;
  if(m!=='all'){
    var p=PFD[PFD.length-1].split('-');
    var last=new Date(+p[0],+p[1]-1,+p[2]);
    last.setMonth(last.getMonth()-parseInt(m,10));
    var iso=last.toISOString().slice(0,10);
    while(i0<PFD.length-1&&PFD[i0]<iso)i0++;
  }
  var xr=[PFD[i0],PFD[PFD.length-1]];
  var lo=Infinity,hi=-Infinity,T=TOT[CUR],R=REAL[CUR],i;
  for(i=i0;i<T.length;i++){if(T[i]<lo)lo=T[i];if(T[i]>hi)hi=T[i];if(R[i]<lo)lo=R[i];if(R[i]>hi)hi=R[i];}
  var pad=(hi-lo)*0.07||1;
  Plotly.relayout(d,{'xaxis.range':xr,'yaxis.range':[lo-pad,hi+pad]});
  if(dd)Plotly.relayout(dd,{'xaxis.range':xr});
  document.querySelectorAll('[data-pr]').forEach(function(b){
    b.classList.toggle('on',b.getAttribute('data-pr')===String(m));});
}
function setCurrency(c){
  CUR=c;
  document.querySelectorAll('.cval').forEach(function(e){e.textContent=e.dataset[c];});
  document.querySelectorAll('.ccy-toggle button').forEach(function(b){
    b.classList.toggle('active',b.dataset.cur===c);});
  var lbl=document.getElementById('ccy-label');
  if(lbl) lbl.textContent=c.toUpperCase();
  var d=document.getElementById('pf-value');
  if(d&&window.Plotly){
    Plotly.restyle(d,{y:[TOT[c],REAL[c],BUY[c],SEL[c]]},[0,1,2,3]);
    Plotly.relayout(d,{'yaxis.title.text':c.toUpperCase()+' (scaled)'});
    applyRange(PF_RANGE);
  }
}
document.addEventListener('DOMContentLoaded',function(){
  setCurrency('mxn');
  document.querySelectorAll('[data-pr]').forEach(function(b){
    b.addEventListener('click',function(){applyRange(b.getAttribute('data-pr'));});});
  // holdings table: click-to-sort headers + ticker filter + "/" shortcut
  var tb=document.getElementById('h-body');
  if(tb){
    var heads=document.querySelectorAll('#h-table thead th');
    heads.forEach(function(th,ci){
      th.classList.add('sortable');
      var arr=document.createElement('span');arr.className='arr';th.appendChild(arr);
      th.addEventListener('click',function(){
        var asc=th.getAttribute('data-dir')!=='asc';
        heads.forEach(function(h){h.removeAttribute('data-dir');
          var a=h.querySelector('.arr');if(a)a.textContent='';});
        th.setAttribute('data-dir',asc?'asc':'desc');
        arr.textContent=asc?'\\u25B4':'\\u25BE';
        var rows=Array.prototype.slice.call(tb.rows);
        rows.sort(function(a,b){
          var x=a.cells[ci].getAttribute('data-s'),y=b.cells[ci].getAttribute('data-s');
          var nx=parseFloat(x),ny=parseFloat(y),c;
          if(isFinite(nx)&&isFinite(ny))c=nx-ny;else c=String(x).localeCompare(String(y));
          return asc?c:-c;});
        rows.forEach(function(r){tb.appendChild(r);});
      });
    });
    var search=document.getElementById('h-search');
    if(search){
      search.addEventListener('input',function(){
        var q=search.value.trim().toUpperCase();
        Array.prototype.forEach.call(tb.rows,function(r){
          r.style.display=(!q||r.cells[0].textContent.toUpperCase().indexOf(q)>-1)?'':'none';});
      });
      document.addEventListener('keydown',function(e){
        var ae=document.activeElement,tag=ae&&ae.tagName;
        if(e.key==='/'&&ae!==search&&tag!=='INPUT'&&tag!=='TEXTAREA'){
          e.preventDefault();search.focus();
          search.scrollIntoView({block:'center',behavior:'smooth'});}
        if(e.key==='Escape'&&ae===search){search.value='';
          search.dispatchEvent(new Event('input'));search.blur();}
      });
    }
  }
});
</script>
""".replace("__TOTM__", _totm).replace("__TOTU__", _totu).replace("__REAM__", _ream).replace("__REAU__", _reau).replace("__BYM__", _bym).replace("__BYU__", _byu).replace("__SYM__", _sym2).replace("__SYU__", _syu).replace("__PFD__", _pfd).replace("__CAP__", f"{CAPITAL:.0f}").replace("__RATE__", f"{RATE:.6f}")

PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Portfolio Tracker</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><script src="{PLOTLY}"></script>
<style>
/* portfolio coherence fixes (2026-06-15):
   - headers inside the new overflow-x scroll tiles must NOT be sticky (sticky+overflow
     ancestor was rendering the first row ABOVE the header);
   - symmetric P/L colours: .ptable td sets the ink colour and out-specifies bare .pos,
     so positives rendered black while span-wrapped negatives stayed red. Raise specificity. */
.ptable thead th{{position:static;top:auto}}
.ptable td.pos{{color:var(--pos)}}
.ptable td.neg{{color:var(--neg)}}
.ptable tr.h-total td{{font-weight:700;border-top:2px solid var(--line-strong);background:#fbfaf8}}
.ptable tr.h-total td:first-child{{letter-spacing:.06em;color:var(--ink)}}
</style></head>
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
amounts; prices, returns and weights are exact. Positions and cost basis come
from the broker statement (source of truth), re-priced live. <b>Accounting:</b>
every position is measured against its cost basis &mdash;
Return = (market value &divide; cost) &minus; 1. For US-dollar holdings the peso
P/L is split into <b>Stock</b> (the US price move at the exchange rate we bought
at) and <b>FX</b> (the peso's move on the original cost); the two sum to Total
P/L = market value &minus; cost. (Stock here folds in a small price&times;FX
interaction term, itemized separately in <b>FX Attribution</b> below.) The GBMF2
cash sleeve, FX positions and non-GBM bank cash are excluded from the equity
book.</div>
<section class="block"><h2>Snapshot</h2>
<div class="ccy-toggle">
<button data-cur="mxn" class="active" onclick="setCurrency('mxn')">MXN</button>
<button data-cur="usd" onclick="setCurrency('usd')">USD</button></div>
<p class="note">Currency: <b id="ccy-label">MXN</b> &mdash; returns read the same
in either currency. Total Return is on cost basis (market value &divide; cost
&minus; 1); the Stock and FX contributions decompose where the peso P/L came
from. Definitions in the <a href="glossary.html">Glossary</a>.</p>
<div class="metrics" style="grid-template-columns:repeat(5,1fr)">{snap}</div>
<div class="metrics" style="grid-template-columns:repeat(3,1fr);margin-top:1.5rem">{banners}</div>
<p class="note" style="margin-top:.8rem"><b>Realized</b> is closed sales against the
cost basis of the shares sold; <b>Unrealized</b> is open positions against the cost
basis still held; <b>Combined</b> weights the two by their cost bases, so it sits
between them. All three are exact &mdash; the display scaling cancels in a
ratio, unlike the peso tiles above.</p></section>
<section class="block"><h2>Market Value vs Cost Basis</h2>
<div class="btctl"><div class="btranges">
<button class="btr on" data-pr="all">All</button>
<button class="btr" data-pr="6">6M</button>
<button class="btr" data-pr="3">3M</button>
<button class="btr" data-pr="1">1M</button>
</div><span class="btlbl">window &middot; hover for daily detail</span></div>
<div class="tile chart"><div class="ch">{div(f1, "pf-value")}</div></div>
<div class="tile chart" style="margin-top:1.5rem"><div class="ch">{div(f1b, "pf-dd")}</div></div>
<p class="note" style="margin-top:.8rem">Drawdown is measured from the running
peak of market value; it reads identically in either currency.</p></section>
{fxa_section}
<section class="block"><h2>Holdings</h2>
<input type="search" id="h-search" class="tsearch" placeholder="Filter holdings&hellip; press /"
 aria-label="Filter holdings by ticker">
<div class="tile" style="padding:0 16px 8px;overflow-x:auto;-webkit-overflow-scrolling:touch">
<table class="ptable" id="h-table" style="min-width:680px"><thead><tr><th>Holding</th><th>Shares</th>
<th>Avg Cost</th><th>Price</th><th>Cost</th><th>Value</th>
<th>Stock P/L</th><th>FX P/L</th><th>Total P/L</th><th>Return</th></tr></thead>
<tbody id="h-body">{rows}</tbody><tfoot>{holdings_total}</tfoot></table></div>
<p class="note" style="margin-top:.8rem">Click a column header to sort; type to
filter. Sorting and filtering are display-only; the TOTAL row stays pinned.</p></section>
{realized_section}
<section class="block"><h2>Portfolio vs Its Holdings</h2>
<div class="grid"><div class="tile chart"><div class="ch">{div(f2, "pf-rel")}</div></div>
<div class="tile chart"><div class="ch">{div(f3, "pf-alloc")}</div></div></div></section>
</main>
<footer class="shell-foot"><div class="container"><p>Figures scaled for
confidentiality. Research and monitoring, not investment advice.</p></div></footer>
{JS}</body></html>"""

# --- confidentiality guard -------------------------------------------------
# Nothing derived from the real book may reach docs/ unscaled. Rendered cells were
# audited by eye; data-s sort attributes were not, and carried the real realized
# P&L to the public site for three weeks (c5ae501, 2026-06-15). Fail the build
# rather than publish. Per-share prices and % returns are exact by design and are
# not checked here.
assert SCALE == 1.8, f"confidentiality scale factor is {SCALE}, expected 1.8"
_leaked = [f"{r['t']}.{k}={r[k]:,.2f}"
           for r in _RROWS
           for k in ("sh", "stock", "fx", "total")
           if abs(r[k]) > 0.005 and f"data-s='{r[k]:.2f}'" in HTML]
if _leaked:
    raise SystemExit("CONFIDENTIALITY GUARD FAILED: unscaled real values in data-s -> "
                     + ", ".join(_leaked))
# Naming the factor in prose lets any reader undo the scaling. Say "scaled by a fixed
# constant", never the number. (WEBSITE_DEPLOY.md rule 1.)
_told = [p for p in (f"&times;{SCALE}", f"x{SCALE}", f"×{SCALE}") if p in HTML]
if _told:
    raise SystemExit(f"CONFIDENTIALITY GUARD FAILED: page names the scale factor -> {_told}")
print(f"  confidentiality guard OK | scale factor x{SCALE} not disclosed | "
      f"{len(_RROWS)} realized rows checked")

open(f"{DOCS}/portfolio.html", "w", encoding="utf-8").write(HTML)
print(f"Portfolio tracker built -> {DOCS}/portfolio.html")
print(f"  {len(latest)} holdings | value(scaled) MXN {tot_val:,.0f} / "
      f"USD {tot_val/RATE:,.0f} | return {port_ret*100:+.1f}% | "
      f"as-of {asof} | USDMXN {RATE:.2f}")
