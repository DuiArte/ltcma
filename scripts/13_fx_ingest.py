"""Ingest of FxPro M5 data -> monthly returns.
Tries cudf (GPU) for speed, falls back to pandas per file if the GPU is
unavailable. Aggregates each instrument to month-end close + monthly returns.
Output: data/fx_monthly.csv  (monthly close levels + *_ret return columns)
"""
import os, time
import pandas as pd

import paths as _paths
SRC = _paths.cuser("Downloads", "fxpro_forex_m5")
OUT = _paths.DATA_S

# instruments most useful to the LTCMA risk / regime / currency layers
WANT = ["#USSPX500", "#USNDAQ100", "#US30", "#US2000",
        "USDMXN", "USDJPY", "EURUSD", "GBPUSD", "USDCAD", "USDCHF",
        "USDCNH", "USDNOK", "USDSEK", "GOLD", "SILVER"]


def month_end_close_cudf(path):
    import cudf
    g = cudf.read_csv(path, sep="\t", usecols=["Time", "Close"])
    g["Time"] = cudf.to_datetime(g["Time"], format="%Y.%m.%d %H:%M")
    g["ym"] = g["Time"].dt.year * 100 + g["Time"].dt.month
    g = g.sort_values("Time")
    m = g.groupby("ym").agg({"Close": "last", "Time": "last"}).reset_index()
    return m.to_pandas()


def month_end_close_pandas(path):
    df = pd.read_csv(path, sep="\t", usecols=["Time", "Close"])
    df["Time"] = pd.to_datetime(df["Time"], format="%Y.%m.%d %H:%M")
    df = df.sort_values("Time")
    df["ym"] = df["Time"].dt.year * 100 + df["Time"].dt.month
    return df.groupby("ym", as_index=False).agg({"Close": "last", "Time": "last"})


monthly, engine = {}, "cudf"
t0 = time.time()
for inst in WANT:
    path = f"{SRC}/FxPro_M5_{inst}.csv"
    if not os.path.exists(path):
        print(f"  MISSING {inst}")
        continue
    try:
        pdf = month_end_close_cudf(path) if engine == "cudf" else None
    except Exception as e:
        print(f"  (cudf unavailable: {str(e)[:50]} -- using pandas)")
        engine = "pandas"
        pdf = None
    if pdf is None:
        pdf = month_end_close_pandas(path)
    pdf["Date"] = pd.to_datetime(pdf["Time"]).dt.to_period("M").dt.to_timestamp("M")
    s = pdf.set_index("Date")["Close"].sort_index()
    name = inst.lstrip("#")
    monthly[name] = s
    print(f"  {name:12s} {len(s):4d} months  "
          f"{s.index.min().date()}..{s.index.max().date()}  last={s.iloc[-1]:.4f}")

elapsed = time.time() - t0
lev = pd.DataFrame(monthly)
ret = lev.pct_change()
ret.columns = [c + "_ret" for c in ret.columns]
out = pd.concat([lev, ret], axis=1)
out.index.name = "Date"
out.to_csv(f"{OUT}/fx_monthly.csv")
print(f"\n{engine} ingest of {len(monthly)} instruments in {elapsed:.1f}s")
print(f"wrote fx_monthly.csv  ({len(lev)} months, {len(monthly)} instruments)")
