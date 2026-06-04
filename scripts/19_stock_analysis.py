"""CFA-style stock analysis tool.
Analyzes any stock with the CFA equity-valuation framework: profitability and
DuPont, solvency/liquidity, growth, relative valuation (multiples) and absolute
valuation (CAPM required return, sustainable growth, Gordon DDM, justified P/E).

Usage:
  python 19_stock_analysis.py                 -> default watchlist
  python 19_stock_analysis.py NVDA TSLA KO    -> analyze any tickers
Output: docs/stock_<TICKER>.html per stock, docs/stocks.html landing+methodology.
Data: Yahoo Finance (free). CFA curriculum used as a methodology reference only.
"""
import sys, os, glob, math, time
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from glossary import NAV, ccy_badge

DOCS = os.path.expanduser("~/LTCMA/docs")
INK, BLUE, GOLD, GREEN, RED, GREY = "#111111", "#0a2540", "#6b7280", "#0a5d3a", "#7c2d12", "#888888"
RF, ERP = 0.045, 0.045            # CAPM risk-free & equity risk premium assumptions
G_CAP = 0.045                     # terminal nominal growth cap (long-run US GDP)
DEFAULT = ["AMZN", "GOOGL", "MSFT", "META", "IBM", "BA", "NVDA", "AAPL"]
# Buffett-style screener universes. The score uses ratios (ROE, D/E, FCF yield,
# gross margin) that are currency-neutral, so US and Mexican names are comparable;
# only the margin-of-safety needs the local-currency price, which cancels in the
# intrinsic/price ratio. The US universe is the full S&P 500 (fetched live from
# Wikipedia, with this curated large-cap list as the offline fallback); IPC = the
# 35-name S&P/BMV IPC.
US_FALLBACK = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "BRK-B", "JPM",
               "V", "MA", "KO", "PEP", "PG", "JNJ", "UNH", "HD", "COST", "WMT",
               "MCD", "AXP", "CVX", "XOM", "MMM", "CAT", "DE", "LMT", "CSCO",
               "TXN", "ORCL", "IBM"]

def sp500_tickers():
    """Current S&P 500 constituents from Wikipedia (Yahoo symbol format).
    Falls back to the curated large-cap list if the fetch/parse fails."""
    try:
        html = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers={"User-Agent": "Mozilla/5.0 (research; LTCMA build)"},
            timeout=30).text
        syms = (pd.read_html(StringIO(html))[0]["Symbol"].astype(str)
                .str.replace(".", "-", regex=False).str.strip().tolist())
        if len(syms) > 400:
            return syms
        print(f"  (warn: S&P 500 list looked short ({len(syms)}); using fallback)")
    except Exception as e:
        print(f"  (warn: S&P 500 list fetch failed: {e}; using fallback)")
    return US_FALLBACK

IPC_SCREEN = ["WALMEX.MX", "FEMSAUBD.MX", "GFNORTEO.MX", "GMEXICOB.MX", "AMXB.MX",
              "CEMEXCPO.MX", "BIMBOA.MX", "ALFAA.MX", "KOFUBL.MX", "TLEVISACPO.MX",
              "GAPB.MX", "ASURB.MX", "OMAB.MX", "KIMBERA.MX", "GRUMAB.MX", "AC.MX",
              "ELEKTRA.MX", "GCARSOA1.MX", "ORBIA.MX", "PINFRA.MX", "MEGACPO.MX",
              "LABB.MX", "GENTERA.MX", "Q.MX", "RA.MX", "BBAJIOO.MX", "VESTA.MX",
              "CHDRAUIB.MX", "GFINBURO.MX", "BOLSAA.MX", "CUERVO.MX", "ALSEA.MX",
              "PE&OLES.MX", "LIVEPOLC-1.MX", "GCC.MX"]
# NAV imported from glossary module
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">')
LAYOUT = dict(template="plotly_white", dragmode=False,
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=14), margin=dict(l=55, r=20, t=46, b=42),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e5e5e5"), yaxis=dict(gridcolor="#e5e5e5"))

def div(fig, name):
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                       config={"displayModeBar": False, "scrollZoom": False,
                               "doubleClick": False, "showAxisDragHandles": False})

def num(x):  return x if isinstance(x, (int, float)) and x == x else None
def pct(x):  return f"{x*100:.1f}%" if num(x) is not None else "n/a"
def rt(x):   return f"{x:.2f}" if num(x) is not None else "n/a"
def big(x):
    x = num(x)
    if x is None: return "n/a"
    for u, d in [("T", 1e12), ("B", 1e9), ("M", 1e6)]:
        if abs(x) >= d: return f"${x/d:.1f}{u}"
    return f"${x:,.0f}"

def page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title>{FONTS}<link rel="stylesheet" href="style.css">'
            f'<script src="{PLOTLY}"></script></head><body>'
            f'<header class="shell"><div class="shell-in">'
            f'<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b>'
            f'</span>{NAV}</div></header>{body}'
            f'<footer class="shell-foot"><div class="container"><p>CFA-framework '
            f'analysis on free Yahoo Finance data. Educational research, not '
            f'investment advice.</p></div></footer></body></html>')

def tiles(items):
    n = len(items)
    return (f'<div class="metrics" style="grid-template-columns:repeat({n},1fr)">'
            + "".join(
        f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
        for k, v in items) + '</div>')

def analyze(ticker):
    t = yf.Ticker(ticker)
    info = t.info or {}
    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
        print(f"  {ticker}: no data, skipped"); return None
    price = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
    name = info.get("longName", ticker)
    beta = num(info.get("beta")) or 1.0
    roe = num(info.get("returnOnEquity")); roa = num(info.get("returnOnAssets"))
    nm = num(info.get("profitMargins"))
    payout = num(info.get("payoutRatio")) or 0.0
    dy = num(info.get("dividendYield"))
    dy = dy / 100 if dy is not None else 0.0
    eps = num(info.get("trailingEps")); fwd_eps = num(info.get("forwardEps"))
    pb_now = num(info.get("priceToBook"))
    bvps = price / pb_now if (pb_now and pb_now > 0) else None
    fcf = num(info.get("freeCashflow"))
    shares = num(info.get("sharesOutstanding"))
    fcfps = fcf / shares if (fcf and shares) else None

    # --- CAPM required return, sustainable growth (capped at terminal) ---
    r = RF + beta * ERP
    g = roe * (1 - payout) if roe is not None else None
    if g is not None:
        g = min(g, G_CAP, r - 0.005)

    # --- stage-1 growth (years 1-5): analyst earnings growth, capped at 25% ---
    g1 = num(info.get("earningsGrowth")) or num(info.get("revenueGrowth"))
    if g1 is not None:
        g1 = max(min(g1, 0.25), 0.0)
    else:
        g1 = G_CAP

    # --- justified multiples + two-stage models ---
    ddm = fcfe_2s = just_pe = just_lpe = just_pb = None
    if g is not None and r > g:
        just_pe = payout * (1 + g) / (r - g)
        if payout > 0:
            just_lpe = payout / (r - g)
        if roe is not None and (roe - g) > 0:
            just_pb = (roe - g) / (r - g)

    def two_stage(cf0, _g1=g1, _g2=G_CAP, _r=r, n=5):
        """Two-stage DCF: cf0 grows at g1 for n years, then g2 perpetually."""
        if cf0 is None or cf0 <= 0 or _r <= _g2:
            return None
        pv1 = sum(cf0 * (1 + _g1) ** t / (1 + _r) ** t for t in range(1, n + 1))
        tv = cf0 * (1 + _g1) ** n * (1 + _g2) / (_r - _g2)
        return pv1 + tv / (1 + _r) ** n

    if dy > 0:                              # two-stage DDM (dividend payers)
        ddm = two_stage(price * dy)
    if fcfps:                               # two-stage FCFE
        fcfe_2s = two_stage(fcfps)

    # --- CFA-framework target prices (multi-method) ---
    # Justified-P/E methods value only the dividend stream, so they make sense
    # only for mature dividend payers (>=30% payout); they understate retention-
    # heavy growth firms. Justified P/B and FCFE perpetuity work for any firm.
    targets = {}
    if payout >= 0.30:
        if just_pe and eps and eps > 0:
            targets["Justified trailing P/E"] = just_pe * eps
        if just_lpe and fwd_eps and fwd_eps > 0:
            targets["Justified leading P/E"] = just_lpe * fwd_eps
    if just_pb and bvps:
        targets["Justified P/B"] = just_pb * bvps
    if ddm:
        targets["Two-stage DDM"] = ddm
    if fcfe_2s:
        targets["Two-stage FCFE"] = fcfe_2s
    tgt = num(info.get("targetMeanPrice"))
    syn = sum(targets.values()) / len(targets) if targets else None
    upside = (syn / price - 1) if syn else None

    # --- DuPont ---
    asset_turn = (roa / nm) if (roa is not None and nm) else None
    leverage = (roe / roa) if (roe is not None and roa) else None
    pe = num(info.get("trailingPE")); fpe = num(info.get("forwardPE"))

    # --- 5y price + 12-month forecast cone ---
    hist_d = t.history(period="5y", interval="1d", auto_adjust=True)["Close"].dropna()
    lr = np.log(hist_d / hist_d.shift(1)).dropna()
    vol_a = float(lr.iloc[-252:].std() * np.sqrt(252)) if len(lr) > 50 else 0.25 * beta
    months = 12
    fwd_idx = pd.date_range(hist_d.index[-1], periods=months + 1, freq="ME")[1:]
    mu = math.log(syn / price) if (syn and syn > 0) else 0.0
    tfrac = np.arange(1, months + 1) / 12.0
    med = price * np.exp(mu * tfrac)
    hi = price * np.exp(mu * tfrac + vol_a * np.sqrt(tfrac))
    lo = price * np.exp(mu * tfrac - vol_a * np.sqrt(tfrac))
    c_fc = go.Figure()
    c_fc.add_scatter(x=hist_d.index, y=hist_d.values, mode="lines",
                     line=dict(color=GREY, width=1.5), name="Historical price")
    c_fc.add_scatter(x=list(fwd_idx) + list(fwd_idx[::-1]),
                     y=list(hi) + list(lo[::-1]), fill="toself",
                     fillcolor="rgba(15,98,254,0.13)", line=dict(width=0),
                     name=f"±1σ band ({vol_a*100:.0f}% vol)")
    c_fc.add_scatter(x=fwd_idx, y=med, mode="lines",
                     line=dict(color=BLUE, width=2.5, dash="dot"),
                     name="Synthesized target path")
    palette = [GOLD, GREEN, RED, "#8a3ffc", "#009d9a"]
    for i, (lbl, v) in enumerate(targets.items()):
        c_fc.add_scatter(x=[fwd_idx[-1]], y=[v], mode="markers",
                         marker=dict(color=palette[i % 5], size=10), name=lbl)
    if tgt:
        c_fc.add_scatter(x=[fwd_idx[-1]], y=[tgt], mode="markers",
                         marker=dict(color=INK, size=11, symbol="diamond"),
                         name=f"Analyst ${tgt:,.0f}")
    c_fc.update_layout(title="Price history (5y) and 12-month forecast",
                       yaxis_title="price (USD)", xaxis_title="date",
                       legend=dict(orientation="h", y=-0.22))

    prof = [("Gross margin", info.get("grossMargins")),
            ("Operating margin", info.get("operatingMargins")),
            ("Net margin", nm), ("ROE", roe), ("ROA", roa)]
    prof = [(k, num(v)) for k, v in prof if num(v) is not None]
    c2 = go.Figure(go.Bar(x=[k for k, _ in prof], y=[v * 100 for _, v in prof],
                          marker_color=BLUE, text=[f"{v*100:.0f}%" for _, v in prof],
                          textposition="outside"))
    c2.update_layout(title="Profitability (%)", yaxis_title="%")

    mult = [("P/E", pe), ("Fwd P/E", fpe), ("P/B", pb_now),
            ("P/S", num(info.get("priceToSalesTrailing12Months"))),
            ("EV/EBITDA", num(info.get("enterpriseToEbitda")))]
    mult = [(k, v) for k, v in mult if v is not None]
    c3 = go.Figure(go.Bar(x=[k for k, _ in mult], y=[v for _, v in mult],
                          marker_color=GOLD, text=[f"{v:.1f}" for _, v in mult],
                          textposition="outside"))
    c3.update_layout(title="Valuation multiples", yaxis_title="x")

    # --- verdict ---
    bits = []
    if syn:
        bits.append(f"the CFA-framework methods synthesize to a 12-month fair "
                    f"value of ${syn:,.2f} ({upside*100:+.0f}% vs the "
                    f"${price:,.2f} market price)")
    if pe and just_pe:
        gap = ("above" if pe > just_pe * 1.15
               else "in line with" if pe > just_pe * 0.85 else "below")
        bits.append(f"the trailing P/E of {pe:.1f} sits {gap} its justified "
                    f"P/E of {just_pe:.1f} (CAPM r={r*100:.1f}%, g={pct(g)})")
    if tgt:
        bits.append(f"consensus analyst target ${tgt:,.0f} "
                    f"({(tgt/price-1)*100:+.0f}%, "
                    f"&lsquo;{info.get('recommendationKey','n/a')}&rsquo;)")
    verdict = f"{name} &mdash; " + "; ".join(bits) + "."

    tr = ""
    for lbl, v in targets.items():
        up_p = (v / price - 1) * 100
        cls = "pos" if up_p >= 0 else "neg"
        tr += (f"<tr><td>{lbl}</td><td>${v:,.2f}</td>"
               f"<td class='{cls}'>{up_p:+.1f}%</td></tr>")
    if tgt:
        upa = (tgt / price - 1) * 100
        cls_a = "pos" if upa >= 0 else "neg"
        tr += (f"<tr><td><i>Analyst consensus (reference)</i></td>"
               f"<td>${tgt:,.2f}</td><td class='{cls_a}'>{upa:+.1f}%</td></tr>")
    if syn:
        cls_up = "pos" if upside >= 0 else "neg"
        syn_line = (f"<b>Synthesized 12-month target</b> "
                    f"<span style='color:#0a2540;font-size:20px;font-weight:600'>"
                    f"${syn:,.2f}</span> <span class='{cls_up}' "
                    f"style='font-weight:600'>{upside*100:+.1f}%</span>")
    else:
        syn_line = "<i>Synthesized target unavailable</i>"

    snap = tiles([("Market Cap", big(info.get("marketCap"))),
                  ("Price", f"${price:,.2f}"), ("Trailing P/E", rt(pe)),
                  ("Beta", rt(beta)), ("Dividend Yield", pct(dy)),
                  ("Synth. Target", f"${syn:,.2f}" if syn else "n/a")])
    val_rows = "".join(
        f"<tr><td>{k}</td><td>{rt(v)}</td></tr>" for k, v in mult)
    body = f"""<section class="hero"><div class="container">
<h1>{name} <span style="color:#888888">({ticker})</span></h1>
<p class="lede">{info.get('sector','')} &middot; {info.get('industry','')}</p>
<p class="asof">CFA-framework equity analysis &middot; data: Yahoo Finance</p>
</div></section><main class="container">
<section class="block"><h2>Snapshot</h2>
{ccy_badge("USD", "US-listed stock, figures in US dollars")}{snap}</section>
<section class="block"><h2>Forecast &amp; Price Targets</h2>
<p class="note">The applicable CFA valuation methods produce intrinsic-value
estimates; the synthesized target is their average. Dividend-discount and FCFE
use a <b>two-stage growth model</b> &mdash; the analyst-implied near-term rate
for five years, then a 4.5% terminal rate &mdash; which avoids the single-stage
pessimism on high-growth firms. Justified-P/E methods are applied only for
mature dividend payers (payout &ge; 30%). The shaded band is the &plusmn;1
standard-deviation range (one-year realised vol ~{vol_a*100:.0f}%). Definitions
in the <a href="glossary.html">Glossary</a>.</p>
<div class="grid">
<div class="tile chart"><div class="ch">{div(c_fc, ticker+'-fc')}</div></div>
<div class="tile" style="padding:18px 22px">
<p style="margin-bottom:14px">{syn_line}</p>
<table class="ptable"><thead><tr><th>Method</th><th>Target</th><th>vs price</th></tr></thead>
<tbody>{tr}</tbody></table>
<p style="font-size:12px;color:#555555;margin-top:14px">
CAPM r = {r*100:.1f}% &middot; stage-1 growth g&#8321; = {pct(g1)}
(analyst, capped at 25%) &middot; terminal g&#8322; = {G_CAP*100:.1f}%
&middot; payout {pct(payout)}.
</p></div></div></section>
<section class="block"><h2>Valuation Multiples</h2>
<div class="grid"><div class="tile chart"><div class="ch">{div(c3,ticker+'-mult')}</div></div>
<div class="tile" style="padding:16px 22px">
<table class="ptable"><thead><tr><th>Multiple</th><th>Value</th></tr></thead>
<tbody>{val_rows}</tbody></table></div></div></section>
<section class="block"><h2>Profitability &amp; DuPont</h2>
<div class="grid"><div class="tile chart"><div class="ch">{div(c2,ticker+'-prof')}</div></div>
<div class="tile" style="padding:16px 22px">
<p style="font-size:14px"><b>DuPont decomposition of ROE</b></p>
<p style="font-size:13px;color:#393939">ROE = net margin &times; asset turnover
&times; financial leverage</p>
<table class="ptable"><tbody>
<tr><td>Net margin</td><td>{pct(nm)}</td></tr>
<tr><td>Asset turnover</td><td>{rt(asset_turn)}</td></tr>
<tr><td>Financial leverage</td><td>{rt(leverage)}</td></tr>
<tr><td>= Return on equity</td><td>{pct(roe)}</td></tr></tbody></table></div></div></section>
<section class="block"><h2>Financial Health &amp; Growth</h2>{tiles([
  ("Debt / Equity", rt((num(info.get('debtToEquity')) or 0)/100)),
  ("Current Ratio", rt(info.get('currentRatio'))),
  ("Quick Ratio", rt(info.get('quickRatio'))),
  ("Revenue Growth", pct(info.get('revenueGrowth'))),
  ("Earnings Growth", pct(info.get('earningsGrowth')))])}</section>
<section class="block"><h2>CFA View</h2>
<div class="scaled-note" style="border-left-color:#0a2540">{verdict}</div></section>
</main>"""
    open(f"{DOCS}/stock_{ticker}.html", "w", encoding="utf-8").write(
        page(f"{ticker} — Equity Analysis", body))
    syn_s = f"${syn:,.2f}" if syn else "n/a"
    print(f"  {ticker}: P/E {rt(pe)}  ROE {pct(roe)}  syn-target {syn_s}  -> stock_{ticker}.html")
    return {"ticker": ticker, "name": name, "sector": info.get("sector", ""),
            "pe": pe, "roe": roe, "price": price, "target": syn}

# ---------- Buffett-style value screener (lightweight: no per-stock page) ----------
def _two_stage_iv(cf0, g1, r, g2=G_CAP, n=5):
    if cf0 is None or cf0 <= 0 or r <= g2:
        return None
    pv1 = sum(cf0 * (1 + g1) ** k / (1 + r) ** k for k in range(1, n + 1))
    tv = cf0 * (1 + g1) ** n * (1 + g2) / (r - g2)
    return pv1 + tv / (1 + r) ** n

def _intrinsic(info, price):
    """Blend of two-stage FCFE/DDM and justified P/E — mirrors analyze().
    The discount rate is floored so the terminal spread (r - g2) is at least 3%,
    which avoids the Gordon-growth blow-up for low-beta names where r approaches
    the terminal growth rate."""
    beta = num(info.get("beta")) or 1.0
    r = max(RF + beta * ERP, G_CAP + 0.03)
    roe = num(info.get("returnOnEquity"))
    payout = num(info.get("payoutRatio")) or 0.0
    eps = num(info.get("trailingEps"))
    fcf = num(info.get("freeCashflow")); sh = num(info.get("sharesOutstanding"))
    fcfps = fcf / sh if (fcf and sh) else None
    dy = num(info.get("dividendYield")); dy = dy / 100 if dy is not None else 0.0
    g1 = num(info.get("earningsGrowth")) or num(info.get("revenueGrowth"))
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

def _cap_tier(mcap):
    if mcap is None:        return "&mdash;"
    if mcap >= 200e9:       return "Mega"
    if mcap >= 10e9:        return "Large"
    if mcap >= 2e9:         return "Mid"
    return "Small"

def buffett_row(ticker):
    info = None
    for _ in range(2):                       # one retry; threaded fetch of ~500 names
        try:
            info = yf.Ticker(ticker).info or {}
            break
        except Exception:
            time.sleep(0.4)
    if info is None:
        return None
    price = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
    if not price:
        return None
    roe = num(info.get("returnOnEquity"))
    de = num(info.get("debtToEquity")); de = de / 100 if de is not None else None
    gm = num(info.get("grossMargins"))
    mcap = num(info.get("marketCap")); fcf = num(info.get("freeCashflow"))
    fcf_y = (fcf / mcap) if (fcf and mcap) else None
    iv = _intrinsic(info, price)
    mos = (iv / price - 1) if iv else None
    pillars = []                                            # each 0..1, full mark at:
    if roe is not None:   pillars.append(_clamp(roe / 0.20))        # ROE 20%
    if de is not None:    pillars.append(_clamp(1 - de))            # D/E 0 (>=1 -> 0)
    if fcf_y is not None: pillars.append(_clamp(fcf_y / 0.08))      # FCF yield 8%
    if gm is not None and gm > 0: pillars.append(_clamp(gm / 0.50)) # gross margin 50%
    if mos is not None:   pillars.append(_clamp(0.5 + mos / 0.80))  # +40% margin of safety
    # require >=3 data pillars for a meaningful score; sparse names (often banks/
    # insurers with no gross margin or FCF) would otherwise rank on 1-2 noisy inputs
    score = round(100 * sum(pillars) / len(pillars)) if len(pillars) >= 3 else None
    return {"ticker": ticker,
            "name": (info.get("shortName") or info.get("longName") or ticker),
            "tier": _cap_tier(mcap),
            "roe": roe, "de": de, "fcf_y": fcf_y, "gm": (gm if gm else None),
            "mos": mos, "score": score, "np": len(pillars)}

def _mos_fmt(x):
    """Margin of safety, capped at +/-100% for display (the rough two-stage DCF
    saturates for low-beta staples and holding companies)."""
    if not (isinstance(x, (int, float)) and x == x):
        return "n/a"
    if x > 1.0:
        return "&ge;&plus;100%"
    if x < -0.9:
        return "&le;&minus;90%"
    return f"{x*100:+.1f}%"

def screen_body(rows):
    rows = [r for r in rows if r]
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    out = ""
    for r in rows:
        sc = r["score"]
        sc_cls = "pos" if (sc is not None and sc >= 70) else ("neg" if (sc is not None and sc < 45) else "")
        mos = r["mos"]
        mos_cls = "pos" if (mos is not None and mos > 0) else ("neg" if (mos is not None and mos < 0) else "")
        out += (f"<tr><td><b>{r['ticker']}</b> "
                f"<span style='font-size:11px;color:#888888'>{r['name'][:26]}</span></td>"
                f"<td><span style='font-size:11px;color:#555555'>{r.get('tier','&mdash;')}</span></td>"
                f"<td>{pct(r['roe'])}</td><td>{rt(r['de'])}</td>"
                f"<td>{pct(r['fcf_y'])}</td><td>{pct(r['gm'])}</td>"
                f"<td class='{mos_cls}'>{_mos_fmt(mos)}</td>"
                f"<td class='{sc_cls}' style='font-weight:600'>"
                f"{sc if sc is not None else 'n/a'}"
                f"<span style='font-size:10px;color:#888888'> /{r['np']}p</span></td></tr>")
    return out

def screen_universe(tickers, workers=8):
    # threaded .info fetch — ~500 names in well under a minute without throttling
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(buffett_row, tickers))

# ---------- run ----------
watch = [s.upper() for s in sys.argv[1:]] or DEFAULT
print(f"Analyzing {len(watch)} stocks...")
done = []
for tk in watch:
    try:
        r = analyze(tk)
        if r: done.append(r)
    except Exception as e:
        print(f"  {tk}: error {e}")

# landing page lists ALL stock_*.html present (so re-runs accumulate)
existing = sorted(os.path.basename(f)[6:-5]
                  for f in glob.glob(f"{DOCS}/stock_*.html"))
cards = "".join(
    f'<a class="scard" href="stock_{tk}.html"><div class="sc-t">{tk}</div>'
    f'<div class="sc-n">analysis &rarr;</div></a>' for tk in existing)

METHOD = """
<section class="block"><h2>Methodology — the CFA equity-analysis framework</h2>
<p class="lede2">Each report follows the standard CFA equity-valuation process:
quality first, then price.</p>
<h3>1. Profitability ratios</h3><p>Gross, operating and net margins measure how
much of revenue survives to each level of the income statement. Return on equity
(ROE) and return on assets (ROA) measure how efficiently capital generates
profit.</p>
<h3>2. DuPont decomposition</h3><p>ROE is broken into three drivers &mdash;
ROE = net margin &times; asset turnover &times; financial leverage. This shows
<i>why</i> a company earns its ROE: fat margins, efficient asset use, or
balance-sheet leverage. Leverage-driven ROE is lower quality than margin-driven
ROE.</p>
<h3>3. Solvency &amp; liquidity</h3><p>Debt/equity gauges balance-sheet risk;
the current and quick ratios gauge the ability to cover short-term obligations.</p>
<h3>4. Relative valuation (multiples)</h3><p>P/E, P/B, P/S and EV/EBITDA price
the company against its earnings, book value, sales and cash earnings. They are
quick but only meaningful in context &mdash; versus the company's history,
its sector, and its growth.</p>
<h3>5. Absolute valuation</h3><p>The required return is estimated with the
<b>CAPM</b>: r = risk-free rate + &beta; &times; equity risk premium
(here %.1f%% + &beta;&middot;%.1f%%). Sustainable growth is g = ROE &times;
(1 &minus; payout ratio). For dividend payers, the <b>Gordon dividend-discount
model</b> values the stock as D&#8321;/(r &minus; g). The <b>justified trailing
P/E</b>, payout &times; (1+g)/(r &minus; g), is the multiple the fundamentals
support &mdash; comparing it to the actual P/E shows whether the market is
optimistic or cautious relative to the fundamentals.</p>
<h3>Limitations</h3><p>Data is from free Yahoo Finance feeds and is approximate;
single-stage DDM assumes constant growth, which suits mature firms better than
high-growth ones. This is an educational framework, not investment advice.</p>
</section>""" % (RF * 100, ERP * 100)

# ---------- value-screener tables ----------
if os.environ.get("SKIP_SCREEN") == "1":
    SCREENER = ""
    print("Screener skipped (SKIP_SCREEN=1)")
else:
    US_UNIVERSE = sp500_tickers()
    print(f"Screening {len(US_UNIVERSE)} US (S&P 500) + {len(IPC_SCREEN)} IPC names...")
    us_rows = screen_universe(US_UNIVERSE)
    ipc_rows = screen_universe(IPC_SCREEN)
    us_cov = sum(1 for r in us_rows if r)
    ipc_cov = sum(1 for r in ipc_rows if r)

    def _sec(title, rows):
        return (f'<h3>{title}</h3>'
                '<div class="tile" style="padding:0 16px 8px;margin-bottom:18px">'
                '<table class="ptable"><thead><tr>'
                '<th>Company</th><th>Tier</th><th>ROE</th><th>D/E</th><th>FCF yield</th>'
                '<th>Gross margin</th><th>Margin of safety</th><th>Buffett score</th>'
                f'</tr></thead><tbody>{screen_body(rows)}</tbody></table></div>')

    SCREENER = (
        '<section class="block"><h2>Buffett-style Value Screener</h2>'
        + ccy_badge("USD", "ratios are currency-neutral; margin of safety uses each stock's local price")
        + '<p class="note">A transparent five-pillar screen in the spirit of '
          'quality-at-a-fair-price investing: durable <b>ROE</b>, low '
          '<b>debt/equity</b>, strong <b>free-cash-flow yield</b>, fat <b>gross '
          'margins</b> (a moat proxy) and a positive <b>margin of safety</b> versus '
          'a two-stage DCF. Each pillar earns a full mark at ROE 20%, D/E 0, FCF '
          'yield 8%, gross margin 50% and &plus;40% margin of safety; the Buffett '
          'score is their average (0&ndash;100) over the pillars that have data &mdash; '
          'the <span style="font-size:11px;color:#888888">/Np</span> tag shows how '
          'many. The <b>Tier</b> column flags market-cap size (Mega &ge;$200B, '
          'Large &ge;$10B, Mid &ge;$2B). The margin of safety is a rough two-stage '
          'DCF and is shown capped at &plusmn;100%; it is unreliable for holding '
          'companies and for financials (banks, insurers), which also lack a '
          'meaningful gross margin and free cash flow and so score on fewer pillars '
          '&mdash; not directly comparable to industrials. Free Yahoo Finance '
          'fundamentals are approximate; educational research, not investment advice.</p>'
        + _sec(f"S&amp;P 500 &mdash; {us_cov}/{len(US_UNIVERSE)} constituents with data, "
               "ranked by Buffett score", us_rows)
        + _sec(f"Mexican IPC &mdash; {ipc_cov}/{len(IPC_SCREEN)} with data", ipc_rows)
        + '</section>')
    print(f"  screener coverage: US {us_cov}/{len(US_UNIVERSE)}, IPC {ipc_cov}/{len(IPC_SCREEN)}")

land = f"""<section class="hero"><div class="container">
<h1>Equity Research</h1>
<p class="lede">CFA-framework analysis of individual stocks &mdash;
profitability, DuPont, financial health, and relative &amp; absolute
valuation. A reusable tool: run it on any ticker.</p>
<p class="asof">Data: Yahoo Finance &middot; {len(existing)} companies analyzed</p>
</div></section><main class="container">
<section class="block"><h2>Companies</h2>
{ccy_badge("USD", "all company figures in US dollars")}
<div class="scards">{cards}</div></section>
{SCREENER}
{METHOD}</main>"""
open(f"{DOCS}/stocks.html", "w", encoding="utf-8").write(
    page("Equity Research — CFA-style Stock Analysis", land))
print(f"\nLanding page: stocks.html ({len(existing)} companies)")
