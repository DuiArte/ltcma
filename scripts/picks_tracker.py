"""picks_tracker -- Pick Tracker and Track Record sections of docs/stocks.html (wave 13, 2026-11-04).

Everything here is computed from data/picks_history.csv (the page's own published ranking, day by day), the
overlays (picks_overlays) and SPY closes. Nothing here feeds the composite, the ranks or the weights.

LIST RULE (wave 14, 2026-11-04): the published list is 20 names, a TWO-SIDED band at the cut
  (picks_history.published_list): a name already on it stays while it ranks <= 25 (STAY); a name off it ranked
  <= 15 (ENTER) always enters and displaces the worst-ranked pick; the remaining places go to the best-ranked
  names. Before wave 14 the list was the plain top 20, and the stored history keeps what was published.
METHOD CHANGES (wave 14): method_info() dates, from the history itself, the first ranking on refreshed macro
  inputs (macro_through) and the first band ranking; entries and exits at those rankings are annotated as a
  method change, the move into the macro-refresh ranking is left out of the exit model, and the Track Record
  says that the rankings before it used inputs frozen at May 2026 data.
EXIT ESTIMATE (empirical, no pretend precision)
  * Deterministic trigger: a pick leaves when its rank falls below 25, i.e. when 25 other names overtake it.
    The page shows today's margin over the rank-26 composite. A pick ranked 21-25 can also be DISPLACED, when
    a name off the list ranks 15th or better and the pick is the worst-ranked one (a pick ranked 1-20 never
    is). The chain below models only the rank exit, so for picks ranked 21-25 it can overstate the stay; the
    page says so and counts the displacements the replay shows.
  * Statistical estimate: a Markov chain over rank states (1-5, 6-10, 11-15, 16-20, 21-23, 24-25, below 25)
    fitted to every pair of consecutive FULL snapshots exactly one NYSE trading day apart (a partial snapshot
    is skipped, and so is the move INTO the first ranking on refreshed macro inputs, a one-off method change),
    over every name ranked 25 or better on the first day (ranks do not depend on membership, so names off the
    list in 21-25 move like listed ones). "Below 25" is absorbing for the time to the FIRST exit. From today's
    state: median trading days
    until the name first leaves, the model's PREDICTIVE range of that time (10th-90th percentile of the
    first-exit distribution: 8 in 10 names starting in the band leave inside it), and the probability it
    leaves within 20 trading days. The moving-block bootstrap over dates (blocks of 10 days, 300 draws,
    fixed seed) gives the uncertainty OF THE MEDIAN only, and is labelled so (wave-13 fix: it used to be
    printed as if it were the range of exit times, which overstated precision about tenfold).
    A state with fewer than 30 observed transitions or 15 distinct days is "insufficient history". Anything
    longer than the history itself (N trading days tracked) is printed as "> N td" (computed up to
    H_MAX = 250). Next to it: the model-free share of past name-days in the same state after which the name
    ranked below 25 within 20 td (overlapping name-days, so its effective sample is far smaller than its count).
RULE REPLAY (in-sample, wave 14): three rules replayed on the SAME stored rankings (plain top 20; the
  one-sided band, stay while rank <= 25, the rejected variant; the two-sided band 15/25), full rankings only:
  entries, rankings with a change, distinct names, spells, short spells, rankings with a top-10 / top-15 name
  kept off the list, follow-the-list basket. 15/25 were chosen on the ranks-only columns (turnover and
  kept-off counts), never on returns; the basket column is in-sample and is not evidence.
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

from picks_history import (BAND, ENTER, EXIT_RANK, LIST_LAUNCH, Panel, RULE_BAND, RULE_FALLBACK,  # noqa: F401
                            RULE_ONE_SIDED, STAY, TOP_N, published_list)

# Frozen capstone macro inputs before wave 14 (facts read from the 2026-06-10 files, wave-14 capstone lane):
# producer run 2026-05-20 on data through 2026-05-19; its USD/CAD series (a static export) ended 2025-11-27.
FROZEN_DATA = "May 2026"
FROZEN_CAD_END = "2025-11-27"

# rank bands of the exit model: the old 16-18 / 19-20 pair at the plain cut moved 5 places down with the band
STATES = [(1, 5, "1-5"), (6, 10, "6-10"), (11, 15, "11-15"), (16, 20, "16-20"), (21, 23, "21-23"),
          (24, EXIT_RANK, f"24-{EXIT_RANK}")]
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
def _macro_break(p):
    """The first ranking on refreshed macro inputs (a one-off method change), or None."""
    try:
        return p.macro_since()[0]
    except Exception:                                                   # noqa: BLE001
        return None


def _transitions(p):
    """[(pair index, origin date, from state, to state)] over consecutive 1-trading-day snapshot pairs. The move
    into the first ranking on refreshed macro inputs is skipped: it is a change of method, not rank dynamics."""
    out, k = [], 0
    part = set(getattr(p, "partial", []) or [])
    brk = _macro_break(p)
    for d0, d1 in zip(p.dates[:-1], p.dates[1:]):
        if p.tdi[d1] - p.tdi[d0] != 1 or d0 in part or d1 in part or d1 == brk:
            continue
        r0, r1 = p.rank.loc[d0], p.rank.loc[d1]
        for tk in p.rank.columns:
            a, b = r0.get(tk), r1.get(tk)
            if pd.isna(a) or pd.isna(b) or a > EXIT_RANK:
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
    # round 3 (L4): how many of the fitted moves come from the frozen-input period (both rankings before the first
    # ranking on refreshed inputs, read from macro_through; every move while no ranking is dated yet)
    brk = _macro_break(p)
    res = {"n_pairs": n_pairs, "n_transitions": len(tr), "states": [],
           "n_frozen": sum(1 for _k, d0, _a, _b in tr if brk is None or d0 < brk),
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
    """Model-free: share of (day, name) observations in each state after which the name ranked below the exit
    line (rank > EXIT_RANK) on some full ranking within the next 20 trading days (only days with >= 20 td of
    history after them). Ranks only, so it reads the same under either list rule."""
    hits, n = np.zeros(OFF), np.zeros(OFF)
    last_td = p.tdi[p.dates[-1]]
    part = set(getattr(p, "partial", []) or [])
    for i, d in enumerate(p.dates):
        if last_td - p.tdi[d] < 20:
            break
        if d in part:
            continue
        fut = [x for x in p.dates[i + 1:] if p.tdi[x] - p.tdi[d] <= 20 and x not in part]
        for tk in p.rank.columns:
            r = p.rank.at[d, tk]
            if pd.isna(r) or r > EXIT_RANK:
                continue
            s = state_of(r)
            n[s] += 1
            if any((p.rank.at[x, tk] == p.rank.at[x, tk]) and p.rank.at[x, tk] > EXIT_RANK for x in fut):
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


def _basket_rows(p, top, spy=None, dropped=None):
    """Follow-the-list basket for a membership frame `top` (date x ticker, 1 on / 0 off / NaN unobserved):
    formed on full rankings only; an interval with no trading day (a holiday snapshot repeating the prior
    close) is skipped rather than counted as a tie / loss."""
    part = set(getattr(p, "partial", []) or [])
    full = [d for d in p.dates if d not in part]
    rows = []
    for d0, d1 in zip(full[:-1], full[1:]):
        if p.tdi[d1] - p.tdi[d0] <= 0:
            continue
        on = [tk for tk in top.columns if top.at[d0, tk] == 1]
        off = [tk for tk in top.columns if top.at[d0, tk] == 0]
        if dropped is not None:
            for tk in on + off:
                if p.window_ret(tk, d0, d1) != p.window_ret(tk, d0, d1) and not (
                        pd.isna(p.adj.at[d0, tk]) or pd.isna(p.adj.at[d1, tk])):
                    dropped[tk] = dropped.get(tk, 0) + 1    # priced on both days, n/a only for a price break
        rows.append({"from": d0, "to": d1, "top20": p.ew_ret(d0, d1, on)[0], "rest": p.ew_ret(d0, d1, off)[0],
                     "ew": p.ew_ret(d0, d1)[0], "spy": spy_ret(spy, d0, d1)})
    return pd.DataFrame(rows, columns=["from", "to", "top20", "rest", "ew", "spy"])


REPLAY_RULES = (("plain", None, None), ("one_sided", STAY, None), ("two_sided", STAY, ENTER))


def rule_replay(p):
    """In-sample replay of three list rules on the same stored rankings (ranks and composites never change):
    the plain top 20; the one-sided band (a listed name stays while rank <= 25; the rejected variant); the
    two-sided band (stay while rank <= 25, enter at rank <= 15). Full rankings only; each band starts from the
    first ranking's plain top 20 and carries its own list forward ranking by ranking (a day with no ranking is
    skipped, as the live rule reads the last recorded list). kept10 / kept15 = rankings on which a name ranked
    10th / 15th or better was off the list. The basket numbers are in-sample and are not evidence."""
    part = set(getattr(p, "partial", []) or [])
    full = [d for d in p.dates if d not in part]
    out = {"n_rankings": len(full), "from": full[0] if full else None, "to": full[-1] if full else None,
           "stay": STAY, "enter": ENTER, "rules": {}}
    for name, stay, enter in REPLAY_RULES:
        fr = pd.DataFrame(np.nan, index=p.dates, columns=p.rank.columns)
        prev = None
        kept10 = kept15 = displaced = 0
        for d in full:
            ranks = p.rank.loc[d].dropna().astype(int).to_dict()
            mem = published_list(ranks, prev if stay is not None else None, stay or STAY, enter)
            fr.loc[d, list(ranks)] = 0.0
            fr.loc[d, mem] = 1.0
            ms = set(mem)
            kept10 += any(r <= 10 and t not in ms for t, r in ranks.items())
            kept15 += any(r <= 15 and t not in ms for t, r in ranks.items())
            if prev is not None and stay is not None:
                displaced += sum(1 for t in set(prev) - ms if ranks.get(t, 10 ** 6) <= stay)
            prev = mem
        sp = p.spells_of(fr)
        done = sp[~sp.ongoing]
        entries, changed_days = 0, 0
        for d0, d1 in zip(full[:-1], full[1:]):
            a = set(fr.columns[fr.loc[d0] == 1])
            new = set(fr.columns[fr.loc[d1] == 1]) - a
            entries += len(new)
            changed_days += bool(new)
        bk = _basket_rows(p, fr)
        cum = float((1 + bk["top20"].fillna(0)).prod() - 1) if len(bk) else None
        out["rules"][name] = {"frame": fr, "spells": len(sp), "completed": len(done),
                              "le5": int((done.trading_days <= 5).sum()) if len(done) else 0,
                              "median_td": float(done.trading_days.median()) if len(done) else None,
                              "entries": entries, "changed_days": changed_days,
                              "turnover": entries / (TOP_N * max(1, len(full) - 1)),
                              "names": int((fr == 1).any().sum()), "basket": cum,
                              "ew": float((1 + bk["ew"].fillna(0)).prod() - 1) if len(bk) else None,
                              "kept10": int(kept10), "kept15": int(kept15), "displaced": int(displaced)}
    pl, bd = out["rules"]["plain"], out["rules"]["two_sided"]
    out["short_avoided"] = pl["le5"] - bd["le5"]
    return out


def track_record(p, spy=None):
    out = {}
    part = set(getattr(p, "partial", []) or [])
    full = [d for d in p.dates if d not in part]
    cache, dropped = {}, {}
    bk = _basket_rows(p, p.top, spy, dropped)
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
    out["replay"] = rule_replay(p)
    out["method"] = method_info(p)
    out["band_since"] = out["method"]["band_since"]
    return out


def method_info(p, mem=None, rec=None, macro=None):
    """The wave-14 method changes, dated from the stored history (so every later build says the same):
      band_since    first ranking published under a band rule (or today's session when today's build uses the
                    band but is not recorded yet); band_fallbacks = later rankings that fell back to the plain
                    top 20;
      macro_since   first ranking made with refreshed (dated) macro inputs; frozen_from / frozen_to = the
                    rankings that used the frozen May 2026 inputs; undated_after = later rankings without a date;
      changes       {ranking: {"what": [...], "entered": [...], "left": [...]}}: the list moves at a method change,
                    which are not ordinary turnover.
    mem / rec / macro = today's membership, history record and macro inputs (all optional)."""
    dates = list(p.dates)
    out = {"band_since": None, "band_fallbacks": [], "macro_since": None, "frozen_from": dates[0] if dates else None,
           "frozen_to": None, "undated_after": 0, "changes": {}, "today_refreshed": False}
    try:
        bs, fb = p.band_since()
        ms, last_frozen, und = p.macro_since()
    except Exception:                                                   # noqa: BLE001
        bs, fb, ms, last_frozen, und = None, [], None, (dates[-1] if dates else None), 0
    today = (rec or {}).get("session")
    recorded = bool((rec or {}).get("recorded"))
    if bs is None and str((mem or {}).get("rule", "")).startswith("band") and today and not recorded:
        bs = today                                    # today's build uses the band but is not in the history
    out.update(band_since=bs, band_fallbacks=fb, macro_since=ms, frozen_to=last_frozen if ms else
               (dates[-1] if dates else None), undated_after=und)
    out["today_refreshed"] = bool(macro and macro.get("basis") == "data through")
    out["pre_listing"] = (macro or {}).get("pre_listing") or ""
    whats = {}
    if ms:
        whats.setdefault(ms, []).append("macro")
    if bs and bs in dates:
        whats.setdefault(bs, []).append("band")
    part = set(getattr(p, "partial", []) or [])
    for d, what in sorted(whats.items()):
        i = dates.index(d)
        prev = next((x for x in reversed(dates[:i]) if x not in part), None)
        ent = lft = []
        if prev is not None and d not in part:
            a = set(p.top.columns[p.top.loc[prev] == 1])
            b = set(p.top.columns[p.top.loc[d] == 1])
            ent, lft = sorted(b - a), sorted(a - b)
        out["changes"][d] = {"what": what, "entered": ent, "left": lft, "prev": prev}
    return out


def method_change_txt(mi, short=False):
    """One sentence per method-change ranking (dates in the page's format)."""
    parts = []
    for d, c in sorted((mi or {}).get("changes", {}).items()):
        w = []
        if "macro" in c["what"]:
            w.append(f"the macro inputs were refreshed for the first time since {FROZEN_DATA}")
        if "band" in c["what"]:
            w.append("the list rule became the two-sided band")
        mv = ""
        if c.get("entered") or c.get("left"):
            mv = (f": {len(c['entered'])} name{'s' if len(c['entered']) != 1 else ''} entered"
                  + (f" ({', '.join(c['entered'])})" if c["entered"] and not short else "")
                  + f" and {len(c['left'])} left" + (f" ({', '.join(c['left'])})" if c["left"] and not short else "")
                  + " at that change, which is not ordinary turnover")
        parts.append(f"The {dfmt(d, True)} ranking is a method change ({' and '.join(w)}){mv}.")
    return " ".join(parts)


# ============================================================ per-ticker tracker rows
def tracker_rows(p, exit_res, spy=None):
    """One row per name of the last ranking. "on" = on the PUBLISHED list (the star; since wave 14 a listed
    name stays while it ranks <= 25). A pick's margin is over the rank-26 composite (the name it must stay
    ahead of); a name off the list gets its place in line (best-ranked first) for the next free place."""
    last = p.dates[-1]
    c20, c21 = p.cutoff(last)
    _c25, c26 = p.cutoff(last, EXIT_RANK)
    sp = p.spells()
    st_by = {r["state"]: r for r in exit_res.get("states", [])}
    rows = []
    order = p.rank.loc[last].dropna().sort_values().index.tolist()
    on_last = {tk for tk in order if p.top_raw.at[last, tk] == 1}
    if not on_last:                                    # a history without membership: the plain top 20
        on_last = {tk for tk in order if int(p.rank.at[last, tk]) <= TOP_N}
    queue = [tk for tk in order if tk not in on_last]
    try:
        changes = set(p.method_changes())
    except Exception:                                                   # noqa: BLE001
        changes = set()
    for tk in order:
        rank = int(p.rank.at[last, tk])
        comp = p.comp.at[last, tk]
        s_tk = sp[sp.ticker == tk]
        cur = s_tk[s_tk.ongoing]
        row = {"ticker": tk, "rank": rank, "on": tk in on_last, "sector": p.sector.get(tk), "n_spells": len(s_tk),
               "composite": comp, "price": p.px.at[last, tk], "by_band": tk in on_last and rank > TOP_N}
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
                       mdd=p.max_drawdown(tk, d0, last), margin=(comp - c26) if c26 == c26 else np.nan,
                       broken=any(b["ticker"] == tk and d0 <= b["from"] for b in p.breaks),
                       at_change=d0 in changes)
            row["exit"] = st_by.get(state_of(rank))
        elif row["on"]:                     # on today's list but no observed spell (cannot happen with a full
            row.update(since=last, td=1, cd=1, launch=False, censored=False, gap_before=0,   # last ranking)
                       entry_rank=rank, entry_price=float(p.adj.at[last, tk]), ret=np.nan, ew=np.nan,
                       spy=np.nan, ex_ew=np.nan, ex_spy=np.nan, mdd=np.nan,
                       margin=(comp - c26) if c26 == c26 else np.nan, broken=False)
            row["exit"] = st_by.get(state_of(rank))
        else:
            prev = s_tk[~s_tk.ongoing]
            row.update(last_on=prev.last_on_list.max() if len(prev) else None,
                       margin=(comp - c20) if c20 == c20 else np.nan, in_line=queue.index(tk) + 1)
        rows.append(row)
    return rows, {"c20": c20, "c21": c21, "c26": c26, "last": last}


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


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def margin_txt(m, on, in_line=None):
    """A pick's distance to its exit line at the published precision: its composite over the rank-26
    composite (since wave 14 a listed name leaves only when it ranks below 25). Names off the list are
    published at 2 dp, so a gap under 0.01 is a tie at that precision and its sign means nothing: say that
    the RANK keeps the name ahead instead of printing "+0.00 vs #26". A name off the list gets its place in
    line for the next free place (the best-ranked name off the list is 1st), not a composite gap: under the
    band it enters only when a pick drops below 25."""
    if not on:
        return f"{ordinal(in_line)} in line" if in_line else "n/a"
    if m is None or (isinstance(m, float) and not np.isfinite(m)):
        return "n/a"
    if abs(m) < 0.005:
        return f"&lt;0.01 above #{EXIT_RANK + 1}"
    return f"{num2(m)} vs #{EXIT_RANK + 1}"


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


def ir_min_indep():
    """insider_record.MIN_INDEP (k of n is shown only from this many independent windows)."""
    try:
        import insider_record as ir
        return ir.MIN_INDEP
    except Exception:                                                   # noqa: BLE001
        return 3


def ir_h():
    """The insider-record horizon (insider_record.HORIZON_TD)."""
    try:
        import insider_record as ir
        return ir.HORIZON_TD
    except Exception:                                                   # noqa: BLE001
        return 60


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
            emp = (f" In the history, names in the same rank band ranked below {EXIT_RANK} within 20 td after "
                   f"{_p(ex['emp_p20'])} of {ex['emp_n']} observed name-days (overlapping, so far fewer "
                   f"independent cases than that).")
        m = r.get("margin")
        nxt = EXIT_RANK + 1
        cut = (f"today it is <b>{num2(m)}</b> above the rank-{nxt} composite" if m == m and abs(m) >= 0.005
               else f"today it is level with the rank-{nxt} composite at the published 2 dp (it is ahead on rank)")
        band = (f" It ranks {r['rank']}, outside the top {TOP_N}: it stays because it was already on the list "
                f"and still ranks {EXIT_RANK} or better. It can also be displaced earlier: when a name off the list "
                f"ranks {ENTER}th or better, the worst-ranked pick leaves to make room (the estimate below counts "
                f"only the rank exit, so it can overstate the stay)." if r.get("by_band") else "")
        chg = (f" It entered at the {dfmt(r['since'], True)} ranking, a method change (see the note above), "
               f"not ordinary turnover." if r.get("at_change") else "")
        ent = ""
        if r.get("gap_before"):
            ent = (f" It entered after {r['gap_before']} trading day{'s' if r['gap_before'] != 1 else ''} with no "
                   f"ranking, so the true entry may be up to that much earlier.")
        blocks.append(f"""<div class="ptb"><h4>Exit</h4><p>Leaves the list when its rank falls below {EXIT_RANK}:
{cut}.{band}{chg} Rank band {e(STATES[state_of(r['rank'])][2])}: median time to
first exit <b>{main}</b> ({sub}; {ex['n_obs'] if ex else 0} transitions, {ex['n_dates'] if ex else 0} days).{emp}{ent}
Not a forecast: ranks are re-derived every build.</p></div>""")
    else:
        lo = (f"last on the list {dfmt(r['last_on'], True)}" if r.get("last_on")
              else f"never on the list since it began ({dfmt(LIST_LAUNCH, True)})")
        line = r.get("in_line")
        wait = (f"It is {ordinal(line)} in line: it enters as soon as it ranks {ENTER}th or better, or when a pick "
                f"ranks below {EXIT_RANK} and it is then the best-ranked name off the list" if line
                else "Off the list")
        held = (f" It ranks inside the top {TOP_N} but outside the top {ENTER}, so it waits while every pick still "
                f"ranks {EXIT_RANK} or better (the band keeps names already on the list)." if r["rank"] <= TOP_N
                else "")
        blocks.append(f'<div class="ptb"><h4>Status</h4><p>Rank {r["rank"]}, {lo}. {wait}.{held}</p></div>')
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
        recs = io_.get("records") or {}
        spy_ok = io_.get("record_spy_ok", True)

        seen = set()

        def own(d):
            import insider_record as ir
            c = str(d.get("owner_cik") or "")
            r = recs.get(c)
            if r is None:
                return "n/a"
            if c in seen:                          # one record per insider: said once, on the first line
                return '<span class="tn">as above</span>'
            seen.add(c)
            tip = (f"purchases {r['k_buy']} of {r['n_buy']}, sales {r['k_sell']} of {r['n_sell']}" if r.get("show") else "")
            return f'<span title="{e(tip)}">{e(ir.record_txt(r, spy_ok))}</span>'
        dl = "".join(f'<tr><td>{dfmt(d["tx_date"], True)}</td><td>{e(d["name"] or "")}</td><td>{e(d["role"])}</td>'
                     f'<td>{d["side"]} ({"P" if d["side"] == "buy" else "S"}){" non-market" if d["nonmarket"] else ""}'
                     f'{" &middot; 10b5-1" if d["plan"] else ""}</td>'
                     f'<td class="num">{money(d["value"])}</td><td class="own">{own(d)}</td><td><a href="{e(d["url"])}">Form 4</a></td></tr>'
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
        cov = e(dfmt(io_.get("cache_from"), True)) if io_.get("cache_from") else ""
        own_note = (f"""<p class="tn">Own record = how this insider's own past trades in this stock were followed by the
stock: a purchase counts as right when the stock then beat SPY over the next {ir_h()} trading days, a sale when it
then lagged SPY (price only, from the close of the trade day). Counted: purchases (code P) and sales (code S =
sale, open market or private), one per insider, day and side, only once their {ir_h()}-day window has closed;
10b5-1 plan trades are not counted (they are scheduled months ahead), only their number is shown. Trades close
together share most of their window, so the cell first gives the number of independent (non-overlapping)
windows, and shows k of n only from {ir_min_indep()} independent windows; otherwise it says too few independent
trades. Small sample and descriptive{', from the Form 4s filed since ' + cov if cov else ''} held here: not a
forecast, and not part of the composite.</p>""" if dl else "")
        blocks.append(f"""<div class="ptb wide"><h4>Insiders (SEC Form 4)</h4><ul class="ptul">{''.join(wl)}</ul>
{('<p class="tn">' + cap + ':</p><table class="ptmini"><tr><th>Traded</th><th>Insider (as filed)</th><th>Role</th><th>Side</th><th>Value</th><th>Own record</th><th></th></tr>' + dl + '</table>') if dl else ''}
<p class="tn">Code P = open-market or private purchase (lines whose footnotes show a non-market purchase are
excluded from the counts and marked in the table); code S = sale, open market or private. By transaction date
inside the window. The 10b5-1 mark comes from the filing's own Rule 10b5-1 box, or a footnote that says the trade was
made under such a plan. {src}</p>{own_note}</div>""")
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
            bb = (f'<br><span class="tn" title="ranks outside the top {TOP_N}; kept by the band (stay while rank '
                  f'&le; {EXIT_RANK})">kept by the band</span>' if r.get("by_band") else "")
            if r.get("at_change"):
                since += ('<br><span class="tn" title="entered at a method change, not ordinary turnover">'
                          'method change</span>')
            rk = (f'{r["rank"]}<br><span class="tn">entry {r["entry_rank"]}</span><br>'
                  f'<span class="tn {cls(mg) if (mg == mg and abs(mg) >= 0.005) else ""}">{margin_txt(mg, True)}</span>'
                  f'{bb}')
            exc = _exit_cell(r.get("exit"))
        else:
            since = (f'off list<br><span class="tn">last on {dfmt(r["last_on"])}</span>' if r.get("last_on")
                     else 'off list<br><span class="tn">never on the list</span>')
            ret, exc = dash, dash
            rk = f'{r["rank"]}<br><span class="tn">{margin_txt(None, False, r.get("in_line"))}</span>'
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
    lm = meta.get("list") or {}
    mi = meta.get("method") or {}
    if lm.get("rule") == RULE_FALLBACK:
        why = safe_text(lm.get("why") or "no usable previous list")
        rule_note = (f' <b>Today the band could not be applied</b> ({e(why)}), so the list is the plain '
                     f'top {TOP_N}.')
    else:
        kept = lm.get("kept_by_band") or []
        rule_note = (f' Today {plural(len(kept), "pick")} rank{"s" if len(kept) == 1 else ""} outside the top {TOP_N} and '
                     f'{"stays" if len(kept) == 1 else "stay"} on the list by the band ({e(", ".join(kept))}).' if kept else "")
        forced, disp = lm.get("forced") or [], lm.get("displaced") or []
        if forced:
            rule_note += (f' Today {e(", ".join(forced))} entered by ranking {ENTER}th or better'
                          + (f', in place of {e(", ".join(disp))}.' if disp else "."))
    bs = meta.get("band_since") or mi.get("band_since")
    fb = mi.get("band_fallbacks") or []
    if bs:
        band_txt = (f"since the {dfmt(bs, True)} ranking a two-sided band applies at the cut: a pick stays while it "
                    f"ranks {EXIT_RANK}th or better, a name off the list enters as soon as it ranks {ENTER}th or better "
                    f"(the worst-ranked pick makes room), and any other free place goes to the best-ranked name off "
                    f"the list"
                    + (f" (on {plural(len(fb), 'later ranking')} the band could not be applied and the plain top "
                       f"{TOP_N} was published: {', '.join(dfmt(d, True) for d in fb[:5])}"
                       f"{', ...' if len(fb) > 5 else ''})" if fb else "")
                    + f"; before that it was the plain top {TOP_N}")
    else:
        band_txt = (f"so far every ranking used the plain top {TOP_N}; a two-sided band (stay while rank &le; "
                    f"{EXIT_RANK}, enter at rank &le; {ENTER}) applies from the next recorded ranking")
    chg_txt = method_change_txt(mi)
    chg_txt = f" {e(chg_txt)}" if chg_txt else ""
    n_chg_left = sum(len(c.get("left") or []) for c in (mi.get("changes") or {}).values())
    return f"""<section class="block" id="tracker">
<h2>Pick Tracker</h2>
<p class="note">Follows every pick from the day it entered the list: how long it has been on it, how it has done
since (against SPY and the equal-weight universe over the same dates), how far it sits above its exit line, how
long names in its rank band have tended to stay, and the analyst, earnings, insider and congressional context.
The list is {TOP_N} names: {band_txt}.{rule_note}{chg_txt} Open a row
(+) for the detail. Built daily from the page's own history ({len(meta['dates'])} daily rankings since the list began
on {dfmt(LIST_LAUNCH, True)}, each dated by the session whose closes it holds; the latest is the
{dfmt(meta['dates'][-1], True)} close).{rec_note} <b>The overlays are context only: they do not change the composite
or the ranks</b>; whether any of them should enter the model is a separate decision. Not advice.</p>
<div class="ptpills" role="group" aria-label="rows">
  <button class="pill on" type="button" data-f="pick">Picks ({n_on})</button>
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
a peak since entry, on daily closing prices. Rank: today, at entry, and the pick's composite margin over the
rank-{EXIT_RANK + 1} composite, the name it must stay ahead of (names off the list are published at 2 dp, so a gap under
0.01 is a tie there and only the rank decides); a name off the list shows its place in line for the next free place.
Exit estimate = median trading days until the name first ranks below {EXIT_RANK}, from a rank-band Markov chain over
{exit_res.get('n_transitions', 0)} day-to-day moves of every name ranked {EXIT_RANK} or better (the move into a method-change
ranking is left out; displacement of a pick ranked {TOP_N + 1}-{EXIT_RANK} is not modelled); range = the model's 10th
to 90th percentile of that time (8 in 10 names in the band leave inside it); then the chance of leaving within 20
trading days, next to how often a name in the band ranked below {EXIT_RANK} within 20 trading days in the history.{frozen_moves_txt(exit_res)}
Of {sp.get('n', 0)} spells so far, {sp.get('completed', 0)} ended, after a median of {sp.get('median_td') or 0:.0f}
trading days (middle half {sp.get('q1') or 0:.0f}–{sp.get('q3') or 0:.0f}); {sp.get('le5', 0)} of them lasted 5
days or less, mostly names hovering at the old cut (before the band){f"; {n_chg_left} ended at a method change, not by ordinary turnover" if n_chg_left else ""}.
Analyst target = Yahoo Finance consensus mean, upside from today's
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


def frozen_txt(mi):
    """The frozen-input disclosure in HISTORY terms (wave 14, C2): which stored rankings used the macro inputs
    frozen at May 2026 data, dated from the history (picks_history macro_through), and since when they refresh."""
    mi = mi or {}
    a, b, since = mi.get("frozen_from"), mi.get("frozen_to"), mi.get("macro_since")
    cad = dfmt(FROZEN_CAD_END, True)
    if not a:
        return ""
    if since:
        und = mi.get("undated_after") or 0
        return (f" rankings from {dfmt(a, True)} to {dfmt(b, True)} used macro inputs (betas, P/E, the FOMC target) "
                f"frozen at {FROZEN_DATA} data (the USD/CAD betas ended {cad}), which kept ranks sticky and tenure "
                f"long, so the tenure, persistence and follow-the-list figures above mostly reflect that period; "
                f"since the {dfmt(since, True)} ranking the inputs are rebuilt weekly"
                + (f" ({plural(und, 'later ranking')} carried no dated inputs)" if und else "") + ";")
    return (f" every ranking so far ({dfmt(a, True)} to {dfmt(b, True)}) used macro inputs (betas, P/E, the FOMC "
            f"target) frozen at {FROZEN_DATA} data (the USD/CAD betas ended {cad}), which keeps ranks sticky and "
            f"tenure long" + ("; refreshed inputs apply from the next recorded ranking" if mi.get("today_refreshed")
                              else "") + ";")


def _frozen_share(ex):
    """(moves on frozen inputs, all fitted moves, quantifier or None) from exit_model()'s counts (round 3)."""
    n, k = int((ex or {}).get("n_transitions") or 0), int((ex or {}).get("n_frozen") or 0)
    if not n or not k:
        return k, n, None
    q = "All" if k == n else "Nearly all" if k >= 0.9 * n else "Most" if 2 * k > n else None
    return k, n, q


def frozen_moves_txt(ex):
    """Exit-estimate footnote (round 3, L4): how many of the model's moves come from the frozen-input period, from
    the history's macro_through dates; the "likely overstates" inference only while they are the majority."""
    k, n, q = _frozen_share(ex)
    if not k:
        return ""
    if q is None:
        return f" {k} of those {n} moves come from rankings on the macro inputs frozen at {FROZEN_DATA} data."
    cnt = "" if q == "All" else f" ({k} of {n})"
    return (f" {q} of those moves{cnt} come from rankings on the macro inputs frozen at {FROZEN_DATA} data, which "
            f"kept ranks sticky, so for now the estimate likely overstates how long a name stays.")


def ai_method_tail(mi, ex=None):
    """Appended to stocks.ai.txt line 3 (round 3, L0): the band's start and the macro-input change, dated from the
    stored history (band_since, macro_through) exactly as the page dates them; true on the first live build, later
    builds, fallback days and an unrecorded build. Never says "rule=" (parse_ai reads the first one). Never
    raises: "" (nothing claimed) when anything is missing."""
    try:
        mi = mi or {}
        out = []
        bs, ms = mi.get("band_since"), mi.get("macro_since")
        if bs:
            out.append(f"{RULE_BAND} since {bs}")   # r4: names the band, so a fallback day cannot misread it
        chg = sorted((mi.get("changes") or {}).keys())
        cw = (f"entries/exits on {' and '.join(chg)} are {'a method change' if len(chg) == 1 else 'method changes'}"
              if chg else "")
        if ms and mi.get("today_refreshed"):
            out.append(f"macro inputs rebuilt weekly since {ms} (frozen at {FROZEN_DATA} data before"
                       + (f"; {cw}" if cw else "") + ")")
        elif ms:
            out.append(f"macro inputs refreshed from {ms} (frozen at {FROZEN_DATA} data before"
                       + (f"; {cw}" if cw else "") + "); today's inputs carry no data-through date")
        elif mi.get("frozen_from"):
            out.append(f"every stored ranking used macro inputs frozen at {FROZEN_DATA} data"
                       + ("; today's ranking (not recorded) uses refreshed inputs" if mi.get("today_refreshed")
                          else ""))
            if cw:
                out.append(cw)
        k, n, q = _frozen_share(ex)
        if q:
            out.append(f"exit_median_td: {q.lower()} model moves ({k} of {n}) on frozen inputs, likely overstates stays")
        return "".join("; " + x for x in out)
    except Exception:                                                   # noqa: BLE001
        return ""


def record_section(tr, chart_html="", macro=None):
    """tr["method"] = method_info() (the frozen-input period and the method changes, from the history itself).
    macro = today's _macro_inputs() (only whether today's inputs are refreshed is used)."""
    ps = tr["persistence"]
    bs = tr["basket_summary"]
    coh = tr["cohort"]

    def get(h, b):
        x = ps[(ps.h == h) & (ps.bucket == b)] if len(ps) else ps
        return x.iloc[0].to_dict() if len(x) else None
    long10 = _ans(get(10, "60+ td"), 10, "picks already on the list 60 trading days or more")
    all10 = _ans(get(10, "top20"), 10, "all picks together")
    rows = ""
    labels = {"0-19 td": "On list 0-19 td", "20-59 td": "On list 20-59 td", "60+ td": "On list 60+ td",
              "top20": "All picks", "rank21_40": "Off the list"}
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
    mi = dict(tr.get("method") or {})
    if macro is not None:
        mi["today_refreshed"] = macro.get("basis") == "data through"
    mtxt = frozen_txt(mi)
    chg = method_change_txt(mi, short=True)
    part = (f" {bs['n_partial']} partial ranking{'s' if bs['n_partial'] != 1 else ''} (fewer names than the "
            f"universe) {'are' if bs['n_partial'] != 1 else 'is'} not used to form baskets or move tenure."
            if bs.get("n_partial") else "")
    since = mi.get("band_since") or tr.get("band_since")
    fb = mi.get("band_fallbacks") or []
    rule_txt = ((f" The list is the plain top {TOP_N} before the {dfmt(since, True)} ranking and follows the two-sided"
                 f" band from that ranking on"
                 + (f", except {plural(len(fb), 'ranking')} on which the band could not be applied and the plain top"
                    f" {TOP_N} was published" if fb else "") + ".")
                if since else f" Every ranking so far used the plain top {TOP_N}; the two-sided band applies from the "
                              f"next recorded ranking.")
    if chg:
        rule_txt += f" {e(chg)}"
    return f"""<section class="block" id="track-record">
<h2>Track Record: will they keep doing well?</h2>
<p class="note">Several picks have been on the list for months, and some did very well. This section asks what the
page's own history says about what tends to come next. {long10} {all10}{coh_txt} The history is short
({n_rank} daily rankings, {dfmt(bs['from'], True)} to {dfmt(bs['to'], True)}); none of this is a forecast or advice.</p>
<div class="tile chart"><div class="ch">{chart_html}</div></div>
<p class="note" style="font-size:12.5px">Follow-the-list basket (equal-weight, the {TOP_N} published picks, re-formed at
every daily ranking, price only): picks {pct(bs['top20'])}, equal-weight universe rebalanced at each ranking
{pct(bs['ew'])}, the names off the list {pct(bs['rest'])}{spy_txt}. The picks beat the universe in {bs['beats']} of
{bs['n']} day-to-day intervals.{rule_txt} Each basket is formed at the close of the day it was ranked, and the ranking
is published only after that close, so these are not returns anyone could have traded at those prices.{drop_txt}{part}
The rebalanced universe differs from the buy-and-hold universe used in the rows above and in the cohort sentence.</p>
{replay_html(tr)}
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


def replay_html(tr):
    """The in-sample replay of both list rules on the same rankings, with its labels (wave 14)."""
    rp = tr.get("replay") or {}
    rr = rp.get("rules") or {}
    pl, one, two = rr.get("plain"), rr.get("one_sided"), rr.get("two_sided")
    if not pl or not one or not two or not rp.get("n_rankings"):
        return ""
    mi = tr.get("method") or {}
    frz = ""                                       # round 3 (L4): no comparison with the refreshed inputs
    if mi.get("macro_since") and mi.get("frozen_to"):
        frz = (f" The rankings up to {dfmt(mi['frozen_to'], True)} used macro inputs frozen at {FROZEN_DATA} data, "
               f"which kept ranks sticky.")
    elif not mi.get("macro_since") and mi.get("frozen_from"):
        frz = f" Every ranking in this replay used macro inputs frozen at {FROZEN_DATA} data, which kept ranks sticky."

    def cells(x):
        return (f'<td class="num">{x["entries"]}</td><td class="num">{x["changed_days"]}</td>'
                f'<td class="num">{x["names"]}</td><td class="num">{x["completed"]} of {x["spells"]}</td>'
                f'<td class="num">{x["le5"]}</td><td class="num">{x["kept10"]}</td><td class="num">{x["kept15"]}</td>'
                f'<td class="num">{pct(x["basket"])}</td>')
    return f"""<h3>Three list rules on the same rankings (in-sample replay)</h3>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable ptrec"><thead><tr><th>Rule</th><th>Names entering</th><th>Rankings with a change</th>
<th>Distinct names</th><th>Spells ended</th><th>Spells of 5 td or less</th><th>Rankings with a top-10 name kept off</th>
<th>Rankings with a top-15 name kept off</th><th>Basket (in-sample)</th></tr></thead><tbody>
<tr><td>Plain top {TOP_N}</td>{cells(pl)}</tr>
<tr><td>One-sided band: stay while rank &le; {EXIT_RANK} (rejected)</td>{cells(one)}</tr>
<tr><td>Two-sided band: stay while rank &le; {EXIT_RANK}, enter at rank &le; {ENTER} (published)</td>{cells(two)}</tr>
</tbody></table></div>
<p class="note" style="font-size:11.5px;margin-top:.9rem">The three rules replayed on the same {rp['n_rankings']} full
rankings ({dfmt(rp['from'], True)} to {dfmt(rp['to'], True)}; the composites and ranks are identical, only membership
differs; each band starts from the first day's top {TOP_N}). The one-sided band keeps the list almost still, but it also
keeps well-ranked names off the list for long stretches (the two kept-off columns), so it was rejected. The two-sided
band lets any name ranked {ENTER}th or better in at once (the worst-ranked pick makes room;
{plural(two['displaced'], 'such displacement')} in this replay). {ENTER} and {EXIT_RANK} were chosen on the ranks-only
columns of this replay as it stood on 4 Nov 2026 (84 rankings, 04 Jun to 03 Nov 2026), never on returns. Basket = follow-the-list, equal-weight, price only, formed
at each ranking's close (not tradeable at those prices); the equal-weight universe rebalanced the same way returned
{pct(pl['ew'])}. <b>The basket column is in-sample and is not evidence</b> that any rule earns more.{frz}</p>"""


def record_figure(tr):
    import plotly.graph_objects as go
    bk = tr["basket"]
    if bk is None or bk.empty:
        return None
    x = [bk["from"].iloc[0]] + bk["to"].tolist()
    fig = go.Figure()
    series = [("cum_top20", "Picks (follow the list)", "#0a2540", 2.2),
              ("cum_ew", "Equal-weight universe (rebalanced)", "#9aa5b1", 1.6),
              ("cum_rest", "Off the list", "#5b7c99", 1.4)]
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
table.ptmini td.own{white-space:normal;min-width:11em;max-width:19em;font-size:11px}
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


def methodology_html(band_since=None, mi=None):
    mi = mi or {}
    fb = mi.get("band_fallbacks") or []
    since = ((f"Before the {dfmt(band_since, True)} ranking it was the plain top 20 by composite. From that ranking on"
              + (f" (except {plural(len(fb), 'ranking')} on which the band could not be applied)" if fb else "") + ",")
             if band_since else "So far it has been the plain top 20 by composite. From the next recorded ranking on,")
    ms = mi.get("macro_since")
    head = (f"Rankings before the {dfmt(ms, True)} ranking used files frozen at {FROZEN_DATA} data (the USD/CAD betas "
            f"ended {dfmt(FROZEN_CAD_END, True)})" if ms else
            f"Every ranking so far used files frozen at {FROZEN_DATA} data (the USD/CAD betas ended "
            f"{dfmt(FROZEN_CAD_END, True)})")
    # round 3 (L5): "rebuilt every Sunday" and the sources only while today's files carry the rebuild's sidecar
    # (mi["today_refreshed"]); restored old files or a missing sidecar get wording that stays true
    if mi.get("today_refreshed"):
        how = ((f"; from that ranking on" if ms else "; from the next recorded ranking on")
               + " they are rebuilt every Sunday from Yahoo prices (stocks, the dollar index, USD/CAD) and FRED (the "
                 "10-year yield; fed funds for the decision labels), and the line under the page title gives the date "
                 "of their prices and of their regressions.")
    elif ms:
        how = ("; from that ranking on, the rankings recorded with a data-through date used files rebuilt by the "
               "site's weekly script. Today's files carry no build record, so the line under the page title gives "
               "only their file date.")
    else:
        how = "; the line under the page title gives their file date."
    macro_p = (f"""<p><b>Macro inputs.</b> The composite's macro variables (betas to the 10-year yield, the dollar index
and USD/CAD; P/E; the post-FOMC 5-day drift that sets the weights) come from two private files.
{head}{how} The {dfmt(ms, True) if ms else 'first'} ranking on the rebuilt inputs is marked as a method
change: names that entered or left there did so at the change, not as ordinary turnover, and the day-to-day move
into it is left out of the exit model.{" FOMC meetings before a stock's first trading day are not counted." if mi.get("pre_listing") == "dropped" else ""}</p>""")
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
<p><b>List membership.</b> The published list is always 20 names. """ + since + """ a two-sided band applies at the cut: a name already on the list stays while it ranks 25th or
better; a name off the list enters as soon as it ranks 15th or better, and the worst-ranked pick makes room (only a
pick ranked 21-25 can be displaced); any other free place goes to the best-ranked name off the list. The previous list
is the one stored for the last recorded session before the build's own; if there is none, or it does not hold 20
names, the build falls back to the plain top 20 and the page says so. The band changes only which names carry the
star: the composite, the ranks and the weights are the same. 15 and 25 were chosen on a ranks-only replay of the
84 stored rankings from 04 Jun to 03 Nov 2026 (turnover and how often a well-ranked name was kept off), never on
returns; the Track Record shows that replay, extended to every ranking since. <code>data/picks_history.csv</code> keeps the raw rank, the top-20 flag and, separately, the published
membership, the rule that built it and the date of the macro inputs.</p>
""" + macro_p + """<p><b>Exit estimate.</b> A pick leaves the list when its rank falls below 25, or, if it ranks 21-25, when a name off
the list ranks 15th or better and displaces it. The estimate is empirical and models only the rank exit: a Markov
chain over rank bands fitted to all day-to-day moves between full rankings of every name ranked 25 or better
(ranks do not depend on membership), so for a pick ranked 21-25 it can overstate the stay. The page shows the
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
backfilled over several days and says so until complete. Exxon Mobil's insiders are read from both of its SEC
registrants (the holding company that has carried the XOM listing since 1 Jul 2026, and the former company, whose
filing list is re-read monthly). Each insider in the detail table gets an own record: how that person's own past
trades in the stock (purchases, code P; sales, code S, open market or private) were followed by the stock over the
next 60 trading days against SPY (price only, from the trade day's close; a purchase is right when the stock beat
SPY, a sale when it lagged). 10b5-1 plan trades are not counted, only trades whose 60-day window has closed count,
and the number of independent (non-overlapping) windows comes first: the result is shown as "k of n" only from 3
independent windows, otherwise as too few independent trades. The horizon was fixed before any result was seen. It
is descriptive and small-sample (only the Form 4s the site holds count; the insider detail says from when), not a
forecast. Congress trades come from the site's weekly STOCK Act
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
