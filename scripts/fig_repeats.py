"""LTCMA - repeated figures on a page (ds_gate R8, 2026-11-10 wave "no repeats", Carlos: "intenta que no se repita
info en la misma pestana").

A page should show each headline figure ONCE per viewport. This module reads a RENDERED page and lists every visible
figure (percent, percentage points, sigma, multiples, money, "N of M", big and counted numbers) with the component and
section it sits in, then groups the occurrences that state the same figure in the same view:

  view       = viewport x currency state. Viewports: phone (375 px) and desktop (1280 px), evaluated against the
               page's own CSS (style.css + its <style> blocks): an element under `display:none` at a width is not
               visible there, so a copy shown only <= 640 px and another only >= 641 px is ONE place. Currency
               state: a `.cval` figure shows its data-mxn text in the MXN state and its data-usd text in the USD
               state (both reachable with the page's toggle); static text shows in both.
  same figure = the same normalised value AND, unless the value is distinctive (two or more decimals, a thousands
               separator, "N of M"), a shared content word in the two occurrences' labels (so "80% hike odds" twice
               is a repeat, "80% of the book" and "80% hike odds" are not).
  roles      = HEADLINE (hero stats / panel, KPI and metric tiles, card big numbers and headline sentences,
               overview / hub / summary cards, section badges, bar lists such as the Expect bars, the Fed rows, the
               Watch lines and the sector flows, ledes), PROSE (notes, captions, list items, headings, report text)
               and DETAIL (table cells incl. totals, the prediction-market snapshot cards: the record behind a
               summary figure, the Research Library's item list). A REPEAT is a figure shown twice in one view where at least one place is a HEADLINE
               and another is a HEADLINE or PROSE, or a HEADLINE restating a DETAIL cell of the same section with the
               same label (a bar list that repeats its own table). Prose-vs-prose and detail-vs-detail are not
               counted, nor two places of the same component type (a grid of tiles, a bar list or a set of
               parallel cards lists distinct things that can coincide in value): explanations, and the narratives the Market Intel pipeline / private REPORT.md files write
               (not authored by the site generators), may cite a number twice.
  excluded   = Plotly charts (legends, axes and hovers live in the chart JSON), the header / Research corner /
               footer, the as-of chip, buttons, filter chips and their counts, legends, credits, <script> / <style> /
               <noscript>, `hidden` elements, visually hidden text.

Known limits (review round 1, PIPE-5 / DC-5): values are compared as normalised STRINGS, so one figure printed at two
precisions (16.11% and 16.1%) is not caught; prose vs prose and the pipeline-authored narratives (the Market Intel
summary bullets vs its divergence cards, the strategy catalogue lines) are not counted, so "0 repeats" is by THIS
definition, not a proof that no number appears twice.

Functional repeats the gate accepts are listed in ALLOW with the reason (a model descriptor such as "12-year", a
heading count that labels its own list, ...). Read-only: parses HTML, writes nothing.
"""
import html as _html
import os
import re

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:                                     # pragma: no cover - bs4 ships with yfinance
    BeautifulSoup = None

VIEWPORTS = {"phone": 375, "desktop": 1280}
STATES = ("mxn", "usd")

# --------------------------------------------------------------------------------------------- excluded zones
# (a) functional surfaces: navigation, chips/filters, buttons, legends, credits, the as-of chip, footers
EXCL_TAGS = {"script", "style", "noscript", "svg", "template", "button", "select", "option", "textarea", "input",
             "nav", "header", "footer", "summary", "code", "pre"}
EXCL_CLASSES = {"asof", "hero-credit", "credits", "rc-menu", "rcn", "vtabs", "ptabs", "toc", "pills", "btctl",
                "ccy-toggle", "legend", "lg", "chip", "chips", "lib-chips", "lib-filters", "fchips", "lib-count",
                "plotly-graph-div", "sr-only", "visually-hidden", "brand", "kicker", "xgo", "cta", "li-meta",
                "ven", "who", "shell-foot", "about-flex", "tags", "role", "certs", "contact", "hp-k", "gends"}
TABLE_TAGS = {"table"}
HEADLINE_CLASSES = {"hero-stats", "hero-stat", "hero-panel", "hp-big", "hp-row", "hp-foot", "metric", "metrics", "kpi",
                    "kpis", "mtile", "mtiles", "xbig", "xh", "xcard", "ovc", "badge", "wline", "brow", "fedrow", "flow",
                    "bars", "lede", "lede2", "stat", "stats", "scard", "sc-n", "bt-mv", "bt-metrics", "oos-v",
                    "oos-stats", "mv", "picks5"}
DETAIL_CLASSES = {"odds", "odd", "lib-list"}
# narratives the site does not author (catalogue verdict lines from data/backtests_strategies.json, the private
# REPORT.md bodies the bt_* pages render verbatim): never counted, kept for the before/after diff
DATAPROSE_CLASSES = {"bt-verdict", "report"}
BLOCK = {"p", "li", "div", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "article", "section", "a", "dd", "dt",
         "figcaption", "blockquote", "aside", "main", "body", "details", "span"}

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|" \
         "september|october|november|december|ene|abr|ago|dic"
STOP = set("""the a an of in on at to from for by with and or but is are was were be been this that these those it its
as than then into over under per via vs versus not no only one all each every more most less least same other own
also its their there here what which who how why when where while if so do does did can could will would should may
might must has have had our my your his her they them we you i me us up down out off about after before since until
through during between against among across within without near new old last next first latest prior previous
year years month months week weeks day days today date dated through ytd so far""".split())
STOP |= set(MONTHS.split("|"))
STOP |= set("bp bps pp pts pt point points percent usd mxn eur kalshi polymarket price prices market markets".split())

# names / descriptors that contain digits but are not figures
NAMES = [r"S&P\s*500", r"S&amp;P\s*500", r"Russell\s*\d{4}", r"Nasdaq[- ]100", r"MSCI\s+\w+",
         r"(?<![\d.,$])\b\d{1,2}Y\b", r"(?<![\d.,$])\b\d{1,2}M\b(?![A-Za-z])", r"CC BY \d\.\d", r"Form \d+", r"\bT\+\d\b", r"\bH\.R\.\s*\d+", r"\bFOMC\b",
         r"\bQ[1-4]\b", r"\bP\d{2}\b", r"\bGPT-\d", r"\bWave \d+\b", r"\bwave \d+\b", r"\bv\d+(?:\.\d+)*\b",
         r"\b[A-Z]{1,4}-[A-Z]{2}\d{2}\b", r"\b[A-Z]{2}-[A-Z]{2}-Sen\b", r"\b\d+:\d+\b", r"\bF\d{2}\b",
         r"#\d+\b", r"\bn\s?[=≥>]\s?\d+", r"\bIQR\b", r"\b\d+(?:st|nd|rd|th)\b", r"\b\d{3}-day\b"]
NAMES += [r"[$]\d[\d,.]*\s?[KMB]?\s?[-–]\s?[$]?\d[\d,.]*\s?[KMB]?",          # disclosure ranges $500K-1M
          r"(?:Over|Under|over|under|>|<)\s?[$]\d[\d,.]*\s?[KMB]?",            # Over $1M, > $500K
          r"\d+\+?\s?bps?\s+(?:hike|cut|increase|decrease|move|change)s?",      # a move size, not a figure
          r"(?:[Hh]ike|[Cc]ut|[Ii]ncrease|[Dd]ecrease)\s*[>+]?\s?\d+\s?bps?",
          r"\(\d+ bps?\)", r"\d+\+ bps?", r"\d+\s?days?\)", r"\(\d+ d\)"]
NAME_RX = re.compile("|".join(NAMES))
DATE_RX = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\b"            # ISO dates / times
    r"|\b\d{1,2}\s+(?:%s)\.?(?:\s+\d{4})?\b" % MONTHS +                 # 09 Dec 2026 / 10 Nov
    r"|\b(?:%s)\.?\s+\d{1,2},?\s+\d{4}\b" % MONTHS +                    # Dec 9, 2026
    r"|\b(?:%s)\.?\s+(?:'\d{2}|\d{4})\b" % MONTHS +                     # Dec 2026
    r"|\b(?:19|20)\d{2}\s*[-–]\s*(?:19|20)?\d{2}\b"                      # 2014-2026
    r"|\b(?:19|20)\d{2}\b"                                              # bare years
    r"|\b\d{1,2}:\d{2}\b", re.I)                                        # clock times

FIG_RX = re.compile(
    r"(?P<nofm>\b\d{1,3}(?:,\d{3})*\s+of\s+(?:the\s+)?\d{1,3}(?:,\d{3})*\b)"
    r"|(?P<money>[+\-−]?\s?(?:US\$|MX\$|\$|€|£)\s?[+\-−]?\d[\d,]*(?:\.\d+)?\s?(?:[KMBT]\b|bn\b|mn\b)?)"
    r"|(?P<pct>[+\-−]?\d[\d,]*(?:\.\d+)?\s?%)"
    r"|(?P<pp>[+\-−]?\d+(?:\.\d+)?\s?(?:pp\b|percentage points?\b|points?\b|pts?\b))"
    r"|(?P<bp>[+\-−]?\d+(?:\.\d+)?\s?bps?\b)"
    r"|(?P<sig>[+\-−]?\d+(?:\.\d+)?\s?(?:σ|&sigma;|sigma\b))"
    r"|(?P<mult>\b\d+(?:\.\d+)?x\b)"
    r"|(?P<num>[+\-−]?\b\d[\d,]*(?:\.\d+)?\b)")
WORD_RX = re.compile(r"[A-Za-z][A-Za-z'\-]+")


def _norm_space(t):
    return re.sub(r"\s+", " ", t.replace("\xa0", " ").replace(" ", " ").replace(" ", " ")).strip()


# --------------------------------------------------------------------------------------------- CSS visibility
def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _media_blocks(css):
    """yield (query or None, selector, body) for every rule, one level of @media nesting."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        head = css[i:j].strip()
        if head.startswith("@media") or head.startswith("@supports"):
            depth, k = 1, j + 1
            while k < n and depth:
                depth += css[k] == "{"
                depth -= css[k] == "}"
                k += 1
            inner = css[j + 1:k - 1]
            for _q, sel, body in _media_blocks(inner):
                yield (head if head.startswith("@media") else _q), sel, body
            i = k
        elif head.startswith("@"):
            depth, k = 1, j + 1
            while k < n and depth:
                depth += css[k] == "{"
                depth -= css[k] == "}"
                k += 1
            i = k
        else:
            k = css.find("}", j)
            if k < 0:
                return
            yield None, head, css[j + 1:k]
            i = k + 1


def _query_matches(q, width):
    if q is None:
        return True
    ql = q.lower()
    if "print" in ql and "screen" not in ql:
        return False
    conds = re.findall(r"\(([^)]*)\)", ql)
    if not conds:
        return "screen" in ql or "all" in ql
    for c in conds:
        c = c.replace(" ", "")
        m = re.fullmatch(r"(max|min)-width:(\d+(?:\.\d+)?)px", c)
        if m:
            v = float(m.group(2))
            if m.group(1) == "max" and not width <= v:
                return False
            if m.group(1) == "min" and not width >= v:
                return False
            continue
        if c.startswith(("prefers-reduced-motion", "hover", "pointer", "any-hover", "any-pointer")):
            return False          # motion / pointer rules never hide content here; be conservative
        if c.startswith(("max-height", "min-height", "orientation", "prefers-color-scheme", "max-aspect", "min-aspect")):
            return False
    return True


def _clean_selector(sel):
    sel = sel.strip()
    if not sel or "::" in sel or re.search(r":(hover|focus|active|visited|focus-visible|focus-within|checked|"
                                           r"target|before|after|first-letter|first-line|placeholder)", sel):
        return None
    sel = re.sub(r":not\(\.js\)|html\.js|html:not\(\.js\)|\.js\b(?=\s)", "", sel).strip()
    sel = re.sub(r"^(html|:root)\s+", "", sel)
    return sel or None


def hidden_sets(soup, css_text):
    """{width: set(id(element))} of elements under display:none at each viewport width."""
    css = _strip_comments(css_text)
    rules = []
    for q, sel, body in _media_blocks(css):
        if re.search(r"display\s*:\s*none", body):
            rules.append((q, sel, "none"))
        elif re.search(r"display\s*:\s*(block|flex|grid|inline|inline-block|inline-flex|table|contents)", body):
            rules.append((q, sel, "show"))
    # a selector naming a class / id / tag the page does not have cannot match: skip it (the shared style.css carries
    # ~1,000 rules for every page); evaluate each remaining selector once for both widths
    have_cls, have_id, have_tag = set(), set(), set()
    for el in soup.find_all(True):
        have_tag.add(el.name)
        have_cls.update(_classes(el))
        if el.get("id"):
            have_id.add(el.get("id"))
    cache = {}

    def sel_all(s):
        if s in cache:
            return cache[s]
        need_c = re.findall(r"\.([A-Za-z_][\w-]*)", s)
        need_i = re.findall(r"#([A-Za-z_][\w-]*)", s)
        need_t = re.findall(r"(?:^|[\s>+~])([a-z][a-z0-9]*)(?=[.#:\[\s>+~]|$)", s)
        if any(c not in have_cls for c in need_c) or any(i not in have_id for i in need_i) or \
                any(t not in have_tag for t in need_t):
            cache[s] = []
            return []
        try:
            cache[s] = soup.select(s)
        except Exception:  # noqa: BLE001 - selector bs4 cannot parse: ignore
            cache[s] = []
        return cache[s]
    out = {}
    for name, w in VIEWPORTS.items():
        hid = {}
        for q, sel, kind in rules:
            if not _query_matches(q, w):
                continue
            for part in sel.split(","):
                s = _clean_selector(part)
                if not s or s.startswith(".jsonly") or ".js " in part:
                    continue
                for el in sel_all(s):
                    hid[id(el)] = kind      # later rules win (source order), as in the cascade (same specificity)
        out[name] = {k for k, v in hid.items() if v == "none"}
    return out


# --------------------------------------------------------------------------------------------- extraction
def _classes(el):
    c = el.get("class") or []
    return set(c if isinstance(c, list) else str(c).split())


def _zone(el):
    """(zone, section, component, role) for a text node's parent chain: zone excluded / table / count; role
    headline / prose / detail."""
    zone, section, comp, role = "count", "", "", "prose"
    cur = el
    while cur is not None and isinstance(cur, Tag):
        cls = _classes(cur)
        if cur.name in EXCL_TAGS or cls & EXCL_CLASSES or cur.has_attr("hidden"):
            zone = "excluded"
        if (cur.name in TABLE_TAGS or cls & DETAIL_CLASSES) and zone == "count":
            zone = "table"
        if cls & DATAPROSE_CLASSES:
            role = "dataprose"
        if cls & HEADLINE_CLASSES and role == "prose":
            role = "headline"
        if not comp and cls:
            comp = f"{cur.name}.{sorted(cls)[0]}"
        if not section and cur.name in ("section", "article", "aside") and (cur.get("id") or cur.find(["h2", "h3"])):
            h = cur.find(["h2", "h3"])
            section = cur.get("id") or (_norm_space(h.get_text(" "))[:40] if h else cur.name)
        cur = cur.parent
    if zone == "table":
        role = "detail"
    return zone, section or "page", comp or el.name, role


def _unit(el):
    """the smallest block around a figure whose text carries words (climb past value-only boxes)."""
    cur = el
    while cur is not None and isinstance(cur, Tag) and cur.name not in BLOCK:
        cur = cur.parent
    for _ in range(4):
        if cur is None or not isinstance(cur, Tag):
            break
        txt = _norm_space(cur.get_text(" "))
        if len([w for w in WORD_RX.findall(DATE_RX.sub(" ", txt)) if w.lower() not in STOP and len(w) > 2]) >= 1:
            break
        cur = cur.parent
    return cur


def _lemma(w):
    w = w.lower().strip("'-")
    for suf in ("ies",):
        if w.endswith(suf) and len(w) > 4:
            return w[:-3] + "y"
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        w = w[:-1]
    return w


def _words(txt):
    return {_lemma(w) for w in WORD_RX.findall(DATE_RX.sub(" ", NAME_RX.sub(" ", txt)))
            if len(w) > 2 and w.lower() not in STOP and _lemma(w) not in STOP}


def _norm_value(kind, raw):
    v = _norm_space(raw).replace("−", "-").replace("&sigma;", "σ").replace(" ", "").lower()
    v = v.lstrip("+")
    if kind == "pp":
        v = re.sub(r"(percentagepoints?|points?|pts?|pp)$", "pp", v)
    if kind == "bp":
        v = re.sub(r"bps?$", "bp", v)
    if kind == "sig":
        v = re.sub(r"(sigma|σ)$", "σ", v)
    if kind == "nofm":
        v = re.sub(r"ofthe", "of", v)
    if kind == "money":
        v = v.replace("us$", "$").replace("mx$", "$")
        v = re.sub(r"^(-?)\$-", r"-$", v)
    return v


def _distinctive(kind, v):
    core = v.lstrip("-$€£")
    if kind == "nofm":
        return True
    m = re.match(r"[\d,]*\.?\d*", core)
    sig = re.sub(r"[^\d]", "", m.group(0) if m else "").lstrip("0")
    if re.search(r"\.\d{2,}", core) and len(sig) >= 3:
        return True                     # 16.11% / 18.68 / 1.26: not 0.30 or 0.00
    if re.search(r"\d,\d{3}", core):
        return True
    return False


def _noun_after(txt, end):
    m = re.match(r"\s*([A-Za-z][A-Za-z\-]+)", txt[end:])
    return _lemma(m.group(1)) if m and m.group(1).lower() not in STOP else ""


def extract(html_text, page=""):
    """Every visible figure on the page: list of dicts (value, kind, zone, section, comp, label words, views)."""
    if BeautifulSoup is None:
        raise RuntimeError("bs4 not installed")
    soup = BeautifulSoup(html_text, "html.parser")
    css = "\n".join(st.get_text() for st in soup.find_all("style"))
    here = os.path.dirname(page) if page and os.path.isfile(page) else ""
    for ln in soup.find_all("link", rel=True):
        href = ln.get("href", "")
        if "stylesheet" in " ".join(ln.get("rel")) and href.endswith(".css") and not href.startswith("http") and here:
            p = os.path.join(here, href)
            if os.path.isfile(p):
                css = open(p, encoding="utf-8", errors="replace").read() + "\n" + css
    hid = hidden_sets(soup, css)
    occ = []
    for tn in soup.find_all(string=True):
        if not isinstance(tn, NavigableString) or not tn.strip() or tn.parent is None:
            continue
        par = tn.parent
        if par.name in ("script", "style", "noscript", "template", "title"):
            continue
        zone, section, comp, role = _zone(par)
        if zone == "excluded":
            continue
        # visibility per viewport: the text node is hidden when any ancestor is display:none at that width
        vis = {}
        for vp in VIEWPORTS:
            hs, cur, ok = hid[vp], par, True
            while cur is not None and isinstance(cur, Tag):
                if id(cur) in hs:
                    ok = False
                    break
                cur = cur.parent
            vis[vp] = ok
        if not any(vis.values()):
            continue
        # currency state: a .cval figure has one text per state
        cv = par if "cval" in _classes(par) else par.find_parent(class_="cval")
        texts = {}
        if cv is not None and cv.has_attr("data-mxn") and cv.has_attr("data-usd"):
            texts = {"mxn": _html.unescape(cv["data-mxn"]), "usd": _html.unescape(cv["data-usd"])}
        else:
            texts = {s: str(tn) for s in STATES}
        unit = _unit(par)
        utxt = _norm_space(unit.get_text(" ")) if unit is not None else _norm_space(str(tn))
        for st, raw_txt in texts.items():
            t = _norm_space(raw_txt)
            masked = DATE_RX.sub(lambda m: " " * len(m.group(0)), t)
            masked = NAME_RX.sub(lambda m: " " * len(m.group(0)), masked)
            for m in FIG_RX.finditer(masked):
                kind = m.lastgroup
                raw = t[m.start():m.end()]
                if kind == "num":
                    digits = re.sub(r"[^\d]", "", raw)
                    alone = _norm_space(masked).strip() == raw.strip()
                    noun = _noun_after(t, m.end())
                    if not alone and not noun:
                        continue                     # a bare number in running text: not a figure
                    if len(digits) == 1 and not alone and not noun:
                        continue
                    key_extra = noun
                else:
                    key_extra = ""
                v = _norm_value(kind, raw)
                dist = _distinctive(kind, v)
                v = v.replace(",", "")                 # 2,389 and 2389 are the same figure
                if kind == "num" and key_extra and len(re.sub(r"[^\d]", "", v)) < 3:
                    v = f"{v} {key_extra}"             # small counts carry their noun; 3+ digits stand alone
                # label words: the unit's text in a +/-12-word window around the figure
                ws = utxt.split()
                pos = next((i for i, w in enumerate(ws) if raw.strip().split()[0] in w), None)
                win = " ".join(ws[max(0, pos - 12):pos + 13]) if pos is not None else utxt[:200]
                occ.append(dict(value=v, raw=_norm_space(raw), kind=kind, zone=zone, role=role, section=section, comp=comp,
                                state=st, vis=[vp for vp, ok in vis.items() if ok],
                                words=sorted(_words(win)), distinctive=dist,
                                ctx=win[:160], node=id(tn)))
    return occ


# --------------------------------------------------------------------------------------------- allowlist
# Functional repeats (page glob, value regex, reason). Keep this list short; every entry says why the repeat is
# not "the same information twice".
ALLOW = [
    ("*", r"^12 year$|^12-year$", "the model's horizon in its name ('the 12-year model'), a descriptor, not a figure"),
    ("*", r"^(1|2|3|4|5|6|7|8|9) (step|tab|view|card|section|part|line|minute|click)$",
     "UI wording (a count of steps / tabs / views), not a data figure"),
]


def _allowed(page, g):
    import fnmatch
    for pg, rx, why in ALLOW:
        if fnmatch.fnmatch(page, pg) and re.search(rx, g["value"]):
            return why
    return None


def repeats(occ, page=""):
    """Groups of counted occurrences that state the same figure in the same view."""
    out = []
    for vp in VIEWPORTS:
        for st in STATES:
            cand = [o for o in occ if o["zone"] in ("count", "table") and vp in o["vis"] and o["state"] == st]
            by = {}
            for o in cand:
                by.setdefault(o["value"], []).append(o)
            for v, lst in by.items():
                if not any(o["role"] == "headline" for o in lst):
                    continue                        # every repeat involves a headline figure
                # dedupe the same text node (a figure inside a cval in both states is one place)
                seen, uniq = set(), []
                for o in lst:
                    if o["node"] in seen:
                        continue
                    seen.add(o["node"])
                    uniq.append(o)
                if len(uniq) < 2:
                    continue
                # an edge = the same figure in two places: distinctive value or a shared label word, and the roles
                # make it a repeat (headline-headline, headline-prose, headline-detail of the same section)
                par = list(range(len(uniq)))

                def find(i):
                    while par[i] != i:
                        par[i] = par[par[i]]
                        i = par[i]
                    return i
                edge = False
                for i, o in enumerate(uniq):
                    for j in range(i + 1, len(uniq)):
                        p = uniq[j]
                        roles = {o["role"], p["role"]}
                        if "headline" not in roles or "dataprose" in roles:
                            continue
                        if o["role"] == p["role"] == "headline" and o["comp"] == p["comp"]:
                            continue                # one component type lists distinct things (tiles, bars, cards)
                        shared = set(o["words"]) & set(p["words"])
                        if "detail" in roles and not (o["section"] == p["section"] and shared):
                            continue
                        if o["distinctive"] or shared:
                            par[find(i)] = find(j)
                            edge = True
                if not edge:
                    continue
                comps = {}
                for i in range(len(uniq)):
                    comps.setdefault(find(i), []).append(i)
                for idx in comps.values():
                    if len(idx) < 2:
                        continue
                    out.append(dict(page=page, value=v, view=f"{vp}/{st}", n=len(idx),
                                    where=[f"{uniq[i]['section']} > {uniq[i]['comp']} [{uniq[i]['role']}]: "
                                           f"{uniq[i]['ctx'][:110]}" for i in idx]))
    # one entry per (value, where-set) across views
    merged = {}
    for g in out:
        k = (g["value"], tuple(g["where"]))
        if k in merged:
            merged[k]["view"] += ", " + g["view"]
        else:
            merged[k] = g
    res = list(merged.values())
    for g in res:
        g["allowed"] = _allowed(page, g)
    return res


def scan_docs(docs, pages=None):
    """{page: {"occ": [...], "repeats": [...]}} for every page under docs (stubs and internal/ skipped)."""
    res = {}
    names = pages or sorted(f for f in os.listdir(docs) if f.endswith(".html"))
    for name in names:
        p = os.path.join(docs, name)
        h = open(p, encoding="utf-8", errors="replace").read()
        if 'http-equiv="refresh"' in h[:2000] and len(h) < 5000:
            continue                                  # redirect stub
        occ = extract(h, p)
        res[name] = {"occ": occ, "repeats": repeats(occ, name)}
    return res


def gate(docs):
    """R8: (errors, warnings, n_pages, n_figures) -- an unallowlisted repeat is an error."""
    errs, warns = [], []
    if BeautifulSoup is None:
        return [], ["R8 skipped: bs4 is not installed"], 0, 0
    res = scan_docs(docs)
    nfig = 0
    for page, r in res.items():
        nfig += sum(1 for o in r["occ"] if o["zone"] == "count")
        for g in r["repeats"]:
            if g["allowed"]:
                continue
            errs.append(f"R8 {page}: {g['raw'] if 'raw' in g else g['value']!s} shown {g['n']}x in {g['view']} -> "
                        + " | ".join(g["where"]))
    return errs, warns, len(res), nfig
