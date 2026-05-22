"""LTCMA — Step 22: low-token AI-readable companions for human outputs.

Standing rule (Carlos): every human report also gets a compact .txt for AI to
ingest cheaply. This builds docs/report.ai.txt from the report markdown:
section map + all numeric tables (pipe-compact) + lead sentence per section.

Re-run after 17_build_site.py. Idempotent.
"""
import os, re

REP  = os.path.expanduser("~/LTCMA/report")
DOCS = os.path.expanduser("~/LTCMA/docs")


def first_sentence(text):
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"[*_`>#]", "", t)            # strip md decoration
    m = re.split(r"(?<=[.!?])\s", t)
    return m[0][:240] if m and m[0] else ""


def digest(md_path, out_path, title):
    raw = open(md_path, encoding="utf-8").read()
    lines = raw.splitlines()

    contents, tables, leads = [], [], []
    cur_sec = None
    para_buf, captured_lead = [], False
    in_table = []

    def flush_table():
        nonlocal in_table
        if len(in_table) >= 2:
            # drop the markdown separator row (---|---)
            rows = [r for r in in_table if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", r)]
            compact = []
            for r in rows:
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                compact.append("|".join(cells))
            if compact:
                tables.append((cur_sec or "", compact))
        in_table = []

    def flush_para():
        nonlocal para_buf, captured_lead
        if para_buf and not captured_lead and cur_sec:
            s = first_sentence(" ".join(para_buf))
            if s:
                leads.append((cur_sec, s)); captured_lead = True
        para_buf = []

    for ln in lines:
        h = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if h:
            flush_table(); flush_para()
            level, txt = len(h.group(1)), h.group(2).strip()
            if level == 2:
                cur_sec = txt; captured_lead = False
                contents.append(txt)
            continue
        if "|" in ln and ln.strip().startswith("|"):
            flush_para(); in_table.append(ln); continue
        else:
            if in_table: flush_table()
        if ln.strip():
            para_buf.append(ln.strip())
        else:
            flush_para()
    flush_table(); flush_para()

    out = []
    out.append(f"{title} — AI digest (low-token companion to the human HTML/PDF).")
    out.append("format: numbered section map; tables pipe-compact; one lead sentence/section. "
               "full prose + charts live in report.html / LTCMA_2026.md.")
    out.append("")
    out.append("# CONTENTS")
    for c in contents:
        out.append(f"- {c}")
    out.append("")
    out.append("# SECTION LEADS")
    for sec, s in leads:
        out.append(f"[{sec}] {s}")
    out.append("")
    out.append("# TABLES (pipe-compact)")
    for sec, rows in tables:
        out.append(f"## {sec}")
        out.extend(rows)
        out.append("")

    open(out_path, "w", encoding="utf-8").write("\n".join(out))
    n_tok_est = len("\n".join(out)) // 4
    print(f"  {out_path}  (~{n_tok_est} tokens, {len(contents)} sections, {len(tables)} tables)")


print("=== LTCMA 22 — AI copies ===")
digest(f"{REP}/LTCMA_2026.md", f"{DOCS}/report.ai.txt", "LTCMA 2026")
print("Done.")
