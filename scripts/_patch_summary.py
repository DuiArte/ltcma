"""Patch ltcma_summary.csv — update Mexico_Govt_Local vol from real series."""
import pandas as pd
import os

D = os.path.expanduser("~/LTCMA/data")
RF = 0.033  # US Cash T-Bill ER (from 03_build_model.py)

vol2 = pd.read_csv(f"{D}/ltcma_vol_v2.csv",  index_col=0)
summ = pd.read_csv(f"{D}/ltcma_summary.csv", index_col=0)

asset = "Mexico_Govt_Local"
real_vol = float(vol2.loc[asset, "vol_blended"])
old_vol  = float(summ.loc[asset, "vol"])

summ.loc[asset, "vol"]         = real_vol
summ.loc[asset, "sharpe_base"] = (summ.loc[asset, "ER_lambda0.5"] - RF) / real_vol
summ.to_csv(f"{D}/ltcma_summary.csv")

print(f"{asset} vol : {old_vol*100:.2f}% → {real_vol*100:.2f}%")
print(f"         Sharpe: {summ.loc[asset,'sharpe_base']:.3f}  (ER={summ.loc[asset,'ER_lambda0.5']*100:.1f}%  RF={RF*100:.1f}%)")
print(f"ltcma_summary.csv updated → {D}/ltcma_summary.csv")
