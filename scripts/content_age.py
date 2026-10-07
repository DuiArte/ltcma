# -*- coding: utf-8 -*-
"""Content age: how old is what a page SAYS -- not when it was built.

Every tab re-renders daily and carries today's "As of" stamp, so the commit age (what pipeline v2
layer 7 graded until 2026-10-07) and the header stamp (what guard_freshness.py grades) both read
"current" over content that is not. Measured the day this was written: research.html said
"As of 06 Oct 2026" above a batch record whose newest row was June 2026; every project repo was
last pushed in June; three of four public backtests end in May and nothing extends them. Carlos
spotted it by eye. This module is the check that would have.

OWNERSHIP -- one manifest, one engine:
  * The SLAs live in Trading_Index\\pipeline\\content\\refresh_manifest.json: each surface may
    carry a `content_rule` naming an extractor below plus `amber_days` / `red_days`.
  * Pipeline v2 layer 7 (Scripts\\pipeline_v2\\layer7_content_refresh.py) calls evaluate() for
    every rule, grades, persists state (regime-change detection), and raises WEBSITE_ALERT.txt.
  * scripts/34_site_freshness.py renders layer 7's verdict as docs/internal/freshness.html.
  This module only MEASURES. It is read-only against the repo and never publishes.

Contract: evaluate(repo, rule, today) -> {
    "content_asof": "YYYY-MM-DD" | None,  # newest dated content the extractor could find
    "age_days": int | None,
    "grade": GREEN | AMBER | RED | INFO,
    "findings": [[grade, text], ...],     # PUBLIC-SAFE: rendered on the internal page
    "facts": {...}}                       # machine-readable extras (regime label, lists)
Public-safe means: no host paths, no private figures, tickers only where the public site already
shows them (the Holdings table on portfolio.html does).
"""
import glob
import json
import os
import re
import urllib.request
from datetime import date, datetime

GREEN, AMBER, RED, INFO = "GREEN", "AMBER", "RED", "INFO"
_ORDER = {RED: 0, AMBER: 1, GREEN: 2, INFO: 3}
_MON = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


# ---------------------------------------------------------------- helpers
def worst(*grades):
    gs = [g for g in grades if g]
    return min(gs, key=lambda g: _ORDER.get(g, 9)) if gs else GREEN


def _read(repo, rel):
    with open(os.path.join(repo, rel), encoding="utf-8", errors="ignore") as f:
        return f.read()


def _visible(html):
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def _meta(html, name):
    m = re.search(r'<meta\s+name="%s"\s+content="([^"]*)"' % re.escape(name), html)
    return m.group(1) if m else None


def _d(s):
    if not s:
        return None
    s = str(s)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _age(today, d):
    return None if d is None else (today - d).days


def _grade_age(age, amber, red):
    if age is None:
        return AMBER
    if red is not None and age > red:
        return RED
    if amber is not None and age > amber:
        return AMBER
    return GREEN


def _result(asof, today, grade, findings, facts=None):
    return {"content_asof": asof.isoformat() if asof else None, "age_days": _age(today, asof),
            "grade": grade, "findings": findings, "facts": facts or {}}


def _sla_text(age, amber, red):
    return "%s old (SLA: amber after %s, red after %s days)" % (
        "age unknown" if age is None else ("1 day" if age == 1 else "%d days" % age), amber, red)


# ---------------------------------------------------------------- extractors
def ex_meta_asof(repo, rule, today):
    """Pages whose generator stamps <meta name="ltcma-content-asof"> with its newest CONTENT date
    (research.html: the automated pipeline's last verdict, else the last curated batch month).
    `check_funnel`: the funnel tiles must equal what the page itself lists -- the "~181 signals"
    tile could not be reproduced from the page for four months."""
    html = _read(repo, rule["file"])
    asof = _d(_meta(html, "ltcma-content-asof"))
    a, r = rule.get("amber_days"), rule.get("red_days")
    age = _age(today, asof)
    if asof is None:
        return _result(None, today, AMBER, [[AMBER, "page carries no ltcma-content-asof meta - "
                                                     "its generator stopped stamping content age"]])
    g = _grade_age(age, a, r)
    out = [[g, "newest content %s: %s" % (asof.isoformat(), _sla_text(age, a, r))]]
    if rule.get("check_funnel"):
        sec = html[html.find('id="batches"'):]
        sec = sec[:sec.find("</table>")]
        n_rows = len(re.findall(r"<tr><td>", sec))
        tiles = re.findall(r'<div class="mv">([^<]+)</div><div class="mk">([^<]+)</div>',
                           html[html.find('id="funnel"'):html.find('id="batches"')])
        n_cards = len(re.findall(r'<article id="f\d+"', html))
        tile = {k.split()[0].lower(): v.strip() for v, k in tiles}
        bad = []
        if tile.get("discovery") and tile["discovery"] != str(n_rows):
            bad.append("batch tile %s vs %d rows" % (tile["discovery"], n_rows))
        if tile.get("load-bearing") and tile["load-bearing"] != str(n_cards):
            bad.append("findings tile %s vs %d cards" % (tile["load-bearing"], n_cards))
        if bad:
            out.append([RED, "funnel tiles disagree with the page: " + "; ".join(bad)])
            g = RED
        else:
            out.append([GREEN, "funnel tiles reconcile to the page (%d batches, %d findings)"
                        % (n_rows, n_cards)])
    return _result(asof, today, g, out)


def ex_regex_date(repo, rule, today):
    """A dated phrase inside the content (not the header stamp), e.g. "Performance as of".
    Takes the OLDEST match across `files` -- one stale card must not hide behind a fresh one."""
    pat = re.compile(rule["pattern"])
    dates, missing = [], []
    for rel in rule.get("files") or [rule["file"]]:
        m = pat.search(_visible(_read(repo, rel)))
        d = _d(m.group(1)) if m else None
        (dates.append(d) if d else missing.append(os.path.basename(rel)))
    a, r = rule.get("amber_days"), rule.get("red_days")
    if not dates:
        return _result(None, today, AMBER, [[AMBER, "content date not found (%s) - the page changed "
                                                     "shape" % rule.get("label", rule["pattern"])]])
    asof = min(dates)
    g = _grade_age(_age(today, asof), a, r)
    out = [[g, "%s %s: %s" % (rule.get("label", "content as of"), asof.isoformat(),
                              _sla_text(_age(today, asof), a, r))]]
    if missing:
        out.append([AMBER, "no content date on: " + ", ".join(missing)])
        g = worst(g, AMBER)
    return _result(asof, today, g, out)


def _held_tickers(repo):
    """Tickers in the PUBLIC Holdings table of portfolio.html (already on the site)."""
    html = _read(repo, "docs/portfolio.html")
    i = html.find('id="h-body"')
    if i < 0:
        return None
    tb = html[i:html.find("</tbody>", i)]
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if cells:
            t = re.sub(r"<[^>]+>|&[a-z]+;", " ", cells[0]).split()
            if t:
                out.append(t[0].upper())
    return out


def ex_stock_pages(repo, rule, today):
    """Per-name research pages: each page's own price date, plus the portfolio linkage.
    The analysis on these pages is recomputed from Yahoo on every build (price, consensus,
    valuation), so there is no hand-written thesis to go stale; the date that can go stale is the
    price date the page prints. Linkage is REPORTED, never acted on: the page set is a research
    watchlist (19_stock_analysis.DEFAULT); adding or archiving names is Carlos's call."""
    a, r = rule.get("amber_days"), rule.get("red_days")
    pages = sorted(glob.glob(os.path.join(repo, "docs", "stock_*.html")))
    per, out, g = {}, [], GREEN
    for p in pages:
        tk = os.path.basename(p)[6:-5].upper()
        m = re.search(r"As of (\d{4}-\d{2}-\d{2})", _visible(_read(repo, os.path.relpath(p, repo))))
        per[tk] = _d(m.group(1)) if m else None
    stale = {t: d for t, d in per.items() if _grade_age(_age(today, d), a, r) != GREEN}
    for t, d in sorted(stale.items()):
        gg = _grade_age(_age(today, d), a, r)
        out.append([gg, "%s priced %s: %s" % (t, d or "?", _sla_text(_age(today, d), a, r))])
        g = worst(g, gg)
    dated = [d for d in per.values() if d]
    asof = min(dated) if dated else None
    if not stale and per:
        out.append([GREEN, "%d pages, oldest price date %s" % (len(per), asof)])
    facts = {"pages": sorted(per)}
    held = _held_tickers(repo)
    if held is not None:
        funds = {x.upper() for x in rule.get("not_single_stocks", [])}
        single = [t for t in held if t not in funds]
        no_page = [t for t in single if t not in per]
        not_held = [t for t in per if t not in held]
        facts.update(held_single=single, held_without_page=no_page, page_not_held=not_held)
        if no_page:
            out.append([AMBER, "held without a research page (%d): %s"
                        % (len(no_page), ", ".join(no_page))])
            g = worst(g, AMBER)
        if not_held:
            out.append([INFO, "research page for a name not held (%d): %s - archive or keep is "
                              "a coverage decision" % (len(not_held), ", ".join(not_held))])
    return _result(asof, today, g, out, facts)


def ex_regime(repo, rule, today):
    """Regime tracker: the newest daily INPUT (the composite is monthly, so "<5 days" is a
    statement about its inputs) plus the current regime label, which layer 7 compares with its
    previous run to raise a regime-change alert."""
    a, r = rule.get("amber_days"), rule.get("red_days")
    html = _read(repo, rule["file"])
    label = None
    try:      # the ONE writer of the regime (20_regime_tracker.py); the home tile reads it too
        label = json.load(open(os.path.join(repo, rule["state_file"]), encoding="utf-8"))["state"]
    except (OSError, ValueError, KeyError):
        m = re.search(r"\b([A-Z][A-Z-]{3,})\s+Current Regime", _visible(html))
        label = m.group(1) if m else None
    inp = None
    path = os.path.join(repo, rule["inputs"])
    try:
        with open(path, encoding="utf-8") as f:
            last = None
            for line in f:
                last = line
        inp = _d(last.split(",")[0]) if last else None
    except OSError:
        pass
    g = _grade_age(_age(today, inp), a, r)
    out = [[g, "newest regime input %s: %s" % (inp or "?", _sla_text(_age(today, inp), a, r))]]
    m = re.search(r"monthly composite through (\w+ \d{4})", _visible(html))
    if m:
        comp = datetime.strptime("1 " + m.group(1), "%d %b %Y").date()
        lag = (today.year - comp.year) * 12 + today.month - comp.month
        if lag > 1:
            out.append([RED, "monthly composite stuck at %s (%d months behind)" % (m.group(1), lag)])
            g = RED
        else:
            out.append([GREEN, "monthly composite through %s" % m.group(1)])
    if label:
        out.append([INFO, "current regime: %s" % label.upper()])
    else:
        out.append([AMBER, "current regime label not found on the page"])
        g = worst(g, AMBER)
    return _result(inp, today, g, out, {"regime": (label or "").upper() or None})


def _gh_pushed(handle, timeout=10):
    req = urllib.request.Request("https://api.github.com/repos/" + handle,
                                 headers={"User-Agent": "ltcma-content-age",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        d = json.load(resp)
    return _d(d.get("pushed_at")), bool(d.get("archived"))


def ex_github_projects(repo, rule, today):
    """Projects tab: each card links a public GitHub repo; the repo's last push IS the project's
    last update (the page had no date at all until 2026-10-07). "Coming soon" cards are skipped;
    an active card past `red_days` is RED -- Carlos: >6 months untouched while listed active."""
    a, r = rule.get("amber_days"), rule.get("red_days")
    html = _read(repo, rule["file"])
    cards = re.findall(r'<a class="(proj-card[^"]*)" href="https://github\.com/([^"/]+/[^"/]+)"', html)
    out, g, per = [], GREEN, {}
    for klass, handle in cards:
        if "proj-soon" in klass:
            continue
        try:
            pushed, archived = _gh_pushed(handle)
        except Exception as e:                       # network is not the project's fault
            out.append([AMBER, "%s: GitHub unreachable (%s)" % (handle, type(e).__name__)])
            g = worst(g, AMBER)
            continue
        per[handle] = pushed.isoformat() if pushed else None
        gg = _grade_age(_age(today, pushed), a, r)
        if archived:
            gg = worst(gg, AMBER)
        out.append([gg, "%s last pushed %s (%s days ago)%s" % (
            handle, pushed or "?", _age(today, pushed), " - archived on GitHub" if archived else "")])
        g = worst(g, gg)
    if not cards:
        return _result(None, today, AMBER, [[AMBER, "no project cards found on the page"]])
    shown = len(re.findall(r'class="proj-updated"', html))
    if shown < len(per):
        out.append([AMBER, "page shows a last-updated date on %d of %d active cards" % (shown, len(per))])
        g = worst(g, AMBER)
    dated = [_d(v) for v in per.values() if v]
    newest = max(dated) if dated else None
    return _result(newest, today, g, out, {"pushed": per})


def ex_backtests(repo, rule, today):
    """Public backtests end where their data ends. A window is "live" only if something carries
    it forward to today; until then its age is the gap between the backtest and the present.
    `live` maps a strategy key to the paper-track series that extends it."""
    a, r = rule.get("amber_days"), rule.get("red_days")
    S = json.load(open(os.path.join(repo, "data", "backtests_strategies.json"), encoding="utf-8"))
    live = rule.get("live") or {}
    out, g, ends = [], GREEN, []
    for s in S["strategies"]:
        if s.get("public") not in (True, "True"):
            continue
        span = str((s.get("dates") or {}).get("data_span") or "")
        m = re.search(r"(\d{4}-\d{2}-\d{2})\s*$", span)
        end = _d(m.group(1)) if m else None
        name = s.get("short_name") or s["key"]
        if s["key"] in live:
            src = live[s["key"]]
            try:
                pt = json.load(open(os.path.join(repo, src["file"]), encoding="utf-8"))
                last = _d(pt[src.get("series", "series")][-1]["date"])
            except (OSError, ValueError, KeyError, IndexError):
                last = None
            gg = _grade_age(_age(today, last), src.get("amber_days", 5), src.get("red_days", 10))
            out.append([gg, "%s: backtest to %s, carried live by the paper-track to %s"
                        % (name, end or "?", last or "?")])
            ends.append(last)
        else:
            gg = _grade_age(_age(today, end), a, r)
            out.append([gg, "%s: backtest ends %s, not extended live (%s days behind)"
                        % (name, end or "?", _age(today, end))])
            ends.append(end)
        g = worst(g, gg)
    dated = [e for e in ends if e]
    return _result(min(dated) if dated else None, today, g, out)


def ex_report(repo, rule, today):
    """The full report is the one hand-written surface. While it lags the model it is published
    as a dated archived edition (report.html redirects there) -- honest, but still a debt."""
    a, r = rule.get("amber_days"), rule.get("red_days")
    html = _read(repo, rule["file"])
    m = re.search(r"archive/report_(\d{4}-\d{2}-\d{2})\.html", html)
    if not m:
        return _result(None, today, INFO, [[INFO, "report served live (no archived edition)"]])
    ed = _d(m.group(1))
    exists = os.path.exists(os.path.join(repo, "docs", "archive", "report_%s.html" % ed))
    g = _grade_age(_age(today, ed), a, r)
    out = [[g, "published as the archived edition of %s: %s" % (ed, _sla_text(_age(today, ed), a, r))]]
    if not exists:
        out.append([RED, "report.html redirects to an archived edition that is not in docs/"])
        g = RED
    return _result(ed, today, g, out)


def ex_json_date(repo, rule, today):
    """A date inside a data file the page is rendered from (e.g. the EMBER paper-track's
    `asof`): the page can only be as current as the series under it."""
    a, r = rule.get("amber_days"), rule.get("red_days")
    try:
        d = json.load(open(os.path.join(repo, rule["file"]), encoding="utf-8"))
        for k in rule["key"].split("."):
            d = d[int(k)] if k.lstrip("-").isdigit() else d[k]
        asof = _d(d)
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        asof = None
    if asof is None:
        return _result(None, today, AMBER, [[AMBER, "%s: date not readable" % rule.get("label", rule["file"])]])
    g = _grade_age(_age(today, asof), a, r)
    return _result(asof, today, g, [[g, "%s %s: %s" % (rule.get("label", "data as of"), asof,
                                                        _sla_text(_age(today, asof), a, r))]])


EXTRACTORS = {"meta_asof": ex_meta_asof, "regex_date": ex_regex_date, "json_date": ex_json_date,
              "stock_pages": ex_stock_pages, "regime": ex_regime,
              "github_projects": ex_github_projects, "backtests": ex_backtests,
              "report": ex_report}


def evaluate(repo, rule, today=None):
    today = today or date.today()
    fn = EXTRACTORS.get(rule.get("extractor"))
    if fn is None:
        return _result(None, today, AMBER, [[AMBER, "unknown extractor %r" % rule.get("extractor")]])
    try:
        return fn(str(repo), rule, today)
    except Exception as e:                            # a broken extractor is a finding, not a crash
        return _result(None, today, AMBER, [[AMBER, "extractor %s failed: %s: %s"
                                             % (rule.get("extractor"), type(e).__name__, str(e)[:120])]])
