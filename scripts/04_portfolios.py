"""Sample-portfolio analytics using the LTCMA outputs."""
import numpy as np
import pandas as pd

import paths as _paths                  # repo-anchored (migration 2026-08-07)
DATA = _paths.DATA_S
summary = pd.read_csv(f"{DATA}/ltcma_summary.csv", index_col=0)
corr = pd.read_csv(f"{DATA}/ltcma_corr.csv", index_col=0)

er = summary["ER_lambda0.5"]
vol = summary["vol"]
cash = summary.loc["US_Cash_TBill", "ER_lambda0.5"]

PORTFOLIOS = {
    "Conservative 30/70": {
        "US_LargeCap": .14, "DM_exUS_Eq": .08, "EM_Eq": .08,
        "US_Treas_Interm": .25, "US_IG_Corp": .15, "Global_Agg_exUS": .10,
        "US_Cash_TBill": .12, "US_HighYield": .04, "EM_USD_Sov": .04},
    "Moderate 60/40": {
        "US_LargeCap": .30, "DM_exUS_Eq": .16, "EM_Eq": .14,
        "US_Treas_Interm": .18, "US_IG_Corp": .10, "Global_Agg_exUS": .06,
        "US_HighYield": .03, "EM_USD_Sov": .03},
    "Growth 90/10": {
        "US_LargeCap": .42, "DM_exUS_Eq": .26, "EM_Eq": .22,
        "US_Treas_Interm": .05, "US_IG_Corp": .03, "EM_USD_Sov": .02},
    "Edge-Tilted (Moderate risk)": {
        "US_LargeCap": .16, "DM_exUS_Eq": .14, "EM_Eq": .16,
        "Mexico_Eq": .07, "Japan_Eq": .07,
        "EM_USD_Sov": .08, "Mexico_Govt_Local": .09, "US_TIPS": .08,
        "US_Treas_Interm": .07, "Gold": .05, "US_Cash_TBill": .03},
}

def port_stats(w: dict):
    a = list(w.keys())
    wt = np.array([w[x] for x in a])
    r = float(wt @ er[a].values)
    v = vol[a].values
    cm = corr.loc[a, a].values
    cov = np.outer(v, v) * cm
    sd = float(np.sqrt(wt @ cov @ wt))
    return r, sd, (r - cash) / sd, wt.sum()

print(f"{'Portfolio':<30}{'ExpRet':>9}{'Vol':>8}{'Sharpe':>8}{'SumW':>7}")
print("-" * 62)
out = []
for name, w in PORTFOLIOS.items():
    r, sd, sh, tot = port_stats(w)
    print(f"{name:<30}{r*100:>8.2f}%{sd*100:>7.2f}%{sh:>8.2f}{tot*100:>6.0f}%")
    out.append({"portfolio": name, "exp_return": r, "vol": sd, "sharpe": sh})

pd.DataFrame(out).to_csv(f"{DATA}/ltcma_portfolios.csv", index=False)
print("\nWrote ltcma_portfolios.csv")
