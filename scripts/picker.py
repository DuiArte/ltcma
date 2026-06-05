"""Composite stock picker — merges every numeric variable from the two stock
pipelines (CFA/Buffett fundamentals + macro-signal sensitivities) into one
reproducible composite score per ticker.

Reproducible recipe (any analyst can re-derive from public data + this formula):
  1. Universe  = the macro-signal coverage set (the tickers that carry BOTH
     fundamental and macro-signal variables).
  2. Variables = every numeric column from either source (see FEATURES).
  3. z-score   = (x - mean) / std, cross-sectional across the universe; missing
     values impute to z = 0 (neutral).
  4. Weights   = each variable's Pearson correlation with realised forward returns
     (mean post-FOMC 5-day drift per ticker), normalised so sum|w| = 1. The
     CORRELATION SIGN sets the variable's direction automatically — nothing is
     hand-picked. Falls back to equal-weight if the target is unavailable.
  5. Composite = sum_v  w_v * z_v   (signed contributions).
  6. Rank desc; top 20 = the picks.

Confidentiality: the WEIGHT VALUES (w_v) stay in code — never rendered. The page
shows the ranked result + each pick's variable contributions (direction + relative
magnitude), not the weights themselves.
"""
import os, time, math
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import yfinance as yf

ANA = "/home/carlos/capstone/data/analytics"
G_CAP = 0.045
RF, ERP = 0.045, 0.045

# ---- variable registry: (key, label, source) -------------------------------
# every numeric variable available across BOTH pipelines
FEATURES = [
    # fundamentals (CFA / Buffett pipeline, live yfinance)
    ("roe",        "ROE",             "fundamental"),
    ("gross_marg", "Gross margin",    "fundamental"),
    ("fcf_yield",  "FCF yield",       "fundamental"),
    ("net_marg",   "Net margin",      "fundamental"),
    ("mos",        "Margin of safety","fundamental"),
    ("buffett",    "Buffett score",   "fundamental"),
    ("rev_growth", "Revenue growth",  "fundamental"),
    ("eps_growth", "Earnings growth", "fundamental"),
    ("inv_de",     "Low leverage",    "fundamental"),   # 1/(1+D/E): higher=safer
    ("mom_12_1",   "12-1 momentum",   "fundamental"),
    # macro-signal pipeline (sensitivities parquet)
    ("inv_pe",     "Earnings yield",  "signal"),         # 1/PE
    ("inv_fwd_pe", "Fwd earnings yld","signal"),         # 1/fwd_PE
    ("beta_rates", "Rate beta",       "signal"),
    ("beta_dxy",   "Dollar beta",     "signal"),
    ("beta_cad",   "CAD beta",        "signal"),
    ("r2",         "Macro R-squared", "signal"),
]
FKEYS = [f[0] for f in FEATURES]
FLABEL = {k: l for k, l, _ in FEATURES}
FSRC = {k: s for k, s, _ in FEATURES}


def _num(x):
    try:
        x = float(x)
        return x if x == x and abs(x) != math.inf else None
    except (TypeError, ValueError):
        return None


def _two_stage_iv(cf0, g1, r, g2=G_CAP, n=5):
    if cf0 is None or cf0 <= 0 or r <= g2:
        return None
    pv1 = sum(cf0 * (1 + g1) ** k / (1 + r) ** k for k in range(1, n + 1))
    tv = cf0 * (1 + g1) ** n * (1 + g2) / (r - g2)
    return pv1 + tv / (1 + r) ** n


def _intrinsic(info, price):
    beta = _num(info.get("beta")) or 1.0
    r = max(RF + beta * ERP, G_CAP + 0.03)
    roe = _num(info.get("returnOnEquity"))
    payout = _num(info.get("payoutRatio")) or 0.0
    eps = _num(info.get("trailingEps"))
    fcf = _num(info.get("freeCashflow")); sh = _num(info.get("sharesOutstanding"))
    fcfps = fcf / sh if (fcf and sh) else None
    dy = _num(info.get("dividendYield")); dy = dy / 100 if dy is not None else 0.0
    g1 = _num(info.get("earningsGrowth")) or _num(info.get("revenueGrowth"))
    g1 = max(min(g1, 0.25), 0.0) if g1 is not None else G_CAP
    vals = []
    if fcfps and fcfps > 0:
        v = _two_stage_iv(fcfps, g1, r); vals += [v] if v else []
    if dy > 0:
        v = _two_stage_iv(price * dy, g1, r); vals += [v] if v else []
    if roe is not None and eps and eps > 0 and payout > 0:
        g = min(roe * (1 - payout), G_CAP, r - 0.005)
        if r > g:
            vals.append(payout * (1 + g) / (r - g) * eps)
    return sum(vals) / len(vals) if vals else None


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def fundamentals(ticker):
    """Live fundamentals + 12-1 momentum for one ticker (2 attempts)."""
    info = None
    for _ in range(2):
        try:
            info = yf.Ticker(ticker).info or {}
            break
        except Exception:
            time.sleep(0.4)
    if not info:
        return None
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    if not price:
        return None
    roe = _num(info.get("returnOnEquity"))
    de = _num(info.get("debtToEquity")); de = de / 100 if de is not None else None
    gm = _num(info.get("grossMargins"))
    nm = _num(info.get("profitMargins"))
    mcap = _num(info.get("marketCap")); fcf = _num(info.get("freeCashflow"))
    fcf_y = (fcf / mcap) if (fcf and mcap) else None
    iv = _intrinsic(info, price)
    mos = (iv / price - 1) if iv else None
    # Buffett 5-pillar score (same construction as 19_stock_analysis.py)
    pil = []
    if roe is not None:   pil.append(_clamp(roe / 0.20))
    if de is not None:    pil.append(_clamp(1 - de))
    if fcf_y is not None: pil.append(_clamp(fcf_y / 0.08))
    if gm is not None and gm > 0: pil.append(_clamp(gm / 0.50))
    if mos is not None:   pil.append(_clamp(0.5 + mos / 0.80))
    buffett = (100 * sum(pil) / len(pil)) if len(pil) >= 3 else None
    # 12-1 momentum: 12m return excluding the most recent month
    mom = None
    try:
        h = yf.Ticker(ticker).history(period="14mo", interval="1mo",
                                      auto_adjust=True)["Close"].dropna()
        if len(h) >= 13:
            mom = float(h.iloc[-2] / h.iloc[-13] - 1)
    except Exception:
        pass
    return {"ticker": ticker, "price": price, "sector": info.get("sector", ""),
            "name": info.get("shortName") or info.get("longName") or ticker,
            "roe": roe, "gross_marg": gm, "fcf_yield": fcf_y, "net_marg": nm,
            "mos": (max(min(mos, 1.0), -0.9) if mos is not None else None),
            "buffett": buffett,
            "rev_growth": _num(info.get("revenueGrowth")),
            "eps_growth": _num(info.get("earningsGrowth")),
            "inv_de": (1.0 / (1.0 + de) if de is not None and de >= 0 else None),
            "mom_12_1": mom}


def build_universe():
    """Return (df, weights, meta). df indexed by ticker with all FEATURES,
    contributions and composite. weights kept internal."""
    sens = pd.read_parquet(f"{ANA}/stock_sensitivities.parquet")
    fomc = pd.read_parquet(f"{ANA}/stock_fomc_reaction.parquet")
    tickers = sorted(sens["ticker"].unique().tolist())
    # forward-return target: mean realised 5-day post-FOMC drift per ticker
    target = fomc.groupby("ticker")["fwd5"].mean()

    with ThreadPoolExecutor(max_workers=8) as ex:
        funds = [r for r in ex.map(fundamentals, tickers) if r]
    fdf = pd.DataFrame(funds).set_index("ticker")

    s = sens.set_index("ticker")
    rows = {}
    for tk in tickers:
        if tk not in fdf.index:
            continue
        f = fdf.loc[tk]
        sv = s.loc[tk] if tk in s.index else {}
        pe = _num(sv.get("pe")); fpe = _num(sv.get("fwd_pe"))
        rows[tk] = {
            "name": f["name"], "sector": f["sector"], "price": f["price"],
            "roe": f["roe"], "gross_marg": f["gross_marg"], "fcf_yield": f["fcf_yield"],
            "net_marg": f["net_marg"], "mos": f["mos"], "buffett": f["buffett"],
            "rev_growth": f["rev_growth"], "eps_growth": f["eps_growth"],
            "inv_de": f["inv_de"], "mom_12_1": f["mom_12_1"],
            "inv_pe": (1.0 / pe if pe and pe > 0 else None),
            "inv_fwd_pe": (1.0 / fpe if fpe and fpe > 0 else None),
            "beta_rates": _num(sv.get("beta_rates")), "beta_dxy": _num(sv.get("beta_dxy")),
            "beta_cad": _num(sv.get("beta_cad")), "r2": _num(sv.get("r2")),
            "target": _num(target.get(tk)),
        }
    df = pd.DataFrame(rows).T
    for c in FKEYS + ["target", "price"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # z-score each feature; impute missing to 0 (neutral)
    z = pd.DataFrame(index=df.index)
    for k in FKEYS:
        col = df[k].astype(float)
        mu, sd = col.mean(), col.std(ddof=0)
        z[k] = ((col - mu) / sd).fillna(0.0) if (sd == sd and sd > 0) else 0.0

    # weights from corr(feature, forward-return target); sign = corr sign
    tgt = df["target"].astype(float)
    have_t = int(tgt.notna().sum())
    raw = {}
    for k in FKEYS:
        if have_t >= 8:
            c = np.corrcoef(z[k].values, tgt.fillna(tgt.mean()).values)[0, 1]
            raw[k] = 0.0 if (c != c) else float(c)
        else:
            raw[k] = 1.0  # equal-weight fallback
    norm = sum(abs(v) for v in raw.values()) or 1.0
    weights = {k: raw[k] / norm for k in FKEYS}

    # contributions + composite
    contrib = pd.DataFrame(index=df.index)
    for k in FKEYS:
        contrib[k] = z[k] * weights[k]
    df["composite"] = contrib.sum(axis=1)
    df = df.sort_values("composite", ascending=False)
    df["rank"] = range(1, len(df) + 1)

    meta = {"weights": weights, "target_coverage": have_t,
            "n_universe": len(df), "z": z, "contrib": contrib,
            "equal_weight_fallback": have_t < 8}
    return df, weights, meta


if __name__ == "__main__":
    df, w, meta = build_universe()
    print("universe=%d  target_coverage=%d/40  fallback=%s" % (
        meta["n_universe"], meta["target_coverage"], meta["equal_weight_fallback"]))
    print("\n=== weights (INTERNAL, by |corr| desc) ===")
    for k, v in sorted(w.items(), key=lambda kv: -abs(kv[1])):
        print("  %-18s %+.4f" % (FLABEL[k], v))
    print("\n=== TOP 20 ===")
    contrib = meta["contrib"]
    for tk, r in df.head(20).iterrows():
        cs = contrib.loc[tk]
        dom = cs.abs().idxmax()
        print("%2d. %-6s %-22s comp=%+.3f  dom=%s(%+.3f)  $%.0f" % (
            int(r["rank"]), tk, str(r["sector"])[:22], r["composite"],
            FLABEL[dom], cs[dom], r["price"]))
    print("\n=== sector distribution (top 20) ===")
    print(df.head(20)["sector"].value_counts().to_string())
    cv = meta["contrib"].var(ddof=0)
    share = (cv / cv.sum()).sort_values(ascending=False)
    print("\n=== variable variance share (dominance check) ===")
    for k, v in share.head(6).items():
        print("  %-18s %5.1f%%" % (FLABEL[k], v * 100))
    print("  MAX share = %.1f%%  (%s)" % (
        share.iloc[0] * 100, "FLAG >80%" if share.iloc[0] > 0.8 else "ok"))
    base = df.sort_values("mom_12_1", ascending=False).head(20).index
    top = df.head(20).index
    overlap = len(set(base) & set(top))
    sp = df[["composite", "mom_12_1"]].astype(float).corr(method="spearman").iloc[0, 1]
    print("\n=== baseline vs naive momentum ===")
    print("  overlap top20: %d/20   Spearman(composite, momentum)=%+.2f" % (overlap, sp))
