"""picks_overlays -- display-only overlays for the Stock Research page (wave 13, 2026-11-04).

Earnings, analyst sentiment, price targets, insider trades and congressional trades for every name in the
universe. NONE of them feeds the composite, the ranks or the confidential weights; the page says so.

Sources and cost per daily build (after picker.build_universe() has passed its publish floor):
  targets, next-earnings timestamp, split facts  0 extra requests: already in the picker's Yahoo .info
                                                 (financialData + v7 quote + defaultKeyStatistics)
  earnings history / EPS revisions / analyst     ONE combined Yahoo quoteSummary call per ticker
    trend / up-downgrades                        (QS_MODULES), crumb shared with the picker: <= 40 requests
  SPY closes (benchmark for since-entry returns) one Yahoo chart request (+1 time-zone lookup when the
                                                 yfinance tz cache is cold)
  insiders                                       SEC EDGAR via insider_form4 (own budget, own cache)
  congress                                       local data/market_intel/congress_public.json (0 requests)
Every Yahoo request goes through yahoo_session (honest transport); a block stops Yahoo for the rest of the
process and every cell that needed it says "not available today (data gap)". Nothing is cached from one day
to the next on the Yahoo side, so a value is never shown as today's when it was not fetched today. Each
overlay carries its own as-of date.
News sentiment: NOT covered. No honest, reproducible, licence-clean per-ticker source was found (wave-13
source scout); the page labels it.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
import yahoo_session as ys

try:
    from paths import DATA
except ImportError:
    DATA = Path(__file__).resolve().parent.parent / "data"

QS_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
QS_MODULES = "calendarEvents,earningsHistory,earningsTrend,recommendationTrend,upgradeDowngradeHistory"
CONGRESS = DATA / "market_intel" / "congress_public.json"
CONGRESS_PAGE = "congressional-activity.html"
CONGRESS_ALIASES = {"GOOGL": ("GOOGL", "GOOG")}
NY = ZoneInfo("America/New_York")
MX = ZoneInfo("America/Mexico_City")
# earnings session rules (Trading_Index/rotation/events_config.yaml earnings.timing, US-listed names)
US_BMO_BEFORE, US_AMC_FROM, US_CLOSE, MIN_TIME = (9, 30), (15, 0), (16, 0), (4, 0)
NEWS = {"status": "gap", "permanent": True,
        "why": "not covered: no honest, reproducible per-ticker news source (headlines are copyrighted, "
               "results are not reproducible and are mostly market-wide)"}
SIDE = {"P": "buy", "S": "sell", "S-partial": "partial sale", "E": "exchange"}
STALL_AFTER = 3                      # consecutive network failures (no HTTP answer) that stop a source this run
NOT_YAHOO = " (site data gap, not a Yahoo transport issue)"      # tag for non-Yahoo lines in YAHOO_ALERT.txt


def _r(v):
    return v.get("raw") if isinstance(v, dict) else v


def _f(v):
    v = _r(v)
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def gap(why, **kw):
    return {"status": "gap", "why": why, **kw}


# ============================================================ Yahoo fetches
def fetch_quote_summaries(tickers, log=print):
    """One combined quoteSummary per ticker through the honest session. -> ({tk: result|gap}, report)."""
    from yfinance.data import YfData
    d = YfData(session=ys.SESSION)
    out, n0, t0 = {}, ys.status()["requests"], time.time()
    errs = Counter()
    fails = 0                                    # consecutive network-level failures (no HTTP answer at all)
    for tk in tickers:
        blk = ys.blocked()
        if blk:
            out[tk] = gap(f"Yahoo blocked this run ({blk})")
            errs["blocked"] += 1
            continue
        if fails >= STALL_AFTER:
            # Yahoo is not answering: stop asking (no retry policy) instead of spending 30 s per ticker
            out[tk] = gap(f"Yahoo not answering ({STALL_AFTER} network failures in a row); not asked again this run")
            errs["stalled"] += 1
            continue
        try:
            r = d.get(QS_URL.format(sym=tk), params={"modules": QS_MODULES, "corsDomain": "finance.yahoo.com",
                                                     "formatted": "false", "symbol": tk}, timeout=30)
        except ys.YahooBlocked as e:
            out[tk] = gap(f"Yahoo blocked this run ({e})")
            errs["blocked"] += 1
            continue
        except Exception as e:                                          # noqa: BLE001
            out[tk] = gap(f"Yahoo request failed ({type(e).__name__})")
            errs[type(e).__name__] += 1
            fails += 1
            continue
        fails = 0
        if r.status_code != 200:
            out[tk] = gap(f"Yahoo answered HTTP {r.status_code}")
            errs[f"HTTP {r.status_code}"] += 1
            continue
        try:
            res = (r.json().get("quoteSummary") or {}).get("result") or []
            out[tk] = {"status": "ok", "res": res[0], "at": datetime.now(timezone.utc)} if res else \
                gap("Yahoo returned no quoteSummary result")
        except ValueError:
            out[tk] = gap("Yahoo answered a non-JSON body")
            errs["non-JSON"] += 1
    rep = {"requests": ys.status()["requests"] - n0, "seconds": round(time.time() - t0, 1),
           "ok": sum(1 for v in out.values() if v["status"] == "ok"), "errors": dict(errs)}
    log(f"overlays: Yahoo quoteSummary {rep['ok']}/{len(tickers)} ok, {rep['requests']} requests, "
        f"{rep['seconds']} s, errors {rep['errors'] or 'none'}")
    return out, rep


def fetch_spy(start, log=print):
    """SPY daily closes (unadjusted Close: price return, like the page's own prices) from `start`."""
    n0 = ys.status()["requests"]
    if ys.blocked():
        return None, f"Yahoo blocked this run ({ys.blocked()})", 0
    try:
        h = yf.Ticker("SPY", session=ys.SESSION).history(start=str(start), auto_adjust=False, actions=False)
    except ys.YahooBlocked as e:
        return None, f"Yahoo blocked this run ({e})", ys.status()["requests"] - n0
    except Exception as e:                                              # noqa: BLE001
        return None, f"SPY history failed ({type(e).__name__})", ys.status()["requests"] - n0
    n = ys.status()["requests"] - n0
    if h is None or h.empty or "Close" not in h:
        return None, "SPY history came back empty", n
    s = h["Close"].dropna()
    s.index = [pd.Timestamp(x).strftime("%Y-%m-%d") for x in s.index]
    log(f"overlays: SPY {len(s)} closes {s.index[0]}..{s.index[-1]} ({n} request(s))")
    return s, None, n


# ============================================================ earnings
def _et(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).astimezone(NY)


def _hm(t):
    return (t.hour, t.minute)


def earnings_session(rel, call=None):
    """US session of a Yahoo earningsDate session code (never a release time): before the open / after the
    close / during the session / unknown. Ported from rotation/extract_events.earnings_timing (US branch)."""
    if rel is None or _hm(rel) < MIN_TIME:
        return "unknown"
    if call is not None and (call.replace(second=0, microsecond=0) == rel.replace(second=0, microsecond=0)
                             or (_hm(rel) >= US_AMC_FROM and call <= rel) or _hm(call) < MIN_TIME
                             or call.date() != rel.date()):
        call = None                                                     # placeholder / not credible
    if rel.weekday() >= 5:
        return "bmo"                                                    # dated on a weekend: before next open
    code = min([rel] + ([call] if call else []))
    if _hm(code) < US_BMO_BEFORE:
        return "bmo"
    if _hm(code) >= US_AMC_FROM and not (call and _hm(call) < US_CLOSE):
        return "amc"
    return "intraday"


def parse_earnings(tk, info, qs, today):
    """Next report (date, session, estimated?, days to it), last 4 EPS surprises, EPS revisions."""
    res = qs.get("res") if qs and qs.get("status") == "ok" else None
    codes, calls, est, src = [], [], None, None
    if res:
        ce = (res.get("calendarEvents") or {}).get("earnings") or {}
        codes = [int(_r(x)) for x in ce.get("earningsDate") or [] if _r(x)]
        calls = [int(_r(x)) for x in ce.get("earningsCallDate") or [] if _r(x)]
        est = ce.get("isEarningsDateEstimate")
        src = "Yahoo calendarEvents"
    if not codes and info:
        for k in ("earn_ts_start", "earn_ts", "earn_ts_end"):
            v = _f(info.get(k))
            if v:
                codes.append(int(v))
        codes = sorted(set(codes))
        c = _f(info.get("earn_call_ts"))
        calls = [int(c)] if c else []
        est = info.get("earn_is_est")
        src = "Yahoo quote"
    out = {"status": "ok", "source": src, "as_of": today.isoformat()}
    fut = sorted(x for x in codes if _et(x).date() >= today)
    if fut:
        rel = _et(fut[0])
        call = next((_et(c) for c in calls if _et(c).date() == rel.date()), None)
        out["next"] = {"date": rel.date().isoformat(), "session": earnings_session(rel, call),
                       "estimated": bool(est) if est is not None else None,
                       "window_end": _et(fut[-1]).date().isoformat() if len(fut) > 1 else None,
                       "days": (rel.date() - today).days}
    elif codes:
        out["next"] = None
        out["last_listed"] = _et(max(codes)).date().isoformat()
    else:
        out["next"] = None
    if res:
        hist = []
        for h in (res.get("earningsHistory") or {}).get("history") or []:
            q = _f(h.get("quarter"))
            hist.append({"quarter": datetime.fromtimestamp(int(q), timezone.utc).date().isoformat() if q else None,
                         "actual": _f(h.get("epsActual")), "estimate": _f(h.get("epsEstimate")),
                         "surprise": _f(h.get("surprisePercent"))})
        hist = [h for h in hist if h["actual"] is not None and h["estimate"] is not None]
        hist.sort(key=lambda h: h["quarter"] or "")
        out["history"] = hist[-4:]
        out["beats"] = sum(1 for h in out["history"] if h["actual"] > h["estimate"])
        rev = {}
        for t in (res.get("earningsTrend") or {}).get("trend") or []:
            if t.get("period") not in ("0q", "+1q", "0y", "+1y"):
                continue
            tr, rv = t.get("epsTrend") or {}, t.get("epsRevisions") or {}
            now_, d30, d90 = _f(tr.get("current")), _f(tr.get("30daysAgo")), _f(tr.get("90daysAgo"))
            rev[t["period"]] = {
                "end": t.get("endDate"), "eps": now_,
                "chg30": (now_ / d30 - 1) if (now_ is not None and d30 and d30 > 0) else None,
                "chg90": (now_ / d90 - 1) if (now_ is not None and d90 and d90 > 0) else None,
                "up30": _f(rv.get("upLast30days")), "down30": _f(rv.get("downLast30days")),
                "n": _f((t.get("earningsEstimate") or {}).get("numberOfAnalysts"))}
        out["revisions"] = rev
    else:
        out["history"], out["revisions"] = None, None
        out["partial"] = qs.get("why") if qs else "combined Yahoo call not made"
    if not res and not codes:
        return gap((qs or {}).get("why") or "no earnings data from Yahoo today")
    return out


# ============================================================ sentiment + targets
def parse_sentiment(tk, info, qs, today):
    res = qs.get("res") if qs and qs.get("status") == "ok" else None
    if not res:
        return gap((qs or {}).get("why") or "combined Yahoo call not made")
    out = {"status": "ok", "as_of": today.isoformat(), "source": "Yahoo Finance (recommendationTrend, "
           "upgradeDowngradeHistory)", "rec_mean": _f((info or {}).get("rec_mean")),
           "rec_key": (info or {}).get("rec_key")}
    tr = {t.get("period"): t for t in (res.get("recommendationTrend") or {}).get("trend") or []}

    def mix(t):
        if not t:
            return None
        b = int(t.get("strongBuy") or 0) + int(t.get("buy") or 0)
        h = int(t.get("hold") or 0)
        s = int(t.get("sell") or 0) + int(t.get("strongSell") or 0)
        n = b + h + s
        return {"buy": b, "hold": h, "sell": s, "n": n, "buy_share": b / n if n else None}
    out["mix_now"], out["mix_3m"] = mix(tr.get("0m")), mix(tr.get("-3m"))
    ud = (res.get("upgradeDowngradeHistory") or {}).get("history") or []
    now_e = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).timestamp() + 86400
    for days in (30, 90):
        rec = [h for h in ud if (_f(h.get("epochGradeDate")) or 0) >= now_e - days * 86400]
        out[f"d{days}"] = {"up": sum(1 for h in rec if h.get("action") == "up"),
                           "down": sum(1 for h in rec if h.get("action") == "down"),
                           "init": sum(1 for h in rec if h.get("action") == "init"),
                           "pt_up": sum(1 for h in rec if h.get("priceTargetAction") == "Raises"),
                           "pt_down": sum(1 for h in rec if h.get("priceTargetAction") == "Lowers"),
                           "n": len(rec)}
    out["news"] = NEWS
    return out


def parse_targets(tk, info, price, today):
    """Yahoo analyst consensus (aggregates only: no firm names) + the picker's own model value."""
    info = info or {}
    mean, lo, hi = _f(info.get("tgt_mean")), _f(info.get("tgt_low")), _f(info.get("tgt_high"))
    med, n = _f(info.get("tgt_median")), _f(info.get("n_analysts"))
    iv = _f(info.get("iv"))
    out = {"status": "ok" if mean else "gap", "as_of": today.isoformat(), "price": price,
           "source": "Yahoo Finance analyst consensus (12-month targets)"}
    if mean:
        out.update(mean=mean, median=med, low=lo, high=hi, n=int(n) if n else None,
                   upside=(mean / price - 1) if price else None,
                   low_up=(lo / price - 1) if (lo and price) else None,
                   high_up=(hi / price - 1) if (hi and price) else None)
    else:
        out["why"] = "Yahoo shows no analyst target for this name today"
    out["model"] = {"iv": iv, "upside": (iv / price - 1) if (iv and price) else None}
    return out


# ============================================================ congress
def load_congress(path=None):
    try:
        return json.loads(Path(path or CONGRESS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def parse_congress(tk, c, today):
    if c is None:
        return gap("congress_public.json not available")
    asof = c.get("as_of")
    names = CONGRESS_ALIASES.get(tk, (tk,))
    rows = [r for r in c.get("rows") or [] if r.get("ticker") in names]
    filed = [r["filed_date"] for r in c.get("rows") or [] if r.get("filed_date")]
    out = {"status": "ok", "as_of": asof, "window": [min(filed), max(filed)] if filed else None,
           "source": "House Clerk PTRs + Senate open dataset (mirror rows marked with a dagger)",
           "n": len(rows)}
    try:
        age = (today - date.fromisoformat(asof)).days
    except (TypeError, ValueError):
        age = None
    out["stale"] = age is not None and age > 10
    out["age_days"] = age
    side = Counter(r.get("direction") for r in rows)
    out["buys"], out["sells"] = side.get("P", 0), side.get("S", 0) + side.get("S-partial", 0)
    out["other"] = len(rows) - out["buys"] - out["sells"]
    out["members"] = len({r.get("member") for r in rows})
    # PTR owner: self / SP spouse / JT joint / DC dependent child (most rows are not the member's own account)
    out["owners"] = dict(Counter(r.get("owner") or "not_indicated" for r in rows))
    out["chambers"] = dict(Counter(r.get("chamber") or "House" for r in rows))
    out["bands"] = dict(Counter(r.get("amount") for r in rows).most_common())
    out["mirror"] = sum(1 for r in rows if r.get("via") == "mirror")
    out["last_filed"] = max((r.get("filed_date") or "" for r in rows), default=None) or None
    out["detail"] = [{"filed": r.get("filed_date"), "traded": r.get("tx_date"), "member": r.get("member"),
                      "party": r.get("party"), "state": r.get("state_dst"), "chamber": r.get("chamber") or "House",
                      "side": SIDE.get(r.get("direction"), r.get("direction")), "amount": r.get("amount"),
                      "type": r.get("asset_type"), "owner": r.get("owner"), "source": r.get("source"),
                      "mirror": r.get("via") == "mirror", "ticker": r.get("ticker")}
                     for r in sorted(rows, key=lambda r: (r.get("filed_date") or "", r.get("tx_date") or ""),
                                     reverse=True)[:12]]
    return out


# ============================================================ orchestration
def info_of(df, tk):
    keys = ("tgt_mean", "tgt_median", "tgt_low", "tgt_high", "n_analysts", "rec_mean", "rec_key", "iv",
            "earn_ts", "earn_ts_start", "earn_ts_end", "earn_is_est", "earn_call_ts")
    r = df.loc[tk]
    return {k: (None if (k not in r.index or (isinstance(r[k], float) and np.isnan(r[k]))) else r[k]) for k in keys}


def spy_start_for(history_start, today):
    """SPY must reach back to the FIRST snapshot of the history (a fixed lookback would make SPY vanish for
    every long-tenure pick once the history outgrows it), with a week of margin; never later than 200 days
    back, so a short history still gets a full chart."""
    lo = today - timedelta(days=200)
    try:
        hs = date.fromisoformat(str(history_start)[:10]) - timedelta(days=7)
    except (TypeError, ValueError):
        return lo.isoformat()
    return min(hs, lo).isoformat()


def build(df, now=None, log=print, sec_budget=160, sec_max_xml=120, offline=False, qs=None, spy=None,
          sec_client=None, cache_root=None, spy_start=None, alert=None):
    """All overlays for every ticker in the picker df. Never raises for a data problem: a failed source is a
    gap in the cells that need it. `qs` / `spy` let tests inject recorded answers (offline). `spy_start` = the
    history's first snapshot date (SPY is fetched from there: still one chart request).
    meta["gaps"] holds (overlay, PUBLIC wording) pairs: fixed phrases and exception TYPES only. The full
    exception text goes to the log and the alert line, never to the page (a path or a long decimal there would
    leak a local path / trip guard_decimals)."""
    import insider_form4 as f4
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(MX).date()
    tickers = list(df.index)
    meta = {"gaps": [], "yahoo": {}, "sec": {}, "spy": {}}
    alert = alert or (None if offline else ys.alert)
    detail = []                                    # (overlay, full text) for the log / alert only
    # Yahoo: SPY first (chart bars need no crumb), then the combined calls
    if spy is None and not offline:
        start = spy_start_for(spy_start, today)
        spy, why, n = fetch_spy(start, log)
        meta["spy"] = {"requests": n, "why": why, "start": start}
        if why:
            meta["gaps"].append(("spy", why))
    elif spy is None:
        meta["spy"] = {"why": "offline"}
    if qs is None and not offline:
        qs, meta["yahoo"] = fetch_quote_summaries(tickers, log)
    elif qs is None:
        qs = {tk: gap("offline build: Yahoo not asked") for tk in tickers}
    bad = [tk for tk in tickers if (qs.get(tk) or {}).get("status") != "ok"]
    if bad:
        why = Counter((qs.get(tk) or {}).get("why") or "missing" for tk in bad).most_common(1)[0][0]
        meta["gaps"].append(("yahoo_extras", f"{len(bad)}/{len(tickers)} tickers ({why})"))
    # SEC
    kw = {"cache_root": cache_root} if cache_root else {}
    try:
        cache, srep = f4.refresh(tickers, now=now, budget=sec_budget, max_xml=sec_max_xml, offline=offline,
                                 client=sec_client, alert=None, log=log, pick_set=tickers[:20], **kw)
    except Exception as e:                                              # noqa: BLE001
        cache, srep = None, {"error": type(e).__name__}
        meta["gaps"].append(("insiders", f"SEC overlay failed ({type(e).__name__})"))
        detail.append(("insiders", f"SEC overlay failed: {type(e).__name__}: {str(e)[:200]}"))
    meta["sec"] = srep
    if srep.get("blocked"):
        meta["gaps"].append(("insiders", f"SEC {srep['blocked']}"))
    if srep.get("stalled"):
        meta["gaps"].append(("insiders", f"SEC {srep['stalled']}"))
    if srep.get("paused"):
        meta["gaps"].append(("insiders", f"SEC not asked this run: {srep['paused']}"))
    log(f"overlays: SEC {srep.get('requests', 0)} requests ({srep.get('submissions', 0)} filing lists, "
        f"{srep.get('xml_fetched', 0)} Form 4 XML, {srep.get('xml_left', 0)} left for later runs, "
        f"{srep.get('rotation_filings_reused', 0)} filings reused from the rotation store), "
        f"blocked {srep.get('blocked')}")
    cong = load_congress()
    if cong is None:
        meta["gaps"].append(("congress", "congress_public.json not available"))
    by = {}
    for tk in tickers:
        info = info_of(df, tk)
        price = float(df.loc[tk, "price"])
        o = {}
        for name, fn in (("earnings", lambda: parse_earnings(tk, info, qs.get(tk), today)),
                         ("sentiment", lambda: parse_sentiment(tk, info, qs.get(tk), today)),
                         ("targets", lambda: parse_targets(tk, info, price, today)),
                         ("congress", lambda: parse_congress(tk, cong, today)),
                         ("insiders", lambda: f4.aggregate(cache, tk, now, srep) if cache is not None
                          else gap(f"SEC overlay failed ({srep.get('error')})"))):
            try:
                o[name] = fn()
            except Exception as e:                                      # noqa: BLE001
                o[name] = gap(f"overlay error ({type(e).__name__})")
                meta["gaps"].append((name, f"{tk}: {type(e).__name__}"))
                detail.append((name, f"{tk}: {type(e).__name__}: {str(e)[:200]}"))
        by[tk] = o
    for name, why in detail:
        log(f"stocks overlay error detail: {name}: {why}")
    for name, why in meta["gaps"]:
        tag = "" if name in ("spy", "yahoo_extras") else NOT_YAHOO
        msg = f"stocks overlay data gap: {name}: {why}{tag}"
        log(msg)
        if alert:
            alert(msg)
    return {"by_ticker": by, "spy": spy, "meta": meta, "today": today}
