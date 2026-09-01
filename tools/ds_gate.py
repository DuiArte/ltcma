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

# Pages that are meta-refresh redirect stubs: no styling, correctly unlinked.
STUBS = {"backtests.html", "signals.html"}
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

    print(f"pages checked: {len(counts)}  "
          f"(styled {len(counts)-len([p for p in counts if p in STUBS])}, stubs {len(STUBS)})")
    for w in warns:
        print(f"  WARN  {w}")
    for e in errs:
        print(f"  FAIL  {e}")
    print("=" * 60)
    print("DS STATIC GATE:", "PASS" if not errs else f"FAIL ({len(errs)})")
    return 1 if errs else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    sys.exit(static_gate(ap.parse_args().write_baseline))
