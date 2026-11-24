# -*- coding: utf-8 -*-
"""Guard: no retail-broker or trading-platform name on any public file (wave r3s, 2026-11-17).

Public pages describe the retail broker and its trading platform in general words (Carlos, 2026-11-17). The
generators write neutral, true words (scripts/vendor_names.py scrub, called by glossary, 17, 22 and 24). This
guard is the backstop: it reads
every public file -- docs/** (what GitHub Pages serves, bt_*.html and portfolio.html included) and data/** (the
public repo shows it), as `git add docs data` would commit them (files .gitignore keeps out are never published, so
they are not read) -- and exits 1 when one still carries a term of the private term list, when a PDF / unknown
binary file there cannot be read, or when the private term list itself is missing or broken (fail closed: nothing
unchecked is published). A KNOWN file (vendor_names.KNOWN) is printed on every run. A finding names the kind of
term and the line, never the spelling.

The term list is private and lives outside the repo (vendor_names.terms_path(): Documents/LTCMA_private/
vendor_terms.txt under paths.DOCUMENTS, or the folder LTCMA_PRIVATE_DATA names). `python scripts/vendor_names.py
--terms` checks it. In the refresh a missing list already stops 17_build_site.py (TermsMissing), before this step.

Load-bearing in daily_refresh.ps1, right after guard_no_snapshot.py: the refresh fails BEFORE it commits, so a name
never reaches GitHub. Read-only: writes nothing. The same scan runs in ds_gate R2 and in confscan.sh.

Fix a failure in the generator that wrote the file (add a phrase rule to vendor_names.RULES if the catch-all
wording reads badly, plus a test line in the private term list; a name joined to other letters or digits, or a
long name in any spelling but the brand's own, always needs a phrase rule or a fix of the text: the scrub leaves
those forms as they are), never by editing docs/ or data/ by hand.
Optional arg: the repo to scan (default: this repo).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vendor_names  # noqa: E402

if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else vendor_names.ROOT
    sys.exit(vendor_names.main(["--scan", repo]))
