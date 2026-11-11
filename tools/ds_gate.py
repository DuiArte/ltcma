"""Design-system regression gate (REDESIGN_PLAN 5.1-5.3).

`daily_refresh.ps1` does NOT run any layout gate -- its "As-of + regression checks
passed" line covers date stamps and the fxaANEL/fxaOS CSS regression only. The plan
says the redesign should SHIP the gate, not merely use it. This is that deliverable.

The assertions split cleanly by what they need:

  STATIC (this file runs them, no browser, no server) --
    A9   no font family outside {Inter, Spectral, JetBrains Mono} in scripts/*.py
    A10  desktop parity: chart/table/tile counts per page vs a stored baseline
    S1   every rule in base.css is scoped under .ds-v2
    S2   no page carries .ds-v2 unless it is a declared Phase-1+ migrated page
    S3   no literal {CSS_LINKS} leaked into a generated page (non-f-string bug)
    S4   the design-system links precede style.css on every styled page
    R1-R7 (2026-11-10 remake) header completeness, Street held, hero credits, assets / budgets / EXIF,
         the home summary against the pages it summarises, the Research Library's links and sources --
         see remake_gate() below.
    R8   (2026-11-10, wave "no repeats") no page shows the same headline figure twice in one view
         (scripts/fig_repeats.py; functional repeats are listed in its ALLOW with a reason)
    R9   (2026-11-10, wave r2, dark mode) tools/theme_gate.py T1-T7: every page with the header is themed (boot,
         control, theme.css), no light-only colour literal left, the light theme keeps its colours, the chart
         palette map inverts exactly and clears 3:1 in dark, the dark text tokens clear 4.5:1

  BROWSER (A1-A8) -- need a real HTTP origin and an interactive session:
    python -m http.server 8777 --directory docs
  and then direct navigation per page at 375 and 1440. They are specified in
  REDESIGN_PLAN 5.2 and are NOT implemented here yet: writing measurement code that
  has never been run against a live page would ship a test whose passing means
  nothing. Phase 1 implements them together with capturing the before-baseline,
  which needs the Browser pane displayed (5.3).

Usage:
    python tools/ds_gate.py                 # static gate
    python tools/ds_gate.py --write-baseline
"""
import os, re, sys, json, glob, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
SCRIPTS = os.path.join(ROOT, "scripts")
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ds_baseline.json")

ALLOWED_FONTS = {"inter", "spectral", "jetbrains mono"}
# Generic families and Plotly/CSS fallbacks are not brand fonts and are exempt.
GENERIC = {"system-ui", "-apple-system", "segoe ui", "roboto", "sans-serif", "serif",
           "monospace", "ui-monospace", "sf mono", "menlo", "consolas", "charter",
           "iowan old style", "cambria", "georgia", "helvetica", "arial",
           "ibm plex sans", "ibm plex mono"}     # 26_* private twin only

# Pages that are meta-refresh redirect stubs: no styling, correctly unlinked. report.html joined them on
# 2026-10-01 (it redirects to the dated archive edition until a TAB_RESYNC, D-20260924-004).
STUBS = {"backtests.html", "signals.html", "report.html"}
# Pages migrated to the new component layer. Phase 0 = none.
MIGRATED = set()


def pages():
    return sorted(p for p in glob.glob(os.path.join(DOCS, "*.html")))


def fail(msg, bucket):
    bucket.append(msg)


def static_gate(write_baseline=False):
    errs, warns = [], []

    # --- S1: base.css fully scoped -------------------------------------------
    bp = os.path.join(DOCS, "_design_system", "base.css")
    if not os.path.exists(bp):
        fail("S1 base.css missing -- run 17_build_site.py", errs)
    else:
        css = open(bp, encoding="utf-8").read()
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)          # strip comments
        for sel in re.findall(r"(?m)^([^@{}\n][^{}\n]*)\{", css):
            for part in sel.split(","):
                part = part.strip()
                if part and ".ds-v2" not in part:
                    fail(f"S1 UNSCOPED rule in base.css: {part!r} -- Phase 0 must stay inert", errs)

    # --- S2/S3/S4: per page ---------------------------------------------------
    counts = {}
    for p in pages():
        name = os.path.basename(p)
        html = open(p, encoding="utf-8", errors="replace").read()

        if "{CSS_LINKS}" in html:
            fail(f"S3 {name}: literal {{CSS_LINKS}} leaked -- the enclosing string is not an f-string", errs)

        has_ds = re.search(r'<body[^>]*class="[^"]*\bds-v2\b', html) is not None
        if has_ds and name not in MIGRATED:
            fail(f"S2 {name}: carries .ds-v2 but is not in MIGRATED -- base.css is now live on it", errs)
        if not has_ds and name in MIGRATED:
            fail(f"S2 {name}: declared MIGRATED but has no .ds-v2 on <body>", errs)

        if name not in STUBS:
            it, ib, ist = (html.find('_design_system/tokens.css'),
                           html.find('_design_system/base.css'),
                           html.find('href="style.css"'))
            if it < 0 or ib < 0:
                fail(f"S4 {name}: missing a design-system <link>", errs)
            elif ist >= 0 and not (it < ist and ib < ist):
                fail(f"S4 {name}: design-system links must PRECEDE style.css "
                     "(equal-specificity selectors overlap; style.css must win until migration)", errs)

        counts[name] = {
            "charts": html.count("plotly-graph-div"),
            "tables": html.count("<table"),
            "tiles": html.count('class="tile') + html.count('class="card')
                     + html.count('class="btcard') + html.count('class="scard'),
        }

    # --- A9: font families in generators -------------------------------------
    for sp in sorted(glob.glob(os.path.join(SCRIPTS, "*.py"))):
        src = open(sp, encoding="utf-8", errors="replace").read()
        for fam in re.findall(r"(?:font-family|family)\s*[:=]\s*[\"']([^\"']+)[\"']", src):
            for one in fam.split(","):
                one = one.strip().strip("'\"").lower()
                if not one or one in GENERIC or one in ALLOWED_FONTS:
                    continue
                if one.startswith(("var(", "{", "$")) or "wght@" in one:
                    continue
                fail(f"A9 {os.path.basename(sp)}: font family {one!r} outside "
                     f"{sorted(ALLOWED_FONTS)}", warns)

    # --- A10: desktop parity vs baseline -------------------------------------
    if write_baseline:
        json.dump(counts, open(BASELINE, "w", encoding="utf-8"), indent=1, sort_keys=True)
        print(f"baseline written: {BASELINE} ({len(counts)} pages)")
    elif os.path.exists(BASELINE):
        base = json.load(open(BASELINE, encoding="utf-8"))
        for name, cur in counts.items():
            old = base.get(name)
            if old is None:
                fail(f"A10 {name}: new page, not in baseline", warns); continue
            for k in ("charts", "tables", "tiles"):
                if old[k] != cur[k]:
                    fail(f"A10 {name}: {k} {old[k]} -> {cur[k]}", errs)
        for name in base:
            if name not in counts:
                fail(f"A10 {name}: page disappeared", errs)
    else:
        fail("A10 no baseline -- run with --write-baseline once on a known-good build", warns)

    try:
        remake_gate(errs, warns)
    except Exception as e:                      # a gate that cannot run is a failure, not a pass
        fail(f"R* remake gate could not run: {type(e).__name__}: {e}", errs)

    print(f"pages checked: {len(counts)}  "
          f"(styled {len(counts)-len([p for p in counts if p in STUBS])}, stubs {len(STUBS)})")
    for w in warns:
        print(f"  WARN  {w}")
    for e in errs:
        print(f"  FAIL  {e}")
    print("=" * 60)
    print("DS STATIC GATE:", "PASS" if not errs else f"FAIL ({len(errs)})")
    return 1 if errs else 0



# =====================================================================================================
# 2026-11-10 remake ("Editorial Terminal" + the Research corner): static assertions on the RENDERED pages.
#   R1  every styled page carries the full header: every main tab and every Research-corner link
#       (glossary.MAIN_TABS / RESEARCH_LINKS), exactly once each, in a details.rc menu inside the "Research"
#       navigation landmark; and every page under docs/ (+ archive/) is reachable: a main tab, a Research-corner
#       page, a declared sub-page (glossary.SUBPAGES) or a redirect stub (round 1, P9)
#   R2  no page links to the held Street LTCMA page while its public JSON is absent (street.hold); and (addendum
#       2026-11-10, Carlos, written) no public file under docs/ names a denylisted private source or script
#       (PRIVATE_NAMES, case-insensitive: every .html / .txt / .css / .js / .json / .xml under docs/, archive/ included)
#   R3  every image hero has its picture AND a visible credit line (credit + CC BY 4.0 + source link);
#       a hero rendered without its image (hero--plain) fails; every page that shows an image prints the
#       credit in its footer too
#   R4  every asset a page references exists in docs/assets/img, is byte-identical to assets/img, is
#       referenced (nothing unreferenced is published), is <= 1.2 MB, the phone source is <= 200 KB
#   R5  no published JPEG / WebP carries EXIF, XMP, IPTC or a comment block
#   R6  the home summary: its build-time self-consistency checks ran (meta), and each figure equals the page
#       it summarises (portfolio tiles + the hero panel + the Hold prose, the Fed-path rows + the Watch lines,
#       the Congress badges / sector flows / hub count, the Market Intel firm count, the findings count, the
#       regime, the snapshot tiles, the published picks list). Round 1 (P2 / DATA-1): a pair whose two pages
#       were built from DIFFERENT data (Fed prices, Congress file, consensus edition, picks session, sidecar)
#       is a WARN naming both dates, never a silent pass and never a false failure
#   R7  the Research Library: every item resolves to an existing page / anchor, every published research
#       page is indexed, the counts reconcile, every listed source's evidence holds, and the page lists
#       exactly the items the index builds
#   R8  (wave "no repeats", Carlos 2026-11-10: "intenta que no se repita info en la misma pestana") no page shows the
#       same headline figure twice in one view (phone / desktop x the MXN / USD states): scripts/fig_repeats.py reads
#       every visible figure with its component, and a figure in a headline component (hero stat / panel, tile,
#       card, badge, bar list, lede) that appears again in another headline component or in prose of the same page,
#       or a bar list that restates its own table, is a FAIL unless fig_repeats.ALLOW lists it with a reason
# =====================================================================================================
import hashlib
import struct

LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
# round 1 (V3): the phone source is now a 9:16 portrait WebP (720 / 1080); the 1080 Pillars crops are ~230 KB
IMG_MAX, LCP_MAX = 1_200_000, 250_000


def _scripts_import():
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import glossary
    import research_index
    return glossary, research_index


# R2 denylist (addendum 2026-11-10, Carlos, written): names of the private research stack that must never reach a
# public file. "dukascopy" = a market-data vendor (cards and report pages scrub it at render time:
# glossary.bt_scrub_vendor); "macro_event_study" = a private research script (regime.html's Tactical Overlay note).
# Add a name here and the gate fails wherever it appears; FxPro / MetaTrader are an open question, not listed.
PRIVATE_NAMES = ("dukascopy", "macro_event_study")
_PN_EXT = (".html", ".htm", ".txt", ".css", ".js", ".json", ".xml")


def private_name_checks(docs=None):
    """R2 denylist over every public text file under docs/ (recursive). Returns the failure lines."""
    docs = docs or DOCS
    rx = re.compile("|".join(re.escape(n) for n in PRIVATE_NAMES), re.I)
    out = []
    for dp, dn, fns in os.walk(docs):
        dn.sort()
        for fn in sorted(fns):
            if not fn.lower().endswith(_PN_EXT):
                continue
            p = os.path.join(dp, fn)
            hits = sorted({m.group(0).lower() for m in rx.finditer(open(p, encoding="utf-8", errors="replace").read())})
            if hits:
                out.append(f"R2 {os.path.relpath(p, docs).replace(os.sep, '/')}: names a private source / script "
                           f"{hits} (denylist ds_gate.PRIVATE_NAMES) -- scrub it in the generator")
    return out


def _all_pages():
    out = pages()
    ad = os.path.join(DOCS, "archive")
    if os.path.isdir(ad):
        out += sorted(glob.glob(os.path.join(ad, "*.html")))
    return out


def _jpeg_meta(b):
    out, i = [], 2
    while i + 4 <= len(b) and b[i] == 0xFF:
        m = b[i + 1]
        if m in (0xD9, 0xDA):
            break
        ln = struct.unpack(">H", b[i + 2:i + 4])[0]
        seg = b[i + 4:i + 2 + ln]
        if (m == 0xE1 and (seg[:6] == b"Exif\x00\x00" or seg[:4] == b"http")) or m in (0xED, 0xFE):
            out.append(hex(m))
        i += 2 + ln
    return out


def _webp_meta(b):
    out, i = [], 12
    while i + 8 <= len(b):
        tag, ln = b[i:i + 4], struct.unpack("<I", b[i + 4:i + 8])[0]
        if tag in (b"EXIF", b"XMP "):
            out.append(tag.decode())
        i += 8 + ln + (ln & 1)
    return out


def remake_gate(errs, warns):
    g, ri = _scripts_import()
    want_tabs = [h for h, _t in g.MAIN_TABS]
    want_rc = [h for h, _t, _d in g.RESEARCH_LINKS]
    street_live = os.path.exists(os.path.join(ROOT, "data", "market_intel", "street_ltcma_public.json"))
    refs, n_hdr, n_hero = {}, 0, 0
    reach = {h.split("#")[0] for h in want_tabs + want_rc}
    for p in _all_pages():
        name = os.path.relpath(p, DOCS).replace("\\", "/")
        html = open(p, encoding="utf-8", errors="replace").read()
        base = os.path.basename(p)
        # R1 reachability: a page nobody can reach from the header is a dead end (or an orphan someone forgot)
        if base not in STUBS and name not in reach and not any(re.fullmatch(rx, name) for rx, _par in g.SUBPAGES):
            fail(f"R1 {name}: not a main tab, not in the Research corner, not a declared sub-page (glossary.SUBPAGES) "
                 "and not a redirect stub -- add it to the header or delete it", errs)
        # R1 header
        if base not in STUBS:
            nav = re.search(r'<nav class="tabs" aria-label="Main">(.*?)</nav>', html, re.S)
            rc = re.search(r'<details class="rc">(.*?)</details>', html, re.S)
            if not nav or not rc:
                fail(f"R1 {name}: header without {'the main tabs' if not nav else 'the Research corner'}", errs)
            elif '<div class="rcn" role="navigation" aria-label="Research"><details class="rc">' not in html:
                fail(f"R1 {name}: the Research corner is not inside its navigation landmark", errs)
            else:
                n_hdr += 1
                tabs = re.findall(r'href="([^"]+)"', nav.group(1))
                rcs = re.findall(r'href="([^"]+)"', rc.group(1))
                if tabs != want_tabs:
                    fail(f"R1 {name}: main tabs {tabs} != {want_tabs}", errs)
                if rcs != want_rc:
                    fail(f"R1 {name}: Research corner {rcs} != {want_rc}", errs)
        # R2 Street held
        if not street_live and "street-ltcma" in html:
            fail(f"R2 {name}: links to street-ltcma while Street LTCMA is held", errs)
        # R3 heroes + credits
        for sec in re.findall(r'<section class="hero hero--img[^"]*"[^>]*>.*?</section>', html, re.S):
            n_hero += 1
            if "hero--plain" in sec.split(">", 1)[0] or "<picture" not in sec:
                fail(f"R3 {name}: image hero rendered WITHOUT its image (assets/ missing?)", errs)
                continue
            cr = re.search(r'<p class="container hero-credit">(.*?)</p>', sec, re.S)
            if not cr or "CC BY 4.0" not in cr.group(1) or LICENSE_URL not in cr.group(1) or "esawebb.org" not in cr.group(1):
                fail(f"R3 {name}: hero without a full credit line (credit, CC BY 4.0, licence + source links)", errs)
        uses = set(re.findall(r'assets/img/([A-Za-z0-9_.\-]+)', html))
        for u in uses:
            refs.setdefault(u, set()).add(name)
        if any(u.startswith("hero_") for u in uses) and not re.search(r'<p class="credits">.*?CC BY 4\.0', html, re.S):
            fail(f"R3 {name}: shows a JWST image but its footer carries no credit", errs)
        if any(u.startswith("carlos_duarte") for u in uses) and 'alt="Carlos Duarte"' not in html:
            fail(f"R3 {name}: the photo has no alt text", errs)
        # LCP source: EVERY candidate of the phone <source> of every hero
        for ss in re.findall(r'<source type="image/webp" media="\(max-width: \d+px\)" srcset="([^"]+)"', html):
            for lcp in re.findall(r"assets/img/([^ ,\"]+)", ss):
                f = os.path.join(DOCS, "assets", "img", lcp)
                if os.path.exists(f) and os.path.getsize(f) > LCP_MAX:
                    fail(f"R4 {name}: phone hero {lcp} is {os.path.getsize(f):,} B > {LCP_MAX:,}", errs)
    # R2 denylist: no private source / script name in any public file
    for e in private_name_checks(DOCS):
        fail(e, errs)
    # R4 assets
    pub = os.path.join(DOCS, "assets", "img")
    src = os.path.join(ROOT, "assets", "img")
    have = set(os.listdir(pub)) if os.path.isdir(pub) else set()
    for u in sorted(refs):
        if u not in have:
            fail(f"R4 assets/img/{u} referenced by {sorted(refs[u])} but not published", errs)
    for f in sorted(have):
        pf = os.path.join(pub, f)
        if f not in refs:
            fail(f"R4 docs/assets/img/{f} is published but no page references it", errs)
        if os.path.getsize(pf) > IMG_MAX:
            fail(f"R4 docs/assets/img/{f} is {os.path.getsize(pf):,} B > {IMG_MAX:,}", errs)
        sf = os.path.join(src, f)
        if not os.path.exists(sf):
            fail(f"R4 docs/assets/img/{f} has no source under assets/img", errs)
        elif hashlib.md5(open(sf, "rb").read()).hexdigest() != hashlib.md5(open(pf, "rb").read()).hexdigest():
            fail(f"R4 docs/assets/img/{f} differs from assets/img/{f}", errs)
        # R5 metadata
        b = open(pf, "rb").read()
        meta = _jpeg_meta(b) if f.lower().endswith((".jpg", ".jpeg")) else (_webp_meta(b) if f.lower().endswith(".webp") else [])
        if meta:
            fail(f"R5 docs/assets/img/{f} carries metadata blocks {meta}", errs)
    # R6 home summary vs the pages it summarises
    n6 = _summary_checks(errs, warns)
    # R7 research library
    n7 = _library_checks(ri, errs, warns)
    # R8 no repeated figure on a page
    n8p, n8f = _repeat_checks(errs, warns)
    # R9 dark mode (static half; the browser half is tools/theme_browser_check.js)
    n9 = _theme_checks(errs, warns)
    print(f"remake gate: {n_hdr} headers, {n_hero} image heroes, {len(have)} published images "
          f"({sum(os.path.getsize(os.path.join(pub, f)) for f in have):,} B), {n6} summary pairs, {n7} library items, "
          f"{n8p} pages / {n8f} counted figures checked for repeats, {n9}")


def _read(name):
    try:
        return open(os.path.join(DOCS, name), encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def _meta_asof(html):
    m = re.search(r'<meta name="ltcma-content-asof" content="(\d{4}-\d{2}-\d{2})"', html)
    return m.group(1) if m else ""


def _summary_checks(errs, warns):
    """R6. Every figure the home restates is compared with the page that publishes it -- but only when both pages
    were built from the SAME data (round 1: market-intel-daily refreshes the Fed prices at 16:45, after the 16:31
    home build; the congress file can change at 08:00; the picks list after 17): a pair from two vintages is a WARN
    that names both dates. A figure the home shows with no counterpart found on its page is a FAIL."""
    import html as _h
    from datetime import datetime
    ix, n = _read("index.html"), 0
    m = re.search(r'<meta name="ltcma-summary-checks" content="(\d+) self-consistency checks passed at build">', ix)
    if not m or int(m.group(1)) == 0:
        fail("R6 index.html: no record that the summary's build-time self-consistency checks ran", errs)
    sv = dict(re.findall(r'data-sum="([^"]+)">([^<]+)<', ix))

    def same(key, val, other, what):
        nonlocal n
        n += 1
        if val != other:
            fail(f"R6 index {key} {val!r} != {what} {other!r}", errs)

    # ---- Hold card, hero panel, Hold prose, Portfolio hub = the portfolio tiles (same sidecar vintage)
    pf = _read("portfolio.html")
    asof = re.search(r'data-sum-asof="([^"]+)"', ix)
    pfa = re.search(r"Performance as of (\d{4}-\d{2}-\d{2})", pf)
    if asof and pfa and asof.group(1) == pfa.group(1):
        tiles = {k: (u, m) for m, u, k in re.findall(r'<div class="mv"><span class="cval" data-mxn="([^"]*)" data-usd="([^"]+)">'
                                                     r'[^<]*</span></div><div class="mk">([^<]+)</div>', pf)}
        for key, lab in (("twrr", "TWRR"), ("spy", "S&amp;P 500"), ("mwrr", "MWRR"), ("alpha", "vs index")):
            same(f"{key}_usd", sv.get(f"{key}_usd"), (tiles.get(lab) or (None, None))[0], f"portfolio.html tile {lab} (USD)")
            # wave "no repeats" (2026-11-10): the Hold card also carries the peso row of the old Live Portfolio section
            if f"{key}_mxn" in sv:
                same(f"{key}_mxn", sv.get(f"{key}_mxn"), (tiles.get(lab) or (None, None))[1],
                     f"portfolio.html tile {lab} (MXN)")
        # the Portfolio hub card counts the open positions = the rows of portfolio.html's Holdings table
        if "hub:portfolio.html" in sv:
            body = re.search(r'<tbody id="h-body">(.*?)</tbody>', pf, re.S)
            same("Portfolio hub", sv["hub:portfolio.html"],
                 f"{len(re.findall(r'<tr>', body.group(1)))} holdings" if body else None,
                 "the rows of portfolio.html's Holdings table")
        # the home's USD / MXN tile reads the same sidecar rate as portfolio.html's Performance stamp
        fx = re.search(r"Performance as of \d{4}-\d{2}-\d{2}.*?USD/MXN\s+(\d+\.\d+)", pf, re.S)
        if "mk:USD / MXN" in sv:
            same("Today USD / MXN", sv["mk:USD / MXN"], f"{float(fx.group(1)):.2f}" if fx else None,
                 "portfolio.html's USD/MXN (Performance stamp)")
    elif asof:
        fail(f"R6 index.html Hold card from {asof.group(1)}, portfolio.html from "
             f"{pfa.group(1) if pfa else '?'}: re-render both", warns)
    for key in ("twrr_usd", "spy_usd", "mwrr_usd", "alpha_usd"):
        if f"hp:{key}" in sv:
            same(f"hero panel {key}", sv[f"hp:{key}"], sv.get(key), "the Hold card")
    if "hold:twrr_abs" in sv:
        same("Hold prose TWRR", sv["hold:twrr_abs"], (sv.get("twrr_usd") or "").lstrip("+-"), "the Hold card")
    if "hold:gap" in sv:
        same("Hold prose gap", sv["hold:gap"], (sv.get("alpha_usd") or "").replace(" pp", "").lstrip("+-"), "the Hold card")

    # ---- Fed: the rows of the Fed view and the Watch lines = Market Intel's Fed-path table and its head line
    mi = _read("ltcma-consensus.html")
    fh = re.search(r'data-fed-taken="(\d{4}-\d{2}-\d{2})"', ix)
    fm = re.search(r"Fed path, meeting by meeting.*?Market prices from (\d{4}-\d{2}-\d{2})", mi, re.S)
    has_fed = "fed_next" in sv or any(k.startswith("fed:") for k in sv)
    if has_fed and not (fh and fm):
        fail(f"R6 index Fed figures without a price date on {'the home' if not fh else 'Market Intel'}", errs)
    elif has_fed and fh.group(1) != fm.group(1):
        fail(f"R6 Fed: home prices from {fh.group(1)}, Market Intel prices from {fm.group(1)} (the 16:45 job ran "
             "after the home was built; both dated on the page, compared once they match)", warns)
    elif has_fed:
        def mi_row(meet):
            r = re.search(re.escape(f'<td class="a">{meet} <span class="cv">') + r'[^<]*</span>(?:\s*<span[^>]*>[^<]*</span>)?</td>'
                          r'<td class="v">([^<]+)</td><td class="v"><b>([^<]+)</b></td><td class="v">([^<]+)</td>', mi)
            return r.groups() if r else None
        nxt = None
        for meet, txt in re.findall(r'<div class="fedrow" data-sum="fed:([^"]+)">.*?<span class="t">([^<]+)</span>', ix, re.S):
            if "/" not in txt:                  # wave "no repeats": the next meeting's odds are in the Watch line
                nxt = meet
                continue
            c, h, k = [x.strip() for x in txt.split("/")]
            n += 1
            if mi_row(meet) != (c, h, k):
                fail(f"R6 index Fed {meet} {txt!r} not the Market Intel row {mi_row(meet)}", errs)
        # the Watch line (the top outcome + the other two) = the Market Intel hero stat and its Fed-table row
        wn = re.search(r'<span>(\w+) at the next FOMC \(([^)]+)\)(?:<em class="wsub" data-sum="fed_next_rest">([^<]+)</em>)?'
                       r'</span><b[^>]*data-sum="fed_next">([^<]+)<', ix)
        hs = re.search(r'<span class="v[^"]*">(\d+%)</span><span class="l">odds of a (\w+) at the ([^<,]+?) FOMC', mi)
        if wn:
            n += 1
            if not hs or (wn.group(1).lower(), wn.group(2), wn.group(4)) != (hs.group(2).lower(), hs.group(3), hs.group(1)):
                fail(f"R6 index Watch next FOMC {wn.groups()} != Market Intel hero {hs.groups() if hs else None}", errs)
            if wn.group(3) and nxt:
                n += 1
                got = dict(x.strip().split(" ", 1) for x in _h.unescape(wn.group(3)).split("\u00b7"))
                got[wn.group(1).lower()] = wn.group(4)
                if mi_row(nxt) != (got.get("cut"), got.get("hold"), got.get("hike")):
                    fail(f"R6 index Watch {nxt} {got} not the Market Intel row {mi_row(nxt)}", errs)
        ff = re.search(r'more likely than not: ([^<]+)</span><b data-sum="fed_first">(\w+)(?: (\d+%))?<', ix)
        if ff:
            n += 1
            mf = re.search(r"The first meeting where a move is more likely than not is <b>([^<]+)</b>: a <b>(\w+)</b>(?: at (\d+%))?", mi)
            if not mf or (ff.group(1).strip(), ff.group(2), ff.group(3)) != (mf.group(1), mf.group(2), mf.group(3)):
                fail(f"R6 index Watch first move {ff.groups()} != Market Intel {mf.groups() if mf else None}", errs)

    # ---- Market Intel hub: firm count = the Market Intel lede (same consensus edition)
    if "hub:ltcma-consensus.html" in sv:
        run = re.search(r'data-cons-run="(\d{4}-\d{2}-\d{2})"', ix)
        lede = re.search(r'<span class="v[^"]*">(\d+)</span><span class="l">asset managers and banks in the consensus', mi)
        if run and run.group(1) != _meta_asof(mi):
            fail(f"R6 Market Intel hub: consensus of {run.group(1)}, page of {_meta_asof(mi)} (compared once they match)", warns)
        else:
            same("Market Intel hub", sv["hub:ltcma-consensus.html"], f"{lede.group(1)} firms" if lede else None,
                 "the Market Intel hero count")

    # ---- Congress: badges, 91-day flows and the hub count = the congress page (same file)
    cg = _read("congressional-activity.html")
    ch = re.search(r'data-cg-asof="(\d{4}-\d{2}-\d{2})"', ix)
    has_cg = any(k.startswith(("cg:", "flow:")) for k in sv) or "hub:congressional-activity.html" in sv
    if has_cg and ch and ch.group(1) != _meta_asof(cg):
        fail(f"R6 Congress: home built from the file of {ch.group(1)}, the page from {_meta_asof(cg)} "
             "(compared once they match)", warns)
    elif has_cg:
        for t, lab in (("LARGE", "trades over $500K"), ("OPTIONS", "option trades"), ("LATE", "filed more than 45 days late")):
            if f"cg:{t}" in sv:
                b = re.search(r'<span class="v">(\d+)</span><span class="l">' + re.escape(lab) + "<", cg)
                same(f"Congress {t}", sv[f"cg:{t}"], b.group(1) if b else None, "the page's hero count")
        win = cg[cg.find('id="win-91d"'):] if 'id="win-91d"' in cg else cg
        for sec_, val in re.findall(r'<div class="flow" data-sum="flow:([^"]+)">.*?<span class="v">([^<]+)</span>', ix, re.S):
            n += 1
            # wave "no repeats": the Net cell carries its bar and sits right after Sector
            if not re.search(r'<td class="a">' + re.escape(sec_) + r'</td><td class="v nb"><span class="nbar"[^>]*>.*?</span></span>'
                             r'<b>' + re.escape(val) + "</b></td>", win):
                fail(f"R6 index Congress flow {sec_} {val!r} not on the page's 91-day table", errs)
        if "hub:congressional-activity.html" in sv:
            hs = re.search(r'<span class="v">([0-9,]+)</span><span class="l">trades filed in the last 13 weeks', cg)
            same("Congress hub", sv["hub:congressional-activity.html"], f"{hs.group(1)} trades" if hs else None,
                 "the congress hero count")

    # ---- Research Library hub: the findings count = the finding cards on Research Notes
    if "hub:research-library.html" in sv:
        n_cards = len(re.findall(r'<article id="f[0-9]+"', _read("research.html")))
        same("Research hub", sv["hub:research-library.html"], f"{n_cards} findings", "the findings on research.html")

    # ---- regime (Watch line + hub) = regime.html
    rg = _read("regime.html")
    if "regime" in sv:
        n += 1
        st = _h.unescape(sv["regime"]).split("·")[0].strip()
        z = re.search(r'([+\-−]\d+\.\d\d)', sv["regime"].replace("&sigma;", ""))
        if st.upper() not in rg.upper() or (z and z.group(1) not in rg):
            fail(f"R6 index regime {sv['regime']!r} not what regime.html shows", errs)
    if "hub:regime.html" in sv:
        n += 1
        mo = re.search(r'<div class="mv">(\d+)</div><div class="mk">Months in Regime</div>', rg)
        hm = re.match(r"(\d+) months?$", sv["hub:regime.html"])
        if not (mo and hm and mo.group(1) == hm.group(1)):
            fail(f"R6 Regime hub {sv['hub:regime.html']!r} not regime.html's months in regime "
                 f"{mo.group(1) if mo else None!r}", errs)

    # ---- (wave "no repeats", 2026-11-10) the Market Snapshot section was merged into the Today view: its tiles had
    # no counterpart but their own copy on the home, so those same-page pairs are gone; USD / MXN is compared with
    # portfolio.html above. If the Markets view is ever left out, 17 renders the full snapshot section instead.

    # ---- picks + the Stock Research hub (only when the stocks page shows the same session)
    ses = re.search(r'data-sum-session="(\d{4}-\d{2}-\d{2})"', ix)
    st_html = _read("stocks.html")
    sa = re.search(r'class="asof">As of (\d{2} \w{3} \d{4})', st_html)
    if ses and sa:
        if datetime.strptime(sa.group(1), "%d %b %Y").date().isoformat() == ses.group(1):
            listed = re.findall(r'<td class="rk">(\d+)</td><td><b>([A-Z.\-]+)</b> <span class="pick-star"', st_html)
            mine = re.findall(r'data-sum="pick:(\d+)"><span class="r">[^<]*</span><span class="t">([^<]+)</span>', ix)
            n += 1
            if listed[:5] != mine:
                fail(f"R6 index picks {mine} != stocks.html {listed[:5]}", errs)
            if "hub:stocks.html" in sv:
                same("Stock Research hub", sv["hub:stocks.html"], f"{len(listed)} picks", "the list on stocks.html")
        else:
            fail(f"R6 picks: home list of {ses.group(1)}, stocks.html {sa.group(1)} (one-session lag, compared next run)", warns)
    return n


def _library_checks(ri, errs, warns):
    lib = _read("research-library.html")
    if not lib:
        fail("R7 research-library.html missing", errs)
        return 0
    items = ri.build_items()
    for pbm in ri.check_items(items):
        fail(f"R7 {pbm}", errs)
    for s, ok, why in ri.check_sources():
        if not ok:
            fail(f"R7 source {s[0]}: {why}", errs)
    ids = re.findall(r'<li class="lib-item" id="i-([^"]+)"', lib)
    if sorted(ids) != sorted(it["id"] for it in items):
        fail(f"R7 the page lists {len(ids)} items, the index builds {len(items)}", errs)
    for h in re.findall(r'<a class="li-title" href="([^"]+)"', lib):
        rel, _, anc = h.partition("#")
        tgt = _read(rel)
        if not tgt or (anc and f'id="{anc}"' not in tgt):
            fail(f"R7 library link {h} does not resolve", errs)
    if 'id="sources"' not in lib:
        fail("R7 research-library.html has no #sources section", errs)
    return len(ids)


def _repeat_checks(errs, warns):
    """R8. Every page under docs/ (redirect stubs skipped): a headline figure shown twice in one view FAILs."""
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import fig_repeats
    e8, w8, npg, nfig = fig_repeats.gate(DOCS)
    for e in e8:
        fail(e, errs)
    for w in w8:
        fail(w, warns)
    return npg, nfig


def _theme_checks(errs, warns):
    """R9. tools/theme_gate.py's static rules T1-T7 over docs/ (each finding prefixed R9)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("theme_gate", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                       "theme_gate.py"))
    tg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tg)
    e9, w9, info = [], [], []
    pages = tg.check_pages(DOCS, e9, w9, info)
    tg.check_palette(DOCS, pages, e9, w9, info)
    tg.check_tokens(e9, info)
    for e in e9:
        fail("R9 " + e, errs)
    for w in w9:
        fail("R9 " + w, warns)
    return "dark mode: " + "; ".join(info)


def rules_gate():
    """R1-R9 only (scripts/guard_site_rules.py runs this in the refresh, after step 31). The static S / A rules stay
    in the full gate: A10 parity moves legitimately with content and is re-based by hand."""
    errs, warns = [], []
    try:
        remake_gate(errs, warns)
    except Exception as e:                      # a gate that cannot run is a failure, not a pass
        fail(f"R* site rules could not run: {type(e).__name__}: {e}", errs)
    for w in warns:
        print(f"  WARN site rules: {w}")
    for e in errs:
        print(f"  FAIL  {e}")
    print("SITE RULES (R1-R9):", "PASS" if not errs else f"FAIL ({len(errs)})")
    return 1 if errs else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--rules-only", action="store_true", help="R1-R9 only (what the refresh runs)")
    a_ = ap.parse_args()
    sys.exit(rules_gate() if a_.rules_only else static_gate(a_.write_baseline))
