# -*- coding: utf-8 -*-
"""Guard: EVERY visible date stamp on EVERY page is current for its own cadence.

Why (2026-09-30): portfolio.html's header said "As of <today>" while its Performance block
said "as of 2026-09-23" for a week, and the home card said "Book as of 2026-09-23". Every
check passed, because daily_refresh.ps1's live verify derived its page set from pages that
ALREADY carried today's stamp -- a page with a stale stamp was excluded by construction and
could never fail. A guard that selects its inputs by the property it is testing is a mirror.

So this reads every stamp (`As of`, `Performance as of`, `Book as of`, `Signals as of`,
`model as of`, `updated`, `built`, `priced`) out of the visible text, not a chosen subset,
and grades each against the cadence of what it describes:

  * default            -> the last completed US session (weekday; before 15:00 CDMX the
                          previous one), with 1 business day of slack for holidays
  * "model as of"      -> 10 calendar days (weekly rebuild, Sun 22:00; watchdog budget)
  * KNOWN_DEBT         -> hand-written surfaces carried at the decision gate; reported as
                          OWED every run, never silently passed, but do not fail the run
                          (a permanently red check gets muted -- that is how F8 hid)

Pages with NO stamp are listed, so "no stamp" can't masquerade as "fresh".
2026-09-30 (b): a current date stamp proved nothing about the NUMBERS under it -- portfolio.html
said "As of today" over six holdings still priced at 2026-09-23. So two CONTENT checks:
  * marks   -- portfolio.html's <meta name="ltcma-marks">: every held name marked, mark date current
  * frozen  -- each holding's published price vs the previous 3 published refreshes (git history
               of docs/portfolio.html): identical across 4 consecutive refresh days = FROZEN.
               Validated on the real history: flagged exactly AAPL CCJ COST GMEXICOB HD WMT.
Runs against the LIVE site by default (`--local` for docs/). Self-test first.
Exit 1 on any stale stamp.
"""
import os, re, sys, urllib.request
from datetime import date, datetime, timedelta

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
SITE = "https://duiarte.github.io/ltcma"
MON = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE = (rf"(\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}} (?:{MON})[a-z]* \d{{4}}|"
        rf"(?:{MON})[a-z]* \d{{1,2}},? \d{{4}})")
STAMP = re.compile(rf"(?i)([A-Za-z ]{{0,24}}?)\b(as of|updated|built|priced)\s*:?\s*{DATE}")
PAYLOAD = re.compile(r"(<script\b.*?</script>|<style\b.*?</style>)", re.S | re.I)
KNOWN_DEBT = {  # page -> why it is allowed to be old; must be cleared by a human
    "report.html": "hand-written report/LTCMA_2026.md; decision gate D-20260924-004 (TAB_RESYNC)",
}
# 2026-10-01: while report/LTCMA_2026.md lags the model, 17 publishes it as a dated,
# bannered edition under docs/archive/ and report.html redirects there. An archived page
# is honest by construction (it says it is old), but the resync is still OWED, so it is
# scanned and reported like KNOWN_DEBT -- moving the page must not make the debt vanish.
ARCHIVE_DEBT = "archived edition; republish via TAB_RESYNC (D-20260924-004)"
BUDGET_DAYS = [(re.compile(r"(?i)model"), 10),
               # ltcma-consensus.html is a MONTHLY edition (Market Intel, task market-intel-monthly,
               # day 1); 38 d = one month + a missed-run margin. MARKET_INTEL_SPEC.md 2/8.
               (re.compile(r"(?i)consensus"), 38)]


def _parse(s):
    for f in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def expected_session(now):
    d = now.date()
    if now.weekday() >= 5 or now.hour < 15:          # US close = 15:00 CDMX
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _bdays_between(a, b):
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def visible(html):
    t = re.sub(r"<[^>]+>", " ", PAYLOAD.sub(" ", html))
    t = t.replace("&middot;", "·").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t)


def check(pages, now):
    """pages: {name: html}. Returns (stale, owed, fresh, unstamped)."""
    exp = expected_session(now)
    stale, owed, fresh, unstamped = [], [], [], []
    for name, html in pages.items():
        found = [((m.group(1).strip() + " " + m.group(2)).strip(), m.group(3))
                 for m in STAMP.finditer(visible(html))]
        if not found:
            unstamped.append(name)
            continue
        for label, ds in found:
            d = _parse(ds.replace(",", ""))
            if d is None:
                continue
            budget = next((b for rx, b in BUDGET_DAYS if rx.search(label)), None)
            if budget is not None:
                ok = (now.date() - d).days <= budget
            else:
                ok = _bdays_between(d, exp) <= 1
            row = (name, label, ds)
            if ok:
                fresh.append(row)
            elif name in KNOWN_DEBT:
                owed.append(row + (KNOWN_DEBT[name],))
            elif name.startswith("archive/"):
                owed.append(row + (ARCHIVE_DEBT,))
            else:
                stale.append(row)
    return stale, owed, fresh, unstamped


_HROW = re.compile(r"<tr><td data-s='([^']+)'>.*?</td><td data-s='[^']*'>.*?</td>"
                   r"<td data-s='[^']*'>.*?</td><td data-s='([\d.]+)'>")
FROZEN_RUNS = 4          # today + 3 previous published refreshes, all identical


def holdings_prices(html):
    m = re.search(r'<table[^>]*id="h-table".*?</table>', html, re.S)
    return dict(_HROW.findall(m.group(0))) if m else {}


def check_marks(html, now):
    """portfolio.html's machine-readable mark coverage. Returns problems."""
    m = re.search(r'<meta name="ltcma-marks" content="([^"]*)"', html)
    if not m:
        return ["portfolio.html: no ltcma-marks meta -- mark coverage unprovable"]
    kv = dict(x.split("=", 1) for x in m.group(1).split(";") if "=" in x)
    out = []
    if kv.get("stale"):
        out.append(f"portfolio.html: holdings NOT re-marked today: {kv['stale']}")
    if kv.get("marked") != kv.get("held"):
        out.append(f"portfolio.html: marked {kv.get('marked')}/{kv.get('held')} holdings")
    d = _parse(kv.get("asof", ""))
    if d is None or _bdays_between(d, expected_session(now)) > 1:
        out.append(f"portfolio.html: marks as of {kv.get('asof')}")
    return out


def check_frozen(today_html, history):
    """history: list of previous published portfolio.html, newest first, one per refresh
    day. A price identical in today + (FROZEN_RUNS-1) previous refreshes is frozen."""
    cur = holdings_prices(today_html)
    prev = [holdings_prices(h) for h in history[:FROZEN_RUNS - 1]]
    if len(prev) < FROZEN_RUNS - 1:
        return []
    return [f"portfolio.html: {t} price {p} unchanged across {FROZEN_RUNS} refreshes"
            for t, p in sorted(cur.items()) if all(h.get(t) == p for h in prev)]


def published_history(n, before):
    """Previous daily-refresh versions of docs/portfolio.html from git, newest first,
    at most one per calendar day (a same-day re-run must not count as a new day)."""
    import subprocess
    root = os.path.dirname(DOCS)
    log = subprocess.run(["git", "-C", root, "log", "--format=%h %cs %s", "-n", "60", "--",
                          "docs/portfolio.html"], capture_output=True, text=True).stdout
    out, days = [], set()
    for line in log.splitlines():
        h, d = line.split()[:2]
        if "daily website refresh" not in line or d in days or d >= before:
            continue                     # one per day, and never today's (= the live page)
        days.add(d)
        out.append(subprocess.run(["git", "-C", root, "show", f"{h}:docs/portfolio.html"],
                                  capture_output=True, text=True, encoding="utf-8").stdout)
        if len(out) >= n:
            break
    return out


def _selftest():
    now = datetime(2026, 9, 30, 17, 0)
    pages = {
        "a.html": "<p>As of 2026-09-30</p><p>Performance as of 2026-09-23</p>",
        "b.html": "<p class=asof>As of 29 Sep 2026</p>",               # 1 bday slack
        "c.html": "<p>LTCMA model as of 27 Sep 2026</p>",              # weekly budget
        "d.html": "<p>no stamp here</p>",
        "report.html": "<p>As of 11 August 2026</p>",
        "e.html": "<script>var x='As of 2020-01-01'</script><p>As of 2026-09-30</p>",
        "archive/report_2026-08-11.html": "<p>As of 11 August 2026</p>",
    }
    stale, owed, fresh, un = check(pages, now)
    assert [s[:2] for s in stale] == [("a.html", "Performance as of")], stale
    assert [o[0] for o in owed] == ["report.html", "archive/report_2026-08-11.html"], owed
    assert "d.html" in un and len(fresh) == 4, (fresh, un)
    row = lambda t, p: (f"<tr><td data-s='{t}'>{t}</td><td data-s='1'>1</td>"
                        f"<td data-s='1'>1</td><td data-s='{p}'>x</td></tr>")
    tbl = lambda *r: '<table class="ptable" id="h-table">' + "".join(r) + "</table>"
    hist = [tbl(row("AAPL", "5875.01"), row("QQQ", str(13000 + i))) for i in range(3)]
    fz = check_frozen(tbl(row("AAPL", "5875.01"), row("QQQ", "13400")), hist)
    assert len(fz) == 1 and "AAPL" in fz[0], fz
    assert check_marks('<meta name="ltcma-marks" content="asof=2026-09-30;marked=21;'
                       'held=21;stale=">', now) == []
    bad = check_marks('<meta name="ltcma-marks" content="asof=2026-09-23;marked=15;'
                      'held=21;stale=AAPL,HD">', now)
    assert len(bad) == 3, bad
    assert check_marks("<p>no meta</p>", now), "missing meta must fail"


def main():
    _selftest()
    local = "--local" in sys.argv
    names = sorted(f for f in os.listdir(DOCS) if f.endswith(".html"))
    _ad = os.path.join(DOCS, "archive")
    if os.path.isdir(_ad):
        names += sorted(f"archive/{f}" for f in os.listdir(_ad) if f.endswith(".html"))
    pages, unreachable = {}, []
    for n in names:
        try:
            if local:
                pages[n] = open(os.path.join(DOCS, n), encoding="utf-8", errors="replace").read()
            else:
                req = urllib.request.Request(f"{SITE}/{n}?fresh={datetime.now():%H%M%S}",
                                             headers={"Cache-Control": "no-cache"})
                pages[n] = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
        except Exception as e:
            unreachable.append(f"{n}: {e}")
    now = datetime.now()
    stale, owed, fresh, un = check(pages, now)
    content = []
    if "portfolio.html" in pages:
        content = check_marks(pages["portfolio.html"], now)
        content += check_frozen(pages["portfolio.html"], published_history(FROZEN_RUNS - 1,
                                                                      now.strftime("%Y-%m-%d")))
    src = "docs/ (local)" if local else SITE
    print(f"FRESHNESS GUARD -- {src} -- expected session {expected_session(now)} -- "
          f"{len(pages)} pages, {len(fresh)} fresh stamps")
    for r in owed:
        print(f"  OWED   {r[0]:28s} {r[1]} {r[2]}  ({r[3]})")
    for n in un:
        print(f"  nostamp {n}")
    for u in unreachable:
        print(f"  UNREACHABLE {u}")
    for r in stale:
        print(f"  ** STALE ** {r[0]:24s} {r[1]} {r[2]}")
    for c in content:
        print(f"  ** STALE NUMBERS ** {c}")
    if stale or unreachable or content:
        print(f"\n{len(stale)} stale stamp(s), {len(content)} stale-number finding(s), "
              f"{len(unreachable)} unreachable page(s)")
        return 1
    print("\nOK: every stamp current for its cadence; every holding re-marked; "
          "no price frozen across %d refreshes" % FROZEN_RUNS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
