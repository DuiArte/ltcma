"""Equity valuation inputs per market — dividend yield, trailing P/E, earnings yield.
Free source: yfinance .info + dividend history fallback."""
import json
import pandas as pd
import yfinance as yf

import paths as _paths                  # repo-anchored (migration 2026-08-07)
DATA = _paths.DATA_S

EQUITY_ETF = {
    "US_LargeCap": "SPY", "US_SmallCap": "IWM", "Mexico_Eq": "EWW",
    "Brazil_Eq": "EWZ", "China_Eq": "MCHI", "Japan_Eq": "EWJ",
    "UK_Eq": "EWU", "France_Eq": "EWQ", "EM_Eq": "EEM", "DM_exUS_Eq": "EFA",
}

rows = []
for name, tk in EQUITY_ETF.items():
    rec = {"asset": name, "ticker": tk}
    try:
        t = yf.Ticker(tk)
        info = t.info or {}
        rec["trailingPE"] = info.get("trailingPE")
        rec["info_yield"] = info.get("yield")  # ETF distribution yield (decimal)
        # robust trailing dividend yield from last 12m distributions
        try:
            divs = t.dividends
            px = t.history(period="2y", auto_adjust=True)["Close"]
            if len(divs) and len(px):
                last12 = divs[divs.index >= (divs.index.max() - pd.Timedelta(days=365))].sum()
                rec["div_yield_ttm"] = round(float(last12 / px.iloc[-1]), 4)
        except Exception as e:
            rec["div_yield_ttm"] = None
    except Exception as e:
        rec["error"] = str(e)
    rows.append(rec)
    print(f"  {name:14s} {tk}  PE={rec.get('trailingPE')}  "
          f"infoYield={rec.get('info_yield')}  divTTM={rec.get('div_yield_ttm')}")

df = pd.DataFrame(rows)
df.to_csv(f"{DATA}/equity_valuations_raw.csv", index=False)
print(f"\nSaved equity_valuations_raw.csv ({len(df)} rows)")
