"""Shared FRED access for all LTCMA scripts.

API endpoint with key (env FRED_API_KEY -> ~/.fred_api_key ->
/mnt/c/Users/carlo/.fred_api_key) -> keyless fredgraph.csv fallback.

Why: the keyless fredgraph.csv scrape started timing out from this host around
2026-05-27 (and was always throttled/blocked from GH Actions cloud IPs). That
single failure mode silently froze data/signals_fred.csv for two weeks, starved
09_priced_in.py of UST tenors (KeyError crash every run) and killed the regime
tracker's EnergyVol facet. api.stlouisfed.org works from both environments —
GH Actions gets the key via the FRED_API_KEY repo secret.

SECURITY: this repo is PUBLIC. Never hard-code the key here or in any script;
read it at runtime from the env var or the local dotfile only.
"""
import io
import os
import time

import pandas as pd
import requests

_API = "https://api.stlouisfed.org/fred/series/observations"
_KEY_PATHS = (os.path.expanduser("~/.fred_api_key"),
              "/mnt/c/Users/carlo/.fred_api_key")


def fred_key():
    k = os.environ.get("FRED_API_KEY")
    if k:
        return k.strip()
    for p in _KEY_PATHS:
        try:
            if os.path.exists(p):
                return open(p).read().strip()
        except OSError:
            continue
    return None


def fred_series(sid, name=None, timeout=(6, 25), attempts=2):
    """Return a FRED series as a date-indexed numeric pd.Series.

    Tries the API (if a key is available), then falls back to the legacy
    keyless fredgraph.csv scrape. Raises the last error if both fail.
    """
    name = name or sid
    key = fred_key()
    last_err = None
    if key:
        for k in range(attempts):
            try:
                r = requests.get(_API, params={"series_id": sid, "api_key": key,
                                               "file_type": "json"},
                                 timeout=timeout)
                r.raise_for_status()
                obs = r.json()["observations"]
                s = pd.Series({o["date"]: o["value"] for o in obs}, name=name)
                s.index = pd.to_datetime(s.index)
                return pd.to_numeric(s, errors="coerce").dropna()
            except Exception as e:
                last_err = e
                if k + 1 < attempts:
                    time.sleep(2 ** k)
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        txt = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (research; LTCMA)"},
                           timeout=timeout).text
        df = pd.read_csv(io.StringIO(txt))
        df.columns = ["Date", name]
        df["Date"] = pd.to_datetime(df["Date"])
        return pd.to_numeric(df.set_index("Date")[name], errors="coerce").dropna()
    except Exception as e:
        raise last_err or e
