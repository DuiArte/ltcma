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

PUBLISHED LIST vs RAW RANK (wave 14, 2026-11-04; Carlos's written OK: hysteresis at the rank-20 cut)
  The published list is 20 names, but since wave 14 it is not simply ranks 1-20. TWO-SIDED band (a
  main-session design choice within Carlos's OK; revert = set ENTER = None and the one-sided rule below):
    * a name ALREADY on the published list (an incumbent) stays while its rank is <= STAY (25);
    * a name off the list ranked <= ENTER (15) always enters; it displaces the worst-ranked incumbent(s)
      (only incumbents ranked 21-25 can be displaced: with 20 incumbents, an outsider inside the top 20
      means an incumbent outside it);
    * the remaining places go to the best-ranked names; the list always has exactly 20 names.
  published_list() implements it; ENTER = None gives the one-sided band (stay while rank <= STAY, no forced
  entry), the variant the wave-14 recheck rejected (it kept top-10 names off the list for months; it is
  still replayed on the page next to the plain top 20 so readers can see why).
  The previous membership is the on_list set of the last recorded session BEFORE the build's own session; if
  there is none or it does not hold exactly 20 names, the build falls back to the plain top 20 and the page
  says so. Columns: is_top20 = the RAW rank <= 20 (unchanged meaning for every old row); on_list = the
  PUBLISHED membership (the page's star); list_rule = "top20" (plain rule: every row before wave 14),
  RULE_BAND ("band15_25") or "top20_fallback" (band rule in force, previous list unusable). Old CSVs without
  the columns load with on_list = is_top20 and list_rule = "top20", which is what was published. The
  composite, the ranks and the weights never change: only which 20 names carry the star.
  15 / 25 were chosen on a RANKS-ONLY replay of the stored rankings (entries, short spells, rankings with a
  top-10 / top-15 name kept off the list), never on returns.
MACRO INPUTS VINTAGE (wave 14): macro_through = the data-through date of the capstone macro inputs the build
  ranked with (the sidecar of capstone_inputs_refresh.py; "" = unknown, i.e. every row before wave 14, when
  the inputs were frozen at May 2026 data). The first session with a date is the method change the page
  annotates (Panel.macro_since()). The git backfill reads it back from the page's hero line.

Facts derived here (no forecasting): spells on the published list, tenure in NYSE trading days and calendar
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
STAY = 25                                             # wave 14: an incumbent stays while rank <= STAY
ENTER = 15                                            # wave 14: an outsider ranked <= ENTER always enters
BAND = STAY - TOP_N                                   # 5: the width of the stay band (one-sided variant = band5)
EXIT_RANK = STAY
RULE_PLAIN, RULE_BAND, RULE_FALLBACK = "top20", f"band{ENTER}_{STAY}", "top20_fallback"
RULE_ONE_SIDED = f"band{BAND}"                        # rejected variant: replayed on the page, never published
# on_list / list_rule / macro_through are APPENDED (wave 14): a reader of the first 11 columns, by name or by
# position, is unchanged
COLS = ["snapshot_date", "rank", "ticker", "sector", "price_usd", "composite", "composite_dp",
        "is_top20", "universe_n", "source", "built_at", "on_list", "list_rule", "macro_through"]
RE_RULE_META = re.compile(r'<meta name="ltcma-picks-rule" content="([^"]+)"')
RE_MACRO_HTML = re.compile(r"macro inputs: prices through (\d{2} [A-Z][a-z]{2} \d{4})")
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
    res = {"asof": None, "header_n": None, "rows": [], "rule": None, "macro": ""}
    if not doc:
        return res
    m = RE_ASOF_HTML.search(doc)
    if m:
        res["asof"] = _date(m.group(1))
        res["header_n"] = int(m.group(2)) if m.group(2) else None
    mr = RE_RULE_META.search(doc)                     # wave 14 pages say which list rule built the star
    res["rule"] = mr.group(1) if mr else None
    mm = RE_MACRO_HTML.search(doc)                    # wave 14 hero: "macro inputs: prices through DD Mon YYYY"
    res["macro"] = (_date(mm.group(1)) or "") if mm else ""
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
    res = {"asof": None, "universe": None, "rows": [], "rule": None}
    if not doc:
        return res
    m = RE_ASOF_AI.search(doc)
    if m:
        res["asof"] = _date(m.group(1))
        res["universe"] = int(m.group(2))
    mr = re.search(r"\brule=(\w+)", doc)              # wave 14 header line 3
    res["rule"] = mr.group(1) if mr else None
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
        rule = h.get("rule") or RULE_PLAIN            # pages before wave 14 carry no rule: the star was ranks 1-20
        for r in h["rows"]:
            # is_top20 = the raw rank; on_list = the star the page published (equal on every pre-wave-14 page)
            row = {"rank": r["rank"], "ticker": r["ticker"], "sector": r["sector"], "price_usd": r["price_usd"],
                   "composite": r["composite"], "composite_dp": r["composite_dp"], "is_top20": r["rank"] <= TOP_N,
                   "universe_n": n, "on_list": bool(r["star"]), "list_rule": rule,
                   "macro_through": h.get("macro") or ""}
            ar = ai_by.get(r["ticker"])
            if ar is not None and ar["composite"] is not None and ar["composite_dp"] > row["composite_dp"]:
                row["composite"], row["composite_dp"] = ar["composite"], ar["composite_dp"]
            if ar is not None and ar["sector"]:
                row["sector"] = ar["sector"]
            out.append(row)
    elif a["rows"]:                                   # html overwritten by another page: the pick lines only
        for r in a["rows"]:                           # (ai.txt lists exactly the published picks)
            out.append({"rank": r["rank"], "ticker": r["ticker"], "sector": r["sector"],
                        "price_usd": r["price_usd"], "composite": r["composite"],
                        "composite_dp": r["composite_dp"], "is_top20": r["rank"] <= TOP_N,
                        "universe_n": a["universe"], "on_list": True,
                        "list_rule": a.get("rule") or RULE_PLAIN, "macro_through": ""})
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
def _bool(s):
    return s.astype(str).str.lower().isin(["true", "1"])


def _normalise(df):
    if df.empty:
        return pd.DataFrame(columns=COLS)
    df = df.copy()
    # wave 14: rows written before on_list / list_rule existed were published under the plain rule, so their
    # published membership IS the raw top-20 flag
    if "on_list" not in df.columns:
        df["on_list"] = df["is_top20"]
    if "list_rule" not in df.columns:
        df["list_rule"] = RULE_PLAIN
    miss = df["on_list"].isna() | (df["on_list"].astype(str).str.strip() == "")
    if miss.any():
        df.loc[miss, "on_list"] = df.loc[miss, "is_top20"]
    lr = df["list_rule"].astype(str).str.strip()
    df["list_rule"] = lr.where(~lr.isin(["", "nan", "None", "<NA>"]), RULE_PLAIN)
    # wave 14: the macro inputs' data-through date; "" = unknown (every row before wave 14: frozen inputs)
    if "macro_through" not in df.columns:
        df["macro_through"] = ""
    mt = df["macro_through"].astype(str).str.strip().str[:10]
    df["macro_through"] = mt.where(mt.str.match(r"^\d{4}-\d{2}-\d{2}$"), "")
    df = df[COLS].copy()
    df["rank"] = df["rank"].astype(int)
    df["composite_dp"] = df["composite_dp"].astype(int)
    df["is_top20"] = _bool(df["is_top20"])
    df["on_list"] = _bool(df["on_list"])
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
                               str(r.source or ""), str(r.built_at or ""), "True" if r.on_list else "False",
                               str(r.list_rule or RULE_PLAIN), str(r.macro_through or "")]))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    return path


def snapshot_from_picker(df, asof_date, built_at=None, members=None, rule=None, macro_through=None):
    """Today's picker DataFrame (indexed by ticker, sorted, with rank/sector/price/composite) -> rows in the
    published precision. Never touches weights. members = the PUBLISHED list (default: ranks 1-20, the plain
    rule); they are the stocks.ai.txt pick lines, published at 3 dp, so they are stored at 3 dp and every
    other name at the page's 2 dp. macro_through = the macro inputs' data-through date (iso) or None."""
    built_at = built_at or dt.datetime.now().astimezone().isoformat(timespec="seconds")
    n = len(df)
    if members is None:
        members = {str(tk) for tk, r in df.iterrows() if int(r["rank"]) <= TOP_N}
        rule = rule or RULE_PLAIN
    members = {str(x) for x in members}
    recs = []
    for tk, r in df.iterrows():
        rank = int(r["rank"])
        on = str(tk) in members
        dp = 3 if on else 2
        recs.append({"snapshot_date": str(asof_date), "rank": rank, "ticker": str(tk),
                     "sector": str(r.get("sector") or ""), "price_usd": round(float(r["price"]), 2),
                     "composite": round(float(r["composite"]), dp), "composite_dp": dp,
                     "is_top20": rank <= TOP_N, "universe_n": n, "source": "daily_build", "built_at": built_at,
                     "on_list": on, "list_rule": rule or RULE_PLAIN, "macro_through": macro_through or ""})
    return _normalise(pd.DataFrame(recs, columns=COLS))


# ------------------------------------------------------------------------------------------- list rule
def published_list(ranks, prev=None, stay=STAY, enter=ENTER, n=TOP_N):
    """The published list. ranks: {ticker: rank} of TODAY's ranking (1 = best); prev: the previous published
    list (iterable of tickers) or None. -> list of tickers sorted by rank.
      * prev None (no usable previous list): the plain top n.
      * otherwise (two-sided band, wave 14): every name of prev ranked <= `stay` is kept; every name NOT in prev
        ranked <= `enter` enters; if that is more than n names, the worst-ranked kept names are displaced (an
        outsider ranked <= enter < n implies an incumbent ranked > n, so only names ranked n+1..stay are ever
        displaced); the remaining places go to the best-ranked names not chosen yet.
      * enter=None: the one-sided band (no forced entry), the rejected variant kept for the replay.
    Always exactly n names whenever today's ranking holds >= n names. Pure: ranks, composites and weights are
    inputs, never changed."""
    order = sorted((int(r), str(t)) for t, r in dict(ranks).items() if r == r)
    if prev is None:
        return [t for _, t in order[:n]]
    prev = {str(x) for x in prev}
    forced = [t for r, t in order if t not in prev and enter is not None and r <= enter][:n]
    keep = [t for r, t in order if t in prev and r <= stay]          # rank order: best first
    keep = keep[:max(0, n - len(forced))]                            # displace the worst-ranked incumbents
    chosen = set(forced) | set(keep)
    fill = [t for _, t in order if t not in chosen][:max(0, n - len(chosen))]
    chosen |= set(fill)
    return [t for _, t in order if t in chosen]


def previous_list(hist, session):
    """(tickers, prev_session, why) of the last recorded session strictly BEFORE `session` (a same-day re-run
    never reads its own earlier build). tickers is None when there is no such session or its published list
    does not hold exactly TOP_N names (why says which)."""
    if hist is None or not len(hist):
        return None, None, "no stored history"
    h = _normalise(hist)
    before = sorted(d for d in h["snapshot_date"].unique() if d < str(session))
    if not before:
        return None, None, f"no ranking stored before {session}"
    d = before[-1]
    on = h[(h["snapshot_date"] == d) & h["on_list"]]["ticker"].tolist()
    if len(on) != TOP_N:
        return None, d, f"the {d} list holds {len(on)} names, not {TOP_N}"
    return on, d, ""


def _fallback(plain, d, why):
    return {"members": plain, "rule": RULE_FALLBACK, "prev_session": d, "why": why, "kept_by_band": [],
            "entered": [], "left": [], "displaced": [], "forced": [], "stay": STAY, "enter": ENTER}


def membership(hist, df_picker, session, stay=STAY, enter=ENTER):
    """Today's published list for the build whose prices belong to `session` (price_session()). NEVER raises:
    any problem with the stored history gives the plain top 20 (rule top20_fallback) and a reason the page
    shows. -> dict(members, rule, prev_session, why, kept_by_band (picks ranked 21-25 kept), entered, left,
    displaced (picks still ranked <= stay that a name ranked <= enter pushed out), forced (names off the list
    that entered because they rank <= enter), stay, enter)."""
    ranks = {str(t): int(r) for t, r in df_picker["rank"].items()}
    plain = published_list(ranks, None)
    try:
        prev, d, why = previous_list(hist, session)
    except Exception as e:                                              # noqa: BLE001
        prev, d, why = None, None, f"history unreadable ({type(e).__name__})"
    if prev is None:
        return _fallback(plain, d, why)
    mem = published_list(ranks, prev, stay, enter)
    if len(mem) != TOP_N:                     # cannot happen with a full ranking; never publish a short list
        return _fallback(plain, d, f"the band gave {len(mem)} names")
    ps, ms = set(prev), set(mem)
    rule = RULE_BAND if (stay, enter) == (STAY, ENTER) else (f"band{enter}_{stay}" if enter is not None
                                                            else f"band{stay - TOP_N}")
    return {"members": mem, "rule": rule, "prev_session": d, "why": "",
            "kept_by_band": [t for t in mem if ranks.get(t, 99) > TOP_N],
            "entered": [t for t in mem if t not in ps], "left": sorted(ps - ms, key=lambda t: ranks.get(t, 99)),
            "displaced": sorted((t for t in ps - ms if ranks.get(t, 99) <= stay), key=lambda t: ranks.get(t, 99)),
            "forced": [t for t in mem if t not in ps and enter is not None and ranks.get(t, 99) <= enter],
            "stay": stay, "enter": enter}


def append_snapshot(hist, snap):
    """Idempotent: rows with the same snapshot_date are replaced, never duplicated."""
    if snap.empty:
        return _normalise(hist)
    dates = set(snap["snapshot_date"])
    keep = hist[~hist["snapshot_date"].isin(dates)] if len(hist) else hist
    return _normalise(pd.concat([keep, snap], ignore_index=True) if len(keep) else snap)


def add_build(hist, df_picker, now=None, members=None, rule=None, macro_through=None):
    """Record today's ranking under the session its prices belong to (price_session). -> (hist, info).
    Same-day post-close build: replaces that session (re-runs are idempotent). Later pre-open build: fills
    the session only if it has no rows. Intraday build: records nothing (quotes are not closes).
    members / rule = the PUBLISHED list of this build (membership()); default = the plain top 20.
    macro_through = the data-through date of the macro inputs this ranking used (None = unknown)."""
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
    snap = snapshot_from_picker(df_picker, sess, built_at=now.isoformat(timespec="seconds"), members=members,
                                rule=rule, macro_through=macro_through)
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
        # the PUBLISHED list (the star; wave 14): spells, tenure, the basket and the tracker follow it
        self.top_raw = h.assign(t=h["on_list"].astype(float)).pivot(
            index="snapshot_date", columns="ticker", values="t").sort_index()
        # the raw rank <= 20 flag (equal to the published list before wave 14); used by the rule replay
        self.top20_raw = h.assign(t=h["is_top20"].astype(float)).pivot(
            index="snapshot_date", columns="ticker", values="t").sort_index()
        self.rule = h.groupby("snapshot_date")["list_rule"].first().to_dict()
        # the macro inputs' data-through date per ranking ("" = unknown: the frozen inputs before wave 14)
        self.macro = h.groupby("snapshot_date")["macro_through"].max().to_dict()
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
        return self.spells_of(self.top)

    def spells_of(self, top):
        """spells() for any membership frame (date x ticker, 1 / 0 / NaN = unobserved), e.g. a rule replay."""
        dates, first = self.dates, self.dates[0]
        rows = []
        for tk in top.columns:
            s = top[tk].reindex(dates)
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

    def cutoff(self, d, rank=TOP_N):
        """(composite of rank `rank`, composite of rank `rank` + 1) on date d, at the stored precision. The
        band's exit line is cutoff(d, EXIT_RANK): a listed name leaves when it falls behind the rank-26 name."""
        r, c = self.rank.loc[d], self.comp.loc[d]
        c20 = c[r == rank]
        c21 = c[r == rank + 1]
        return (float(c20.iloc[0]) if len(c20) else np.nan, float(c21.iloc[0]) if len(c21) else np.nan)

    def macro_since(self):
        """-> (since, last_frozen, n_undated_after): the first ranking made with dated (refreshed) macro inputs,
        the last ranking before it (the end of the frozen-input period) and how many later rankings carry no
        date again (inputs rolled back or the sidecar missing). (None, last ranking, 0) while no ranking has
        refreshed inputs. Read from the stored history, so it is the same on every later build."""
        since = next((d for d in self.dates if self.macro.get(d)), None)
        if since is None:
            return None, (self.dates[-1] if self.dates else None), 0
        before = [d for d in self.dates if d < since]
        undated = sum(1 for d in self.dates if d > since and not self.macro.get(d))
        return since, (before[-1] if before else None), undated

    def band_since(self):
        """-> (first ranking published under a band rule, [later rankings that fell back to the plain top 20])."""
        since = next((d for d in self.dates if str(self.rule.get(d, "")).startswith("band")), None)
        fb = [d for d in self.dates if since and d > since and self.rule.get(d) == RULE_FALLBACK]
        return since, fb

    def method_changes(self):
        """{ranking: [what changed]} for the one-off method changes the page annotates (wave 14): the first
        ranking on refreshed macro inputs and the first ranking under the band rule. Entries and exits at these
        rankings come from the change of method, not from ordinary day-to-day turnover."""
        out = {}
        ms = self.macro_since()[0]
        if ms:
            out.setdefault(ms, []).append("macro")
        bs = self.band_since()[0]
        if bs:
            out.setdefault(bs, []).append("band")
        return out

    def rank_noise_at_cut(self, lo=TOP_N - 4, hi=EXIT_RANK, within=BAND):
        """Ranks only (no returns): over consecutive full rankings one trading day apart, the 1-day rank moves
        of names ranked lo..hi on the first day. -> dict(n, share within +/- `within` ranks, median |move|,
        90th percentile |move|). The band is meant to absorb this noise; it was NOT chosen from it."""
        part = set(self.partial)
        mv = []
        for d0, d1 in zip(self.dates[:-1], self.dates[1:]):
            if self.tdi[d1] - self.tdi[d0] != 1 or d0 in part or d1 in part:
                continue
            r0, r1 = self.rank.loc[d0], self.rank.loc[d1]
            for tk in self.rank.columns:
                a, b = r0.get(tk), r1.get(tk)
                if pd.isna(a) or pd.isna(b) or not (lo <= a <= hi):
                    continue
                mv.append(abs(int(b) - int(a)))
        if not mv:
            return {"n": 0}
        mv = np.array(mv)
        return {"n": int(len(mv)), "share_within": float((mv <= within).mean()), "median": float(np.median(mv)),
                "p90": float(np.percentile(mv, 90)), "lo": lo, "hi": hi, "within": within}


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
