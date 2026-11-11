"""Wave r2 deploy kit: the GENERATED docs commit 2 carries, written in the live clone after commit 1 (the new sources),
without running any page generator.

FORWARD:
  1. docs/style.css exactly as 17_build_site.py writes it (its `CSS` literal, read with ast, through 17's own write
     expression `themed_css(CSS + ET_CSS, "style.css")`, text mode as 17) + docs/_design_system/{tokens,base,theme}.css
     (design_system.emit(), what 17 calls).
  2. every TRACKED page (docs/*.html, docs/archive/*.html): its committed blob through tools/theme_transform.py
     transform() -- the previous header replaced by the new one exactly once, then design_system.themed() -- so a page
     a generator keeps at its committed copy (19 / 25 on a Yahoo block, 20 best-effort) is dark-capable with the new
     header, exactly as its generator would now write it (proven on the staged render: transform(previous render) ==
     new render for every page, tools/theme_transform.py prove). A page whose previous header is not found exactly once
     is left as it is (it stays light: it does not link theme.css) and listed.
  The header strings must equal the kit's (kit/nav_old.txt, nav_new.txt) when computed in this clone.
REVERSE (rollback, after `git revert <commit 1>`): every tracked page carrying the theme head gets the previous head
  and header back (kit strings, exact, each once; the var(--token, literal) colours stay: in light they ARE the
  literals), style.css + tokens/base exactly as the reverted 17 writes them; theme.css is removed by the rollback's
  `git rm`.
usage: python -X utf8 -B deploy_docs_r2.py <repo> --kit <kit_dir> --old-glossary <file>      (forward, commit 2)
       python -X utf8 -B deploy_docs_r2.py <repo> --kit <kit_dir> --reverse                     (rollback)
Shipped in the repo (tools/, with theme_transform.py and the kit as tools/theme_kit/) by wave r2's commit 1, so the
rollback does not depend on any local folder (round 1, review PIPE-2).
Prints one JSON line {"changed": [...], "transformed": [...], "skipped": [...]} last; exit 1 on any inconsistency."""
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
KIT = Path(sys.argv[sys.argv.index("--kit") + 1]).resolve()
OLD_GL = Path(sys.argv[sys.argv.index("--old-glossary") + 1]).resolve() if "--old-glossary" in sys.argv else None
REVERSE = "--reverse" in sys.argv
SCRIPTS, DOCS = repo / "scripts", repo / "docs"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
os.chdir(SCRIPTS)


def die(msg):
    print(f"DEPLOY_DOCS_R2 ERROR: {msg}")
    sys.exit(1)


def git(*a):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True)
    if r.returncode != 0:
        die(f"git {' '.join(a)}: {r.stderr.decode('utf-8', 'replace')[:300]}")
    return r.stdout


# the kit strings carry no CR (they are Python string constants); a checkout that converted the files to CRLF must not
# make them miss the pages (round 1: the kit now ships in the repo, tools/theme_kit/)
kit = {n: (KIT / n).read_bytes().decode("utf-8").replace("\r\n", "\n")
       for n in ("nav_old.txt", "nav_new.txt", "head_old.txt", "head_new.txt")}
import design_system as ds  # noqa: E402  (the repo's own: new after commit 1, previous after the revert)

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
changed = ["docs/style.css", "docs/_design_system/tokens.css", "docs/_design_system/base.css"]
if (DOCS / "_design_system" / "theme.css").exists() and not REVERSE:
    changed.append("docs/_design_system/theme.css")

# ---- 2. the pages
pages = [p for p in git("ls-files", "--", "docs/*.html", "docs/archive/*.html").decode().split("\n") if p.strip()]
done, skipped = [], []
if not REVERSE:
    if OLD_GL is None:
        die("--old-glossary is required forward")
    import theme_transform as tt
    import glossary as gl
    old_nav = tt.nav_of(OLD_GL, SCRIPTS)
    if old_nav != kit["nav_old.txt"] or gl.NAV != kit["nav_new.txt"]:
        die("the header computed in this clone differs from the kit's (Street / Congress state changed?)")
    if ds.CSS_LINKS != kit["head_old.txt"] or ds.HEAD_LINKS != kit["head_new.txt"]:
        die("CSS_LINKS / HEAD_LINKS differ from the kit's")
    for rel in pages:
        blob = git("show", f"HEAD:{rel}").decode("utf-8")
        out, st = tt.transform(blob, old_nav, gl.NAV, ds, rel)
        if st == "themed":
            (repo / rel).write_bytes(out.encode("utf-8"))
            done.append(rel)
        else:
            skipped.append(f"{rel} ({st})")
else:
    for rel in pages:
        blob = git("show", f"HEAD:{rel}").decode("utf-8")
        if kit["head_new.txt"] not in blob:
            skipped.append(f"{rel} (no theme head)")
            continue
        if blob.count(kit["head_new.txt"]) != 1 or blob.count(kit["nav_new.txt"]) > 1:
            die(f"{rel}: theme head / header not found exactly once")
        out = blob.replace(kit["head_new.txt"], kit["head_old.txt"]).replace(kit["nav_new.txt"], kit["nav_old.txt"])
        if kit["head_new.txt"] in out or kit["nav_new.txt"] in out:
            die(f"{rel}: reverse substitution incomplete")
        (repo / rel).write_bytes(out.encode("utf-8"))
        done.append(rel)
changed += done
print(f"{'REVERSE' if REVERSE else 'FORWARD'}: style.css {len(style):,} chars; {len(done)} page(s) "
      f"{'restored' if REVERSE else 'transformed'}, {len(skipped)} left as they are")
print(json.dumps({"changed": changed, "transformed": done, "skipped": skipped}))
