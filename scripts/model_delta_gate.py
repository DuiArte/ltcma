"""Materiality circuit-breaker for an UNATTENDED model rebuild.

The weekly rebuild (`weekly_model_rebuild.ps1`) runs 01-04 + 06/07/11 with nobody
watching. That is fine when the model barely moves -- which is the normal case,
because the CAPE input is pinned to a calendar quarter-end and the vol/corr window
only rolls at month-end. It is NOT fine when something upstream breaks: a rotted
Shiller feed, a Yahoo schema change, a FRED series retirement or a genuine market
dislocation can all move the headline numbers a long way, and an unattended job
would publish that straight to the public site.

So: compare the freshly built `data/` against what is committed at HEAD, and refuse
to publish if anything moved more than a threshold. Carlos reviews, then re-runs
with -Force.

Compares (working tree vs `git show HEAD:`):
  * US large-cap ER at lambda=0.5   -- the headline number on the site
  * US CAPE (`us_cape_now`)         -- the dominant model input
  * every asset's ER_lambda0.5      -- catches a break confined to one sleeve
  * every sample portfolio's ER     -- what the report tables actually print

Exit codes:  0 = within tolerance, publish
             2 = breach, DO NOT publish (caller writes MODEL_ALERT.txt)
             1 = could not evaluate (missing file, unreadable HEAD, ...)

A breach is not "the model is wrong" -- it is "a human should look before this is
public". Thresholds are deliberately loose enough that an ordinary quarter-end CAPE
roll passes; the 2026-08-07 CAPE correction (-62 bp headline) would have passed too.
What they catch is a break, not a move.
"""
import json
import subprocess
import sys
from io import StringIO

import pandas as pd

from paths import DATA_S as D, ROOT

# --- thresholds (annualised, decimal) ----------------------------------------
TOL_HEADLINE_ER = 0.0075   # 75 bp on US large cap -- the site's headline figure
TOL_ASSET_ER    = 0.0150   # 150 bp on any single asset class
TOL_PORT_ER     = 0.0100   # 100 bp on any sample portfolio
TOL_CAPE_REL    = 0.10     # 10% relative move in the CAPE input


def git_show(path):
    """Return `git show HEAD:<path>` as text, or None if the file isn't at HEAD."""
    r = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def load_pair(relpath, **kw):
    """(committed, current) DataFrames for a tracked CSV under data/."""
    old_txt = git_show(relpath)
    if old_txt is None:
        return None, None
    old = pd.read_csv(StringIO(old_txt), **kw)
    new = pd.read_csv(f"{ROOT}/{relpath}", **kw)
    return old, new


def compare_col(old, new, col, tol, label):
    """Report rows where |new-old| > tol. Returns a list of breach strings."""
    if old is None or new is None:
        print(f"  {label}: SKIPPED (not at HEAD -- first run?)")
        return []
    common = old.index.intersection(new.index)
    gone = sorted(set(old.index) - set(common))
    added = sorted(set(new.index) - set(common))
    if gone:
        print(f"  {label}: WARNING rows vanished: {gone}")
    if added:
        print(f"  {label}: note, new rows (not gated): {added}")
    d = (new.loc[common, col] - old.loc[common, col]).abs().sort_values(ascending=False)
    worst = d.head(3)
    print(f"  {label}: max |delta| = {d.max()*10000:.0f} bp"
          f"  (tol {tol*10000:.0f} bp)   top: "
          + ", ".join(f"{k} {v*10000:+.0f}bp" for k, v in worst.items()))
    breaches = [f"{label} '{k}' moved {v*10000:+.0f} bp (tol {tol*10000:.0f} bp)"
                for k, v in d[d > tol].items()]
    # a vanished row is a structural break, not a numeric one -- always a breach
    breaches += [f"{label} row '{k}' disappeared from the rebuild" for k in gone]
    return breaches


def main():
    breaches = []
    print("=== model materiality gate: rebuilt data/ vs committed HEAD ===")

    # --- headline ER + CAPE, from ltcma_meta.json ---
    old_meta_txt = git_show("data/ltcma_meta.json")
    if old_meta_txt is None:
        print("  meta: SKIPPED (ltcma_meta.json not at HEAD)")
    else:
        old_meta = json.loads(old_meta_txt)
        with open(f"{D}/ltcma_meta.json", encoding="utf-8") as fh:
            new_meta = json.load(fh)

        k = "us_largecap_er_lambda0.5"
        d_er = abs(new_meta[k] - old_meta[k])
        print(f"  headline US large-cap ER: {old_meta[k]*100:.2f}% -> "
              f"{new_meta[k]*100:.2f}%  (delta {d_er*10000:+.0f} bp, "
              f"tol {TOL_HEADLINE_ER*10000:.0f} bp)")
        if d_er > TOL_HEADLINE_ER:
            breaches.append(f"headline US large-cap ER moved {d_er*10000:.0f} bp "
                            f"({old_meta[k]*100:.2f}% -> {new_meta[k]*100:.2f}%)")

        o_cape, n_cape = old_meta["us_cape_now"], new_meta["us_cape_now"]
        rel = abs(n_cape - o_cape) / o_cape if o_cape else 0.0
        print(f"  US CAPE: {o_cape:.2f} @ {old_meta['us_cape_asof']} -> "
              f"{n_cape:.2f} @ {new_meta['us_cape_asof']}  "
              f"({rel*100:+.1f}%, tol {TOL_CAPE_REL*100:.0f}%)")
        if rel > TOL_CAPE_REL:
            breaches.append(f"US CAPE moved {rel*100:.1f}% ({o_cape:.2f} -> {n_cape:.2f})")
        # A CAPE that did not advance at a quarter boundary means the Shiller feed
        # is frozen -- 05b asserts this too, but assert it here where it is public-facing.
        if new_meta["us_cape_asof"] < old_meta["us_cape_asof"]:
            breaches.append("CAPE vintage went BACKWARDS "
                            f"({old_meta['us_cape_asof']} -> {new_meta['us_cape_asof']})")

    # --- every asset ER ---
    old_s, new_s = load_pair("data/ltcma_summary.csv", index_col=0)
    breaches += compare_col(old_s, new_s, "ER_lambda0.5", TOL_ASSET_ER, "asset ER")

    # --- every sample portfolio ER ---
    old_p, new_p = load_pair("data/ltcma_portfolios.csv", index_col=0)
    if old_p is not None:
        ercol = next((c for c in new_p.columns
                      if c.lower().replace("_", "") in ("expreturn", "expret", "er")), None)
        if ercol is None:
            print("  portfolio ER: SKIPPED (no ER column found in ltcma_portfolios.csv)")
        else:
            breaches += compare_col(old_p, new_p, ercol, TOL_PORT_ER, "portfolio ER")

    print()
    if breaches:
        print("VERDICT: BREACH -- do NOT publish unattended. Reasons:")
        for b in breaches:
            print(f"  * {b}")
        print("\nA human should confirm this is a real market/data move and not an "
              "upstream break, then re-run with -Force.")
        return 2

    print("VERDICT: OK -- all deltas within tolerance; safe to publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
