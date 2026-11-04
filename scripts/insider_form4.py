"""insider_form4 -- SEC Form 4 insider trades for the Stock Research universe (wave 13, 2026-11-04).

Display-only overlay for docs/stocks.html. It never feeds the composite, the ranks or the weights.

FETCH POLICY (MARKET_INTEL_DATA_SOURCES E01, house rules):
  * sec.gov / data.sec.gov ONLY, with the canonical SEC User-Agent below (never sent to any other host);
  * one request start per MIN_INTERVAL s (0.3 s: under SEC's 10/s and the house 4/s ceiling);
  * NO retry of anything. 401/403/410/429 = blocked: the host is not asked again this run, the cause is
    printed and alerted, and every cell that needed it says "not available today (data gap)";
  * redirects are NOT followed (a 3xx is a gap), so the SEC User-Agent can never be carried to another host;
  * stall breaker: STALL_AFTER network failures in a row (no HTTP answer) or the run's wall-clock cap
    (max_seconds, default 300 s; the CLI backfill passes more) stop SEC for the rest of the run;
  * one SEC job at a time on this machine (the house 4 req/s ceiling is per machine, not per process): the
    run does not start, or stops at once, while the rotation model's flow job holds its lock
    (Documents\\Rotation_Signals\\raw\\flow\\flow.lock, held by a live process) or while that job's persisted
    sec.gov cooldown (flow_state.json host_cooldown, set after a 429) is running; both are READ-ONLY here.
    A site-side lock (.cache/sec_form4/sec.lock) keeps two site processes (daily build, CLI backfill) apart.
    The rotation does not read the site's lock, so the site re-checks the rotation's lock every few seconds
    while it runs and stops when it appears;
  * a per-run request budget (default 160; the one staging run used <= 120).
COST CONTROL: submissions JSON per issuer is re-asked only when the copy in the cache is older than
  SUBM_MIN_AGE_H (standard If-Modified-Since / If-None-Match are sent when SEC gave validators; for
  submissions it gives none, so the age rule is what saves requests). A Form 4 XML is fetched once, ever.
  The rotation model's Form 4 store (Trading_Index flow parquet) is read READ-ONLY and every filing it
  already parsed is reused, never re-fetched. The first runs backfill 180 days newest-first, at most
  max_xml filings per run; until an issuer's window is complete its cell says how far the backfill got.
CACHE: <repo>/.cache/sec_form4/ (git-ignored; public SEC data, not published as a file).
PARSER: parse_form4 / tx_footnotes / nonmarket_footnotes are ported verbatim from
  Trading_Index/rotation/informed_flow.py (F4_PARSE_VERSION 3); tests/test_insider.py checks parity.
NAMES: reporting-owner names are shown exactly as the SEC publishes them on the filing (SHOW_NAMES).

  python scripts/insider_form4.py --backfill [--max-xml 2000] [--budget 2400]   # one-time, off-hours
  python scripts/insider_form4.py --status
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

try:
    from paths import ROOT, CUSER
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent
    CUSER = Path("C:/Users/carlo")

UA = "Carlos Duarte Quantitative Research carlosduartem@hotmail.com"      # SEC canonical UA, sec.gov only
MIN_INTERVAL = 0.3
BLOCK_CODES = (401, 403, 410, 429)
SUBM_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
CACHE = ROOT / ".cache" / "sec_form4"
ROTATION_FLOW = Path(CUSER) / "Documents" / "Rotation_Signals" / "raw" / "flow"
ROTATION_F4 = ROTATION_FLOW / "form4_transactions.parquet"
ROTATION_LOCK = ROTATION_FLOW / "flow.lock"              # 'pid iso-start' while the rotation flow job runs
ROTATION_STATE = ROTATION_FLOW / "flow_state.json"       # host_cooldown {host: {until: iso, ...}}
SEC_HOSTS = ("data.sec.gov", "www.sec.gov", "sec.gov", "efts.sec.gov")
STALL_AFTER = 3
MAX_SECONDS = 300
PAUSE_CHECK_S = 5.0
SUBM_MIN_AGE_H = 20
KEEP_DAYS = 200                      # filing list kept per issuer (>= the 180-day window + margin)
WINDOWS = (90, 180)
STALE_DAYS = 3                       # filing list older than this: shown with its own as-of date
GAP_DAYS = 10                        # ... older than this: a gap, never shown as current
SHOW_NAMES = True                    # insider names as the SEC publishes them (Carlos may switch to roles)
F4_PARSE_VERSION = 3

# CIKs from SEC company_tickers.json (local copy fetched 2026-10-31; 0 requests at run time).
# XOM maps to 2115436 there (not the historical 34088): flagged in DEPLOY_NOTES, verify before relying on it.
UNIVERSE_CIK = {"AAPL": 320193, "ABBV": 1551152, "ADBE": 796343, "AMD": 2488, "AMZN": 1018724, "ANET": 1596532,
                "ARM": 1973239, "AVGO": 1730168, "BAC": 70858, "COIN": 1679788, "COST": 909832, "CRM": 1108524,
                "CRWD": 1535527, "CVX": 93410, "DDOG": 1561550, "GOOGL": 1652044, "HD": 354950, "INTU": 896878,
                "JPM": 19617, "KO": 21344, "LLY": 59478, "META": 1326801, "MSFT": 789019, "MSTR": 1050446,
                "NET": 1477333, "NFLX": 1065280, "NOW": 1373715, "NVDA": 1045810, "NVO": 353278, "ORCL": 1341439,
                "PLTR": 1321655, "SHOP": 1594805, "SMCI": 1375365, "SNOW": 1640147, "T": 732717, "TSLA": 1318605,
                "UNH": 731766, "VZ": 732712, "WMT": 104169, "XOM": 2115436}
NO_FORM4 = {"NVO": "foreign private issuer: it files 6-K / 20-F, and insiders file no Form 4 (0 of 1,001 "
                   "filings in its SEC list are Form 4)"}
LINE_COLS = ["accession", "seq", "issuer_cik", "ticker", "form", "filing_date", "as_of", "owner_cik",
             "owner_name", "is_director", "is_officer", "officer_title", "is_ten_pct", "aff10b5one", "tx_date",
             "code", "acq_disp", "shares", "price", "value_usd", "footnotes", "url", "source"]
NOTABLE = re.compile(r"chief executive|\bceo\b|chief financial|\bcfo\b|president|chair|chief operating|\bcoo\b",
                     re.I)
PLAN_RX = re.compile(r"10b5-?1", re.I)
# a footnote that mentions a plan only to deny it ("not made pursuant to a Rule 10b5-1 plan") is not a plan
NEG_WORD_RX = re.compile(r"\b(?:not|no|neither|nor|without|outside)\b", re.I)


def plan_footnote(s):
    """True when some footnote mention of a Rule 10b5-1 plan is not denied in the same sentence before it."""
    for part in str(s or "").split(" | "):
        for m in PLAN_RX.finditer(part):
            before = re.split(r"[.;]\s", part[:m.start()])[-1][-80:]
            if not NEG_WORD_RX.search(before):
                return True
    return False


# ============================================================ parser (ported from informed_flow.py, v3)
def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _t(el, path):
    v = el.findtext(path)
    return v.strip() if v else None


def _b(el, path):
    v = (_t(el, path) or "").lower()
    return v in ("1", "true")


FOOTNOTE_SKIP = ("postTransactionAmounts",)
OWN_MARK = " (ownership)"


def tx_footnotes(tx, notes, max_chars=600):
    ids, where = [], defaultdict(set)
    for child in tx:
        if child.tag in FOOTNOTE_SKIP:
            continue
        for f in child.iter("footnoteId"):
            i = f.get("id")
            if not i:
                continue
            if i not in ids:
                ids.append(i)
            where[i].add(child.tag)
    return " | ".join(f"{i}{OWN_MARK if where[i] == {'ownershipNature'} else ''}: {notes.get(i, '')[:max_chars]}"
                      for i in ids) or None


def parse_form4(xml_text):
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    notes = {fn.get("id"): " ".join("".join(fn.itertext()).split()) for fn in root.findall("footnotes/footnote")}
    owners = root.findall("reportingOwner")
    o = owners[0] if owners else None
    head = {"issuer_cik": (_t(root, "issuer/issuerCik") or "").lstrip("0"), "ticker": _t(root, "issuer/issuerTradingSymbol"),
            "issuer_name": _t(root, "issuer/issuerName"), "form": _t(root, "documentType"),
            "owner_cik": (_t(o, "reportingOwnerId/rptOwnerCik") or "").lstrip("0") if o is not None else None,
            "owner_name": _t(o, "reportingOwnerId/rptOwnerName") if o is not None else None, "n_owners": len(owners),
            "is_director": _b(o, "reportingOwnerRelationship/isDirector") if o is not None else None,
            "is_officer": _b(o, "reportingOwnerRelationship/isOfficer") if o is not None else None,
            "officer_title": _t(o, "reportingOwnerRelationship/officerTitle") if o is not None else None,
            "is_ten_pct": _b(o, "reportingOwnerRelationship/isTenPercentOwner") if o is not None else None,
            "aff10b5one": _b(root, "aff10b5One")}
    txs = []
    for i, tx in enumerate(root.findall("nonDerivativeTable/nonDerivativeTransaction")):
        sh = _f(_t(tx, "transactionAmounts/transactionShares/value"))
        px = _f(_t(tx, "transactionAmounts/transactionPricePerShare/value"))
        txs.append({"seq": i, "security": _t(tx, "securityTitle/value"), "tx_date": _t(tx, "transactionDate/value"),
                    "code": _t(tx, "transactionCoding/transactionCode"),
                    "acq_disp": _t(tx, "transactionAmounts/transactionAcquiredDisposedCode/value"),
                    "shares": sh, "price": px, "value_usd": sh * px if (sh is not None and px is not None) else None,
                    "shares_after": _f(_t(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")),
                    "direct_indirect": _t(tx, "ownershipNature/directOrIndirectOwnership/value"),
                    "footnotes": tx_footnotes(tx, notes), "parse_version": F4_PARSE_VERSION})
    return head, txs


_NM_CORE = (r"substitut|acquired from .{0,60}trust|in exchange for|(?<!stock )exchange of|in[- ]kind|"
            r"dividend reinvest|reinvest\w* of (?:the )?dividend|\bDRIP\b|employee stock purchase|\bESPP\b|"
            r"privately negotiated|private (?:purchase|transaction|placement)|underwrit|public offering|"
            r"directed share|401\s?\(k\)")
NONMARKET_RX = re.compile(_NM_CORE + r"|gift|transfer(?:red)? (?:from|to)", re.I)
NONMARKET_OWN_RX = re.compile(_NM_CORE, re.I)


def nonmarket_footnotes(s):
    for part in str(s or "").split(" | "):
        own = part.split(":", 1)[0].endswith(OWN_MARK)
        if (NONMARKET_OWN_RX if own else NONMARKET_RX).search(part):
            return True
    return False


# ============================================================ honest SEC client
class SecClient:
    """sec.gov hosts only, canonical UA, one start per MIN_INTERVAL s, no retries, no redirects, stop at a
    block, stop after STALL_AFTER network failures in a row or after max_seconds, stop when pause_check()
    returns a reason (the rotation's SEC job started)."""

    def __init__(self, budget, min_interval=MIN_INTERVAL, session=None, alert=None, log=print,
                 max_seconds=MAX_SECONDS, pause_check=None):
        import requests
        self._rq = requests
        self.s = session if session is not None else requests.Session()
        self.s.trust_env = False
        self.s.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
        self.budget, self.min_interval = int(budget), float(min_interval)
        self.sent, self.bytes, self.t_last = 0, 0, 0.0
        self.blocked, self.stalled, self.paused, self.gaps = None, None, None, []
        self.alert, self.log = alert, log
        self.max_seconds, self.t0, self.fails = float(max_seconds), None, 0
        self.pause_check, self.t_pause = pause_check, 0.0

    def _stop(self, attr, why):
        setattr(self, attr, why)
        msg = f"stocks overlay data gap: SEC {why}; not retried, no further SEC request this run"
        self.log(msg)
        if self.alert:
            self.alert(msg)

    def get(self, url, what="", headers=None):
        host = (urlparse(url).hostname or "").lower()
        if not (host == "sec.gov" or host.endswith(".sec.gov")):
            raise ValueError(f"SEC client refuses non-SEC host {host}: the SEC User-Agent is for sec.gov only")
        if self.blocked or self.stalled or self.paused:
            return None
        if self.sent >= self.budget:
            self.gaps.append(f"{what}: budget of {self.budget} SEC requests reached")
            return None
        now = time.time()
        self.t0 = self.t0 or now
        if now - self.t0 > self.max_seconds:
            self._stop("stalled", f"run time cap of {self.max_seconds:.0f} s reached")
            return None
        if self.pause_check and now - self.t_pause >= PAUSE_CHECK_S:
            self.t_pause = now
            why = self.pause_check()
            if why:
                self.paused = why
                self.log(f"insider: SEC paused: {why}")
                return None
        wait = self.min_interval - (time.time() - self.t_last)
        if wait > 0:
            time.sleep(wait)
        self.sent += 1
        try:
            # allow_redirects=False: a redirect would carry the SEC User-Agent to its target; a 3xx is a gap
            r = self.s.get(url, timeout=30, headers=headers or None, allow_redirects=False)
        except self._rq.RequestException as e:
            self.t_last = time.time()
            self.fails += 1
            self.gaps.append(f"{what}: {type(e).__name__}: {str(e)[:120]}")
            if self.fails >= STALL_AFTER:
                self._stop("stalled", f"not answering ({self.fails} network failures in a row on {host})")
            return None
        self.t_last, self.fails = time.time(), 0
        self.bytes += len(r.content or b"")
        if r.status_code in BLOCK_CODES:
            self.blocked = f"HTTP {r.status_code} on {host} ({what})"
            msg = f"stocks overlay data gap: SEC {self.blocked}; not retried, no further SEC request this run"
            self.log(msg)
            if self.alert:
                self.alert(msg)
            return None
        if 300 <= r.status_code < 400 and r.status_code != 304:
            self.gaps.append(f"{what}: HTTP {r.status_code} redirect not followed")
        return r


# ============================================================ one SEC job at a time on this machine
def pid_alive(pid):
    """True / False / None (unknown). Windows: OpenProcess + GetExitCodeProcess (never os.kill(pid, 0): on Windows
    that would terminate the process)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.OpenProcess(0x1000, False, pid)                      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            err = ctypes.get_last_error()
            return True if err == 5 else False if err == 87 else None
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return None
            return code.value == 259                                 # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_holder(path):
    """'pid iso' lock file -> pid if that process is alive, else None."""
    try:
        txt = Path(path).read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return None
    if not txt:
        return None
    return int(txt[0]) if txt[0].isdigit() and pid_alive(txt[0]) else None


def rotation_sec_busy(now=None, lock=None, state=None):
    """READ-ONLY look at the rotation model's flow job: a reason string while it runs (live lock) or while its
    persisted sec.gov cooldown is active, else None."""
    now = now or _now()
    holder = _lock_holder(lock or ROTATION_LOCK)
    if holder:
        return f"the rotation model's flow job is running (pid {holder}); SEC requests wait for it"
    try:
        st = json.loads(Path(state or ROTATION_STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for host, c in ((st or {}).get("host_cooldown") or {}).items():
        if str(host).lower() in SEC_HOSTS and isinstance(c, dict):
            until = _ts(c.get("until"))
            if until and until > now:
                return f"{host} cooldown after an HTTP {c.get('status', '429')} until {_iso(until)}"
    return None


class SiteLock:
    """One site-side SEC job at a time (daily build vs CLI backfill). Not taken -> .held is False."""

    def __init__(self, root):
        self.path, self.held = Path(root) / "sec.lock", False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        holder = _lock_holder(self.path)
        if holder and holder != os.getpid():
            return self
        try:
            self.path.write_text(f"{os.getpid()} {_iso(_now())}\n", encoding="utf-8")
            self.held = True
        except OSError:
            pass
        return self

    def __exit__(self, *exc):
        if self.held:
            try:
                self.path.unlink()
            except OSError:
                pass
        return False


# ============================================================ cache
def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(x):
    return x.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if x else None


def _ts(s):
    try:
        t = pd.Timestamp(s)
        return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).to_pydatetime()
    except (TypeError, ValueError):
        return None


class Cache:
    def __init__(self, root=None):
        self.root = Path(root or CACHE)
        self.state_p = self.root / "state.json"
        self.lines_p = self.root / "form4_lines.csv.gz"
        try:
            self.state = json.loads(self.state_p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault("issuers", {})
        self.state.setdefault("handled", {})
        self.state.setdefault("fail404", {})
        try:
            self.lines = pd.read_csv(self.lines_p, dtype=str, keep_default_na=False)
        except (OSError, ValueError, pd.errors.EmptyDataError):
            self.lines = pd.DataFrame(columns=LINE_COLS)
        for c in LINE_COLS:
            if c not in self.lines:
                self.lines[c] = ""
        self.new_lines = []

    def add_lines(self, rows):
        self.new_lines.extend(rows)

    def all_lines(self):
        df = pd.concat([self.lines[LINE_COLS], pd.DataFrame(self.new_lines, columns=LINE_COLS).astype(str)],
                       ignore_index=True) if self.new_lines else self.lines[LINE_COLS]
        return df.drop_duplicates(["accession", "seq"], keep="first")

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lines = self.all_lines()
        keep_from = (_now() - timedelta(days=2 * KEEP_DAYS)).date().isoformat()     # bounded cache
        lines = lines[lines["filing_date"].astype(str) >= keep_from]
        buf = io.StringIO()
        lines.to_csv(buf, index=False, lineterminator="\n")
        tmp = self.lines_p.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
        os.replace(tmp, self.lines_p)
        tmp = self.state_p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=0, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.state_p)
        self.lines, self.new_lines = lines, []


def _row(head, tx, acc, cik, ticker, form, filing_date, as_of, url, source):
    r = {**head, **tx, "accession": acc, "issuer_cik": head.get("issuer_cik") or str(cik),
         "ticker": ticker, "form": form, "filing_date": filing_date, "as_of": as_of, "url": url, "source": source}
    return {c: ("" if r.get(c) is None else str(r.get(c))) for c in LINE_COLS}


def merge_rotation(cache, path=None, log=print):
    """Reuse the rotation model's parsed Form 4 lines (READ-ONLY) for universe issuers."""
    p = Path(path or ROTATION_F4)
    if not p.exists():
        return 0
    try:
        rot = pd.read_parquet(p)
    except Exception as e:                                              # noqa: BLE001
        log(f"insider: rotation Form 4 store unreadable ({type(e).__name__}); not reused")
        return 0
    cik2t = {str(c): t for t, c in UNIVERSE_CIK.items()}
    rot = rot[rot["issuer_cik"].astype(str).isin(cik2t)]
    handled = cache.state["handled"]
    rows, accs = [], set()
    for r in rot.to_dict("records"):
        acc = str(r["accession"])
        if acc in handled and handled[acc] != "parsed:rotation":
            continue
        rr = {c: ("" if r.get(c) is None or (isinstance(r.get(c), float) and math.isnan(r.get(c))) else str(r.get(c)))
              for c in LINE_COLS}
        rr["ticker"] = cik2t[str(r["issuer_cik"])]
        rr["source"] = "rotation_store"
        rows.append(rr)
        accs.add(acc)
    have = set(cache.all_lines()["accession"])
    rows = [r for r in rows if r["accession"] not in have]
    cache.add_lines(rows)
    for a in accs:
        handled.setdefault(a, "parsed:rotation")
    return len(accs)


# ============================================================ refresh
def _form4_entries(rec, lo):
    """Columnar SEC filing list -> [[accession, filingDate, acceptanceDateTime, primary doc, form]] (Form 4 / 4-A
    filed on or after lo)."""
    forms = rec.get("form") or []
    n = len(forms)
    acc, fd = rec.get("accessionNumber") or [None] * n, rec.get("filingDate") or [""] * n
    at, doc = rec.get("acceptanceDateTime") or [None] * n, rec.get("primaryDocument") or [""] * n
    return [[acc[k], fd[k], at[k], (doc[k] or "").split("/")[-1], f] for k, f in enumerate(forms)
            if f in ("4", "4/A") and (fd[k] or "") >= lo]


def _filings(st):
    """Recent + older-page Form 4 entries of one issuer, de-duplicated by accession."""
    seen, out = set(), []
    for f in (st.get("filings") or []) + [x for p in (st.get("older") or {}).values() for x in p.get("rows") or []]:
        if f[0] not in seen:
            seen.add(f[0])
            out.append(f)
    return out


def _listed_from(st):
    """Earliest filing date the stored list covers (recent list + fetched older pages)."""
    c = [st.get("recent_from")] + [p.get("from") for p in (st.get("older") or {}).values()]
    c = [x for x in c if x]
    return min(c) if c else None


def _subm_due(st, now):
    t = _ts(st.get("subm_at")) if st else None
    return t is None or (now - t) >= timedelta(hours=SUBM_MIN_AGE_H)


def refresh(tickers, now=None, budget=160, max_xml=120, offline=False, cache_root=None, client=None,
            alert=None, log=print, rotation_path=None, pick_set=None, max_seconds=MAX_SECONDS, busy_check=None):
    """Bring the cache up to date for `tickers` (priority order: picks first). Returns (cache, report).
    busy_check() -> reason|None (default rotation_sec_busy): asked before the first SEC request and every few
    seconds during the run; a reason means no (further) SEC request this run (rep["paused"])."""
    tickers = list(tickers)
    now = now or _now()
    cache = Cache(cache_root)
    rep = {"rotation_filings_reused": merge_rotation(cache, rotation_path, log), "submissions": 0,
           "submissions_skipped_recent": 0, "xml_fetched": 0, "xml_left": 0, "blocked": None, "stalled": None,
           "paused": None, "gaps": [], "requests": 0, "bytes": 0, "offline": offline}
    if offline:
        cache.save()
        return cache, rep
    busy = busy_check if busy_check is not None else (rotation_sec_busy if client is None else (lambda: None))
    why = busy()
    if why:
        rep["paused"] = why
        log(f"insider: SEC not asked this run: {why}")
        cache.save()
        return cache, rep
    with SiteLock(cache.root) as lk:
        if not lk.held:
            rep["paused"] = "another site SEC job is running (site lock held)"
            log(f"insider: SEC not asked this run: {rep['paused']}")
            cache.save()
            return cache, rep
        sec = client or SecClient(budget, alert=alert, log=log, max_seconds=max_seconds, pause_check=busy)
        return _refresh_run(cache, rep, sec, tickers, now, max_xml, pick_set)


def _refresh_run(cache, rep, sec, tickers, now, max_xml, pick_set):
    def stopped():
        return getattr(sec, "blocked", None) or getattr(sec, "stalled", None) or getattr(sec, "paused", None)
    lo_keep = (now - timedelta(days=KEEP_DAYS)).date().isoformat()
    order = [t for t in tickers if t in UNIVERSE_CIK and t not in NO_FORM4]
    for tk in order:                                                  # 1) filing lists
        if stopped():
            break
        cik = UNIVERSE_CIK[tk]
        st = cache.state["issuers"].get(str(cik)) or {}
        if not _subm_due(st, now):
            rep["submissions_skipped_recent"] += 1
            continue
        hdr = {}
        if st.get("lm"):
            hdr["If-Modified-Since"] = st["lm"]
        if st.get("etag"):
            hdr["If-None-Match"] = st["etag"]
        r = sec.get(SUBM_URL.format(cik=cik), what=f"submissions {tk}", headers=hdr)
        if r is None:
            continue
        if r.status_code == 304:
            st["subm_at"] = _iso(now)
            cache.state["issuers"][str(cik)] = st
            rep["submissions"] += 1
            continue
        if r.status_code != 200:
            sec.gaps.append(f"submissions {tk}: HTTP {r.status_code}")
            continue
        try:
            j = r.json()
        except ValueError:
            sec.gaps.append(f"submissions {tk}: non-JSON body")
            continue
        rec = (j.get("filings") or {}).get("recent") or {}
        fl = _form4_entries(rec, lo_keep)
        oldest_listed = min(rec.get("filingDate") or [""]) if rec.get("filingDate") else ""
        older = dict(st.get("older") or {})
        # A heavy filer's "recent" list (<= 1,000 filings) can end inside the window (banks file thousands of
        # prospectus supplements): the older pages are immutable, so each is fetched once and kept.
        if oldest_listed and oldest_listed > lo_keep:
            for page in (j.get("filings") or {}).get("files") or []:
                name = page.get("name")
                if not name or name in older or (page.get("filingTo") or "") < lo_keep or stopped():
                    continue
                rp = sec.get(f"https://data.sec.gov/submissions/{name}", what=f"submissions page {tk} {name}")
                if rp is None or rp.status_code != 200:
                    break
                try:
                    older[name] = {"from": page.get("filingFrom"), "rows": _form4_entries(rp.json(), lo_keep)}
                except ValueError:
                    break
        cache.state["issuers"][str(cik)] = {"ticker": tk, "subm_at": _iso(now), "filings": fl,
                                           "lm": r.headers.get("Last-Modified"), "etag": r.headers.get("ETag"),
                                           "recent_from": oldest_listed, "older": older}
        rep["submissions"] += 1
    handled = cache.state["handled"]                                  # 2) Form 4 XMLs
    lo90 = (now - timedelta(days=90)).date().isoformat()
    picks = set(pick_set if pick_set is not None else tickers[:20])
    pend = []
    for pri, tk in enumerate(order):
        st = cache.state["issuers"].get(str(UNIVERSE_CIK[tk])) or {}
        miss = [f for f in _filings(st) if f[0] not in handled]
        miss90 = sum(1 for f in miss if f[1] >= lo90)
        for f in miss:
            # 90-day window first, picks first, issuers closest to a complete window first, newest first
            pend.append((0 if f[1] >= lo90 else 1, 0 if tk in picks else 1, miss90, pri,
                         -int(f[1].replace("-", "")), tk, f))
    pend.sort(key=lambda x: x[:5])
    for *_k, tk, f in pend:
        if stopped() or rep["xml_fetched"] >= max_xml or sec.sent >= sec.budget:
            rep["xml_left"] += 1
            continue
        acc, fdate, accept, doc, form = f
        cik = UNIVERSE_CIK[tk]
        if not doc.lower().endswith(".xml"):
            handled[acc] = "not_xml"
            continue
        url = DOC_URL.format(cik=cik, acc=acc.replace("-", ""), doc=doc)
        r = sec.get(url, what=f"form4 {tk} {acc}")
        rep["xml_fetched"] += 1
        if r is None:
            rep["xml_left"] += 1
            continue
        if r.status_code != 200:
            sec.gaps.append(f"form4 {tk} {acc}: HTTP {r.status_code}")
            if r.status_code == 404:
                n = cache.state["fail404"][acc] = int(cache.state["fail404"].get(acc) or 0) + 1
                if n >= 3:
                    handled[acc] = "missing_404"
            rep["xml_left"] += 1
            continue
        try:
            head, txs = parse_form4(r.text)
        except ET.ParseError as e:
            sec.gaps.append(f"form4 {tk} {acc}: XML parse error {str(e)[:60]}")
            rep["xml_left"] += 1
            continue
        lm = None
        try:
            lm = parsedate_to_datetime(r.headers.get("Last-Modified")) if r.headers.get("Last-Modified") else None
        except (TypeError, ValueError, IndexError):
            lm = None
        stamps = [x for x in (_ts(accept) if accept else None, lm, now) if x is not None]
        as_of = _iso(min(stamps))
        if head["issuer_cik"] and head["issuer_cik"] != str(cik):
            handled[acc] = "other_issuer"
            continue
        if not txs:
            handled[acc] = "no_rows"
            continue
        cache.add_lines([_row(head, tx, acc, cik, tk, form, fdate, as_of, url, "site_fetch") for tx in txs])
        handled[acc] = "parsed"
    rep.update(requests=sec.sent, bytes=sec.bytes, blocked=sec.blocked, gaps=list(sec.gaps),
               stalled=getattr(sec, "stalled", None), paused=getattr(sec, "paused", None))
    cache.save()
    return cache, rep


# ============================================================ aggregates
def _money(x):
    a = abs(x)
    s = f"${a / 1e9:,.1f}B" if a >= 1e9 else f"${a / 1e6:,.1f}M" if a >= 1e6 else f"${a / 1e3:,.0f}K" if a >= 1e3 \
        else f"${a:,.0f}"
    return ("-" if x < 0 else "") + s


def _role(r):
    t = (r.get("officer_title") or "").strip()
    if t:
        return t
    if str(r.get("is_director")).lower() == "true":
        return "Director"
    if str(r.get("is_ten_pct")).lower() == "true":
        return "10% owner"
    return "Insider"


def aggregate(cache, ticker, now=None, rep=None):
    """-> dict for the page: status ok / partial / gap, as_of, per-window stats, detail lines."""
    now = now or _now()
    if ticker in NO_FORM4:
        return {"status": "gap", "why": NO_FORM4[ticker], "permanent": True}
    cik = UNIVERSE_CIK.get(ticker)
    if cik is None:
        return {"status": "gap", "why": "no SEC CIK on file for this ticker"}
    st = cache.state["issuers"].get(str(cik))
    if not st or not st.get("subm_at"):
        why = "SEC filing list not fetched yet (backfill pending)"
        if rep and rep.get("blocked"):
            why = f"SEC blocked this run ({rep['blocked']})"
        elif rep and (rep.get("stalled") or rep.get("paused")):
            why = f"SEC not asked this run ({rep.get('stalled') or rep.get('paused')})"
        return {"status": "gap", "why": why}
    subm_at = _ts(st["subm_at"])
    age_d = (now - subm_at).total_seconds() / 86400 if subm_at else 999
    rf = st.get("recent_from") or ""
    if not _filings(st) and rf and rf > (now - timedelta(days=365)).date().isoformat():
        # a filing list that starts within the last year and holds no Form 4 at all: the CIK on file is
        # probably a new registrant while insiders still file under an older CIK (XOM: 2115436 vs 34088).
        return {"status": "gap", "why": f"SEC list for CIK {cik} starts {rf} and holds no Form 4: CIK mapping "
                                        f"unverified (insiders may file under an older CIK)"}
    if age_d > GAP_DAYS:
        return {"status": "gap", "why": f"SEC filing list last refreshed {st['subm_at'][:10]} (> {GAP_DAYS} days)"}
    handled = cache.state["handled"]
    lines = cache.all_lines()
    lines = lines[lines["issuer_cik"].astype(str) == str(cik)]
    out = {"status": "ok", "as_of": st["subm_at"][:10], "stale": age_d > STALE_DAYS, "windows": {},
           "source": "SEC EDGAR Form 4 (non-derivative table)"}
    listed_from = _listed_from(st)
    for w in WINDOWS:
        lo = (now - timedelta(days=w)).date().isoformat()
        fl = [f for f in _filings(st) if f[1] >= lo]
        miss = [f for f in fl if f[0] not in handled]
        truncated = bool(listed_from and listed_from > lo)
        x = lines[(lines["filing_date"] >= lo) & (lines["tx_date"].str[:10] >= lo)]
        p = x[(x["code"] == "P") & (x["acq_disp"] == "A")]
        if len(p):
            p = p[~p["footnotes"].map(nonmarket_footnotes)]
        s = x[(x["code"] == "S") & (x["acq_disp"] == "D")]
        val = lambda d: float(pd.to_numeric(d["value_usd"], errors="coerce").fillna(0).sum())  # noqa: E731
        s_val = val(s)
        plan = s[s["aff10b5one"].str.lower().eq("true") | s["footnotes"].map(plan_footnote)]
        ins = pd.concat([p, s])
        roles = sorted({_role(r) for r in ins.to_dict("records") if NOTABLE.search(_role(r))
                        or _role(r) == "10% owner"})
        other = x[~x.index.isin(p.index) & ~x.index.isin(s.index)]
        out["windows"][w] = {
            "complete": not miss and not truncated, "list_truncated_from": listed_from if truncated else None,
            "n_filings": len(fl), "n_missing": len(miss),
            "n_buy_tx": len(p), "buy_usd": val(p), "n_buyers": int(p["owner_cik"].nunique()),
            "n_sell_tx": len(s), "sell_usd": s_val, "n_sellers": int(s["owner_cik"].nunique()),
            "net_usd": val(p) - s_val, "n_insiders": int(ins["owner_cik"].nunique()),
            "plan_share": (val(plan) / s_val) if s_val > 0 else None, "roles": roles,
            "n_other_lines": len(other)}
    w = out["windows"][max(WINDOWS)]
    x = lines[(lines["filing_date"] >= (now - timedelta(days=max(WINDOWS))).date().isoformat())]
    x = x[x["code"].isin(["P", "S"])].copy()
    x["v"] = pd.to_numeric(x["value_usd"], errors="coerce").fillna(0)
    det = []
    for r in x.sort_values("v", ascending=False).head(8).to_dict("records"):
        det.append({"tx_date": r["tx_date"][:10], "name": r["owner_name"] if SHOW_NAMES else None,
                    "role": _role(r), "side": "buy" if r["code"] == "P" else "sell",
                    "nonmarket": r["code"] == "P" and nonmarket_footnotes(r["footnotes"]),
                    "shares": _f(r["shares"]), "price": _f(r["price"]), "value": r["v"],
                    "plan": str(r["aff10b5one"]).lower() == "true" or plan_footnote(r["footnotes"]),
                    "url": r["url"]})
    out["detail"] = det
    if not out["windows"][90]["complete"]:
        out["status"] = "partial"
    return out


def status(cache_root=None):
    c = Cache(cache_root)
    now = _now()
    for tk in sorted(UNIVERSE_CIK):
        a = aggregate(c, tk, now)
        if a["status"] == "gap":
            print(f"{tk:6s} gap: {a['why']}")
            continue
        w90, w180 = a["windows"][90], a["windows"][180]
        print(f"{tk:6s} {a['status']:7s} as_of {a['as_of']} 90d {w90['n_filings'] - w90['n_missing']}/"
              f"{w90['n_filings']} 180d {w180['n_filings'] - w180['n_missing']}/{w180['n_filings']}")


def _blackout():
    """No live calls 16:00-17:30 or 18:45-21:15 America/Mexico_City (UTC-6, no DST since 2022)."""
    m = datetime.now(timezone.utc) - timedelta(hours=6)
    m = m.hour * 60 + m.minute
    return (16 * 60 <= m < 17 * 60 + 30) or (18 * 60 + 45 <= m < 21 * 60 + 15)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--max-xml", type=int, default=2000)
    ap.add_argument("--budget", type=int, default=2400)
    ap.add_argument("--max-seconds", type=int, default=1800, help="wall-clock cap of the SEC run")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    if a.backfill:
        if _blackout():
            print("inside a scheduled refresh window (16:00-17:30 / 18:45-21:15 CDMX): not run"); return 1
        _, rep = refresh(sorted(UNIVERSE_CIK), budget=a.budget, max_xml=a.max_xml, max_seconds=a.max_seconds)
        print(json.dumps({k: v for k, v in rep.items() if k != "gaps"}, default=str), f"gaps={len(rep['gaps'])}")
    if a.status or not a.backfill:
        status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
