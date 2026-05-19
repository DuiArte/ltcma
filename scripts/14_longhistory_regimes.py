"""Recalibrate regime risk using long history (2000-2026).
The 2013-26 ETF window contains no global financial crisis.
- Equity long history: Shiller monthly (clean, covers 2000-02 + 2008 + 2020).
- FX long history: FxPro M5 pairs (clean continuous spot data since 2000).
NB: the FxPro INDEX CFDs (#USNDAQ100 etc.) were found to have spurious
year-boundary jumps in early years and are excluded -- FX pairs only.
Output: data/regime_longhistory.csv
"""
import os
import numpy as np
import pandas as pd

D = os.path.expanduser("~/LTCMA/data")

# ---- clean long series: equity from Shiller, FX from FxPro ----
fx = pd.read_csv(f"{D}/fx_monthly.csv", index_col=0, parse_dates=True)
fxret = fx[[c for c in fx.columns if c.endswith("_ret")]].copy()
fxret.columns = [c[:-4] for c in fxret.columns]
shiller = pd.read_csv(f"{D}/longhistory/shiller_monthly.csv", index_col=0, parse_dates=True)

series = {"US_Equity": shiller["US_Eq_ret"].dropna(),
          "EURUSD": fxret["EURUSD"].dropna(), "USDJPY": fxret["USDJPY"].dropna(),
          "GBPUSD": fxret["GBPUSD"].dropna(), "USDMXN": fxret["USDMXN"].dropna(),
          "GOLD": fxret["GOLD"].dropna()}

# ---- uncertainty indices, monthly ----
gpr = pd.read_excel(f"{D}/signals_gpr_raw.xls")[["month", "GPR"]].set_index("month")["GPR"]
gpr.index = gpr.index + pd.offsets.MonthEnd(0)
sig = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)
epu = sig["EPU_US"].dropna()
epu.index = epu.index + pd.offsets.MonthEnd(0)
epu = epu.groupby(epu.index).last()

# ---- classify the long window (2000+) into calm/stress ----
base = series["US_Equity"].loc["2000":].index
idx = base.intersection(gpr.index).intersection(epu.index)
z = lambda s: (s - s.loc[idx].mean()) / s.loc[idx].std()
score = (z(gpr).loc[idx] + z(epu).loc[idx]) / 2
stress = score >= score.quantile(2 / 3)
print(f"Long window {idx.min().date()}..{idx.max().date()} ({len(idx)} months); "
      f"stress months: {int(stress.sum())} ({stress.mean()*100:.0f}%)")

# ---- regime vol multiples on the clean long series ----
print(f"\n{'series':12s} {'window':>9s} {'vol_calm':>9s} {'vol_stress':>11s} {'multiple':>9s}")
rows = []
for name, r in series.items():
    common = r.index.intersection(idx)
    rc = r.reindex(common)
    st = stress.reindex(common)
    vc, vs = rc[~st].std() * np.sqrt(12), rc[st].std() * np.sqrt(12)
    rows.append({"series": name, "n_months": len(common),
                 "vol_calm": vc, "vol_stress": vs, "vol_multiple": vs / vc})
    print(f"{name:12s} {len(common):8d}m {vc*100:8.1f}% {vs*100:10.1f}% {vs/vc:8.2f}x")
lh = pd.DataFrame(rows).set_index("series")

# ---- equity multiple: long history vs the 2013-26 ETF estimate ----
rv = pd.read_csv(f"{D}/regime_vol.csv", index_col=0)
eq_short = rv.loc["US_LargeCap", "vol_stress"] / rv.loc["US_LargeCap", "vol_calm"]
eq_long = lh.loc["US_Equity", "vol_multiple"]
print(f"\nEquity stress/calm vol multiple:")
print(f"  2013-26 ETF window (no GFC) : {eq_short:.2f}x")
print(f"  2000-26 incl. 2008 + 2020   : {eq_long:.2f}x")
blended = 0.5 * eq_short + 0.5 * eq_long
print(f"  -> blended estimate for the model: {blended:.2f}x")

# ---- MXN long-run depreciation & volatility ----
mxn = fx["USDMXN"].dropna()
yrs = (mxn.index[-1] - mxn.index[0]).days / 365.25
mxn_depr = (mxn.iloc[-1] / mxn.iloc[0]) ** (1 / yrs) - 1
mxn_vol = fxret["USDMXN"].std() * np.sqrt(12)
print(f"\nUSDMXN  {mxn.index[0].date()}..{mxn.index[-1].date()} ({yrs:.1f}y)")
print(f"  MXN depreciation vs USD: {mxn_depr*100:.2f}%/yr  (LTCMA assumption 2.5%)")
print(f"  USDMXN volatility: {mxn_vol*100:.1f}%/yr")

# ---- crisis snapshot (clean Shiller equity) ----
print("\nWorst equity months in the long window (Shiller US):")
for dt, v in series["US_Equity"].reindex(idx).dropna().nsmallest(5).items():
    print(f"  {dt.date()}  {v*100:+.1f}%   EPU {epu.get(dt, np.nan):.0f}  "
          f"GPR {gpr.get(dt, np.nan):.0f}  ({'stress' if stress.get(dt) else 'calm'})")

lh["eq_multiple_2013_26"] = eq_short
lh["eq_multiple_blended"] = blended
lh["mxn_depreciation_yr"] = mxn_depr
lh["mxn_vol_yr"] = mxn_vol
lh.to_csv(f"{D}/regime_longhistory.csv")
print("\nwrote regime_longhistory.csv")
