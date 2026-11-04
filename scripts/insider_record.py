"""insider_record -- each shown insider's own past record in the stock (wave 14, 2026-11-04).

Carlos (2026-11-04): "Nombre mas cargo y chance su hit rate si lo tienes". Names as filed and the role were
already shown (insider_form4.SHOW_NAMES). This adds, for every insider in the detail table of a ticker, how that
person's OWN past open-market trades in that issuer were followed by the stock. Descriptive, small-sample,
not a forecast. Display-only: it never feeds the composite, the ranks, the weights or the list membership.

RULES (all fixed BEFORE any result was computed; nothing here was tuned on what it shows)
  * Horizon: ONE horizon, HORIZON_TD = 60 NYSE trading days (about one quarter). Why: long enough that the
    two-business-day Form 4 filing lag and day-to-day noise do not decide the outcome; short enough that
    trades in the site's SEC cache (Form 4s filed in the last ~200 days, the 180-day backfill) can complete it
    (a 120- or 250-day horizon would leave almost no completed trade); one fixed horizon, so there is no
    choosing the horizon that looks best.
  * Trade: one insider (reporting-owner CIK), one transaction date, one side; every Form 4 line of that day and
    side counts once (insider_form4.trade_events: the page's own P / S filters, non-market purchases out).
  * Outcome: excess = stock return - SPY return, both price only (no dividends), from the close of the
    transaction day (the first NYSE session on or after the transaction date) to the close HORIZON_TD
    sessions later. A purchase (code P) is a hit when excess > 0; a sale (code S) when excess < 0. Only
    completed horizons count (the end session is on or before the last completed session of the build).
  * 10b5-1 plan trades (the filing's Rule 10b5-1 box, or a footnote saying the trade was under such a plan)
    are NOT counted: they are scheduled months ahead (a cooling-off period applies), so their timing says
    little about the insider's own view on that day. Their number is shown next to the record.
  * Round 2 (main-session design choice D2 within Carlos's OK "hit rate si lo tienes"): the number of
    INDEPENDENT (non-overlapping) 60-day windows comes first, and "k of n" is shown only when it is >= MIN_INDEP
    (3); otherwise "too few independent trades (n trades, m windows)". Never a percentage. Next to it: the
    window covered (first to last counted trade). Trades close together share most of their window, so a
    trade count overstates the evidence. Revert: MIN_INDEP = 0 shows k of n from MIN_N trades again.
PRICES (honest, cheap)
  1. the cached Yahoo daily chart of the stock (.cache/insider_px/<TICKER>.json, git-ignored), when it holds
     both dates. One chart request per ticker, made at most once per day and only when a completed trade of a
     shown insider cannot be priced from the cache or from (2); bars after the last completed session are
     never stored. In practice: once, for the trades older than the page's own history.
  2. the page's own history (data/picks_history.csv, since 2026-06-04: build-time closes, Yahoo-confirmed
     splits applied; a window across a price break is n/a).
  Otherwise the trade is "not priced" (counted apart, never guessed). SPY: the build's own SPY closes (the
  existing single chart request, started early enough for the oldest trade). A trade whose SPY window is not
  covered never triggers a stock chart request (the stock chart cannot fix it).
  Round 2 (D4): after a chart request for a ticker, every trade that is still not priced is marked unpriceable
  in that ticker's cache file (the date of the attempt) and is not retried for RETRY_DAYS (7); a failed or empty
  answer marks them too (a Yahoo block does not: nothing was answered). An empty frame counts toward the
  STALL_AFTER (3) failures in a row that stop the requests for the rest of the build.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from paths import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

import picks_history as ph

HORIZON_TD = 60
MIN_N = 3                       # trades (kept for the tooltip / tests); the display rule is MIN_INDEP
MIN_INDEP = 3                   # independent (non-overlapping) windows needed to show "k of n"
PX_CACHE = ROOT / ".cache" / "insider_px"
STALL_AFTER = 3
RETRY_DAYS = 7                  # an unpriceable trade is asked for again no sooner than this
GAP_KINDS = ("blocked", "failed", "empty")


# ------------------------------------------------------------------------------------------- calendar
def session_on_or_after(d):
    d = date.fromisoformat(str(d)[:10])
    while not ph.is_trading_day(d):
        d += timedelta(days=1)
    return d.isoformat()


def nth_session_after(s0, n=HORIZON_TD):
    """The session n NYSE trading days after session s0."""
    d, k = date.fromisoformat(str(s0)[:10]), 0
    while k < n:
        d += timedelta(days=1)
        if ph.is_trading_day(d):
            k += 1
    return d.isoformat()


def last_complete_session(now):
    """The last session whose close has printed at build time `now` (aware)."""
    s, basis, _tier = ph.price_session(now)
    return s if basis == "close" else ph.prev_trading_day(s).isoformat()


# ------------------------------------------------------------------------------------------- price cache
def _cache_path(tk, root=None):
    return Path(root or PX_CACHE) / f"{tk}.json"


def load_px(tk, root=None):
    try:
        j = json.loads(_cache_path(tk, root).read_text(encoding="utf-8"))
        return j if isinstance(j.get("closes"), dict) else None
    except (OSError, ValueError, AttributeError):
        return None


def save_px(tk, closes, fetched_on, start, root=None, requests=None, unpriceable=None):
    p = _cache_path(tk, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {"ticker": tk, "fetched_on": fetched_on, "start": start, "requests": requests,
            "source": "Yahoo Finance chart (daily Close, split-adjusted at fetch, no dividends) via yahoo_session",
            "closes": {k: round(float(v), 4) for k, v in sorted(closes.items())},
            "unpriceable": dict(sorted((unpriceable or {}).items()))}
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=0, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def fetch_px(tk, start, last_session, log=print):
    """ONE Yahoo chart request through the honest session (same call as picks_overlays.fetch_spy). -> (closes
    {iso: close} up to last_session only, why|None, requests)."""
    import yahoo_session as ys
    import yfinance as yf
    n0 = ys.status()["requests"]
    if ys.blocked():
        return None, f"Yahoo blocked this run ({ys.blocked()})", 0
    end = (date.fromisoformat(last_session) + timedelta(days=1)).isoformat()
    try:
        h = yf.Ticker(tk, session=ys.SESSION).history(start=str(start), end=end, auto_adjust=False, actions=False)
    except ys.YahooBlocked as e:
        return None, f"Yahoo blocked this run ({e})", ys.status()["requests"] - n0
    except Exception as e:                                              # noqa: BLE001
        return None, f"price history failed ({type(e).__name__})", ys.status()["requests"] - n0
    n = ys.status()["requests"] - n0
    if ys.blocked():                              # yfinance swallows some errors: a block shows up here
        return None, f"Yahoo blocked this run ({ys.blocked()})", n
    if h is None or h.empty or "Close" not in h:
        return None, "price history came back empty", n
    s = h["Close"].dropna()
    out = {pd.Timestamp(x).strftime("%Y-%m-%d"): float(v) for x, v in s.items()}
    out = {k: v for k, v in out.items() if k <= last_session}       # never store a bar that is not a close yet
    return out, None, n


# ------------------------------------------------------------------------------------------- outcomes
def _ret_yahoo(px, s0, s1):
    c = (px or {}).get("closes") or {}
    a, b = c.get(s0), c.get(s1)
    return (b / a - 1) if (a and b) else None


def _ret_panel(panel, tk, s0, s1):
    if panel is None or tk not in panel.adj.columns or s0 not in panel.adj.index or s1 not in panel.adj.index:
        return None
    r = panel.window_ret(tk, s0, s1)
    return r if r == r else None


def _spy_ret(spy, s0, s1):
    if spy is None or not len(spy) or s0 not in spy.index or s1 not in spy.index:
        return None
    a, b = float(spy.loc[s0]), float(spy.loc[s1])
    return (b / a - 1) if a else None


def outcomes(events, spy, last_session, px=None, panel=None, horizon=HORIZON_TD):
    """events: insider_form4.trade_events rows (one ticker). -> DataFrame with s0, s1, status in
    {plan, pending, unpriced, done}, source, excess, hit."""
    rows = []
    for e in events.to_dict("records"):
        s0 = session_on_or_after(e["date"])
        s1 = nth_session_after(s0, horizon)
        r = {**e, "s0": s0, "s1": s1, "status": None, "source": None, "excess": np.nan, "hit": None, "need": None}
        if e["plan"]:
            r["status"] = "plan"
        elif s1 > last_session:
            r["status"] = "pending"
        else:
            sr = _spy_ret(spy, s0, s1)
            tr, src = _ret_yahoo(px, s0, s1), "yahoo_chart"
            if tr is None:
                tr, src = _ret_panel(panel, e["ticker"], s0, s1), "page_history"
            if tr is None or sr is None:
                r["status"] = "unpriced"
                r["need"] = "spy" if sr is None else "stock"   # only "stock" can be fixed by a stock chart
            else:
                x = tr - sr
                r.update(status="done", source=src, excess=x, hit=bool(x > 0) if e["side"] == "buy" else bool(x < 0))
        rows.append(r)
    return pd.DataFrame(rows)


def _nonoverlap(s0s, horizon=HORIZON_TD):
    """How many of the windows [s0, s0 + horizon] can be picked without overlapping (earliest first)."""
    n, nxt = 0, None
    for s in sorted(s0s):
        if nxt is None or s >= nxt:
            n += 1
            nxt = nth_session_after(s, horizon)
    return n


def summarise(oc):
    """One insider's outcomes -> the record dict the page prints."""
    done = oc[oc["status"] == "done"] if len(oc) else oc
    out = {"n": int(len(done)), "k": int(done["hit"].sum()) if len(done) else 0,
           "n_buy": int((done["side"] == "buy").sum()) if len(done) else 0,
           "k_buy": int(done[done["side"] == "buy"]["hit"].sum()) if len(done) else 0,
           "n_sell": int((done["side"] == "sell").sum()) if len(done) else 0,
           "k_sell": int(done[done["side"] == "sell"]["hit"].sum()) if len(done) else 0,
           "n_plan": int((oc["status"] == "plan").sum()) if len(oc) else 0,
           "n_pending": int((oc["status"] == "pending").sum()) if len(oc) else 0,
           "n_unpriced": int((oc["status"] == "unpriced").sum()) if len(oc) else 0,
           "first": str(done["date"].min()) if len(done) else None,
           "last": str(done["date"].max()) if len(done) else None,
           "n_indep": _nonoverlap(done["s0"].tolist()) if len(done) else 0,
           "horizon": HORIZON_TD, "min_indep": MIN_INDEP,
           "sources": sorted(set(done["source"])) if len(done) else []}
    out["show"] = out["n"] >= MIN_N and out["n_indep"] >= MIN_INDEP
    return out


def _key(r):
    """One trade's key in the unpriceable marks: insider, first session, side."""
    return f"{r['owner_cik']}|{r['s0']}|{r['side']}"


def _gap_kind(why):
    w = (why or "").lower()
    return "blocked" if w.startswith("yahoo blocked") else "empty" if "empty" in w else "failed"


def _due(oc, marks, today, retry_days=RETRY_DAYS):
    """Unpriced trades a stock chart could price that are not marked, or were marked >= retry_days ago."""
    if not len(oc):
        return oc
    need = oc[(oc["status"] == "unpriced") & (oc["need"] == "stock")]
    lim = (date.fromisoformat(today) - timedelta(days=retry_days)).isoformat()
    keep = [i for i, r in need.iterrows() if str(marks.get(_key(r), "0000-00-00")) <= lim]
    return need.loc[keep]


def build(cache, by_ticker, spy, now, panel=None, offline=False, log=print, px_root=None, fetch=None):
    """Records for every insider SHOWN (the detail lines of each ticker's insider overlay).
    by_ticker: {tk: insider overlay dict (insider_form4.aggregate)} -> ({tk: {owner_cik: record}}, report).
    fetch(tk, start, last_session, log) is the Yahoo chart call (tests inject a fake); offline = no fetch.
    Never raises for a data problem."""
    import insider_form4 as f4
    fetch = fetch or fetch_px
    last = last_complete_session(now)
    today = now.astimezone(ph.MX).date().isoformat()
    rep = {"requests": 0, "fetched": [], "gaps": [], "gap_kinds": [], "marked": 0, "last_session": last,
           "spy": spy is not None and len(spy) > 0}
    out, fails = {}, 0
    all_lines = cache.all_lines()                 # read once; trade_events filters it per ticker
    for tk, ins in by_ticker.items():
        if not ins or ins.get("status") not in ("ok", "partial"):
            continue
        owners = {d.get("owner_cik") for d in ins.get("detail") or [] if d.get("owner_cik")}
        if not owners:
            continue
        ev = f4.trade_events(cache, tk, all_lines)
        ev = ev[ev["owner_cik"].astype(str).isin(owners)]
        px = load_px(tk, px_root)
        oc = outcomes(ev, spy, last, px, panel) if len(ev) else pd.DataFrame()
        marks = dict((px or {}).get("unpriceable") or {})
        need = _due(oc, marks, today)
        if len(need) and not offline and spy is not None and len(spy) and fails < STALL_AFTER and \
                (px or {}).get("fetched_on") != today:
            start = (date.fromisoformat(min(need["s0"])) - timedelta(days=7)).isoformat()
            if px and px.get("start"):
                start = min(start, px["start"])
            closes, why, n = fetch(tk, start, last, log)
            rep["requests"] += n
            kind = None
            if closes:
                save_px(tk, closes, today, start, px_root, requests=n, unpriceable=marks)
                rep["fetched"].append(tk)
                fails = 0
                px = load_px(tk, px_root)
                oc = outcomes(ev, spy, last, px, panel)
            else:
                kind = _gap_kind(why)
                rep["gaps"].append(f"{tk}: {why}")
                rep["gap_kinds"].append(kind)
                fails = STALL_AFTER if kind == "blocked" else fails + 1      # failed AND empty count (D4)
            if kind != "blocked":                     # an answered (or failed) request: mark what is still unpriced
                still = oc[(oc["status"] == "unpriced") & (oc["need"] == "stock")] if len(oc) else oc
                if len(still):
                    marks.update({_key(r): today for _, r in still.iterrows()})
                    cur = load_px(tk, px_root) or {}
                    save_px(tk, cur.get("closes") or {}, cur.get("fetched_on"), cur.get("start") or start, px_root,
                            requests=cur.get("requests"), unpriceable=marks)
                    rep["marked"] += len(still)
        recs = {}
        for oc_cik in owners:
            sub = oc[oc["owner_cik"].astype(str) == str(oc_cik)] if len(oc) else oc
            recs[str(oc_cik)] = summarise(sub)
        out[tk] = recs
    log(f"insider records: {sum(len(v) for v in out.values())} insiders over {len(out)} tickers; Yahoo chart "
        f"requests {rep['requests']} ({', '.join(rep['fetched']) or 'none'}); gaps {len(rep['gaps'])}; "
        f"trades marked unpriceable {rep['marked']} (retried after {RETRY_DAYS} d)")
    return out, rep


# ------------------------------------------------------------------------------------------- wording
def _mon(d, year=True):
    x = date.fromisoformat(str(d)[:10])
    return x.strftime("%b %Y" if year else "%b")


def window_txt(r):
    if not r.get("first"):
        return ""
    a, b = r["first"], r["last"]
    if a[:7] == b[:7]:
        return _mon(a)
    return f"{_mon(a, a[:4] != b[:4])}–{_mon(b)}"


def record_txt(r, spy_ok=True):
    """The table cell (plain text; the caller escapes nothing here: no user text inside)."""
    if r is None:
        return "n/a"
    if not spy_ok:
        return "not available today (data gap)"
    extra = []
    if r.get("n_plan"):
        extra.append(f"{r['n_plan']} plan trade{'s' if r['n_plan'] != 1 else ''} not counted")
    if r.get("n_pending"):
        extra.append(f"{r['n_pending']} under {r['horizon']} td old")
    if r.get("n_unpriced"):
        extra.append(f"{r['n_unpriced']} not priced")
    tail = f" ({'; '.join(extra)})" if extra else ""
    m, n = int(r.get("n_indep") or 0), int(r.get("n") or 0)
    if not r.get("show"):
        return (f"too few independent trades ({n} trade{'s' if n != 1 else ''}, {m} window{'s' if m != 1 else ''})"
                f"{tail}")
    return (f"{m} independent window{'s' if m != 1 else ''} · {r['k']} of {n} trades right · {r['horizon']} td vs SPY"
            f" · {window_txt(r)}{tail}")
