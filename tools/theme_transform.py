"""The page transformation of wave r2 (dark mode): what the new generators do to a page they render, applied to a
page that was rendered by the previous code. Used (a) to build the staged previews of the pages 19 / 20 / 25 render
(they cannot run offline: Yahoo / FRED), (b) by the deploy's commit 2 on every committed page, and (c) to PROVE it:
`--prove A B` checks transform(A/<p>) == B/<p> byte for byte for every page both trees rendered from the same data.

transform(page) = the previous glossary.NAV replaced by the new one (exactly once; the new NAV adds the theme
control + its script), then design_system.themed() (head boot + theme.css link + colour literals -> var(--token,
literal)). A page whose previous header is not found exactly once is NOT touched (it stays light: it does not link
theme.css). themed() is idempotent, so a page that already carries the new header is only themed.

usage:
  python -X utf8 -B theme_transform.py prove <repo_new> <old_glossary.py> <dirA> <dirB> [pages...]
  python -X utf8 -B theme_transform.py apply <repo_new> <old_glossary.py> <src_dir> <dst_dir> <page> [<page>...]
"""
import json
import sys
from pathlib import Path


def load(repo_new):
    scripts = Path(repo_new).resolve() / "scripts"
    sys.path.insert(0, str(scripts))
    sys.dont_write_bytecode = True
    import design_system as ds
    import glossary as gl
    return ds, gl, scripts


def nav_of(src, scripts):
    """glossary.NAV as that glossary source computes it FOR THIS REPO (Street / Congress tabs depend on data files
    the module finds through __file__)."""
    g = {"__file__": str(scripts / "glossary.py"), "__name__": "glossary_for_theme"}
    exec(compile(Path(src).read_text(encoding="utf-8"), str(src), "exec"), g)
    return g["NAV"]


# Script-side colour literals the wave changed in a generator's own JS (themed() never rewrites inside <script>):
# exact (old, new) pairs, each applied at most once.
SCRIPT_PAIRS = [("r.style.background='rgba(10,37,64,.07)';",                       # 23: range-button flash
                 "r.style.background='var(--l-tint07,rgba(10,37,64,.07))';"),
                # colour names in prose that must hold in both themes (17 correlation note, 18 entries note)
                ("Which assets move together (dark blue) and which move in",
                 "Which assets move together (blue) and which move in"),
                ("of the book (navy) and of the S&amp;P 500 (grey), flows",
                 "of the book (blue) and of the S&amp;P 500 (grey), flows"),
                # round 1 (review PIPE-5): 23's empty-window row, written by its range script
                ('<td colspan="6" style="text-align:left;color:#888">Window too short',
                 '<td colspan="6" style="text-align:left;color:var(--l-muted,#888)">Window too short')]


def transform(html, old_nav, new_nav, ds, name="page"):
    """Returns (new_html, status). status: 'themed' | 'already' | 'skipped:<why>'."""
    if ds.HEAD_LINKS in html and new_nav in html:
        return html, "already"
    n_old, n_new = html.count(old_nav), html.count(new_nav)
    if n_new == 1 and n_old == 0:
        out = html
    elif n_old == 1 and n_new == 0:
        out = html.replace(old_nav, new_nav)
        if out.replace(new_nav, old_nav) != html:
            return html, "skipped:header substitution not exact"
    else:
        return html, f"skipped:previous header {n_old}x, new header {n_new}x"
    if out.count(ds.CSS_LINKS) != 1:
        return html, f"skipped:CSS_LINKS {out.count(ds.CSS_LINKS)}x"
    for a, b in SCRIPT_PAIRS:
        if out.count(a) > 1:
            return html, "skipped:script pair not unique"
        out = out.replace(a, b)
    del ds.THEME_UNMAPPED[:]
    t = ds.themed(out, name)
    if ds.HEAD_LINKS not in t:
        return html, "skipped:themed() did not apply"
    return t, "themed"


def main():
    mode, repo_new, old_gl = sys.argv[1], sys.argv[2], sys.argv[3]
    ds, gl, scripts = load(repo_new)
    old_nav, new_nav = nav_of(old_gl, scripts), gl.NAV
    assert old_nav != new_nav, "old and new NAV are identical"
    if mode == "prove":
        A, B = Path(sys.argv[4]), Path(sys.argv[5])
        names = sys.argv[6:] or sorted(p.relative_to(A).as_posix() for p in A.rglob("*.html"))
        ok, bad, skip = [], [], []
        for n in names:
            a, b = A / n, B / n
            if not a.exists() or not b.exists():
                skip.append(f"{n} (missing)")
                continue
            ha, hb = a.read_text(encoding="utf-8"), b.read_text(encoding="utf-8")
            t, st = transform(ha, old_nav, new_nav, ds, n)
            if st.startswith("skipped"):
                (ok if t == hb else bad).append(f"{n} ({st})")
                continue
            (ok if t == hb else bad).append(n)
        print(json.dumps({"equal": ok, "different": bad, "skipped": skip}, indent=1))
        sys.exit(1 if bad else 0)
    if mode == "apply":
        src, dst = Path(sys.argv[4]), Path(sys.argv[5])
        res = {}
        for n in sys.argv[6:]:
            h = (src / n).read_text(encoding="utf-8")
            t, st = transform(h, old_nav, new_nav, ds, n)
            res[n] = st
            if st.startswith("skipped"):
                continue
            (dst / n).parent.mkdir(parents=True, exist_ok=True)
            with open(dst / n, "w", encoding="utf-8") as fh:      # text mode, as the generators write
                fh.write(t)
        print(json.dumps(res, indent=1))
        sys.exit(1 if any(v.startswith("skipped") for v in res.values()) else 0)


if __name__ == "__main__":
    main()
