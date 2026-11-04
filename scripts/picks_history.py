"""picks_history -- the day-by-day record of the Stock Research composite ranking (wave 13, 2026-11-04).

data/picks_history.csv has one row per (snapshot_date, ticker): the page's own ranking of the research
universe on each build day. It is PUBLIC by design, because every value in it was already published on
docs/stocks.html / docs/stocks.ai.txt. Composites are stored at the precision the page published them
(3 dp for the top 20, as in stocks.ai.txt; 2 dp for ranks 21-40, as on the page since 2026-09-24), so the
file discloses nothing more about the confidential picker weights than the pages already do. Weights are
never read or written here.

snapshot_date = the NYSE SESSION WHOSE CLOSES THE ROW HOLDS (wave-13 fix round), not the build's calendar
day. A build after 16:10 ET on a trading day holds that day's closes; a build before the 09:30 ET open (after
midnight, a catch-up at logon) or on a weekend / holiday holds the PREVIOUS session's closes; a build during
the session (09:30-16:10 ET) holds intraday quotes and is never recorded (it would not line up with SPY's
close). price_session() is the one rule, used by the daily append and by the backfill alike.

Writers
  backfill  once (or whenever the CSV is missing): every committed snapshot of docs/stocks.html and
            docs/stocks.ai.txt, read with read-only `git log` / `git show` (no checkout, no network). Each
            commit is dated by price_session(build time), build time = the commit time (or the end of the
            page's own "As of" day when the commit came later). Per session: a full-table commit beats an
            ai.txt-only one; a commit built on the session's own CDMX day beats a later pre-open one; then
            the LAST commit wins. Intraday commits are skipped. So a pre-open build is used only for a
            session that has no same-day build (2026-06-09 is recovered from 6189e6d this way), and a
            holiday build (07-03, 09-07: the prior day's prices again) never adds a zero-return day.
  append    every build that passes the picker's publish floor: a build on the session's own day REPLACES
            that session's rows (idempotent, never duplicated); a later pre-open build fills the session
            only when it has no rows; an intraday build records nothing. A day the picker could not rebuild
            the page adds nothing: that day is a gap, never a carried-forward row.

Facts derived here (no forecasting): spells on the top 20, tenure in NYSE trading days and calendar
days, entry prices, split handling. Prices are the page's own Yahoo prices at build time (price return,
no dividends). Splits are applied ONLY when Yahoo confirms them (defaultKeyStatistics.lastSplitFactor /
lastSplitDate, recorded in data/picks_splits.json by the build). A split-like jump is a "price break" (any
return window spanning it is n/a, never guessed) only while Yahoo gives no split information that rules a
split out: when today's Yahoo lastSplitDate is EARLIER than the jump (and Yahoo was asked >= 5 trading days
after it), the jump is a real price move and returns across it are shown.
A partial snapshot (fewer names than the usual universe, e.g. 2026-08-26 with 38) keeps its prices but its
ranks are over a different set, so its top-20 flags are treated as unobserved (no spell change, no exit-model
move, no basket formed on it).

  python scripts/picks_history.py --backfill [--repo PATH] [--out PATH] [--force]
  python scripts/picks_history.py --summary
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import html as htmllib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

try:
    from paths import ROOT, DATA
except ImportError:                                   # imported from a test with scripts/ on sys.path
    ROOT = Path(__file__).resolve().parent.parent
    DATA = ROOT / "data"

HIST = DATA / "picks_history.csv"
SPLITS = DATA / "picks_splits.json"
TOP_N = 20
COLS = ["snapshot_date", "rank", "ticker", "sector", "price_usd", "composite", "composite_dp",
        "is_top20", "universe_n", "source", "built_at"]
PAGE_PATHS = ("docs/stocks.html", "docs/stocks.ai.txt")
GIT_READ_ONLY = {"log", "show", "rev-parse"}          # the only git subcommands this module may run
# The composite picker and its top-20 list first appeared on 2026-06-04 (commit 8431783 created picker.py;
# the stocks.html before it has no picks table). Tenure counted from this date is exact, not a lower bound.
LIST_LAUNCH = "2026-06-04"
NY = ZoneInfo("America/New_York")
MX = ZoneInfo("America/Mexico_City")
OPEN_ET, CLOSE_DONE_ET = (9, 30), (16, 10)            # after 16:10 ET the regular-session close has printed

# NYSE full-day closures by the exchange's rules (Rule 7.2): New Year's Day, MLK Day, Presidents' Day, Good
# Friday, Memorial Day, Juneteenth (since 2022), Independence Day, Labor Day, Thanksgiving, Christmas; a
# Saturday holiday moves to Friday, a Sunday one to Monday, and New Year's Day on a Saturday is not observed.
# Computed for any year (no list to extend). Unscheduled closures (e.g. a national day of mourning) are not
# predictable: add them to SPECIAL_CLOSURES when they happen. NYSE_HOLIDAYS_CHECKED is the exchange's own
# published 2026-2027 list; tests/test_picks_history.py checks the rules reproduce it.
SPECIAL_CLOSURES: set = set()
NYSE_HOLIDAYS_CHECKED = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05",
    "2027-09-06", "2027-11-25", "2027-12-24",
}


def _easter(y):
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, (b, c) = y % 19, divmod(y, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return dt.date(y, month, day + 1)


def _nth_weekday(y, month, weekday, n):
    """n-th (1-based) `weekday` (Mon=0) of the month; n = -1 is the last one."""
    if n > 0:
        d = dt.date(y, month, 1)
        return d + dt.timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
    d = (dt.date(y, month + 1, 1) if month < 12 else dt.date(y + 1, 1, 1)) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d):
    return d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d


@functools.lru_cache(maxsize=None)
def nyse_holidays(y):
    out = {_nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3), _easter(y) - dt.timedelta(days=2),
           _nth_weekday(y, 5, 0, -1), _observed(dt.date(y, 7, 4)), _nth_weekday(y, 9, 0, 1),
           _nth_weekday(y, 11, 3, 4), _observed(dt.date(y, 12, 25))}
    if dt.date(y, 1, 1).weekday() != 5:                # a Saturday New Year's Day is not observed
        out.add(_observed(dt.date(y, 1, 1)))
    if y >= 2022:
        out.add(_observed(dt.date(y, 6, 19)))
    return frozenset(x.isoformat() for x in out) | frozenset(s for s in SPECIAL_CLOSURES if s[:4] == str(y))

# the html drops " Services" from the sector label (25_stock_picks: sec.replace(" Services", ""))
SECTOR_RESTORE = {"Communication": "Communication Services", "Financial": "Financial Services"}
RE_ASOF_HTML = re.compile(r'class="asof">\s*As of\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})'
                          r'(?:\s*(?:&middot;|·)\s*(\d+)\s+names)?')
RE_ASOF_AI = re.compile(r'^asof=([^;]+);\s*universe=(\d+)(.*)$', re.M)
RE_TABLE = re.compile(r'<table class="ptable picks">(.*?)</table>', re.S)
RE_ROW = re.compile(r'<tr data-status="(\w+)" data-pick="([01])">(.*?)</tr>', re.S)
RE_TD = re.compile(r'<td[^>]*>(.*?)</td>', re.S)
RE_TAG = re.compile(r'<[^>]+>')


# ------------------------------------------------------------------------------------------- git
def _git(repo, *args):
    """Read-only git against `repo` only: never discovers a parent repository, never takes the index lock."""
    if not args or args[0] not in GIT_READ_ONLY:
        raise ValueError(f"picks_history: git {args[:1]} refused (read-only: {sorted(GIT_READ_ONLY)})")
    repo = Path(repo).resolve()
    if not (repo / ".git").exists():
        return None
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(repo.parent), GIT_OPTIONAL_LOCKS="0")
    r = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args], capture_output=True, env=env)
    return r.stdout if r.returncode == 0 else None


def is_git_repo(repo):
    return (Path(repo) / ".git").exists() and _git(repo, "rev-parse", "--git-dir") is not None


# ------------------------------------------------------------------------------------------- parse
def _text(fragment):
    return htmllib.unescape(RE_TAG.sub("", fragment)).strip()


def _num(s):
    s = str(s).replace("$", "").replace(",", "").replace("−", "-").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _dp(s):
    s = str(s).strip().replace("+", "").replace("-", "")
    return len(s.split(".")[1]) if "." in s else 0


def _date(s):
    try:
        return dt.datetime.strptime(" ".join(str(s).split()), "%d %b %Y").date().isoformat()
    except ValueError:
        return None


def parse_html(doc):
    res = {"asof": None, "header_n": None, "rows": []}
    if not doc:
        return res
    m = RE_ASOF_HTML.search(doc)
    if m:
        res["asof"] = _date(m.group(1))
        res["header_n"] = int(m.group(2)) if m.group(2) else None
    t = RE_TABLE.search(doc)
    if not t:
        return res
    for status, pick, body in RE_ROW.findall(t.group(1)):
        tds = RE_TD.findall(body)
        if len(tds) < 5:
            continue
        tick_m = re.search(r'<b>([^<]+)</b>', tds[1])
        comp_raw = _text(tds[4])
        sector = _text(tds[2])
        res["rows"].append({
            "rank": int(_text(tds[0])),
            "ticker": htmllib.unescape(tick_m.group(1)).strip() if tick_m else None,
            "star": "pick-star" in tds[1], "sector": SECTOR_RESTORE.get(sector, sector),
            "price_usd": _num(_text(tds[3])), "composite": _num(comp_raw), "composite_dp": _dp(comp_raw)})
    return res


def parse_ai(doc):
    """stocks.ai.txt -> asof + top-20 rows. Lines carry rank|ticker|sector|price|composite|dominant_var and,
    since wave 13, extra columns appended at the END (ignored here)."""
    res = {"asof": None, "universe": None, "rows": []}
    if not doc:
        return res
    m = RE_ASOF_AI.search(doc)
    if m:
        res["asof"] = _date(m.group(1))
        res["universe"] = int(m.group(2))
    for line in doc.splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 5 and parts[0].isdigit():
            res["rows"].append({"rank": int(parts[0]), "ticker": parts[1].strip(), "sector": parts[2].strip(),
                                "price_usd": _num(parts[3]), "composite": _num(parts[4]),
                                "composite_dp": _dp(parts[4])})
    return res


def _commit_rows(repo, sha, commit_iso):
    """One commit -> (snapshot_date, rows, full_table)."""
    def show(path):
        b = _git(repo, "show", f"{sha}:{path}")
        return None if b is None else b.decode("utf-8", errors="replace")
    h, a = parse_html(show(PAGE_PATHS[0])), parse_ai(show(PAGE_PATHS[1]))
    snap = h["asof"] or a["asof"] or commit_iso[:10]
    ai_by = {r["ticker"]: r for r in a["rows"]} if a["asof"] == snap else {}
    out = []
    if h["rows"]:
        n = len(h["rows"])
        for r in h["rows"]:
            row = {"rank": r["rank"], "ticker": r["ticker"], "sector": r["sector"], "price_usd": r["price_usd"],
                   "composite": r["composite"], "composite_dp": r["composite_dp"], "is_top20": bool(r["star"]),
                   "universe_n": n}
            ar = ai_by.get(r["ticker"])
            if ar is not None and ar["composite"] is not None and ar["composite_dp"] > row["composite_dp"]:
                row["composite"], row["composite_dp"] = ar["composite"], ar["composite_dp"]
            if ar is not None and ar["sector"]:
                row["sector"] = ar["sector"]
            out.append(row)
    elif a["rows"]:                                   # html overwritten by another page: top 20 only
        for r in a["rows"]:
            out.append({"rank": r["rank"], "ticker": r["ticker"], "sector": r["sector"],
                        "price_usd": r["price_usd"], "composite": r["composite"],
                        "composite_dp": r["composite_dp"], "is_top20": r["rank"] <= TOP_N,
                        "universe_n": a["universe"]})
    return snap, out, bool(h["rows"])


def build_time_of_commit(commit_iso, page_asof=None):
    """Best estimate of when a committed page was BUILT: the commit time, unless the commit came after the
    end of the page's own "As of" day (CDMX), in which case the build happened on that day (latest moment)."""
    t = pd.Timestamp(commit_iso)
    if page_asof:
        end = pd.Timestamp(f"{page_asof} 23:59:59").tz_localize(MX)
        if t > end:
            t = end
    return t.to_pydatetime()


def backfill_from_git(repo, since=None, report=None):
    """Every committed snapshot -> DataFrame[COLS], dated by price_session(). Read-only; returns an empty frame
    when `repo` is not a git checkout (e.g. a staging copy). `report` (a dict) receives what was skipped."""
    out = _git(repo, "log", "--format=%H|%cI", "--", *PAGE_PATHS)
    if out is None:
        return pd.DataFrame(columns=COLS)
    commits = []
    for line in out.decode("utf-8").splitlines():
        if line.strip():
            sha, ci = line.split("|")
            commits.append((sha, ci))
    best, skipped = {}, {"intraday": [], "no_rows": 0}  # session -> ((full, tier, time, sha), rows, ci)
    for sha, ci in commits:
        hdr, rows, full = _commit_rows(repo, sha, ci)
        if not rows:
            skipped["no_rows"] += 1
            continue
        sess, basis, tier = price_session(build_time_of_commit(ci, hdr))
        if basis != "close":
            skipped["intraday"].append(sha[:7])
            continue
        key = (full, tier, pd.Timestamp(ci).tz_convert("UTC"), sha)
        if sess not in best or key > best[sess][0]:
            best[sess] = (key, rows, ci)
    recs = []
    for snap, (key, rows, ci) in best.items():
        if since and snap < since:
            continue
        for r in rows:
            recs.append({**r, "snapshot_date": snap, "source": "git_backfill", "built_at": ci})
    if report is not None:
        report.update(skipped, kept={s: v[0][3][:7] for s, v in sorted(best.items())})
    df = pd.DataFrame(recs, columns=COLS)
    return _normalise(df)


# ------------------------------------------------------------------------------------------- store
def _normalise(df):
    if df.empty:
        return pd.DataFrame(columns=COLS)
    df = df[COLS].copy()
    df["rank"] = df["rank"].astype(int)
    df["composite_dp"] = df["composite_dp"].astype(int)
    df["is_top20"] = df["is_top20"].astype(str).str.lower().isin(["true", "1"])
    df["universe_n"] = pd.to_numeric(df["universe_n"], errors="coerce").astype("Int64")
    df["price_usd"] = pd.to_numeric(df["price_usd"], errors="coerce")
    df["composite"] = pd.to_numeric(df["composite"], errors="coerce")
    df["snapshot_date"] = df["snapshot_date"].astype(str)
    return df.sort_values(["snapshot_date", "rank", "ticker"]).reset_index(drop=True)


def load(path=None):
    path = Path(path or HIST)
    if not path.exists():
        return pd.DataFrame(columns=COLS)
    return _normalise(pd.read_csv(path, dtype={"snapshot_date": str, "ticker": str, "source": str,
                                               "built_at": str, "sector": str}, keep_default_na=False,
                                  na_values=[""]))


def save(df, path=None):
    """Deterministic text (fixed decimals, LF), written atomically."""
    path = Path(path or HIST)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _normalise(df)
    lines = [",".join(COLS)]
    for r in df.itertuples(index=False):
        comp = "" if pd.isna(r.composite) else f"{r.composite:.{int(r.composite_dp)}f}"
        px = "" if pd.isna(r.price_usd) else f"{r.price_usd:.2f}"
        un = "" if pd.isna(r.universe_n) else str(int(r.universe_n))
        sec = str(r.sector or "")
        sec = f'"{sec}"' if "," in sec else sec
        lines.append(",".join([r.snapshot_date, str(int(r.rank)), r.ticker, sec, px, comp,
                               str(int(r.composite_dp)), "True" if r.is_top20 else "False", un,
                               str(r.source or ""), str(r.built_at or "")]))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    return path


def snapshot_from_picker(df, asof_date, built_at=None):
    """Today's picker DataFrame (indexed by ticker, sorted, with rank/sector/price/composite) -> rows in the
    published precision. Never touches weights."""
    built_at = built_at or dt.datetime.now().astimezone().isoformat(timespec="seconds")
    n = len(df)
    recs = []
    for tk, r in df.iterrows():
        rank = int(r["rank"])
        dp = 3 if rank <= TOP_N else 2
        recs.append({"snapshot_date": str(asof_date), "rank": rank, "ticker": str(tk),
                     "sector": str(r.get("sector") or ""), "price_usd": round(float(r["price"]), 2),
                     "composite": round(float(r["composite"]), dp), "composite_dp": dp,
                     "is_top20": rank <= TOP_N, "universe_n": n, "source": "daily_build", "built_at": built_at})
    return _normalise(pd.DataFrame(recs, columns=COLS))


def append_snapshot(hist, snap):
    """Idempotent: rows with the same snapshot_date are replaced, never duplicated."""
    if snap.empty:
        return _normalise(hist)
    dates = set(snap["snapshot_date"])
    keep = hist[~hist["snapshot_date"].isin(dates)] if len(hist) else hist
    return _normalise(pd.concat([keep, snap], ignore_index=True) if len(keep) else snap)


def add_build(hist, df_picker, now=None):
    """Record today's ranking under the session its prices belong to (price_session). -> (hist, info).
    Same-day post-close build: replaces that session (re-runs are idempotent). Later pre-open build: fills
    the session only if it has no rows. Intraday build: records nothing (quotes are not closes)."""
    now = now or dt.datetime.now().astimezone()
    sess, basis, tier = price_session(now)
    info = {"session": sess, "basis": basis, "tier": tier, "recorded": False, "why": ""}
    if basis != "close":
        info["why"] = "intraday build: quotes are not closes, so today's ranking is not recorded"
        return _normalise(hist), info
    have = bool(len(hist)) and bool((hist["snapshot_date"] == sess).any())
    if have and tier < 2:
        info["why"] = (f"pre-open build: the {sess} session already has its own post-close ranking, "
                       f"which is kept")
        return _normalise(hist), info
    snap = snapshot_from_picker(df_picker, sess, built_at=now.isoformat(timespec="seconds"))
    info["recorded"] = True
    return append_snapshot(hist, snap), info


def ensure(path=None, repo=None, log=print):
    """The stored history; backfilled from `repo`'s git history (read-only) when the CSV is missing."""
    path, repo = Path(path or HIST), Path(repo or ROOT)
    if path.exists():
        return load(path)
    if not is_git_repo(repo):
        log(f"picks_history: {path.name} missing and {repo} is not a git checkout: history starts today")
        return pd.DataFrame(columns=COLS)
    df = backfill_from_git(repo)
    log(f"picks_history: backfilled {df['snapshot_date'].nunique()} snapshots ({len(df)} rows) from git")
    save(df, path)
    return df


def record_today(df_picker, now=None, path=None, repo=None, log=print):
    hist, info = add_build(ensure(path, repo, log), df_picker, now)
    if info["recorded"]:
        save(hist, path)
    return hist, info


# ------------------------------------------------------------------------------------------- splits
def _ratio(factor):
    """'3:2' -> 1.5, '4:1' -> 4.0, '1:10' -> 0.1; None if unreadable or 1."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)\s*", str(factor or ""))
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    return a / b if a > 0 and b > 0 and abs(a / b - 1) > 1e-9 else None


def load_splits(path=None):
    try:
        return json.loads(Path(path or SPLITS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_splits(df_picker, today, path=None, first_date=None):
    """Record Yahoo-confirmed splits (picker info lastSplitFactor / lastSplitDate) that fall inside the
    history. Kept across days, so a later split never erases an earlier one. Returns the dict."""
    path = Path(path or SPLITS)
    sp = load_splits(path)
    changed = False
    for tk, r in df_picker.iterrows():
        f, d = r.get("split_factor"), r.get("split_date")
        rt = _ratio(f)
        if rt is None or d is None or (isinstance(d, float) and np.isnan(d)):
            continue
        try:
            day = dt.datetime.fromtimestamp(int(d), dt.timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            continue
        if first_date and day <= first_date:
            continue
        lst = sp.setdefault(str(tk), [])
        if not any(x["date"] == day for x in lst):
            lst.append({"date": day, "factor": str(f), "ratio": rt, "seen": str(today),
                        "source": "Yahoo defaultKeyStatistics lastSplitFactor/lastSplitDate"})
            changed = True
    if changed:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(json.dumps(sp, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    return sp


def last_split_info(df_picker, asof):
    """Today's Yahoo lastSplitFactor / lastSplitDate per ticker (in memory, never stored: it is re-read every
    build, so it is always as of today). -> {ticker: {"date": iso, "factor": str, "asof": asof}}. A ticker
    with no split information from Yahoo today is absent."""
    out = {}
    if "split_date" not in getattr(df_picker, "columns", []):
        return out
    for tk, r in df_picker.iterrows():
        d = r.get("split_date")
        if d is None or (isinstance(d, float) and np.isnan(d)):
            continue
        try:
            day = dt.datetime.fromtimestamp(int(d), dt.timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            continue
        out[str(tk)] = {"date": day, "factor": str(r.get("split_factor") or ""), "asof": str(asof)}
    return out


# ------------------------------------------------------------------------------------------- calendar
def is_trading_day(d):
    d = dt.date.fromisoformat(str(d)[:10])
    return d.weekday() < 5 and d.isoformat() not in nyse_holidays(d.year)


def prev_trading_day(d):
    """The last NYSE trading day strictly before date d."""
    d = dt.date.fromisoformat(str(d)[:10]) - dt.timedelta(days=1)
    while not is_trading_day(d):
        d -= dt.timedelta(days=1)
    return d


def price_session(ts):
    """When a page is built at `ts` (aware datetime), whose closes does it hold? -> (session iso, basis, tier).
    basis "close": the quotes are that session's closes; "intraday": built during the session (not recorded).
    tier 2 = built on the session's own CDMX calendar day (the normal 16:31 build), 1 = a later build (after
    midnight / before the open / weekend), 0 = intraday."""
    if ts.tzinfo is None:
        ts = ts.astimezone()
    t = ts.astimezone(NY)
    d, hm = t.date(), (t.hour, t.minute)
    if is_trading_day(d):
        if hm >= CLOSE_DONE_ET:
            s = d
        elif hm >= OPEN_ET:
            return d.isoformat(), "intraday", 0
        else:
            s = prev_trading_day(d)
    else:
        s = prev_trading_day(d)
    return s.isoformat(), "close", (2 if ts.astimezone(MX).date() == s else 1)


def trading_days(start, end):
    days = pd.bdate_range(start, end).strftime("%Y-%m-%d")
    return [d for d in days if is_trading_day(d)]


def td_between(a, b):
    """Trading days from date a to date b (b after a: positive)."""
    a, b = str(a)[:10], str(b)[:10]
    if b < a:
        return -td_between(b, a)
    return len(trading_days(a, b)) - (1 if is_trading_day(a) else 0)


def td_index_map(dates):
    """NYSE trading-day ordinal of every date (a non-trading day maps to the trading day before it)."""
    dates = sorted(set(str(d) for d in dates))
    if not dates:
        return {}
    tds = trading_days(dates[0], dates[-1])
    pos = {d: i for i, d in enumerate(tds)}
    out, last = {}, 0
    for d in sorted(set(tds) | set(dates)):
        if d in pos:
            last = pos[d]
        out[d] = last
    return {d: out[d] for d in dates}


# ------------------------------------------------------------------------------------------- panel
class Panel:
    """Pivoted history + split-adjusted prices + price breaks. All facts, no forecasts.
    last_split: today's Yahoo split information per ticker (last_split_info()); it decides whether a
    split-like jump is a real move (Yahoo's last split is earlier than the jump) or a break (no information)."""

    MIN_TD_AFTER_JUMP = 5            # Yahoo must have been asked this many trading days after a jump

    def __init__(self, hist, splits=None, last_split=None):
        h = _normalise(hist)
        self.hist = h
        self.dates = sorted(h["snapshot_date"].unique().tolist())
        self.tdi = td_index_map(self.dates)
        self.px = h.pivot(index="snapshot_date", columns="ticker", values="price_usd").sort_index()
        self.rank = h.pivot(index="snapshot_date", columns="ticker", values="rank").sort_index()
        self.comp = h.pivot(index="snapshot_date", columns="ticker", values="composite").sort_index()
        self.top_raw = h.assign(t=h["is_top20"].astype(float)).pivot(
            index="snapshot_date", columns="ticker", values="t").sort_index()
        # partial snapshots (fewer names than the usual universe): prices kept, top-20 flags unobserved
        n_by = h.groupby("snapshot_date").size()
        self.full_n = int(n_by.mode().max()) if len(n_by) else 0
        last = self.dates[-1] if self.dates else None
        self.partial = sorted(d for d, n in n_by.items() if n < self.full_n and d != last)
        self.top = self.top_raw.copy()
        if self.partial:
            self.top.loc[self.partial, :] = np.nan
        self.sector = h.groupby("ticker")["sector"].last()
        self.splits = splits or {}
        self.last_split = last_split or {}
        self.adj, self.applied = self._adjust()
        self.real_jumps = []
        self.breaks = self._breaks()

    def _adjust(self):
        adj, applied = self.px.copy(), []
        for tk, lst in self.splits.items():
            if tk not in adj.columns:
                continue
            for s in lst:
                rt = float(s.get("ratio") or 0)
                if rt <= 0:
                    continue
                mask = adj.index < s["date"]
                if mask.any() and (~mask).any():
                    adj.loc[mask, tk] = adj.loc[mask, tk] / rt
                    applied.append((tk, s["date"], s.get("factor")))
        return adj, applied

    def _ruled_out_by_yahoo(self, tk, d_from, d_to):
        """True when today's Yahoo split information says no split happened in (d_from, d_to]: its last split
        is earlier than the jump, and Yahoo was asked at least MIN_TD_AFTER_JUMP trading days after it."""
        ls = self.last_split.get(tk) or {}
        if not ls.get("date") or not ls.get("asof"):
            return False
        return ls["date"] <= d_from and td_between(d_to, ls["asof"]) >= self.MIN_TD_AFTER_JUMP

    def _breaks(self):
        """Split-like jumps between consecutive observations that no confirmed split explains and that Yahoo's
        split information does not rule out (those are recorded in self.real_jumps and kept as real moves)."""
        out = []
        for tk in self.adj.columns:
            s = self.adj[tk].dropna()
            vals, idx = s.values, s.index.tolist()
            for i in range(1, len(vals)):
                r = vals[i] / vals[i - 1]
                cands = [1 / k for k in range(2, 11)] + [k for k in range(2, 11)] + [2 / 3, 3 / 2]
                near = any(abs(r / c - 1) < 0.01 for c in cands)
                if not near:
                    continue
                later = vals[i + 1] if i + 1 < len(vals) else None
                persists = later is None or abs(np.log(later / vals[i])) < 0.15
                if not persists:
                    continue
                jump = {"ticker": tk, "from": idx[i - 1], "to": idx[i], "ratio": round(float(r), 4)}
                if self._ruled_out_by_yahoo(tk, idx[i - 1], idx[i]):
                    self.real_jumps.append({**jump, "yahoo_last_split": self.last_split[tk]["date"]})
                else:
                    out.append(jump)
        return out

    def window_ret(self, tk, d0, d1):
        """Price return d0 -> d1 on split-adjusted prices; NaN when missing or spanning a price break."""
        try:
            p0, p1 = self.adj.at[d0, tk], self.adj.at[d1, tk]
        except KeyError:
            return np.nan
        if pd.isna(p0) or pd.isna(p1):
            return np.nan
        for b in self.breaks:
            if b["ticker"] == tk and d0 <= b["from"] and b["to"] <= d1:
                return np.nan
        return float(p1 / p0 - 1)

    def ew_ret(self, d0, d1, names=None):
        names = list(self.adj.columns) if names is None else list(names)
        v = [self.window_ret(tk, d0, d1) for tk in names]
        v = [x for x in v if x == x]
        return (float(np.mean(v)) if v else np.nan), len(v)

    def max_drawdown(self, tk, d0, d1):
        s = self.adj.loc[(self.adj.index >= d0) & (self.adj.index <= d1), tk].dropna()
        if len(s) < 2:
            return np.nan
        for b in self.breaks:
            if b["ticker"] == tk and d0 <= b["from"] and b["to"] <= d1:
                return np.nan
        return float((s / s.cummax() - 1).min())

    def spells(self):
        """One row per top-20 spell, counted between OBSERVED rankings: it starts on the first ranking that
        shows the name in the top 20 and ends on the last one. A day with no ranking at all (machine off,
        refresh failed) or a partial snapshot inside a spell does not interrupt it. At an entry or exit next to
        such a gap the true date lies inside the gap: gap_before_td / gap_after_td say how many trading days
        had no ranking right before the entry / right after the last day on the list.
        left_censored = the spell was already running when the HISTORY starts, which only happens when the
        history starts after the list itself began (LIST_LAUNCH); since_launch = on since the list began."""
        dates, first = self.dates, self.dates[0]
        rows = []
        for tk in self.top.columns:
            s = self.top[tk]
            start = end = prev_obs = before = None
            n_obs = 0
            for d in dates:
                v = s.loc[d]
                if pd.isna(v):
                    continue
                if v:
                    if start is None:
                        start, n_obs, before = d, 0, prev_obs
                    end, n_obs = d, n_obs + 1
                elif start is not None:
                    rows.append(self._spell(tk, start, end, d, n_obs, first, before))
                    start = end = None
                prev_obs = d
            if start is not None:
                rows.append(self._spell(tk, start, end, None, n_obs, first, before))
        cols = ["ticker", "start", "last_on_list", "exit_observed", "ongoing", "left_censored", "since_launch",
                "snapshots_on_list", "trading_days", "calendar_days", "entry_rank", "gap_before_td",
                "gap_after_td"]
        return pd.DataFrame(rows, columns=cols).sort_values(["ticker", "start"]).reset_index(drop=True) \
            if rows else pd.DataFrame(columns=cols)

    def _spell(self, tk, start, end, exit_d, n_obs, first, before):
        gb = (self.tdi[start] - self.tdi[before] - 1) if before else 0
        ga = (self.tdi[exit_d] - self.tdi[end] - 1) if exit_d else 0
        return {"ticker": tk, "start": start, "last_on_list": end, "exit_observed": exit_d,
                "ongoing": exit_d is None, "left_censored": start == first and first > LIST_LAUNCH,
                "since_launch": start == LIST_LAUNCH, "snapshots_on_list": n_obs,
                "trading_days": self.tdi[end] - self.tdi[start] + 1,
                "calendar_days": (pd.Timestamp(end) - pd.Timestamp(start)).days + 1,
                "entry_rank": int(self.rank.at[start, tk]), "gap_before_td": max(int(gb), 0),
                "gap_after_td": max(int(ga), 0)}

    def tenure_on(self):
        """Trading days since the current spell began, per (date, ticker); NaN when off the list."""
        ten = pd.DataFrame(np.nan, index=self.top.index, columns=self.top.columns)
        for tk in self.top.columns:
            start = None
            for d in self.top.index:
                v = self.top.at[d, tk]
                if pd.isna(v):
                    continue
                if v:
                    start = d if start is None else start
                    ten.at[d, tk] = self.tdi[d] - self.tdi[start]
                else:
                    start = None
        return ten

    def cutoff(self, d):
        """(composite of rank 20, composite of rank 21) on date d, at the stored precision."""
        r, c = self.rank.loc[d], self.comp.loc[d]
        c20 = c[r == TOP_N]
        c21 = c[r == TOP_N + 1]
        return (float(c20.iloc[0]) if len(c20) else np.nan, float(c21.iloc[0]) if len(c21) else np.nan)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backfill", action="store_true", help="rebuild the CSV from the repo's git history")
    ap.add_argument("--repo", default=str(ROOT), help="git checkout to read (read-only); default: this repo")
    ap.add_argument("--out", default=str(HIST))
    ap.add_argument("--force", action="store_true", help="overwrite an existing CSV")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args(argv)
    if a.backfill:
        if Path(a.out).exists() and not a.force:
            print(f"{a.out} exists; pass --force to rebuild it from git"); return 1
        if not is_git_repo(a.repo):
            print(f"not a git checkout: {a.repo}"); return 1
        rep = {}
        df = backfill_from_git(a.repo, report=rep)
        save(df, a.out)
        print(f"backfill: {df['snapshot_date'].nunique()} snapshots, {len(df)} rows, "
              f"{df['snapshot_date'].min()}..{df['snapshot_date'].max()} -> {a.out}; intraday commits skipped "
              f"{len(rep.get('intraday', []))}")
    if a.summary:
        p = Panel(load(a.out), load_splits())
        sp = p.spells()
        print(f"{len(p.dates)} snapshots {p.dates[0]}..{p.dates[-1]}; spells {len(sp)} "
              f"({int((~sp.ongoing).sum())} completed); partial days {p.partial}; splits applied {p.applied}; "
              f"breaks {p.breaks} (no Yahoo split information here; the daily build passes it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
