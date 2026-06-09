"""Shared site components: the navigation bar, the plain-language glossary,
and the currency badge. Imported by 17/18/19 so there is one source of truth.
"""

# --- navigation (single source of truth across all pages) ---
NAV = ('<nav><a href="index.html">Dashboard</a>'
       '<a href="report.html">Full Report</a>'
       '<a href="portfolio.html">Portfolio</a>'
       '<a href="strategies.html">Strategies</a>'
       '<a href="stocks.html">Stock Research</a>'
       '<a href="regime.html">Regime Tracker</a>'
       '<a href="projects.html">Projects</a>'
       '<a href="glossary.html">Glossary</a>'
       '<a href="index.html#about">About</a></nav>'
       """<script>document.addEventListener('DOMContentLoaded',function(){var p=(location.pathname.split('/').pop()||'index.html');document.querySelectorAll('nav a').forEach(function(a){if(a.getAttribute('href')===p)a.classList.add('active');});});</script>""")


def ccy_badge(currency, note=""):
    """A small badge stating which currency the figures on this step are in."""
    extra = f" &middot; {note}" if note else ""
    return (f'<span class="ccy">Currency: <b>{currency}</b>{extra}</span>')


# --- glossary: plain-language definitions, grouped by area ---
# Each entry: (term, plain-English explanation -- no math, no jargon).
GLOSSARY = {
    "Portfolio Accounting & FX": [
        ("Recycled 8M base",
         "The equity book is measured against a fixed $18,000,000 MXN starting "
         "pool, with capital recycled through it. Total Return = (today's total "
         "value &minus; 8M) &divide; 8M &mdash; not against the running cost of "
         "what we currently hold."),
        ("GBMF2 cash sleeve",
         "Cash from equity sales parks in the GBMF2 fund between trades, so it is "
         "counted as the equity book's cash: Total Value = holdings at market price "
         "+ GBMF2 cash. We use the real broker balance, never a reconstructed guess."),
        ("Undocumented MORE shares = a BUY",
         "If a holding grows with no matching trade ticket, we treat the extra "
         "shares as a purchase at the price implied by the broker's cost-basis "
         "column. It raises cost basis; it never counts as profit."),
        ("Undocumented FEWER shares = a SELL",
         "If a holding shrinks with no matching ticket, we treat the missing shares "
         "as a sale and book the gain or loss into Realized P/L, at the price "
         "implied by the change in the cost-basis column."),
        ("Realized vs Unrealized P/L",
         "Unrealized = how much our current holdings are worth above (or below) "
         "what we paid for them. Realized = gains already locked in as cash. "
         "Together they make total profit."),
        ("FX conversion",
         "One source for USD/MXN &mdash; Yahoo Finance's close on the as-of date "
         "&mdash; used identically everywhere on a page and shown to four decimals "
         "(e.g. 17.3201). Internal math keeps full precision."),
    ],
    "Returns & Valuation": [
        ("Expected return",
         "Our best estimate of how much an investment earns per year, on "
         "average, over the next 12 years. It is an estimate, not a promise."),
        ("Building-block model",
         "Instead of guessing returns from past performance, we add up the "
         "pieces that actually drive a return — income, growth, inflation and "
         "any change in how expensive the asset is."),
        ("Valuation reversion (the lambda dial)",
         "Expensive markets tend to cool off and cheap ones to catch up. "
         "'Lambda' is a dial from 0 to 1 setting how strongly we assume that "
         "happens — 0 = not at all, 1 = fully."),
        ("CAPE",
         "A way to judge how expensive a stock market is, comparing today's "
         "price to ten years of earnings so one unusual year doesn't distort "
         "it. A high CAPE means the market is expensive."),
        ("Dividend yield",
         "The cash a company pays its shareholders each year, as a percentage "
         "of the share price."),
        ("Buyback yield",
         "When a company buys back its own shares, each remaining share owns a "
         "bigger slice of the business — effectively another form of return."),
        ("Equity risk premium",
         "The extra return investors expect for holding stocks instead of "
         "safe government bonds, to compensate for the bumpier ride."),
        ("Base currency",
         "The currency every figure in a section is expressed in. Returns on "
         "foreign assets are converted into this currency."),
    ],
    "Risk": [
        ("Volatility",
         "How much an investment's value swings up and down. Higher volatility "
         "means a bumpier ride — bigger gains but also bigger drops."),
        ("Correlation",
         "Whether two investments tend to move together or apart. Things that "
         "move apart cushion each other; things that move together don't."),
        ("Diversification",
         "Spreading money across investments that don't all move the same way, "
         "so a bad patch in one is softened by others."),
        ("Ledoit-Wolf shrinkage",
         "A statistical clean-up step that makes the table of how assets move "
         "together more reliable, by pulling noisy estimates toward a sensible "
         "average."),
        ("Sharpe ratio",
         "How much return you get for the risk you take. Higher is better — "
         "more reward per unit of bumpiness."),
        ("Drawdown",
         "The drop from an investment's peak value to its low point — a "
         "measure of the worst stretch an investor would have lived through."),
    ],
    "Simulation": [
        ("Monte Carlo simulation",
         "Running tens of thousands of possible futures for an investment to "
         "see the whole range of where it could end up, not just one guess."),
        ("Market regime",
         "A stretch of time with a distinct mood — a 'calm' regime versus a "
         "'stress' regime where markets are jumpier and move together more."),
        ("Fat tails",
         "Real markets produce extreme good and bad outcomes more often than a "
         "simple bell curve suggests. Modelling 'fat tails' takes that "
         "seriously."),
        ("Percentile",
         "A way to describe a range of outcomes. The 5th percentile is a bad "
         "case (only 5% of outcomes are worse); the 95th is a good case."),
        ("CVaR (conditional value at risk)",
         "The average result across only the worst outcomes — a more honest "
         "picture of the downside than a single worst-case number."),
        ("Probability of loss",
         "The share of simulated futures in which the investment ends up worth "
         "less than it started."),
    ],
    "Markets & Rates": [
        ("Yield",
         "The annual income a bond pays, as a percentage of its price."),
        ("Yield curve",
         "Interest rates for bonds of different lengths, plotted together. Its "
         "shape hints at what the market expects the economy to do."),
        ("Forward rate",
         "The interest rate the market currently expects to apply in the "
         "future — read out of today's bond prices."),
        ("Breakeven inflation",
         "The rate of inflation the bond market is currently expecting, "
         "derived by comparing ordinary and inflation-protected bonds."),
        ("Basis point",
         "One hundredth of a percent (0.01%). A rate moving from 4.00% to "
         "4.25% has moved 25 basis points."),
        ("GPR — Geopolitical Risk index",
         "A measure built from newspaper text of how much geopolitical tension "
         "(wars, conflict) is in the news."),
        ("EPU — Economic Policy Uncertainty",
         "A newspaper-based measure of how uncertain government and central-"
         "bank policy looks right now."),
        ("Priced in",
         "Something the market already expects, so it is reflected in current "
         "prices. A forecast only matters where it differs from what's "
         "priced in."),
    ],
    "Stock Analysis": [
        ("P/E ratio",
         "Price-to-earnings: the share price divided by earnings per share. "
         "Roughly, how many years of profit you are paying for."),
        ("P/B ratio",
         "Price-to-book: the share price versus the company's accounting net "
         "worth per share."),
        ("EV/EBITDA",
         "Compares a company's whole value (including debt) to its cash "
         "earnings — a way to value firms regardless of how they're financed."),
        ("ROE — return on equity",
         "How much profit a company generates on the money its shareholders "
         "have invested. Higher is generally better."),
        ("ROA — return on assets",
         "How much profit a company generates on all the assets it controls."),
        ("DuPont decomposition",
         "Breaking ROE into its three causes — profit margin, how hard assets "
         "are worked, and borrowing — to see why a company earns what it "
         "earns."),
        ("Profit margin",
         "The share of every sales dollar that survives as profit."),
        ("CAPM — required return",
         "A standard way to estimate the return an investor should demand from "
         "a stock, given its risk: a safe rate plus a premium for risk."),
        ("DDM — dividend discount model",
         "Values a share as the worth, in today's money, of all the dividends "
         "it is expected to pay in the future."),
        ("Justified P/E",
         "The price-to-earnings ratio a company's fundamentals actually "
         "support. Comparing it to the real P/E shows if the market is "
         "optimistic or cautious."),
        ("Beta",
         "How much a stock tends to move when the whole market moves. Above 1 "
         "= more jumpy than the market; below 1 = steadier."),
        ("Intrinsic value",
         "What a share is worth based on its fundamentals — its earnings, "
         "cash flows and growth — regardless of what the market currently "
         "charges for it."),
        ("Synthesized target",
         "The average intrinsic-value estimate across several CFA valuation "
         "methods. Used here as a 12-month price target."),
        ("Justified P/B",
         "The price-to-book ratio that a company's profitability and growth "
         "actually support. Computed as (ROE − g) / (r − g)."),
        ("Two-stage DDM",
         "Values a dividend-paying share assuming dividends grow at a high "
         "rate (analyst-implied) for the next five years, then settle at a "
         "sustainable terminal rate forever. Avoids the single-stage model's "
         "pessimism on high-growth firms."),
        ("Two-stage FCFE",
         "Values a share as the present value of free cash flow to equity, "
         "growing at the near-term rate for five years and then at a terminal "
         "rate. The workhorse intrinsic-value model for firms with positive "
         "but volatile cash flow, including most non-dividend payers."),
        ("Stage-1 growth (g₁)",
         "The high-growth rate assumed for years 1–5 in a two-stage model. "
         "Sourced from analyst earnings-growth estimates and capped at 25% "
         "to keep projections sensible."),
        ("Terminal growth",
         "The long-run growth rate a mature company can sustain — typically "
         "capped near long-run nominal GDP (around 4–5%)."),
        ("Forecast cone",
         "The shaded range around a forward price path showing the ±1 "
         "standard-deviation band, given the stock's recent volatility."),
    ],
    "Portfolio": [
        ("Holding",
         "A single investment owned in the portfolio — one stock or fund."),
        ("Allocation (weight)",
         "How much of the portfolio is in a given holding, as a percentage."),
        ("Cost basis",
         "What was originally paid for a holding — the benchmark for measuring "
         "gain or loss."),
        ("Unrealized profit / loss",
         "The gain or loss on a holding that is still owned — it becomes real "
         "only when sold."),
    ],
}


# ============================================================================
# Interactive systematic-backtest widget (shared by 17_build_site & 23_strategies)
# ----------------------------------------------------------------------------
# One source of truth for: the OOS return series, the Python indicator engine
# (used to render the initial table server-side) and the client-side JS engine
# (re-indexes the growth-of-100 curves and recomputes every indicator from any
# user-chosen start date). Methodology stays proprietary — results only.
# ============================================================================

def bt_load():
    """Load the four strategies' monthly OOS return series. Returns a dict keyed
    by code; each value has name/color/rf/bn plus aligned dates/s(trategy)/b(ench).

    The raw series live in Carlos's private host strategy repos (~/SARS, ~/DUO, …),
    which are absent on a clean clone or the GitHub Actions runner. When the host
    CSVs are present (local builds) we read them; when they're absent (CI) we fall
    back to the series already embedded as window.BT_DATA in the previously-built,
    already-public docs/index.html. That keeps host + CI builds identical without
    committing any new data — the growth-of-100 series are public on the live site
    by design; tickers, logic and parameters never leave the host."""
    import os
    import pandas as pd
    H = os.path.expanduser("~")
    DEFS = {
        "SARS": ("Adaptive US Equity", "#0a2540", 0.045, "S&P 500",
                 f"{H}/SARS/data/backtest/backtest_returns.csv", "SARS", "SP500"),
        "DUO":  ("Balanced Multi-strategy", "#8a3ffc", 0.045, "S&P 500",
                 f"{H}/DUO/data/duo_returns.csv", "DUO", "SPY"),
        "MARS": ("Defensive Multi-asset", "#6b7280", 0.045, "S&P 500",
                 f"{H}/MARS/data/backtest/backtest_returns.csv", "MARS", "SP500"),
        "BARS": ("Mexican Equity Rotation", "#0a5d3a", 0.09, "IPC",
                 f"{H}/BARS/data/backtest/backtest_returns.csv", "BARS", "IPC"),
    }
    try:
        data = {}
        for k, (name, color, rf, bn, path, col, bcol) in DEFS.items():
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            s = df[col].dropna()
            b = df[bcol].dropna()
            idx = s.index.intersection(b.index).sort_values()
            data[k] = dict(name=name, color=color, rf=rf, bn=bn,
                           dates=[d.strftime("%Y-%m-%d") for d in idx],
                           s=[round(float(x), 8) for x in s.reindex(idx)],
                           b=[round(float(x), 8) for x in b.reindex(idx)])
        return data
    except (FileNotFoundError, OSError, KeyError):
        # CI / clean clone: private strategy repos absent. Recover the series from
        # the already-public docs/index.html (window.BT_DATA), built by the host.
        import re
        import json
        here = os.path.dirname(os.path.abspath(__file__))
        idx = os.path.join(os.path.dirname(here), "docs", "index.html")
        html = open(idx, encoding="utf-8").read()
        m = re.search(r"window\.BT_DATA=(\{.*?\});window\.BT_CFG=", html, re.S)
        if not m:
            raise RuntimeError("bt_load: no host series and no BT_DATA in docs/index.html")
        bt = json.loads(m.group(1))
        return {k: bt[k] for k in DEFS if k in bt}


def bt_common(data, keys=("SARS", "DUO", "MARS")):
    """Common (intersection) date window for the USD strategies, plus each
    strategy's returns and the shared S&P line aligned to it. Returns
    (common_dates, {code: strat_returns}, spy_returns)."""
    common = set(data[keys[0]]["dates"])
    for k in keys[1:]:
        common &= set(data[k]["dates"])
    common = sorted(common)
    aligned = {}
    for k in keys:
        m = dict(zip(data[k]["dates"], data[k]["s"]))
        aligned[k] = [m[d] for d in common]
    spym = dict(zip(data[keys[0]]["dates"], data[keys[0]]["b"]))
    spy = [spym[d] for d in common]
    return common, aligned, spy


def bt_g100(r):
    """Growth of 100 (first point = 100), matching nav/nav[0]*100."""
    import numpy as np
    nav = np.cumprod(1 + np.asarray(r, float))
    return list(nav / nav[0] * 100) if len(nav) else []


def bt_dd(r):
    """Drawdown series in percent (<=0)."""
    import numpy as np
    nav = np.cumprod(1 + np.asarray(r, float))
    peak = np.maximum.accumulate(nav)
    return list((nav / peak - 1) * 100) if len(nav) else []


def bt_indicators(s, b, rf):
    """Full professional indicator set over a return window. Mirrors the JS
    engine exactly so the server-rendered table matches the interactive one.
    Returns None when fewer than 6 observations."""
    import numpy as np
    s = np.asarray(s, float)
    b = np.asarray(b, float)
    n = len(s)
    if n < 6:
        return None
    ann = (1 + s).prod() ** (12 / n) - 1
    annb = (1 + b).prod() ** (12 / n) - 1
    vol = s.std(ddof=1) * np.sqrt(12)
    neg = s[s < 0]
    dvol = neg.std(ddof=1) * np.sqrt(12) if len(neg) > 1 else np.nan
    nav = np.cumprod(1 + s)
    peak = np.maximum.accumulate(nav)
    dd_ = nav / peak - 1
    mdd = dd_.min()
    var = b.var(ddof=1)
    beta = np.cov(s, b)[0, 1] / var if var > 0 else np.nan
    alpha = ann - (rf + beta * (annb - rf))
    te = (s - b).std(ddof=1) * np.sqrt(12)
    ir = (ann - annb) / te if te > 0 else np.nan
    up = (s[b > 0].mean() / b[b > 0].mean()) if (b > 0).any() else np.nan
    dn = (s[b < 0].mean() / b[b < 0].mean()) if (b < 0).any() else np.nan
    totret = (1 + s).prod() - 1
    posS = s[s > 0].sum()
    negS = s[s < 0].sum()
    omega = posS / (-negS) if negS < 0 else np.nan
    gtp = s.sum() / (-negS) if negS < 0 else np.nan
    ulcer = np.sqrt((dd_ ** 2).mean()) * 100
    recov = totret / abs(mdd) if mdd < 0 else np.nan
    m = s.mean()
    m2 = ((s - m) ** 2).mean()
    m3 = ((s - m) ** 3).mean()
    m4 = ((s - m) ** 4).mean()
    skew = m3 / m2 ** 1.5 if m2 > 0 else np.nan
    kurt = m4 / m2 ** 2 - 3 if m2 > 0 else np.nan
    var95 = np.percentile(s, 5)
    cv = s[s <= var95]
    cvar95 = cv.mean() if len(cv) else var95
    p95 = np.percentile(s, 95)
    p05 = np.percentile(s, 5)
    tail = abs(p95) / abs(p05) if p05 != 0 else np.nan
    under = nav < peak
    mx = cur = 0
    for u in under:
        if u:
            cur += 1
            mx = max(mx, cur)
        else:
            cur = 0
    return dict(ann_ret=ann, ann_vol=vol, sharpe=(ann - rf) / vol if vol else np.nan,
                sortino=(ann - rf) / dvol if dvol and not np.isnan(dvol) else np.nan,
                max_dd=mdd, calmar=ann / abs(mdd) if mdd else np.nan,
                win=(s > 0).mean(), best=s.max(), worst=s.min(), alpha=alpha,
                beta=beta, te=te, ir=ir, up_cap=up, dn_cap=dn, omega=omega,
                gtp=gtp, recov=recov, ulcer=ulcer, skew=skew, kurt=kurt,
                var95=var95, cvar95=cvar95, tail=tail, longdd=mx, n=n)


# Client-side engine: reads window.BT_DATA + window.BT_CFG, re-indexes the
# growth-of-100 curves and recomputes every indicator from the chosen start.
BT_JS = r"""(function(){
  if(!window.BT_DATA||!window.BT_CFG)return;
  var D=window.BT_DATA,CFG=window.BT_CFG,HP=(typeof Plotly!=="undefined");
  function sum(a){var s=0,i;for(i=0;i<a.length;i++)s+=a[i];return s;}
  function mean(a){return a.length?sum(a)/a.length:NaN;}
  function vari(a){if(a.length<2)return NaN;var m=mean(a),s=0,i;for(i=0;i<a.length;i++)s+=(a[i]-m)*(a[i]-m);return s/(a.length-1);}
  function std(a){return Math.sqrt(vari(a));}
  function cov(a,b){var ma=mean(a),mb=mean(b),s=0,i;for(i=0;i<a.length;i++)s+=(a[i]-ma)*(b[i]-mb);return s/(a.length-1);}
  function prod1p(a){var p=1,i;for(i=0;i<a.length;i++)p*=(1+a[i]);return p;}
  function navc(a){var o=[],p=1,i;for(i=0;i<a.length;i++){p*=(1+a[i]);o.push(p);}return o;}
  function g100(a){var n=navc(a);if(!n.length)return n;var b=n[0];return n.map(function(v){return v/b*100;});}
  function ddser(a){var n=navc(a),pk=-1e18,o=[],i;for(i=0;i<n.length;i++){if(n[i]>pk)pk=n[i];o.push((n[i]/pk-1)*100);}return o;}
  function maxdd(a){var n=navc(a),pk=-1e18,m=0,i,d;for(i=0;i<n.length;i++){if(n[i]>pk)pk=n[i];d=n[i]/pk-1;if(d<m)m=d;}return m;}
  function ulcer(a){var n=navc(a),pk=-1e18,ss=0,i,d;for(i=0;i<n.length;i++){if(n[i]>pk)pk=n[i];d=n[i]/pk-1;ss+=d*d;}return n.length?Math.sqrt(ss/n.length)*100:NaN;}
  function longdd(a){var n=navc(a),pk=-1e18,cur=0,mx=0,i;for(i=0;i<n.length;i++){if(n[i]>=pk){pk=n[i];cur=0;}else{cur++;if(cur>mx)mx=cur;}}return mx;}
  function pctile(a,p){if(!a.length)return NaN;var s=a.slice().sort(function(x,y){return x-y;});var idx=(s.length-1)*p,lo=Math.floor(idx),hi=Math.ceil(idx);return lo===hi?s[lo]:s[lo]+(s[hi]-s[lo])*(idx-lo);}
  function mom(a,k){var m=mean(a),s=0,i;for(i=0;i<a.length;i++)s+=Math.pow(a[i]-m,k);return s/a.length;}
  function skew(a){var m2=mom(a,2),m3=mom(a,3);return m2>0?m3/Math.pow(m2,1.5):NaN;}
  function exkurt(a){var m2=mom(a,2),m4=mom(a,4);return m2>0?m4/(m2*m2)-3:NaN;}
  function metrics(s,b,rf){
    var n=s.length,i;if(n<6)return null;
    var ann=Math.pow(prod1p(s),12/n)-1,annb=Math.pow(prod1p(b),12/n)-1;
    var vol=std(s)*Math.sqrt(12),neg=s.filter(function(x){return x<0;});
    var dvol=neg.length>1?std(neg)*Math.sqrt(12):NaN,mdd=maxdd(s);
    var vb=vari(b),beta=vb>0?cov(s,b)/vb:NaN,alpha=ann-(rf+beta*(annb-rf));
    var diff=[];for(i=0;i<n;i++)diff.push(s[i]-b[i]);
    var te=std(diff)*Math.sqrt(12),ir=te>0?(ann-annb)/te:NaN;
    var bp=[],bn=[],sp=[],sn=[];
    for(i=0;i<n;i++){if(b[i]>0){bp.push(b[i]);sp.push(s[i]);}else if(b[i]<0){bn.push(b[i]);sn.push(s[i]);}}
    var up=bp.length?mean(sp)/mean(bp):NaN,dn=bn.length?mean(sn)/mean(bn):NaN;
    var totret=prod1p(s)-1,posS=0,negS=0;
    for(i=0;i<n;i++){if(s[i]>0)posS+=s[i];else negS+=s[i];}
    var omega=negS<0?posS/(-negS):NaN,gtp=negS<0?sum(s)/(-negS):NaN;
    var recov=mdd<0?totret/(-mdd):NaN,v95=pctile(s,0.05);
    var cv=s.filter(function(x){return x<=v95;}),cvar=cv.length?mean(cv):v95;
    var p95=pctile(s,0.95),p05=pctile(s,0.05),tail=p05!==0?Math.abs(p95)/Math.abs(p05):NaN;
    var win=0;for(i=0;i<n;i++)if(s[i]>0)win++;
    return {ann_ret:ann,ann_vol:vol,sharpe:vol?(ann-rf)/vol:NaN,sortino:dvol?(ann-rf)/dvol:NaN,
      max_dd:mdd,calmar:mdd?ann/Math.abs(mdd):NaN,win:win/n,best:Math.max.apply(null,s),worst:Math.min.apply(null,s),
      alpha:alpha,beta:beta,te:te,ir:ir,up_cap:up,dn_cap:dn,omega:omega,gtp:gtp,recov:recov,ulcer:ulcer(s),
      skew:skew(s),kurt:exkurt(s),var95:v95,cvar95:cvar,tail:tail,longdd:longdd(s),n:n};
  }
  var _common=null;
  function commonDates(){
    if(_common)return _common;
    var base=D.SARS.dates.slice();
    ["DUO","MARS"].forEach(function(k){var set={};D[k].dates.forEach(function(d){set[d]=1;});base=base.filter(function(d){return set[d];});});
    base.sort();_common=base;return base;
  }
  var _maps={};
  function asMap(k){if(_maps[k])return _maps[k];var m={},i;for(i=0;i<D[k].dates.length;i++)m[D[k].dates[i]]=i;_maps[k]=m;return m;}
  function alignRets(k,dates){var m=asMap(k),sa=[],ba=[],i,j;for(i=0;i<dates.length;i++){j=m[dates[i]];sa.push(D[k].s[j]);ba.push(D[k].b[j]);}return {s:sa,b:ba};}
  function idxFrom(dates,start){var i=0;while(i<dates.length&&dates[i]<start)i++;return i;}
  function fp(x){return isFinite(x)?(x*100).toFixed(1)+"%":"—";}
  function fps(x){return isFinite(x)?(x>=0?"+":"")+(x*100).toFixed(1)+"%":"—";}
  function fn(x,d){return isFinite(x)?x.toFixed(d===undefined?2:d):"—";}
  var FMT={ann_ret:fp,ann_vol:fp,max_dd:fp,win:fp,te:fp,var95:fp,cvar95:fp,best:fps,worst:fps,alpha:fps,
    sharpe:fn,sortino:fn,calmar:fn,beta:fn,ir:fn,up_cap:fn,dn_cap:fn,omega:fn,gtp:fn,recov:fn,skew:fn,kurt:fn,tail:fn,
    ulcer:function(x){return isFinite(x)?x.toFixed(1)+"%":"—";},
    longdd:function(x){return isFinite(x)?x+" m":"—";}};
  function setCell(k,key,t){var el=document.getElementById(CFG.cellPrefix+"_"+k+"_"+key);if(el)el.textContent=t;}
  function updateCharts(start){
    var cd=commonDates().filter(function(d){return d>=start;});
    if(HP&&CFG.eq&&document.getElementById(CFG.eq)){
      var xs=[],ys=[];
      ["SARS","DUO","MARS"].forEach(function(k){var a=alignRets(k,cd);xs.push(cd);ys.push(g100(a.s));});
      var sp=alignRets("SARS",cd);xs.push(cd);ys.push(g100(sp.b));
      Plotly.restyle(CFG.eq,{x:xs,y:ys},[0,1,2,3]);
      Plotly.relayout(CFG.eq,{"xaxis.autorange":true,"yaxis.autorange":true});
    }
    if(HP&&CFG.dd&&document.getElementById(CFG.dd)){
      var dx=[],dy=[];
      ["SARS","DUO","MARS"].forEach(function(k){var a=alignRets(k,cd);dx.push(cd);dy.push(ddser(a.s));});
      var s2=alignRets("SARS",cd);dx.push(cd);dy.push(ddser(s2.b));
      Plotly.restyle(CFG.dd,{x:dx,y:dy},[0,1,2,3]);
      Plotly.relayout(CFG.dd,{"xaxis.autorange":true,"yaxis.autorange":true});
    }
    if(HP&&CFG.bars&&document.getElementById(CFG.bars)){
      var i0=idxFrom(D.BARS.dates,start),bd=D.BARS.dates.slice(i0),bs=D.BARS.s.slice(i0),bb=D.BARS.b.slice(i0);
      Plotly.restyle(CFG.bars,{x:[bd,bd],y:[g100(bs),g100(bb)]},[0,1]);
      Plotly.relayout(CFG.bars,{"xaxis.autorange":true,"yaxis.autorange":true});
    }
  }
  function updateTable(start){
    CFG.cols.forEach(function(k){
      var s,b,ds;
      if(k!=="BARS"&&CFG.mode==="common"){var cd=commonDates().filter(function(d){return d>=start;});var a=alignRets(k,cd);s=a.s;b=a.b;ds=cd;}
      else{var i0=idxFrom(D[k].dates,start);s=D[k].s.slice(i0);b=D[k].b.slice(i0);ds=D[k].dates.slice(i0);}
      var m=metrics(s,b,D[k].rf);
      CFG.rows.forEach(function(key){setCell(k,key,m?FMT[key](m[key]):"—");});
      var w=document.getElementById(CFG.cellPrefix+"_"+k+"_window");
      if(w)w.textContent=ds.length?ds[0].slice(0,4)+"–"+ds[ds.length-1].slice(0,4)+" ("+ds.length+"m)":"—";
    });
  }
  function buildAxis(){
    if(CFG.axisCommon)return commonDates().slice();
    var set={};CFG.cols.forEach(function(k){if(D[k])D[k].dates.forEach(function(d){set[d]=1;});});
    var ax=Object.keys(set);ax.sort();return ax;
  }
  var AXIS=buildAxis(),LAST=AXIS[AXIS.length-1];
  function apply(start){
    updateCharts(start);updateTable(start);
    var lbl=document.getElementById(CFG.label);
    if(lbl){var mp=start.split("-"),MN=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],mon=MN[parseInt(mp[1],10)-1]+" "+mp[0];
      var yrs=(new Date(LAST+"T00:00:00")-new Date(start+"T00:00:00"))/(365.25*864e5);
      lbl.textContent="From "+mon+" · "+yrs.toFixed(1)+"y";}
  }
  function yearsAgoIdx(n){var p=LAST.split("-");
    var iso=(parseInt(p[0],10)-n)+"-"+p[1]+"-"+p[2],i=0;while(i<AXIS.length&&AXIS[i]<iso)i++;return Math.min(i,AXIS.length-1);}
  function init(){
    var sl=document.getElementById(CFG.slider);
    var rb=document.querySelectorAll("[data-bt-range][data-bt-group='"+CFG.group+"']");
    function clearOn(){for(var j=0;j<rb.length;j++)rb[j].classList.remove("on");}
    if(sl){sl.min=0;sl.max=AXIS.length-1;sl.step=1;sl.value=0;
      sl.addEventListener("input",function(){apply(AXIS[+sl.value]);clearOn();});}
    for(var i=0;i<rb.length;i++){(function(btn){btn.addEventListener("click",function(){
      var r=btn.getAttribute("data-bt-range"),idx=r==="all"?0:yearsAgoIdx(parseInt(r,10));
      if(sl)sl.value=idx;apply(AXIS[idx]);clearOn();btn.classList.add("on");
    });})(rb[i]);}
    apply(AXIS[0]);
  }
  if(document.readyState!=="loading")init();else document.addEventListener("DOMContentLoaded",init);
})();"""


# ============================================================================
# Shared backtest-catalog card renderer.
# Single source of truth for the strategy cards shown on BOTH backtests.html
# (24_backtests.py — full curated showcase) and strategies.html (23_strategies.py
# — the validated building blocks behind the live regime-adaptive book). Both
# read the same canonical catalog (Trading_Index hub -> committed repo fallback)
# and the same card markup, so a metric only ever lives in one place.
# ============================================================================
_BT_HUB = ["/mnt/c/Users/carlo/Trading_Index/strategies.json",
           r"C:\Users\carlo\Trading_Index\strategies.json"]


def _bt_resolve(p):
    """First existing form of a path: raw (native Windows) then /mnt-mapped (WSL)."""
    import os
    if not p:
        return None
    if len(p) > 2 and p[1] == ":" and p[2] in "\\/":
        alt = "/mnt/" + p[0].lower() + "/" + p[3:].replace("\\", "/")
    else:
        alt = p.replace("\\", "/")
    for cand in (p, alt):
        if cand and os.path.exists(cand):
            return cand
    return None


def bt_catalog():
    """Load the canonical backtest catalog: Trading_Index hub first (where Carlos
    edits), else the committed repo fallback so a clean clone / CI still builds."""
    import os
    import json
    here = os.path.dirname(os.path.abspath(__file__))
    fb = os.path.join(os.path.dirname(here), "data", "backtests_strategies.json")
    for cand in _BT_HUB + [fb]:
        rp = _bt_resolve(cand)
        if rp:
            with open(rp, encoding="utf-8") as fh:
                return json.load(fh)
    return {"strategies": []}


BT_BADGE = {"green": ("Deployable", "#0a5d3a"),
            "yellow": ("Ensemble component", "#6b7280"),
            "red": ("Pass / no edge", "#7c2d12")}

_BT_ROW = [("best_raw_sharpe", "Raw Sharpe"), ("dsr", "DSR"), ("pbo", "PBO"),
           ("max_dd_pct", "Max DD"), ("cagr_pct", "CAGR")]


def _bt_esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bt_fmt(key, val):
    if val is None:
        return "n/a", "na"
    if isinstance(val, str):
        return val, ("na" if val.strip().lower() in ("n/a", "na", "") else "")
    if key in ("max_dd_pct", "cagr_pct"):
        return f"{val:+.1f}%", ("neg" if val < 0 else "")
    return f"{val:.2f}", ("neg" if isinstance(val, (int, float)) and val < 0 else "")


# Some entries (ensembles) store the headline Sharpe/PBO under richer keys
# (e.g. static_drift_weights: sharpe / pbo_structural) rather than the single-
# strategy fields, so the card falls back to those before showing "n/a".
_BT_ALT = {"best_raw_sharpe": "sharpe", "pbo": "pbo_structural"}


def _km_get(km, k):
    if k in km:
        return km[k]
    alt = _BT_ALT.get(k)
    return km.get(alt) if alt else None


# ── confidentiality discipline (public site) ────────────────────────────────
# Performance metrics are scale-invariant and publishable (Sharpe/DSR/PBO/DD/CAGR);
# tickers, asset universes, entry/exit logic, parameter values and internal paths
# are NOT. Card titles + descriptions for the public entries are curated below;
# anything not curated falls through the regex redactor as a backstop so a future
# public entry can never leak verbatim. (Carlos, 2026-06-04 — same restraint as the
# x1.8 portfolio scaling.) The allowed exception is the headline weight ratio
# (e.g. "50/30/20"), which Carlos has cleared for display.
import re as _re

_BT_TICKERS = (r"SPY|QQQ|IEF|GLD|XAUUSD|XAGUSD|EURUSD|USDJPY|GBPUSD|EURJPY|GBPJPY|"
               r"EFA|EEM|DIA|IWM|EWW|DBC|XLK|XLF|SLV|NAFTRAC|SOXX|VGT|VUG|DBMF|IShares")
_BT_REDACT = [
    # ticker runs (SPY/QQQ/EFA, SPY+QQQ+EFA, "SPY, IEF, GLD") -> [assets]
    (_re.compile(r"\b(?:%s)(?:\s*[/+,&-]\s*(?:%s))*\b" % (_BT_TICKERS, _BT_TICKERS)),
     "[assets]"),
    (_re.compile(r"\b\d{2,3}-?\s?EMA\b|\bSMA-?\d{2,3}\b"), "[trend filter]"),
    (_re.compile(r"\b\d+(?:\.\d+)?\s?sigma\b|\bATR\s?[x×]?\s?\d+(?:\.\d+)?\b"), "[threshold]"),
    (_re.compile(r"\b\d+R\b"), "[target]"),
    (_re.compile(r"\b[a-z_]{3,}\s?=\s?-?\d+(?:\.\d+)?\b"), "[param]"),
    (_re.compile(r"\b\d+m lookback\b|\blookback[ =]\d+\b", _re.I), "[lookback]"),
    # bar-window lookback params: "30/60/120-bar", "150-bar", "20-day" sign filter
    (_re.compile(r"\b\d{1,3}(?:/\d{1,3})+-?\s?(?:bar|day|d)\b", _re.I), "[lookback]"),
    (_re.compile(r"\b\d{2,3}-?\s?(?:bar|day)\s?(?:sign|sma|ema|filter|window|lookback)\b", _re.I),
     "[lookback]"),
    (_re.compile(r"Trading_Index|SignalLib|/home/\S+|[Cc]:\\\\Users\S*|Downloads\S*|"
                 r"/mnt/\S+|REPORT\.md", _re.I), "[internal]"),
]


def _bt_redact(text):
    """Backstop redactor for any non-curated public text (defence in depth)."""
    if not text:
        return text
    for rx, repl in _BT_REDACT:
        text = rx.sub(repl, text)
    return _re.sub(r"\[assets\](?:\s*[/+,&-]?\s*\[assets\])+", "[assets]", text)


# Curated public-safe (name, what_it_tests, verdict) for each public entry. Keeps
# the thesis, verdict and all performance metrics; drops tickers, universe lists,
# entry/exit mechanics, sleeve compositions and parameter values.
_BT_PUBLIC = {
    "buy_the_dip": (
        "Buy-the-Dip / Sell-the-Rip",
        "Daily pullback-in-uptrend: buy weakness while a long-term trend filter is "
        "positive, optionally fade rips in downtrends, across a broad diversified "
        "index-ETF universe. 2010–2026.",
        "Robust, low-drawdown S&P replacement — the edge is structural (positive across "
        "most of the parameter space), not curve-fit. Deploy as a diversified ensemble: "
        "a low-drawdown core, not a return amplifier. DSR 0.60–0.80, PBO 0.37–0.48; "
        "roughly 2× the S&P's Calmar at a fraction of its drawdown."),
    "static_diversification": (
        "Static Multi-Asset Diversification",
        "An equal-weight, low-turnover blend across three asset classes (equity, "
        "intermediate government bonds, gold), rebalanced periodically, with an optional "
        "trend-based cash filter. 2011–2026.",
        "The static blend beat every rotation variant tested: Sharpe 1.00, DSR 0.96, "
        "near-zero turnover, and it beats the S&P on Sharpe, Calmar and drawdown. Deploy "
        "as a low-cost diversified core; the trend filter is an optional crash overlay."),
    "crt": (
        "Candle Range Theory (CRT) + Regime Filter",
        "A three-candle range-reversal pattern gated by a daily long-term trend filter, "
        "tested vanilla and with regime overlays across several FX and metals markets. "
        "2016–2026.",
        "A thin but real edge once trend-gated — PF 1.22, Sharpe 0.59, Calmar 0.33 — "
        "usable as one signal inside the regime-adaptive ensemble, never standalone. "
        "(Ungated it had no post-cost edge.)"),
    "static_drift_weights": (
        "Static Drift-Weight 50/30/20 — GFC-tested",
        "Fixed 50/30/20 allocation across three validated sleeves (an equity trend "
        "ensemble / a static multi-asset blend / a regime overlay), rebalanced monthly, "
        "with no regime gating and no kill switch. Packaged after the gated capstone "
        "showed this simpler version dominates it.",
        "Deployable — GFC-tested. Sharpe 1.33, MaxDD -3.92%, CAGR 5.06% over 194 months "
        "(16.2y). Extended 21-year test including the 2008 GFC passes the 10% drawdown bar "
        "at -9.85% with headroom. Beats the S&P on Sharpe (1.33 vs 1.00) and at matched "
        "risk. Held-out 2025+ Sharpe 1.95; a +50% cost shock only trims Sharpe to 1.28. "
        "A sleep-better risk-reduction product, not an alpha amplifier."),
}


def _bt_public(strat):
    """Return confidentiality-safe (name, what_it_tests, verdict_line) for a card."""
    cur = _BT_PUBLIC.get(strat.get("key"))
    if cur:
        return cur
    return (_bt_redact(strat.get("short_name") or strat.get("name", "")),
            _bt_redact(strat.get("what_it_tests", "")),
            _bt_redact(strat.get("verdict_line", "")))


def bt_card(strat, report_link=None, xref=""):
    """Render one strategy as a card. report_link -> "Full report" anchor;
    xref -> an optional cross-reference line (e.g. deployment status / sibling page).
    Name/description/verdict are routed through the confidentiality filter."""
    badge = strat.get("badge", "red")
    label = strat.get("verdict") or BT_BADGE.get(badge, ("", ""))[0]
    pname, ptests, pverd = _bt_public(strat)
    km = strat.get("key_metrics", {})
    tiles = ""
    for k, lbl in _BT_ROW:
        txt, cls = _bt_fmt(k, _km_get(km, k))
        tiles += (f'<div class="bt-m"><div class="bt-mv {cls}">{_bt_esc(txt)}</div>'
                  f'<div class="bt-mk">{lbl}</div></div>')
    dates = strat.get("dates", {})
    run, span = dates.get("run", ""), dates.get("data_span", "")
    link = (f'<a class="bt-link" href="{report_link}">Full report &rarr;</a>'
            if report_link else '<span class="bt-span">report on local disk</span>')
    xr = f'<p class="bt-xref">{xref}</p>' if xref else ""
    return (
        f'<article class="btcard bt-{badge}">'
        f'<div class="bt-head"><span class="bt-badge bt-{badge}">{_bt_esc(_bt_redact(label))}</span>'
        f'<span class="bt-date">{_bt_esc(run)}</span></div>'
        f'<h3 class="bt-name">{_bt_esc(pname)}</h3>'
        f'<p class="bt-tests">{_bt_esc(ptests)}</p>'
        f'<div class="bt-metrics">{tiles}</div>'
        f'<p class="bt-verdict">{_bt_esc(pverd)}</p>'
        f'{xr}'
        f'<div class="bt-foot"><span class="bt-span">{_bt_esc(span)}</span>{link}</div>'
        f'</article>')


# Card/badge/grid CSS — shared so both pages render identical cards. (Page-layout
# CSS like the methodology box stays local to 24_backtests.py.)
BT_CARD_CSS = r"""
.btgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1.5rem}
.btcard{background:#fff;border:1px solid #e5e5e5;border-top:3px solid #d4d4d4;
padding:24px 24px 20px;box-shadow:none;display:flex;flex-direction:column;transition:background .15s ease-out}
.btcard:hover{background:rgba(10,37,64,.045)}
.btcard.bt-green{border-top-color:#0a5d3a}
.btcard.bt-yellow{border-top-color:#6b7280}
.btcard.bt-red{border-top-color:#7c2d12}
.bt-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
.bt-badge{font-size:10.5px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;
color:#fff;padding:4px 10px;border-radius:0}
.bt-badge.bt-green{background:#0a5d3a}
.bt-badge.bt-yellow{background:#6b7280}
.bt-badge.bt-red{background:#7c2d12}
.bt-date{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:11.5px;color:#888}
.bt-name{font-family:'Spectral',Georgia,serif;font-size:19px;font-weight:500;color:#111;margin:0 0 6px;line-height:1.25}
.bt-tests{font-size:13px;color:#555;line-height:1.5;margin:0 0 16px}
.bt-metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:0;background:none;
border:1px solid #e5e5e5;margin-bottom:16px}
.bt-m{background:#fff;padding:11px 8px;text-align:center;border-right:1px solid #e5e5e5}
.bt-m:last-child{border-right:0}
.bt-mv{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:16px;font-weight:500;color:#111;letter-spacing:-.01em}
.bt-mv.neg{color:#7c2d12}.bt-mv.na{color:#888}
.bt-mk{font-size:9.5px;color:#888;margin-top:4px;letter-spacing:.06em;text-transform:uppercase}
.bt-verdict{font-size:13.5px;color:#333;line-height:1.55;margin:0 0 18px;flex:1}
.bt-xref{font-size:12.5px;color:#0a2540;line-height:1.5;margin:0 0 14px;
border-left:2px solid rgba(10,37,64,.20);padding-left:12px}
.bt-xref a{color:#0a2540;font-weight:500}
.bt-foot{display:flex;justify-content:space-between;align-items:center;gap:10px;
border-top:1px solid #e5e5e5;padding-top:14px}
.bt-span{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:11px;color:#888}
.bt-link{color:#0a2540;text-decoration:none;font-size:13px;font-weight:500;white-space:nowrap}
.bt-link:hover{text-decoration:underline}
@media(max-width:560px){.bt-metrics{grid-template-columns:repeat(3,1fr)}.bt-m:nth-child(3n){border-right:0}}
"""
