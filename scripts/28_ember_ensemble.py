"""LTCMA — Step 28: EMBER 4-sleeve ensemble live paper-track (data refresh).

Maintains an accumulating, daily mark-to-market equity curve for the proposed
4-sleeve EMBER ensemble (Finding #38) versus a Static 50/30/20 reference basket,
starting on the paper-track inception date (first host run, 2026-06-18). The
curve is computed from yfinance daily closes on the constituent ETFs, weighted
per sleeve composition, with a MONTHLY rebalance and DAILY mark-to-market.

This is the DATA step only — it accumulates state in data/ember_papertrack.json
(and a transparency CSV). The strategies page (23_strategies.py) renders the
chart from that state. Kept ticker-free in everything it writes to docs/ — the
constituent symbols live here in scripts/ (committed, like every other fetch
script) and in the private procedure doc, never in the rendered public site
(confidentiality rule 4/7; confscan greps docs/*.html + *.ai.txt only).

PAPER-TRACK, NOT LIVE CAPITAL. The live track follows the target sleeve baskets
in their current (risk-on) configuration with within-sleeve equal weight — it
does NOT reproduce each sleeve's internal regime/trend gates (BTD dip signals,
the crypto BTC-trend gate, the rates/EM vol-targeting). Those live in the
backtest. This is a deliberately transparent, reproducible stand-in. See
AI_PROCEDURES note + the caveats rendered on strategies.html.

Best-effort: a yfinance outage leaves the prior on-disk state untouched (Yahoo
blocks cloud IPs, so this runs on the host pipeline only, never the GH Action).
"""
import json
import sys
from datetime import date

import pandas as pd
import yfinance as yf

from paths import DATA_S as DATA

STATE = f"{DATA}/ember_papertrack.json"
CSV = f"{DATA}/ember_papertrack.csv"

# ── sleeve composition (within-sleeve EQUAL weight; live-proxy, see header) ────
# Sleeve weights are the Finding #38 inverse-vol recommendation.
SLEEVES = {
    "anchor": (0.33, ["SPY", "IEF", "GLD"]),                 # deployed flagship defensive core
    "rates":  (0.42, ["SHV", "IEF", "TLT", "TIP", "BIL"]),   # Treasury duration ladder (#35)
    "crypto": (0.07, ["IBIT", "FBTC", "ETHA", "FETH"]),      # spot digital-asset ETFs (#37)
    "em":     (0.18, ["EWZ", "MCHI", "EWY", "INDA", "EWS",   # diversified EM countries (#29)
                      "THD", "EZA", "TUR", "EPOL"]),
}
# The anchor proxy IS the Static 50/30/20 defensive basket (SPY/IEF/GLD, 50/30/20),
# so the baseline overlay = that same basket at 100% weight — an apples-to-apples
# "ensemble vs deployed-book-proxy" comparison on one reproducible benchmark.
ANCHOR_W = {"SPY": 0.50, "IEF": 0.30, "GLD": 0.20}


def ember_weights():
    """Effective per-ticker target weight across all four sleeves (sums to 1).
    Anchor follows the Static 50/30/20 split; every other sleeve is within-sleeve
    equal weight."""
    w = {}
    for key, (sw, names) in SLEEVES.items():
        for t in names:
            inc = sw * ANCHOR_W[t] if key == "anchor" else sw / len(names)
            w[t] = w.get(t, 0.0) + inc
    return w


def baseline_weights():
    return {t: ANCHOR_W[t] for t in ANCHOR_W}


EMBER_W = ember_weights()
BASE_W = baseline_weights()
ALL_TICKERS = sorted(set(EMBER_W) | set(BASE_W))


def fetch_closes():
    """Daily adjusted-close panel for every constituent, forward-filled on the
    common (SPY) trading calendar. Returns None on a total fetch failure."""
    df = yf.download(ALL_TICKERS, period="6mo", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        return None
    closes = df["Close"] if "Close" in df.columns.get_level_values(0) else df
    if isinstance(closes, pd.Series):
        closes = closes.to_frame()
    closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
    # align to days SPY trades, forward-fill the rest (all are US-listed ETFs)
    if "SPY" in closes.columns:
        closes = closes.loc[closes["SPY"].notna()]
    closes = closes.ffill()
    missing = [t for t in ALL_TICKERS if t not in closes.columns]
    if missing:
        print(f"  (warn: tickers absent from feed: {missing})")
    closes = closes[[t for t in ALL_TICKERS if t in closes.columns]].dropna()
    return closes


def nav(units, prices):
    return float(sum(units[t] * prices[t] for t in units))


def set_units(weights, value, prices):
    return {t: value * w / prices[t] for t, w in weights.items()}


def main():
    try:
        closes = fetch_closes()
    except Exception as e:                               # noqa: BLE001
        print(f"  (warn: yfinance fetch failed: {e}); leaving prior state untouched")
        return 0
    if closes is None or closes.empty:
        print("  (warn: empty price panel); leaving prior state untouched")
        return 0

    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = None

    dates = [d.strftime("%Y-%m-%d") for d in closes.index]

    if st is None:
        # ── seed: paper-track starts on the latest available close ────────────
        d0 = dates[-1]
        p0 = {t: float(closes.iloc[-1][t]) for t in closes.columns}
        st = {
            "start_date": d0,
            "rebalance_month": d0[:7],
            "units": {"ember": set_units(EMBER_W, 100.0, p0),
                      "baseline": set_units(BASE_W, 100.0, p0)},
            "series": [{"date": d0, "ember": 100.0, "baseline": 100.0}],
        }
        print(f"  seeded EMBER paper-track at {d0} (NAV=100)")
    else:
        last = st["series"][-1]["date"]
        new_dates = [d for d in dates if d > last]
        for d in new_dates:
            prices = {t: float(closes.loc[pd.Timestamp(d)][t]) for t in closes.columns}
            # monthly rebalance: on the first trading day of a new month, mark
            # NAV with the carried units (continuity), then reset to target wts.
            if d[:7] != st["rebalance_month"]:
                e_nav = nav(st["units"]["ember"], prices)
                b_nav = nav(st["units"]["baseline"], prices)
                st["units"]["ember"] = set_units(EMBER_W, e_nav, prices)
                st["units"]["baseline"] = set_units(BASE_W, b_nav, prices)
                st["rebalance_month"] = d[:7]
            e_nav = nav(st["units"]["ember"], prices)
            b_nav = nav(st["units"]["baseline"], prices)
            st["series"].append({"date": d, "ember": round(e_nav, 4),
                                 "baseline": round(b_nav, 4)})
        if new_dates:
            print(f"  appended {len(new_dates)} day(s): {new_dates[0]}..{new_dates[-1]}")
        else:
            print(f"  no new trading days since {last}")

    st["asof"] = dates[-1]
    st["weights"] = {"anchor": 33, "rates": 42, "crypto": 7, "em": 18}
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, separators=(",", ":"))

    s = pd.DataFrame(st["series"])
    s.to_csv(CSV, index=False)

    e, b = s.iloc[-1]["ember"], s.iloc[-1]["baseline"]
    print(f"EMBER paper-track: {len(s)} day(s) since {st['start_date']} | "
          f"ensemble {e:.2f} vs baseline {b:.2f} (rel {e - b:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
