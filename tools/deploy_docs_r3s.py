"""Wave r3s deploy, commit 2: put the committed public files in neutral words WITHOUT running a page generator.

usage: python -X utf8 -B tools/deploy_docs_r3s.py <repo> [--check]

Why. Commit 1 ships the sources (scripts/vendor_names.py and the generators that call it). The pages committed on
main were written by the r3 generators and still name the retail broker / trading platform. The next refresh
re-renders them, but a best-effort step that fails (24 without the private hub, say) would leave its committed page
as it is -- and the load-bearing guard_vendor_names.py would then stop every refresh. So commit 2 rewrites the
committed files exactly as the r3s generators would:
  docs/** text files   vendor_names.scrub() on the whole file (the same function 17 / 22 / 23 / 24 / 27 / 31 now
                       call; Plotly "bdata" payloads and data: URIs are never touched). A file without a name is
                       left byte for byte.
  data/backtests_strategies.json   vendor_names.scrub_obj() on its values, written as 24 writes it
                       (json.dump, indent=2, ensure_ascii=False, text mode)
Proof (wave r3s gates): this tool on the r3 render of the same data = the r3s render, every file, byte for byte.
Then vendor_names.scan() must PASS on the repo. Prints one JSON line {"changed": [...], "scan": "PASS"|"FAIL"}.
--check: print what would change, write nothing (exit 0).

There is no reverse step: rolling back wave r3s = `git revert` of commit 1 and the refresh, whose r3 generators
write the old wording again. A page left neutral until then is harmless.
"""
import json
import os
import sys

REPO = os.path.abspath(sys.argv[1])
CHECK = "--check" in sys.argv[2:]
sys.path.insert(0, os.path.join(REPO, "scripts"))
import vendor_names as vn  # noqa: E402

TEXT = {".html", ".htm", ".txt", ".css", ".js", ".json", ".xml", ".svg"}
CATALOG = os.path.join("data", "backtests_strategies.json")


def main():
    changed = []
    docs = os.path.join(REPO, "docs")
    for dp, dn, fns in os.walk(docs):
        dn.sort()
        for fn in sorted(fns):
            if os.path.splitext(fn)[1].lower() not in TEXT:
                continue
            p = os.path.join(dp, fn)
            raw = open(p, "rb").read()
            text = raw.decode("utf-8")
            new = vn.scrub(text)
            if new != text:
                changed.append(os.path.relpath(p, REPO).replace(os.sep, "/"))
                if not CHECK:
                    with open(p, "wb") as fh:
                        fh.write(new.encode("utf-8"))
    cat = os.path.join(REPO, CATALOG)
    if os.path.exists(cat):
        with open(cat, encoding="utf-8") as fh:
            data = json.load(fh)
        safe = vn.scrub_obj(data)
        if safe != data:
            changed.append(CATALOG.replace(os.sep, "/"))
            if not CHECK:
                with open(cat, "w", encoding="utf-8") as out:          # as 24_backtests.load_catalog writes it
                    json.dump(safe, out, indent=2, ensure_ascii=False)
    for rel in changed:
        print(("WOULD CHANGE " if CHECK else "FORWARD ") + rel)
    bad, counts = vn.scan(REPO)
    for rel, why in bad:
        print(f"  FAIL {rel}: {why}")
    if CHECK:
        print(json.dumps({"would_change": changed, "scan_now": "PASS" if not bad else "FAIL"}))
        return 0
    print(json.dumps({"changed": changed, "scan": "PASS" if not bad else "FAIL", "files": sum(counts.values())}))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
