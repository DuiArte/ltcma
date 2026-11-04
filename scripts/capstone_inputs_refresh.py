"""Refresh the two private capstone macro inputs that the site's stock picker reads (wave 14, 2026-11-04).

    ~/capstone/data/analytics/stock_sensitivities.parquet   one row per ticker (40)
    ~/capstone/data/analytics/stock_fomc_reaction.parquet   one row per (ticker, FOMC meeting)
    ~/capstone/data/analytics/capstone_inputs_meta.json     sidecar: data-through date, build time, sources

Port of the WSL producer ~/capstone/analytics/build_stock_sensitivities.py (last run 2026-05-20). Same universe,
same window start, same regressions, same rounding, same FOMC event rule and the same parquet schema. What changed,
and why (every point is in DEPLOY_NOTES.md):
  * Transport. The producer called yfinance with its default session (Chrome impersonation). Here every Yahoo call
    goes through the site's scripts/yahoo_session.py SESSION (honest UA, no impersonation, 401/403/410/429 never
    retried). FRED is read directly (API with Carlos's key, or the keyless fredgraph.csv), research UA, no retry on
    a block. The producer read FRED from a stale local CSV.
  * USDCAD. The producer read a static FxPro M5 export that ends 2025-11-27, so its betas silently stopped there.
    This port takes USDCAD from one honest source for the whole window (CAD_SOURCE below; chosen on evidence).
  * P/E and market cap are pinned to the as-of close (Yahoo's own ratio x close/quote price), so a re-run on the same
    as-of day gives the same numbers whatever the time of day. On a weekend run the scale is 1 (Yahoo's value).
  * Only completed sessions: the window ends at --asof (default: yesterday, local date), like the producer's
    exclusive END = run date.
  * The FOMC dates are embedded (public facts) instead of a hand-typed CSV; one wrong date is corrected (see FOMC_DATES).
  * The CPI table (stock_cpi_reaction.parquet) is NOT rebuilt: nothing on the site reads it.
  * Round 2 (main-session design choice C3): FOMC meetings BEFORE a ticker's first trading day are DROPPED
    (DROP_PRE_LISTING). The producer measured them from the first trading day, so 50 rows repeated one IPO-week
    drift (ARM 29, COIN 10, PLTR 6, SNOW 5) and the page's n was false (e.g. ARM "Hike n=11" although ARM listed
    after every 2022-23 hike). Revert: DROP_PRE_LISTING = False (the producer's rule, byte-for-byte).
Kept on purpose (faithful): the DFF-based decision labels, the fixed 2018-01-01 start of the regression window.
Location: LTCMA-website/scripts/ (public repo: the 40-name universe and the method are already public on the page;
no weights, no data; it writes only outside the repo). The WSL producer must NEVER be run against the live network
(its yfinance calls use the default, Chrome-impersonating session).

Contract:
  * Refuses, loudly, to overwrite good files when an input is incomplete: one line in YAHOO_ALERT.txt
    (yahoo_session.alert -> LTCMA_ALERT_DIR or C:\\Users\\carlo\\Scripts\\logs), exit 1, previous files untouched.
  * Writes atomically: temp file in the same folder, read back and compared, then os.replace; previous files are
    copied to <out>/_backup/<stamp>/ first (last KEEP_BACKUPS kept); a failed second replace rolls the first back.
  * Deterministic: the build is a pure function of the raw snapshot it saves (<out>/_snapshots/<asof>/); the same
    snapshot gives byte-identical parquets (--from-snapshot rebuilds offline, no network).
  * Never commits anything, never writes inside a git checkout, holds no picker weights. The outputs are private.

Usage:
    python capstone_inputs_refresh.py                      # fetch (honest) + build + validate + write
    python capstone_inputs_refresh.py --dry-run            # fetch + build + validate, write nothing
    python capstone_inputs_refresh.py --from-snapshot DIR  # offline rebuild from a saved snapshot
    python capstone_inputs_refresh.py --lock               # standalone: take Global\\LTCMA_REPO_LOCK first
Exit: 0 written (or dry-run OK), 1 refused / failed (alert written), 2 usage error.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ANA = os.path.expanduser("~/capstone/data/analytics")      # same folder picker.ANA reads
SENS_NAME = "stock_sensitivities.parquet"
FOMC_NAME = "stock_fomc_reaction.parquet"
META_NAME = "capstone_inputs_meta.json"
KEEP_BACKUPS = 8
KEEP_SNAPSHOTS = 4
SCHEMA_VERSION = 1

# ---- universe: verbatim from the producer (order matters: it is the parquet's index) ----------------------------
UNIVERSE = [
    "NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AVGO", "TSLA", "ORCL", "NFLX",
    "PLTR", "CRWD", "NET", "SNOW", "NOW", "CRM", "INTU", "ADBE", "AMD", "ANET",
    "SHOP", "ARM", "SMCI", "COIN", "MSTR", "DDOG",
    "LLY", "COST", "ABBV", "NVO",
    "WMT", "HD", "UNH",
    "JPM", "BAC", "XOM", "CVX", "KO", "VZ", "T",
]
START = "2018-01-01"                                       # producer's fixed regression start
DXY_SYMBOL = "DX-Y.NYB"
CAD_SOURCE = "yahoo"                                       # "yahoo" (CAD=X, CAD per USD) | "fred" (DEXCAUS, CAD per USD)
CAD_YAHOO = "CAD=X"
CAD_FRED = "DEXCAUS"
# Label alignment. Yahoo's FX daily bar dated D closes around 00:00 UTC of D, i.e. the New York evening of D-1, so
# its value is moved back one bar to sit on the session it belongs to. Evidence (2018-01..2025-11, wave 14): daily
# returns vs the producer's FxPro series (NY-close, 17:00 ET) correlate 0.929 after the shift, 0.032 without it;
# FRED DEXCAUS (12:00 ET noon rate) reaches 0.791. The newest session therefore has no USDCAD return and drops out
# of the regression (its value would be the live, still-forming bar).
CAD_LABEL_SHIFT = {"yahoo": -1}

# FOMC decision days (second day of each meeting). The producer's fomc_calendar.csv, verbatim, except:
#   * 2026-05-06 -> 2026-04-29: the Fed's calendar page (federalreserve.gov/monetarypolicy/fomccalendars.htm, read
#     2026-11-04) lists April 28-29, 2026; 05-06 was the 2025 pattern carried over by hand.
#   * 2027 added from the same page (Jan 26-27, Mar 16-17, Apr 27-28, Jun 8-9, Jul 27-28, Sep 14-15, Oct 26-27,
#     Dec 7-8). 2021-2026 match that page; 2020 is the producer's list (not on that page; not re-checked).
# Scheduled meetings plus the 2020-03-15 Sunday meeting; the 2020-03-03 inter-meeting cut is absent (as in the
# producer). A date enters the table once 5 sessions follow it. Add the next year's dates when the Fed publishes
# them: the script alerts when fewer than CALENDAR_LEAD_DAYS of future dates remain.
FOMC_DATES = (
    "2020-01-29", "2020-03-15", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
)
CALENDAR_LEAD_DAYS = 45
DROP_PRE_LISTING = True          # C3: a meeting before a ticker's first trading day is not a row (False = producer)

# ---- completeness floors (a refusal, never a partial file) ---------------------------------------------------------
MAX_PRICE_LAG_DAYS = 5          # newest bar vs --asof (a weekend + a holiday)
MAX_FACTOR_LAG_DAYS = {"dxy": 7, "cad": 14, "dgs10": 7, "dff": 7}   # factor's last obs vs the newest price bar
MIN_NOBS_RATIO = 0.98           # a ticker's regression sample may not shrink vs the previous file
MIN_PE_COVERAGE = 0.90          # share of tickers with a finite P/E

# ---- honest transport (non-Yahoo) -----------------------------------------------------------------------------------
BLOCK_CODES = {401, 403, 410, 429}
FRED_API = "https://api.stlouisfed.org/fred/series/observations"
FRED_GRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv"
_COUNTS = {"fred": 0}

SENS_COLS = ["ticker", "sector", "industry", "marketcap_B", "pe", "fwd_pe", "n_obs", "r2",
             "beta_rates", "t_rates", "beta_dxy", "t_dxy", "beta_cad", "t_cad"]
FOMC_COLS = ["ticker", "fomc", "decision", "fwd1", "fwd5"]
INFO_KEYS = ("trailingPE", "forwardPE", "trailingEps", "forwardEps", "currentPrice", "regularMarketPrice",
             "marketCap", "sector", "industry", "shortName", "quoteType")


class Refused(Exception):
    """Inputs incomplete: nothing is written, the previous files stay."""


def log(msg):
    print(f"{datetime.now():%H:%M:%S} capstone: {msg}", flush=True)


def _alert(msg):
    """One line in YAHOO_ALERT.txt via the site helper (the convention the watchdog reads)."""
    line = f"capstone inputs: {msg}"
    try:
        import yahoo_session as ys
        ys.alert(line)
    except Exception:                                                   # noqa: BLE001
        print("!! " + line, file=sys.stderr, flush=True)


def _user_agent():
    try:
        import yahoo_session as ys
        return ys.USER_AGENT
    except Exception:                                                   # noqa: BLE001
        return "Mozilla/5.0 (compatible; CarlosDuarteResearch/0.1; market-intel CMA fetcher)"


# =============================================================================== fetch (the only network code)
def _http_session():
    import requests
    s = requests.Session()
    s.trust_env = False                                    # no env proxies
    s.headers.update({"User-Agent": _user_agent()})
    return s


def fetch_fred(sid, start, end, http=None):
    """FRED series as a date-indexed float Series. API with Carlos's key first; on a timeout / 5xx / no key the
    keyless fredgraph.csv once. 401/403/410/429 are a block: never retried, Refused."""
    import requests
    http = http or _http_session()
    key = None
    try:
        from fred_api import fred_key
        key = fred_key()
    except Exception:                                                   # noqa: BLE001
        key = os.environ.get("FRED_API_KEY")
    if key:
        _COUNTS["fred"] += 1
        try:
            r = http.get(FRED_API, params={"series_id": sid, "api_key": key, "file_type": "json",
                                           "observation_start": start, "observation_end": end}, timeout=(6, 30))
            if r.status_code in BLOCK_CODES:
                raise Refused(f"FRED BLOCKED: HTTP {r.status_code} on {sid} (api); not retried")
            if r.status_code == 200:
                obs = r.json()["observations"]
                s = pd.Series({o["date"]: o["value"] for o in obs}, name=sid, dtype=object)
                s.index = pd.to_datetime(s.index)
                return pd.to_numeric(s, errors="coerce").dropna().sort_index()
            log(f"FRED api {sid}: HTTP {r.status_code}; trying fredgraph.csv once")
        except requests.RequestException as e:
            log(f"FRED api {sid}: {type(e).__name__}; trying fredgraph.csv once")
    _COUNTS["fred"] += 1
    r = http.get(FRED_GRAPH, params={"id": sid, "cosd": start, "coed": end}, timeout=(6, 30))
    if r.status_code in BLOCK_CODES:
        raise Refused(f"FRED BLOCKED: HTTP {r.status_code} on {sid} (fredgraph); not retried")
    if r.status_code != 200:
        raise Refused(f"FRED {sid}: HTTP {r.status_code} on fredgraph.csv")
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", sid]
    df["date"] = pd.to_datetime(df["date"])
    return pd.to_numeric(df.set_index("date")[sid], errors="coerce").dropna().sort_index()


def _closes(data, symbols):
    """yf.download frame -> DataFrame of Close columns (one per symbol)."""
    if data is None or len(data) == 0:
        return pd.DataFrame(columns=symbols, dtype=float)
    if isinstance(data.columns, pd.MultiIndex):
        c = data["Close"]
    else:
        c = data[["Close"]].rename(columns={"Close": symbols[0]})
    c = c.reindex(columns=symbols)
    c.index = pd.DatetimeIndex(c.index).tz_localize(None) if getattr(c.index, "tz", None) else pd.DatetimeIndex(c.index)
    return c.astype(float)


def fetch_snapshot(asof, snapdir, cad_source=CAD_SOURCE, full_info=None):
    """Fetch every raw input once, through honest transports, into snapdir. Returns the manifest dict.
    full_info: optional dict that receives each ticker's whole Yahoo .info (evidence harness only)."""
    import yfinance as yf
    import yahoo_session as ys                             # honest Yahoo transport (no impersonation)
    os.makedirs(snapdir, exist_ok=True)
    end_excl = (pd.Timestamp(asof) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    t0 = time.time()
    r0 = ys.status()["requests"]

    # 1. daily closes, auto-adjusted (producer: batches of 10; SPY dropped: the producer fetched it and never used it)
    frames = []
    for i in range(0, len(UNIVERSE), 10):
        chunk = UNIVERSE[i:i + 10]
        try:
            d = yf.download(chunk, start=START, end=end_excl, auto_adjust=True, progress=False, threads=True,
                            group_by="column", session=ys.SESSION)
        except ys.YahooBlocked as e:
            raise Refused(f"Yahoo blocked during prices: {e}")
        frames.append(_closes(d, chunk))
        if ys.blocked():
            raise Refused(f"Yahoo blocked during prices: {ys.blocked()}")
    prices = pd.concat(frames, axis=1).sort_index()
    prices.index.name = "date"

    # 2. DXY (Yahoo, as in the producer)
    try:
        d = yf.download(DXY_SYMBOL, start=START, end=end_excl, auto_adjust=True, progress=False, session=ys.SESSION)
    except ys.YahooBlocked as e:
        raise Refused(f"Yahoo blocked during DXY: {e}")
    dxy = _closes(d, [DXY_SYMBOL])[DXY_SYMBOL].rename("dxy")

    # 3. USDCAD (producer: static FxPro export ending 2025-11-27 -> replaced by one honest source)
    if cad_source == "yahoo":
        try:
            d = yf.download(CAD_YAHOO, start=START, end=end_excl, auto_adjust=True, progress=False,
                            session=ys.SESSION)
        except ys.YahooBlocked as e:
            raise Refused(f"Yahoo blocked during USDCAD: {e}")
        cad = _closes(d, [CAD_YAHOO])[CAD_YAHOO].rename("cad")
    elif cad_source == "fred":
        cad = fetch_fred(CAD_FRED, START, asof).rename("cad")
    else:
        raise ValueError(f"unknown cad_source {cad_source!r}")

    # 4. FRED: 10y yield (rates factor) + effective fed funds (decision labels)
    dgs10 = fetch_fred("DGS10", "2017-12-01", asof).rename("dgs10")
    dff = fetch_fred("DFF", "2019-12-01", asof).rename("dff")

    # 5. P/E, sector, industry, market cap (Yahoo .info via the honest session)
    info = {}
    for t in UNIVERSE:
        if ys.blocked():
            break
        try:
            inf = yf.Ticker(t, session=ys.SESSION).info or {}
        except ys.YahooBlocked:
            break
        except Exception as e:                                          # noqa: BLE001
            log(f"info {t}: {type(e).__name__}: {e}")
            inf = {}
        if full_info is not None:
            full_info[t] = inf
        info[t] = {k: inf.get(k) for k in INFO_KEYS}
    if ys.blocked():
        raise Refused(f"Yahoo blocked during .info: {ys.blocked()}")

    prices.to_parquet(os.path.join(snapdir, "prices.parquet"))
    pd.DataFrame({"dxy": dxy}).to_parquet(os.path.join(snapdir, "dxy.parquet"))
    pd.DataFrame({"cad": cad}).to_parquet(os.path.join(snapdir, "cad.parquet"))
    pd.DataFrame({"dgs10": dgs10}).to_parquet(os.path.join(snapdir, "dgs10.parquet"))
    pd.DataFrame({"dff": dff}).to_parquet(os.path.join(snapdir, "dff.parquet"))
    with open(os.path.join(snapdir, "info.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1, sort_keys=True, default=str)
    st = ys.status()
    man = {"asof": asof, "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "cad_source": cad_source, "start": START,
           "requests": {"yahoo": st["requests"] - r0, "fred": _COUNTS["fred"]},
           "yahoo_blocks": st["blocks"], "seconds": round(time.time() - t0, 1),
           "transport": "yahoo_session.SESSION (honest UA, no impersonation); FRED research UA"}
    man["files"] = {f: _sha256(os.path.join(snapdir, f)) for f in sorted(os.listdir(snapdir))
                    if f != "manifest.json"}
    with open(os.path.join(snapdir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
    return man


# =============================================================================== build (pure, offline)
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def load_snapshot(snapdir):
    def one(name, col):
        s = pd.read_parquet(os.path.join(snapdir, name))[col]
        s.index = pd.DatetimeIndex(s.index)
        return s.astype(float)
    with open(os.path.join(snapdir, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    prices = pd.read_parquet(os.path.join(snapdir, "prices.parquet"))
    prices.index = pd.DatetimeIndex(prices.index)
    with open(os.path.join(snapdir, "info.json"), encoding="utf-8") as fh:
        info = json.load(fh)
    return {"manifest": man, "prices": prices.astype(float), "dxy": one("dxy.parquet", "dxy"),
            "cad": one("cad.parquet", "cad"), "dgs10": one("dgs10.parquet", "dgs10"),
            "dff": one("dff.parquet", "dff"), "info": info}


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def _meta_from_info(inf, close_asof):
    """Producer: pe = trailingPE or forwardPE; fwd_pe = forwardPE; marketcap. Pinned to the as-of close."""
    inf = inf or {}
    qp = _num(inf.get("currentPrice")) or _num(inf.get("regularMarketPrice"))
    scale = (close_asof / qp) if (qp and close_asof) else 1.0
    tpe, fpe = _num(inf.get("trailingPE")), _num(inf.get("forwardPE"))
    pe = tpe if tpe else fpe                               # producer: `trailingPE or forwardPE`
    mcap = _num(inf.get("marketCap")) or 0.0
    return {"pe": pe * scale if pe is not None else None,
            "fwd_pe": fpe * scale if fpe is not None else None,
            "sector": inf.get("sector") or "?", "industry": inf.get("industry") or "?",
            "marketcap": mcap * scale}


def _decision(dff, d):
    """Producer's rule, verbatim: median DFF d+2..d+14 minus median d-5..d-1 (forward-filled daily)."""
    pre = dff.reindex(pd.date_range(d - pd.Timedelta(days=5), d - pd.Timedelta(days=1), freq="D")).ffill().dropna()
    post = dff.reindex(pd.date_range(d + pd.Timedelta(days=2), d + pd.Timedelta(days=14), freq="D")).ffill().dropna()
    if pre.empty or post.empty:
        return "Unknown"
    ch = post.median() - pre.median()
    if ch < -0.10:
        return "Cut"
    if ch > 0.10:
        return "Hike"
    return "Hold"


def cad_for_regression(cad, source):
    """The USDCAD level series on the session labels of the stock closes (see CAD_LABEL_SHIFT)."""
    s = cad.dropna()
    k = CAD_LABEL_SHIFT.get(source, 0)
    return s.shift(k).dropna() if k else s


def fomc_rows_expected(prices, fomc_dates=FOMC_DATES, drop_pre_listing=DROP_PRE_LISTING):
    """{ticker: number of FOMC rows build() must give}: meetings with >= 6 sessions on/after them and, when
    drop_pre_listing, on/after the ticker's first trading day."""
    dates = pd.to_datetime(pd.Series(fomc_dates))
    out = {}
    for t in UNIVERSE:
        if t not in prices.columns:
            continue
        p = prices[t].dropna()
        if p.empty:
            continue
        first = p.index.min()
        out[t] = int(sum(1 for d in dates if (not drop_pre_listing or d >= first) and (p.index >= d).sum() >= 6))
    return out


def build(snap, fomc_dates=FOMC_DATES, end=None, drop_pre_listing=DROP_PRE_LISTING):
    """Snapshot -> (sens, fomc). Pure. `end` (inclusive) truncates every series (evidence replays only).
    drop_pre_listing: skip meetings before a ticker's first trading day (C3); False = the producer's rule."""
    import statsmodels.api as sm
    prices, dxy, dgs10, dff = (snap["prices"], snap["dxy"], snap["dgs10"], snap["dff"])
    cad = cad_for_regression(snap["cad"], snap["manifest"].get("cad_source"))
    if end is not None:
        e = pd.Timestamp(end)
        prices, dxy, cad, dgs10, dff = (x.loc[:e] for x in (prices, dxy, cad, dgs10, dff))

    # factor panel, producer's construction (pct_change "pad" made explicit: ffill, then fill_method=None)
    factors = pd.DataFrame({
        "dgs10_chg": dgs10.dropna().diff(),
        "dxy_chg": dxy.ffill().pct_change(fill_method=None),
        "cad_chg": cad.dropna().pct_change(fill_method=None),
    })
    stocks = pd.DataFrame({t: prices[t] for t in UNIVERSE if t in prices.columns})
    stock_rets = stocks.ffill().pct_change(fill_method=None)
    panel = factors.join(stock_rets, how="inner").dropna(how="all")
    panel = panel.dropna(subset=["dgs10_chg", "dxy_chg", "cad_chg"])

    last_close = {t: prices[t].dropna() for t in UNIVERSE if t in prices.columns}
    results = []
    for t in UNIVERSE:
        if t not in panel.columns:
            continue
        sub = panel[["dgs10_chg", "dxy_chg", "cad_chg", t]].dropna()
        if len(sub) < 200:
            continue
        m = sm.OLS(sub[t], sm.add_constant(sub[["dgs10_chg", "dxy_chg", "cad_chg"]])).fit()
        lc = last_close[t]
        md = _meta_from_info(snap["info"].get(t), float(lc.iloc[-1]) if len(lc) else None)
        results.append({
            "ticker": t, "sector": md["sector"], "industry": md["industry"],
            "marketcap_B": round((md["marketcap"] or 0) / 1e9, 1),
            "pe": md["pe"], "fwd_pe": md["fwd_pe"],
            "n_obs": int(m.nobs), "r2": round(m.rsquared, 4),
            "beta_rates": round(m.params["dgs10_chg"], 4), "t_rates": round(m.tvalues["dgs10_chg"], 2),
            "beta_dxy": round(m.params["dxy_chg"], 3), "t_dxy": round(m.tvalues["dxy_chg"], 2),
            "beta_cad": round(m.params["cad_chg"], 3), "t_cad": round(m.tvalues["cad_chg"], 2),
        })
    sens = pd.DataFrame(results, columns=SENS_COLS)
    sens = sens.astype({"ticker": object, "sector": object, "industry": object, "marketcap_B": "float64",
                        "pe": "float64", "fwd_pe": "float64", "n_obs": "int64", "r2": "float64",
                        "beta_rates": "float64", "t_rates": "float64", "beta_dxy": "float64",
                        "t_dxy": "float64", "beta_cad": "float64", "t_cad": "float64"})
    sens = sens.sort_values("pe", ascending=False, na_position="last", kind="mergesort")

    # FOMC reactions, producer's rule (first close on/after the meeting, then 1 and 5 sessions later); a meeting
    # before the ticker's first trading day is dropped unless drop_pre_listing is False (the producer's behaviour)
    dates = pd.to_datetime(pd.Series(fomc_dates)).astype("datetime64[ns]")
    dec = {d: _decision(dff, d) for d in dates}
    rows = []
    for t in UNIVERSE:
        if t not in prices.columns:
            continue
        p = prices[t].dropna()
        first = p.index.min() if len(p) else None
        for d in dates:
            if drop_pre_listing and first is not None and d < first:
                continue
            future = p.index[p.index >= d]
            if len(future) < 6:
                continue
            p0, p1, p5 = float(p.loc[future[0]]), float(p.loc[future[1]]), float(p.loc[future[5]])
            rows.append({"ticker": t, "fomc": d, "decision": dec[d], "fwd1": p1 / p0 - 1, "fwd5": p5 / p0 - 1})
    fomc = pd.DataFrame(rows, columns=FOMC_COLS)
    fomc = fomc.astype({"ticker": object, "fomc": "datetime64[ns]", "decision": object,
                        "fwd1": "float64", "fwd5": "float64"}).reset_index(drop=True)
    return sens, fomc


# =============================================================================== validation (the refusal)
def validate(snap, sens, fomc, asof, prev_sens=None, prev_fomc=None, fomc_dates=FOMC_DATES,
             drop_pre_listing=DROP_PRE_LISTING):
    """Return a list of reasons to refuse (empty = complete)."""
    bad = []
    prices = snap["prices"]
    missing = [t for t in UNIVERSE if t not in prices.columns or prices[t].dropna().empty]
    if missing:
        bad.append(f"no prices for {len(missing)} ticker(s): {','.join(missing[:8])}")
    if prices.dropna(how="all").empty:
        return bad + ["no price data at all"]
    newest = prices.dropna(how="all").index.max()
    lag = (pd.Timestamp(asof) - newest).days
    if lag > MAX_PRICE_LAG_DAYS or lag < 0:
        bad.append(f"newest price bar {newest.date()} is {lag} d from as-of {asof}")
    stale = [t for t in UNIVERSE if t in prices.columns and not prices[t].dropna().empty
             and prices[t].dropna().index.max() < newest]
    if stale:
        bad.append(f"{len(stale)} ticker(s) end before {newest.date()}: {','.join(stale[:8])}")
    for k in ("dxy", "cad", "dgs10", "dff"):
        s = snap[k].dropna()
        if s.empty:
            bad.append(f"{k}: empty")
            continue
        flag = (newest - s.index.max()).days
        if flag > MAX_FACTOR_LAG_DAYS[k]:
            bad.append(f"{k}: last obs {s.index.max().date()} is {flag} d behind prices")
    late = [k for k in ("dgs10", "dxy", "cad")
            if not snap[k].dropna().empty and snap[k].dropna().index.min() > pd.Timestamp(START) + pd.Timedelta(days=4)]
    if late or (not snap["dff"].dropna().empty and snap["dff"].dropna().index.min() > pd.Timestamp("2020-01-01")):
        bad.append(f"a factor series starts after the window start (truncated history: {','.join(late) or 'dff'})")
    no_info = [t for t in UNIVERSE if not (snap["info"].get(t) or {}).get("sector")]
    if no_info:
        bad.append(f".info missing for {len(no_info)} ticker(s): {','.join(no_info[:8])}")

    # outputs
    if sorted(sens["ticker"]) != sorted(UNIVERSE):
        lost = sorted(set(UNIVERSE) - set(sens["ticker"]))
        bad.append(f"sensitivities cover {len(sens)}/{len(UNIVERSE)} tickers (missing {','.join(lost[:8])})")
    num = ["r2", "beta_rates", "t_rates", "beta_dxy", "t_dxy", "beta_cad", "t_cad"]
    if len(sens) and sens[num].isna().any().any():
        bad.append("NaN in a beta / t / r2 column")
    if len(sens):
        cov = sens["pe"].notna().mean()
        if cov < MIN_PE_COVERAGE:
            bad.append(f"P/E finite for {cov:.0%} of tickers (< {MIN_PE_COVERAGE:.0%})")
    if fomc.empty:
        bad.append("FOMC table empty")
    else:
        per = fomc.groupby("ticker").size()
        exp = fomc_rows_expected(prices, fomc_dates, drop_pre_listing)
        off = [t for t in UNIVERSE if int(per.get(t, 0)) != exp.get(t, -1)]
        if sorted(per.index) != sorted(UNIVERSE) or off:
            bad.append(f"FOMC rows per ticker differ from the calendar ({len(per)} tickers; "
                       f"{','.join(off[:8]) or 'missing tickers'})")
        if (fomc["decision"] == "Unknown").any():
            bad.append(f"{int((fomc['decision'] == 'Unknown').sum())} FOMC rows with an Unknown decision (DFF gap)")
        if fomc[["fwd1", "fwd5"]].isna().any().any():
            bad.append("NaN in fwd1 / fwd5")
    # vs the previous files: history only grows
    if prev_sens is not None and len(sens):
        a = sens.set_index("ticker")["n_obs"]
        b = prev_sens.set_index("ticker")["n_obs"].reindex(a.index)
        shrunk = [t for t in a.index if pd.notna(b.get(t)) and a[t] < MIN_NOBS_RATIO * b[t]]
        if shrunk:
            bad.append(f"regression sample shrank vs the previous file for {','.join(shrunk[:8])}")
    if prev_fomc is not None and not fomc.empty and not prev_fomc.empty:
        if fomc["fomc"].nunique() < prev_fomc["fomc"].nunique():
            bad.append(f"fewer FOMC meetings ({fomc['fomc'].nunique()}) than the previous file "
                       f"({prev_fomc['fomc'].nunique()})")
    return bad


def calendar_warning(asof, fomc_dates=FOMC_DATES):
    last = max(pd.Timestamp(d) for d in fomc_dates)
    if last < pd.Timestamp(asof) + pd.Timedelta(days=CALENDAR_LEAD_DAYS):
        return (f"FOMC_DATES ends {last.date()}; add the next year's meetings from the Fed's calendar page "
                f"(federalreserve.gov/monetarypolicy/fomccalendars.htm) or new meetings stop entering the target")
    return None


# =============================================================================== write (atomic + backup)
def _read_prev(out_dir):
    try:
        return (pd.read_parquet(os.path.join(out_dir, SENS_NAME)), pd.read_parquet(os.path.join(out_dir, FOMC_NAME)))
    except Exception:                                                   # noqa: BLE001
        return None, None


def _prune(dirpath, keep):
    try:
        subs = sorted(d for d in os.listdir(dirpath) if os.path.isdir(os.path.join(dirpath, d)))
    except OSError:
        return
    for d in subs[:-keep] if keep > 0 else subs:
        shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)


def write_outputs(out_dir, sens, fomc, meta, stamp=None):
    """Backup -> temp -> read back + compare -> os.replace (sens, fomc, then the sidecar). Rolls back on failure."""
    os.makedirs(out_dir, exist_ok=True)
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    targets = [(SENS_NAME, sens), (FOMC_NAME, fomc)]
    bdir = os.path.join(out_dir, "_backup", stamp)
    had = [n for n, _ in targets + [(META_NAME, None)] if os.path.exists(os.path.join(out_dir, n))]
    if had:
        os.makedirs(bdir, exist_ok=True)
        for n in had:
            shutil.copy2(os.path.join(out_dir, n), os.path.join(bdir, n))
    tmps = []
    try:
        for n, df in targets:
            tmp = os.path.join(out_dir, f".{n}.{os.getpid()}.tmp")
            df.to_parquet(tmp)
            back = pd.read_parquet(tmp)
            pd.testing.assert_frame_equal(back, df, check_exact=True)
            tmps.append((tmp, n))
        mtmp = os.path.join(out_dir, f".{META_NAME}.{os.getpid()}.tmp")
        with open(mtmp, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1, sort_keys=True)
        tmps.append((mtmp, META_NAME))
    except Exception:
        for tmp, _ in tmps:
            _silent_remove(tmp)
        raise
    done = []
    try:
        for tmp, n in tmps:
            os.replace(tmp, os.path.join(out_dir, n))
            done.append(n)
    except Exception:
        for n in done:                                     # roll back what was already replaced
            src = os.path.join(bdir, n)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(out_dir, n))
            else:
                _silent_remove(os.path.join(out_dir, n))
        for tmp, _ in tmps:
            _silent_remove(tmp)
        raise
    _prune(os.path.join(out_dir, "_backup"), KEEP_BACKUPS)
    return bdir if had else None


def _silent_remove(p):
    try:
        os.remove(p)
    except OSError:
        pass


# =============================================================================== lock (standalone runs only)
class RepoLock:
    """Global\\LTCMA_REPO_LOCK, the mutex daily_refresh.ps1 / weekly_model_rebuild.ps1 take. Only for a standalone
    run: a child of a ps1 that already holds it must NOT ask (a mutex is owned per thread; the child would wait)."""
    NAMES = ("Global\\LTCMA_REPO_LOCK", "Local\\LTCMA_REPO_LOCK")

    def __init__(self, timeout_s=25 * 60, names=None):
        self.timeout_s, self.h, self.names = timeout_s, None, tuple(names or self.NAMES)

    def __enter__(self):
        if os.name != "nt":
            return self
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        for name in self.names:
            h = k32.CreateMutexW(None, False, name)
            if not h:
                continue
            r = k32.WaitForSingleObject(ctypes.c_void_p(h), int(self.timeout_s * 1000))
            if r in (0, 0x80):                             # WAIT_OBJECT_0 / WAIT_ABANDONED = owned
                self.h, self.k32 = h, k32
                return self
            k32.CloseHandle(ctypes.c_void_p(h))
            raise Refused(f"repo lock {name} not acquired within {self.timeout_s}s")
        raise Refused("could not open the repo lock mutex")

    def __exit__(self, *a):
        if self.h:
            import ctypes
            self.k32.ReleaseMutex(ctypes.c_void_p(self.h))
            self.k32.CloseHandle(ctypes.c_void_p(self.h))
            self.h = None
        return False


def regression_span(snap):
    """First / last session that enters the regressions (all three factors and at least one stock return)."""
    cad = cad_for_regression(snap["cad"], snap["manifest"].get("cad_source"))
    f = pd.DataFrame({"a": snap["dgs10"].dropna().diff(), "b": snap["dxy"].ffill().pct_change(fill_method=None),
                      "c": cad.pct_change(fill_method=None)})
    r = snap["prices"].ffill().pct_change(fill_method=None)
    p = f.join(r, how="inner").dropna(how="all").dropna(subset=["a", "b", "c"])
    return (p.index.min().date().isoformat(), p.index.max().date().isoformat()) if len(p) else (None, None)


# =============================================================================== main
def default_asof(today=None):
    return ((today or date.today()) - timedelta(days=1)).isoformat()


def run(asof, out_dir, snapshot_dir=None, from_snapshot=None, dry_run=False, cad_source=CAD_SOURCE,
        fomc_dates=FOMC_DATES, full_info=None, fetch=None):
    """One refresh. Returns (code, summary dict). Never raises for a refusal: alerts and returns 1."""
    t0 = time.time()
    try:
        if from_snapshot:
            snapdir = from_snapshot
            man = None
        else:
            snapdir = snapshot_dir or os.path.join(out_dir, "_snapshots", asof)
            man = (fetch or fetch_snapshot)(asof, snapdir, cad_source=cad_source, full_info=full_info)
            log(f"fetched snapshot {snapdir}: {man['requests']} request(s), {man['seconds']}s")
        snap = load_snapshot(snapdir)
        asof = snap["manifest"].get("asof", asof)
        sens, fomc = build(snap, fomc_dates=fomc_dates)
        prev_sens, prev_fomc = _read_prev(out_dir)
        bad = validate(snap, sens, fomc, asof, prev_sens, prev_fomc, fomc_dates=fomc_dates)
        if bad:
            raise Refused("; ".join(bad))
    except Exception as e:                                              # noqa: BLE001  (a refusal or any failure)
        why = str(e) if isinstance(e, Refused) else f"error {type(e).__name__}: {e}"
        prev = _prev_through(out_dir)
        _alert(f"NOT refreshed ({why[:600]}); previous files kept{(' (data through ' + prev + ')') if prev else ''}")
        return 1, {"refused": why}
    newest = snap["prices"].dropna(how="all").index.max().date().isoformat()
    span = list(regression_span(snap))
    meta = {"schema_version": SCHEMA_VERSION, "data_through": newest, "asof": asof,
            "prices_through": newest, "betas_through": span[1],
            "pre_listing": "dropped" if DROP_PRE_LISTING else "measured from first trading day",
            "built_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "n_tickers": int(len(sens)), "n_fomc_meetings": int(fomc["fomc"].nunique()),
            "fomc_last": fomc["fomc"].max().date().isoformat(),
            "regression_span": span, "cad_source": snap["manifest"].get("cad_source"),
            "snapshot": os.path.abspath(snapdir), "snapshot_manifest_sha256": _sha256(os.path.join(snapdir, "manifest.json")),
            "producer": "LTCMA-website/scripts/capstone_inputs_refresh.py (port of ~/capstone/analytics/"
                        "build_stock_sensitivities.py)",
            "transport": snap["manifest"].get("transport"),
            # an offline rebuild makes no request: say so, and keep the snapshot's own fetch counts apart
            "requests": ({"yahoo": 0, "fred": 0} if from_snapshot else snap["manifest"].get("requests")),
            "snapshot_requests": snap["manifest"].get("requests")}
    summary = {"data_through": newest, "n_tickers": len(sens), "fomc_rows": len(fomc),
               "fomc_meetings": meta["n_fomc_meetings"], "fomc_last": meta["fomc_last"],
               "seconds": round(time.time() - t0, 1), "requests": meta["requests"]}
    w = calendar_warning(asof, fomc_dates)
    if w:
        _alert("WARN " + w)
    if dry_run:
        log(f"DRY RUN OK: {summary}; nothing written")
        return 0, dict(summary, sens=sens, fomc=fomc, meta=meta)
    try:
        bdir = write_outputs(out_dir, sens, fomc, meta)
    except Exception as e:                                              # noqa: BLE001
        _alert(f"NOT refreshed (write failed: {type(e).__name__}: {e}); previous files restored")
        return 1, {"refused": f"write failed: {e}"}
    if not from_snapshot:
        _prune(os.path.join(out_dir, "_snapshots"), KEEP_SNAPSHOTS)
    log(f"written {out_dir}: {summary}; backup {bdir}")
    return 0, dict(summary, sens=sens, fomc=fomc, meta=meta, backup=bdir)


def _prev_through(out_dir):
    try:
        with open(os.path.join(out_dir, META_NAME), encoding="utf-8") as fh:
            return json.load(fh).get("data_through")
    except Exception:                                                   # noqa: BLE001
        p = os.path.join(out_dir, SENS_NAME)
        return datetime.fromtimestamp(os.path.getmtime(p)).date().isoformat() + " (file date)" \
            if os.path.exists(p) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--asof", default=None, help="last completed session to include (default: yesterday)")
    ap.add_argument("--out-dir", default=os.environ.get("CAPSTONE_ANA", ANA))
    ap.add_argument("--snapshot-dir", default=None)
    ap.add_argument("--from-snapshot", default=None, help="offline rebuild from a saved snapshot dir")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cad-source", default=CAD_SOURCE, choices=("yahoo", "fred"))
    ap.add_argument("--lock", action="store_true", help="take Global\\LTCMA_REPO_LOCK (standalone runs only)")
    a = ap.parse_args(argv)
    asof = a.asof or default_asof()
    try:
        datetime.strptime(asof, "%Y-%m-%d")
    except ValueError:
        print("--asof must be YYYY-MM-DD", file=sys.stderr)
        return 2
    if a.lock:
        try:
            with RepoLock():
                return run(asof, a.out_dir, a.snapshot_dir, a.from_snapshot, a.dry_run, a.cad_source)[0]
        except Refused as e:
            _alert(f"NOT refreshed ({e})")
            return 1
    return run(asof, a.out_dir, a.snapshot_dir, a.from_snapshot, a.dry_run, a.cad_source)[0]


if __name__ == "__main__":
    sys.exit(main())
