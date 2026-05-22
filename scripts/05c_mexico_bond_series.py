"""Build a synthetic USD total-return index for Mexico 10-year government bonds
(constant-maturity Mbono) from FRED yield and FX data already in data/.

Method
------
At each month t:

  1. Local (MXN) return — constant-maturity approximation:
       r_MXN_t = y_{t-1} / 12  -  D_mod(y_{t-1}) × (y_t − y_{t-1})
     D_mod is computed analytically for a par bond with semi-annual coupons at
     the prevailing yield level (so it tightens as yields rise, loosens as they
     fall — the correct economic behaviour for Mbonos).

  2. FX return (MXN appreciation vs USD):
       r_FX_t = USDMXN_{t-1} / USDMXN_t − 1
     DEXMXUS is pesos per dollar, so a rising series = peso depreciation = ↓ USD.

  3. USD total return:
       r_USD_t = (1 + r_MXN_t) × (1 + r_FX_t) − 1

Sources
-------
  Mexico_10Y  — FRED IRLTLT01MXM156N (OECD harmonized 10y govt yield, monthly)
  USDMXN      — FRED DEXMXUS (daily bilateral rate), resampled to month-end

Output
------
  data/mexico_bond_monthly.csv — price-level index (rebased 100 at inception,
  2001-09-01 onward), monthly, 1st-of-month convention.

  This file is merged into prices_monthly.csv by 06_rebuild_risk.py, replacing
  the EM_Local_Debt proxy previously used for Mexico_Govt_Local.
"""
import os
import numpy as np
import pandas as pd

D = os.path.expanduser("~/LTCMA/data")


# ── helpers ──────────────────────────────────────────────────────────────────
def mod_dur(y_val: float, n: int = 10, m: int = 2) -> float:
    """Analytical modified duration for an n-year par bond (m coupons per year)."""
    if not np.isfinite(y_val) or y_val <= 0:
        return float(n) * 0.95          # conservative floor (never < 0)
    y_m  = y_val / m                    # yield per period
    T    = n * m                        # total coupon periods
    ts   = np.arange(1, T + 1, dtype=float)
    cf   = np.full(T, y_m)             # fractional coupon (par = 1.0)
    cf[-1] += 1.0                       # principal repayment
    pv   = cf / (1.0 + y_m) ** ts
    mac  = np.dot(ts, pv) / pv.sum()   # Macaulay duration in periods
    return (mac / m) / (1.0 + y_m)     # convert to years, then modify


# ── load raw data ─────────────────────────────────────────────────────────────
macro = pd.read_csv(f"{D}/macro.csv",        index_col=0, parse_dates=True)
sig   = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)

# Mexico 10Y yield (OECD harmonized, monthly, percent → decimal)
# FRED dates are 1st-of-month; fill sparse early observations and any gaps.
yield_raw = macro["Mexico_10Y"].dropna() / 100.0
full_ms   = pd.date_range(yield_raw.index.min(), yield_raw.index.max(), freq="MS")
yield_m   = yield_raw.reindex(full_ms).ffill()   # fills March 2026 gap, etc.

# End-of-month USDMXN → 1st-of-month convention (to match prices_monthly.csv)
usdmxn_d  = sig["USDMXN"].dropna()
usdmxn_eom = usdmxn_d.resample("ME").last()
usdmxn_m  = usdmxn_eom.copy()
usdmxn_m.index = usdmxn_eom.index.to_period("M").to_timestamp()   # EOM → MS


# ── align on common 1st-of-month index ───────────────────────────────────────
idx = yield_m.index.intersection(usdmxn_m.index).sort_values()
y   = yield_m.reindex(idx)
fx  = usdmxn_m.reindex(idx)

assert y.isna().sum() == 0, "Unexpected NaN in yield_m after ffill"


# ── monthly return construction ───────────────────────────────────────────────
y_prev = y.shift(1)                                 # yield at start of month
dy     = y - y.shift(1)                             # change during month
d_mod  = y_prev.apply(lambda v: mod_dur(v) if pd.notna(v) else np.nan)

# MXN total return: income (carry) + price change (duration × yield move)
r_mxn = y_prev / 12.0 - d_mod * dy

# FX: peso appreciates when USDMXN (pesos/dollar) falls
r_fx  = fx.shift(1) / fx - 1

# USD total return
r_usd = (1.0 + r_mxn) * (1.0 + r_fx) - 1.0
r_usd = r_usd.dropna()
r_usd.name = "Mexico_Govt_Local"


# ── price-level index (rebased to 100 at inception) ──────────────────────────
px_idx = (1.0 + r_usd).cumprod() * 100.0
px_idx.name = "Mexico_Govt_Local"


# ── diagnostics ──────────────────────────────────────────────────────────────
n_obs   = len(r_usd)
ann_ret = (1.0 + r_usd).prod() ** (12.0 / n_obs) - 1.0
ann_vol = r_usd.std() * np.sqrt(12)
max_dd  = float((px_idx / px_idx.cummax() - 1.0).min())
avg_dur = float(d_mod.dropna().mean())

print("=" * 60)
print("Mexico Govt Local — synthetic USD total-return index")
print("=" * 60)
print(f"  Source yields : FRED IRLTLT01MXM156N (Mexico 10Y OECD)")
print(f"  Source FX     : FRED DEXMXUS (daily USDMXN, EOM resampled)")
print(f"  Period        : {r_usd.index.min().date()} .. {r_usd.index.max().date()}")
print(f"  N months      : {n_obs}")
print(f"  Ann return    : {ann_ret*100:+.2f}%   (LTCMA target: +6.3%)")
print(f"  Ann vol       : {ann_vol*100:.2f}%")
print(f"  Max drawdown  : {max_dd*100:.1f}%")
print(f"  Avg mod dur   : {avg_dur:.2f}y   (range {d_mod.dropna().min():.2f}–{d_mod.dropna().max():.2f}y)")

# Duration sample
print("\n  Modified duration at selected yields:")
for y_test in [0.05, 0.07, 0.09, 0.11, 0.14]:
    print(f"    y={y_test*100:.0f}%  →  D_mod={mod_dur(y_test):.2f}y")

# Comparison with EM_Local_Debt proxy
try:
    px_etf = pd.read_csv(f"{D}/prices_monthly.csv", index_col=0, parse_dates=True)
    if "EM_Local_Debt" in px_etf.columns:
        emlc_r  = px_etf["EM_Local_Debt"].pct_change().dropna()
        common  = r_usd.index.intersection(emlc_r.index)
        if len(common) >= 24:
            corr_v  = float(r_usd.reindex(common).corr(emlc_r.reindex(common)))
            emlc_v  = emlc_r.reindex(common).std() * np.sqrt(12)
            emlc_a  = (1.0 + emlc_r.reindex(common)).prod() ** (12.0 / len(common)) - 1.0
            mex_a2  = (1.0 + r_usd.reindex(common)).prod() ** (12.0 / len(common)) - 1.0
            mex_v2  = r_usd.reindex(common).std() * np.sqrt(12)
            print(f"\nVs EM_Local_Debt proxy ({len(common)} common months "
                  f"{common.min().date()}–{common.max().date()}):")
            print(f"  Mexico_Govt_Local  ann_ret={mex_a2*100:.2f}%  "
                  f"ann_vol={mex_v2*100:.2f}%")
            print(f"  EM_Local_Debt      ann_ret={emlc_a*100:.2f}%  "
                  f"ann_vol={emlc_v*100:.2f}%")
            print(f"  Correlation        : {corr_v:.3f}  "
                  f"({'high — similar, proxy was reasonable' if corr_v > 0.7 else 'moderate — real series differs meaningfully'})")
except FileNotFoundError:
    pass


# ── save ──────────────────────────────────────────────────────────────────────
out = px_idx.to_frame()
out.to_csv(f"{D}/mexico_bond_monthly.csv")
print(f"\nSaved → {D}/mexico_bond_monthly.csv  ({n_obs} rows)")
print("Next step: re-run 06_rebuild_risk.py  (proxy removed, real series loaded)")
