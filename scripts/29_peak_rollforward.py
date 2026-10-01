# -*- coding: utf-8 -*-
"""Roll the validated peak-concurrent sidecar forward to today's marks. Runs DAILY.

Why this exists (2026-09-30): the Performance block of portfolio.html and the home
portfolio card read `real_numbers/peak_sidecar.json`. That file was produced by a MANUAL,
hand-dated chain (portfolio_updates/site_peakbase_<date>/_build: mxn_peak -> peak_curves ->
guards -> make_site_sidecar) that no scheduled job ran. So the page header said "As of
today" while the Performance block said "as of 2026-09-23" for a week, and every freshness
check passed because they only read the header stamp.

What this does -- and what it deliberately does NOT do:
  * The ANCHOR is the newest validated sidecar under site_peakbase_*/_build. It is never
    modified. Every run recomputes from it, so the roll is idempotent and a partial intraday
    bar is simply replaced by the final close on the next run.
  * Between the anchor and today NO FILL is allowed. The bases, cost, realized and the fill
    markers are the walk's; only PRICES and FX move. If any broker export in
    GBM_Account_Archive is newer than the anchor, this refuses (exit 3) -- new fills mean a
    re-walk through the guarded chain, and rolling across them would publish a book that
    does not exist.
  * LEVEL marks, as the broker values a position: shares x the SIC .MX quote (US close x
    MXN=X only where no .MX series exists -- CCJ), GMEXICOB.MX for the peso-native line.
    USD = MXN / MXN=X, the anchor's own convention. These per-position marks are ALSO what
    18_portfolio.py uses for the holdings table and the top tiles: one mark per page.
  * TWRR chains the new days (no flows), SPY's flow-matched book is marked forward with its
    share count, and every headline field 17/18 read is recomputed from the rolled curve.

Private in, private out: real pesos never touch the repo. Exit codes: 0 rolled or already
current, 3 refused (new fills), 4 pricing failed (sidecar left as-is, the page keeps its
honest older date and the refresh log says so).
"""
import glob, json, os, sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

UPD = paths.cuser("Documents", "portfolio_updates")
OUTF = paths.cuser("Documents", "CarlosDuarteWebsite", "real_numbers", "peak_sidecar.json")
POSF = paths.cuser("Documents", "CarlosDuarteWebsite", "real_numbers", "position_latest.json")
ARCH = paths.cuser("Documents", "GBM_Account_Archive")
NATIVE_YF = {"GMEXICOB": "GMEXICOB.MX"}


def _anchor():
    best = None
    for f in glob.glob(os.path.join(UPD, "site_peakbase_*", "_build", "peak_sidecar.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if best is None or d["as_of"] > best[1]["as_of"]:
            best = (f, d)
    if best is None:
        raise SystemExit("no validated anchor sidecar under site_peakbase_*/_build")
    return best


def _closes(sym, start):
    h = yf.download(sym, start=start, interval="1d", auto_adjust=True, progress=False)
    if isinstance(h.columns, pd.MultiIndex):
        h.columns = h.columns.get_level_values(0)
    s = h["Close"].dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated(keep="last")]


def main():
    af, A = _anchor()
    asof_a = pd.Timestamp(A["as_of"])
    print(f"  anchor: {af} (as_of {A['as_of']}, {len(A['curve'])} days)")

    # ---- no-new-fills precondition --------------------------------------------------
    amt = os.path.getmtime(af)
    newer = [p for p in glob.glob(os.path.join(ARCH, "**", "*.*"), recursive=True)
             if os.path.getmtime(p) > amt and Path(p).suffix.lower() in (".csv", ".xlsx", ".xls")
             and "_parsed" not in p]
    if newer:
        print(f"  REFUSED: {len(newer)} broker export(s) newer than the anchor, e.g. "
              f"{os.path.basename(newer[0])} -- new fills need a re-walk through the guarded "
              f"site_peakbase chain (WEBSITE_DEPLOY.md). Sidecar left as-is.")
        return 3
    ps = json.loads(Path(POSF).read_text(encoding="utf-8"))
    if ps["as_of"] != A["as_of"]:
        print(f"  REFUSED: position_latest.json as_of {ps['as_of']} != anchor {A['as_of']}")
        return 3

    # ---- market data from the anchor day on --------------------------------------------
    start = (asof_a - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        # from the curve's first day: spy_tr is cross-checked against Yahoo end to end
        spy = _closes("SPY", (pd.Timestamp(A["curve"][0]["d"]) - pd.Timedelta(days=7))
                      .strftime("%Y-%m-%d"))
        fx = _closes("MXN=X", start)
        px = {}
        for p in A["positions"]:
            sym = NATIVE_YF.get(p["ticker"]) if p["native"] else p["ticker"]
            px[p["ticker"]] = _closes(sym, start)
        # SIC venue quote (.MX): what the broker marks the position at. Used for the PESO
        # side whenever it has data at the anchor and recently; the US listing x FX is the
        # fallback (CCJ has no .MX). 2026-09-30: marking pesos with US x FX alone drifted
        # +0.57% (max 1.95%) above the .MX quotes within 5 sessions.
        sic = {}
        for p in A["positions"]:
            if p["native"]:
                continue
            try:
                s_mx = _closes(p["ticker"] + ".MX", start)
            except Exception:
                continue
            if not s_mx.loc[:asof_a].empty and s_mx.index.max() >= spy.index.max() - pd.Timedelta(days=4):
                sic[p["ticker"]] = s_mx
    except Exception as e:
        print(f"  pricing FAILED ({e}) -- sidecar left at {A['as_of']}")
        return 4
    days = spy.index[spy.index > asof_a]
    if len(days) == 0:
        Path(OUTF).write_text(json.dumps(A, indent=1), encoding="utf-8")
        print(f"  no US session after {A['as_of']} yet -- anchor republished unchanged")
        return 0
    fxd = fx.reindex(spy.index.union(fx.index)).sort_index().ffill()
    missing = [t for t, s in px.items()
               if s.loc[:asof_a].empty or s.index.max() < days[-1] - pd.Timedelta(days=4)]
    if missing:
        print(f"  pricing FAILED for {missing} -- sidecar left at {A['as_of']}")
        return 4

    def at(s, d):                                   # last close on or before d
        return float(s.loc[:d].iloc[-1])

    fx_a = at(fxd, asof_a)
    spy_a = at(spy, asof_a)
    L = dict(A["curve"][-1])
    assert L["d"] == A["as_of"], "anchor curve does not end at its own as_of"

    # The anchor's own SPY level can be the PREVIOUS session's close: peak_curves.py
    # downloads with an exclusive end=as_of, so the 2026-09-23 anchor carried 09-22's
    # 773.38 (real 09-23 close 767.81). Every rolled day scales from that level, so the
    # whole post-anchor SPY series ran +0.72% hot and the site published S&P +13.56%
    # against a real +12.74% (02-13 -> 09-30), understating alpha by 0.8 pp. Re-derive
    # the anchor-day level from the previous anchor row by the REAL close ratio (ratio,
    # not level, so a dividend re-adjustment of Yahoo's history cannot bite), and keep
    # the flow-matched share count, which the stale price did not affect.
    P0 = A["curve"][-2]
    spy_fix = P0["spy"] * spy_a / at(spy, pd.Timestamp(P0["d"]))
    if abs(spy_fix / L["spy"] - 1) > 1e-4:
        print(f"  SPY anchor re-based: {L['spy']:.2f} -> {spy_fix:.2f} "
              f"({(spy_fix / L['spy'] - 1) * 100:+.2f}%; peak_curves end= is exclusive)")
        sh = L["spy_mv"] / L["spy"]
        L["spy"], L["spy_mv"] = spy_fix, sh * spy_fix

    # LEVEL marks, exactly as the broker values a position: shares x today's quote.
    # sum(shares x px_mxn) over the SIC names reproduces the anchor curve's mv_mxn to the
    # centavo, and the anchor's mv_usd is mv_mxn / FX, so both conventions carry over.
    # (The first cut rolled the anchor by GROWTH; the anchor xlsx marks were intraday, so
    # that carried a +0.6% level offset vs the .MX quotes into every later day.)
    sicpos = [p for p in A["positions"] if not p["native"]]

    def mark(p, d):
        """(px_mxn, source) for position p on day d."""
        t = p["ticker"]
        if p["native"]:
            return at(px[t], d), ".MX"
        if t in sic:
            return at(sic[t], d), ".MX"
        return at(px[t], d) * at(fxd, d), "US x FX"

    curve = list(A["curve"][:-1]) + [L]
    prev = dict(L)
    spy_sh = L["spy_mv"] / L["spy"]
    for d in days:
        mv_m = sum(p["shares"] * mark(p, d)[0] for p in sicpos)
        r = dict(d=d.strftime("%Y-%m-%d"), fx=at(fxd, d),
                 mv_mxn=mv_m, mv_usd=mv_m / at(fxd, d),
                 cost_mxn=L["cost_mxn"], cost_usd=L["cost_usd"],
                 real_mxn=L["real_mxn"], real_usd=L["real_usd"],
                 util_mxn=L["util_mxn"], util_usd=L["util_usd"],
                 spy=L["spy"] * at(spy, d) / spy_a,
                 spy_cost=L["spy_cost"], spy_real=L["spy_real"])
        r["spy_mv"] = spy_sh * r["spy"]
        for c in ("mxn", "usd"):
            r[f"pl_{c}"] = r[f"mv_{c}"] - r[f"cost_{c}"] + r[f"real_{c}"]
            r[f"plpct_{c}"] = r[f"pl_{c}"] / A[f"base_{c}"]
            day = r[f"mv_{c}"] / prev[f"mv_{c}"] - 1.0          # no flows after the anchor
            if abs(day) > 0.15:
                print(f"  SANITY FAILED: {c} book moved {day:+.1%} on {r['d']} -- not rolling")
                return 4
            r[f"twr_{c}"] = (1 + prev[f"twr_{c}"]) * (1 + day) - 1
        curve.append(r)
        prev = r

    last = days[-1]
    P = dict(A)
    P["curve"] = curve
    P["as_of"] = last.strftime("%Y-%m-%d")
    P["fx_today"] = at(fxd, last)
    P["fx_today_date"] = fxd.loc[:last].index[-1].strftime("%Y-%m-%d")
    P["rolled_from"] = A["as_of"]
    P["rolled_by"] = "scripts/29_peak_rollforward.py (prices + FX only, no fills)"
    for c in ("mxn", "usd"):
        P[f"pl_{c}"] = prev[f"pl_{c}"]
        P[f"mwrr_{c}"] = prev[f"pl_{c}"] / A[f"base_{c}"]
        P[f"twrr_{c}"] = prev[f"twr_{c}"]
        P[f"mv_{c}"] = prev[f"mv_{c}"]
        P[f"unreal_{c}"] = prev[f"mv_{c}"] - prev[f"cost_{c}"]
        P[f"real_{c}"] = prev[f"real_{c}"]
    P["spy_tr"] = curve[-1]["spy"] / curve[0]["spy"] - 1
    # cross-check against the market itself, same window, no curve in between
    _spy_mkt = at(spy, last) / at(spy, pd.Timestamp(curve[0]["d"])) - 1 \
        if spy.index.min() <= pd.Timestamp(curve[0]["d"]) else None
    if _spy_mkt is not None:
        assert abs(P["spy_tr"] - _spy_mkt) < 5e-4, \
            f"SPY TR {P['spy_tr']:.4%} disagrees with Yahoo {_spy_mkt:.4%} over the same window"
    P["spy_pl"] = prev["spy_mv"] - prev["spy_cost"] + prev["spy_real"]
    P["spy_mwrr"] = P["spy_pl"] / A["spy_peak"]
    P["spy_mwrr_common"] = P["spy_pl"] / A["base_usd"]
    u = [c["util_usd"] for c in curve]
    P["util_now"], P["util_mean"], P["util_min"] = u[-1], sum(u) / len(u), min(u)
    pos, srcs = [], {}
    fx_l = at(fxd, last)
    for p in A["positions"]:
        m, src = mark(p, last)
        srcs[src] = srcs.get(src, 0) + 1
        q = dict(p, px_mxn=m, px_usd=m / fx_l, mv_mxn=p["shares"] * m,
                 mv_usd=p["shares"] * m / fx_l, mark_src=src, mark_date=P["as_of"])
        q["ret_mxn"] = q["mv_mxn"] / q["cost_mxn"] - 1
        q["ret_usd"] = q["mv_usd"] / q["cost_usd"] - 1
        pos.append(q)
    P["positions"] = pos
    assert abs(sum(q["mv_mxn"] for q in pos if not q["native"]) - P["mv_mxn"]) < 0.01

    # invariants the approved page depends on
    assert P["base_mxn"] == A["base_mxn"] and P["base_usd"] == A["base_usd"]
    assert len(P["markers"]) == len(A["markers"])
    assert abs(P["pl_mxn"] - (P["mv_mxn"] - curve[-1]["cost_mxn"] + P["real_mxn"])) < 0.01

    Path(OUTF).write_text(json.dumps(P, indent=1), encoding="utf-8")
    print(f"  rolled {A['as_of']} -> {P['as_of']} (+{len(days)} sessions) | "
          f"MWRR {P['mwrr_usd']*100:.2f}% USD / {P['mwrr_mxn']*100:.2f}% MXN | "
          f"TWRR {P['twrr_usd']*100:.2f}% USD | SPY TR {P['spy_tr']*100:.2f}% | "
          f"USDMXN {P['fx_today']:.4f} | marks {srcs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
