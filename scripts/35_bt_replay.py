"""LTCMA - Step 35: out-of-sample replay of the public backtests (DATA step).

Each public backtest ends where its data ended (spring 2026). This step carries three of them
forward to the latest US close with the SAME frozen rules and writes data/bt_replay/<key>.json;
24_backtests.py draws it on bt_<key>.html and 23_strategies.py adds a one-line card note.

LABEL: "out-of-sample replay" -- recomputed every day from public end-of-day prices with rules
frozen before the window began. It is NOT live trading and must never be called that (Carlos:
"A live track that backfills history is a backtest in costume").

  buy_the_dip             the DEPLOYED equal-weight daily-return blend of the selected SPY/QQQ/EFA
                          configurations (make_report.build_portfolio), not the SPY-only curve.
  static_diversification  the report's headline static row, TAAParams("C","6m",3,"W",False):
                          SPY/IEF/GLD equal weight, WEEKLY rebalance, 0.10% round trip. The
                          catalogue text says monthly/quarterly; the published numbers are weekly.
  static_drift_weights    fixed 50/30/20, rebalanced at every completed month-end (the rulebook:
                          weights do NOT drift). A = the buy_the_dip blend above. B = SPY/IEF/GLD
                          equal weight, monthly, 0.10%/3 per month (the frozen sleeve's own cost
                          rule). C = the OPERATED rule, NOT the backtest's M5 CRT tape (private
                          Documents/AI_PROCEDURES/STATIC_50_30_20_OPERATIONS.md sec. 0-1): long GLD
                          iff the daily close > EMA200, else cash, traded at the next open, 0.10%
                          round trip. Idle cash earns nothing, as in every sleeve of the backtest.
  crt                     FROZEN, never extended (text in glossary.BT_FROZEN): the FxPro M5 branch is
                          closed by design, the standing rule is 1H/4H/1D only, and Findings #24/#52
                          call its 0.59 Sharpe a data-era artifact.

CONFIDENTIALITY: engines and selected parameters are imported / read at RUNTIME from the private
workspaces the hub names (Trading_Index/strategies.json -> paths.workspace). Nothing here writes
parameters, engine code or trade tapes into this public repo: only a growth-of-100 curve and a
few summary numbers per strategy.

SEAM, checked on every run BEFORE anything is written: the fresh-data re-run must reproduce the
frozen backtest on its own window -- BTD equity per instrument and the TAA equity within SEAM_TOL
on every day except the frozen cache's final bar (captured intraday, 12:27 CDMX 2026-05-26), with
identical BTD trade entry dates; for 50/30/20, sleeves A and B recomputed plus the frozen sleeve C
must give the frozen monthly returns within SEAM_TOL. A broken seam writes nothing for that
strategy and exits 1 (best-effort step in daily_refresh.ps1: logged as WARN, the rest continues;
the content-age monitor then flags the stale replay after 5 days).

IDEMPOTENT: every run recomputes from 2010 and rewrites the file; nothing is appended. Host-only:
without the hub / private code / network it prints a SKIP line, exits 0 and leaves the committed
files untouched. It never moves a file's as-of backwards.

    python 35_bt_replay.py            # compute + write
    python 35_bt_replay.py --dry-run  # compute + print, write nothing
"""
import json
import os
import sys

import numpy as np
import pandas as pd

from paths import DATA
from glossary import _BT_HUB, _bt_resolve

sys.dont_write_bytecode = True          # no __pycache__ dropped into the private workspaces

OUT = DATA / "bt_replay"
LABEL = "out-of-sample replay"
KEYS = ("buy_the_dip", "static_diversification", "static_drift_weights")
SEAM_TOL = 1e-4                         # 0.01%; the measured seam is ~2e-6
BTD_MEMBERS = ("SPY", "QQQ", "EFA")      # the deployed blend (BTD REPORT.md, "Recommendation")
STATIC_LEGS = ("SPY", "IEF", "GLD")
CASH_PROXY = "SHY"                      # taa_core.CASH: the engine needs the column even unused
GOLD = "GLD"
W_A, W_B, W_C = 0.50, 0.30, 0.20
SLEEVE_B_MONTHLY_COST = 0.001 / 3       # ensemble14 02_build_sleeves.py (frozen sleeve B rule)
SLEEVE_C_EMA_DAYS = 200                 # rulebook sleeve C: "long iff GLD close > EMA200(daily)"
ETF_COST_PER_SIDE = 0.0010 / 2          # the family's 0.10% round trip
NY_SETTLED = (16, 30)                   # a bar dated "today" is final only after 16:30 New York


def skip(msg):
    print(f"  35_bt_replay: SKIP - {msg}; committed data/bt_replay left untouched")
    return 0


# ---------------------------------------------------------------- private code + data
def _hub():
    for cand in _BT_HUB:
        rp = _bt_resolve(cand)
        if rp:
            with open(rp, encoding="utf-8") as fh:
                return {s["key"]: s for s in json.load(fh).get("strategies", [])}
    return None


def _workspace(hub, key):
    return _bt_resolve(((hub.get(key) or {}).get("paths") or {}).get("workspace"))


def _span_end(strat):
    """'2010-01-04 -> 2026-05-26' -> Timestamp('2026-05-26'): the backtest's own end date."""
    return pd.Timestamp(str((strat.get("dates") or {}).get("data_span", "")).split("->")[-1].strip())


def _import_btd(code_dir):
    """engine.py does `from data import ...`, so the private code dir sits on sys.path only for
    the duration of the import."""
    sys.path.insert(0, code_dir)
    try:
        for m in ("data", "engine"):
            sys.modules.pop(m, None)
        import data as btd_data          # noqa: E402  (private, host-only)
        import engine as btd_engine      # noqa: E402  (private, host-only)
    finally:
        sys.path.remove(code_dir)
    return btd_data, btd_engine


def _import_file(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _closed_only(df):
    """Drop a bar dated today (New York) until the session has settled. The frozen caches' own
    last bar is exactly that kind of intraday partial; the replay must not repeat it."""
    now = pd.Timestamp.now(tz="America/New_York")
    if len(df) and df.index[-1].date() >= now.date() and (now.hour, now.minute) < NY_SETTLED:
        df = df.iloc[:-1]
    return df


def fetch(btd_data, tickers):
    """Fresh daily OHLC through the private loader's own fetch (`data._yf_one`: yfinance,
    auto_adjust=True, from 2010-01-01) -- the call that built the frozen caches, minus the cache
    write. All tickers are cut to their common last CLOSED session; calendars must agree."""
    out = {t: _closed_only(btd_data._yf_one(t).sort_index()) for t in tickers}
    last = min(df.index[-1] for df in out.values())
    out = {t: df[df.index <= last] for t, df in out.items()}
    ref = out[tickers[0]].index
    for t, df in out.items():
        if not df.index.equals(ref):
            raise RuntimeError(f"calendar mismatch: {t} {len(df)} bars vs {tickers[0]} {len(ref)}")
    return out


# ---------------------------------------------------------------- shared helpers
def _rebased(eq, start):
    """Growth of 100 from the backtest's last bar (the last trading day <= its end date)."""
    s = eq.index[eq.index <= start][-1]
    eq = eq[eq.index >= s]
    return 100.0 * eq / eq.iloc[0]


# Yahoo's adjusted prices differ by ~1e-7..2e-6 (relative) between two identical requests, so
# a 4-dp series would rewrite a tenth of its history on every run. 2 dp on a base of 100 is the
# site's display ceiling and keeps an unchanged history unchanged in git (measured 2026-10-07).
DP = 2


def _series(v):
    return [{"date": d.strftime("%Y-%m-%d"), "value": round(float(x), DP)} for d, x in v.items()]


def _metrics(v, **extra):
    v = v.astype(float)
    dd = v / v.cummax() - 1.0
    m = {"return_pct": round((float(v.iloc[-1]) / float(v.iloc[0]) - 1.0) * 100, DP),
         "max_drawdown_pct": round(float(dd.min()) * 100, DP),
         "trading_days": int(len(v) - 1)}
    m.update(extra)
    return m


def _frozen_gap(fresh, frozen):
    """Max relative gap fresh/frozen over the frozen window EXCLUDING its final bar (captured
    intraday when the backtest ran). Returns (gap, last date compared)."""
    common = frozen.index[:-1].intersection(fresh.index)
    gap = (fresh.reindex(common) / frozen.reindex(common) - 1.0).abs()
    return float(gap.max()), common[-1]


def _monthly(eq):
    m = eq.resample("ME").last().pct_change().dropna()
    m.index = m.index.to_period("M").to_timestamp("M")
    return m


# ---------------------------------------------------------------- buy_the_dip blend
def btd_blend(ws, btd_engine, px):
    """Frozen engine + frozen selected params per instrument (read from the private summary.csv,
    held in memory only), then make_report.build_portfolio's equal-weight daily-return blend."""
    summ = pd.read_csv(os.path.join(ws, "results", "summary.csv"))
    params = {r["instrument"]: json.loads(r["params"]) for _, r in summ.iterrows()}
    rets, trades, seam = [], {}, {}
    for t in BTD_MEMBERS:
        feat = btd_engine.make_features(px[t])
        tr = btd_engine.backtest(feat, t, params[t])
        eq = btd_engine.daily_equity(tr, feat["dates"], feat["c"], risk=0.01)
        frozen = pd.read_csv(os.path.join(ws, "results", f"{t}_equity.csv"), index_col=0,
                             parse_dates=True)["equity"]
        gap, thru = _frozen_gap(eq, frozen)
        ftr = pd.read_csv(os.path.join(ws, "results", f"{t}_selected_trades.csv"),
                          parse_dates=["entry_dt"])
        f_in = ftr.loc[ftr["entry_dt"] <= thru, "entry_dt"].reset_index(drop=True)
        n_in = tr.loc[tr["entry_dt"] <= thru, "entry_dt"].reset_index(drop=True)
        seam[t] = {"gap": gap, "through": thru, "trades_match": bool(f_in.equals(n_in))}
        # the engine force-closes a position still open on the last bar; flag those as open
        last = len(feat["c"]) - 1
        trades[t] = pd.DataFrame({
            "entry_dt": tr["entry_dt"],
            "open": (tr["reason"] == "time") & (tr["exit_i"] == last)
                    & ((tr["exit_i"] - tr["entry_i"]) < params[t]["time_stop"])})
        rets.append(eq.pct_change().fillna(0.0))
    idx = rets[0].index
    for r in rets[1:]:
        idx = idx.union(r.index)
    port_r = pd.concat([r.reindex(idx).fillna(0.0) for r in rets], axis=1).mean(axis=1)
    return pd.Series(np.cumprod(1.0 + port_r.to_numpy()), index=idx), port_r, trades, seam


def replay_btd(strat, blend_eq, trades, seam):
    v = _rebased(blend_eq, _span_end(strat))
    n_tr = sum(int((tr["entry_dt"] > v.index[0]).sum()) for tr in trades.values())
    n_open = sum(int(tr["open"].sum()) for tr in trades.values())
    ok = all(s["gap"] < SEAM_TOL and s["trades_match"] for s in seam.values())
    info = {"check": "each sleeve's daily equity vs the frozen equity file (relative), and its "
                     "trade entry dates vs the frozen trade list",
            "through": max(s["through"] for s in seam.values()).strftime("%Y-%m-%d"),
            "gaps": {t: f"{s['gap']:.2g}{'' if s['trades_match'] else ' TRADES DIFFER'}"
                     for t, s in seam.items()}}
    notes = ["Equal-weight daily-return blend of the three deployed buy-the-dip sleeves, each run by "
             "the frozen engine with its frozen selected configuration; 1% risk per trade; 0.10% "
             "round trip.",
             "A position still open at the as-of close is marked at that close net of its exit cost "
             "(the engine closes open trades on the last bar), so the final point can move by that "
             "cost on the next run."]
    return v, _metrics(v, n_trades=n_tr, open_positions=n_open), ok, info, notes, {}


# ---------------------------------------------------------------- static_diversification
def replay_static(strat, ws, tc, px):
    p = tc.TAAParams("C", "6m", 3, "W", False)     # make_report.CANDS: the headline static row
    panel = pd.concat({t: px[t]["close"] for t in STATIC_LEGS + (CASH_PROXY,)}, axis=1)
    panel.index.name = "Date"
    eq, _, _ = tc.backtest(panel, p, start="2011-01-01")
    eq0, _, _ = tc.backtest(tc.load_prices(os.path.join(ws, "data", "prices_daily.csv")), p,
                            start="2011-01-01")
    gap, thru = _frozen_gap(eq, eq0)
    v = _rebased(eq, _span_end(strat))
    reb = tc.rebalance_dates(panel.index, p.freq)
    n_reb = int(sum(1 for i in reb if v.index[0] < panel.index[i] < v.index[-1]))
    info = {"check": "the frozen engine's daily equity on fresh prices vs the same engine on the "
                     "frozen price file (relative)",
            "through": thru.strftime("%Y-%m-%d"), "gaps": {"equity": f"{gap:.2g}"}}
    notes = ["Equal weight across the three legs, rebalanced WEEKLY -- the configuration behind the "
             "published figures (the catalogue text describes monthly/quarterly) -- 0.10% round "
             "trip on one-way turnover.",
             "The engine treats the latest bar of an unfinished week as that week's rebalance, so the "
             "final days can move by a fraction of a basis point once the week completes."]
    return v, _metrics(v, n_rebalances=n_reb), gap < SEAM_TOL, info, notes, {}


# ---------------------------------------------------------------- static_drift_weights
def sleeve_c_operated(g):
    """Rulebook sleeve C: signal on the daily close vs its EMA; all-in / all-out at the NEXT
    open; idle cash earns nothing (as in every sleeve of the backtest); 0.05% per side."""
    o, c = g["open"].to_numpy(float), g["close"].to_numpy(float)
    ema = pd.Series(c).ewm(span=SLEEVE_C_EMA_DAYS, adjust=False).mean().to_numpy()
    want = c > ema
    r, pos = np.zeros(len(c)), np.zeros(len(c))
    for i in range(1, len(c)):
        held, tgt = pos[i - 1], (1.0 if want[i - 1] else 0.0)
        if held == 0.0 and tgt == 1.0:                       # buy at today's open
            r[i] = (1.0 - ETF_COST_PER_SIDE) * c[i] / o[i] - 1.0
        elif held == 1.0 and tgt == 0.0:                     # sell at today's open
            r[i] = (1.0 - ETF_COST_PER_SIDE) * o[i] / c[i - 1] - 1.0
        elif held == 1.0:
            r[i] = c[i] / c[i - 1] - 1.0
        pos[i] = tgt
    return pd.Series(r, index=g.index), pd.Series(pos, index=g.index)


def _month_end(idx):
    """True on the last bar of every COMPLETED month (the next bar opens a new month). The
    final bar never is: its month may not be over."""
    ym = idx.year * 12 + idx.month
    return np.r_[ym[1:] != ym[:-1], False]


def replay_drift(strat, ws, blend_eq, blend_r, trades, px):
    idx = blend_eq.index
    legs = pd.concat({t: px[t]["close"] for t in STATIC_LEGS}, axis=1).reindex(idx)
    rC, posC = sleeve_c_operated(px[GOLD].reindex(idx))

    # ---- seam: sleeves A and B recomputed + the FROZEN sleeve C -> the frozen monthly book ----
    fz = pd.read_csv(os.path.join(ws, "inputs", "sleeves_monthly.csv"), index_col=0, parse_dates=True)
    fz.index = fz.index.to_period("M").to_timestamp("M")
    sm = pd.read_csv(os.path.join(ws, "results", "strategy_monthly.csv"), index_col=0, parse_dates=True)
    sm.index = sm.index.to_period("M").to_timestamp("M")
    A_m = _monthly(blend_eq)
    B_m = legs.resample("ME").last().pct_change().dropna().mean(axis=1) - SLEEVE_B_MONTHLY_COST
    B_m.index = B_m.index.to_period("M").to_timestamp("M")
    win = sm.index
    book = (W_A * A_m.reindex(win).fillna(0.0) + W_B * B_m.reindex(win).fillna(0.0)
            + W_C * fz["crt_gold"].reindex(win).fillna(0.0))
    gaps = {"sleeve_a": float((A_m.reindex(win) - fz["buy_the_dip"].reindex(win)).abs().max()),
            "sleeve_b": float((B_m.reindex(win) - fz["static_SPY_IEF_GLD"].reindex(win)).abs().max()),
            "book": float((book - sm["return"]).abs().max())}
    ok = all(np.isfinite(g) and g < SEAM_TOL for g in gaps.values())
    C_m = _monthly((1.0 + rC).cumprod())
    both = pd.concat([C_m.rename("op"), fz["crt_gold"].rename("bt")], axis=1).reindex(win).dropna()
    corr = float(both["op"].corr(both["bt"]))

    # ---- daily book from the backtest's end: 50/30/20 (B 1/3 each) at every month-end close ----
    s = int(np.nonzero(idx <= _span_end(strat))[0][-1])
    rA = blend_r.reindex(idx).fillna(0.0).to_numpy()
    rL = legs.pct_change().fillna(0.0).to_numpy()
    rc = rC.to_numpy()
    me = _month_end(idx)
    V = 100.0
    a, b, c = W_A * V, np.full(3, W_B * V / 3), W_C * V
    b0, vals = b.sum(), [V]
    for i in range(s + 1, len(idx)):
        a *= 1.0 + rA[i]
        b = b * (1.0 + rL[i])
        c *= 1.0 + rc[i]
        V = a + b.sum() + c
        if me[i]:                                   # completed month: B's cost, then rebalance
            V -= SLEEVE_B_MONTHLY_COST * b0
            a, b, c = W_A * V, np.full(3, W_B * V / 3), W_C * V
            b0 = b.sum()
        vals.append(V)
    v = pd.Series(vals, index=idx[s:])

    # self-check: every completed month of the daily book == the monthly 50/30/20 formula
    ends = v[np.r_[True, me[s + 1:]]]
    if len(ends) > 1:
        want = (W_A * A_m + W_B * B_m + W_C * C_m).reindex(
            ends.index[1:].to_period("M").to_timestamp("M")).to_numpy()
        got = ends.pct_change().dropna().to_numpy()
        gaps["daily_vs_monthly_formula"] = float(np.max(np.abs(got - want)))
        ok = ok and gaps["daily_vs_monthly_formula"] < 1e-10

    n_a = sum(int((tr["entry_dt"] > v.index[0]).sum()) for tr in trades.values())
    n_c = int(np.abs(np.diff(posC.to_numpy()))[s:].sum())
    n_reb = int(me[s + 1:].sum())
    info = {"check": "monthly returns of sleeves A and B recomputed on fresh prices, and of the "
                     "50/30/20 book built from them plus the frozen sleeve C, vs the frozen files "
                     "(absolute)",
            "through": win[-1].strftime("%Y-%m-%d"),
            "gaps": {k: f"{g:.2g}" for k, g in gaps.items()}}
    notes = ["Fixed 50/30/20, rebalanced to target at every completed month-end; no regime gating, "
             "no kill switch. Sleeve A: the buy-the-dip blend. Sleeve B: three legs in equal weight, "
             "monthly, the frozen sleeve's 0.10%/3 monthly cost.",
             "Sleeve C is the OPERATED daily trend rule (long gold while its daily close is above its "
             "200-day EMA, otherwise cash, traded at the next open), NOT the backtest's five-minute-"
             "bar CRT gold sleeve, whose data cannot be extended.",
             "The replay starts at the end of the backtest window; the 50/30/20 rules were fixed "
             "later, from data that ended with that window."]
    extra = {"sleeve_c": {"rule": "operated daily trend rule (not the backtest tape)",
                          "monthly_corr_vs_backtest_sleeve": round(corr, 2),
                          "corr_window": f"{both.index[0]:%Y-%m}..{both.index[-1]:%Y-%m}",
                          "corr_months": int(len(both))}}
    return v, _metrics(v, n_trades=n_a + n_c, n_rebalances=n_reb), ok, info, notes, extra


# ---------------------------------------------------------------- write
def _dump(obj):
    """Readable header, one series point per line (a daily run then diffs as a few lines)."""
    head = {k: v for k, v in obj.items() if k != "series"}
    pts = ",\n".join("  " + json.dumps(p, separators=(",", ":")) for p in obj["series"])
    txt = json.dumps(head, indent=1, ensure_ascii=False)[:-2] + ',\n "series": [\n' + pts + "\n ]\n}\n"
    json.loads(txt)                                     # never write something unreadable
    return txt


def write(key, obj, dry):
    path = OUT / f"{key}.json"
    try:
        prev = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        prev = None
    if prev and prev.get("asof", "") > obj["asof"]:
        print(f"  {key}: fresh as-of {obj['asof']} is OLDER than the committed {prev['asof']} "
              f"(stale feed?) - not written")
        return False
    if not dry:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(_dump(obj))
    return True


def main(argv):
    dry = "--dry-run" in argv
    hub = _hub()
    if hub is None:
        return skip("strategy hub not found (host-only)")
    ws = {k: _workspace(hub, k) for k in KEYS}
    if not all(ws.values()):
        return skip("private workspace(s) not found: " + ", ".join(k for k, v in ws.items() if not v))
    try:
        btd_data, btd_engine = _import_btd(os.path.join(ws["buy_the_dip"], "code"))
        tc = _import_file("ltcma_private_taa_core",
                          os.path.join(ws["static_diversification"], "code", "taa_core.py"))
    except Exception as e:                                   # noqa: BLE001
        return skip(f"private engine import failed ({type(e).__name__}: {e})")
    try:
        px = fetch(btd_data, BTD_MEMBERS + ("IEF", GOLD, CASH_PROXY))
    except Exception as e:                                   # noqa: BLE001
        return skip(f"price fetch failed ({type(e).__name__}: {str(e)[:160]})")

    blend_eq, blend_r, trades, seam = btd_blend(ws["buy_the_dip"], btd_engine, px)
    runs = {"buy_the_dip": lambda: replay_btd(hub["buy_the_dip"], blend_eq, trades, seam),
            "static_diversification": lambda: replay_static(hub["static_diversification"],
                                                            ws["static_diversification"], tc, px),
            "static_drift_weights": lambda: replay_drift(hub["static_drift_weights"],
                                                         ws["static_drift_weights"],
                                                         blend_eq, blend_r, trades, px)}
    failed = []
    for key in KEYS:
        v, metrics, ok, info, notes, extra = runs[key]()
        gaps = info.pop("gaps")
        if not ok:
            failed.append(key)
            print(f"  ** {key}: SEAM BROKEN - the fresh re-run no longer reproduces the frozen "
                  f"backtest through {info['through']} (gaps {gaps}, tolerance {SEAM_TOL:g}); "
                  f"nothing written")
            continue
        # The measured gaps go to the log, not the file: they jitter run to run with Yahoo's
        # adjusted prices (~1e-6), and the file should only change when the replay does.
        obj = {"key": key, "label": LABEL,
               "rules_frozen": (hub[key].get("dates") or {}).get("run"),
               "start": v.index[0].strftime("%Y-%m-%d"),
               "asof": v.index[-1].strftime("%Y-%m-%d"),
               "metrics": metrics,
               "seam": {**info, "tolerance": SEAM_TOL, "passed": True},
               **extra, "notes": notes, "series": _series(v)}
        done = write(key, obj, dry)
        print(f"  {key:23s} {obj['start']} -> {obj['asof']}  return {metrics['return_pct']:+.2f}%  "
              f"maxDD {metrics['max_drawdown_pct']:.2f}%  seam ok through {info['through']} {gaps}"
              f"{'' if done else '  [kept committed file]'}{'  [dry run]' if dry else ''}")
    if failed:
        print(f"  35_bt_replay: {len(failed)} seam failure(s): {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
