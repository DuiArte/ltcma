"""Fetch priced-in and uncertainty signal data.
- FRED: full Treasury curve, VIX, breakeven inflation, credit spreads, EPU
- GPR (geopolitical risk) and TPU (trade policy uncertainty) from source files
Outputs: data/signals_fred.csv, data/signals_gpr.csv (best-effort)
"""
import io, time, os
import pandas as pd
import requests

D = os.path.expanduser("~/LTCMA/data")
HDR = {"User-Agent": "Mozilla/5.0 (research; LTCMA build)"}

FRED = {
    # Treasury curve (priced-in rate path)
    "UST_1M": "DGS1MO", "UST_3M": "DGS3MO", "UST_6M": "DGS6MO",
    "UST_1Y": "DGS1", "UST_2Y": "DGS2", "UST_3Y": "DGS3", "UST_5Y": "DGS5",
    "UST_7Y": "DGS7", "UST_10Y": "DGS10", "UST_20Y": "DGS20", "UST_30Y": "DGS30",
    "FedFunds": "DFF",
    # priced-in inflation
    "Breakeven_10Y": "T10YIE", "Breakeven_5Y": "T5YIE", "Inflation_5y5y": "T5YIFR",
    # priced-in risk
    "VIX": "VIXCLS", "HY_OAS": "BAMLH0A0HYM2", "IG_OAS": "BAMLC0A0CM",
    "EM_spread": "BAMLEMCBPIOAS", "Curve_10Y2Y": "T10Y2Y", "Curve_10Y3M": "T10Y3M",
    # economic policy uncertainty (monthly)
    "EPU_US": "USEPUINDXM", "EPU_Global": "GEPUCURRENT",
    # FX
    "USDMXN": "DEXMXUS",
}

def fetch_fred(name, sid, attempts=4, timeout=60):
    """FRED's fredgraph.csv throttles cloud IPs (GH Actions especially). Retry
    with exponential backoff before giving up."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    last_err = None
    for k in range(attempts):
        try:
            txt = requests.get(url, headers=HDR, timeout=timeout).text
            df = pd.read_csv(io.StringIO(txt))
            df.columns = ["Date", name]
            df["Date"] = pd.to_datetime(df["Date"])
            df[name] = pd.to_numeric(df[name], errors="coerce")
            return df.set_index("Date")[name].dropna()
        except Exception as e:
            last_err = e
            time.sleep(2 ** k)
    raise last_err

out = {}
for name, sid in FRED.items():
    try:
        s = fetch_fred(name, sid)
        out[name] = s
        print(f"  {name:16s} ({sid:14s}) last={s.iloc[-1]:8.2f} @ {s.index[-1].date()}  n={len(s)}")
    except Exception as e:
        print(f"  {name:16s} ({sid}) FAILED: {e}")
    time.sleep(0.25)

sig_new = pd.DataFrame(out)

# Merge with the prior on-disk CSV so a partial/total fetch failure never
# wipes out historical data. New values win where both exist.
csv_path = f"{D}/signals_fred.csv"
if os.path.exists(csv_path):
    try:
        sig_old = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    except Exception as e:
        print(f"  WARN: could not read prior {csv_path}: {e}")
        sig_old = pd.DataFrame()
else:
    sig_old = pd.DataFrame()

if sig_new.empty and sig_old.empty:
    raise RuntimeError("FRED fetch produced no data and no prior CSV exists")

if sig_new.empty:
    print(f"\nWARN: all FRED fetches failed — keeping prior signals_fred.csv intact")
    sig = sig_old
else:
    sig = sig_old.combine_first(sig_new)  # union of dates+cols
    for col in sig_new.columns:           # let fresh data overwrite stale
        sig[col] = sig_new[col].combine_first(sig.get(col))
    sig = sig.sort_index()

sig.to_csv(csv_path)
print(f"\nsignals_fred.csv: {len(sig)} rows, {len(sig.columns)} cols "
      f"(new={sig_new.shape}, prior={sig_old.shape})")

# ---- GPR / TPU (Caldara-Iacoviello) -- best effort, multiple URL fallbacks ----
GPR_URLS = [
    "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
    "https://www.matteoiacoviello.com/gpr_files/gpr_web_latest.xls",
]
for url in GPR_URLS:
    try:
        r = requests.get(url, headers=HDR, timeout=60)
        r.raise_for_status()
        path = f"{D}/signals_gpr_raw.xls"
        with open(path, "wb") as f:
            f.write(r.content)
        xl = pd.ExcelFile(path)
        print(f"\nGPR downloaded from {url}")
        print(f"  sheets: {xl.sheet_names}")
        df0 = xl.parse(xl.sheet_names[0], nrows=3)
        print(f"  columns: {list(df0.columns)[:14]}")
        break
    except Exception as e:
        print(f"\nGPR url failed ({url}): {e}")
