# -*- coding: utf-8 -*-
"""S&P 500 benchmark read YTD, from the previous year-end close (Carlos, 2026-10-07).

"Los benchmarks se leen YTD; se eligio no comprar en los primeros dias del ano." The book's
curve (the peak sidecar) starts at its first trade, 2026-02-13. Staying out of the market until
then was a decision, so it is scored, not excused:
  * the BOOK's YTD time-weighted return counts the weeks before its first trade at 0% (cash) --
    while the book's whole history lies inside the year it equals the since-inception TWRR;
  * the S&P 500 (SPY adjusted close, the total-return proxy the curve already uses) is measured
    from the year-end close, in USD and in MXN (SPY x USD/MXN).
Same convention as Carlos's Portfolio_YTD_Real_*.xlsx, row "Memo: calendar-YTD S&P". Until this
change the tiles measured the S&P from the first trade instead, which in pesos added the dollar's
+5% rebound from its February low to the benchmark (+21% vs ~+15.5% YTD).

PRE-INCEPTION LINK. The curve has no points before the first trade, so the S&P's move from the
year-end close to that day comes from data/benchmark_ytd_link.json: daily SPY adjusted closes
(Yahoo) and USD/MXN from the site's own FX spine -- Dukascopy H1, last bar of each UTC day, the
series the walk used through 2026-05-27; it reproduces the curve's first fx (17.1623) exactly.
Ratios of adjusted closes between two PAST dates are invariant to later dividend back-adjustment,
so the file is built once (`python benchmark_ytd.py --build-link`) and validated on every use
against the curve's first point.

From the first full year on (2027+), the year-end close is a point on the curve itself and no
link is needed: book YTD = (1+twr_t)/(1+twr_yearend) - 1, S&P YTD from the curve's own spy/fx.
"""
import json
import os
import sys
from datetime import date, timedelta

from paths import DATA, cuser

LINK = os.path.join(str(DATA), "benchmark_ytd_link.json")


def _d(s):
    return date.fromisoformat(str(s)[:10])


def _load_link(year_end, first, first_fx):
    with open(LINK, encoding="utf-8") as f:
        L = json.load(f)
    p = L["path"]
    if L["year_end"] != year_end.isoformat() or p[-1]["d"] != first.isoformat():
        raise SystemExit(f"benchmark_ytd: link file covers {L['year_end']}..{p[-1]['d']}, the curve "
                         f"needs {year_end}..{first} - rebuild: python benchmark_ytd.py --build-link")
    if abs(p[-1]["fx"] - first_fx) > 1e-6:
        raise SystemExit(f"benchmark_ytd: link fx on {first} is {p[-1]['fx']}, the curve says "
                         f"{first_fx} - two FX sources would be spliced into one benchmark")
    return p


def ytd(curve):
    """YTD returns at the curve's last date + the daily YTD path for charts.

    curve: the peak sidecar's list of {d, spy, fx, twr_usd, twr_mxn}. Returns a dict with
    year_end, asof, first_trade, spy_usd, spy_mxn, book_usd, book_mxn and `path`: a list of
    {d, book_usd, book_mxn, spy_usd, spy_mxn}, cumulative from the year-end close."""
    c = sorted(curve, key=lambda r: r["d"])
    first, last = c[0], c[-1]
    asof = _d(last["d"])
    ye = date(asof.year - 1, 12, 31)
    path = []
    if _d(first["d"]) > ye:
        # inception inside the year: the book was in cash, by choice, until its first trade
        pre = _load_link(ye, _d(first["d"]), float(first["fx"]))
        s0, x0 = pre[0]["spy"], pre[0]["fx"]
        link = pre[-1]["spy"] / s0                     # S&P, year-end close -> first trade
        for r in pre[:-1]:                             # the first trade itself comes from the curve
            path.append({"d": r["d"], "book_usd": 0.0, "book_mxn": 0.0,
                         "spy_usd": r["spy"] / s0 - 1, "spy_mxn": r["spy"] * r["fx"] / (s0 * x0) - 1})
        spy_u = lambda r: link * r["spy"] / first["spy"] - 1
        spy_m = lambda r: (1 + spy_u(r)) * r["fx"] / x0 - 1
        book_u = lambda r: r["twr_usd"]
        book_m = lambda r: r["twr_mxn"]
        rows = c
    else:
        base = [r for r in c if _d(r["d"]) <= ye][-1]
        spy_u = lambda r: r["spy"] / base["spy"] - 1
        spy_m = lambda r: r["spy"] * r["fx"] / (base["spy"] * base["fx"]) - 1
        book_u = lambda r: (1 + r["twr_usd"]) / (1 + base["twr_usd"]) - 1
        book_m = lambda r: (1 + r["twr_mxn"]) / (1 + base["twr_mxn"]) - 1
        rows = [r for r in c if _d(r["d"]) >= _d(base["d"])]
    for r in rows:
        path.append({"d": r["d"][:10], "book_usd": book_u(r), "book_mxn": book_m(r),
                     "spy_usd": spy_u(r), "spy_mxn": spy_m(r)})
    end = path[-1]
    return {"year_end": ye.isoformat(), "asof": asof.isoformat(), "first_trade": first["d"][:10],
            "spy_usd": end["spy_usd"], "spy_mxn": end["spy_mxn"],
            "book_usd": end["book_usd"], "book_mxn": end["book_mxn"], "path": path}


def build_link():
    """One-off (re-runnable): daily SPY adjusted close + spine USD/MXN, year-end -> first trade."""
    import pandas as pd
    import yfinance as yf
    pk = json.load(open(cuser("Documents", "CarlosDuarteWebsite", "real_numbers", "peak_sidecar.json"),
                        encoding="utf-8"))
    c = sorted(pk["curve"], key=lambda r: r["d"])
    first, first_fx = _d(c[0]["d"]), float(c[0]["fx"])
    ye = date(first.year - 1, 12, 31)
    h = pd.read_parquet(cuser("Downloads", "dukascopy_data", "USDMXN", "H1.parquet"))["close"]
    h.index = h.index.tz_convert("UTC")
    fx = h.groupby(h.index.date).last()                # Dukascopy H1, last bar of each UTC day
    px = yf.download("SPY", start=(ye - timedelta(days=10)).isoformat(),
                     end=(first + timedelta(days=1)).isoformat(), auto_adjust=False, progress=False)
    adj = px["Adj Close"]
    adj = (adj.iloc[:, 0] if hasattr(adj, "columns") else adj).dropna()
    days = [d.date() for d in adj.index if ye - timedelta(days=7) <= d.date() <= first]
    start = max(d for d in days if d <= ye)            # the year's last trading close
    path = [{"d": d.isoformat(), "spy": round(float(adj[str(d)].iloc[0] if hasattr(adj[str(d)], "iloc")
                                                    else adj[str(d)]), 6),
             "fx": round(float(fx[d]), 6)} for d in days if d >= start]
    assert path[-1]["d"] == first.isoformat(), f"no SPY close on the first trade {first}"
    assert abs(path[-1]["fx"] - first_fx) < 1e-6, f"spine fx {path[-1]['fx']} != curve {first_fx}"
    out = {"_comment": "S&P 500 YTD link: year-end close -> the book's first trade. Built by "
                       "scripts/benchmark_ytd.py --build-link; read by benchmark_ytd.ytd(). "
                       "Ratios only are used, so later dividend back-adjustment does not matter.",
           "year_end": ye.isoformat(), "first_trade": first.isoformat(),
           "sources": {"spy": "Yahoo SPY adjusted close (total-return proxy), same as the curve",
                       "fx": "Dukascopy USDMXN H1, last bar of each UTC day (the site's FX spine "
                             "through 2026-05-27; reproduces the curve's first fx)"},
           "built": date.today().isoformat(), "path": path}
    with open(LINK, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    print(f"link {path[0]['d']} -> {path[-1]['d']}: {len(path)} days | SPY {path[-1]['spy'] / path[0]['spy'] - 1:+.4%} "
          f"| fx {path[0]['fx']} -> {path[-1]['fx']} -> {LINK}")


if __name__ == "__main__":
    if "--build-link" in sys.argv:
        build_link()
    else:
        pk = json.load(open(cuser("Documents", "CarlosDuarteWebsite", "real_numbers", "peak_sidecar.json"),
                            encoding="utf-8"))
        y = ytd(pk["curve"])
        print({k: (round(v * 100, 3) if isinstance(v, float) else v) for k, v in y.items() if k != "path"})
