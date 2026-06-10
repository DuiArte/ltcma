"""LTCMA data collection — free sources only (yfinance + FRED CSV endpoint)."""
import io, time, sys
import pandas as pd
import requests
import yfinance as yf

DATA = r"C:\Users\carlo\LTCMA\data"

# --- Asset-class universe: ETF proxies (USD total-return via auto_adjust) ---
EQUITY = {
    "US_LargeCap": "SPY", "US_SmallCap": "IWM", "Mexico_Eq": "EWW",
    "Brazil_Eq": "EWZ", "China_Eq": "MCHI", "Japan_Eq": "EWJ",
    "UK_Eq": "EWU", "France_Eq": "EWQ", "EM_Eq": "EEM", "DM_exUS_Eq": "EFA",
}
FIXED_INCOME = {
    "US_Cash_TBill": "BIL", "US_Treas_Interm": "IEF", "US_Treas_Long": "TLT",
    "US_TIPS": "TIP", "US_IG_Corp": "LQD", "US_HighYield": "HYG",
    "EM_USD_Sov": "EMB", "EM_Local_Debt": "EMLC", "Global_Agg_exUS": "BNDX",
}
REAL_ASSETS = {
    "US_REITs": "VNQ", "Global_REITs_exUS": "VNQI",
    "Commodities": "DBC", "Gold": "GLD",
}
UNIVERSE = {**EQUITY, **FIXED_INCOME, **REAL_ASSETS}

# --- FRED series (CSV endpoint, no API key) ---
FRED = {
    "US_10Y": "DGS10", "US_2Y": "DGS2", "US_3M": "DGS3MO",
    "US_TIPS_10Y_real": "DFII10", "US_FedFunds": "DFF", "US_CPI": "CPIAUCSL",
    "US_BAA_yield": "BAA", "US_AAA_yield": "AAA",
    "US_HY_OAS": "BAMLH0A0HYM2", "US_IG_OAS": "BAMLC0A0CM",
    "EM_USD_spread": "BAMLEMCBPIOAS",
    "US_RealGDP": "GDPC1",
    "Mexico_10Y": "IRLTLT01MXM156N", "Japan_10Y": "IRLTLT01JPM156N",
    "UK_10Y": "IRLTLT01GBM156N", "France_10Y": "IRLTLT01FRM156N",
    "Mexico_CPI": "MEXCPIALLMINMEI", "Mexico_PolicyRate": "INTDSRMXM193N",
    "USDMXN": "DEXMXUS", "USDJPY": "DEXJPUS", "USDBRL": "DEXBZUS",
    "USDCNY": "DEXCHUS", "GBPUSD": "DEXUSUK", "EURUSD": "DEXUSEU",
}

def fetch_prices():
    tickers = list(UNIVERSE.values())
    print(f"Downloading {len(tickers)} tickers from Yahoo Finance...")
    raw = yf.download(tickers, period="max", interval="1mo",
                      auto_adjust=True, progress=False)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    close = close.rename(columns={v: k for k, v in UNIVERSE.items()})
    close = close[list(UNIVERSE.keys())]
    close.index.name = "Date"
    close.to_csv(f"{DATA}/prices_monthly.csv")
    print(f"  prices_monthly.csv  rows={len(close)}  span={close.index.min().date()}..{close.index.max().date()}")
    for col in close.columns:
        s = close[col].dropna()
        print(f"    {col:22s} start={s.index.min().date() if len(s) else 'NA':>12}  n={len(s)}")
    return close

def fetch_fred():
    out = {}
    for name, sid in FRED.items():
        try:
            from fred_api import fred_series   # API w/ key -> fredgraph fallback
            out[name] = fred_series(sid, name=name, timeout=(6, 30))
            last = out[name].dropna()
            print(f"  FRED {name:22s} ({sid:18s}) last={last.iloc[-1]:.3f} @ {last.index[-1].date()}")
        except Exception as e:
            print(f"  FRED {name:22s} ({sid}) FAILED: {e}")
        time.sleep(0.3)
    macro = pd.DataFrame(out)
    macro.to_csv(f"{DATA}/macro.csv")
    print(f"  macro.csv  rows={len(macro)}  cols={len(macro.columns)}")
    return macro

if __name__ == "__main__":
    print("=== PRICES ===")
    fetch_prices()
    print("\n=== MACRO (FRED) ===")
    fetch_fred()
    print("\nDone.")
