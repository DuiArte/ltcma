"""picks_tracker -- Pick Tracker and Track Record sections of docs/stocks.html (wave 13, 2026-11-04).

Everything here is computed from data/picks_history.csv (the page's own published ranking, day by day), the
overlays (picks_overlays) and SPY closes. Nothing here feeds the composite, the ranks or the weights.

EXIT ESTIMATE (empirical, no pretend precision)
  * Deterministic trigger: a pick leaves when its composite falls below the #20 cutoff, i.e. when a name
    now ranked 21+ overtakes it. The page shows today's margin over the rank-21 composite.
  * Statistical estimate: a Markov chain over rank states (1-5, 6-10, 11-15, 16-18, 19-20, off the list)
    fitted to every pair of consecutive FULL snapshots exactly one NYSE trading day apart (a partial snapshot
    is skipped). "Off" is absorbing for the time to the FIRST exit. From today's state: median trading days
    until the name first leaves, the model's PREDICTIVE range of that time (10th-90th percentile of the
    first-exit distribution: 8 in 10 names starting in the band leave inside it), and the probability it
    leaves within 20 trading days. The moving-block bootstrap over dates (blocks of 10 days, 300 draws,
    fixed seed) gives the uncertainty OF THE MEDIAN only, and is labelled so (wave-13 fix: it used to be
    printed as if it were the range of exit times, which overstated precision about tenfold).
    A state with fewer than 30 observed transitions or 15 distinct days is "insufficient history". Anything
    longer than the history itself (N trading days tracked) is printed as "> N td" (computed up to
    H_MAX = 250). Next to it: the model-free share of past name-days in the same state after which the name
    left within 20 td (overlapping name-days, so its effective sample is far smaller than its count).
TRACK RECORD ("will they keep doing well?")
  * follow-the-list basket (equal-weight top 20, re-formed at every full snapshot) vs the equal-weight
    universe REBALANCED at each ranking, ranks 21-40 and SPY (price return). Entries use the ranking day's
    close, which is published only after that close, so the basket is a description, not a tradeable result;
  * forward excess return vs the equal-weight universe at 5 / 10 / 20 trading days, by tenure on the list;
    95% interval = t interval over INDEPENDENT (non-overlapping) windows only, so n is small and stated;
  * the launch cohort (on the list since it began) vs the BUY-AND-HOLD equal-weight universe over the same
    dates, with a 95% t interval over its names; the cohort is chosen after the fact (the names that stayed),
    so it is descriptive only.
Returns are price-only (no dividends) on the page's own build-time Yahoo prices, split-adjusted only for
Yahoo-confirmed splits; any window spanning an unexplained split-like jump is n/a.
"""
from __future__ import annotations

import html as _h
import math
import re
from datetime import date, datetime

import numpy as np
import pandas as pd

from picks_history import LIST_LAUNCH, Panel, TOP_N  # noqa: F401

STATES = [(1, 5, "1-5"), (6, 10, "6-10"), (11, 15, "11-15"), (16, 18, "16-18"), (19, 20, "19-20")]
OFF = len(STATES)
H_MAX = 250
BOOT_B, BLOCK_L, SEED = 300, 10, 20261104
MIN_OBS, MIN_DATES = 30, 15
HORIZONS = (5, 10, 20)
TENURE_BUCKETS = [(0, 20, "0-19 td"), (20, 60, "20-59 td"), (60, 10 ** 6, "60+ td")]
T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 12: 2.18,
       15: 2.13, 20: 2.09, 30: 2.04, 60: 2.00}


def _t95(df_):
    keys = sorted(k for k in T95 if k <= df_) or [1]
    return T95[keys[-1]] if df_ < 120 else 1.98


def e(x):
    return _h.escape(str(x), quote=True)


def state_of(rank):
    if rank is None or (isinstance(rank, float) and math.isnan(rank)):
        return None
    for i, (lo, hi, _) in enumerate(STATES):
        if lo <= rank <= hi:
            return i
    return OFF


# ============================================================ exit model
def _transitions(p):
    """[(pair index, origin date, from state, to state)] over consecutive 1-trading-day snapshot pairs."""
    out, k = [], 0
    part = set(getattr(p, "partial", []) or [])
    for d0, d1 in zip(p.dates[:-1], p.dates[1:]):
        if p.tdi[d1] - p.tdi[d0] != 1 or d0 in part or d1 in part:
            continue
        r0, r1 = p.rank.loc[d0], p.rank.loc[d1]
        for tk in p.rank.columns:
            a, b = r0.get(tk), r1.get(tk)
            if pd.isna(a) or pd.isna(b) or a > TOP_N:
                continue
            out.append((k, d0, state_of(a), state_of(b)))
        k += 1
    return out, k


def _counts(tr, n_pairs, idx=None):
    c = np.zeros((n_pairs, OFF, OFF + 1))
    for k, _d, a, b in tr:
        c[k, a, b] += 1
    return c if idx is None else c[idx]


def _survival(P, full=False):
    """P: OFF x (OFF+1) row-stochastic over the list states + OFF. -> (median td to first exit, inf beyond
    H_MAX; P(first exit within 20 td)) for every starting state; with full=True also the 10th and 90th
    percentiles of the first-exit time (the model's predictive range; inf beyond H_MAX)."""
    Q = P[:, :OFF]
    med, p20 = np.full(OFF, np.inf), np.full(OFF, np.nan)
    q10, q90 = np.full(OFF, np.inf), np.full(OFF, np.inf)
    V = np.eye(OFF)
    for t in range(1, H_MAX + 1):
        V = V @ Q
        S = V.sum(axis=1)                       # share still on the list t days after starting in each state
        if t == 20:
            p20 = 1 - S
        med[(S <= 0.5) & ~np.isfinite(med)] = t
        q10[(S <= 0.9) & ~np.isfinite(q10)] = t
        q90[(S <= 0.1) & ~np.isfinite(q90)] = t
    return (med, p20, q10, q90) if full else (med, p20)


def _matrix(c, fallback=None):
    """Row-normalised transition counts. A state with no observations stays put (identity row) unless a
    fallback row is given (bootstrap draws fall back to the full-sample row); such a state is reported as
    insufficient history anyway."""
    tot = c.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        P = c / tot
    miss = tot[:, 0] == 0
    if miss.any():
        P[miss] = fallback[miss] if fallback is not None else np.hstack([np.eye(OFF), np.zeros((OFF, 1))])[miss]
    return P


def exit_model(p):
    tr, n_pairs = _transitions(p)
    res = {"n_pairs": n_pairs, "n_transitions": len(tr), "states": [],
           "span_td": (p.tdi[p.dates[-1]] - p.tdi[p.dates[0]] + 1) if p.dates else 0}
    if n_pairs < 5:
        res["insufficient"] = True
        return res
    C = _counts(tr, n_pairs)
    full = C.sum(axis=0)
    P = _matrix(full)
    med, p20, q10, q90 = _survival(P, full=True)
    rng = np.random.RandomState(SEED)
    L = min(BLOCK_L, n_pairs)
    nb = int(math.ceil(n_pairs / L))
    bm, bp = [], []
    for _ in range(BOOT_B):
        starts = rng.randint(0, n_pairs - L + 1, size=nb)
        idx = np.concatenate([np.arange(s, s + L) for s in starts])[:n_pairs]
        m, q = _survival(_matrix(C[idx].sum(axis=0), fallback=P))
        bm.append(m)
        bp.append(q)
    bm, bp = np.minimum(np.array(bm), H_MAX + 1), np.array(bp)     # beyond H_MAX -> H_MAX + 1 (printed "> 250")
    dates_by_state = [set() for _ in range(OFF)]
    for _k, d, a, _b in tr:
        dates_by_state[a].add(d)
    emp = _empirical_p20(p)
    for s, (lo, hi, lab) in enumerate(STATES):
        n_obs = int(full[s].sum())
        n_dates = len(dates_by_state[s])
        row = {"state": s, "label": lab, "n_obs": n_obs, "n_dates": n_dates, "n_exit_next_day": int(full[s, OFF]),
               "median": float(med[s]), "p20": float(p20[s]),
               "pred_lo": float(q10[s]), "pred_hi": float(q90[s]),
               "med_lo": float(np.nanpercentile(bm[:, s], 10)), "med_hi": float(np.nanpercentile(bm[:, s], 90)),
               "p20_lo": float(np.nanpercentile(bp[:, s], 10)), "p20_hi": float(np.nanpercentile(bp[:, s], 90)),
               "emp_p20": None if emp[s][0] is None else float(emp[s][0]), "emp_n": emp[s][1],
               "insufficient": n_obs < MIN_OBS or n_dates < MIN_DATES, "span_td": res["span_td"]}
        res["states"].append(row)
    sp = p.spells()
    done = sp[~sp.ongoing]
    res["spells"] = {"n": len(sp), "completed": len(done), "left_censored": int(sp.left_censored.sum()),
                     "since_launch": int(sp.since_launch.sum()),
                     "median_td": float(done.trading_days.median()) if len(done) else None,
                     "q1": float(done.trading_days.quantile(.25)) if len(done) else None,
                     "q3": float(done.trading_days.quantile(.75)) if len(done) else None,
                     "le5": int((done.trading_days <= 5).sum())}
    return res


def _empirical_p20(p):
    """Model-free: share of (day, name) observations in each state after which the name was off the list at
    some snapshot within the next 20 trading days (only days with >= 20 td of history after them)."""
    hits, n = np.zeros(OFF), np.zeros(OFF)
    last_td = p.tdi[p.dates[-1]]
    part = set(getattr(p, "partial", []) or [])
    for i, d in enumerate(p.dates):
        if last_td - p.tdi[d] < 20:
            break
        if d in part:
            continue
        fut = [x for x in p.dates[i + 1:] if p.tdi[x] - p.tdi[d] <= 20]
        for tk in p.rank.columns:
            r = p.rank.at[d, tk]
            if pd.isna(r) or r > TOP_N:
                continue
            s = state_of(r)
            n[s] += 1
            if any(p.top.at[x, tk] == 0 for x in fut):
                hits[s] += 1
    return [((hits[s] / n[s]) if n[s] else None, int(n[s])) for s in range(OFF)]


# ============================================================ SPY helpers
def spy_at(spy, d):
    if spy is None or not len(spy):
        return np.nan
    s = spy[spy.index <= d]
    return float(s.iloc[-1]) if len(s) else np.nan


def spy_ret(spy, d0, d1):
    a, b = spy_at(spy, d0), spy_at(spy, d1)
    if spy is not None and len(spy) and spy.index[0] > d0:
        return np.nan
    return (b / a - 1) if (a == a and b == b and a) else np.nan


# ============================================================ track record
def _fwd_date(p, i, h, slack=5):
    want = p.tdi[p.dates[i]] + h
    for j in range(i + 1, len(p.dates)):
        if p.tdi[p.dates[j]] >= want:
            return p.dates[j] if p.tdi[p.dates[j]] - want <= slack else None
    return None


def _nonoverlap(p, dates, h):
    keep, nxt = [], -1
    for d in dates:
        if p.tdi[d] >= nxt:
            keep.append(d)
            nxt = p.tdi[d] + h
    return set(keep)


def _t_interval(vals):
    """(mean, lo, hi) of a 95% t interval; lo/hi None when fewer than 3 values."""
    v = [x for x in vals if x == x]
    k = len(v)
    if not k:
        return None, None, None
    m = float(np.mean(v))
    if k < 3:
        return m, None, None
    se = float(np.std(v, ddof=1)) / math.sqrt(k)
    return m, m - _t95(k - 1) * se, m + _t95(k - 1) * se


def track_record(p, spy=None):
    out = {}
    part = set(getattr(p, "partial", []) or [])
    full = [d for d in p.dates if d not in part]
    # follow-the-list basket: formed on full rankings only; an interval with no trading day (a holiday
    # snapshot repeating the prior close) is skipped rather than counted as a tie / loss
    rows, cache = [], {}
    dropped = {}
    for d0, d1 in zip(full[:-1], full[1:]):
        if p.tdi[d1] - p.tdi[d0] <= 0:
            continue
        on = [tk for tk in p.top.columns if p.top.at[d0, tk] == 1]
        off = [tk for tk in p.top.columns if p.top.at[d0, tk] == 0]
        for tk in on + off:
            if p.window_ret(tk, d0, d1) != p.window_ret(tk, d0, d1) and not (
                    pd.isna(p.adj.at[d0, tk]) or pd.isna(p.adj.at[d1, tk])):
                dropped[tk] = dropped.get(tk, 0) + 1        # priced on both days, n/a only for a price break
        rows.append({"from": d0, "to": d1, "top20": p.ew_ret(d0, d1, on)[0], "rest": p.ew_ret(d0, d1, off)[0],
                     "ew": p.ew_ret(d0, d1)[0], "spy": spy_ret(spy, d0, d1)})
    bk = pd.DataFrame(rows, columns=["from", "to", "top20", "rest", "ew", "spy"])
    for c in ("top20", "rest", "ew", "spy"):
        bk["cum_" + c] = (1 + bk[c].fillna(0)).cumprod() - 1
    spy_ok = bool(bk["spy"].notna().all()) if len(bk) else False
    out["basket"] = bk
    out["basket_summary"] = {"n": len(bk), "from": full[0] if full else None, "to": full[-1] if full else None,
                             "n_rankings": len(p.dates), "n_partial": len(part),
                             "top20": float(bk.cum_top20.iloc[-1]) if len(bk) else None,
                             "ew": float(bk.cum_ew.iloc[-1]) if len(bk) else None,
                             "rest": float(bk.cum_rest.iloc[-1]) if len(bk) else None,
                             "spy": float(bk.cum_spy.iloc[-1]) if (len(bk) and spy_ok) else None,
                             "beats": int((bk.top20 > bk.ew).sum()) if len(bk) else 0,
                             "dropped": dropped}
    # forward excess by tenure
    ten = p.tenure_on()
    obs = []
    for h in HORIZONS:
        for i, d in enumerate(p.dates):
            d1 = _fwd_date(p, i, h)
            if d1 is None:
                continue
            if (d, d1) not in cache:
                cache[(d, d1)] = p.ew_ret(d, d1)[0]
            ew = cache[(d, d1)]
            for tk in p.top.columns:
                v = p.top.at[d, tk]
                if pd.isna(v):
                    continue
                r = p.window_ret(tk, d, d1)
                if r != r or ew != ew:
                    continue
                if v:
                    tn = ten.at[d, tk]
                    b = next(lab for lo, hi, lab in TENURE_BUCKETS if lo <= tn < hi)
                    grp = "top20"
                else:
                    b, grp = "rank21_40", "rank21_40"
                obs.append((h, d, tk, grp, b, r - ew))
    o = pd.DataFrame(obs, columns=["h", "date", "ticker", "group", "bucket", "excess"])
    tab = []
    for h in HORIZONS:
        oh = o[o.h == h]
        no = _nonoverlap(p, sorted(oh.date.unique()), h)
        for b in [lab for _, _, lab in TENURE_BUCKETS] + ["top20", "rank21_40"]:
            sel = oh[oh.group == "top20"] if b == "top20" else oh[oh.bucket == b]
            if sel.empty:
                continue
            per = sel[sel.date.isin(no)].groupby("date")["excess"].mean()
            k = len(per)
            m = float(per.mean()) if k else None
            if k >= 3:
                se = float(per.std(ddof=1)) / math.sqrt(k)
                lo, hi = m - _t95(k - 1) * se, m + _t95(k - 1) * se
            else:
                lo = hi = None
            tab.append({"h": h, "bucket": b, "n_obs": len(sel), "n_names": sel.ticker.nunique(),
                        "n_dates": sel.date.nunique(), "mean": float(sel.excess.mean()),
                        "hit": float((sel.excess > 0).mean()), "k_indep": k, "indep_mean": m, "lo": lo, "hi": hi})
    out["persistence"] = pd.DataFrame(tab)
    # who the 60+ td bucket really is (the caveat is derived, not hand-written)
    o60 = o[(o.group == "top20") & (o.bucket == "60+ td")] if len(o) else o
    # the launch cohort: on the list at every ranking since the list itself began (LIST_LAUNCH)
    sp = p.spells()
    launch_names = set(sp[sp.since_launch].ticker)
    out["long_bucket"] = {"names": sorted(set(o60.ticker)) if len(o60) else [],
                          "launch_share": float(o60.ticker.isin(launch_names).mean()) if len(o60) else None}
    coh = sp[sp.ongoing & sp.since_launch].ticker.tolist()
    d0, d1 = p.dates[0], p.dates[-1]
    rets = {tk: p.window_ret(tk, d0, d1) for tk in coh}
    good = [v for v in rets.values() if v == v]
    ew_bh, n_ew = p.ew_ret(d0, d1)                   # buy-and-hold equal-weight universe over the same dates
    mx, lo, hi = _t_interval([v - ew_bh for v in good]) if (good and ew_bh == ew_bh) else (None, None, None)
    out["cohort"] = {"names": coh, "n": len(coh), "n_priced": len(good),
                     "excluded": sorted(tk for tk, v in rets.items() if v != v),
                     "mean": float(np.mean(good)) if good else None, "ew": ew_bh, "ew_n": n_ew,
                     "excess": mx, "lo": lo, "hi": hi,
                     "spy": spy_ret(spy, d0, d1), "from": d0, "to": d1, "rets": rets}
    return out


# ============================================================ per-ticker tracker rows
def tracker_rows(p, exit_res, spy=None):
    last = p.dates[-1]
    c20, c21 = p.cutoff(last)
    sp = p.spells()
    st_by = {r["state"]: r for r in exit_res.get("states", [])}
    rows = []
    order = p.rank.loc[last].dropna().sort_values().index.tolist()
    for tk in order:
        rank = int(p.rank.at[last, tk])
        comp = p.comp.at[last, tk]
        s_tk = sp[sp.ticker == tk]
        cur = s_tk[s_tk.ongoing]
        row = {"ticker": tk, "rank": rank, "on": rank <= TOP_N, "sector": p.sector.get(tk), "n_spells": len(s_tk),
               "composite": comp, "price": p.px.at[last, tk]}
        if row["on"] and len(cur):
            c = cur.iloc[0]
            d0 = c.start
            r = p.window_ret(tk, d0, last)
            ew, n_ew = p.ew_ret(d0, last)
            sr = spy_ret(spy, d0, last)
            row.update(since=d0, td=int(c.trading_days), cd=int(c.calendar_days), launch=bool(c.since_launch),
                       censored=bool(c.left_censored), gap_before=int(c.gap_before_td),
                       entry_rank=int(c.entry_rank), entry_price=float(p.adj.at[d0, tk]),
                       ret=r, ew=ew, spy=sr, ex_ew=(r - ew) if (r == r and ew == ew) else np.nan,
                       ex_spy=(r - sr) if (r == r and sr == sr) else np.nan,
                       mdd=p.max_drawdown(tk, d0, last), margin=(comp - c21) if c21 == c21 else np.nan,
                       broken=any(b["ticker"] == tk and d0 <= b["from"] for b in p.breaks))
            row["exit"] = st_by.get(state_of(rank))
        elif row["on"]:                     # on today's list but no observed spell (cannot happen with a full
            row.update(since=last, td=1, cd=1, launch=False, censored=False, gap_before=0,   # last ranking)
                       entry_rank=rank, entry_price=float(p.adj.at[last, tk]), ret=np.nan, ew=np.nan,
                       spy=np.nan, ex_ew=np.nan, ex_spy=np.nan, mdd=np.nan,
                       margin=(comp - c21) if c21 == c21 else np.nan, broken=False)
            row["exit"] = st_by.get(state_of(rank))
        else:
            prev = s_tk[~s_tk.ongoing]
            row.update(last_on=prev.last_on_list.max() if len(prev) else None,
                       margin=(comp - c20) if c20 == c20 else np.nan)
        rows.append(row)
    return rows, {"c20": c20, "c21": c21, "last": last}


# ============================================================ formatting
def pct(x, signed=True, dp=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    s = f"{x * 100:+.{dp}f}" if signed else f"{x * 100:.{dp}f}"
    if float(s) == 0:
        s = f"{0:.{dp}f}"                        # a value that rounds to zero has no sign ("−0.0%" says nothing)
    return (s + "%").replace("-", "−")


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def usd(x, dp=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"${x:,.{dp}f}"


def money(x):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    a = abs(x)
    s = f"${a / 1e9:,.1f}B" if a >= 1e9 else f"${a / 1e6:,.1f}M" if a >= 1e6 else f"${a / 1e3:,.0f}K" \
        if a >= 1e3 else f"${a:,.0f}"
    return ("−" if x < 0 else "") + s


def dfmt(d, year=False):
    try:
        x = date.fromisoformat(str(d)[:10])
    except ValueError:
        return e(d)
    return x.strftime("%d %b %Y" if year else "%d %b")


def num2(x):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:+.2f}".replace("-", "−")


def cls(x):
    return "" if x is None or (isinstance(x, float) and not np.isfinite(x)) else ("pos" if x >= 0 else "neg")


GAP = '<span class="ptgap">not available today (data gap)</span>'


def gap_cell(o):
    why = safe_text((o or {}).get("why") or "data gap")
    if (o or {}).get("permanent"):
        return f'<span class="ptgap" title="{e(why)}">not covered</span>'
    return f'<span class="ptgap" title="{e(why)}">not available today (data gap)</span>'


def gap_why(o):
    return e(safe_text((o or {}).get("why", "")))


def _p(x):
    if x is None or not np.isfinite(x):
        return "n/a"
    if x == 0:
        return "0%"
    return "&lt;1%" if x < 0.005 else pct(x, False, 0)


def margin_txt(m, on):
    """The composite's distance to the cut at the published precision. Ranks 21-40 are published at 2 dp, so
    a gap under 0.01 is a tie at that precision and its sign means nothing: say which side of the cut the
    RANK puts the name on instead of printing "-0.00 vs #21"."""
    if m is None or (isinstance(m, float) and not np.isfinite(m)):
        return "n/a"
    if abs(m) < 0.005:
        return "&lt;0.01 above #21" if on else "&lt;0.01 below #20"
    return f"{num2(m)} vs {'#21' if on else '#20'}"


_PATH_RX = re.compile(r"[A-Za-z]:[\\/][^\s;,)]*|/(?:home|mnt|Users|tmp)/[^\s;,)]*")
_LONGNUM_RX = re.compile(r"\d+\.\d{3,}")


def safe_text(s):
    """Visible gap wording: never a local path (privacy) and never a number with 3+ decimals (guard_decimals
    is load-bearing: one would block the whole refresh). Exception messages stay in the log / alert line."""
    s = _PATH_RX.sub("[path]", str(s or ""))
    return _LONGNUM_RX.sub(lambda m: m.group(0).split(".")[0], s)


def _fmt_td(v, H):
    return f"&gt;{H}" if (v is None or not np.isfinite(v) or v > H) else f"{v:.0f}"


def exit_text(ex, span=None):
    """(main, sub) for the exit wording. Anything longer than the history itself (span trading days) is printed
    as "> span td": five months of rankings cannot date an exit further out than that. The range shown is the
    model's PREDICTIVE range of exit times (10th-90th percentile); the bootstrap interval is only the
    uncertainty of the median and is labelled so."""
    if not ex:
        return "n/a", ""
    if ex["insufficient"]:
        return "insufficient history", f"n={ex['n_obs']} moves over {ex['n_dates']} days"
    H = int(span or ex.get("span_td") or H_MAX)
    m = ex["median"]
    rng = (f"8 in 10 names in this band leave between {_fmt_td(ex.get('pred_lo'), H)} and "
           f"{_fmt_td(ex.get('pred_hi'), H)} td")
    if not np.isfinite(m) or m > H:
        main, unc = f"&gt; {H} td", "the median itself is longer than the history so far"
    else:
        main = f"~{m:.0f} td"
        unc = (f"the median itself is uncertain: bootstrap 80% {_fmt_td(ex['med_lo'], H)} to "
               f"{_fmt_td(ex['med_hi'], H)} td")
    emp = f", history {_p(ex['emp_p20'])}" if ex.get("emp_p20") is not None else ""
    return main, f"{rng}; {unc} &middot; out within 20 td: model {_p(ex['p20'])}{emp}"


# ============================================================ HTML: tracker
def _earn_cell(o):
    if not o or o.get("status") != "ok":
        return gap_cell(o)
    n = o.get("next")
    if n:
        ses = {"bmo": "pre-open", "amc": "after close", "intraday": "in session"}.get(n["session"], "time n/a")
        est = " (est.)" if n.get("estimated") else ""
        dd = "today" if n["days"] == 0 else f"in {n['days']} d"
        top = f"{dfmt(n['date'])}{est}"
        sub = f"{ses} &middot; {dd}"
    else:
        top, sub = "not set", (f"last {dfmt(o['last_listed'])}" if o.get("last_listed") else "no date")
    beat = (f'<br><span class="tn">beat {o["beats"]} of {len(o["history"])}</span>' if o.get("history") else "")
    return f'{top}<br><span class="tn">{sub}</span>{beat}'


def _sent_cell(o):
    if not o or o.get("status") != "ok":
        return gap_cell(o)
    m = o.get("mix_now")
    top = f"buy {pct(m['buy_share'], False, 0)}" if m and m.get("buy_share") is not None else "mix n/a"
    d = o.get("d90") or {}
    return (f'{top}<br><span class="tn">90 d: {d.get("up", 0)} up / {d.get("down", 0)} down</span>'
            f'<br><span class="tn">targets +{d.get("pt_up", 0)} / −{d.get("pt_down", 0)}</span>')


def _tgt_cell(o):
    if not o or o.get("status") != "ok":
        return f'{gap_cell(o)}<br><span class="tn">{_model_txt(o)}</span>'
    return (f'{usd(o["mean"], 0)} <span class="{cls(o.get("upside"))}">{pct(o.get("upside"), True, 0)}</span>'
            f'<br><span class="tn">n={o.get("n") or "?"} &middot; {usd(o.get("low"), 0)}–{usd(o.get("high"), 0)}</span>'
            f'<br><span class="tn">{_model_txt(o)}</span>')


def _model_txt(o):
    m = (o or {}).get("model") or {}
    return f"model {usd(m['iv'], 0)}" if m.get("iv") else "model n/a"


def _exit_cell(ex):
    """Compact exit cell; the full wording is in the detail row."""
    if not ex:
        return "n/a"
    if ex["insufficient"]:
        return f'insufficient history<br><span class="tn">n={ex["n_obs"]}</span>'
    H = int(ex.get("span_td") or H_MAX)
    m = ex["median"]
    hist = f" (hist. {_p(ex['emp_p20'])})" if ex.get("emp_p20") is not None else ""
    p20 = f'<br><span class="tn">out ≤ 20 td: {_p(ex["p20"])}{hist}</span>'
    rng = (f'<br><span class="tn">range {_fmt_td(ex.get("pred_lo"), H)}–{_fmt_td(ex.get("pred_hi"), H)} td'
           f'</span>')
    if not np.isfinite(m) or m > H:
        return f'&gt; {H} td{rng}{p20}'
    return f'~{m:.0f} td{rng}{p20}'


def _ins_cell(o):
    if not o or o.get("status") == "gap":
        return gap_cell(o)
    w = o["windows"][90]
    if not w["complete"]:
        why = (f"list from {w['list_truncated_from']}" if w.get("list_truncated_from")
               else f"{w['n_filings'] - w['n_missing']}/{w['n_filings']} filings")
        return f'<span class="ptgap">backfill in progress</span><br><span class="tn">{e(why)}</span>'
    if not (w["n_buy_tx"] or w["n_sell_tx"]):
        return f'none on the market<br><span class="tn">{w["n_filings"]} Form 4</span>'
    return (f'<span class="{cls(w["net_usd"])}">net {money(w["net_usd"])}</span><br><span class="tn">'
            f'{plural(w["n_buy_tx"], "buy")} / {plural(w["n_sell_tx"], "sell")}</span>')


def _cong_cell(o):
    if not o or o.get("status") != "ok":
        return gap_cell(o)
    if not o["n"]:
        return '<span class="tn">none filed</span>'
    return (f'{plural(o["buys"], "buy")} / {plural(o["sells"], "sell")}<br><span class="tn">filed by {o["members"]} member'
            f'{"s" if o["members"] != 1 else ""}{" &dagger;" if o["mirror"] else ""}</span>')


# PTR owner codes, as on congressional-activity.html ("Owner: self, SP spouse, JT joint, DC dependent child")
OWNER = {"self": "self", "SP": "SP", "JT": "JT", "DC": "DC", "not_indicated": "not stated"}
OWNER_WORD = {"self": "self", "SP": "spouse", "JT": "joint", "DC": "dependent child", "not_indicated": "not stated"}


def owner_mix(counts):
    """{owner code: n} -> '2 self, 2 spouse, 1 dependent child' (every row of the window, not only the
    detail lines)."""
    c = {}
    for code, n in (counts or {}).items():
        w = OWNER_WORD.get(code, "not stated")
        c[w] = c.get(w, 0) + int(n)
    order = ["self", "spouse", "joint", "dependent child", "not stated"]
    return ", ".join(f"{c[k]} {k}" for k in order if c.get(k))


def _detail(r, ov, meta):
    tk = r["ticker"]
    o = ov.get(tk, {})
    blocks = []
    # exit
    if r["on"]:
        ex = r.get("exit")
        main, sub = exit_text(ex)
        emp = ""
        if ex and ex.get("emp_p20") is not None:
            emp = (f" In the history, names in the same rank band left within 20 td after "
                   f"{_p(ex['emp_p20'])} of {ex['emp_n']} observed name-days (overlapping, so far fewer "
                   f"independent cases than that).")
        m = r.get("margin")
        cut = (f"today it is <b>{num2(m)}</b> above the rank-21 composite" if m == m and abs(m) >= 0.005
               else "today it is level with the rank-21 composite at the published 2 dp (it is ahead on rank)")
        ent = ""
        if r.get("gap_before"):
            ent = (f" It entered after {r['gap_before']} trading day{'s' if r['gap_before'] != 1 else ''} with no "
                   f"ranking, so the true entry may be up to that much earlier.")
        blocks.append(f"""<div class="ptb"><h4>Exit</h4><p>Leaves the list when its composite falls below the #20
cutoff: {cut}. Rank band {e(STATES[state_of(r['rank'])][2])}: median time to first exit <b>{main}</b> ({sub};
{ex['n_obs'] if ex else 0} transitions, {ex['n_dates'] if ex else 0} days).{emp}{ent} Not a forecast: ranks are
re-derived every build.</p></div>""")
    else:
        lo = (f"last on the list {dfmt(r['last_on'], True)}" if r.get("last_on")
              else f"never in the top 20 since the list began ({dfmt(LIST_LAUNCH, True)})")
        m = r.get("margin")
        dist = (f"Composite {num2(m)} from the #20 cutoff" if m == m and abs(m) >= 0.005
                else "Composite level with the #20 cutoff at the published 2 dp (behind it on rank)")
        blocks.append(f'<div class="ptb"><h4>Status</h4><p>Rank {r["rank"]}, {lo}. {dist}.</p></div>')
    # earnings
    eo = o.get("earnings")
    if eo and eo.get("status") == "ok":
        hist = "".join(f'<tr><td>{dfmt(h["quarter"], True)}</td><td class="num">{h["actual"]:.2f}</td>'
                       f'<td class="num">{h["estimate"]:.2f}</td><td class="num {cls(h["surprise"])}">'
                       f'{pct(h["surprise"])}</td></tr>' for h in eo.get("history") or [])
        rv = eo.get("revisions") or {}
        rvt = "".join(f'<tr><td>{ {"0q": "This quarter", "+1q": "Next quarter", "0y": "This year", "+1y": "Next year"}[k]}</td>'
                      f'<td class="num">{(v["eps"] if v["eps"] is not None else float("nan")):.2f}</td>'
                      f'<td class="num {cls(v["chg30"])}">{pct(v["chg30"])}</td><td class="num {cls(v["chg90"])}">'
                      f'{pct(v["chg90"])}</td><td class="num">{int(v["up30"] or 0)}/{int(v["down30"] or 0)}</td></tr>'
                      for k, v in rv.items() if v.get("eps") is not None)
        nxt = eo.get("next")
        nx = (f"Next report {dfmt(nxt['date'], True)}{' (Yahoo marks the date as estimated)' if nxt.get('estimated') else ''}, "
              f"{ {'bmo': 'before the open', 'amc': 'after the close', 'intraday': 'during the session'}.get(nxt['session'], 'time not given')}."
              if nxt else "No upcoming report date published.")
        blocks.append(f"""<div class="ptb"><h4>Earnings</h4><p>{nx}</p>
{('<table class="ptmini"><tr><th>Quarter</th><th>EPS</th><th>Est.</th><th>Surprise</th></tr>' + hist + '</table>') if hist else '<p class="tn">EPS history: ' + e(eo.get('partial') or 'n/a') + '</p>'}
{('<table class="ptmini"><tr><th>EPS estimate</th><th>Now</th><th>30 d</th><th>90 d</th><th>Up/down 30 d</th></tr>' + rvt + '</table>') if rvt else ''}
<p class="tn">Yahoo Finance, as of {dfmt(eo['as_of'], True)}. The time is Yahoo's session code, not a release time.</p></div>""")
    else:
        blocks.append(f'<div class="ptb"><h4>Earnings</h4><p>{gap_cell(eo)}: {gap_why(eo)}</p></div>')
    # analysts + targets
    so, to = o.get("sentiment"), o.get("targets")
    parts = []
    if to and to.get("status") == "ok":
        parts.append(f"Consensus 12-month target {usd(to['mean'])} (median {usd(to.get('median'))}, range "
                     f"{usd(to.get('low'))}–{usd(to.get('high'))}, {to.get('n') or '?'} analysts): "
                     f"{pct(to.get('upside'))} from {usd(to['price'])}. The count includes targets that may be months old.")
    else:
        parts.append(f"Analyst targets: {gap_cell(to)}.")
    m = (to or {}).get("model") or {}
    if m.get("iv"):
        parts.append(f"Picker model value {usd(m['iv'])} ({pct(m.get('upside'))}): a crude two-stage FCF / dividend / "
                     f"DDM estimate with 5-year growth capped at 25%, so it sits far below the price for fast growers. "
                     f"It is not a price target. It enters the composite only through the margin-of-safety variable "
                     f"(its gap to the price, clipped at +100% / −90%) and the Buffett score.")
    if so and so.get("status") == "ok":
        mn, m3 = so.get("mix_now"), so.get("mix_3m")
        if mn:
            parts.append(f"Ratings now: {mn['buy']} buy, {mn['hold']} hold, {mn['sell']} sell"
                         + (f" (buy share {pct(m3['buy_share'], False, 0)} three months ago)." if m3 and m3.get('buy_share') is not None else "."))
        d30, d90 = so.get("d30") or {}, so.get("d90") or {}
        parts.append(f"Rating changes: {d30.get('up', 0)} up / {d30.get('down', 0)} down in 30 days, "
                     f"{d90.get('up', 0)} up / {d90.get('down', 0)} down in 90 days; target raises / cuts "
                     f"{d30.get('pt_up', 0)}/{d30.get('pt_down', 0)} (30 d), {d90.get('pt_up', 0)}/{d90.get('pt_down', 0)} (90 d).")
        if so.get("rec_mean"):
            parts.append(f"Mean recommendation {so['rec_mean']:.1f} (1 = strong buy, 5 = sell).")
    else:
        parts.append(f"Rating trend: {gap_cell(so)}.")
    parts.append("News sentiment: not covered (no honest, reproducible source).")
    blocks.append(f'<div class="ptb"><h4>Analysts</h4><p>{" ".join(parts)}</p><p class="tn">Yahoo Finance aggregates only, '
                  f'no firm names; as of {dfmt((to or so or {}).get("as_of") or meta["today"], True)}.</p></div>')
    # insiders
    io_ = o.get("insiders")
    if io_ and io_.get("status") in ("ok", "partial"):
        wl = []
        for w in (90, 180):
            x = io_["windows"][w]
            if not x["complete"]:
                why = (f"the SEC list held here starts {x['list_truncated_from']}" if x.get("list_truncated_from")
                       else f"{x['n_filings'] - x['n_missing']} of {x['n_filings']} filings parsed so far")
                wl.append(f"<li>{w} days: backfill in progress ({e(why)})</li>")
                continue
            plan = f", {pct(x['plan_share'], False, 0)} of sales under 10b5-1 plans" if x.get("plan_share") is not None else ""
            roles = f"; roles: {e(', '.join(x['roles']))}" if x["roles"] else ""
            wl.append(f"<li>{w} days: {x['n_buy_tx']} purchases (code P; {money(x['buy_usd'])}, {x['n_buyers']} insiders), "
                      f"{x['n_sell_tx']} sales (code S; {money(x['sell_usd'])}, {x['n_sellers']} insiders), net "
                      f"<b>{money(x['net_usd'])}</b>{plan}{roles}. {x['n_filings']} Form 4 filings; "
                      f"{x['n_other_lines']} other lines (grants, exercises, tax withholding, gifts) not counted.</li>")
        dl = "".join(f'<tr><td>{dfmt(d["tx_date"], True)}</td><td>{e(d["name"] or "")}</td><td>{e(d["role"])}</td>'
                     f'<td>{d["side"]} ({"P" if d["side"] == "buy" else "S"}){" non-market" if d["nonmarket"] else ""}'
                     f'{" &middot; 10b5-1" if d["plan"] else ""}</td>'
                     f'<td class="num">{money(d["value"])}</td><td><a href="{e(d["url"])}">Form 4</a></td></tr>'
                     for d in io_.get("detail") or [])
        # The filing list's date is a STAMP only while it is current (guard_freshness grades every "as of"
        # at the daily cadence); an older list is said plainly, with a date but no stamp wording.
        asof_d = str(io_.get("as_of") or "")
        try:
            age = (date.fromisoformat(str(meta["today"])[:10]) - date.fromisoformat(asof_d[:10])).days
        except ValueError:
            age = 99
        src = (f"SEC EDGAR, filing list as of {dfmt(asof_d, True)}." if age <= 1 else
               f"SEC EDGAR. Not refreshed today: the filing list was last fetched on {dfmt(asof_d, True)}.")
        cap = ("Largest P / S lines among the filings parsed so far (backfill incomplete)"
               if not io_["windows"][180]["complete"] else "Largest P / S lines, 180 days")
        blocks.append(f"""<div class="ptb wide"><h4>Insiders (SEC Form 4)</h4><ul class="ptul">{''.join(wl)}</ul>
{('<p class="tn">' + cap + ':</p><table class="ptmini"><tr><th>Traded</th><th>Insider (as filed)</th><th>Role</th><th>Side</th><th>Value</th><th></th></tr>' + dl + '</table>') if dl else ''}
<p class="tn">Code P = open-market or private purchase (lines whose footnotes show a non-market purchase are
excluded from the counts and marked in the table); code S = sale, open market or private. By transaction date
inside the window. The 10b5-1 mark comes from the filing's own Rule 10b5-1 box, or a footnote that says the trade was
made under such a plan. {src}</p></div>""")
    else:
        blocks.append(f'<div class="ptb"><h4>Insiders (SEC Form 4)</h4><p>{gap_cell(io_)}: {gap_why(io_)}</p></div>')
    # congress
    co = o.get("congress")
    if co and co.get("status") == "ok":
        w = co.get("window") or ["?", "?"]
        dl = "".join(f'<tr><td>{dfmt(d["filed"], True)}</td><td>{e(d["member"])} <span class="tn">({e(d["party"] or "?")}-'
                     f'{e(d["state"] or "")})</span></td><td>{e(d["chamber"])}</td><td>{e(OWNER.get(d.get("owner"), "not stated"))}</td>'
                     f'<td>{e(d["side"])}</td><td>{e(d["amount"])}</td>'
                     f'<td>{dfmt(d["traded"], True)}</td><td><a href="{e(d["source"])}">filing</a>{"&dagger;" if d["mirror"] else ""}</td></tr>'
                     for d in co.get("detail") or [])
        stale = f" The weekly file is {co['age_days']} days old." if co.get("stale") else ""
        mix = owner_mix(co.get("owners"))
        body = (f"{plural(co['n'], 'trade')} filed: {plural(co['buys'], 'buy')}, {plural(co['sells'], 'sale')}"
                f"{', ' + str(co['other']) + ' other' if co['other'] else ''}, filed by {co['members']} member"
                f"{'s' if co['members'] != 1 else ''}"
                f"{' (owner: ' + e(mix) + ')' if mix else ''}. A trade filed by a member is often a spouse's, a joint "
                f"or a dependent child's account, as the Owner column shows. Amount bands: "
                f"{e(', '.join(f'{k} ({v})' for k, v in co['bands'].items()))}."
                if co["n"] else "No trades in this ticker were filed in the window.")
        # "disclosures as of" is graded by guard_freshness on the weekly cadence (9 days), like the
        # congressional activity page's own stamp; a daily-cadence label here would go red every Wednesday.
        blocks.append(f"""<div class="ptb wide"><h4>Congress (STOCK Act filings)</h4><p>{body}</p>
{('<table class="ptmini"><tr><th>Filed</th><th>Member</th><th>Chamber</th><th>Owner</th><th>Side</th><th>Amount</th><th>Traded</th><th></th></tr>' + dl + '</table>') if dl else ''}
<p class="tn">Filed {dfmt(w[0], True)} to {dfmt(w[1], True)} (the public dataset keeps 13 weeks; not 365 days). Amounts are the disclosed
ranges. Owner: self, SP spouse, JT joint, DC dependent child, as filed. &dagger; = row from the open Senate / scanned-House
dataset. All rows on the <a href="{e('congressional-activity.html')}">congressional activity page</a>; weekly file,
disclosures as of {dfmt(co['as_of'], True)}.{stale}</p></div>""")
    else:
        blocks.append(f'<div class="ptb"><h4>Congress</h4><p>{gap_cell(co)}: {gap_why(co)}</p></div>')
    return "".join(blocks)


def tracker_section(rows, ov, exit_res, cut, meta):
    trs = []
    for i, r in enumerate(rows):
        tk = r["ticker"]
        o = ov.get(tk, {})
        did = f"ptd-{e(tk)}"
        dash = '<span class="tn">&mdash;</span>'
        if r["on"]:
            mark = ("&ge; " if r.get("censored") else
                    f'<span title="entered after {r["gap_before"]} trading days with no ranking">~</span>'
                    if r.get("gap_before") else "")
            sub = "since the list began" if r.get("launch") else f'{r["td"]} td &middot; {r["cd"]} days'
            since = (f'{mark}{dfmt(r["since"], True)}<br><span class="tn">{sub}</span>'
                     + (f'<br><span class="tn">{r["td"]} td &middot; {r["cd"]} days</span>' if r.get("launch") else ""))
            if r["ret"] == r["ret"]:
                ret = (f'<span class="{cls(r["ret"])}">{pct(r["ret"])}</span><br><span class="tn">SPY {pct(r["spy"])}'
                       f' &middot; univ. {pct(r["ew"])}</span><br><span class="tn">max DD {pct(r["mdd"])}</span>')
            else:
                ret = ('<span class="ptgap" title="the price history has a split-like jump and Yahoo gives no split '
                       'information that rules a split out">n/a (price break)</span>')
            mg = r.get("margin")
            rk = (f'{r["rank"]}<br><span class="tn">entry {r["entry_rank"]}</span><br>'
                  f'<span class="tn {cls(mg) if (mg == mg and abs(mg) >= 0.005) else ""}">{margin_txt(mg, True)}</span>')
            exc = _exit_cell(r.get("exit"))
        else:
            since = (f'off list<br><span class="tn">last on {dfmt(r["last_on"])}</span>' if r.get("last_on")
                     else 'off list<br><span class="tn">never in top 20</span>')
            ret, exc = dash, dash
            mg = r.get("margin")
            rk = (f'{r["rank"]}<br><span class="tn {cls(mg) if (mg == mg and abs(mg) >= 0.005) else ""}">'
                  f'{margin_txt(mg, False)}</span>')
        trs.append(
            f'<tr data-pick="{1 if r["on"] else 0}"{"" if r["on"] else " hidden"}>'
            f'<td><button class="pt-x" type="button" aria-expanded="false" aria-controls="{did}" data-t="{did}" '
            f'aria-label="details for {e(tk)}">+</button></td>'
            f'<td><b>{e(tk)}</b></td><td>{since}</td><td class="num">{ret}</td><td class="num">{rk}</td>'
            f'<td class="num">{exc}</td><td class="num">{_tgt_cell(o.get("targets"))}</td>'
            f'<td>{_earn_cell(o.get("earnings"))}</td><td>{_sent_cell(o.get("sentiment"))}</td>'
            f'<td>{_ins_cell(o.get("insiders"))}</td><td>{_cong_cell(o.get("congress"))}</td></tr>'
            f'<tr class="pt-detail" id="{did}" data-pick="{1 if r["on"] else 0}" hidden><td colspan="11">'
            f'<div class="ptdet">{_detail(r, ov, meta)}</div></td></tr>')
    sp = exit_res.get("spells") or {}
    n_on = sum(1 for r in rows if r["on"])
    gaps = [safe_text(g) for g in (meta.get("gap_lines") or [])]
    gap_note = (f'<p class="note" style="font-size:12px">Data gaps today: {e("; ".join(gaps))}.</p>' if gaps else "")
    rec = meta.get("record") or {}
    rec_note = ""
    if rec and not rec.get("recorded"):
        rec_note = f' Today\'s build is not added to the history ({e(rec.get("why", ""))}).'
    return f"""<section class="block" id="tracker">
<h2>Pick Tracker</h2>
<p class="note">Follows every pick from the day it entered the top 20: how long it has been on the list, how it
has done since (against SPY and the equal-weight universe over the same dates), how far it sits above the cut,
how long names in its rank band have tended to stay, and the analyst, earnings, insider and congressional
context. Open a row (+) for the detail. Built daily from the page's own history ({len(meta['dates'])} daily
rankings since the list began on {dfmt(LIST_LAUNCH, True)}, each dated by the session whose closes it holds; the
latest is the {dfmt(meta['dates'][-1], True)} close).{rec_note} <b>The overlays are context only: they do not change
the composite or the ranks</b>; whether any of them should enter the model is a separate decision. Not advice.</p>
<div class="ptpills" role="group" aria-label="rows">
  <button class="pill on" type="button" data-f="pick">Top-20 picks ({n_on})</button>
  <button class="pill" type="button" data-f="all">All {len(rows)}</button>
</div>
<div class="tile" style="padding:0 14px 8px;overflow-x:auto">
<table class="ptable ptrack"><thead><tr>
<th></th><th>Ticker</th><th>On list since</th><th>Since entry</th><th>Rank</th><th>Exit estimate</th>
<th>Analyst target</th><th>Next earnings</th><th>Analysts</th><th>Insiders 90 d</th><th>Congress</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table></div>
<p class="note" style="font-size:11.5px;margin-top:.9rem">td = NYSE trading days. "Since the list began" = on the
list at every ranking since the composite list was first published ({dfmt(LIST_LAUNCH, True)}), so that tenure is
exact. ~ = the entry follows trading days with no ranking (machine off, refresh failed), so the true entry may be
up to that many days earlier.{' &ge; = already on the list when this history starts, so the true start is earlier.' if sp.get('left_censored') else ''}
Since entry = price change from the first day of the current spell (price only, no dividends; Yahoo-confirmed
splits applied), next to SPY and the buy-and-hold equal-weight universe over the same dates; max DD = worst fall from
a peak since entry, on daily closing prices. Rank: today, at entry, and the composite's margin over the rank-21
composite (picks) or its distance to the rank-20 composite (others), at the published precision (ranks 21-40 are
published at 2 dp, so a gap under 0.01 is a tie there and only the rank decides). Exit estimate = median trading
days until the name first leaves the top 20, from a rank-band Markov chain over {exit_res.get('n_transitions', 0)}
day-to-day moves; range = the model's 10th to 90th percentile of that time (8 in 10 names in the band leave inside
it); then the chance of leaving within 20 trading days, next to how often that happened in the history. Of
{sp.get('n', 0)} spells so far, {sp.get('completed', 0)} ended, after a median of {sp.get('median_td') or 0:.0f}
trading days (middle half {sp.get('q1') or 0:.0f}–{sp.get('q3') or 0:.0f}); {sp.get('le5', 0)} of them lasted 5
days or less, mostly names hovering at the cut. Analyst target = Yahoo Finance consensus mean, upside from today's
price, analyst count and range (aggregates, no firm names); model = the picker's own crude valuation, not a target.
Analysts = share of buy ratings, rating changes and target raises / cuts in 90 days. Insiders = SEC Form 4
purchases (code P) and sales (code S: open market or private). Congress = STOCK Act filings, counted by filing
member (many are a spouse's or a joint account; see the Owner column in the detail; &dagger; open dataset).</p>
{gap_note}
</section>"""


# ============================================================ HTML: track record
def _ok(v):
    return v is not None and not (isinstance(v, float) and not np.isfinite(v))


def _ans(row, h, who):
    """One plain sentence from the numbers; the wording follows the interval, never the other way round."""
    if row is None or not _ok(row.get("lo")):
        k = int(row["k_indep"]) if row is not None else 0
        return f"There are too few independent {h}-day windows ({k}) to compare {who} with the universe."
    lo, hi = row["lo"], row["hi"]
    word = "ahead of" if lo > 0 else "behind" if hi < 0 else "not measurably different from"
    return (f"Over the next {h} trading days, {who} were {word} the equal-weight universe: mean excess "
            f"{pct(row['indep_mean'])} per window, 95% interval {pct(lo)} to {pct(hi)}, "
            f"{int(row['k_indep'])} independent windows.")


def record_section(tr, chart_html="", macro=None):
    """macro = {"date": iso, "age_days": n} of the capstone macro inputs (file date, read at build time), so the
    caveat about frozen inputs is said only while it is true."""
    ps = tr["persistence"]
    bs = tr["basket_summary"]
    coh = tr["cohort"]

    def get(h, b):
        x = ps[(ps.h == h) & (ps.bucket == b)] if len(ps) else ps
        return x.iloc[0].to_dict() if len(x) else None
    long10 = _ans(get(10, "60+ td"), 10, "picks already on the list 60 trading days or more")
    all10 = _ans(get(10, "top20"), 10, "all top-20 picks together")
    rows = ""
    labels = {"0-19 td": "On list 0-19 td", "20-59 td": "On list 20-59 td", "60+ td": "On list 60+ td",
              "top20": "All top-20 picks", "rank21_40": "Ranks 21-40"}
    for b in ["0-19 td", "20-59 td", "60+ td", "top20", "rank21_40"]:
        cells = ""
        for h in HORIZONS:
            x = get(h, b)
            if x is None:
                cells += '<td class="num">n/a</td>'
                continue
            ci = (f"{pct(x['lo'])} to {pct(x['hi'])} (mean {pct(x['indep_mean'])})" if _ok(x["lo"])
                  else "too few windows")
            cells += (f'<td class="num"><span class="{cls(x["mean"])}">{pct(x["mean"], True, 2)}</span><br>'
                      f'<span class="tn">95%: {ci}</span><br>'
                      f'<span class="tn">{int(x["k_indep"])} indep. windows &middot; hit {pct(x["hit"], False, 0)}</span><br>'
                      f'<span class="tn">{int(x["n_obs"])} obs / {int(x["n_dates"])} days</span></td>')
        rows += f'<tr><td>{labels[b]}</td>{cells}</tr>'
    spy_txt = f", SPY {pct(bs['spy'])}" if _ok(bs.get("spy")) else ", SPY not available today (data gap)"
    coh_txt = ""
    if coh["n"] and _ok(coh.get("mean")) and _ok(coh.get("ew")):
        if _ok(coh.get("lo")):
            word = ("ahead of" if coh["lo"] > 0 else "behind" if coh["hi"] < 0 else "not measurably different from")
            ci = (f" (mean excess {pct(coh['excess'])}, 95% interval {pct(coh['lo'])} to {pct(coh['hi'])} across its "
                  f"{coh['n_priced']} names)")
        else:
            word, ci = "not comparable with", f" (too few names with a clean price history: {coh['n_priced']})"
        excl = ""
        if coh.get("excluded"):
            excl = (f" {', '.join(coh['excluded'])} {'is' if len(coh['excluded']) == 1 else 'are'} left out of that "
                    f"average: a split-like price jump that Yahoo's split information does not rule out makes "
                    f"{'its' if len(coh['excluded']) == 1 else 'their'} return n/a.")
        coh_txt = (f" The {coh['n']} names on the list at every ranking since it began ({dfmt(coh['from'], True)}) "
                   f"returned {pct(coh['mean'])} on average, {word} the buy-and-hold equal-weight universe over "
                   f"the same dates ({pct(coh['ew'])}){ci}"
                   + (f"; SPY returned {pct(coh['spy'])}" if _ok(coh.get("spy")) else "")
                   + "." + excl
                   + " That group is chosen after the fact (the names that stayed), so it describes the past and"
                     " says nothing about what comes next; its names move together, so even this interval is too"
                     " narrow. Individual names spread widely around the average (detail rows above).")
    drop = bs.get("dropped") or {}
    drop_txt = (f" Name-intervals left out because a split-like jump makes the return n/a: "
                f"{', '.join(f'{k} ({v})' for k, v in sorted(drop.items()))}." if drop else "")
    n_rank = bs.get("n_rankings") or (bs["n"] + 1)
    months = max(1, round(((pd.Timestamp(bs["to"]) - pd.Timestamp(bs["from"])).days) / 30.4)) if bs.get("from") else 0
    lb = tr.get("long_bucket") or {}
    if lb.get("names"):
        share = lb.get("launch_share")
        lbt = (f"the 60+ td group is {len(lb['names'])} names"
               + (f", {pct(share, False, 0)} of its observations from names on the list since it began"
                  if share is not None else ""))
    else:
        lbt = "no name has reached 60 td yet"
    mi = macro or {}
    mtxt = ""
    if mi.get("date") and mi.get("age_days") is not None and mi["age_days"] > 30:
        mtxt = (f" the macro inputs to the composite (betas, P/E, the FOMC target) were last refreshed on "
                f"{dfmt(mi['date'], True)}, which keeps ranks sticky and tenure long;")
    part = (f" {bs['n_partial']} partial ranking{'s' if bs['n_partial'] != 1 else ''} (fewer names than the "
            f"universe) {'are' if bs['n_partial'] != 1 else 'is'} not used to form baskets or move tenure."
            if bs.get("n_partial") else "")
    return f"""<section class="block" id="track-record">
<h2>Track Record: will they keep doing well?</h2>
<p class="note">Several picks have been on the list for months, and some did very well. This section asks what the
page's own history says about what tends to come next. {long10} {all10}{coh_txt} The history is short
({n_rank} daily rankings, {dfmt(bs['from'], True)} to {dfmt(bs['to'], True)}); none of this is a forecast or advice.</p>
<div class="tile chart"><div class="ch">{chart_html}</div></div>
<p class="note" style="font-size:12.5px">Follow-the-list basket (equal-weight top 20, re-formed at every daily ranking,
price only): top 20 {pct(bs['top20'])}, equal-weight universe rebalanced at each ranking {pct(bs['ew'])}, ranks 21-40
{pct(bs['rest'])}{spy_txt}. The top 20 beat the universe in {bs['beats']} of {bs['n']} day-to-day intervals. Each basket
is formed at the close of the day it was ranked, and the ranking is published only after that close, so these are
not returns anyone could have traded at those prices.{drop_txt}{part} The rebalanced universe differs from the
buy-and-hold universe used in the rows above and in the cohort sentence.</p>
<h3>Forward excess return vs the equal-weight universe</h3>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable ptrec"><thead><tr><th>Group (tenure at the start)</th><th>Next 5 td</th><th>Next 10 td</th>
<th>Next 20 td</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="note" style="font-size:11.5px;margin-top:.9rem">Mean = average over every (day, name) observation; hit =
share of observations beating the universe. The 95% interval uses only independent (non-overlapping) windows,
one average per window, so it is wide and honest about how little data there is. Caveats: about {months} month{'s' if months != 1 else ''}
of history; overlapping windows within the means; tech-heavy names move together, so observations are not
independent; {lbt}; the universe is a fixed 40-name list chosen before the sample;{mtxt} prices are daily closing
quotes, price return only. Past behaviour of the list does not predict its future. Not investment advice.</p>
</section>"""


def record_figure(tr):
    import plotly.graph_objects as go
    bk = tr["basket"]
    if bk is None or bk.empty:
        return None
    x = [bk["from"].iloc[0]] + bk["to"].tolist()
    fig = go.Figure()
    series = [("cum_top20", "Top 20 (follow the list)", "#0a2540", 2.2),
              ("cum_ew", "Equal-weight universe (rebalanced)", "#9aa5b1", 1.6),
              ("cum_rest", "Ranks 21-40", "#5b7c99", 1.4)]
    if bk["spy"].notna().all():
        series.append(("cum_spy", "SPY", "#0f766e", 1.4))
    for col, name, color, wd in series:
        y = [0.0] + (bk[col] * 100).round(4).tolist()
        fig.add_scatter(x=x, y=y, mode="lines", name=name, line=dict(color=color, width=wd),
                        hovertemplate="%{x|%d %b %Y}: %{y:.2f}%<extra>" + name + "</extra>")
    fig.update_layout(title="Cumulative price return since tracking began (%)",
                      yaxis=dict(ticksuffix="%", tickformat=",.0f", hoverformat=",.2f"),
                      xaxis=dict(tickformat="%b %Y", hoverformat="%d %b %Y"),
                      legend=dict(orientation="h", y=-0.2), height=360)
    return fig


TRACKER_CSS = r"""
.ptpills{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 14px}
table.ptrack td{vertical-align:top}
table.ptrack th,table.ptrack>tbody>tr:not(.pt-detail)>td{white-space:nowrap;padding:8px 9px}
table.ptrack tr[hidden]{display:none}
table.ptrack>tbody>tr:not(.pt-detail) .ptgap{display:inline-block;max-width:9.5em;white-space:normal;line-height:1.3}
.ptb.wide{grid-column:1/-1}
table.ptrec td{white-space:nowrap;vertical-align:top}table.ptrec .tn{font-size:11px;color:#888}
table.ptmini th,table.ptmini td{white-space:nowrap}
table.ptrack td:nth-child(2){font-family:'Inter',sans-serif}
table.ptrack .tn{font-size:11px;color:#888}
.pt-x{font:500 13px 'JetBrains Mono',monospace;width:24px;height:24px;line-height:20px;padding:0;border:1px solid #d4d4d4;
background:#fff;color:#0a2540;cursor:pointer;border-radius:0}
.pt-x:hover{background:rgba(10,37,64,.05)}
.ptgap{font-size:11.5px;color:#888;font-style:italic}
tr.pt-detail td{background:#fbfbfb;white-space:normal;text-align:left}
tr.pt-detail:hover td{background:#fbfbfb}
.ptdet{position:sticky;left:0;max-width:min(980px,84vw);display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
gap:12px 22px;padding:8px 2px 12px;font-size:12.5px;line-height:1.5;color:#333}
.ptb h4{font:500 11px 'Inter',sans-serif;letter-spacing:.06em;text-transform:uppercase;color:#888;margin:0 0 4px}
.ptb p{margin:0 0 6px}.ptul{margin:0 0 6px 16px;padding:0}
table.ptmini{border-collapse:collapse;font-size:11.5px;margin:4px 0 6px;font-variant-numeric:tabular-nums}
table.ptmini th{color:#888;font-weight:500;text-align:left;padding:2px 8px 2px 0;border-bottom:1px solid #e5e5e5}
table.ptmini td{padding:2px 8px 2px 0;border-bottom:1px solid #f0f0f0;text-align:left}
table.ptmini td.num{text-align:right;font-family:'JetBrains Mono',ui-monospace,monospace}
@media(max-width:560px){.ptdet{grid-template-columns:1fr;max-width:86vw}}
"""

TRACKER_JS = r"""<script>
(function(){
document.querySelectorAll('.pt-x').forEach(function(b){b.addEventListener('click',function(){
  var r=document.getElementById(b.getAttribute('data-t'));if(!r)return;var open=r.hasAttribute('hidden');
  if(open){r.removeAttribute('hidden');}else{r.setAttribute('hidden','');}
  b.setAttribute('aria-expanded',open?'true':'false');b.textContent=open?'−':'+';});});
document.querySelectorAll('.ptpills').forEach(function(g){g.querySelectorAll('.pill').forEach(function(b){
  b.addEventListener('click',function(){g.querySelectorAll('.pill').forEach(function(x){x.classList.remove('on');});
  b.classList.add('on');var all=b.getAttribute('data-f')==='all';
  document.querySelectorAll('table.ptrack tbody tr').forEach(function(tr){
    var pick=tr.getAttribute('data-pick')==='1';
    if(tr.classList.contains('pt-detail')){if(!all&&!pick){tr.setAttribute('hidden','');}return;}
    if(all||pick){tr.removeAttribute('hidden');}else{tr.setAttribute('hidden','');}});});});});
})();
</script>"""


def methodology_html():
    return """<p><b>Pick Tracker.</b> Every build adds the full ranking to <code>data/picks_history.csv</code>
(rebuilt once from the page's committed history). Each ranking is dated by the trading session whose closing
prices it holds: a build after the close counts for that day, a build after midnight or before the open for the
previous session (only when that session has no ranking of its own), and a build during the session is not
recorded. A re-run on the same day replaces that day, never duplicates it. Composites are stored at the precision
the page publishes. A day the picker could not rebuild the page is a gap: nothing is carried forward. Tenure is
counted between rankings that exist: a gap inside a spell does not interrupt it, and an entry or exit next to a gap
is dated by the first / last ranking that shows it (the true date lies inside the gap; entries after a gap are
marked ~). A partial ranking (fewer names than the universe) keeps its prices, but its top 20 is not used. Splits
are applied only when Yahoo confirms them; a split-like jump makes returns across it n/a unless Yahoo's own split
record (a last split earlier than the jump) shows it was a real price move.</p>
<p><b>Exit estimate.</b> A pick leaves the list when its composite falls below the #20 cutoff. The estimate is
empirical: a Markov chain over rank bands fitted to all day-to-day moves between full rankings. The page shows the
median time to first exit and the model's range for it (10th to 90th percentile: 8 in 10 names starting in the band
leave inside it); a block bootstrap gives the uncertainty of the median itself. Fewer than 30 moves or 15 days in a
band reads "insufficient history", and anything longer than the history itself reads "&gt; N td" (N = trading days
tracked so far), because the history cannot date an exit further out than that. Next to the model's chance of
leaving within 20 trading days the page shows how often that actually happened in the history (counted over
overlapping name-days, so it rests on far fewer independent cases than its count); the chain ignores how sticky a
name's band is, so it tends to overstate movement in the middle bands. Ranks are re-derived every build, so a pick
can leave in one day when the inputs move.</p>
<p><b>Overlays.</b> Earnings dates, surprises and estimate revisions, analyst ratings and consensus targets come from
Yahoo Finance (aggregates only, fetched every build; a block or outage makes the cell read "not available today",
never yesterday's value). Insider trades come from SEC EDGAR Form 4 filings (purchases, code P, and sales, code S,
open market or private; non-market purchases excluded; plan sales flagged; names as filed); a new issuer is
backfilled over several days and says so until complete. Congress trades come from the site's weekly STOCK Act
dataset, counted by the member who filed them, with the owner (self, spouse, joint, dependent child) as filed.
News sentiment is not covered. None of the overlays enters the composite or the ranks.</p>"""


def ai_fields(rows, ov):
    """Extra stocks.ai.txt columns, appended at the END of each top-20 line (old parsers ignore them)."""
    out = {}
    for r in rows:
        if not r["on"]:
            continue
        tk = r["ticker"]
        o = ov.get(tk, {})
        to, eo = o.get("targets") or {}, o.get("earnings") or {}
        nx = eo.get("next") if eo.get("status") == "ok" else None
        ex = r.get("exit") or {}
        span = int(ex.get("span_td") or H_MAX) if ex else H_MAX
        exm = "na" if not ex or ex.get("insufficient") else (
            f">{span}" if (not np.isfinite(ex["median"]) or ex["median"] > span) else f"{ex['median']:.0f}")
        f = lambda v, k=100, d=1: "na" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v * k:+.{d}f}"  # noqa: E731
        out[tk] = [(">=" if r.get("censored") else "") + str(r.get("since") or "na"),
                   str(r.get("td") or "na"), f(r.get("ret")), f(r.get("ex_spy")), exm,
                   f"{to['mean']:.2f}" if to.get("status") == "ok" else "na",
                   f(to.get("upside")) if to.get("status") == "ok" else "na",
                   f"{nx['date']} {nx['session']}" if nx else "na"]
    return out


AI_HEADER5 = ("tracker fields (appended; na = not available today; on_list_since prefixed >= only when the spell began "
              "before the stored history): on_list_since|td_on_list|ret_since_entry_pct|"
              "vs_spy_pp|exit_median_td|target_mean|target_upside_pct|next_earnings")
