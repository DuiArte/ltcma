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
#       credit in its footer too. Wave r3 (builder B, Carlos 2026-11-10 "Dale play a todo"): the credit line is
#       checked against assets/credits.json (title, the source page's credit verbatim, the licence and -- when it
#       has one -- its link, the source page on an allowed host: esawebb.org / nasa.gov), the footer carries the
#       SAME line, every page shows its own photograph (design_system.PAGE_HEROES; the stock pages share Stock
#       Research's), no two pages share one, and the retired keys (RETIRED_HERO_KEYS) are gone from assets/ and docs/
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
#   (R9 dark mode, R10 share head, R11 the On-this-page bar: see their functions below)
#   R12 (wave r3, builder C) Congress grouped by filing (the data file's filings, whole, every trade in the HTML),
#       the Stock Research phone cards (each cell labelled with its column header) and the fitted Pick Tracker
#       (column priorities, one rank sparkline per row agreeing with the row's rank): _table_checks
# =====================================================================================================
import hashlib
import struct
from urllib.parse import urlparse

LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
# round 1 (V3): the phone source is now a 9:16 portrait WebP (720 / 1080); the 1080 Pillars crops are ~230 KB
IMG_MAX, LCP_MAX = 1_200_000, 250_000


def _scripts_import():
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import glossary
    import research_index
    return glossary, research_index


def _ds():
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import design_system
    return design_system


# R3 (wave r3): the hosts a hero's source page may sit on (the licence is read per key from assets/credits.json)
HERO_HOSTS = ("esawebb.org", "www.nasa.gov", "nasa.gov", "science.nasa.gov", "images.nasa.gov")


def _hero_credit_checks(name, sec, html, ds, errs, used):
    """R3 (wave r3): one image hero section of page `name` against credits.json and PAGE_HEROES."""
    import html as _h
    key = re.search(r'data-hero="([^"]+)"', sec.split(">", 1)[0])
    key = key.group(1) if key else ""
    base = name.split("/")[-1]
    want = ds.page_hero(base)
    if not want:
        fail(f"R3 {name}: an image hero on a page without a photograph of its own (design_system.PAGE_HEROES)", errs)
    elif key != want[0]:
        fail(f"R3 {name}: shows the photograph {key!r}, its own is {want[0]!r} (design_system.PAGE_HEROES)", errs)
    if key in ds.RETIRED_HERO_KEYS:
        fail(f"R3 {name}: shows the retired photograph {key!r}", errs)
    used.setdefault(key, set()).add(base)
    c = (ds._credits().get("heroes") or {}).get(key)
    cr = re.search(r'<p class="container hero-credit">(.*?)</p>', sec, re.S)
    if not c:
        fail(f"R3 {name}: hero {key!r} has no entry in assets/credits.json", errs)
        return
    if not cr:
        fail(f"R3 {name}: hero without a credit line", errs)
        return
    line = cr.group(1)
    lu = c.get("license_url", LICENSE_URL if c.get("license") == "CC BY 4.0" else None)
    miss = [w for w, ok in (("title", _h.escape(c["title"], quote=True) in line),
                            ("credit", _h.escape(c["credit"], quote=True) in line),
                            ("licence", _h.escape(c["license"], quote=True) in line),
                            ("licence link", (not lu) or f'href="{lu}"' in line),
                            ("source link", f'href="{c["source"]}"' in line),
                            ("'cropped'", ", cropped" in line)) if not ok]
    if c.get("license") == "CC BY 4.0" and lu != LICENSE_URL:
        miss.append("CC BY 4.0 licence link")
    if urlparse(c["source"]).hostname not in HERO_HOSTS:
        miss.append(f"source host {urlparse(c['source']).hostname!r} not in {HERO_HOSTS}")
    if miss:
        fail(f"R3 {name}: hero credit line lacks {', '.join(miss)} (assets/credits.json {key!r})", errs)
    foot = re.search(r'<p class="credits">(.*?)</p>', html, re.S)
    if not foot or ds.hero_credit(key) not in foot.group(1):
        fail(f"R3 {name}: the footer does not carry the hero's credit line", errs)


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
    ds, used = _ds(), {}
    reach = {h.split("#")[0] for h in want_tabs + want_rc}
    for p in _all_pages():
        name = os.path.relpath(p, DOCS).replace("\\", "/")
        html = open(p, encoding="utf-8", errors="replace").read()
        base = os.path.basename(p)
        # R1 reachability: a page nobody can reach from the header is a dead end (or an orphan someone forgot)
        if base not in STUBS and name not in reach and name not in ERROR_PAGES \
                and not any(re.fullmatch(rx, name) for rx, _par in g.SUBPAGES):
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
            _hero_credit_checks(name, sec, html, ds, errs, used)
        uses = set(re.findall(r'assets/img/([A-Za-z0-9_.\-]+)', html))
        for u in uses:
            refs.setdefault(u, set()).add(name)
        if any(u.startswith("hero_") for u in uses) and not re.search(r'<p class="credits">.+?</p>', html, re.S):
            fail(f"R3 {name}: shows a hero image but its footer carries no credit", errs)
        # wave r3: a page with a photograph of its own shows it (a hero that lost its image fails above)
        if ds.page_hero(base) and 'data-hero="' not in html and base not in STUBS:
            fail(f"R3 {name}: has a photograph of its own ({ds.page_hero(base)[0]}) but no image hero", errs)
        if any(u.startswith("carlos_duarte") for u in uses) and 'alt="Carlos Duarte"' not in html:
            fail(f"R3 {name}: the photo has no alt text", errs)
        # LCP source: EVERY candidate of the phone <source> of every hero
        for ss in re.findall(r'<source type="image/webp" media="\(max-width: \d+px\)" srcset="([^"]+)"', html):
            for lcp in re.findall(r"assets/img/([^ ,\"]+)", ss):
                f = os.path.join(DOCS, "assets", "img", lcp)
                if os.path.exists(f) and os.path.getsize(f) > LCP_MAX:
                    fail(f"R4 {name}: phone hero {lcp} is {os.path.getsize(f):,} B > {LCP_MAX:,}", errs)
    # R3 (wave r3): one photograph per page -- no two pages share a key, except the stock pages, which share Stock
    # Research's; the retired keys left assets/ and docs/
    for k, pgs in sorted(used.items()):
        own = {p for p in pgs if not re.fullmatch(ds.STOCK_PAGE, p)}
        if len(own) > 1:
            fail(f"R3 the photograph {k!r} is shown by {sorted(own)}: one photograph per page", errs)
    for d_ in (os.path.join(ROOT, "assets", "img"), os.path.join(DOCS, "assets", "img")):
        if os.path.isdir(d_):
            for f in sorted(os.listdir(d_)):
                if any(f.startswith(f"hero_{k}_") for k in ds.RETIRED_HERO_KEYS):
                    fail(f"R3 {os.path.relpath(os.path.join(d_, f), ROOT)}: a retired photograph's file is still there", errs)
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
        if f.lower().endswith(".png"):           # wave r3: the favicon / card PNGs and the SVG mark
            meta = _png_meta(b)
        elif f.lower().endswith(".svg"):
            meta = _svg_meta(b)
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
    # R10 share head, 404 / sitemap / robots, Plotly bundle, one Fed vintage, Congress money (wave r3)
    n10 = _share_checks(errs, warns)
    # R11 the "On this page" bar + note() (wave r3, builder B)
    n11 = _bar_checks(errs, warns)
    # R12 Congress grouped by filing, the Stock Research phone cards + the fitted Pick Tracker (wave r3, builder C)
    n12 = _table_checks(errs, warns)
    print(f"remake gate: {n_hdr} headers, {n_hero} image heroes, {len(have)} published images "
          f"({sum(os.path.getsize(os.path.join(pub, f)) for f in have):,} B), {n6} summary pairs, {n7} library items, "
          f"{n8p} pages / {n8f} counted figures checked for repeats, {n9}; R10: {n10} pages with a share head; "
          f"R11: {n11}; R12: {n12}")


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
            # wave r3 (builder C): the cells carry their column header as data-label (design_system.card_tables)
            listed = re.findall(r'<td class="rk"[^>]*>(\d+)</td><td[^>]*><b>([A-Z.\-]+)</b> <span class="pick-star"', st_html)
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


# =====================================================================================================================
# R10 (wave r3, 2026-11-10; Carlos, written ~15:00, "Dale play a todo"): pages ready to share, the lighter Plotly
# bundle, one Fed-odds vintage, the Congress money format. On the RENDERED pages:
#   - every public page carries ONE share block (design_system.site_head): the title "<Name> · Carlos Duarte" of
#     design_system.page_meta, one description of 50-160 characters, canonical = og:url = its public URL, og:title,
#     og:description, the Twitter card, its 1200 x 630 PNG card (published), the favicon set (published)
#   - 404.html exists, noindex, resolves from the site root (<base href="/ltcma/">); sitemap.xml = what
#     design_system.sitemap_xml writes for this docs/ (every URL an existing page; no stub, no internal/); robots.txt =
#     design_system.ROBOTS_TXT (no path listed)
#   - a page with charts loads exactly one Plotly bundle; the cartesian bundle only when every trace type is in
#     design_system.CARTESIAN_TYPES (a trace of another type would not draw: FAIL); the full bundle on an all-cartesian
#     page is a WARN (a committed copy written before r3)
#   - Market Intel: the hero's Fed date = the Fed path's date; when the Fed path is newer than the consensus run, the
#     Summary does not restate the run's next-FOMC odds
#   - Congress money: no "$-" and no "$0K" on the home or the Congress page
# =====================================================================================================================
ERROR_PAGES = {"404.html"}          # reachable from any missing URL (GitHub Pages serves docs/404.html), never linked


def _png_meta(b):
    """PNG text / EXIF / time chunks (personal or tool metadata); colour chunks are not metadata."""
    out, i = [], 8
    while i + 8 <= len(b):
        n, t = struct.unpack(">I", b[i:i + 4])[0], b[i + 4:i + 8]
        if t in (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"):
            out.append(t.decode("latin-1"))
        i += 12 + n
    return out


def _svg_meta(b):
    s = b.decode("utf-8", "replace").lower()
    return [k for k in ("<metadata", "<!--", "sodipodi", "inkscape", "rdf:", "xmlns:dc") if k in s]


def _png_size(p):
    b = open(p, "rb").read(32)
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", b[16:24])


def _share_checks(errs, warns, body=True):
    """R10. body=False: the head / share files only (the r3 deploy's commit 2 writes the head of committed pages
    whose body the refresh re-renders afterwards)."""
    import html as _h
    _scripts_import()
    import design_system as ds
    n, pub = 0, os.path.join(DOCS, "assets", "img")
    for p in _all_pages():
        name = os.path.relpath(p, DOCS).replace("\\", "/")
        if os.path.basename(p) in STUBS:
            continue
        html = open(p, encoding="utf-8", errors="replace").read()
        # the Plotly bundle
        tags = re.findall(r'<script src="(https://cdn\.plot\.ly/[^"]+)"></script>', html)
        try:
            types = {tr.get("type", "scatter") for _d, data, _l in ds._plotly_calls(html) for tr in data}
        except ValueError as e:
            fail(f"R10 {name}: the chart figures cannot be read ({e})", errs)
            types = set()
        if types:
            if len(tags) != 1:
                fail(f"R10 {name}: {len(tags)} Plotly bundles for {len(types)} trace type(s)", errs)
            elif tags[0] == ds.PLOTLY_CARTESIAN and not types <= ds.CARTESIAN_TYPES:
                fail(f"R10 {name}: the cartesian Plotly bundle with trace type(s) {sorted(types - ds.CARTESIAN_TYPES)} "
                     "it does not register (those charts would not draw)", errs)
            elif tags[0] == ds.PLOTLY_FULL and types <= ds.CARTESIAN_TYPES:
                fail(f"R10 {name}: the full Plotly bundle on an all-cartesian page (a copy written before r3?)", warns)
            elif tags[0] not in (ds.PLOTLY_FULL, ds.PLOTLY_CARTESIAN):
                fail(f"R10 {name}: unknown Plotly bundle {tags[0]}", errs)
        elif tags:
            fail(f"R10 {name}: loads Plotly without a chart", warns)
        # the share head
        pm = ds.page_meta(name, ds.share_strip(html))
        if pm is None:
            fail(f"R10 {name}: no share metadata for this page (design_system.page_meta)", errs)
            continue
        n += 1
        title, _desc, card, path = pm
        if html.count("<!--share") != 1 or html.count("<!--/share-->") != 1:
            fail(f"R10 {name}: share block missing or repeated", errs)
            continue
        # fix round 1 (r3 continuation, V2-11 / V2-12): the r3 head's script (deep links, the skip link) in the block
        blk = re.search(r"<!--share title0=.*?<!--/share-->", html, re.S)
        if not blk or blk.group(0).count(ds.SITE_JS) != 1:
            fail(f"R10 {name}: the r3 head script (design_system.SITE_JS: deep links, skip link, the chart redraw once the "
                 "fonts are in) is not in the share block", errs)
        t = re.findall(r"<title>(.*?)</title>", html, re.S)
        if t != [title]:
            fail(f"R10 {name}: title {t} != {title!r}", errs)
        for rel in ("favicon.svg", "favicon_32.png", "apple_touch_180.png"):
            if f'href="assets/img/{rel}"' not in html or not os.path.isfile(os.path.join(pub, rel)):
                fail(f"R10 {name}: favicon {rel} not linked or not published", errs)
        if name in ERROR_PAGES:
            if '<meta name="robots" content="noindex">' not in html or '<base href="/ltcma/">' not in html:
                fail(f"R10 {name}: the error page must be noindex and resolve from the site root", errs)
            continue
        d = re.findall(r'<meta name="description" content="([^"]*)">', html)
        if len(d) != 1:
            fail(f"R10 {name}: {len(d)} meta descriptions", errs)
        elif not 50 <= len(_h.unescape(d[0])) <= 160:
            fail(f"R10 {name}: description of {len(_h.unescape(d[0]))} characters (50-160)", errs)
        url = f"{ds.SITE_URL}/{path}"
        for k, want in (('<link rel="canonical" href="', url), ('<meta property="og:url" content="', url),
                        ('<meta property="og:title" content="', ds._attr(title))):
            got = re.findall(re.escape(k) + r'([^"]*)"', html)
            if got != [want]:
                fail(f"R10 {name}: {k.split()[1]} {got} != {want!r}", errs)
        if d and f'<meta property="og:description" content="{d[0]}">' not in html:
            fail(f"R10 {name}: og:description is not the page's description", errs)
        if card:
            img = f"{ds.SITE_URL}/{ds.ASSET_URL}/og_{card}.png"
            f = os.path.join(pub, f"og_{card}.png")
            if f'<meta property="og:image" content="{img}">' not in html or \
                    '<meta name="twitter:card" content="summary_large_image">' not in html:
                fail(f"R10 {name}: og:image / twitter card missing", errs)
            elif not os.path.isfile(f) or _png_size(f) != (1200, 630):
                fail(f"R10 {name}: card og_{card}.png not published as a 1200 x 630 PNG", errs)
            # fix round 1 (r3 continuation, V2-9): the alt text says what the card shows
            alt = re.findall(r'<meta property="og:image:alt" content="([^"]*)">', html)
            if card in getattr(ds, "OG_CARD_TEXT", {}) and alt != [ds._attr(ds.og_alt(card))]:
                fail(f"R10 {name}: og:image:alt {alt[:1]} is not what card og_{card}.png shows ({ds.og_alt(card)!r})", errs)
    # the error page, the sitemap, robots.txt
    if not os.path.isfile(os.path.join(DOCS, "404.html")):
        fail("R10 docs/404.html missing (17 writes it: design_system.emit_share)", errs)
    smp = os.path.join(DOCS, "sitemap.xml")
    if not os.path.isfile(smp):
        fail("R10 docs/sitemap.xml missing", errs)
    else:
        sm = open(smp, encoding="utf-8").read()
        if sm != ds.sitemap_xml(DOCS):
            fail("R10 sitemap.xml is not what design_system.sitemap_xml writes for this docs/ (stale?)", errs)
        for u in re.findall(r"<loc>([^<]+)</loc>", sm):
            rel = u[len(ds.SITE_URL) + 1:] or "index.html"
            f = os.path.join(DOCS, *rel.split("/"))
            if not u.startswith(ds.SITE_URL + "/") or not os.path.isfile(f) or rel.startswith("internal/") \
                    or os.path.basename(rel) in STUBS or rel in ERROR_PAGES:
                fail(f"R10 sitemap.xml lists {u}: not a public page in docs/", errs)
    rp = os.path.join(DOCS, "robots.txt")
    if not os.path.isfile(rp) or open(rp, encoding="utf-8").read() != ds.ROBOTS_TXT:
        fail("R10 docs/robots.txt missing or not design_system.ROBOTS_TXT", errs)
    if not body:
        return n
    # Congress money format
    for nm in ("index.html", "congressional-activity.html"):
        h = _read(nm) or ""
        vis = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", h))
        if "$-" in vis or re.search(r"\$0K\b", vis):
            fail(f"R10 {nm}: a dollar amount printed as '$-...' or '$0K' (design_system.money)", errs)
    # one Fed vintage on Market Intel
    mi = _read("ltcma-consensus.html") or ""
    hd = re.search(r"Kalshi prices from (\d{2} \w{3} \d{4})", mi)
    lg = re.search(r"Market prices from (\d{4}-\d{2}-\d{2}), refreshed", mi)
    if hd and lg:
        import datetime as _dt
        if _dt.datetime.strptime(hd.group(1), "%d %b %Y").date().isoformat() != lg.group(1):
            fail(f"R10 ltcma-consensus.html: hero Fed odds from {hd.group(1)}, the Fed path from {lg.group(1)}", errs)
    smr = re.search(r'<section class="block" id="summary">(.*?)</section>', mi, re.S)
    if "with the newer prices of" in mi and smr and re.search(r"next FOMC at \d", smr.group(1)):
        fail("R10 ltcma-consensus.html: the Summary restates the run's older next-FOMC odds", errs)
    for p in fed_vintage_problems(mi):
        fail(f"R10 ltcma-consensus.html: {p}", errs)
    return n


# fix round 1 (r3 continuation, 2026-11-11, DCL-1): when the Fed path's pull is newer than the consensus run (the page
# says "with the newer prices of"), no next-FOMC percentage may stand UNDATED anywhere in the page's main text -- the
# Summary, the divergences, any other consensus-run prose. Left out: the dated snapshot cards and the dated event
# outlook (each carries its own price date); allowed: a figure followed by the run's stamp "(prices of ...)" (what
# 30's _fomc_fix writes for a phrasing it cannot point at the Fed path). A percentage counts as next-FOMC when it sits
# within a short reach of "next FOMC" without a sentence / clause break (". ", "; ", ": ") in between.
_FOMC_NUM = r"\d+(?:\.\d+)?%?(?:\s*[-\u2013]\s*\d+(?:\.\d+)?)?%"
_FOMC_NEAR = re.compile(r"next FOMC(?:(?!\. |; |: ).){0,25}?" + _FOMC_NUM + r"|" + _FOMC_NUM
                        + r"(?:(?!\. |; |: ).){0,32}?next FOMC", re.S)


def fed_vintage_problems(mi):
    import html as _h
    if "with the newer prices of" not in mi:
        return []
    m = re.search(r"<main\b.*?</main>", mi, re.S)
    body = m.group(0) if m else mi
    body = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", body)
    body = re.sub(r'(?s)<div class="odds"[^>]*>.*?</section>', " ", body)        # the dated snapshot cards
    body = re.sub(r'(?s)<table class="mi ol">.*?</table>', " ", body)             # the dated event outlook
    txt = re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", body)))
    out = []
    for mm in _FOMC_NEAR.finditer(txt):
        for k in re.finditer(_FOMC_NUM, mm.group(0)):
            if not txt[mm.start() + k.end():].lstrip().startswith("(prices of "):
                out.append(f"an undated next-FOMC price next to the Fed path's newer pull: '{mm.group(0)[:100]}'")
                break
    return out


_OTP = re.compile(r'<nav class="otp" aria-label="On this page">(.*?)</nav>', re.S)


def _bar_checks(errs, warns):
    """R11 (wave r3, builder B): the sticky "On this page" bar of the long pages and the note() component.
    - every page with sections in design_system.PAGE_SECTIONS (and the archived report) carries exactly ONE bar, right
      before <main>, with >= 2 links, in the table's order, each to an id that is on the page exactly once (the archived
      report's links carry its own path: it has <base href="../">), the script that marks the current section, and no
      other page carries one;
    - portfolio.html: the bar holds the MXN | USD switch and r2's separate .ccy-bar is gone (one sticky strip);
    - note(): every method note has a non-empty <summary>; the portfolio's scaling disclosure is visible (not inside a
      <details>), sits above the first money tile and names no number (it gives no factor)."""
    ds = _ds()
    n_bar = n_note = 0
    for p in _all_pages():
        name = os.path.relpath(p, DOCS).replace("\\", "/")
        html = open(p, encoding="utf-8", errors="replace").read()
        secs = ds.page_sections(name)
        bars = _OTP.findall(html)
        if not secs:
            if bars:
                fail(f"R11 {name}: carries an On-this-page bar but has no sections in design_system.PAGE_SECTIONS", errs)
            continue
        if len(bars) != 1:
            fail(f"R11 {name}: {len(bars)} On-this-page bars (want 1)", errs)
            continue
        n_bar += 1
        m = _OTP.search(html)
        if not re.match(r"\s*<main\b", html[m.end():]):
            fail(f"R11 {name}: the bar is not right before <main>", errs)
        if ds.OTP_JS not in bars[0]:
            fail(f"R11 {name}: the bar's script is missing", errs)
        hrefs = re.findall(r'<li><a href="([^"]+)">', bars[0])
        pre = name if "<base href=" in html[:4000] else ""
        if len(hrefs) < 2:
            fail(f"R11 {name}: the bar links {len(hrefs)} section(s)", errs)
        order = [i for i, _l in secs]
        got = []
        for h in hrefs:
            if not h.startswith(pre + "#"):
                fail(f"R11 {name}: bar link {h!r} does not resolve on this page" + (" (it has <base href>)" if pre else ""), errs)
                continue
            i = h[len(pre) + 1:]
            got.append(i)
            k = len(re.findall(r'\bid="' + re.escape(i) + '"', html))
            if k != 1:
                fail(f"R11 {name}: bar link #{i}: {k} elements carry that id (want exactly 1)", errs)
        if got != [i for i in order if i in got]:
            fail(f"R11 {name}: the bar's links are not in the page table's order", errs)
        missing = [i for i in order if f'id="{i}"' in html and i not in got]
        if missing:
            fail(f"R11 {name}: sections on the page but not in the bar: {missing}", errs)
        if name == "portfolio.html":
            if 'data-cur="mxn"' not in bars[0] or 'data-cur="usd"' not in bars[0]:
                fail("R11 portfolio.html: the bar does not hold the MXN | USD switch", errs)
            if 'class="ccy-bar"' in html:
                fail("R11 portfolio.html: r2's separate currency bar is still on the page (two sticky strips)", errs)
    for p in _all_pages():
        name = os.path.relpath(p, DOCS).replace("\\", "/")
        html = open(p, encoding="utf-8", errors="replace").read()
        for sm in re.findall(r'<details class="nt nt-m[^"]*"><summary>(.*?)</summary>', html, re.S):
            n_note += 1
            if not re.sub(r"<[^>]+>|&\w+;|\s", "", sm):
                fail(f"R11 {name}: a method note without a summary", errs)
        if name == "portfolio.html":
            d = re.search(r'<p class="nt nt-d pf-disc">(.*?)</p>', html, re.S)
            mt = html.find('<div class="metrics"')
            if not d:
                fail("R11 portfolio.html: the scaling disclosure is missing", errs)
            else:
                pre_ = html[:d.start()]
                if pre_.count("<details") > pre_.count("</details>"):
                    fail("R11 portfolio.html: the scaling disclosure sits inside a closed note", errs)
                if mt >= 0 and d.start() > mt:
                    fail("R11 portfolio.html: the scaling disclosure is not above the first money tile", errs)
                if "scaled" not in d.group(1) or re.search(r"\d", re.sub(r"<[^>]+>|&\w+;", "", d.group(1))):
                    fail("R11 portfolio.html: the scaling disclosure must say 'scaled' and name no number", errs)
    return f"{n_bar} pages with the On-this-page bar, {n_note} method notes"


# =====================================================================================================================
# R12 (wave r3, builder C; Carlos, written 2026-11-10 ~15:00, "Dale play a todo"): the tables builder C reshaped.
#   Congress: the trades table is grouped by filing (table.mi.cgt; one tbody.cgg per filing, ONE header row whose
#     "<b>N trade(s)</b>" equals its trade rows, its button controls it); the filings are exactly what the data file
#     gives, re-derived here independently of the generator: every filing with a trade among the newest MAXROWS rows of
#     data/market_intel/congress_public.json, WHOLE, in the order those rows first show it, each with all its trades in
#     the file's order (member, filing date, link, tickers, sides); no row or filing carries `hidden` in the HTML (without
#     JavaScript everything shows); filing ids unique; the filter bar (JavaScript only), its controls and the script are
#     there; the cap note's counts are the page's.
#   Stock Research: every table.ptable on stocks.html sits in a .tile.pcw and each of its body cells carries its column's
#     header as data-label (design_system.card_labels on the unlabelled table reproduces the page's table exactly); the
#     Pick Tracker table is "fit": every row has picks_tracker.TRACK_PRI as data-pri and ONE rank sparkline, whose latest
#     rank is the rank the row shows; the footnote explains the sparkline; style.css carries the cards' rules. A committed
#     stocks.html from before r3-C (no .pcw: 25 could not render yet, a Yahoo block) is a WARN, never a FAIL.
# =====================================================================================================================
_CG_HIDDEN = re.compile(r"<(?:tr|tbody)\b[^>]*\shidden(?:[\s>=])", re.I)


def _congress_checks(errs, warns):
    import html as _h
    cg = _read("congressional-activity.html")
    if not cg:
        return "Congress page absent"
    sec = re.search(r'<section class="block" id="trades">(.*?)</section>', cg, re.S)
    if not sec:
        fail("R12 congressional-activity.html: no #trades section", errs)
        return "Congress: no trades section"
    tb = re.search(r'<table class="mi cgt">(.*?)</table>', sec.group(1), re.S)
    if not tb:
        fail("R12 congressional-activity.html: the trades are not grouped by filing (no table.mi.cgt)", errs)
        return "Congress: not grouped"
    tb = tb.group(1)
    if _CG_HIDDEN.search(tb):
        fail("R12 congressional-activity.html: a filing or trade carries `hidden` in the HTML (without JavaScript every "
             "trade must show)", errs)
    groups = re.findall(r'<tbody class="cgg" id="([^"]+)" data-m="([^"]*)" data-c="([^"]*)">(.*?)</tbody>', tb, re.S)
    if len(groups) != tb.count("<tbody"):
        fail(f"R12 congressional-activity.html: {tb.count('<tbody')} row groups, {len(groups)} of them filings", errs)
    ids = [g[0] for g in groups]
    if len(set(ids)) != len(ids) or any(cg.count(f'id="{i}"') != 1 for i in ids):
        fail("R12 congressional-activity.html: a filing id is not unique on the page", errs)
    # the data file, re-derived independently of the generator
    src30 = open(os.path.join(SCRIPTS, "30_market_intel.py"), encoding="utf-8").read()
    mx = re.search(r"^CG_MAXROWS = (\d+)", src30, re.M)
    data = json.load(open(os.path.join(ROOT, "data", "market_intel", "congress_public.json"), encoding="utf-8"))
    rows = data.get("rows") or []
    exp, order = {}, []
    for r in rows:
        exp.setdefault((r.get("member"), r.get("filed_date"), r.get("source")), []).append(r)
    for r in rows[:int(mx.group(1)) if mx else 400]:
        k = (r.get("member"), r.get("filed_date"), r.get("source"))
        if k not in order:
            order.append(k)
    if not mx:
        fail("R12 30_market_intel.py: no CG_MAXROWS (the trades table's cap)", errs)
    if len(groups) != len(order):
        fail(f"R12 congressional-activity.html: {len(groups)} filings on the page, the data gives {len(order)}", errs)
    side = {"P": "P", "S": "S", "S-partial": "S", "E": "E"}
    n_rows = 0
    for i, (gid, mem, ch, body) in enumerate(groups):
        heads = re.findall(r'<tr class="cgh">(.*?)</tr>', body, re.S)
        trs = re.findall(r'<tr class="cgr" data-t="([^"]*)" data-s="([PSEO])">', body)
        n_rows += len(trs)
        if len(heads) != 1 or len(trs) != body.count("<tr") - 1:
            fail(f"R12 congressional-activity.html #{gid}: {len(heads)} header rows, {len(trs)} trades of "
                 f"{body.count('<tr') - 1} rows", errs)
            continue
        cnt = re.search(r"<b>(\d+) trades?</b>", heads[0])
        if not cnt or int(cnt.group(1)) != len(trs):
            fail(f"R12 congressional-activity.html #{gid}: the header says {cnt.group(1) if cnt else '?'} trades, the "
                 f"filing has {len(trs)} rows", errs)
        if f'aria-controls="{gid}"' not in heads[0]:
            fail(f"R12 congressional-activity.html #{gid}: the header's button does not control its filing", errs)
        if i >= len(order):
            continue
        k = order[i]
        want = exp[k]
        got = [(_h.unescape(t), s) for t, s in trs]
        h0 = re.sub(r'<span class="nw">(.*?)</span>', r"\1", heads[0])     # fix round 1 (V2-3): unbroken date / band
        if (_h.unescape(mem) != (k[0] or "") or f"filed {_h.escape(str(k[1] or ''), quote=True)} &middot;" not in h0
                or f'href="{_h.escape(str(k[2] or ""), quote=True)}"' not in heads[0]
                or got != [(x.get("ticker") or "", side.get(x.get("direction"), "O")) for x in want]):
            fail(f"R12 congressional-activity.html #{gid}: not the data file's filing {i + 1} ({k[0]}, filed {k[1]}, "
                 f"{len(want)} trades)", errs)
    for need in ('id="cgq"', 'id="cgm"', 'id="cgc"', 'id="cgs"', 'id="cgr"', 'id="cgn"'):
        if sec.group(1).count(need) != 1:
            fail(f"R12 congressional-activity.html: the filter control {need} is missing or repeated", errs)
    if 'class="cgbar jsonly"' not in sec.group(1) or "document.querySelector('table.cgt')" not in cg:
        fail("R12 congressional-activity.html: the filter bar (JavaScript only) or its script is missing", errs)
    cap = re.search(r"Showing the newest (\d+) filings, whole: ([0-9,]+) of the ([0-9,]+) trades", sec.group(1))
    if len(rows) > n_rows and (not cap or (int(cap.group(1)), int(cap.group(2).replace(",", "")),
                                            int(cap.group(3).replace(",", ""))) != (len(groups), n_rows, len(rows))):
        fail(f"R12 congressional-activity.html: the cap note does not say {len(groups)} filings, {n_rows} of "
             f"{len(rows)} trades", errs)
    return f"Congress {len(groups)} filings / {n_rows} trades"


def _stock_table_checks(errs, warns):
    st = _read("stocks.html")
    if not st:
        return "stocks.html absent"
    ds = _ds()
    tabs = list(re.finditer(r'<table class="ptable(?: [^"]*)?">', st))
    if 'class="tile pcw"' not in st:
        # fix round 1 (r3 continuation, PIPE2-3): only a page WITHOUT any of the r3 25's own markup (its method notes,
        # the fitted tracker, the sparklines) is the committed pre-r3 copy; an r3 render that lost its cards FAILs
        r3_25 = [k for k in ('<details class="nt nt-m', '<table class="ptable ptrack fit">', '<svg class="spk"') if k in st]
        if r3_25:
            fail(f"R12 stocks.html: rendered by the wave-r3 25 ({', '.join(r3_25)}) but without its phone cards "
                 "(design_system.card_tables did not run: no .tile.pcw)", errs)
            return f"stocks: {len(tabs)} tables, r3 render WITHOUT phone cards"
        fail("R12 stocks.html: no phone cards yet (a committed copy from before wave r3-C: 25 adds them at its next "
             "render)", warns)
        return f"stocks: {len(tabs)} tables, cards not rendered yet"
    css = open(os.path.join(DOCS, "style.css"), encoding="utf-8").read() if os.path.isfile(os.path.join(DOCS, "style.css")) else ""
    if ".tile.pcw>table.ptable>tbody>tr>td::before{content:attr(data-label)" not in css or ".spk .l{" not in css:
        fail("R12 style.css: the phone-card / sparkline rules are missing (design_system.ET_CSS)", errs)
    for t in tabs:
        pre = st[:t.start()].rstrip()
        if not re.search(r'<div class="tile pcw" style="[^"]*">$', pre):
            fail(f"R12 stocks.html: a table ({t.group(0)}) is not in a phone-card tile (.tile.pcw)", errs)
            continue
        end = ds._table_end(st, t.start())
        tbl = st[t.start():end]
        if ds.card_labels(re.sub(r' data-label="[^"]*"', "", tbl)) != tbl:
            fail(f"R12 stocks.html: a cell of {t.group(0)} is not labelled with its column header (card_labels)", errs)
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    import picks_tracker as pt
    n_tr = 0
    if '<table class="ptable ptrack' in st:
        if '<table class="ptable ptrack fit">' not in st:
            fail("R12 stocks.html: the Pick Tracker is not fitted (picks_tracker.tracker_fit)", errs)
        for row in re.findall(r'<tr data-pick="[01]"(?: hidden)?>(.*?)</tr>', st, re.S):
            n_tr += 1
            tds = re.findall(r"<td([^>]*)>(.*?)</td>", row, re.S)
            tk = re.search(r'aria-controls="ptd-([^"]+)"', row)
            tk = tk.group(1) if tk else "?"
            pri = tuple(int(m.group(1)) if m else 0 for m in (re.search(r'data-pri="(\d)"', a) for a, _c in tds))
            if pri != tuple(pt.TRACK_PRI):
                fail(f"R12 stocks.html Pick Tracker {tk}: column priorities {pri} != picks_tracker.TRACK_PRI", errs)
                continue
            rk = tds[4][1]
            sv = re.findall(r'<svg class="spk"[^>]*>.*?</svg>', rk, re.S)
            last = re.search(r'aria-label="[^"]*?(\d+) at the latest', sv[0]) if len(sv) == 1 else None
            shown = re.search(r"</svg>(\d+)", rk)
            if len(sv) != 1 or not last or not shown or last.group(1) != shown.group(1):
                fail(f"R12 stocks.html Pick Tracker {tk}: {len(sv)} rank sparkline(s); latest "
                     f"{last.group(1) if last else '?'} vs the row's rank {shown.group(1) if shown else '?'}", errs)
        if pt.SPARK_NOTE.strip() not in st:
            fail("R12 stocks.html: the Pick Tracker footnote does not explain the sparkline", errs)
    # polish round (2026-11-11, RC2-2): the Composite Picks filter states its state to a screen reader
    pills = re.search(r'<div class="pills" data-group="picks">(.*?)</div>', st, re.S)
    n_ap = 0
    if not pills:
        fail("R12 stocks.html: no Composite Picks filter pills", errs)
    else:
        bts = re.findall(r"<button\b([^>]*)>", pills.group(1))
        for a in bts:
            on = re.search(r'class="pill on"', a) is not None
            ap = re.search(r'aria-pressed="(true|false)"', a)
            if not ap or (ap.group(1) == "true") != on:
                fail(f"R12 stocks.html: a Composite Picks pill without the matching aria-pressed ({a.strip()[:60]})", errs)
            else:
                n_ap += 1
        if sum(1 for a in bts if 'class="pill on"' in a) != 1:
            fail("R12 stocks.html: the Composite Picks filter has no single 'on' pill", errs)
        if "x.setAttribute('aria-pressed','false')" not in st or "b.setAttribute('aria-pressed','true')" not in st:
            fail("R12 stocks.html: the filter script does not keep aria-pressed in sync (25 FILTER_JS)", errs)
    return f"stocks {len(tabs)} card tables, Pick Tracker {n_tr} rows with a sparkline, {n_ap} pills with aria-pressed"


_CFA_VIEW = re.compile(r'CFA View</h2>\s*<div class="scaled-note"[^>]*>(.*?)</div>', re.S)


def _stock_page_checks(errs, warns):
    """polish round (2026-11-11, C4): the CFA View's justified-P/E clause on every stock page the new 19 wrote"""
    n_new = n_old = n_clause = 0
    for f in sorted(os.listdir(DOCS)):
        if not re.fullmatch(r"stock_[A-Za-z0-9.\-]+\.html", f):
            continue
        h = _read(f) or ""
        v = _CFA_VIEW.search(h)
        if not v or "the CFA-framework methods put the 12-month fair value" not in v.group(1):
            n_old += 1                  # a committed copy in the older wording: 19 rewrites it at its next render
            continue
        n_new += 1
        view = v.group(1)
        po = re.search(r"&middot; payout (-?\d+\.\d)%\.", h)
        tp = re.search(r'<div class="mv">([^<]*)</div><div class="mk">Trailing P/E</div>', h)
        if not po or not tp:
            fail(f"R12 {f}: the Forecast footnote's payout or the Trailing P/E tile is missing", errs)
            continue
        pay, pe = float(po.group(1)), tp.group(1)
        has_pe = pe not in ("n/a", "") and float(pe.replace(",", "")) != 0
        nm = re.findall(r"the justified P/E is n/m \(([^)]*)\)", view)
        if pay < 30 and has_pe:
            ok = [f"payout {po.group(1)}% &lt; 30%"] if pay != 0 else ["no dividend", "payout 0.0% &lt; 30%"]
            if not nm:
                # r2's 19 wrote the same wording without the clause where its justified P/E was 0 or missing (a 0%
                # payout, no ROE): a page it wrote cannot be told from one that lost the clause, so a WARN
                fail(f"R12 {f}: payout {po.group(1)}% below 30% with a trailing P/E and no n/m clause (a page written "
                     f"before the polish round's 19: it adds 'n/m ({ok[0]})' at its next render)", warns)
            elif len(nm) != 1 or nm[0] not in ok:
                fail(f"R12 {f}: payout {po.group(1)}% but the CFA View prints n/m ({'; '.join(nm)}) (want n/m ({ok[0]}))",
                     errs)
            else:
                n_clause += 1
        elif nm:
            fail(f"R12 {f}: an n/m clause at payout {po.group(1)}% (n/m is only below 30% with a trailing P/E)", errs)
    return f"stock pages {n_new} (new 19) + {n_old} committed: {n_clause} n/m clauses"


def _entries_note_checks(errs, warns):
    """polish round (2026-11-11, V-2): the entries chart's band note sits clear of the y tick labels. Follow-up RC1B-1
    (2026-11-12): EVERY 'in cash, by choice' note on the page is checked, not only #pf-entry's -- the decisions chart
    #pf-twr carries the same note (its cash band's vrect annotation, 'top left' = the plot's left edge). 18 is the only
    generator that writes the note, portfolio.html the only page that carries it."""
    h = _read("portfolio.html") or ""
    if 'id="pf-entry"' not in h and "in cash, by choice" not in h:
        return "entries chart absent"
    ds = _ds()
    names = {"pf-entry": "the entries chart", "pf-twr": "the decisions chart"}
    seen, notes = set(), []
    for cid, _data, lay in ds._plotly_calls(h):
        seen.add(cid)
        for a in lay.get("annotations", []):
            if a.get("text") != "in cash, by choice":
                continue
            notes.append(f"{cid} {'offset ' + str(a['xshift']) + ' px' if 'xshift' in a else 'not offset'}")
            if a.get("xanchor") != "left":
                continue
            what = f"{names.get(cid, 'the chart')}'s (#{cid}) 'in cash, by choice' note"
            if "xshift" not in a:
                # a committed page written before 18 shifted this note (the deploy does not re-render 18): 18 shifts it
                # at its next render, so a WARN, never a FAIL
                fail(f"R12 portfolio.html: {what} is not offset yet (a page written before 18 shifted it: 18 does at "
                     "its next render)", warns)
            elif (a.get("xshift") or 0) < 8:
                fail(f"R12 portfolio.html: {what} starts at the plot's edge, against the y tick labels (V-2, RC1B-1: "
                     "xshift >= 8 px)", errs)
    if 'id="pf-entry"' in h and "pf-entry" not in seen:
        fail("R12 portfolio.html: no Plotly figure for #pf-entry", errs)
        return "entries chart unreadable"
    head = "" if 'id="pf-entry"' in h else "entries chart absent; "
    return head + "'in cash, by choice' notes: " + (", ".join(notes) if notes else "none (no cash band)")


# fix round 1 (r3 continuation, 2026-11-11, RG-1): the r3 CSS fixes stay in what the generators emit. Static half (the
# browser half is tools/layout_browser_check.js, see WEBSITE_STYLE_GUIDE): in docs/style.css the .tile clips without
# being a scroll container (overflow:clip) and the heads of tables in a tile sit below the header + bar, no @media print
# rule hides the footer (.shell-foot: the disclaimer and the image credit), the Research menu hangs from the header on
# phones (V2-1), a licence name never breaks (V2-7); on the Congress page the filing header is sized from its scroller
# (a size container, 100cqi: V2-2). Decisions pass (2026-11-11, RC1-1 / RC1-2): the menu hangs from the header row right
# under its button (top:auto, never a fixed px offset: a no-JS header can wrap the button onto a second row); with the
# theme control shown theme.css does it (r2's two [data-theme-pref] rules), on landscape phones style.css does it too.
CSS_FIXES = (
    ("the sticky-head fix (.tile clips without being a scroll container)", r"\.tile\{[^}]*overflow:hidden;overflow:clip\}"),
    ("the head offset of tables sitting in a tile",
     re.escape('@supports (overflow:clip){.tile:not([style*="overflow"])>.ptable thead th{top:calc(var(--hdr) + var(--otph) - 1px)}')),
    ("the Research menu on landscape phones without JavaScript (V2-1, RC1-2)",
     re.escape(".rc{position:static}\n  .rc-menu{left:auto;right:16px;width:min(640px,calc(100% - 32px));top:auto;margin-top:8px}")),
    ("licence names unbroken (V2-7)", re.escape('a[rel~="license"]{white-space:nowrap}')),
    # polish round (2026-11-11, V-1 / RC2-1): below 360 px with the theme control the corner shows its icon + caret only,
    # so brand + corner + control keep ONE header row down to 320 px (the control wrapped and the open menu covered it)
    ("the one-row phone header with the theme control below 360 px (V-1, RC2-1)",
     re.escape("@media(max-width:359.98px){[data-theme-pref] .rc>summary{font-size:0;gap:2px;padding:0 10px}\n"
               "  [data-theme-pref] .rc>summary>svg:first-child,[data-theme-pref] .rc>summary .car{display:block}}")),
)
THEME_MENU = (
    ("the Research menu on phones (V2-1)",
     r"@media\(max-width:\d+\.98px\)\{\[data-theme-pref\] \.shell-in\{position:relative\}\[data-theme-pref\] \.rc\{position:static\}"
     r"\[data-theme-pref\] \.rc-menu\{left:16px;right:16px;width:auto;top:auto;margin-top:8px\}\}"),
    ("the Research menu on landscape phones (V2-1)",
     r"@media\(max-height:520px\) and \(min-width:560px\) and \(max-width:\d+px\)\{\[data-theme-pref\] \.shell-in\{position:relative\}"
     r"\[data-theme-pref\] \.rc\{position:static\}\[data-theme-pref\] \.rc-menu\{left:auto;right:16px;"
     r"width:min\(640px,calc\(100% - 32px\)\);top:auto;margin-top:8px\}\}"),
)
MENU_FIXED_TOP = re.compile(r"\.rc-menu\{(?:[^}]*;)?\s*top:\d+(?:\.\d+)?px")


def _print_rule_hiding(css, needle=".shell-foot"):
    """The first rule inside an @media print block whose selector names `needle` and sets display:none, or None."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"@media\s+print\s*\{", css):
        i, depth = m.end(), 1
        while i < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        for r in re.finditer(r"([^{}]+)\{([^{}]*)\}", css[m.end():i - 1]):
            if any(needle in s for s in r.group(1).split(",")) and re.search(r"display\s*:\s*none", r.group(2)):
                return r.group(0).strip()[:140]
    return None


def _css_fix_checks(errs, warns):
    p = os.path.join(DOCS, "style.css")
    if not os.path.isfile(p):
        fail("R12 style.css missing", errs)
        return "style.css absent"
    css = open(p, encoding="utf-8").read().replace("\r\n", "\n")
    nok = 0
    for what, rx in CSS_FIXES:
        if not re.search(rx, css):
            fail(f"R12 style.css: {what} is missing (design_system.ET_CSS / 17_build_site.py)", errs)
        else:
            nok += 1
    fx = MENU_FIXED_TOP.search(re.sub(r"/\*.*?\*/", "", css, flags=re.S))
    if fx:
        fail(f"R12 style.css: the Research menu has a fixed top offset ({fx.group(0)[-60:]}): on a two-row header it "
             "covers its own button (RC1-1); use top:auto + margin-top", errs)
    tp = os.path.join(DOCS, "_design_system", "theme.css")
    th = open(tp, encoding="utf-8").read() if os.path.isfile(tp) else ""
    if not th:
        fail("R12 _design_system/theme.css missing (the Research menu rules on phones)", errs)
    for what, rx in THEME_MENU:
        if th and not re.search(rx, th):
            fail(f"R12 theme.css: {what} is missing (design_system._THEME_CONTROL_CSS)", errs)
        elif th:
            nok += 1
    hid = _print_rule_hiding(css)
    if hid:
        fail(f"R12 style.css: a print rule hides the footer (disclaimer + image credit): {hid}", errs)
    cg = _read("congressional-activity.html") or ""
    if '<table class="mi cgt">' in cg and not ("container-type:inline-size" in cg and "max-width:calc(100cqi - 20px)" in cg
                                               and 'class="mi-wrap cgw"><table class="mi cgt">' in cg):
        fail("R12 congressional-activity.html: the filing header is not sized from its scroller (.mi-wrap.cgw "
             "container, 100cqi: V2-2)", errs)
    return (f"CSS fixes {nok}/{len(CSS_FIXES) + len(THEME_MENU)} (style.css + theme.css), print footer "
            f"{'HIDDEN' if hid else 'prints'}")


def _table_checks(errs, warns):
    return (_congress_checks(errs, warns) + "; " + _stock_table_checks(errs, warns) + "; "
            + _css_fix_checks(errs, warns) + "; " + _stock_page_checks(errs, warns) + "; "
            + _entries_note_checks(errs, warns))


def rules_gate():
    """R1-R12 only (scripts/guard_site_rules.py runs this in the refresh, after step 31). The static S / A rules stay
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
    print("SITE RULES (R1-R12):", "PASS" if not errs else f"FAIL ({len(errs)})")
    return 1 if errs else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--rules-only", action="store_true", help="R1-R12 only (what the refresh runs)")
    a_ = ap.parse_args()
    sys.exit(rules_gate() if a_.rules_only else static_gate(a_.write_baseline))
