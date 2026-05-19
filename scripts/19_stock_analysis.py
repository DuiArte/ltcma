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
import sys, os, glob
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

DOCS = os.path.expanduser("~/LTCMA/docs")
INK, BLUE, GOLD, GREEN, RED, GREY = "#161616", "#0f62fe", "#b28600", "#198038", "#da1e28", "#8d8d8d"
RF, ERP = 0.045, 0.045            # CAPM risk-free & equity risk premium assumptions
DEFAULT = ["AMZN", "GOOGL", "MSFT", "META", "IBM", "BA", "NVDA", "AAPL"]
NAV = ('<nav><a href="index.html">Dashboard</a>'
       '<a href="report.html">Full Report</a><a href="portfolio.html">Portfolio</a>'
       '<a href="stocks.html">Stock Analysis</a>'
       '<a href="index.html#about">About</a></nav>')
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')
LAYOUT = dict(template="plotly_white", dragmode=False,
              font=dict(family="IBM Plex Sans, sans-serif", size=12, color=INK),
              title_font=dict(color=INK, size=14), margin=dict(l=55, r=20, t=46, b=42),
              paper_bgcolor="white", plot_bgcolor="white",
              xaxis=dict(gridcolor="#e0e0e0"), yaxis=dict(gridcolor="#e0e0e0"))

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
            f'<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>Equity Research</b>'
            f'</span>{NAV}</div></header>{body}'
            f'<footer class="shell-foot"><div class="container"><p>CFA-framework '
            f'analysis on free Yahoo Finance data. Educational research, not '
            f'investment advice.</p></div></footer></body></html>')

def tiles(items):
    return ('<div class="metrics">' + "".join(
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
    dy = num(info.get("dividendYield"))           # in percent
    dy = dy / 100 if dy is not None else 0.0

    # --- CAPM required return, sustainable growth ---
    r = RF + beta * ERP
    g = roe * (1 - payout) if roe is not None else None
    if g is not None: g = min(g, r - 0.005)       # cap to keep DDM finite
    # --- Gordon DDM & justified trailing P/E ---
    ddm = just_pe = None
    if g is not None and r > g:
        if dy > 0:
            ddm = price * dy * (1 + g) / (r - g)
        just_pe = payout * (1 + g) / (r - g)

    # --- DuPont ---
    asset_turn = (roa / nm) if (roa is not None and nm) else None
    leverage = (roe / roa) if (roe is not None and roa) else None

    pe = num(info.get("trailingPE")); fpe = num(info.get("forwardPE"))
    tgt = num(info.get("targetMeanPrice"))

    # --- verdict ---
    bits = []
    if pe and just_pe:
        bits.append(f"trades at a trailing P/E of {pe:.1f} versus a justified "
                    f"P/E of {just_pe:.1f} (CAPM r={r*100:.1f}%, sustainable "
                    f"g={g*100:.1f}%) &mdash; the market is pricing "
                    f"{'optimism beyond the fundamentals' if pe > just_pe*1.15 else 'broadly in line with fundamentals' if pe > just_pe*0.85 else 'a discount to fundamentals'}")
    if ddm:
        bits.append(f"a Gordon dividend-discount model implies a value of "
                    f"${ddm:,.0f} ({'above' if ddm > price else 'below'} the "
                    f"${price:,.0f} price)")
    elif dy == 0:
        bits.append("it pays no dividend, so a dividend-discount model does not "
                    "apply &mdash; valuation rests on multiples and growth")
    if tgt:
        bits.append(f"consensus analyst target is ${tgt:,.0f} "
                    f"({(tgt/price-1)*100:+.0f}% vs price), rating "
                    f"&lsquo;{info.get('recommendationKey','n/a')}&rsquo;")
    verdict = f"{name} " + "; ".join(bits) + "."

    # --- charts ---
    hist = t.history(period="5y", interval="1mo", auto_adjust=True)["Close"]
    c1 = go.Figure()
    c1.add_scatter(x=hist.index, y=hist.values, mode="lines",
                   line=dict(color=BLUE, width=2), fill="tozeroy",
                   fillcolor="rgba(15,98,254,0.07)")
    c1.update_layout(title="Price — 5 years", yaxis_title="price")

    prof = [("Gross margin", info.get("grossMargins")),
            ("Operating margin", info.get("operatingMargins")),
            ("Net margin", nm), ("ROE", roe), ("ROA", roa)]
    prof = [(k, num(v)) for k, v in prof if num(v) is not None]
    c2 = go.Figure(go.Bar(x=[k for k, _ in prof], y=[v * 100 for _, v in prof],
                          marker_color=BLUE, text=[f"{v*100:.0f}%" for _, v in prof],
                          textposition="outside"))
    c2.update_layout(title="Profitability (%)", yaxis_title="%")

    mult = [("P/E", pe), ("Fwd P/E", fpe), ("P/B", num(info.get("priceToBook"))),
            ("P/S", num(info.get("priceToSalesTrailing12Months"))),
            ("EV/EBITDA", num(info.get("enterpriseToEbitda")))]
    mult = [(k, v) for k, v in mult if v is not None]
    c3 = go.Figure(go.Bar(x=[k for k, _ in mult], y=[v for _, v in mult],
                          marker_color=GOLD, text=[f"{v:.1f}" for _, v in mult],
                          textposition="outside"))
    c3.update_layout(title="Valuation multiples", yaxis_title="x")

    # --- assemble ---
    snap = tiles([("Market Cap", big(info.get("marketCap"))),
                  ("Price", f"${price:,.2f}"), ("Trailing P/E", rt(pe)),
                  ("Beta", rt(beta)), ("Dividend Yield", pct(dy)),
                  ("Analyst Target", f"${tgt:,.0f}" if tgt else "n/a")])
    val_rows = "".join(
        f"<tr><td>{k}</td><td>{rt(v)}</td></tr>" for k, v in mult)
    body = f"""<section class="hero"><div class="container">
<h1>{name} <span style="color:#8d8d8d">({ticker})</span></h1>
<p class="lede">{info.get('sector','')} &middot; {info.get('industry','')}</p>
<p class="asof">CFA-framework equity analysis &middot; data: Yahoo Finance</p>
</div></section><main class="container">
<section class="block"><h2>Snapshot</h2>{snap}</section>
<section class="block"><h2>Valuation</h2>
<div class="grid"><div class="tile chart"><div class="ch">{div(c3,ticker+'-mult')}</div></div>
<div class="tile" style="padding:16px 22px">
<table class="ptable"><thead><tr><th>Multiple</th><th>Value</th></tr></thead>
<tbody>{val_rows}</tbody></table>
<p style="font-size:13px;color:#525252;margin-top:14px">
<b>CAPM required return r</b> = {RF*100:.1f}% + &beta;&middot;{ERP*100:.1f}%
= <b>{r*100:.1f}%</b>.<br><b>Sustainable growth g</b> = ROE&middot;(1&minus;payout)
= <b>{pct(g)}</b>.<br><b>Justified trailing P/E</b> = payout&middot;(1+g)/(r&minus;g)
= <b>{rt(just_pe)}</b>.<br><b>Gordon DDM value</b> = {'$'+format(ddm,',.0f') if ddm else 'n/a (no dividend)'}.
</p></div></div></section>
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
<section class="block"><h2>Price History</h2>
<div class="tile chart"><div class="ch">{div(c1,ticker+'-px')}</div></div></section>
<section class="block"><h2>CFA View</h2>
<div class="scaled-note" style="border-left-color:#0f62fe">{verdict}</div></section>
</main>"""
    open(f"{DOCS}/stock_{ticker}.html", "w", encoding="utf-8").write(
        page(f"{ticker} — Equity Analysis", body))
    print(f"  {ticker}: P/E {rt(pe)}  ROE {pct(roe)}  -> stock_{ticker}.html")
    return {"ticker": ticker, "name": name, "sector": info.get("sector", ""),
            "pe": pe, "roe": roe, "price": price}

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

land = f"""<section class="hero"><div class="container">
<h1>Equity Research</h1>
<p class="lede">CFA-framework analysis of individual stocks &mdash;
profitability, DuPont, financial health, and relative &amp; absolute
valuation. A reusable tool: run it on any ticker.</p>
<p class="asof">Data: Yahoo Finance &middot; {len(existing)} companies analyzed</p>
</div></section><main class="container">
<section class="block"><h2>Companies</h2><div class="scards">{cards}</div></section>
{METHOD}</main>"""
open(f"{DOCS}/stocks.html", "w", encoding="utf-8").write(
    page("Equity Research — CFA-style Stock Analysis", land))
print(f"\nLanding page: stocks.html ({len(existing)} companies)")
