"""Define market regimes (calm / stress) from news-uncertainty indices.
Stress = months in the top tercile of a combined GPR + EPU score.
Computes regime-specific means, vols, correlations and the Markov transition
matrix -- the quantified-news layer feeding the regime-switching simulation.
Outputs: data/regime_vol.csv, regime_corr_calm.csv, regime_corr_stress.csv,
         data/regime_meta.csv
"""
import os
import numpy as np
import pandas as pd

from paths import DATA_S as D  # repo-anchored (2026-06-10)

# ---------- uncertainty indices, monthly ----------
gpr = pd.read_excel(f"{D}/signals_gpr_raw.xls")[["month", "GPR"]]
gpr = gpr.set_index("month")["GPR"]
gpr.index = gpr.index + pd.offsets.MonthEnd(0)

sig = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)
epu = sig["EPU_US"].dropna()
epu.index = epu.index + pd.offsets.MonthEnd(0)
epu = epu.groupby(epu.index).last()

# ---------- ETF monthly returns ----------
px = pd.read_csv(f"{D}/prices_monthly.csv", index_col=0, parse_dates=True)
px.index = px.index + pd.offsets.MonthEnd(0)
rets = px.pct_change().dropna()
assets = list(rets.columns)

# ---------- combined stress score over the common window ----------
idx = rets.index.intersection(gpr.index).intersection(epu.index)
z = lambda s: (s - s.loc[idx].mean()) / s.loc[idx].std()
score = (z(gpr).loc[idx] + z(epu).loc[idx]) / 2.0
thresh = score.quantile(2 / 3)               # top tercile = stress
regime = (score >= thresh).astype(int)       # 1 = stress, 0 = calm
R = rets.loc[idx]
print(f"Window {idx.min().date()}..{idx.max().date()}  ({len(idx)} months)")
print(f"Stress months: {regime.sum()} ({regime.mean()*100:.0f}%)  "
      f"threshold score={thresh:.2f}")

calm_m, stress_m = R[regime == 0], R[regime == 1]

# ---------- regime-specific moments (annualized) ----------
vol = pd.DataFrame({
    "vol_calm": calm_m.std() * np.sqrt(12),
    "vol_stress": stress_m.std() * np.sqrt(12),
    "mean_calm": calm_m.mean() * 12,
    "mean_stress": stress_m.mean() * 12,
})
vol["vol_multiple"] = vol["vol_stress"] / vol["vol_calm"]

corr_calm = calm_m.corr()
corr_stress = stress_m.corr()

# Mexico_Govt_Local proxy = EM_Local_Debt
for df in (corr_calm, corr_stress):
    df["Mexico_Govt_Local"] = df["EM_Local_Debt"]
    df.loc["Mexico_Govt_Local"] = df.loc["EM_Local_Debt"]
    df.loc["Mexico_Govt_Local", "Mexico_Govt_Local"] = 1.0
vol.loc["Mexico_Govt_Local"] = vol.loc["EM_Local_Debt"]

# ---------- Markov transition matrix ----------
r = regime.values
trans = np.zeros((2, 2))
for a, b in zip(r[:-1], r[1:]):
    trans[a, b] += 1
trans = trans / trans.sum(axis=1, keepdims=True)
p_stress_uncond = regime.mean()

# ---------- save ----------
vol.to_csv(f"{D}/regime_vol.csv")
corr_calm.to_csv(f"{D}/regime_corr_calm.csv")
corr_stress.to_csv(f"{D}/regime_corr_stress.csv")
meta = pd.DataFrame({
    "metric": ["p_calm_to_calm", "p_calm_to_stress", "p_stress_to_calm",
               "p_stress_to_stress", "p_stress_uncond", "n_months"],
    "value": [trans[0, 0], trans[0, 1], trans[1, 0], trans[1, 1],
              p_stress_uncond, len(idx)],
})
meta.to_csv(f"{D}/regime_meta.csv", index=False)

# ---------- report ----------
eq = ["US_LargeCap", "EM_Eq", "Mexico_Eq", "DM_exUS_Eq"]
print("\n=== REGIME MOMENTS (annualized) ===")
print(f"{'asset':18s} {'mean_calm':>10s} {'mean_strs':>10s} "
      f"{'vol_calm':>9s} {'vol_strs':>9s} {'volx':>6s}")
for a in eq + ["US_Treas_Long", "US_HighYield", "Gold", "EM_USD_Sov"]:
    v = vol.loc[a]
    print(f"{a:18s} {v['mean_calm']*100:9.1f}% {v['mean_stress']*100:9.1f}% "
          f"{v['vol_calm']*100:8.1f}% {v['vol_stress']*100:8.1f}% {v['vol_multiple']:6.2f}")

avg_corr = lambda c: c.loc[eq, eq].values[np.triu_indices(4, 1)].mean()
print(f"\nAvg equity cross-correlation  calm={avg_corr(corr_calm):.2f}  "
      f"stress={avg_corr(corr_stress):.2f}")
print(f"Transition matrix:  calm->calm {trans[0,0]:.2f}  calm->stress {trans[0,1]:.2f}")
print(f"                  stress->calm {trans[1,0]:.2f}  stress->stress {trans[1,1]:.2f}")
print(f"Stress persistence (avg stress spell): {1/trans[1,0]:.1f} months")
print(f"\nGPR now: {gpr.iloc[-1]:.0f}   EPU now: {epu.iloc[-1]:.0f}   "
      f"current stress score: {score.iloc[-1]:.2f}  "
      f"-> {'STRESS' if score.iloc[-1]>=thresh else 'CALM'} regime")
