"""Merged Stocks page (docs/stocks.html) — combines the former Stock Analysis and
Stock Signals pages into one, led by a reproducible COMPOSITE PICKER.

Sections, in order:
  1. Composite Picks — every numeric variable from BOTH pipelines (CFA/Buffett
     fundamentals + macro-signal sensitivities), z-scored, weighted by each
     variable's correlation with realised forward returns, ranked. Top 20 = picks.
     Status pills: All / Buy candidates / Watch list.
  2. Macro Factor Signals — the former signals.html content (β to rates/dollar/CAD,
     post-FOMC drift) for the same universe.
  3. Per-company CFA reports — links to the stock_<TICKER>.html tool pages.

Picker internals (the variable WEIGHTS) stay in picker.py and are never rendered;
the cards show the ranked result + each pick's variable contributions only.
"""
import os, json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from glossary import NAV, ccy_badge
import picker

from paths import DOCS_S as DOCS  # repo-anchored (2026-06-10)
ANA = picker.ANA
INK, BLUE, GOLD, GREEN, RED, GREY = "#111111", "#0a2540", "#6b7280", "#0a5d3a", "#7c2d12", "#888888"
PLOTLY = "https://cdn.plot.ly/plotly-2.35.0.min.js"
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">')
SECTOR_C = {
    "Technology": "#0a2540", "Consumer Cyclical": "#6b7280",
    "Communication Services": "#8a3ffc", "Healthcare": "#0a5d3a",
    "Financial Services": "#009d9a", "Consumer Defensive": "#fa4d56",
    "Energy": "#7c2d12", "Industrials": "#555555",
}
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


# ---------------------------------------------------------------- commentary
# Deterministic, template-driven 1-liner from the dominant signed contributors.
# No model judgement — fully reproducible from the contribution vector.
_POS = {
    "roe": "high quality (ROE)", "gross_marg": "fat gross margins",
    "fcf_yield": "strong free-cash-flow yield", "net_marg": "wide net margins",
    "mos": "a positive margin of safety", "buffett": "a high quality score",
    "rev_growth": "fast revenue growth", "eps_growth": "fast earnings growth",
    "inv_de": "a clean balance sheet", "mom_12_1": "price momentum",
    "inv_pe": "a cheap earnings multiple", "inv_fwd_pe": "a cheap forward multiple",
    "beta_rates": "rate-tailwind positioning", "beta_dxy": "dollar-tailwind positioning",
    "beta_cad": "favourable cross-FX beta", "r2": "high macro explainability",
}
_NEG = {
    "roe": "weak ROE", "gross_marg": "thin gross margins",
    "fcf_yield": "low cash yield", "net_marg": "thin net margins",
    "mos": "a stretched valuation", "buffett": "a low quality score",
    "rev_growth": "slow revenue growth", "eps_growth": "slow earnings growth",
    "inv_de": "elevated leverage", "mom_12_1": "weak momentum",
    "inv_pe": "a rich earnings multiple", "inv_fwd_pe": "a rich forward multiple",
    "beta_rates": "rate-headwind exposure", "beta_dxy": "dollar-headwind exposure",
    "beta_cad": "adverse cross-FX beta", "r2": "noisy macro fit",
}


def commentary(cs):
    pos = cs[cs > 0].sort_values(ascending=False)
    neg = cs[cs < 0].sort_values()
    parts = []
    if len(pos):
        lead = [_POS[k] for k in pos.index[:2]]
        parts.append("Driven by " + " and ".join(lead))
    if len(neg):
        parts.append("offset by " + _NEG[neg.index[0]])
    return ("; ".join(parts) + ".") if parts else "Balanced across signals."


def chips(cs, n=5):
    """Top-n contributors by |magnitude| as +/- chips — direction + relative
    bar, NO weight values (confidentiality)."""
    top = cs.reindex(cs.abs().sort_values(ascending=False).index)[:n]
    mx = cs.abs().max() or 1.0
    out = ""
    for k, v in top.items():
        cls = "cpos" if v >= 0 else "cneg"
        w = max(8, int(round(abs(v) / mx * 46)))
        out += (f'<span class="chip {cls}" title="{picker.FLABEL[k]} '
                f'({"+" if v>=0 else "-"})"><span class="chip-b" style="width:{w}px"></span>'
                f'{picker.FLABEL[k]}</span>')
    return out


def picks_section(df, meta):
    contrib = meta["contrib"]
    rows = ""
    for tk, r in df.iterrows():
        cs = contrib.loc[tk]
        rank = int(r["rank"])
        is_pick = rank <= 20
        status = "buy" if r["composite"] > 0 else "watch"
        sec = str(r["sector"]) or "—"
        color = SECTOR_C.get(sec, GREY)
        comp_cls = "pos" if r["composite"] >= 0 else "neg"
        star = ' <span class="pick-star" title="Top-20 pick">★</span>' if is_pick else ""
        rows += (
            f'<tr data-status="{status}" data-pick="{1 if is_pick else 0}">'
            f'<td class="rk">{rank}</td>'
            f'<td><b>{tk}</b>{star}<br><span class="tn">{str(r["name"])[:30]}</span></td>'
            f'<td><span class="sec" style="background:{color}">{sec.replace(" Services","")}</span></td>'
            f'<td class="num">${r["price"]:,.2f}</td>'
            f'<td class="num {comp_cls}"><b>{r["composite"]:+.3f}</b></td>'
            f'<td class="chips">{chips(cs)}</td>'
            f'<td class="cmt">{commentary(cs)}</td></tr>')
    n_buy = int((df["composite"] > 0).sum())
    note = ("equal-weight z-score (no forward-return history)" if meta["equal_weight_fallback"]
            else "weighted by each variable's correlation with realised forward returns")
    return f"""<section class="block" id="picks">
<h2>Composite Picks</h2>
<p class="note">Every numeric variable from <b>both</b> stock pipelines — CFA/Buffett
fundamentals (ROE, margins, FCF yield, margin of safety, growth, leverage, 12-1
momentum) and macro-signal sensitivities (earnings yield, β to rates / dollar / CAD,
macro R²) — is z-scored across the {meta['n_universe']}-name universe, then combined
into one composite score per ticker, {note}. The variable <i>direction</i> is set by
that correlation, not hand-picked. Tickers are ranked; the top 20 (★) are the picks.
Each row shows the variables that contributed most (direction + relative size); the
underlying weights are proprietary. Educational research on the public universe — not
advice, and not a statement of any holding.</p>
<div class="pills" data-group="picks">
  <button class="pill on" data-f="all">All ({meta['n_universe']})</button>
  <button class="pill" data-f="buy">Buy candidates ({n_buy})</button>
  <button class="pill" data-f="watch">Watch list ({meta['n_universe']-n_buy})</button>
  <button class="pill" data-f="pick">Top-20 picks</button>
</div>
<div class="tile" style="padding:0 14px 8px;overflow-x:auto">
<table class="ptable picks"><thead><tr>
<th>#</th><th>Ticker</th><th>Sector</th><th>Price</th><th>Composite</th>
<th>Top contributing variables</th><th>Commentary</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="note" style="font-size:11.5px">Forward-return proxy for the weight
derivation: mean realised 5-trading-day return after each FOMC decision per ticker
(the available forward-return history; {meta['target_coverage']}/40 names covered).
Composite weights are derived, not chosen, and recomputed on every build.</p>
</section>"""


def signals_section():
    sens = pd.read_parquet(f"{ANA}/stock_sensitivities.parquet").copy()
    fomc = pd.read_parquet(f"{ANA}/stock_fomc_reaction.parquet")
    sens["abs_rates"] = sens["beta_rates"].abs()
    sens = sens.sort_values("abs_rates", ascending=False)
    sens["sector_short"] = sens["sector"].fillna("Other").str.replace(" Services", "")

    def cell_beta(beta, t):
        cls = "pos" if beta > 0 else ("neg" if beta < 0 else "")
        bold = "font-weight:600" if abs(t) > 2 else ""
        return (f'<td class="num {cls}" style="{bold}">{beta:+.3f}'
                f'<br><span class="tn">t={t:+.1f}</span></td>')

    sens_rows = ""
    for _, r in sens.iterrows():
        color = SECTOR_C.get(r["sector"], GREY)
        sens_rows += (
            f'<tr><td>{r["ticker"]}</td>'
            f'<td><span class="sec" style="background:{color}">{r["sector_short"]}</span></td>'
            f'<td class="num">${r["marketcap_B"]:,.0f}B</td>'
            f'<td class="num">{r["pe"]:,.1f}</td><td class="num">{r["fwd_pe"]:,.1f}</td>'
            f'{cell_beta(r["beta_rates"], r["t_rates"])}'
            f'{cell_beta(r["beta_dxy"], r["t_dxy"])}'
            f'{cell_beta(r["beta_cad"], r["t_cad"])}'
            f'<td class="num">{r["r2"]*100:.1f}%</td></tr>')

    f1 = go.Figure()
    for sec, g in sens.groupby("sector"):
        f1.add_scatter(x=g["beta_rates"], y=g["beta_dxy"], mode="markers+text",
                       text=g["ticker"], textposition="top center", textfont=dict(size=9),
                       marker=dict(color=SECTOR_C.get(sec, GREY), size=12,
                                   line=dict(color="white", width=1)), name=sec)
    f1.add_hline(y=0, line=dict(color=GREY, width=0.5))
    f1.add_vline(x=0, line=dict(color=GREY, width=0.5))
    f1.update_layout(title="Macro factor exposures — β to 10Y rates vs β to dollar (DXY)",
                     xaxis_title="β to 10Y yield change (per 1pp)",
                     yaxis_title="β to DXY % change", legend=dict(orientation="h", y=-0.18))

    pivot = fomc.groupby(["ticker", "decision"])["fwd5"].mean().unstack("decision")
    counts = fomc.groupby(["ticker", "decision"])["fomc"].count().unstack("decision")
    overall = fomc.groupby("ticker")["fwd5"].mean().sort_values(ascending=False)
    pivot = pivot.reindex(overall.index); counts = counts.reindex(overall.index)
    fomc_rows = ""
    for tk in pivot.index:
        cells = []
        for dec in ["Cut", "Hold", "Hike"]:
            if dec in pivot.columns and not pd.isna(pivot.loc[tk, dec]):
                v = pivot.loc[tk, dec]; n = int(counts.loc[tk, dec])
                cls = "pos" if v >= 0 else "neg"
                cells.append(f'<td class="num {cls}">{v*100:+.2f}%<br><span class="tn">n={n}</span></td>')
            else:
                cells.append('<td class="num" style="color:#888">—</td>')
        o = overall[tk]; cls_o = "pos" if o >= 0 else "neg"
        cells.append(f'<td class="num {cls_o}" style="font-weight:600">{o*100:+.2f}%</td>')
        fomc_rows += f"<tr><td>{tk}</td>{''.join(cells)}</tr>"

    return f"""<section class="block" id="signals">
<h2>Macro Factor Signals</h2>
<p class="note">The former Stock Signals page, folded in here: each name's macro
factor exposures (β to the 10-year yield, the dollar, USDCAD) and its post-FOMC
drift. These same variables feed the composite above. Bold β cells have a
t-statistic above 2 (significant). Definitions in the
<a href="glossary.html">Glossary</a>.</p>
<div class="tile chart"><div class="ch">{div(f1, "sens-scatter")}</div></div>
<h3>Sensitivities (sorted by |β to rates|)</h3>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto;margin-bottom:18px">
<table class="ptable"><thead><tr>
<th>Ticker</th><th>Sector</th><th>Mkt Cap</th><th>P/E</th><th>Fwd P/E</th>
<th>β rates</th><th>β DXY</th><th>β USDCAD</th><th>R²</th></tr></thead>
<tbody>{sens_rows}</tbody></table></div>
<h3>Post-FOMC reaction (avg 5-day forward return by decision)</h3>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable"><thead><tr>
<th>Ticker</th><th>Cut</th><th>Hold</th><th>Hike</th><th>Overall</th></tr></thead>
<tbody>{fomc_rows}</tbody></table></div>
</section>""", len(sens), int(pivot.shape[0])


def companies_section():
    import glob
    existing = sorted(os.path.basename(f)[6:-5] for f in glob.glob(f"{DOCS}/stock_*.html"))
    cards = "".join(
        f'<a class="scard" href="stock_{tk}.html"><div class="sc-t">{tk}</div>'
        f'<div class="sc-n">CFA report &rarr;</div></a>' for tk in existing)
    return f"""<section class="block" id="companies">
<h2>Per-company CFA reports</h2>
<p class="note">Full CFA-framework equity analysis (profitability, DuPont,
financial health, relative &amp; absolute valuation) for the analyzed names. The
Buffett-style value screen over the full S&amp;P 500 remains available via the
per-company tool.</p>
<div class="scards">{cards}</div></section>"""


PAGE_CSS = r"""
.pills{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 18px}
.pill{font:500 12px 'Inter',sans-serif;letter-spacing:.02em;color:#0a2540;background:#fff;
border:1px solid #d4d4d4;padding:6px 14px;cursor:pointer;border-radius:0;transition:all .12s}
.pill:hover{background:rgba(10,37,64,.05)}
.pill.on{background:#0a2540;color:#fff;border-color:#0a2540}
table.picks td.rk{font-family:'JetBrains Mono',monospace;color:#888;text-align:right;width:30px}
table.picks .tn{font-size:11px;color:#888}
.num{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;text-align:right}
.sec{color:#fff;padding:2px 8px;font-size:11px;font-family:'Inter',sans-serif;white-space:nowrap}
.pick-star{color:#0a5d3a}
td.chips{min-width:230px}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;color:#333;
background:#f4f4f4;padding:2px 7px;margin:2px 3px 2px 0;white-space:nowrap}
.chip-b{display:inline-block;height:7px;border-radius:0}
.chip.cpos .chip-b{background:#0a5d3a}.chip.cneg .chip-b{background:#7c2d12}
.chip.cneg{color:#7c2d12}
td.cmt{font-size:12px;color:#444;line-height:1.45;min-width:240px}
"""

FILTER_JS = r"""<script>
document.querySelectorAll('.pills').forEach(function(grp){
  grp.querySelectorAll('.pill').forEach(function(b){
    b.addEventListener('click',function(){
      grp.querySelectorAll('.pill').forEach(function(x){x.classList.remove('on');});
      b.classList.add('on');var f=b.getAttribute('data-f');
      document.querySelectorAll('table.picks tbody tr').forEach(function(tr){
        var show=(f==='all')||(f==='pick'&&tr.getAttribute('data-pick')==='1')||
                 (tr.getAttribute('data-status')===f);
        tr.style.display=show?'':'none';
      });
    });
  });
});
</script>"""


def main():
    df, weights, meta = picker.build_universe()
    sig_html, n_sens, n_fomc = signals_section()
    asof = pd.Timestamp.today().strftime("%d %b %Y")

    body = f"""<section class="hero"><div class="container">
<h1>Stock Research</h1>
<p class="lede">Picks, analysis and signals in one place. A reproducible composite
picker reads <b>every variable</b> from the fundamental and macro-signal pipelines,
z-scores and combines them, and ranks the {meta['n_universe']}-name research universe.</p>
<p class="asof">As of {asof} &middot; {meta['n_universe']} names &middot; data: Yahoo Finance + FRED-derived macro betas</p>
</div></section>
<main class="container">
{ccy_badge("USD", "figures in US dollars; ratios are currency-neutral")}
{picks_section(df, meta)}
{sig_html}
{companies_section()}
<section class="block"><h2>Methodology &amp; limitations</h2>
<div class="bt-method2">
<p><b>Composite.</b> For each ticker in the union of the two pipelines, collect every
numeric variable, z-score it cross-sectionally (missing → 0), and form a weighted sum.
Weights = each variable's Pearson correlation with realised forward returns; the sign
of that correlation sets the variable's direction. Normalised so the absolute weights
sum to 1. Rank by composite; top 20 are the picks.</p>
<p><b>Forward-return proxy.</b> The only realised forward-return history available
across the universe is the post-FOMC 5-day drift, so weights are derived from each
variable's cross-sectional correlation with the mean post-FOMC 5-day return. This is a
genuine realised-return signal but a narrow one; a broader forward-return panel would
sharpen the weights. If that history were absent the picker falls back to equal-weight
z-scores (documented on the build).</p>
<p><b>Universe.</b> The composite runs on the names that carry <i>both</i> fundamental
and macro-signal variables (the macro-signal coverage set). The broader S&amp;P 500
Buffett value screen stays available via the per-company tool.</p>
<p><b>Not advice.</b> Educational research over a public universe. Free Yahoo Finance
fundamentals are approximate; past forward-return relationships do not guarantee
future returns.</p></div></section>
</main>"""

    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Stock Research — Picks, Analysis &amp; Signals</title>{FONTS}'
            f'<link rel="stylesheet" href="style.css"><style>{PAGE_CSS}</style>'
            f'<script src="{PLOTLY}"></script></head><body>'
            f'<header class="shell"><div class="shell-in">'
            f'<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b>'
            f'</span>{NAV}</div></header>{body}'
            f'<footer class="shell-foot"><div class="container"><p>Composite picker '
            f'and CFA-framework analysis on free public data. Educational research, '
            f'not investment advice.</p></div></footer>{FILTER_JS}</body></html>')
    open(f"{DOCS}/stocks.html", "w", encoding="utf-8").write(html)

    # low-token AI copy + reproducibility dump (weights stay OUT of the public copy)
    top = df.head(20)
    contrib = meta["contrib"]
    ai = ["STOCK COMPOSITE PICKS — AI COPY (low-token)",
          f"asof={asof}; universe={meta['n_universe']}; target=mean post-FOMC fwd5; "
          f"coverage={meta['target_coverage']}/40; fallback={meta['equal_weight_fallback']}",
          "composite=sum(corr-derived-weight*zscore); weights private; top20=picks",
          "fields: rank|ticker|sector|price|composite|dominant_var"]
    for tk, r in top.iterrows():
        dom = contrib.loc[tk].abs().idxmax()
        ai.append(f"{int(r['rank'])}|{tk}|{r['sector']}|{r['price']:.2f}|"
                  f"{r['composite']:+.3f}|{picker.FLABEL[dom]}")
    open(f"{DOCS}/stocks.ai.txt", "w", encoding="utf-8").write("\n".join(ai) + "\n")

    print(f"stocks.html built: {meta['n_universe']} names, "
          f"{int((df['composite']>0).sum())} buy candidates, "
          f"signals {n_sens} sens / {n_fomc} FOMC")
    # sanity summary to stdout (for the build log / report)
    cv = contrib.var(ddof=0); share = (cv / cv.sum()).sort_values(ascending=False)
    base = df.sort_values("mom_12_1", ascending=False).head(20).index
    overlap = len(set(base) & set(df.head(20).index))
    print(f"  sectors(top20): {df.head(20)['sector'].value_counts().to_dict()}")
    print(f"  max var share: {share.iloc[0]*100:.1f}% ({share.index[0]})")
    print(f"  vs naive-momentum overlap: {overlap}/20")


if __name__ == "__main__":
    main()
