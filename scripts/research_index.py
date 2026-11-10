"""Research Library index + Sources registry (2026-11-10 remake; Carlos: "pon la parte de research en un
rincon que se pueda explorar mejor. El fundamento de todo esto, las fuentes").

Pure functions over what the EXISTING research pages are built from -- never a hand-typed list of items
(WEBSITE_AGENT_RULES 5, "hand-typed tiles drift"):
  * Research Notes  : FINDINGS + BATCHES, read as literals from scripts/27_research_notes.py (ast, not run)
  * Strategies      : the backtest catalog (glossary.bt_catalog), with 23's status labels and the same
                      confidentiality filter (glossary._bt_public / _bt_redact); public entries link their
                      bt_<key>.html report (emitted by 24), the rest the catalogue section on strategies.html
  * Projects        : PROJECTS literal from scripts/17_build_site.py (+ the "Last push" dates projects.html shows)
  * Stock research  : DEFAULT watchlist literal from scripts/19_stock_analysis.py (the stock_<T>.html pages)
  * Full Report     : the "## " sections of report/LTCMA_2026.md (ids = python-markdown's toc slugify, as 17 renders)
  * Page sections   : <section class="block" id=...><h2> of each research page AS RENDERED in docs/
Private ledgers stay COUNTS ONLY (data/research_tally.json is the public, counts-only tally).

SOURCES: every external data source / publisher that feeds a PUBLIC page. Each entry carries `evidence` =
(public file, regex) pairs that must match in a PUBLIC generator or public data file of this repo; an entry
whose evidence does not hold is left off the page (and ds_gate fails). Private inputs (broker records, private
projects and their data) are never listed, and no credential or private URL is printed.

Round 1 (2026-11-10 review): summaries never show a redaction placeholder ("[assets]" ...: the clause or
sentence that carries one is dropped) or a market-data vendor's name; a backtest's summary leads with its
catalogue badge and the sentence that states the result, and a research / archived one must read as negative
(check_items); the batch record is read whatever its deployable count and reconciled with the table; the
research pages come from glossary.RESEARCH_LINKS + glossary.SUBPAGES, not a fixed list.
"""
import ast
import html as _html
import json
import os
import re
from datetime import date, datetime

from paths import DATA, DOCS, REPORT, ROOT

SCRIPTS = os.path.join(str(ROOT), "scripts")
TOPICS = [  # (label, regex over title + summary): keyword tags, shown as such on the page
    ("Equities", r"\b(equit\w*|stocks?|S&(?:amp;)?P|index[- ]ETF|sector|earnings|CAPE|valuation|share)"),
    ("Rates & bonds", r"\b(bonds?|treasur\w*|yields?|rates?|duration|credit|term[- ]premium|TIPS|govt)\b"),
    ("FX", r"\b(FX|currenc\w*|peso|dollar|carry)\b"),
    ("Gold & commodities", r"\b(gold|metals?|commodit\w*|oil|silver|precious)\b"),
    ("Volatility & options", r"\b(volatil\w*|options?|VIX|variance)\b"),
    ("Crypto", r"\bcrypto\w*"),
    ("Macro & regimes", r"\b(macro\w*|Fed|FOMC|inflation|CPI|payrolls?|regimes?|recession|monetary)\b"),
    ("Multi-asset", r"\b(multi-asset|diversif\w*|allocation|portfolios?|blend|sleeves?|ensemble)\b"),
    ("Method", r"\b(protocol|overfit\w*|walk-forward|survivorship|Sharpe|bias|costs?|robust\w*|gates?|benchmark)\b"),
]
TYPE_ORDER = ["Report section", "Finding", "Research batch", "Backtest", "Project", "Stock page", "Page section", "Page"]


# ------------------------------------------------------------------------------------------- helpers
def literal(script, name):
    """A module-level literal (list / tuple / dict of str / numbers) read from a script WITHOUT running it."""
    with open(os.path.join(SCRIPTS, script), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {script}")


def text(s):
    """HTML snippet -> plain text."""
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", str(s or ""))).split())


_ABBR = re.compile(r"(?:\b[A-Z]\.){1,3}$|\b(?:vs|e\.g|i\.e|Inc|Co|Corp|Ltd|St|No|approx|incl)\.$")


def sentences(s):
    """Sentences, not cut at an abbreviation ("J.P. Morgan", "U.S.", "vs.")."""
    t = text(s)
    out = []
    for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", t):
        if out and _ABBR.search(out[-1]):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return [x for x in out if x.strip()]


def _cut(t, n):
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


def first_sentence(s, n=220):
    """The first sentence, not cut at an abbreviation ("J.P. Morgan", "U.S.", "vs.")."""
    ss = sentences(s)
    return _cut(ss[0] if ss else text(s), n)


# a redaction placeholder left by glossary._bt_redact ("[assets]", "[trend filter]" ...) and market-data vendors:
# neither belongs in a summary (HON-1). The page they come from keeps its own wording.
_MARK = re.compile(r"\[[a-z][a-z ]*\]")
_VENDOR = re.compile(r"\s*\b(?:Dukascopy|FxPro|MetaTrader\s?\d?)\b", re.I)


def clean(s):
    """Text without vendor names and without the parenthetical / dash clause / sentence carrying a placeholder."""
    t = _VENDOR.sub("", text(s))
    t = re.sub(r"\s*\([^()]*\[[a-z][a-z ]*\][^()]*\)", "", t)
    keep = []
    for sen in sentences(t):
        if _MARK.search(sen):
            parts = [c for c in re.split(r"\s+[—–]\s+", sen) if not _MARK.search(c)]
            if not parts:
                continue
            sen = " — ".join(parts)
            sen = sen[:1].upper() + sen[1:]
            if sen[-1] not in ".!?…":
                sen += "."
        keep.append(sen)
    return re.sub(r"\s{2,}", " ", " ".join(keep)).replace(" ,", ",").strip()


def brief(s, n=220):
    """A summary: redacted like the research pages, cleaned, first sentence."""
    from glossary import _bt_redact
    return first_sentence(clean(_bt_redact(text(s))), n)


def topics(*parts):
    blob = " ".join(text(p) for p in parts)
    return [lab for lab, rx in TOPICS if re.search(rx, blob, re.I)]


def _read(rel):
    p = os.path.join(str(DOCS), rel)
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _iso(d):
    try:
        return date.fromisoformat(str(d)[:10]).isoformat()
    except (TypeError, ValueError):
        return ""


def nice(iso):
    return date.fromisoformat(iso).strftime("%d %b %Y") if iso else ""


def report_target():
    """report.html, or the archived edition it redirects to (17: D-20260924-004)."""
    r = _read("report.html") or ""
    m = re.search(r'http-equiv="refresh" content="0; url=([^"]+)"', r)
    return m.group(1) if m else "report.html"


def report_edition():
    try:
        md = open(os.path.join(str(REPORT), "LTCMA_2026.md"), encoding="utf-8").read()
    except OSError:
        return ""
    m = re.search(r"Model as-of date:\**\s*(\d{1,2} [A-Z][a-z]+ \d{4})", md)
    try:
        return datetime.strptime(m.group(1), "%d %B %Y").date().isoformat() if m else ""
    except ValueError:
        return ""


def _item(**k):
    # the research pages' own confidentiality backstop (glossary._bt_redact: ticker runs, parameters, internal
    # names) on every title and summary, so the library is held to the same rule as research / strategies, which
    # confscan.sh scans; it is applied before the topic tags are read. Then clean(): no placeholder, no vendor.
    from glossary import _bt_redact
    k["title"] = _VENDOR.sub("", text(_bt_redact(k.get("title", ""))))
    k["summary"] = clean(_bt_redact(text(k.get("summary", ""))))
    k.setdefault("outcome", "")
    k.setdefault("date", "")
    k.setdefault("date_label", nice(k["date"]) if k.get("date") else "")
    k.setdefault("topics", topics(k.get("title", ""), k.get("summary", "")))
    k.setdefault("external", "")
    return k


# ------------------------------------------------------------------------------------------- items
def report_items():
    from markdown.extensions.toc import slugify
    try:
        md = open(os.path.join(str(REPORT), "LTCMA_2026.md"), encoding="utf-8").read()
    except OSError:
        return []
    tgt, ed = report_target(), report_edition()
    out = []
    parts = re.split(r"(?m)^## ", md)[1:]
    for p in parts:
        head, _, body = p.partition("\n")
        head = head.strip()
        para = next((x for x in re.split(r"\n\s*\n", body)
                     if x.strip() and not x.lstrip().startswith(("#", "|", "!", "```", "-", "*", ">"))
                     and not re.match(r"\s*\d+[.)]\s", x)), "")
        para = re.sub(r"[*_`]", "", para)
        out.append(_item(id="report-" + slugify(head, "-"), type="Report section", title=head,
                         summary=brief(para), date=ed, page="Full Report",
                         href=f"{tgt}#{slugify(head, '-')}"))
    return out


def finding_items():
    from glossary import _bt_redact
    lab = {"closed": "Axis closed", "method": "Protocol rule", "positive": "Positive result"}
    out = []
    for num, tag, d, title, body in literal("27_research_notes.py", "FINDINGS"):
        out.append(_item(id="finding-" + num.strip("#"), type="Finding", title=f"{num} {_bt_redact(title)}",
                         summary=brief(body), outcome=lab.get(tag, tag), date=_iso(d),
                         page="Research Notes", href=f"research.html#f{num.strip('#')}"))
    return out


# one batch row as 27 renders it; the deployable cell is read whatever its value or class (HON-5: a batch with a
# deployable result must not vanish from the library), and the rows are reconciled with the table (check_items)
_BROW = re.compile(r'<tr><td>([^<]+)</td><td>([^<]+)</td><td class="ax">(.*?)</td><td>([^<]*)</td>'
                   r'<td(?: class="[^"]*")?[^>]*>(\d+)</td><td class="ax">(.*?)</td></tr>', re.S)


def batch_table_rows(rs):
    """The number of rows in research.html's #batches table (whatever their content)."""
    sec = rs[rs.find('id="batches"'):] if 'id="batches"' in rs else ""
    sec = sec[:sec.find("</table>")] if "</table>" in sec else ""
    body = sec[sec.find("<tbody>"):] if "<tbody>" in sec else sec[sec.find("</thead>"):]
    return len(re.findall(r"<tr>", body))


def _month(label):
    """'Jun 2026' -> 2026-06-01; a range 'Sep–Nov 2026' (the automated pipeline's row) -> its LAST month."""
    t = text(label).replace("&ndash;", "–")
    m = re.search(r"([A-Z][a-z]{2})\s*(\d{4})\s*$", t)
    try:
        return datetime.strptime(f"1 {m.group(1)} {m.group(2)}", "%d %b %Y").date().isoformat() if m else ""
    except ValueError:
        return ""


def batch_items():
    """The batch record AS PUBLISHED on research.html (27 adds the automated pipeline's row, computed from its
    verdicts, to the BATCHES literal); the literal is the fallback when the page is not there."""
    from glossary import _bt_redact
    out = []
    rs = _read("research.html") or ""
    sec = rs[rs.find('id="batches"'):]
    sec = sec[:sec.find("</table>")]
    rows = [tuple(text(x) for x in r) for r in _BROW.findall(sec)]
    if not rows:
        rows = [(c, m, a, t, "0", o) for c, m, a, t, o in literal("27_research_notes.py", "BATCHES")]
    for code, month, axis, trials, ndep, outcome in rows:
        iso = _month(month)
        tri = f" ({trials} trials)" if str(trials).strip() not in ("", "—", "-") else ""
        nd = int(ndep) if str(ndep).isdigit() else 0
        out.append(_item(id="batch-" + re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-"), type="Research batch",
                         title=f"{code}: {_bt_redact(axis)}", summary=brief(outcome) + tri,
                         outcome="Negative (0 deployable)" if nd == 0 else f"{nd} deployable", date=iso,
                         date_label=month, page="Research Notes", href="research.html#batches"))
    return out


def _status(s):
    """23_strategies._status, same labels (the catalogue card's pill)."""
    if s.get("badge") == "green":
        return "Deployed · GFC-tested" if s.get("gfc_test_passed") else "Deployable"
    if s.get("badge") == "yellow":
        return "Research · ensemble"
    return "Failed / archived"


# the sentence that states the result: for a research / archived entry the strongest negative first, for a
# deployable one the sentence with its metrics (HON-1: "PASS on rotation ..." alone read as a pass)
NEG1 = re.compile(r"\b(FAIL\w*|NOT DEPLOY\w*|DO NOT|nothing|none|no edge|not real|harm\w*|collaps\w*|inverted|"
                  r"overfit\w*|demot\w*|dead|mirage|kills?)\b", re.I)
NEG2 = re.compile(r"\b(never|thin|hurts?|negative|below|decay\w*|standalone-fail|not)\b", re.I)
RESULT = re.compile(r"\b(Sharpe|CAGR|Calmar|DSR|PBO|drawdown|MaxDD|MDD)\b", re.I)


def bt_summary(status, badge, verdict):
    """'<catalogue badge>. <the sentence that states the result>' -- the card's own words, cleaned."""
    ss = sentences(clean(verdict))
    order = (NEG1, NEG2, RESULT) if status != "deployed" else (RESULT,)
    key = next((x for rx in order for x in ss if rx.search(x)), "" if status != "deployed" else (ss[0] if ss else ""))
    b = clean(badge).rstrip(".")
    out = f"{b}. {key}" if key and key.lower().rstrip(".") not in b.lower() else f"{b}."
    if status != "deployed" and not (NEG1.search(out) or NEG2.search(out)):
        out = f"{b}."                         # never a research / archived summary that reads as a pass
    return _cut(out, 300)


def backtest_items():
    from glossary import bt_catalog, _bt_public, _bt_redact, BT_FROZEN, BT_BADGE
    out = []
    for s in bt_catalog().get("strategies", []):
        name, _tests, verdict = _bt_public(s)
        pub = bool(s.get("public"))
        href = (s.get("report_html") or f"bt_{s['key']}.html") if pub else "strategies.html#backtests"
        st = _status(s) + (" · frozen" if s["key"] in BT_FROZEN else "")
        kind = "deployed" if s.get("badge") == "green" else ("research" if s.get("badge") == "yellow" else "archived")
        badge = _bt_redact(s.get("verdict") or BT_BADGE.get(s.get("badge", "red"), ("", ""))[0])
        out.append(_item(id="bt-" + s["key"].replace("_", "-"), type="Backtest", title=text(name),
                         summary=bt_summary(kind, text(badge), verdict), summary_whole=True, outcome=st,
                         kind=kind, date=_iso((s.get("dates") or {}).get("run")),
                         page="Strategies" + (" · report" if pub else ""), href=href))
    return out


def project_items():
    proj = literal("17_build_site.py", "PROJECTS")
    page = _read("projects.html") or ""
    out = []
    from glossary import _bt_redact
    for name, handle, url, desc, status, live in proj:
        if "[internal]" in _bt_redact(f"{name} {handle}"):
            continue     # a name confscan treats as internal stays on projects.html only (still indexed as a page)
        m = re.search(re.escape(f'<span class="proj-handle">{handle}</span>') +
                      r'.*?(?:Last push &middot; (\d{2} \w{3} \d{4})|class="proj-foot")', page, re.S)
        iso = ""
        if m and m.group(1):
            iso = datetime.strptime(m.group(1), "%d %b %Y").date().isoformat()
        out.append(_item(id="project-" + handle.split("/")[-1], type="Project", title=text(name),
                         summary=brief(desc), outcome=status, date=iso, date_label=(
                             f"last push {nice(iso)}" if iso else ""),
                         page="Projects", href="projects.html", external=url if live else ""))
    return out


def stock_items():
    out = []
    for t in literal("19_stock_analysis.py", "DEFAULT"):
        pg = _read(f"stock_{t}.html")
        if pg is None:
            continue
        ttl = re.search(r"<title>([^<]+)</title>", pg)
        m = re.search(r'class="asof">As of (\d{4}-\d{2}-\d{2})', pg)
        out.append(_item(id=f"stock-{t.lower()}", type="Stock page", title=f"{t}: CFA-framework equity analysis",
                         summary="DuPont return on equity, a dividend-discount value, justified P/E and the "
                                 "analyst consensus for one company on the research watchlist.",
                         date=m.group(1) if m else "", page="Stock Research", href=f"stock_{t}.html",
                         topics=["Equities"]))
        if ttl and t not in ttl.group(1):
            raise SystemExit(f"research_index: stock_{t}.html title {ttl.group(1)!r} does not name {t}")
    return out


SEC_RX = re.compile(r'<section class="block"[^>]*\bid="([^"]+)"[^>]*>\s*<h2[^>]*>(.*?)</h2>(.*?)</section>', re.S)


def _pages():
    """The research pages indexed section by section: the Research corner's pages (glossary.RESEARCH_LINKS, less
    the library itself and the report, which is indexed by its own sections) + Stock Research."""
    from glossary import RESEARCH_LINKS
    out = [(h, t) for h, t, _d in RESEARCH_LINKS if "#" not in h and h not in ("research-library.html", "report.html")]
    return out + [("stocks.html", "Stock Research")]


def section_items():
    out = []
    # undated on purpose: a page's content date is its render / pipeline date, not the date of a research result,
    # and "Newest first" would otherwise open with page sections
    for rel, label in _pages():
        pg = _read(rel)
        if pg is None:
            continue
        for sid, h2, body in SEC_RX.findall(pg):
            note = re.search(r'<p class="note"[^>]*>(.*?)</p>', body, re.S)
            out.append(_item(id=f"sec-{rel.split('.')[0]}-{sid}", type="Page section", title=text(h2),
                             summary=brief(note.group(1)) if note else "", page=label, href=f"{rel}#{sid}"))
        lede = re.search(r'<p class="lede">(.*?)</p>', pg, re.S)
        out.append(_item(id=f"page-{rel.split('.')[0]}", type="Page", title=label,
                         summary=brief(lede.group(1)) if lede else "", page=label, href=rel))
    return out


def build_items():
    items = (report_items() + finding_items() + batch_items() + backtest_items() + project_items()
             + stock_items() + section_items())
    seen = set()
    for it in items:
        if it["id"] in seen:
            raise SystemExit(f"research_index: duplicate item id {it['id']}")
        seen.add(it["id"])
    return items


def research_pages():
    """Every published research page: the Research corner's pages (glossary.RESEARCH_LINKS; the report as the page
    it redirects to), Stock Research, and every file matching a sub-page pattern of glossary.SUBPAGES (bt_*,
    stock_*, archive/report_*). A page added to the corner is therefore checked without touching this file."""
    from glossary import RESEARCH_LINKS, SUBPAGES
    pages = {h.split("#")[0] for h, _t, _d in RESEARCH_LINKS} - {"research-library.html", "report.html"}
    pages |= {report_target().split("#")[0], "stocks.html"}
    files = [f for f in os.listdir(str(DOCS)) if f.endswith(".html")]
    ad = os.path.join(str(DOCS), "archive")
    if os.path.isdir(ad):
        files += [f"archive/{f}" for f in os.listdir(ad) if f.endswith(".html")]
    for f in files:
        if any(re.fullmatch(rx, f) for rx, _parent in SUBPAGES):
            pages.add(f)
    return sorted(p for p in pages if _read(p) is not None)


def check_items(items):
    """Problems: an internal link to a missing page/anchor, a published research page no item links to, and the
    counts that must reconcile with the pages (findings cards, catalogue cards)."""
    probs = []
    for it in items:
        rel, _, anc = it["href"].partition("#")
        pg = _read(rel)
        if pg is None:
            probs.append(f"{it['id']}: {rel} does not exist")
        elif anc and not re.search(r'\bid="%s"' % re.escape(anc), pg):
            probs.append(f"{it['id']}: #{anc} not found in {rel}")
        if it["external"] and not it["external"].startswith("https://github.com/DuiArte/"):
            probs.append(f"{it['id']}: external link outside github.com/DuiArte: {it['external']}")
    linked = {it["href"].split("#")[0] for it in items}
    for p in research_pages():
        if p not in linked:
            probs.append(f"published research page {p} is not in the library")
    rs = _read("research.html") or ""
    n_cards = len(re.findall(r'<article id="f\d+"', rs))
    n_f = sum(1 for it in items if it["type"] == "Finding")
    if rs and n_cards != n_f:
        probs.append(f"findings: {n_f} items vs {n_cards} cards on research.html")
    sg = _read("strategies.html") or ""
    n_st = len(re.findall(r'<article data-status="[a-z]+" class="btcard st-[a-z]+ bt-', sg))   # not the note-cards
    n_b = sum(1 for it in items if it["type"] == "Backtest")
    if sg and n_st != n_b:
        probs.append(f"backtests: {n_b} items vs {n_st} catalogue cards on strategies.html")
    n_rows, n_bat = batch_table_rows(rs), sum(1 for it in items if it["type"] == "Research batch")
    if rs and n_rows != n_bat:
        probs.append(f"batches: {n_bat} items vs {n_rows} rows in research.html#batches")
    for it in items:
        if it["type"] == "Backtest" and it.get("kind") != "deployed" and not (NEG1.search(it["summary"])
                                                                            or NEG2.search(it["summary"])):
            probs.append(f"{it['id']}: a {it.get('kind')} backtest whose summary does not read as negative")
        if _MARK.search(it["summary"]) or _MARK.search(it["title"]) or _VENDOR.search(it["summary"]):
            probs.append(f"{it['id']}: a redaction placeholder or a vendor name in the title / summary")
    return probs


def tally():
    """The public counts-only tally (27 writes data/research_tally.json from the private ledger)."""
    try:
        t = json.load(open(os.path.join(str(DATA), "research_tally.json"), encoding="utf-8"))
        return int(t.get("total") or sum(g["n"] for g in t["groups"])), t.get("asof", "")
    except (OSError, ValueError, KeyError, TypeError):
        return None, ""


# ------------------------------------------------------------------------------------------- sources
def _consensus():
    try:
        return json.load(open(os.path.join(str(DATA), "market_intel", "consensus_public.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _congress():
    try:
        return json.load(open(os.path.join(str(DATA), "market_intel", "congress_public.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fred_series():
    """The FRED series the daily signals step pulls (08_fetch_signals.FRED), read as a literal."""
    try:
        return sorted(set(literal("08_fetch_signals.py", "FRED").values()))
    except (KeyError, OSError, ValueError, SyntaxError):
        return []


SOURCES = [
    # key, name, provides, pages [(href, label)], cadence, link, terms, evidence [(public file, regex)]
    ("fred", "FRED, Federal Reserve Bank of St. Louis",
     "Treasury yields across the curve, fed funds, breakeven inflation, VIX, credit spreads, the US dollar against "
     "the peso, the Mexico 10-year yield and the economic-policy-uncertainty series.",
     [("index.html", "Dashboard"), ("regime.html", "Regime Tracker"), ("stocks.html", "Stock Research"),
      ("report.html", "Full Report")],
     "Every weekday (signals); weekly with the model rebuild", "https://fred.stlouisfed.org",
     "Free to use with attribution under FRED's terms; some series stay the copyright of their original source "
     "(for example ICE BofA spreads and Cboe's VIX).",
     [("scripts/08_fetch_signals.py", r"fred_series"), ("scripts/fred_api.py", r"api\.stlouisfed\.org"),
      ("scripts/20_regime_tracker.py", r"fred_series")]),
    ("yahoo", "Yahoo Finance",
     "End-of-day prices and fundamentals: the portfolio's marks, the stock research pages and the picks, the S&P 500 "
     "benchmark, the regime tracker's index series, the out-of-sample backtest replays and the model's ETF prices.",
     [("portfolio.html", "Portfolio"), ("stocks.html", "Stock Research"), ("regime.html", "Regime Tracker"),
      ("strategies.html", "Strategies"), ("index.html", "Dashboard")],
     "Every weekday", "https://finance.yahoo.com",
     "Yahoo's terms of service. Read through an honest client that does not impersonate a browser; a blocked "
     "request is recorded as a gap, never retried.",
     [("scripts/yahoo_session.py", r"class HonestSession"), ("scripts/18_portfolio.py", r"yf\.download"),
      ("scripts/19_stock_analysis.py", r"yf\.Ticker"), ("scripts/picker.py", r"yf\.Ticker"),
      ("scripts/benchmark_ytd.py", r"yf\.download")]),
    ("gpr", "Geopolitical Risk index (Caldara and Iacoviello)",
     "The monthly geopolitical-risk index behind the Dashboard's news-uncertainty gauge and the regime tracker.",
     [("index.html", "Dashboard"), ("regime.html", "Regime Tracker")],
     "Every weekday check; the index itself is monthly", "https://www.matteoiacoviello.com/gpr.htm",
     "Published by the authors for research use; cite Caldara and Iacoviello (2022).",
     [("scripts/08_fetch_signals.py", r"matteoiacoviello\.com")]),
    ("epu", "Economic Policy Uncertainty (Baker, Bloom and Davis)",
     "The US and global policy-uncertainty indices, read through FRED.",
     [("index.html", "Dashboard"), ("regime.html", "Regime Tracker")],
     "Monthly series, checked every weekday", "https://www.policyuncertainty.com",
     "Published by the authors for research use; cite Baker, Bloom and Davis (2016).",
     [("scripts/08_fetch_signals.py", r"USEPUINDXM")]),
    ("sec", "SEC EDGAR (Form 4 insider filings)",
     "Insider buys and sales (Form 4) for the Stock Research universe.",
     [("stocks.html", "Stock Research")], "Every weekday, paced", "https://www.sec.gov/edgar/search/",
     "US government public records. Read under the SEC's fair-access policy (a declared user agent, paced "
     "requests, no redirects followed).",
     [("scripts/insider_form4.py", r"data\.sec\.gov")]),
    ("wiki_sp500", "Wikipedia: List of S&P 500 companies",
     "The S&P 500 constituent list the stock screener draws its US universe from.",
     [("stocks.html", "Stock Research")], "Every weekday", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
     "Text under CC BY-SA 4.0; only the list of tickers is used.",
     [("scripts/19_stock_analysis.py", r"wikipedia\.org")]),
    ("house", "U.S. House of Representatives, Office of the Clerk",
     "Periodic Transaction Reports: the trades members of the House disclose under the STOCK Act.",
     [("congressional-activity.html", "Congress"), ("index.html", "Dashboard")],
     "Checked for new filings every weekday", "https://disclosures-clerk.house.gov/FinancialDisclosure",
     "Public records, reproduced for research.",
     [("data/market_intel/congress_public.json", r"disclosures-clerk\.house\.gov"),
      ("scripts/30_market_intel.py", r"Office of the Clerk")]),
    ("senate_mirror", "Senate filings: the open dataset austin-starks/congressional-stock-trades",
     "Senate trades, and House filings that are scanned images, built from the official disclosures (marked with a "
     "dagger on the page).",
     [("congressional-activity.html", "Congress")], "Checked every weekday",
     "https://huggingface.co/datasets/austin-starks/congressional-stock-trades",
     "Open dataset on Hugging Face; see its dataset card for terms. The Senate's own site blocks automated access "
     "and this site does not work around it.",
     [("scripts/30_market_intel.py", r"austin-starks/congressional-stock-trades"),
      ("data/market_intel/congress_public.json", r'"via":\s*"mirror"')]),
    ("legislators", "unitedstates/congress-legislators",
     "Committee and subcommittee memberships, used to flag trades in a sector a member's committee oversees.",
     [("congressional-activity.html", "Congress")], "With each congress rebuild",
     "https://github.com/unitedstates/congress-legislators",
     "Open data project; see the repository for its public-domain dedication.",
     [("scripts/30_market_intel.py", r"unitedstates/congress-legislators")]),
    ("kalshi", "Kalshi",
     "Fed decision markets meeting by meeting, and event markets in the six-month outlook.",
     [("ltcma-consensus.html", "Market Intel"), ("index.html", "Dashboard")],
     "Every weekday (16:45)", "https://kalshi.com",
     "Read-only public market data; prices are not forecasts and nothing is traded.",
     [("data/market_intel/fed_path_public.json", r"kalshi\.com"), ("scripts/30_market_intel.py", r"kalshi\.com")]),
    ("polymarket", "Polymarket",
     "Fed and macro, geopolitics and other event markets alongside Kalshi.",
     [("ltcma-consensus.html", "Market Intel")], "Every weekday (16:45)", "https://polymarket.com",
     "Read-only public market data (prices only; no wallet or trader information is shown).",
     [("data/market_intel/fed_path_public.json", r"polymarket\.com"), ("scripts/30_market_intel.py", r"polymarket\.com")]),
    ("cma", "Capital market assumption publishers",
     "Long-run expected returns and outlooks from asset managers and banks, set against this site's model "
     "(numbers only where the publisher allows republication; otherwise the stated view and a link).",
     [("ltcma-consensus.html", "Market Intel"), ("index.html", "Dashboard")],
     "Checked every weekday; rebuilt on each new edition", "ltcma-consensus.html#sources",
     "Each publisher's own terms; figures are attributed and linked to the original documents.",
     [("data/market_intel/consensus_public.json", r'"publishers"')]),
    ("shiller", "Robert Shiller's U.S. stock market data (Yale)",
     "Monthly S&P composite prices, dividends, earnings and the CAPE since 1871: the model's long-history input.",
     [("report.html", "Full Report"), ("index.html", "Dashboard")],
     "Weekly model rebuild (Sundays)", "http://www.econ.yale.edu/~shiller/data.htm",
     "Free data published by the author; cite Shiller.",
     [("scripts/05a_download_longhistory.py", r"ie_data\.xls")]),
    ("french", "Kenneth R. French Data Library (Tuck, Dartmouth)",
     "Regional market factor returns used as long-history proxies for developed, European, Japanese and emerging "
     "markets.", [("report.html", "Full Report")], "Weekly model rebuild (Sundays)",
     "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
     "Free data published by the author; cite the data library.",
     [("scripts/05a_download_longhistory.py", r"ken\.french")]),
    ("damodaran", "Aswath Damodaran, historical returns (NYU Stern)",
     "Annual returns on US stocks, bonds, bills, real estate and gold since 1928.",
     [("report.html", "Full Report")], "Weekly model rebuild (Sundays)", "https://pages.stern.nyu.edu/~adamodar/",
     "Free data published by the author; cite Damodaran.",
     [("scripts/05a_download_longhistory.py", r"adamodar")]),
    ("github", "GitHub REST API",
     "The date each public project repository was last pushed.", [("projects.html", "Projects")],
     "Every weekday", "https://docs.github.com/en/rest", "GitHub's terms; unauthenticated, public metadata only.",
     [("scripts/content_age.py", r"api\.github\.com/repos")]),
    ("webb", "ESA/Webb image archive (NASA, ESA, CSA, STScI)",
     "The JWST images behind the page headers (cropped).",
     [("index.html", "Dashboard"), ("portfolio.html", "Portfolio"), ("ltcma-consensus.html", "Market Intel"),
      ("congressional-activity.html", "Congress"), ("research-library.html", "Research Library")],
     "Fixed images", "https://esawebb.org/images/", "CC BY 4.0, credited on every page that shows one.",
     [("assets/credits.json", r"esawebb\.org"), ("scripts/design_system.py", r"def hero\(")]),
]
# Report references (11.3) that stay OUT of the Sources directory even though the archived report cites them:
# broker market data is a private input by the site's rules (WEBSITE_AGENT_RULES 2), so it is not listed.
REF_EXCLUDE = re.compile(r"\bFxPro\b|MetaTrader", re.I)


def check_sources():
    """[(source, ok, why)] -- an entry is live only when every evidence pair matches a public file of this repo."""
    out = []
    for s in SOURCES:
        bad = []
        for rel, rx in s[7]:
            p = os.path.join(str(ROOT), *rel.split("/"))
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    if not re.search(rx, fh.read()):
                        bad.append(f"{rel}: /{rx}/ not found")
            except OSError:
                bad.append(f"{rel}: missing")
            if rel.startswith("scripts/") and not os.path.basename(rel)[:2].isdigit() and rel not in (
                    "scripts/fred_api.py", "scripts/yahoo_session.py", "scripts/picker.py", "scripts/benchmark_ytd.py",
                    "scripts/insider_form4.py", "scripts/content_age.py", "scripts/design_system.py"):
                bad.append(f"{rel}: not a known public generator module")
        out.append((s, not bad, "; ".join(bad)))
    return out


def references():
    """The works the Full Report cites (11.3 References), minus broker data (REF_EXCLUDE)."""
    try:
        md = open(os.path.join(str(REPORT), "LTCMA_2026.md"), encoding="utf-8").read()
    except OSError:
        return []
    m = re.search(r"(?ms)^### 11\.3 References\s*\n(.*?)(?=^###|\Z)", md)
    if not m:
        return []
    out = []
    for para in re.split(r"\n\s*\n", m.group(1)):
        t = " ".join(para.split())
        if not t or not re.search(r"\(\d{4}\)\.", t[:160]) or REF_EXCLUDE.search(t):
            continue
        url = re.search(r"\s(https?://\S+?)\.?$", t)
        body = t[:url.start()].strip() if url else t
        out.append((re.sub(r"\*", "", body), url.group(1) if url else ""))
    return out
