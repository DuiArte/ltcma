"""LTCMA model — building-block expected returns + vol/correlation matrix.
All assumptions sourced inline. Horizon = 12y (midpoint of 10-15y).
Outputs: data/ltcma_returns.csv, ltcma_vol.csv, ltcma_corr.csv, ltcma_summary.csv
"""
import json
import numpy as np
import pandas as pd

import paths as _paths                  # repo-anchored (migration 2026-08-07)
DATA = _paths.DATA_S
H = 12                 # horizon, years
INFL_US = 0.024        # US LT inflation (consensus LTCMA ~2.3-2.5%)
LAMBDAS = [0.0, 0.5, 1.0]   # valuation-reversion dial: none / partial / full

# ============================================================
# US LARGE-CAP VALUATION INPUT — sourced LIVE, never hardcoded.
#
# The CAPE that drives US_LargeCap's valuation reversion comes from the
# repo's own Shiller series (05a downloads ie_data.xls -> 05b parses it to
# data/longhistory/shiller_monthly.csv). It was previously a hardcoded
# 34.7 "as of 12/31/2025" that silently went two quarters stale and read
# LOW even against its own source (2026-08-07 audit, item #1).
#
# Vintage is pinned to the latest calendar QUARTER-END rather than the last
# row: Shiller's final one-to-three months carry an estimated CPI (see the
# "CPI estimated" footnote in ie_data.xls), and a quarter-end anchor matches
# the quarterly cadence of the LTCMA itself. Deterministic and reproducible.
# ============================================================
CAPE_FALLBACK = (34.7, "2025-12-31", "STALE hardcoded fallback (Siblis Research)")

def load_us_cape():
    """(cape, as_of, source) for US large cap, from the free public Shiller series."""
    p = f"{DATA}/longhistory/shiller_monthly.csv"
    try:
        s = pd.read_csv(p, index_col=0, parse_dates=True)["CAPE"].dropna()
        q = s[s.index.month.isin((3, 6, 9, 12))]
        if not len(q):
            raise ValueError("no quarter-end observations in the CAPE column")
        return (round(float(q.iloc[-1]), 2), str(q.index[-1].date()),
                "Shiller ie_data via 05a->05b")
    except Exception as e:
        print(f"!! WARNING: could not read the live Shiller CAPE from {p} ({e}).")
        print(f"!! Falling back to {CAPE_FALLBACK[0]} as of {CAPE_FALLBACK[1]} — the "
              f"equity valuation input is STALE. Run 05a then 05b to refresh it.")
        return CAPE_FALLBACK

CAPE_NOW, CAPE_ASOF, CAPE_SRC = load_us_cape()
print(f"US_LargeCap CAPE = {CAPE_NOW}  as of {CAPE_ASOF}   [{CAPE_SRC}]")

# ============================================================
# EQUITY BUILDING BLOCKS
# DY=dividend yield, BB=net buyback yield, g=real EPS growth,
# cape_now / cape_fair drive valuation reversion.
# Sources: US CAPE = live Shiller series (above); yfinance trailing P/E &
# yields (May 2026); Damodaran 2026 country ERP; trend-growth = IMF/OECD
# consensus.
# cape_fair = judgment anchor (long-run modern fair value) -- documented,
# and deliberately left alone by the 2026-08-07 refresh: only val_now was
# stale, and 26.0 is a conservative anchor vs the ~28.2 30y mean.
# ============================================================
EQUITY = {
    # asset            DY     BB     g      val_now    val_fair  metric
    "US_LargeCap":     (0.012, 0.017, 0.025, CAPE_NOW, 26.0,  "CAPE"),
    "US_SmallCap":     (0.013, 0.005, 0.025, 19.0,   18.0,  "P/E"),
    "Mexico_Eq":       (0.032, 0.000, 0.018, 13.0,   15.0,  "P/E"),
    "Brazil_Eq":       (0.045, 0.000, 0.020, 11.8,   11.5,  "P/E"),
    "China_Eq":        (0.022, 0.005, 0.030, 17.7,   15.0,  "CAPE"),
    "Japan_Eq":        (0.022, 0.010, 0.015, 29.4,   25.0,  "CAPE"),
    "UK_Eq":           (0.038, 0.005, 0.013, 20.2,   16.0,  "CAPE"),
    "France_Eq":       (0.030, 0.005, 0.015, 21.0,   20.0,  "CAPE"),
    "EM_Eq":           (0.028, 0.000, 0.028, 16.0,   16.0,  "CAPE"),
    "DM_exUS_Eq":      (0.032, 0.004, 0.015, 18.0,   19.0,  "CAPE"),
}

def equity_return(DY, BB, g, val_now, val_fair, lam):
    """ER (USD) = DY + BB + g_real + US inflation + lambda*valuation reversion.
    Relative-PPP assumption: foreign inflation is offset by FX depreciation,
    so the nominal anchor in USD is US inflation."""
    reversion = (val_fair / val_now) ** (1.0 / H) - 1.0
    return DY + BB + g + INFL_US + lam * reversion, reversion

# ============================================================
# FIXED INCOME  (single estimate; sourced yields May 2026)
# ER = starting yield + roll +/- normalization - expected credit loss
# Yields/spreads: FRED 5/15/2026.  Credit loss = default x (1-recovery).
# ============================================================
FIXED_INCOME = {
    # asset             ER      note
    "US_Cash_TBill":   (0.033, "avg(3.7% spot, ~3.0% equilibrium cash rate)"),
    "US_Treas_Interm": (0.045, "YTM ~4.5% (7-10y), slight normalization gain"),
    "US_Treas_Long":   (0.048, "YTM ~4.9% (20y+), duration/normalization"),
    "US_TIPS":         (0.045, "10y real yield 2.1% + US inflation 2.4%"),
    "US_IG_Corp":      (0.050, "YTM ~5.3% - ~0.2% loss - tight-spread drag"),
    "US_HighYield":    (0.050, "YTM ~7.5% - ~2.3% credit loss - tight-OAS drag"),
    "EM_USD_Sov":      (0.060, "EMBI YTM ~7.0% - ~0.9% sovereign loss"),
    "EM_Local_Debt":   (0.048, "local yield ~6.3% - ~1.5% EM FX depreciation"),
    "Global_Agg_exUS": (0.038, "BNDX USD-hedged: hedged yield ~3.8%"),
    "Mexico_Govt_Local":(0.063,"Mbono 10y 8.88% - ~2.5% MXN depreciation vs USD"),
}

# ============================================================
# REAL ASSETS
# ============================================================
REAL_ASSETS = {
    "US_REITs":          (0.063, "income ~3.8% + real growth ~2% + inflation"),
    "Global_REITs_exUS": (0.064, "income ~4.2% + growth ~1.5% + inflation"),
    "Commodities":       (0.035, "collateral ~3.3% + ~0% real spot + roll"),
    "Gold":              (0.033, "inflation 2.4% + ~1% long-run real return"),
}

# Mexico_Govt_Local: real series built by 05c_mexico_bond_series.py.
# Proxy (EM_Local_Debt) used only as fallback if the file is missing.
VOL_PROXY = {}   # no proxies needed when pipeline is fully run

# ============================================================
# 1. EXPECTED RETURNS
# ============================================================
rows = []
for a, (DY, BB, g, vn, vf, metric) in EQUITY.items():
    rec = {"asset": a, "class": "Equity", "DY": DY, "BB": BB, "g_real": g,
           "infl": INFL_US, "val_metric": metric, "val_now": vn, "val_fair": vf}
    for lam in LAMBDAS:
        er, rev = equity_return(DY, BB, g, vn, vf, lam)
        rec[f"ER_lambda{lam}"] = er
    rec["val_reversion_annual"] = rev
    rows.append(rec)

for a, (er, note) in FIXED_INCOME.items():
    rows.append({"asset": a, "class": "Fixed Income", "note": note,
                 "ER_lambda0.0": er, "ER_lambda0.5": er, "ER_lambda1.0": er})

for a, (er, note) in REAL_ASSETS.items():
    rows.append({"asset": a, "class": "Real Asset", "note": note,
                 "ER_lambda0.0": er, "ER_lambda0.5": er, "ER_lambda1.0": er})

ret = pd.DataFrame(rows).set_index("asset")
ret.to_csv(f"{DATA}/ltcma_returns.csv")

# ============================================================
# 2. VOLATILITY & CORRELATION  (trailing 15y monthly total returns)
# ============================================================
px = pd.read_csv(f"{DATA}/prices_monthly.csv", index_col=0, parse_dates=True)

# Merge real Mexico Govt Local bond series if available
import os as _os
_mex_path = f"{DATA}/mexico_bond_monthly.csv"
if _os.path.exists(_mex_path):
    _mex = pd.read_csv(_mex_path, index_col=0, parse_dates=True)
    px = px.join(_mex[["Mexico_Govt_Local"]], how="left")
    print(f"Mexico_Govt_Local: loaded real series from {_mex_path}")
else:
    print("WARNING: mexico_bond_monthly.csv not found — run 05c first; "
          "Mexico_Govt_Local vol/corr will be absent from simple model.")

rets = np.log(px / px.shift(1)).dropna(how="all")
window = rets.loc[rets.index >= (rets.index.max() - pd.DateOffset(years=15))]

vol = (window.std() * np.sqrt(12)).rename("annual_vol")
corr = window.corr()

# Fallback proxy only if Mexico_Govt_Local still missing (file not found above)
for tgt, src in VOL_PROXY.items():
    vol[tgt] = vol[src]
    corr[tgt] = corr[src]
    corr.loc[tgt] = corr.loc[src]
    corr.loc[tgt, tgt] = 1.0

vol.to_csv(f"{DATA}/ltcma_vol.csv")
corr.to_csv(f"{DATA}/ltcma_corr.csv")

# ============================================================
# 3. SUMMARY TABLE
# ============================================================
summary = ret[["class", "ER_lambda0.0", "ER_lambda0.5", "ER_lambda1.0"]].copy()
summary["vol"] = vol
summary["sharpe_base"] = (summary["ER_lambda0.5"] - FIXED_INCOME["US_Cash_TBill"][0]) / summary["vol"]
summary["lambda_spread"] = summary["ER_lambda0.0"] - summary["ER_lambda1.0"]
summary.to_csv(f"{DATA}/ltcma_summary.csv")

# ============================================================
# 3b. MODEL VINTAGE METADATA
# The daily refresh re-renders the site every day but NEVER runs 01/02/03,
# so "today" is the signals date, not the model date. index.html used to
# stamp today's date over frozen model output (2026-08-07 audit, item #10).
# This file is what lets 17_build_site.py stamp the two dates separately.
# ============================================================
meta = {
    "model_built": pd.Timestamp.today().strftime("%Y-%m-%d"),
    "horizon_years": H,
    "us_cape_now": CAPE_NOW,
    "us_cape_asof": CAPE_ASOF,
    "us_cape_source": CAPE_SRC,
    "us_cape_fair": EQUITY["US_LargeCap"][4],
    "us_largecap_er_lambda0.5": float(summary.loc["US_LargeCap", "ER_lambda0.5"]),
    "infl_us": INFL_US,
}
with open(f"{DATA}/ltcma_meta.json", "w", encoding="utf-8") as fh:
    json.dump(meta, fh, indent=2)
print(f"Wrote ltcma_meta.json  (model_built={meta['model_built']}, "
      f"CAPE {meta['us_cape_now']} @ {meta['us_cape_asof']})")

pd.set_option("display.width", 160, "display.max_columns", 20)
print("=== EXPECTED RETURNS (USD, 12y) & RISK ===\n")
disp = summary.copy()
for c in ["ER_lambda0.0", "ER_lambda0.5", "ER_lambda1.0", "vol", "lambda_spread"]:
    disp[c] = (disp[c] * 100).round(2)
disp["sharpe_base"] = disp["sharpe_base"].round(2)
disp = disp.rename(columns={"ER_lambda0.0": "ER_noRev", "ER_lambda0.5": "ER_BASE",
                            "ER_lambda1.0": "ER_fullRev", "lambda_spread": "valBet"})
print(disp.to_string())
print("\nValuation-reversion is a return BET where 'valBet' is large.")
print(f"\nWrote: ltcma_returns.csv, ltcma_vol.csv, ltcma_corr.csv, ltcma_summary.csv")
print(f"Vol/corr window: {window.index.min().date()} .. {window.index.max().date()}  ({len(window)} months)")
