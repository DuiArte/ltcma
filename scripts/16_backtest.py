"""Vintage backtest of the LTCMA building-block methodology.
For each past year-end, reconstruct the model's 10-year forecast using ONLY
data available then, and compare to the realized 10-year outcome.
- Equity: building-block (DY + real growth + inflation + lambda*CAPE reversion)
- Bond  : starting 10-year Treasury yield -> realized 10-year bond return
No look-ahead: fair-value CAPE = expanding mean; inflation = trailing realized.
Outputs: data/backtest_results.csv, report/figures/fig_backtest.png
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from paths import DATA_S as D  # repo-anchored (2026-06-10)
import paths as _paths
FIG = str(_paths.REPORT / "figures")
NAVY, GOLD, RED, GREY = "#1a3a5c", "#c8961e", "#a23b3b", "#8a9099"
G_REAL, HORIZON = 0.019, 10           # real EPS growth assumption, years

# ---- raw Shiller monthly: P, D, CPI, GS10, CAPE ----
raw = pd.read_excel(f"{D}/longhistory/raw/shiller_ie_data.xls",
                    sheet_name="Data", header=None, skiprows=8)
draw = pd.to_numeric(raw[0], errors="coerce")
m = draw.notna()
yr = draw[m].astype(int)
mo = ((draw[m] - yr) * 100).round().astype(int).clip(1, 12)
idx = pd.to_datetime(dict(year=yr, month=mo, day=1)) + pd.offsets.MonthEnd(0)
sh = pd.DataFrame({
    "P": pd.to_numeric(raw[1], errors="coerce")[m].values,
    "D": pd.to_numeric(raw[2], errors="coerce")[m].values,
    "CPI": pd.to_numeric(raw[4], errors="coerce")[m].values,
    "GS10": pd.to_numeric(raw[6], errors="coerce")[m].values,
    "RealTR": pd.to_numeric(raw[9], errors="coerce")[m].values,
    "CAPE": pd.to_numeric(raw[12], errors="coerce")[m].values}, index=idx)
sh = sh[~sh.index.duplicated()]
sh["TR"] = sh["RealTR"] * sh["CPI"]          # nominal total-return index
sh["DY"] = sh["D"] / sh["P"]
dec = sh[sh.index.month == 12].copy()        # year-end vintages

# ---- EQUITY backtest ----
rows = []
for t in dec.index:
    fut = t + pd.DateOffset(years=HORIZON)
    if fut not in sh.index or pd.isna(dec.loc[t, "CAPE"]):
        continue
    cape = dec.loc[t, "CAPE"]
    dy = dec.loc[t, "DY"]
    fair = sh.loc[:t, "CAPE"].mean()                       # expanding, no look-ahead
    past_cpi = sh["CPI"].asof(t - pd.DateOffset(years=10))
    infl = (dec.loc[t, "CPI"] / past_cpi) ** (1 / 10) - 1 if past_cpi else 0.024
    realized = (sh.loc[fut, "TR"] / dec.loc[t, "TR"]) ** (1 / HORIZON) - 1
    rec = {"vintage": t.year, "CAPE": cape, "realized": realized}
    for lam in (0.0, 0.5, 1.0):
        rev = (fair / cape) ** (1 / HORIZON) - 1
        rec[f"pred_l{lam}"] = dy + G_REAL + infl + lam * rev
    rows.append(rec)
eq = pd.DataFrame(rows)

# ---- BOND backtest: starting 10y yield -> realized 10y bond return ----
dam = pd.read_csv(f"{D}/longhistory/damodaran_annual.csv")
tb = pd.to_numeric(dam["US T. Bond (10-year)"], errors="coerce")
if tb.abs().median() > 1.5:
    tb = tb / 100
tb.index = dam["Year"].astype(int)
brows = []
for t in dec.index:
    y0 = dec.loc[t, "GS10"]
    yrs = range(t.year + 1, t.year + 1 + HORIZON)
    if pd.isna(y0) or not all(y in tb.index for y in yrs):
        continue
    realized = np.prod([1 + tb[y] for y in yrs]) ** (1 / HORIZON) - 1
    brows.append({"vintage": t.year, "start_yield": y0 / 100, "realized": realized})
bond = pd.DataFrame(brows)

# ---- metrics ----
def stats(pred, real):
    e = pred - real
    sd = real.std()
    return (np.corrcoef(pred, real)[0, 1], np.abs(e).mean(), e.mean(),
            (np.abs(e) < 0.5 * sd).mean())

print("=== EQUITY building-block backtest (US, 10-year, 1900s-2014 vintages) ===")
print(f"{'lambda':>8s} {'corr':>7s} {'MAE':>8s} {'bias':>8s} {'hit<0.5SD':>10s}")
for lam in (0.0, 0.5, 1.0):
    c, mae, bias, hit = stats(eq[f"pred_l{lam}"], eq["realized"])
    print(f"{lam:8.1f} {c:7.2f} {mae*100:7.2f}% {bias*100:+7.2f}% {hit*100:9.0f}%")
n = len(eq)
print(f"  ({n} vintages, {eq.vintage.min()}-{eq.vintage.max()})")

# modern subsample
mod = eq[eq.vintage >= 1990]
print(f"\n  modern vintages (1990+, n={len(mod)}):")
for lam in (0.0, 0.5, 1.0):
    c, mae, bias, hit = stats(mod[f"pred_l{lam}"], mod["realized"])
    print(f"   lambda={lam}: corr {c:.2f}  MAE {mae*100:.2f}%  bias {bias*100:+.2f}%")

cb, maeb, biasb, hitb = stats(bond["start_yield"], bond["realized"])
print(f"\n=== BOND backtest: starting 10y yield vs realized 10y return ===")
print(f"  corr {cb:.2f}   MAE {maeb*100:.2f}%   bias {biasb*100:+.2f}%   "
      f"hit<0.5SD {hitb*100:.0f}%   ({len(bond)} vintages)")

eq.to_csv(f"{D}/backtest_results.csv", index=False)
bond.to_csv(f"{D}/backtest_bond.csv", index=False)

# ---- figure ----
fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.7))
# (1) equity predicted vs realized
sc = ax[0].scatter(eq["pred_l0.5"] * 100, eq["realized"] * 100,
                   c=eq["vintage"], cmap="viridis", s=34)
lim = [-4, 20]
ax[0].plot(lim, lim, "--", color=GREY, lw=1)
ax[0].set_xlim(lim); ax[0].set_ylim(lim)
ax[0].set_xlabel("forecast 10y return (%)"); ax[0].set_ylabel("realized 10y return (%)")
ax[0].set_title("Equity building-block (λ=0.5)", color=NAVY, fontweight="bold")
fig.colorbar(sc, ax=ax[0], label="vintage year")
# (2) CAPE vs realized
ax[1].scatter(eq["CAPE"], eq["realized"] * 100, color=NAVY, s=30)
ax[1].set_xlabel("starting CAPE"); ax[1].set_ylabel("realized 10y return (%)")
ax[1].set_title("Starting valuation predicts return", color=NAVY, fontweight="bold")
ax[1].grid(alpha=.25)
# (3) bond starting yield vs realized
ax[2].scatter(bond["start_yield"] * 100, bond["realized"] * 100, color=GOLD, s=30)
bl = [0, 16]
ax[2].plot(bl, bl, "--", color=GREY, lw=1)
ax[2].set_xlim(bl); ax[2].set_ylim(bl)
ax[2].set_xlabel("starting 10y yield (%)"); ax[2].set_ylabel("realized 10y return (%)")
ax[2].set_title(f"Bond: yield predicts return (r={cb:.2f})", color=NAVY, fontweight="bold")
fig.suptitle("LTCMA methodology backtest — forecast vs realized 10-year outcomes",
             fontweight="bold", color=NAVY)
fig.tight_layout()
fig.savefig(f"{FIG}/fig_backtest.png", dpi=130)
print(f"\nwrote backtest_results.csv, backtest_bond.csv, fig_backtest.png")
