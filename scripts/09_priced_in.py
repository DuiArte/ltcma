"""Priced-in indicator dashboard.
Extracts what the market currently expects -- rate path, inflation, risk --
and contrasts it with the LTCMA assumptions. Gaps = explicit active bets.
Output: data/priced_in.csv
"""
import os
import numpy as np
import pandas as pd

D = os.path.expanduser("~/LTCMA/data")
sig = pd.read_csv(f"{D}/signals_fred.csv", index_col=0, parse_dates=True)
last = sig.ffill().iloc[-1]

# ---------- 1. PRICED-IN POLICY-RATE PATH (Treasury forward rates) ----------
# par yields treated as zero rates (indicator-grade approximation)
# Tolerate missing tenors (same fix as 17_build_site): a FRED outage that
# deadline-skips a series must degrade the curve, not crash the whole page.
TEN_ALL = {"UST_3M": .25, "UST_6M": .5, "UST_1Y": 1, "UST_2Y": 2, "UST_3Y": 3,
           "UST_5Y": 5, "UST_7Y": 7, "UST_10Y": 10}
TEN = {k: t for k, t in TEN_ALL.items()
       if k in last.index and pd.notna(last[k])}
_missing = [k for k in TEN_ALL if k not in TEN]
if _missing:
    print(f"  (warn: missing UST tenors {_missing} — building curve from {len(TEN)})")
if len(TEN) < 4 or "UST_1Y" not in TEN:
    raise SystemExit("priced_in: too few UST tenors in signals_fred.csv to build the path")
y = {t: last[k] / 100 for k, t in TEN.items()}
funds = last["FedFunds"] / 100

fwd = []
ts = sorted(y)
for t1, t2 in zip(ts[:-1], ts[1:]):
    f = ((1 + y[t2]) ** t2 / (1 + y[t1]) ** t1) ** (1 / (t2 - t1)) - 1
    fwd.append((t1, t2, f))

print("=== PRICED-IN POLICY-RATE PATH ===")
print(f"Current fed funds (effective): {funds*100:.2f}%")
print(f"Spot 1Y Treasury: {y[1]*100:.2f}%  ->  avg short rate priced over next 12m "
      f"= {y[1]*100:.2f}% ({(y[1]-funds)*100:+.2f}% vs funds)")
for t1, t2, f in fwd:
    print(f"  fwd short rate {t1:>4}-{t2:<4}y: {f*100:5.2f}%")
near = fwd[2][2]  # 1y-2y forward
verdict = ("NO cuts priced -- market sees the Fed at/near done; mild hike bias"
           if y[1] >= funds - 0.0015 else "cuts priced in")
print(f"READ: {verdict}")

# ---------- 2. PRICED-IN INFLATION ----------
print("\n=== PRICED-IN INFLATION ===")
be10, be5, fwd5y5y = last["Breakeven_10Y"], last["Breakeven_5Y"], last["Inflation_5y5y"]
print(f"10y breakeven: {be10:.2f}%   5y breakeven: {be5:.2f}%   "
      f"5y5y forward: {fwd5y5y:.2f}%")
print(f"LTCMA inflation assumption: 2.40%  ->  gap vs 10y breakeven: {2.40-be10:+.2f}%")

# ---------- 3. PRICED-IN RISK (percentile vs own history) ----------
def pct_rank(series, val):
    s = series.dropna()
    return float((s < val).mean() * 100)

print("\n=== PRICED-IN RISK ===")
vix_p = pct_rank(sig["VIX"], last["VIX"])
hy_p = pct_rank(sig["HY_OAS"], last["HY_OAS"])
em_p = pct_rank(sig["EM_spread"], last["EM_spread"])
print(f"VIX {last['VIX']:.1f}  ({vix_p:.0f}th pctile of history) -> "
      f"{'calm' if vix_p<50 else 'stressed'}")
print(f"HY OAS {last['HY_OAS']:.2f}%  ({hy_p:.0f}th pctile) -> "
      f"{'spreads TIGHT, credit priced for perfection' if hy_p<25 else 'normal'}")
print(f"EM spread {last['EM_spread']:.2f}%  ({em_p:.0f}th pctile)")
print(f"Yield curve 10Y-3M: {last['Curve_10Y3M']:+.2f}%  -> "
      f"{'no recession signal' if last['Curve_10Y3M']>0 else 'INVERTED - recession signal'}")
print(f"EPU (policy uncertainty): {last['EPU_US']:.0f}  (baseline ~100) -> "
      f"{'ELEVATED' if last['EPU_US']>150 else 'normal'}")

# ---------- 4. DASHBOARD TABLE: priced-in vs LTCMA ----------
rows = [
    ("Policy-rate path", f"~{y[1]*100:.1f}% avg next 12m; 1-2y fwd {near*100:.1f}%",
     "Cash ER 3.3% (assumes drift to ~3.0-3.3% neutral)",
     "Market prices NO cuts; if right, near-term cash yields above the LTCMA path"),
    ("Long-run inflation", f"10y breakeven {be10:.2f}%, 5y5y {fwd5y5y:.2f}%",
     "2.40%", "Aligned -- LTCMA sits mid-range of what's priced"),
    ("US credit risk", f"HY OAS {last['HY_OAS']:.2f}% ({hy_p:.0f}th pctile, very tight)",
     "US HY ER 5.0% (tight-spread drag already applied)",
     "Market prices near-zero default stress; LTCMA already cautious -- agreement"),
    ("Equity volatility", f"VIX {last['VIX']:.1f} ({vix_p:.0f}th pctile)",
     "Equity vols 13-33%", "Market calm; no near-term stress priced"),
    ("Recession", f"Curve 10Y-3M {last['Curve_10Y3M']:+.2f}% (positive)",
     "n/a", "No recession priced in"),
    ("Policy uncertainty", f"EPU {last['EPU_US']:.0f} (elevated)",
     "n/a", "High policy noise but low market vol -- complacency divergence"),
]
dash = pd.DataFrame(rows, columns=["signal", "market_priced_in",
                                   "ltcma_assumption", "read"])
dash.to_csv(f"{D}/priced_in.csv", index=False)
print("\n=== PRICED-IN vs LTCMA (saved priced_in.csv) ===")
for _, r in dash.iterrows():
    print(f"\n* {r['signal']}")
    print(f"    market : {r['market_priced_in']}")
    print(f"    ltcma  : {r['ltcma_assumption']}")
    print(f"    read   : {r['read']}")
