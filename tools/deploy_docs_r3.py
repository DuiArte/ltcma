"""Wave r3 deploy kit: the GENERATED docs commit 2 carries, written in the live clone after commit 1 (the new sources),
without running any page generator. Shipped in the repo (tools/) by r3's commit 1, so the rollback needs no local folder.

FORWARD (commit 2):
  1. docs/style.css exactly as 17_build_site.py writes it (its `CSS` literal, read with ast, through 17's own write
     expression, text mode as 17) + docs/_design_system/*.css (design_system.emit(), what 17 calls) -- r3 changes
     style.css (the sticky table heads, the printed footer, the fifth money tile; builder B: the "On this page" bar
     and the note() component)
  2. design_system.emit_share(docs): the favicon set + the share cards (copied from assets/img, byte-identical),
     docs/404.html, docs/sitemap.xml, docs/robots.txt -- exactly what 17 now writes on every build; builder B: every
     hero photograph the pages now show (design_system.all_asset_names(), copied byte-identically like every
     generator does) and the retired photographs' files (RETIRED_HERO_KEYS) removed from docs/assets/img
  3. every TRACKED page (docs/*.html, docs/archive/*.html): its committed blob through design_system.hero_retrofit
     (builder B: the page's own photograph, its committed hero text kept byte for byte, the footer credit),
     design_system.otp_insert and design_system.site_head -- otp_insert + site_head are what themed() runs on every
     generated page, hero_retrofit is what hero_for() writes -- so a page a generator keeps at its committed copy
     (19 / 25 on a Yahoo block, 20 on a FRED block) gets the r3 head, its photograph and its bar exactly as its
     generator would write them. A redirect stub / unknown page is left as it is.
REVERSE (rollback, after `git revert <commit 1>`; self-contained: the reverted design_system has no r3 code):
  every tracked page loses its share block (the page's own <title> comes back from the block's opening comment), goes
  back to the full Plotly bundle, loses the "On this page" bar (portfolio.html: the currency switch goes back into
  r2's .ccy-bar, first in <main>) and gets r2's hero back (R2_HEROES through the reverted design_system.hero(); the
  stock / regime pages their plain hero); the r3 photographs' files leave docs/assets/img (the reverted generators
  re-emit r2's); style.css + the sheets exactly as the reverted 17 writes them. The share files are removed by the
  rollback's `git rm`.
usage: python -X utf8 -B deploy_docs_r3.py <repo>              (forward)
       python -X utf8 -B deploy_docs_r3.py <repo> --reverse    (rollback)
Prints one JSON line {"changed": [...], "transformed": [...], "skipped": [...], "heroes_new": [...], "removed": [...]}
last; exit 1 on any inconsistency."""
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
REVERSE = "--reverse" in sys.argv
SCRIPTS, DOCS = repo / "scripts", repo / "docs"
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
os.chdir(SCRIPTS)
FULL = '<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>'
CART = '<script src="https://cdn.plot.ly/plotly-cartesian-2.35.0.min.js"></script>'
SHARE = re.compile(r'<!--share title0="([^"]*)"-->.*?<!--/share-->', re.S)
# builder B, reverse: r2's photographs (page -> key, object-position) and the r3-only keys
R2_HEROES = {"index.html": ("cliffs", "center 38%"), "portfolio.html": ("cliffs_detail", "center 40%"),
             "research-library.html": ("cliffs_detail", "center 45%"), "ltcma-consensus.html": ("pillars", "center 30%"),
             "congressional-activity.html": ("pillars_base", "center 60%")}
R3_KEYS = ("zs7", "hh4647", "ngc6822", "ngc6440", "earth_night")
OTP = re.compile(r'<nav class="otp" aria-label="On this page">.*?</nav>\n?', re.S)
SWITCH = re.compile(r'(<div class="ccy-in" role="group".*?</button></div></div>)', re.S)
HERO_IMG = re.compile(r'<section class="hero hero--img ?([^"]*)" data-hero="([^"]+)">(.*?)</section>', re.S)
FOOT = re.compile(r'(<footer class="shell-foot"><div class="container">)(.*?)(</div></footer>)', re.S)
CREDITS = re.compile(r'<p class="credits">.*?</p>', re.S)


def die(msg):
    print(f"DEPLOY_DOCS_R3 ERROR: {msg}")
    sys.exit(1)


def git(*a):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True)
    if r.returncode != 0:
        die(f"git {' '.join(a)}: {r.stderr.decode('utf-8', 'replace')[:300]}")
    return r.stdout


def strip(html):
    """The exact inverse of design_system.site_head's head (kept here: the reverted design_system has none)."""
    m = SHARE.search(html)
    if m:
        t0 = m.group(1).replace("-%2D", "--").replace("%22", '"').replace("%25", "%")
        html = html[:m.start()] + html[m.end():]
        html = re.sub(r"<title>.*?</title>", lambda _m: f"<title>{t0}</title>", html, count=1, flags=re.S)
    return html.replace(CART, FULL)


def r2_body(html, page, ds):
    """Builder B, reverse: the bar out (the portfolio's switch back into r2's .ccy-bar) and r2's hero + footer credit
    back (the hero's inner HTML byte for byte). Exact inverse of hero_retrofit + otp_insert on an r2 page."""
    m = OTP.search(html)
    if m:
        sw = SWITCH.search(m.group(0))
        html = html[:m.start()] + html[m.end():]
        if sw:
            k = html.find('<main class="container">\n')
            if k < 0:
                die(f"{page}: no <main> to put the currency switch back into")
            k += len('<main class="container">\n')
            html = html[:k] + '<div class="ccy-bar">' + sw.group(1) + '</div>\n' + html[k:]
    h = list(HERO_IMG.finditer(html))
    if len(h) != 1:
        return html
    cls, key, body = h[0].groups()
    want = R2_HEROES.get(page)
    if want and key == want[0]:
        return html
    if key not in R3_KEYS and key not in ("pillars",):
        return html
    a = body.find('<div class="container hero-in">')
    b = body.rfind('</div><p class="container hero-credit">')
    if a < 0 or b < 0:
        die(f"{page}: an r3 hero without its inner / credit (cannot restore r2's)")
    inner = body[a + len('<div class="container hero-in">'):b]
    new = (ds.hero(want[0], inner, str(DOCS), pos=want[1], cls=cls) if want
           else f'<section class="hero"><div class="container">{inner}</div></section>')
    html = html[:h[0].start()] + new + html[h[0].end():]
    f = list(FOOT.finditer(html))
    if len(f) != 1:
        die(f"{page}: footer not found once")
    hd, mid, tl = f[0].groups()
    mid = CREDITS.sub("", mid) + (ds.credits_footer(want[0]) if want else "")
    return html[:f[0].start()] + hd + mid + tl + html[f[0].end():]


import design_system as ds  # noqa: E402  (the repo's own: r3 after commit 1, r2 after the revert)

# ---- 1. style.css exactly as 17 writes it + the design-system sheets
tree = ast.parse((SCRIPTS / "17_build_site.py").read_text(encoding="utf-8"))
css = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CSS" for t in node.targets):
        css = ast.literal_eval(node.value)
write_expr = None
for node in ast.walk(tree):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write"
            and isinstance(node.func.value, ast.Call) and getattr(node.func.value.func, "id", "") == "open"
            and "style.css" in ast.unparse(node.func.value.args[0])):
        write_expr = node.args[0]
if css is None or write_expr is None:
    die("could not find 17's CSS literal / its style.css write")
names = {n.id for n in ast.walk(write_expr) if isinstance(n, ast.Name)}
if not names <= {"CSS", "ET_CSS", "themed_css"}:
    die(f"17 writes style.css from names this tool does not know: {sorted(names)}")
env = {"CSS": css, "ET_CSS": getattr(ds, "ET_CSS", "")}
if "themed_css" in names:
    env["themed_css"] = ds.themed_css
style = eval(compile(ast.Expression(write_expr), "17-style-write", "eval"), env)
with open(DOCS / "style.css", "w", encoding="utf-8") as fh:          # text mode, as 17 does
    fh.write(style)
ds.emit(str(DOCS))
changed = ["docs/style.css", "docs/_design_system/tokens.css", "docs/_design_system/base.css",
           "docs/_design_system/theme.css"]
heroes_new, removed = [], []
IMG = DOCS / "assets" / "img"
tracked = {p.strip() for p in git("ls-files", "--", "docs/assets/img").decode().split("\n") if p.strip()}

# ---- 2. the share files + the photographs (forward only)
if not REVERSE:
    if not hasattr(ds, "site_head") or not hasattr(ds, "emit_share") or not hasattr(ds, "hero_retrofit"):
        die("the repo's design_system has no site_head / emit_share / hero_retrofit (commit 1 not applied?)")
    if not ds.emit_share(str(DOCS)):
        die("a favicon / card source is missing under assets/img")
    changed += ["docs/404.html", "docs/sitemap.xml", "docs/robots.txt"] + [f"docs/{ds.ASSET_URL}/{n}" for n in ds.SHARE_FILES]
    imgs = [n for n in ds.all_asset_names() if n.startswith("hero_")]
    if not ds.emit_assets(str(DOCS), imgs):
        die("a hero photograph's source is missing under assets/img")
    for n in imgs:
        rel = f"docs/{ds.ASSET_URL}/{n}"
        changed.append(rel)
        if rel not in tracked:
            heroes_new.append(rel)
    for f in sorted(IMG.glob("hero_*")) if IMG.is_dir() else []:
        if any(f.name.startswith(f"hero_{k}_") for k in ds.RETIRED_HERO_KEYS):
            f.unlink()
            removed.append(f"docs/{ds.ASSET_URL}/{f.name}")
    changed += removed
else:
    # the r3 photographs leave docs/ (r2's come back through the reverted hero() below / the refresh)
    for f in sorted(IMG.glob("hero_*")) if IMG.is_dir() else []:
        if any(f.name.startswith(f"hero_{k}_") for k in R3_KEYS):
            f.unlink()
            removed.append(f"docs/{ds.ASSET_URL}/{f.name}")
    changed += removed

# ---- 3. the pages
pages = [p for p in git("ls-files", "--", "docs/*.html", "docs/archive/*.html").decode().split("\n") if p.strip()]
done, skipped, bar_later = [], [], []
for rel in pages:
    if rel == "docs/404.html":
        continue                                  # written in step 2 (forward) / removed by git rm (reverse)
    blob = git("show", f"HEAD:{rel}").decode("utf-8")
    page = rel[len("docs/"):]
    if REVERSE:
        out = r2_body(strip(blob), page, ds)
    else:
        hb = ds.hero_retrofit(blob, page, str(DOCS))
        out = ds.site_head(ds.otp_insert(hb, page), page)
        ph = ds.page_hero(page)
        if ph and "<!--share" in out and f'data-hero="{ph[0]}"' not in out:
            die(f"{rel}: the page's photograph ({ph[0]}) could not be put on the committed page")
        # a committed page rendered by older code may carry fewer than two of the ids its bar links (its generator
        # adds them at the next render, and themed() then adds the bar): it stays without a bar until then
        if ds.page_sections(page) and ds.OTP_MARK not in out and "<!--share" in out:
            if ds.section_nav(page, hb):
                die(f"{rel}: the On-this-page bar could not be put on the committed page")
            bar_later.append(rel)
    if out == blob:
        skipped.append(f"{rel} (unchanged)")
        continue
    if not REVERSE and ("<!--share" not in out and CART not in out):
        die(f"{rel}: changed without the r3 head")
    (repo / rel).write_bytes(out.encode("utf-8"))
    done.append(rel)
changed += done
if REVERSE:
    left = [p for p in done if re.search(r'data-hero="(' + "|".join(R3_KEYS) + ')"', (repo / p).read_text(encoding="utf-8"))]
    if left:
        die(f"r3 photographs still on {left}")
print(f"{'REVERSE' if REVERSE else 'FORWARD'}: style.css {len(style):,} chars; {len(done)} page(s) "
      f"{'restored' if REVERSE else 'transformed'}, {len(skipped)} left as they are; photographs: {len(heroes_new)} new, "
      f"{len(removed)} removed; bar at the next render: {bar_later}")
print(json.dumps({"changed": changed, "transformed": done, "skipped": skipped, "heroes_new": heroes_new,
                  "removed": removed, "bar_later": bar_later}))
