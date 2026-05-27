"""Shared site components: the navigation bar, the plain-language glossary,
and the currency badge. Imported by 17/18/19 so there is one source of truth.
"""

# --- navigation (single source of truth across all pages) ---
NAV = ('<nav><a href="index.html">Dashboard</a>'
       '<a href="report.html">Full Report</a>'
       '<a href="portfolio.html">Portfolio</a>'
       '<a href="strategies.html">Strategies</a>'
       '<a href="backtests.html">Backtests</a>'
       '<a href="stocks.html">Stock Analysis</a>'
       '<a href="signals.html">Stock Signals</a>'
       '<a href="regime.html">Regime Tracker</a>'
       '<a href="glossary.html">Glossary</a>'
       '<a href="index.html#about">About</a></nav>')


def ccy_badge(currency, note=""):
    """A small badge stating which currency the figures on this step are in."""
    extra = f" &middot; {note}" if note else ""
    return (f'<span class="ccy">Currency: <b>{currency}</b>{extra}</span>')


# --- glossary: plain-language definitions, grouped by area ---
# Each entry: (term, plain-English explanation -- no math, no jargon).
GLOSSARY = {
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
    by code; each value has name/color/rf/bn plus aligned dates/s(trategy)/b(ench)."""
    import os
    import pandas as pd
    H = os.path.expanduser("~")
    DEFS = {
        "SARS": ("Adaptive US Equity", "#0f62fe", 0.045, "S&P 500",
                 f"{H}/SARS/data/backtest/backtest_returns.csv", "SARS", "SP500"),
        "DUO":  ("Balanced Multi-strategy", "#8a3ffc", 0.045, "S&P 500",
                 f"{H}/DUO/data/duo_returns.csv", "DUO", "SPY"),
        "MARS": ("Defensive Multi-asset", "#b28600", 0.045, "S&P 500",
                 f"{H}/MARS/data/backtest/backtest_returns.csv", "MARS", "SP500"),
        "BARS": ("Mexican Equity Rotation", "#198038", 0.09, "IPC",
                 f"{H}/BARS/data/backtest/backtest_returns.csv", "BARS", "IPC"),
    }
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
