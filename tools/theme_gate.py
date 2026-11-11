"""Dark-mode gate (wave r2, 2026-11-10): the STATIC half. The real-browser half (computed contrast of every text node
and every chart in both themes at 1440 and 375, the toggle round trip, console errors) is
`tools/theme_browser_check.js`, run in a browser against a served docs/ (DEPLOY_NOTES part B says how).

  T1  every page with the header carries the theme head (design_system.HEAD_LINKS) once, before style.css, the control
      (id="thm") once and the chart / control script once
  T2  docs/_design_system/theme.css is exactly design_system.THEME_CSS, and every token a themed page uses in a colour
      property has a dark value there (both dark contexts)
  T3  no light-only colour literal is left in a themed page's <style> blocks / style="" attributes / style.css, outside
      the theme-invariant contexts (image heroes, @media print, custom-property definitions, masks, var() fallbacks)
  T4  light identity: in every var(--t, L) the token is either undefined in light (the literal applies) or its light
      value is L itself, so the light theme renders the old colour
  T5  the chart palette (design_system.CHART_DARK) inverts exactly (injective, no dark value is also a light key, no
      page uses a dark value as a light colour) and every colour a chart strokes or fills in dark is >= 3:1 on the
      dark card; a trace colour the map does not know must itself be >= 3:1 there. Round 1 (review V1): two trace
      colours that share a chart and are >= 15 CIEDE2000 apart in light stay >= 15 apart in dark
  T6  the dark text tokens are >= 4.5:1 on the dark ground / card / chip, the text-on-accent token on every fill
  T7  no page script sets a colour style to a literal (themed() never rewrites inside <script>), neither through
      `.style.<colour>=` nor (round 1, review PIPE-5) as a style="" attribute inside an HTML fragment it writes
  T3 also reads the generators' own palettes (round 1, review PIPE-4): every colour 25_stock_picks.py can emit as a
      sector chip background has a dark token and a chart dark value, even on a day no such chip is on the page
  Not seen statically: a colour a script computes at run time (`el.style.color = c`), a figure that only a script
  builds; those are the browser half's (theme_browser_check.js).
usage: python -X utf8 -B tools/theme_gate.py [docs_dir]   (exit 1 on any FAIL)
"""
import ast
import json
import math
import os
import re
import sys
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.dont_write_bytecode = True
import design_system as ds  # noqa: E402

STYLE = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.S | re.I)
SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.S | re.I)
VARF = re.compile(r"var\(--([\w-]+)\s*,\s*([^()]*(?:\([^()]*\))?[^()]*)\)")
VARN = re.compile(r"var\(--([\w-]+)")
ROOTDEF = re.compile(r"(?:^|[}\s]):root\s*\{([^}]*)\}", re.S)
# chart colours that are grounds, grid / zero / spike lines or translucent fills, not strokes a reader must see
CHART_DECOR = {"#ffffff", "rgba(255,255,255,.97)", "#f1f1f1", "#f4f4f2", ds.GRIDLN, "#d4d4d4", "#ebf0f8", "#c9c9c9",
               "#7fb3ad", "#7e97b3", "rgba(15,98,254,0.13)", "rgba(154,165,177,0.12)", *ds.TINT.values()}
DARK_TEXT = ["ink", "sec", "muted", "accent", "amber", "up", "down", "pos", "neg", "st-green", "st-blue", "st-purple",
             "st-gray", "teal", "bench", "slate", "warn", "l-ink", "l-ink2", "l-ink25", "l-ink3", "l-sec", "l-sec6",
             "l-muted", "l-muted2", "l-faint"]
EMITTED = {t for m in ds._KIND_MAP.values() for t in m.values()}   # tokens themed() writes
FILLS = ["accent", "pos", "neg", "st-gray", "slate", "c-violet", "c-red", "c-cyan", "amber", "up", "down", "accent-hover",
         "l-sec", "l-muted"]                    # l-sec / l-muted: 25's Industrials / unknown-sector chips (PIPE-4)
# generator palettes a page carries only on some days (round 1, review PIPE-4): script -> names of its module-level
# colour constants / dicts that it writes as a chip BACKGROUND (style="background:...") and as Plotly marker colours
GEN_PALETTES = {"25_stock_picks.py": ("SECTOR_C", "GREY")}
PAIR_DE = 15.0                                  # T5 pairs: CIEDE2000 distance kept in dark when light had it
FRAG = re.compile(r"""style=\\?["']([^"'\\]*)""")      # a style attribute inside a script's HTML fragment


def lum(c):
    r, g, b, _ = ds.canon(c)
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r / 255) + 0.7152 * f(g / 255) + 0.0722 * f(b / 255)


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _lab(c):
    r, g, b, _ = ds.canon(c)
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = f(r / 255), f(g / 255), f(b / 255)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    h = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * h(y) - 16, 500 * (h(x) - h(y)), 200 * (h(y) - h(z))


def de2000(a, b):
    """CIEDE2000 colour difference of two sRGB colours"""
    L1, a1, b1 = _lab(a)
    L2, a2, b2 = _lab(b)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = math.degrees(math.atan2(b1, a1p)) % 360, math.degrees(math.atan2(b2, a2p)) % 360
    dL, dC = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dH = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lb, Cbp, hb = (L1 + L2) / 2, (C1p + C2p) / 2, (h1p + h2p) / 2
    if C1p * C2p != 0 and abs(h1p - h2p) > 180:
        hb += 180
    T = (1 - 0.17 * math.cos(math.radians(hb - 30)) + 0.24 * math.cos(math.radians(2 * hb))
         + 0.32 * math.cos(math.radians(3 * hb + 6)) - 0.20 * math.cos(math.radians(4 * hb - 63)))
    SL = 1 + 0.015 * (Lb - 50) ** 2 / math.sqrt(20 + (Lb - 50) ** 2)
    SC, SH = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    dT = 30 * math.exp(-((hb - 275) / 25) ** 2)
    RT = -math.sin(math.radians(2 * dT)) * 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    return math.sqrt((dL / SL) ** 2 + (dC / SC) ** 2 + (dH / SH) ** 2 + RT * (dC / SC) * (dH / SH))


def dark_of(name):
    return ds.ET_DARK.get(name) or (ds.THEME_TOKENS.get(name) or (None, None))[1]


def light_defs(texts):
    """custom properties defined in light :root blocks (style.css, tokens.css, a page's <style>)"""
    out = {}
    for t in texts:
        t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
        t = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", t)       # no dark / print / media blocks
        for body in ROOTDEF.findall(t):
            for d in body.split(";"):
                if d.strip().startswith("--") and ":" in d:
                    k, v = d.split(":", 1)
                    out[k.strip()[2:]] = v.strip()
    return out


def page_css(html):
    return [m for m in STYLE.findall(html)]


def colour_vars(css_texts, attrs):
    """names used inside colour-kind properties"""
    names = set()
    for t in list(css_texts) + list(attrs):
        for d in re.split(r"[;{}]", t):
            if ":" in d:
                p, v = d.split(":", 1)
                if ds._prop_kind(p.split("{")[-1]):
                    names |= set(VARN.findall(v))
    return names


def attrs_of(html):
    body = SCRIPT.sub("", STYLE.sub("", html))
    return [m.group(2) if m.group(2) is not None else m.group(3) for m in ds._STYLE_ATTR.finditer(body)]


def check_pages(docs, errs, warns, info):
    style_css = open(os.path.join(docs, "style.css"), encoding="utf-8").read()
    tok_css = open(os.path.join(docs, "_design_system", "tokens.css"), encoding="utf-8").read()
    # T2 theme.css
    tp = os.path.join(docs, "_design_system", "theme.css")
    if not os.path.exists(tp):
        errs.append("T2 docs/_design_system/theme.css missing")
        theme_css = ""
    else:
        theme_css = open(tp, encoding="utf-8").read()
        if theme_css != ds.THEME_CSS:
            errs.append("T2 docs/_design_system/theme.css differs from design_system.THEME_CSS (stale build?)")
    dark_names = set(ds.ET_DARK) | set(ds.THEME_TOKENS)
    for ctx in ('@media screen and (prefers-color-scheme:dark){:root:not([data-theme="light"]){',
                '@media screen{:root[data-theme="dark"]{'):
        i = theme_css.find(ctx)
        blk = theme_css[i + len(ctx): theme_css.find("}", i + len(ctx))] if i >= 0 else ""
        have = {d.split(":", 1)[0].strip()[2:] for d in blk.split(";") if d.strip().startswith("--")}
        miss = sorted(dark_names - have)
        if i < 0 or miss:
            errs.append(f"T2 theme.css: dark context {ctx[:40]!r} {'missing' if i < 0 else 'lacks ' + ', '.join(miss)}")
    # T3 / T4 on style.css itself
    del ds.THEME_UNMAPPED[:]
    if ds.themed_css(style_css, "style.css") != style_css or ds.THEME_UNMAPPED:
        errs.append(f"T3 style.css: colour literal(s) not tokenised: {sorted(set(u[2] for u in ds.THEME_UNMAPPED))[:8]}")
    pages = []
    for dp, _, fs in os.walk(docs):
        for f in fs:
            if f.endswith(".html"):
                pages.append(os.path.relpath(os.path.join(dp, f), docs).replace("\\", "/"))
    themed_n = 0
    for name in sorted(pages):
        html = open(os.path.join(docs, name), encoding="utf-8").read()
        has_nav = '<nav class="tabs"' in html
        is_themed = ds.HEAD_LINKS in html
        if not has_nav:
            if is_themed:
                warns.append(f"T1 {name}: themed but has no header (no control)")
            continue
        # T1
        if html.count(ds.HEAD_LINKS) != 1:
            errs.append(f"T1 {name}: theme head (HEAD_LINKS) found {html.count(ds.HEAD_LINKS)}x")
            continue
        themed_n += 1
        hd = html[:html.find("</head>")]
        if not (0 <= hd.find(ds.THEME_BOOT) < hd.find('href="style.css"')):
            errs.append(f"T1 {name}: the boot script does not precede style.css in <head>")
        n_thm = html.count('id="thm"')
        if n_thm != 1:
            errs.append(f"T1 {name}: theme control id=thm found {n_thm}x")
        if html.count("window.ltcmaTheme=") != 1:
            errs.append(f"T1 {name}: theme script found {html.count('window.ltcmaTheme=')}x")
        css = page_css(html)
        at = attrs_of(html)
        # T3: re-tokenising a themed page must change nothing and leave nothing unmapped
        del ds.THEME_UNMAPPED[:]
        for c in css:
            if ds.themed_css(c, name) != c:
                errs.append(f"T3 {name}: a <style> block still carries a colour literal outside var()")
        for a in at:
            if ds._decls(a, name) != a:
                errs.append(f"T3 {name}: style=\"{a[:70]}\" carries a colour literal outside var()")
        if ds.THEME_UNMAPPED:
            errs.append(f"T3 {name}: unknown colour literal(s) {sorted(set(u[2] for u in ds.THEME_UNMAPPED))[:8]}"
                        f" (add them to design_system _FG/_BG/_BD/_SH with a dark token)")
        # T2 tokens used in colour properties have a dark value
        used = colour_vars(css + [style_css], at)
        light = light_defs([style_css, tok_css] + css)
        fb_named = {t for blob in css + at for t, fb in VARF.findall(blob) if ds.canon(fb.strip()) is not None}
        for t in sorted(used):
            if t in dark_names:
                continue
            if (t in light and ds.canon(light[t].split(",")[0]) is not None) or t in fb_named:
                errs.append(f"T2 {name}: colour token --{t} has no dark value in theme.css")
        # T4 light identity
        for blob in css + at:
            for t, fb in VARF.findall(blob):
                fb = fb.strip()
                if ds.canon(fb) is None:
                    continue
                lv = light.get(t)
                if t in EMITTED and lv is not None and ds.canon(lv) != ds.canon(fb):
                    errs.append(f"T4 {name}: var(--{t},{fb}) but --{t} is {lv} in light (the light theme would change)")
        # T7 script literals
        for s in SCRIPT.findall(html):
            for m in re.finditer(r"\.style\.(color|background(?:Color)?|border(?:Color)?|fill)\s*=\s*(['\"])(.*?)\2", s):
                if ds._COLOR.search(m.group(3)) and "var(" not in m.group(3):
                    errs.append(f"T7 {name}: script sets .style.{m.group(1)}={m.group(3)!r} (a literal, no dark value)")
            if "Plotly.newPlot(" in s:
                continue                         # figure JSON: its colours are the chart map's (T5), not CSS
            for m in FRAG.finditer(s):
                del ds.THEME_UNMAPPED[:]
                if ds._decls(m.group(1), name) != m.group(1) or ds.THEME_UNMAPPED:
                    errs.append(f"T7 {name}: script writes an HTML fragment with style=\"{m.group(1)[:60]}\" (a "
                                f"colour literal outside var(): it stays light in dark)")
            del ds.THEME_UNMAPPED[:]
    info.append(f"{themed_n} themed pages")
    return pages


def chart_colours(docs, pages):
    """every colour string used by a Plotly figure (data + layout, template excluded): {canon: (sample, kinds)}"""
    out = {}
    for name in pages:
        html = open(os.path.join(docs, name), encoding="utf-8").read()
        for did, data, layout in ds._plotly_calls(html):
            layout = {k: v for k, v in layout.items() if k != "template"}

            def walk(o, path):
                if isinstance(o, dict):
                    if "bdata" in o:
                        return
                    for k, v in o.items():
                        walk(v, path + "." + k)
                elif isinstance(o, list):
                    for v in o:
                        walk(v, path)
                elif isinstance(o, str):
                    if ds.canon(o) is not None and ("color" in path or path.endswith("colorscale")):
                        out.setdefault(ds.canon(o), [o, set()])[1].add(path.split(".", 2)[1] + ":" + path.rsplit(".", 1)[-1])
                    for m in re.finditer(r"colou?r\s*:\s*(#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\))", o):
                        out.setdefault(ds.canon(m.group(1)), [m.group(1), set()])[1].add("inline-text")
            walk({"data": data, "layout": layout}, "")
    return out


def check_palette(docs, pages, errs, warns, info, cmap=None):
    cmap = ds.CHART_DARK if cmap is None else cmap
    panel = ds.ET_DARK["panel"]
    keys = {}
    for k, v in cmap.items():
        ck, cv = ds.canon(k), ds.canon(v)
        if ck is None or cv is None:
            errs.append(f"T5 CHART_DARK {k!r} -> {v!r}: not a colour")
            continue
        if cv in keys.values():
            errs.append(f"T5 CHART_DARK is not injective: {v!r} is the dark value of two colours")
        keys[ck] = cv
    for ck, cv in keys.items():
        if cv in keys:
            errs.append(f"T5 CHART_DARK dark value {cv} is also a light key (the way back would be ambiguous)")
    decor = {ds.canon(c) for c in CHART_DECOR}
    for k, v in cmap.items():
        if ds.canon(k) in decor or ds.canon(v)[3] < 1:
            continue
        r = contrast(v, panel)
        if r < 3:
            errs.append(f"T5 CHART_DARK {k} -> {v}: {r:.2f}:1 on the dark card (< 3)")
    used = chart_colours(docs, pages) if pages else {}
    dark_vals = set(keys.values())
    for c, (sample, kinds) in sorted(used.items(), key=lambda kv: str(kv[0])):
        if c in dark_vals:
            errs.append(f"T5 a page uses {sample} as a LIGHT chart colour, but it is a dark value of the map")
        if c in keys or c in decor or c[3] == 0:
            continue
        # unknown: it keeps its light value in dark; a stroke / marker must then be >= 3:1 on the dark card
        a = c[3]
        base = "#%02x%02x%02x" % c[:3]
        r = contrast(base, panel)
        if a >= 0.5 and r < 3:
            errs.append(f"T5 chart colour {sample} ({', '.join(sorted(kinds))[:80]}) is not in CHART_DARK and is "
                        f"{r:.2f}:1 on the dark card")
    info.append(f"chart palette: {len(keys)} mapped colours, {len(used)} distinct colours on the pages")
    # T5 pairs (round 1, review V1): trace colours that share a chart keep their separation in dark
    pairs = chart_pairs(docs, pages) if pages else {}
    hx = lambda c: "#%02x%02x%02x" % c[:3]
    bad = 0
    for (a, b), where in sorted(pairs.items()):
        la, lb = hx(a), hx(b)
        da = hx(keys[a + (1.0,)]) if a + (1.0,) in keys else la
        db = hx(keys[b + (1.0,)]) if b + (1.0,) in keys else lb
        dl, dd = de2000(la, lb), de2000(da, db)
        if dl >= PAIR_DE and dd < PAIR_DE:
            bad += 1
            errs.append(f"T5 chart colours {la} / {lb} share {where[0]} (+{len(where) - 1}): CIEDE2000 {dl:.1f} in light, "
                        f"{dd:.1f} in dark ({da} / {db}; < {PAIR_DE:g}: the two series read as one)")
    info.append(f"{len(pairs)} colour pairs sharing a chart, {bad} losing their separation in dark")


def chart_pairs(docs, pages):
    """{(rgb_a, rgb_b): [page#div, ...]} for every two opaque trace colours (line / marker) that share a chart"""
    decor = {ds.canon(c) for c in CHART_DECOR}       # full colour incl. alpha: a TINT of NAVY is decor, NAVY is not
    out = {}
    for name in pages:
        html = open(os.path.join(docs, name), encoding="utf-8").read()
        for did, data, _layout in ds._plotly_calls(html):
            cols = set()
            for t in data:
                for path in (("line", "color"), ("marker", "color")):
                    o = t
                    for p in path:
                        o = o.get(p) if isinstance(o, dict) else None
                    for v in (o if isinstance(o, list) else [o]):
                        c = ds.canon(v) if isinstance(v, str) else None
                        if c and c not in decor and c[3] >= 0.5:
                            cols.add(c[:3])
            for a, b in combinations(sorted(cols), 2):
                out.setdefault((a, b), []).append(f"{name}#{did}")
    return out


def check_generators(errs, info, scripts=None, cmap=None):
    """T3 / T5 on the generators' own palettes (GEN_PALETTES), whatever today's pages happen to carry"""
    scripts = scripts or os.path.join(ROOT, "scripts")
    cmap = ds.CHART_DARK if cmap is None else cmap
    ckeys = {ds.canon(k) for k in cmap}
    n = 0
    for fn, names in GEN_PALETTES.items():
        p = os.path.join(scripts, fn)
        if not os.path.exists(p):
            info.append(f"{fn} not found (generator palettes not checked)")
            continue
        vals = []
        for node in ast.walk(ast.parse(open(p, encoding="utf-8").read())):
            if not isinstance(node, ast.Assign):
                continue
            for tgt in node.targets:
                pairs = (list(zip(tgt.elts, node.value.elts)) if isinstance(tgt, ast.Tuple) and isinstance(node.value, ast.Tuple)
                         else [(tgt, node.value)])
                for t_, v_ in pairs:
                    if not (isinstance(t_, ast.Name) and t_.id in names):
                        continue
                    if isinstance(v_, ast.Dict):
                        vals += [(t_.id, ast.literal_eval(x)) for x in v_.values]
                    elif isinstance(v_, ast.Constant) and isinstance(v_.value, str):
                        vals.append((t_.id, v_.value))
        for nm, v in vals:
            n += 1
            c = ds.canon(v)
            if c is None:
                continue
            if ds._KIND_MAP["bg"].get(c) is None:
                errs.append(f"T3 {fn} {nm} {v}: a sector-chip background with no dark token (design_system _BG)")
            if c not in ckeys:
                errs.append(f"T5 {fn} {nm} {v}: a chart colour that is not in CHART_DARK")
    info.append(f"generator palettes: {n} colours of {', '.join(GEN_PALETTES)}")


def check_tokens(errs, info):
    for t in DARK_TEXT:
        v = dark_of(t)
        for g in ("bg", "panel", "chip"):
            r = contrast(v, ds.ET_DARK[g])
            if r < 4.5:
                errs.append(f"T6 dark --{t} {v} on --{g}: {r:.2f}:1 (< 4.5)")
    on = ds.THEME_TOKENS["on-accent"][1]
    for t in FILLS:
        r = contrast(on, dark_of(t))
        if r < 4.5:
            errs.append(f"T6 dark --on-accent on --{t}: {r:.2f}:1 (< 4.5)")
    info.append(f"dark tokens: {len(DARK_TEXT)} text tokens x 3 grounds, on-accent x {len(FILLS)} fills")


def main():
    docs = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs")
    errs, warns, info = [], [], []
    pages = check_pages(docs, errs, warns, info)
    check_palette(docs, pages, errs, warns, info)
    check_generators(errs, info)
    check_tokens(errs, info)
    for w in warns:
        print("WARN", w)
    for e in errs:
        print("FAIL", e)
    print(f"THEME GATE (T1-T7): {'FAIL' if errs else 'PASS'} -- " + "; ".join(info))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
