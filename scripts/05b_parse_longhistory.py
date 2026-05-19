"""Parse long-history datasets into clean monthly/annual return series.
Outputs to data/longhistory/:
  french_monthly.csv   - regional equity total returns, monthly, 1990+
  shiller_monthly.csv  - US equity nominal total return + CAPE, monthly, 1871+
  damodaran_annual.csv - US asset-class annual returns, 1928+
"""
import os, io, zipfile, re
import numpy as np
import pandas as pd

LH = os.path.expanduser("~/LTCMA/data/longhistory")
RAW = f"{LH}/raw"

# ---------- 1. KEN FRENCH regional monthly market total returns ----------
FRENCH = {
    "DM_World": ("french_Developed.zip", "Developed_3_Factors.csv"),
    "DM_exUS":  ("french_Developed_exUS.zip", "Developed_ex_US_3_Factors.csv"),
    "Europe":   ("french_Europe.zip", "Europe_3_Factors.csv"),
    "Japan":    ("french_Japan.zip", "Japan_3_Factors.csv"),
    "EM":       ("french_Emerging.zip", "Emerging_5_Factors.csv"),
}
fr = {}
for region, (zf, csv) in FRENCH.items():
    with zipfile.ZipFile(f"{RAW}/{zf}") as z:
        lines = z.read(csv).decode("latin-1").splitlines()
    hdr = next(i for i, l in enumerate(lines) if l.lstrip().startswith(",Mkt-RF"))
    rows = []
    for l in lines[hdr + 1:]:
        parts = [p.strip() for p in l.split(",")]
        if len(parts) < 5 or not re.fullmatch(r"\d{6}", parts[0]):
            break  # reached annual section / footer
        ym, mktrf, rf = parts[0], float(parts[1]), float(parts[-1])
        rows.append((ym, (mktrf + rf) / 100.0))  # market total return, decimal
    s = pd.Series(dict(rows))
    s.index = pd.to_datetime(s.index, format="%Y%m") + pd.offsets.MonthEnd(0)
    fr[region] = s
    print(f"French {region:9s}: {len(s)} months  {s.index.min().date()}..{s.index.max().date()}")
french = pd.DataFrame(fr)
french.index.name = "Date"
french.to_csv(f"{LH}/french_monthly.csv")

# ---------- 2. SHILLER monthly US equity total return + CAPE ----------
sh = pd.read_excel(f"{RAW}/shiller_ie_data.xls", sheet_name="Data",
                   header=None, skiprows=8)
date_raw = pd.to_numeric(sh[0], errors="coerce")
cpi = pd.to_numeric(sh[4], errors="coerce")
real_tr = pd.to_numeric(sh[9], errors="coerce")   # Real Total Return Price
cape = pd.to_numeric(sh[12], errors="coerce")     # CAPE / P/E10
m = date_raw.notna() & real_tr.notna()
yr = date_raw[m].astype(int)
mo = ((date_raw[m] - yr) * 100).round().astype(int).clip(1, 12)
idx = pd.to_datetime(dict(year=yr, month=mo, day=1)) + pd.offsets.MonthEnd(0)
nominal_tr = (real_tr[m].values * cpi[m].values)        # nominal TR index
shiller = pd.DataFrame({"US_Eq_TR_index": nominal_tr,
                        "CAPE": cape[m].values}, index=idx)
shiller["US_Eq_ret"] = shiller["US_Eq_TR_index"].pct_change()
shiller.index.name = "Date"
shiller.to_csv(f"{LH}/shiller_monthly.csv")
print(f"\nShiller: {len(shiller)} months  {shiller.index.min().date()}..{shiller.index.max().date()}")
print(f"  CAPE  now={shiller['CAPE'].dropna().iloc[-1]:.1f}  "
      f"mean(all)={shiller['CAPE'].mean():.1f}  "
      f"mean(1990+)={shiller.loc['1990':,'CAPE'].mean():.1f}  "
      f"median(1990+)={shiller.loc['1990':,'CAPE'].median():.1f}")

# ---------- 3. DAMODARAN annual asset-class returns ----------
try:
    raw = pd.read_excel(f"{RAW}/damodaran_histret.xls",
                        sheet_name="Returns by year", header=None)
    # locate the header row containing 'Year' and the return columns
    hrow = None
    for i in range(len(raw)):
        rowvals = [str(x) for x in raw.iloc[i].tolist()]
        if any(v.strip() == "Year" for v in rowvals):
            hrow = i
            break
    da = pd.read_excel(f"{RAW}/damodaran_histret.xls",
                       sheet_name="Returns by year", header=hrow)
    da = da.loc[:, ~da.columns.astype(str).str.startswith("Unnamed")]
    da = da[pd.to_numeric(da["Year"], errors="coerce").notna()]
    da["Year"] = da["Year"].astype(int)
    da.to_csv(f"{LH}/damodaran_annual.csv", index=False)
    print(f"\nDamodaran annual: header row {hrow}, {len(da)} years "
          f"{da['Year'].min()}..{da['Year'].max()}")
    print("  columns:", [c for c in da.columns][:10])
except Exception as e:
    print(f"\nDamodaran parse issue: {e}")

print("\nDone. Long-history files in", LH)
