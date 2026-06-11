"""GPU Monte Carlo simulation engine (VCMM-style) — cupy on the RTX 4060.
Simulates N multi-asset return paths over the 12y horizon from the LTCMA means
and the Ledoit-Wolf shrunk covariance, in log-return space (guarantees no
wealth below zero). Produces return distributions, downside percentiles and
shortfall probabilities for every asset class and the sample portfolios.

Outputs: data/mc_assets.csv, data/mc_portfolios.csv
"""
import os, time
import numpy as np
import pandas as pd
import cupy as cp

from paths import DATA_S as D  # repo-anchored (2026-06-10)
H = 12                # horizon (years)
N = 250_000           # simulated paths
INFL = 0.024          # US inflation benchmark
CASH = 0.033          # cash benchmark
SEED = 20260518

# ---------- inputs ----------
summary = pd.read_csv(f"{D}/ltcma_summary.csv", index_col=0)
cov = pd.read_csv(f"{D}/ltcma_cov_v2.csv", index_col=0)
assets = list(cov.index)
mu = summary.loc[assets, "ER_lambda0.5"].values          # arithmetic annual ER
Sig = cov.values                                          # annual covariance

# ---------- arithmetic -> log-space moments ----------
var = np.diag(Sig)
m_log = np.log(1 + mu) - 0.5 * np.log(1 + var / (1 + mu) ** 2)
S_log = np.log(1 + Sig / np.outer(1 + mu, 1 + mu))
# enforce PSD on the log-covariance
w, V = np.linalg.eigh(S_log)
w = np.clip(w, 1e-12, None)
S_log = (V * w) @ V.T
L = np.linalg.cholesky(S_log)

# ---------- GPU simulation ----------
cp.random.seed(SEED)
t0 = time.time()
m_g = cp.asarray(m_log);  L_g = cp.asarray(L)
Z = cp.random.standard_normal((N, H, len(assets)), dtype=cp.float32)
logret = m_g + Z @ L_g.T.astype(cp.float32)          # annual log returns (N,H,A)
arith = cp.expm1(logret)                              # annual arithmetic returns
gpu_t = time.time() - t0
print(f"GPU sim: {N:,} paths x {H}y x {len(assets)} assets in {gpu_t:.2f}s "
      f"({cp.cuda.runtime.getDeviceProperties(0)['name'].decode()})")

# ---------- per-asset 12y annualized return distribution ----------
asset_term = cp.prod(1 + arith, axis=1)               # terminal wealth (N,A)
asset_ann = asset_term ** (1.0 / H) - 1.0
pcts = [5, 25, 50, 75, 95]
ap = cp.percentile(asset_ann, cp.asarray(pcts, dtype=cp.float32), axis=0)
p_loss = cp.mean(asset_term < 1.0, axis=0)            # P(nominal loss over 12y)
p_infl = cp.mean(asset_ann < INFL, axis=0)            # P(fail to beat inflation)

arows = []
for i, a in enumerate(assets):
    arows.append({"asset": a, "ER_point": mu[i],
                  **{f"p{p}": float(ap[j, i]) for j, p in enumerate(pcts)},
                  "P_loss_12y": float(p_loss[i]),
                  "P_below_infl": float(p_infl[i])})
adf = pd.DataFrame(arows).set_index("asset")
adf.to_csv(f"{D}/mc_assets.csv")

# ---------- portfolios (annually rebalanced) ----------
PORTFOLIOS = {
    "Conservative 30/70": {"US_LargeCap": .14, "DM_exUS_Eq": .08, "EM_Eq": .08,
        "US_Treas_Interm": .25, "US_IG_Corp": .15, "Global_Agg_exUS": .10,
        "US_Cash_TBill": .12, "US_HighYield": .04, "EM_USD_Sov": .04},
    "Moderate 60/40": {"US_LargeCap": .30, "DM_exUS_Eq": .16, "EM_Eq": .14,
        "US_Treas_Interm": .18, "US_IG_Corp": .10, "Global_Agg_exUS": .06,
        "US_HighYield": .03, "EM_USD_Sov": .03},
    "Growth 90/10": {"US_LargeCap": .42, "DM_exUS_Eq": .26, "EM_Eq": .22,
        "US_Treas_Interm": .05, "US_IG_Corp": .03, "EM_USD_Sov": .02},
    "Edge-Tilted (Moderate risk)": {"US_LargeCap": .16, "DM_exUS_Eq": .14,
        "EM_Eq": .16, "Mexico_Eq": .07, "Japan_Eq": .07, "EM_USD_Sov": .08,
        "Mexico_Govt_Local": .09, "US_TIPS": .08, "US_Treas_Interm": .07,
        "Gold": .05, "US_Cash_TBill": .03},
}
prows = []
for name, w in PORTFOLIOS.items():
    wv = cp.zeros(len(assets), dtype=cp.float32)
    for k, v in w.items():
        wv[assets.index(k)] = v
    port_annual = cp.sum(arith * wv, axis=2)          # (N,H)
    term = cp.prod(1 + port_annual, axis=1)           # terminal wealth (N,)
    ann = term ** (1.0 / H) - 1.0
    pc = cp.percentile(ann, cp.asarray(pcts, dtype=cp.float32))
    prows.append({"portfolio": name,
                  **{f"p{p}": float(pc[j]) for j, p in enumerate(pcts)},
                  "mean_ann": float(cp.mean(ann)),
                  "P_loss_12y": float(cp.mean(term < 1.0)),
                  "P_below_infl": float(cp.mean(ann < INFL)),
                  "P_below_cash": float(cp.mean(ann < CASH)),
                  "term_p5_per_100k": float(cp.percentile(term, 5)) * 100_000})
pdf = pd.DataFrame(prows).set_index("portfolio")
pdf.to_csv(f"{D}/mc_portfolios.csv")

# ---------- report ----------
pd.set_option("display.width", 170)
print("\n=== ASSET CLASSES: 12y annualized return distribution ===")
show = (adf[["p5", "p25", "p50", "p75", "p95"]] * 100).round(1)
show["P_loss"] = (adf["P_loss_12y"] * 100).round(1)
show["P<infl"] = (adf["P_below_infl"] * 100).round(1)
print(show.to_string())

print("\n=== PORTFOLIOS: 12y annualized return distribution ===")
ps = (pdf[["p5", "p25", "p50", "p75", "p95", "mean_ann"]] * 100).round(2)
ps["P<infl%"] = (pdf["P_below_infl"] * 100).round(1)
ps["P<cash%"] = (pdf["P_below_cash"] * 100).round(1)
ps["worst5%_$100k"] = pdf["term_p5_per_100k"].round(0)
print(ps.to_string())
print(f"\nWrote mc_assets.csv, mc_portfolios.csv  | seed={SEED}")
