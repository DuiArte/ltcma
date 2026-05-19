"""Regime-switching, fat-tailed GPU Monte Carlo engine.
- Monthly steps over the 12y horizon, 100k paths, cupy on the RTX 4060.
- Two regimes (calm/stress) with a Markov transition matrix calibrated from the
  GPR+EPU news-uncertainty indices; the simulation STARTS in the stress regime
  (current GPR/EPU reading).
- Multivariate Student-t innovations (nu=6) for fat tails.
- Stress regime amplifies volatility and correlation; means held at the LTCMA
  values in both regimes (the 2013-26 sample does not reliably identify a mean
  shift -- imposing one would overfit).
- Plus a deterministic geopolitical-stress scenario.
Outputs: data/mc_regime_assets.csv, data/mc_regime_portfolios.csv,
         data/geopolitical_scenario.csv
"""
import os, time
import numpy as np
import pandas as pd
import cupy as cp

D = os.path.expanduser("~/LTCMA/data")
H, N, NU = 144, 100_000, 6.0          # months, paths, t degrees of freedom
INFL, CASH = 0.024, 0.033
SEED = 20260518

summary = pd.read_csv(f"{D}/ltcma_summary.csv", index_col=0)
cov_v2 = pd.read_csv(f"{D}/ltcma_cov_v2.csv", index_col=0)
rvol = pd.read_csv(f"{D}/regime_vol.csv", index_col=0)
cc = pd.read_csv(f"{D}/regime_corr_calm.csv", index_col=0)
cs = pd.read_csv(f"{D}/regime_corr_stress.csv", index_col=0)
meta = pd.read_csv(f"{D}/regime_meta.csv").set_index("metric")["value"]

assets = list(cov_v2.index)
mu = summary.loc[assets, "ER_lambda0.5"].values            # arithmetic annual ER
vol_target = np.sqrt(np.diag(cov_v2.values))               # LTCMA blended vol
p_stress = meta["p_stress_uncond"]
p_calm = 1 - p_stress

# ---- split LTCMA vol into regime vols preserving the empirical stress ratio ----
m = (rvol.loc[assets, "vol_stress"] / rvol.loc[assets, "vol_calm"]).values
sig_calm = vol_target / np.sqrt(p_calm + p_stress * m**2)
sig_stress = m * sig_calm

# ---- regime annual covariances, then -> monthly log-space ----
def logspace(mu_a, sig_a, corr):
    cov_a = np.outer(sig_a, sig_a) * corr
    S = np.log(1 + cov_a / np.outer(1 + mu_a, 1 + mu_a))
    mlog = np.log(1 + mu_a) - 0.5 * np.diag(S)
    w, V = np.linalg.eigh(S); w = np.clip(w, 1e-12, None)
    S = (V * w) @ V.T
    return mlog / 12.0, S / 12.0                           # monthly

mlog_c, S_c = logspace(mu, sig_calm, cc.loc[assets, assets].values)
mlog_s, S_s = logspace(mu, sig_stress, cs.loc[assets, assets].values)
# Student-t: scale cov so the t-distribution has the target covariance
L_c = cp.asarray(np.linalg.cholesky(S_c * (NU - 2) / NU), dtype=cp.float32)
L_s = cp.asarray(np.linalg.cholesky(S_s * (NU - 2) / NU), dtype=cp.float32)
mc_g, ms_g = cp.asarray(mlog_c, cp.float32), cp.asarray(mlog_s, cp.float32)

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
W = cp.zeros((len(PORTFOLIOS), len(assets)), dtype=cp.float32)
for i, w in enumerate(PORTFOLIOS.values()):
    for k, v in w.items():
        W[i, assets.index(k)] = v

# ---- simulation: memory-light monthly loop, keeps only running wealth ----
cp.random.seed(SEED)
t0 = time.time()
trans = cp.asarray([[meta["p_calm_to_calm"], meta["p_calm_to_stress"]],
                    [meta["p_stress_to_calm"], meta["p_stress_to_stress"]]],
                   dtype=cp.float32)
regime = cp.ones(N, dtype=cp.int32)                # START in stress (current)
asset_logw = cp.zeros((N, len(assets)), dtype=cp.float32)
port_w = cp.ones((N, len(PORTFOLIOS)), dtype=cp.float32)
stress_months = cp.zeros(N, dtype=cp.float32)

for _ in range(H):
    u = cp.random.random(N, dtype=cp.float32)
    p_switch = cp.where(regime == 0, trans[0, 1], trans[1, 1])
    regime = cp.where(regime == 0, (u < trans[0, 1]).astype(cp.int32),
                      (u < trans[1, 1]).astype(cp.int32))
    stress_months += regime
    Z = cp.random.standard_normal((N, len(assets)), dtype=cp.float32)
    g = cp.random.chisquare(NU, size=(N, 1)).astype(cp.float32)
    tscale = cp.sqrt(NU / g)
    r_c = mc_g + (Z @ L_c.T) * tscale
    r_s = ms_g + (Z @ L_s.T) * tscale
    logret = cp.where((regime == 1)[:, None], r_s, r_c)     # (N,assets)
    asset_logw += logret
    arith = cp.expm1(logret)
    port_ret = arith @ W.T                                  # (N,nport)
    port_w *= (1 + port_ret)

gpu_t = time.time() - t0
print(f"Regime MC: {N:,} paths x {H} months x {len(assets)} assets, "
      f"Student-t(nu={NU:.0f}) in {gpu_t:.2f}s")
print(f"Avg fraction of horizon in stress regime: "
      f"{float(stress_months.mean())/H*100:.0f}%")

# ---- asset distributions ----
pcts = [5, 25, 50, 75, 95]
asset_ann = cp.exp(asset_logw / 12.0) - 1.0
ap = cp.percentile(asset_ann, cp.asarray(pcts, cp.float32), axis=0)
aloss = cp.mean(asset_logw < 0, axis=0)
arows = []
for i, a in enumerate(assets):
    arows.append({"asset": a, **{f"p{p}": float(ap[j, i]) for j, p in enumerate(pcts)},
                  "P_loss_12y": float(aloss[i])})
pd.DataFrame(arows).set_index("asset").to_csv(f"{D}/mc_regime_assets.csv")

# ---- portfolio distributions ----
port_ann = port_w ** (1.0 / 12.0) - 1.0
prows = []
for i, name in enumerate(PORTFOLIOS):
    col = port_ann[:, i]
    pc = cp.percentile(col, cp.asarray(pcts, cp.float32))
    prows.append({"portfolio": name,
                  **{f"p{p}": float(pc[j]) for j, p in enumerate(pcts)},
                  "mean_ann": float(cp.mean(col)),
                  "P_loss_12y": float(cp.mean(port_w[:, i] < 1.0)),
                  "P_below_infl": float(cp.mean(col < INFL)),
                  "P_below_cash": float(cp.mean(col < CASH)),
                  "cvar5_ann": float(cp.mean(col[col <= cp.percentile(col, 5)]))})
pd.DataFrame(prows).set_index("portfolio").to_csv(f"{D}/mc_regime_portfolios.csv")

# ---- deterministic geopolitical-stress scenario (1-year shock) ----
# calibrated from 2008/2020-type severe geopolitical/financial shocks
SHOCK = {"US_LargeCap": -.28, "US_SmallCap": -.34, "Mexico_Eq": -.38,
    "Brazil_Eq": -.42, "China_Eq": -.30, "Japan_Eq": -.30, "UK_Eq": -.28,
    "France_Eq": -.30, "EM_Eq": -.34, "DM_exUS_Eq": -.30, "US_Cash_TBill": .02,
    "US_Treas_Interm": .06, "US_Treas_Long": .12, "US_TIPS": .04,
    "US_IG_Corp": -.04, "US_HighYield": -.14, "EM_USD_Sov": -.16,
    "EM_Local_Debt": -.20, "Mexico_Govt_Local": -.18, "Global_Agg_exUS": .03,
    "US_REITs": -.30, "Global_REITs_exUS": -.30, "Commodities": -.10, "Gold": .15}
shock = np.array([SHOCK[a] for a in assets])
geo = [{"portfolio": n, "shock_1y_return": float(sum(w.get(a, 0) * SHOCK[a]
        for a in assets))} for n, w in PORTFOLIOS.items()]
pd.DataFrame(geo).to_csv(f"{D}/geopolitical_scenario.csv", index=False)

pd.set_option("display.width", 170)
print("\n=== REGIME-SWITCHING MC: portfolios, 12y annualized ===")
pp = pd.DataFrame(prows).set_index("portfolio")
show = (pp[["p5", "p25", "p50", "p75", "p95", "mean_ann", "cvar5_ann"]] * 100).round(2)
show["P_loss%"] = (pp["P_loss_12y"] * 100).round(1)
show["P<infl%"] = (pp["P_below_infl"] * 100).round(1)
print(show.to_string())
print("\n=== GEOPOLITICAL STRESS SCENARIO (1-year shock) ===")
for g in geo:
    print(f"  {g['portfolio']:30s} {g['shock_1y_return']*100:+6.1f}%")
print("\nWrote mc_regime_assets.csv, mc_regime_portfolios.csv, geopolitical_scenario.csv")
