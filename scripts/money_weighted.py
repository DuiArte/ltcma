# -*- coding: utf-8 -*-
"""Money-weighted return = the exact IRR of every dated trade (Carlos, 2026-10-07: "quiero el
mas objetivo posible").

It replaces "P&L / peak capital". That ratio divided the whole record's profit by the single
largest amount ever deployed at one instant (01 Sep 2026, 12:20) while the book used 57% of it
on average: it roughly halved what the money earned, moved retroactively whenever a new peak was
set, and ignored how long each peso was invested. The IRR has no free parameter -- it is the one
rate at which every buy, every sale and today's market value net to zero.

Conventions (GIPS):
  * flows = the book's fills (a buy puts money in, a sale's net proceeds take it out); terminal
    = market value at the as-of close. Same universe as the peak sidecar's curve: market value
    minus net flows reproduces its P&L to the centavo, in both currencies.
  * reported over the period and NOT annualized while the record is under a year (GIPS: periods
    shorter than one year must not be annualized); annualized from 365 days on, and labelled so.
  * measured from the first trade: money-weighting weeks in which no money was invested has no
    meaning (the TWRR's YTD convention scores those weeks at 0% instead -- benchmark_ytd.py).
  * the index comparison on MONEY puts the IDENTICAL flows into SPY (the sidecar's replica:
    spy_mv - net flows == spy_pl to the cent), so book and index share every flow and the
    comparison is pure.
"""
from datetime import date

import numpy as np


def _d(s):
    return date.fromisoformat(str(s)[:10])


def _irr(days, amounts, horizon, terminal):
    """Annual IRR r solving sum(a_i * (1+r)^((horizon - t_i)/365)) = terminal (future-value
    form; a_i > 0 = money in). Bisection on a bracket with a sign change; None if there is none."""
    a = np.asarray(amounts, dtype=float)
    e = (horizon - np.asarray(days, dtype=float)) / 365.0
    f = lambda r: float(np.sum(a * np.power(1.0 + r, e)) - terminal)
    lo, hi = -0.95, 1.0
    flo = f(lo)
    while f(hi) * flo > 0 and hi < 1e6:            # widen until the sign changes
        hi *= 4.0
    if f(hi) * flo > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if fm * flo > 0:
            lo, flo = mid, fm
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return 0.5 * (lo + hi)


def _as_period(r, span):
    """(value, annualized?) -- cumulative over the period under a year, annual rate from one year."""
    if r is None:
        return None, False
    if span >= 365:
        return r, True
    return (1.0 + r) ** (span / 365.0) - 1.0, False


def mwr(curve, markers):
    """Money-weighted returns of the book and of SPY with the same money, USD and MXN.

    Returns {first_trade, asof, days, annualized, book_usd, book_mxn, spy_usd, spy_mxn,
    path: [{d, book_usd, book_mxn, spy_usd, spy_mxn}]} -- the path is the since-first-trade
    money-weighted return to each date (cumulative, not annualized while under a year)."""
    c = sorted(curve, key=lambda r: r["d"])
    t0 = _d(c[0]["d"])
    fl = sorted(((_d(x["d"]) - t0).days, (1.0 if x["side"] == "buy" else -1.0) * x["net_usd"],
                 (1.0 if x["side"] == "buy" else -1.0) * x["net_mxn"]) for x in markers)
    days = np.array([f[0] for f in fl], dtype=float)
    a_usd = np.array([f[1] for f in fl])
    a_mxn = np.array([f[2] for f in fl])
    path = []
    for r in c:
        h = (_d(r["d"]) - t0).days
        k = int(np.searchsorted(days, h, side="right"))   # flows dated on or before this close
        if k == 0:
            continue
        span = max(h, 1)
        row = {"d": r["d"][:10]}
        for key, term, amt in (("book_usd", r["mv_usd"], a_usd), ("book_mxn", r["mv_mxn"], a_mxn),
                               ("spy_usd", r["spy_mv"], a_usd),
                               ("spy_mxn", r["spy_mv"] * r["fx"], a_mxn)):
            if h == 0:      # zero horizon: the IRR's limit is the simple return on the day's flows
                row[key] = term / float(np.sum(amt[:k])) - 1.0
            else:
                row[key] = _as_period(_irr(days[:k], amt[:k], h, term), span)[0]
        path.append(row)
    end = path[-1]
    span = (_d(c[-1]["d"]) - t0).days
    return {"first_trade": t0.isoformat(), "asof": c[-1]["d"][:10], "days": span,
            "annualized": span >= 365, "book_usd": end["book_usd"], "book_mxn": end["book_mxn"],
            "spy_usd": end["spy_usd"], "spy_mxn": end["spy_mxn"], "path": path}


if __name__ == "__main__":
    import json
    from paths import cuser
    pk = json.load(open(cuser("Documents", "CarlosDuarteWebsite", "real_numbers", "peak_sidecar.json"),
                        encoding="utf-8"))
    m = mwr(pk["curve"], pk["markers"])
    print({k: (round(v * 100, 3) if isinstance(v, float) else v) for k, v in m.items() if k != "path"})
    print("path points:", len(m["path"]), "| first:", {k: (round(v * 100, 3) if isinstance(v, float) else v)
                                                       for k, v in m["path"][0].items()})
    print("old peak-based: usd", round(pk["mwrr_usd"] * 100, 3), "mxn", round(pk["mwrr_mxn"] * 100, 3),
          "| spy (peak-based)", round(pk["spy_mwrr"] * 100, 3))
