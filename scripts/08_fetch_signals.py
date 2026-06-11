"""Fetch priced-in and uncertainty signal data.
- FRED: full Treasury curve, VIX, breakeven inflation, credit spreads, EPU
- GPR (geopolitical risk) and TPU (trade policy uncertainty) from source files
Outputs: data/signals_fred.csv, data/signals_gpr.csv (best-effort)
"""
import io, time, os
import pandas as pd
import requests

from paths import DATA_S as D  # repo-anchored (2026-06-10)
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

# Fail-fast budget. FRED's fredgraph.csv blocks/throttles cloud IPs (GitHub
# Actions especially): connections hang until the timeout, every time. With a
# 60s timeout x4 retries x ~25 series that burned ~1h45m of CI before failing.
# A (connect, read) tuple kills a hung connect in 6s, 2 attempts cap per series,
# and FRED_DEADLINE caps the whole loop — once blocked, we skip the rest and fall
# back to the committed signals_fred.csv (which the host scheduler keeps fresh).
CONNECT_TO, READ_TO, ATTEMPTS = 6, 25, 2
FRED_DEADLINE = 300  # seconds for the entire FRED loop, then skip remaining

def fetch_fred(name, sid, attempts=ATTEMPTS, timeout=(CONNECT_TO, READ_TO)):
    # Shared helper: api.stlouisfed.org with FRED_API_KEY (env or dotfile),
    # keyless fredgraph fallback. The keyless scrape froze signals_fred.csv
    # for 2 weeks (2026-05-27..06-09) when FRED started timing this host out.
    from fred_api import fred_series
    return fred_series(sid, name=name, timeout=timeout, attempts=attempts)

out = {}
_t0 = time.monotonic()
_skipped = 0
for name, sid in FRED.items():
    if time.monotonic() - _t0 > FRED_DEADLINE:
        _skipped += 1
        continue
    try:
        s = fetch_fred(name, sid)
        out[name] = s
        print(f"  {name:16s} ({sid:14s}) last={s.iloc[-1]:8.2f} @ {s.index[-1].date()}  n={len(s)}")
    except Exception as e:
        print(f"  {name:16s} ({sid}) FAILED: {e}")
    time.sleep(0.1)
if _skipped:
    print(f"  ...FRED_DEADLINE ({FRED_DEADLINE}s) hit — skipped {_skipped} series, "
          f"using prior values from disk")

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
# Download to a *temp* path and only replace the real file once pandas confirms
# the bytes are a real Excel workbook. Without this guard, a throttled/redirected
# response (HTML body with 200 OK from a CDN) silently overwrites the on-disk
# XLS with garbage, and the next step (17_build_site.py) crashes immediately
# on pd.read_excel(). Seen on GitHub Actions runners; locally the URL works.
GPR_URLS = [
    "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
    "https://www.matteoiacoviello.com/gpr_files/gpr_web_latest.xls",
]
final_path = f"{D}/signals_gpr_raw.xls"
tmp_path = f"{D}/signals_gpr_raw.xls.tmp"
for url in GPR_URLS:
    try:
        r = requests.get(url, headers=HDR, timeout=(CONNECT_TO, READ_TO))
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            f.write(r.content)
        xl = pd.ExcelFile(tmp_path)          # validate BEFORE replacing
        sheets = xl.sheet_names
        df0 = xl.parse(sheets[0], nrows=3)
        xl.close()                           # Windows: release the handle, else os.replace -> WinError 32
        os.replace(tmp_path, final_path)     # atomic swap on success only
        print(f"\nGPR downloaded from {url}")
        print(f"  sheets: {sheets}")
        print(f"  columns: {list(df0.columns)[:14]}")
        break
    except Exception as e:
        print(f"\nGPR url failed ({url}): {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
else:
    print(f"\nGPR all URLs failed — keeping prior {final_path} intact "
          f"(exists: {os.path.exists(final_path)})")
