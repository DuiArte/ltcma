"""Rebuild the risk model: Ledoit-Wolf shrunk covariance + long-history vol blend.
Outputs: data/ltcma_corr_v2.csv, ltcma_vol_v2.csv, ltcma_cov_v2.csv,
         data/longhistory/damodaran_longrun.csv
"""
import os
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

D = os.path.expanduser("~/LTCMA/data")
LH = f"{D}/longhistory"

# ---------- ETF monthly simple returns ----------
px = pd.read_csv(f"{D}/prices_monthly.csv", index_col=0, parse_dates=True)
rets = px.pct_change().iloc[1:]
common = rets.dropna()                       # common complete window, all assets
print(f"Common ETF window: {common.index.min().date()}..{common.index.max().date()} "
      f"({len(common)} months, {common.shape[1]} assets)")

# ---------- Ledoit-Wolf shrinkage ----------
lw = LedoitWolf().fit(common.values)
cov_m = pd.DataFrame(lw.covariance_, index=common.columns, columns=common.columns)
print(f"Ledoit-Wolf shrinkage intensity: {lw.shrinkage_:.3f}")
vol_short = np.sqrt(np.diag(cov_m) * 12)
vol_short = pd.Series(vol_short, index=common.columns)
dinv = np.diag(1 / np.sqrt(np.diag(cov_m)))
corr = pd.DataFrame(dinv @ cov_m.values @ dinv, index=common.columns, columns=common.columns)

# ---------- long-history annualized vol ----------
french = pd.read_csv(f"{LH}/french_monthly.csv", index_col=0, parse_dates=True)
shiller = pd.read_csv(f"{LH}/shiller_monthly.csv", index_col=0, parse_dates=True)
dam = pd.read_csv(f"{LH}/damodaran_annual.csv")

fr90 = french.loc["1990":]
sh90 = shiller.loc["1990":, "US_Eq_ret"].dropna()
long_vol = {
    "US_LargeCap":  sh90.std() * np.sqrt(12),
    "DM_exUS_Eq":   fr90["DM_exUS"].std() * np.sqrt(12),
    "Japan_Eq":     fr90["Japan"].std() * np.sqrt(12),
    "EM_Eq":        fr90["EM"].std() * np.sqrt(12),
    "France_Eq":    fr90["Europe"].std() * np.sqrt(12),
    "UK_Eq":        fr90["Europe"].std() * np.sqrt(12),
}
# Damodaran annual returns -> annual vol (detect % vs decimal).
# NB: only clean matches kept. Damodaran "Real Estate" is appraisal-based
# property (not listed REITs) and his small cap is an extreme bottom decile
# (not Russell 2000) -- both excluded to avoid distorting the blend.
dcol = {"US_Cash_TBill": "3-month T.Bill",
        "US_Treas_Interm": "US T. Bond (10-year)",
        "US_IG_Corp": " Baa Corporate Bond",
        "Gold": "Gold*"}
for asset, col in dcol.items():
    if col in dam.columns:
        s = pd.to_numeric(dam[col], errors="coerce").dropna()
        if s.abs().median() > 1.5:   # stored as percent
            s = s / 100.0
        long_vol[asset] = s.std()
# Long Treasury: scale 10y bond vol by duration ratio (~16/7.5)
if "US_Treas_Interm" in long_vol:
    long_vol["US_Treas_Long"] = long_vol["US_Treas_Interm"] * (16.0 / 7.5)

# ---------- blend: 50/50 short window vs long history ----------
vol_blend = vol_short.copy()
for a, lv in long_vol.items():
    if a in vol_blend.index:
        vol_blend[a] = np.sqrt(0.5 * vol_short[a] ** 2 + 0.5 * lv ** 2)

# Mexico_Govt_Local proxied from EM_Local_Debt
PROXY = {"Mexico_Govt_Local": "EM_Local_Debt"}
for tgt, src in PROXY.items():
    vol_blend[tgt] = vol_blend[src]
    vol_short[tgt] = vol_short[src]
    corr[tgt] = corr[src]; corr.loc[tgt] = corr.loc[src]; corr.loc[tgt, tgt] = 1.0

# ---------- final annualized covariance (LW corr scaled to blended vol) ----------
assets = list(vol_blend.index)
corr = corr.loc[assets, assets]
Dv = np.diag(vol_blend.values)
cov_annual = pd.DataFrame(Dv @ corr.values @ Dv, index=assets, columns=assets)

# PSD check
eig = np.linalg.eigvalsh(cov_annual.values)
print(f"Covariance min eigenvalue: {eig.min():.2e}  (PSD: {eig.min() >= -1e-10})")

corr.to_csv(f"{D}/ltcma_corr_v2.csv")
cov_annual.to_csv(f"{D}/ltcma_cov_v2.csv")
pd.DataFrame({"vol_short_15y": vol_short, "vol_blended": vol_blend}).to_csv(f"{D}/ltcma_vol_v2.csv")

# ---------- Damodaran long-run average returns (geometric) ----------
lr = []
for name, col in [("US Large Cap", "S&P 500 (includes dividends)"),
                   ("US Small Cap", "US Small cap (bottom decile)"),
                   ("3m T-Bill", "3-month T.Bill"),
                   ("10y T-Bond", "US T. Bond (10-year)"),
                   ("Baa Corp Bond", " Baa Corporate Bond"),
                   ("Real Estate", "Real Estate"), ("Gold", "Gold*")]:
    if col in dam.columns:
        s = pd.to_numeric(dam[col], errors="coerce").dropna()
        if s.abs().median() > 1.5:
            s = s / 100.0
        geo = (1 + s).prod() ** (1 / len(s)) - 1
        lr.append({"asset": name, "geo_mean_1928_2025": geo,
                   "annual_vol": s.std(), "n_years": len(s)})
lrdf = pd.DataFrame(lr)
lrdf.to_csv(f"{LH}/damodaran_longrun.csv", index=False)

print("\n=== Damodaran long-run nominal returns (1928-2025) ===")
for _, r in lrdf.iterrows():
    print(f"  {r['asset']:16s} geo {r['geo_mean_1928_2025']*100:6.2f}%   "
          f"vol {r['annual_vol']*100:6.2f}%")

print("\n=== Volatility: 15y window vs long-history blend ===")
cmp = pd.DataFrame({"vol_15y": vol_short, "vol_blended": vol_blend})
cmp = (cmp * 100).round(2)
print(cmp.to_string())
