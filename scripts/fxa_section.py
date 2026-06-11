"""Single source for the FX-attribution UI block (repo-native since 2026-06-10;
absorbed from Downloads\\fx_attribution_2026-05-26\\code\\make_section.py so the
pipeline carries no code dependency outside the repo — the lot-history *data*
cache stays external). Produces a self-contained, scoped HTML *fragment* (its
own CSS + inlined JSON + IIFE JS) that can be dropped into any host page (the
LTCMA portfolio page, the real-numbers copies) without colliding with the
host's global currency toggle. Also wraps a fragment into a standalone page.

FX-impact convention (Carlos, 2026-06-10 — supersedes the old "opportunity
gain" USD view): the FX line applies ONLY to holdings not denominated in the
selected base currency, symmetric translation attribution.
  MXN base: dollar-denominated holdings carry the USD->MXN translation
            (stock at buy-FX + FX on cost + interaction = actual peso P&L);
            peso-native holdings have no FX leg.
  USD base: peso-native holdings carry the MXN->USD translation
            (USD P&L = MXN_value/X_val - MXN_cost/X_buy; FX = total - stock);
            dollar-denominated holdings have no FX leg (pure USD stock move).
Native rows store x_buy as the 1.0 sentinel ("no FX leg in MXN frame"); the
USD view needs a real buy rate, so anything <= 1.5 falls back to the
portfolio-blended buy FX (port_xbuy) and stays flagged approximate.

`scale` multiplies every MXN money field (P&L, cost basis); FX rates are exact.
"""
import json
from copy import deepcopy

MONEY_KEYS = ("stock", "fx", "interaction", "pnl", "mxn_cost")


def scale_data(data, scale):
    d = deepcopy(data)
    if scale != 1.0:
        for r in d["rows"]:
            r["shares"] = r["shares"] * scale     # site scales share counts too
            for bucket in ("realized", "unrealized"):
                for k in MONEY_KEYS:
                    if r[bucket].get(k) is not None:
                        r[bucket][k] = r[bucket][k] * scale
    d["scale"] = scale
    return d


# --- color themes ---------------------------------------------------------- #
LIGHT = dict(blue="#0f62fe", blue_hover="#edf5ff", btn_bg="#fff", btn_txt="#0f62fe",
             th_bg="#161616", th_txt="#fff", border="#e0e0e0", txt="#161616",
             pos="#198038", neg="#da1e28", zero="#8d8d8d", muted="#525252",
             gold="#b28600", row_hover="#eef4ff", tot_bg="#f4f4f4", panel="#fff",
             mono="'IBM Plex Mono',monospace", sans="'IBM Plex Sans',sans-serif")
DARK = dict(blue="#58a6ff", blue_hover="#1c2333", btn_bg="#0d1117", btn_txt="#58a6ff",
            th_bg="#0d1117", th_txt="#e6edf3", border="#30363d", txt="#e6edf3",
            pos="#3fb950", neg="#f85149", zero="#8b949e", muted="#8b949e",
            gold="#d29922", row_hover="#1c2333", tot_bg="#161b22", panel="#161b22",
            mono="ui-monospace,SFMono-Regular,Menlo,monospace",
            sans="-apple-system,Inter,Segoe UI,sans-serif")
THEMES = {"light": LIGHT, "dark": DARK}


# --- scoped CSS (prefixed so it never touches the host page) --------------- #
def _css(p, t):
    return (""
            "#@P-root{margin:40px 0;font-family:@SANS;color:@TXT}"
            "#@P-root>h2{font-size:13px;font-weight:600;letter-spacing:.4px;text-transform:uppercase;color:@TXT;padding-bottom:10px;margin-bottom:14px;border-bottom:1px solid @BORDER;display:flex;align-items:center;gap:10px}"
            "#@P-root>h2::before{content:'';width:14px;height:14px;background:@BLUE;flex:none}"
            "#@P-root .fxa-intro{color:@MUTED;font-size:13px;margin:0 0 12px;line-height:1.55}"
            "#@P-root .fxa-intro b{color:@TXT}"
            "#@P-root .fxa-card{background:@PANEL;border:1px solid @BORDER;padding:0 14px 8px;overflow-x:auto;margin-top:4px}"
            "#@P-root .fxa-controls{display:flex;gap:26px;flex-wrap:wrap;align-items:flex-end;margin:6px 0}"
            "#@P-root .fxa-l{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.4px;color:@MUTED;margin-bottom:6px;display:block}"
            "#@P-root .fxa-seg{display:inline-flex;border:1px solid @BLUE}"
            "#@P-root .fxa-seg button{background:@BTNBG !important;color:@BTNTXT !important;border:0;border-right:1px solid @BLUE;padding:7px 20px;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:background .12s,color .12s}"
            "#@P-root .fxa-seg button:last-child{border-right:0}"
            "#@P-root .fxa-seg button:hover{background:@HOVER !important}"
            "#@P-root .fxa-seg button.on{background:@BLUE !important;color:@BTNON !important}"
            "#@P-root .fxa-ctlnote{font-size:12px;color:@MUTED;background:@PANEL;border-left:3px solid @GOLD;padding:9px 14px;margin:12px 0 4px;line-height:1.5}"
            "#@P-root .fxa-ctlnote b{color:@TXT}"
            "#@P-root .fxa-view{font-size:12.5px;color:@MUTED;margin:10px 0 8px;min-height:18px}"
            "#@P-root .fxa-view b{color:@BLUE}"
            "#@P-root table.fxa-tbl{border-collapse:collapse;width:100%;font-size:13px;background:@PANEL;color:@TXT}"
            "#@P-root .fxa-tbl th{background:@THBG;color:@THTXT;text-align:right;padding:9px 12px;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.3px}"
            "#@P-root .fxa-tbl th:first-child{text-align:left}"
            "#@P-root .fxa-tbl td{border-bottom:1px solid @BORDER;padding:8px 12px;text-align:right;font-family:@MONO}"
            "#@P-root .fxa-tbl td.fxa-tk{text-align:left;font-family:@SANS;font-weight:600}"
            "#@P-root .fxa-tbl tbody tr:hover td{background:@ROWHOVER}"
            "#@P-root .fxa-tbl tr.fxa-tot td{border-top:2px solid @THTXT;font-weight:600;background:@TOTBG}"
            "#@P-root .fxa-pos{color:@POS}#@P-root .fxa-neg{color:@NEG}#@P-root .fxa-zero{color:@ZERO}"
            "#@P-root .fxa-delta{font-family:@MONO;font-size:11px;margin-left:6px}"
            "#@P-root .fxa-dpos{color:@POS}#@P-root .fxa-dneg{color:@NEG}"
            "#@P-root .fxa-flag{font-size:9px;color:@GOLD;font-weight:600;vertical-align:super;margin-left:2px}"
            "#@P-root .fxa-foot{font-size:11.5px;color:@MUTED;margin-top:14px;line-height:1.6}"
            "#@P-root .fxa-foot b{color:@TXT}"
            ).replace("@BLUE", t["blue"]).replace("@HOVER", t["blue_hover"]) \
             .replace("@BTNBG", t["btn_bg"]).replace("@BTNTXT", t["btn_txt"]) \
             .replace("@BTNON", t["th_txt"] if t is DARK else "#fff") \
             .replace("@THBG", t["th_bg"]).replace("@THTXT", t["th_txt"]) \
             .replace("@BORDER", t["border"]).replace("@TXT", t["txt"]) \
             .replace("@MUTED", t["muted"]).replace("@GOLD", t["gold"]) \
             .replace("@NEG", t["neg"]).replace("@ZERO", t["zero"]) \
             .replace("@ROWHOVER", t["row_hover"]).replace("@TOTBG", t["tot_bg"]) \
             .replace("@MONO", t["mono"]).replace("@SANS", t["sans"]) \
             .replace("@PANEL", t["panel"]).replace("@POS", t["pos"]).replace("@P", p)


# --- the JS (scoped to the root element, IIFE) ----------------------------- #
def _js(p, data_json):
    return ("""
(function(){
  const DATA = __DATA__;
  const X_NOW = DATA.x_now, SCALE = DATA.scale||1;
  const PXB = DATA.port_xbuy || X_NOW;   // blended buy-FX proxy when a real one is missing
  const root = document.getElementById("__P__-root");
  let MODE='normal', CCY='MXN';
  function fmt(v){
    const n=Math.round(v), s=Math.abs(n).toLocaleString('en-US');
    const cls=n>0?'fxa-pos':(n<0?'fxa-neg':'fxa-zero');
    return '<span class="'+cls+'">'+(n<0?'-':'')+'$'+s+'</span>';
  }
  // a usable USD/MXN buy rate: native rows store the 1.0 "no FX leg" sentinel
  function xbuy(b){ return (b.x_buy && b.x_buy>1.5) ? b.x_buy : PXB; }
  function xval(b){ return (b.x_val && b.x_val>1.5) ? b.x_val : X_NOW; }
  // stock effect in USD = the asset move at constant (buy-date) FX
  function usdStock(b,native){
    if(!b.mxn_cost && !b.stock) return 0;
    return b.stock / xbuy(b);
  }
  // USD-base FX translation impact: ONLY peso-native holdings carry it
  // (dollar-denominated holdings are already in base currency -> no FX leg).
  // total_usd = MXN_value/X_val - MXN_cost/X_buy ; fx = total - stock.
  function usdFx(b,native){
    if(!native || !b.mxn_cost) return 0;
    const xb=xbuy(b), xv=xval(b);
    return (b.mxn_cost + b.stock)/xv - (b.mxn_cost + b.stock)/xb;
  }
  function bval(b,native){
    if(CCY==='MXN') return MODE==='normal' ? b.stock : b.pnl;
    const s=usdStock(b,native);
    return MODE==='normal' ? s : s + usdFx(b,native);
  }
  function normVal(b,native){const m=MODE;MODE='normal';const v=bval(b,native);MODE=m;return v;}
  function dtag(v,d){
    let h=fmt(v);
    if(MODE==='fx' && Math.abs(Math.round(d))>=1){
      const dc=d>=0?'fxa-dpos':'fxa-dneg';
      h+='<span class="fxa-delta '+dc+'">('+(d>=0?'+':'\\u2212')+'$'+Math.abs(Math.round(d)).toLocaleString('en-US')+' FX)</span>';
    }
    return h;
  }
  function cell(b,native){return dtag(bval(b,native), bval(b,native)-normVal(b,native));}
  function totCell(rv,uv,r){
    const tv=rv+uv, d=(rv-normVal(r.realized,r.native))+(uv-normVal(r.unrealized,r.native));
    return dtag(tv,d);
  }
  function render(){
    const tb=root.querySelector("#__P__-tbody"); tb.innerHTML='';
    const tot={r:0,u:0,t:0,rd:0,ud:0};
    const rows=[...DATA.rows].sort((a,b)=>
      (bval(b.realized,b.native)+bval(b.unrealized,b.native))-(bval(a.realized,a.native)+bval(a.unrealized,a.native)));
    for(const r of rows){
      const rv=bval(r.realized,r.native), uv=bval(r.unrealized,r.native);
      tot.r+=rv; tot.u+=uv; tot.t+=rv+uv;
      tot.rd+=rv-normVal(r.realized,r.native); tot.ud+=uv-normVal(r.unrealized,r.native);
      const flag=r.approx?'<span class="fxa-flag" title="approximated (no transaction history)">A</span>':
        (r.native?'<span class="fxa-flag" title="peso-native: no FX leg in MXN view; carries the MXN-&gt;USD translation in USD view">P</span>':'');
      const tr=document.createElement('tr');
      tr.innerHTML='<td class="fxa-tk">'+r.ticker+flag+'</td>'+
        '<td>'+r.shares.toLocaleString('en-US')+'</td>'+
        '<td>'+cell(r.realized,r.native)+'</td>'+
        '<td>'+cell(r.unrealized,r.native)+'</td>'+
        '<td>'+totCell(rv,uv,r)+'</td>';
      tb.appendChild(tr);
    }
    const tf=root.querySelector("#__P__-tfoot"); tf.innerHTML='';
    const trf=document.createElement('tr'); trf.className='fxa-tot';
    trf.innerHTML='<td class="fxa-tk">ALL IN-SCOPE</td><td></td>'+
      '<td>'+dtag(tot.r,tot.rd)+'</td><td>'+dtag(tot.u,tot.ud)+'</td>'+
      '<td>'+dtag(tot.t,tot.rd+tot.ud)+'</td>';
    tf.appendChild(trf);
    root.querySelector("#__P__-view").innerHTML=viewText();
  }
  function viewText(){
    if(MODE==='normal'&&CCY==='MXN') return 'Showing <b>stock effect only</b>, in Mexican pesos \\u2014 your P&L if USD/MXN had never moved.';
    if(MODE==='normal'&&CCY==='USD') return 'Showing the <b>pure stock move in US dollars</b>, FX stripped out.';
    if(MODE==='fx'&&CCY==='MXN') return 'Showing your <b>actual peso P&L</b> (stock + FX + interaction). Tag = FX contribution on <b>dollar-denominated</b> holdings; a stronger peso <span class="fxa-dneg">hurts</span> (USD assets worth fewer pesos). Peso-native holdings carry no FX leg here.';
    return 'Showing <b>dollar P&L including the MXN\\u2192USD translation</b> on <b>peso-native</b> holdings. Tag = that translation; dollar-denominated holdings are already in base currency and carry no FX leg here.';
  }
  function bind(id,set){
    root.querySelector('#'+id).addEventListener('click',function(e){
      if(e.target.tagName!=='BUTTON')return;
      [...e.currentTarget.children].forEach(b=>b.classList.remove('on'));
      e.target.classList.add('on'); set(e.target.dataset.v); render();
    });
  }
  bind("__P__-mode",v=>MODE=v); bind("__P__-ccy",v=>CCY=v);
  render();
})();
""".replace("__DATA__", data_json).replace("__P__", p))


def build_section(data, scale=1.0, prefix="fxa", title="FX Attribution",
                  scaled_note=False, theme="light"):
    t = THEMES[theme]
    d = scale_data(data, scale)
    data_json = json.dumps(d, separators=(",", ":"))
    asof = d["as_of"]
    xn = d["x_now"]
    scale_txt = (f" Figures scaled &times;{scale:g} for confidentiality (magnitudes "
                 "illustrative; the stock/FX split and percentages are exact)."
                 if scale != 1.0 else "")
    foot = (
        "<b>Method.</b> Moving-average lots. Realized lots use blended buy-FX &amp; "
        "sell-date FX; unrealized uses blended buy-FX &amp; current USD/MXN. "
        "Each P&amp;L = stock + FX + interaction; \"Normal\" = stock only. "
        "<b>The FX line applies only to holdings not denominated in the selected "
        "base currency</b>: in MXN, dollar-denominated holdings carry the "
        "USD&rarr;MXN translation; in USD, peso-native holdings carry the "
        "MXN&rarr;USD translation (MXN_value/X_now &minus; MXN_cost/X_buy, less "
        "the stock effect). USD/MXN from yfinance daily. VGT 8:1 / VUG 6:1 splits "
        "(2026-04-24) handled. <span class=\"fxa-flag\">A</span>=approximated (no "
        "tx record; blended buy-FX); <span class=\"fxa-flag\">P</span>=peso-native "
        "(GMEXICO B)." + scale_txt)
    return f"""<section id="{prefix}-root">
<h2>{title}</h2>
<p class="fxa-intro">How much of your equity P&amp;L is the <b>stocks moving</b> vs the
<b>peso moving</b> &mdash; split into already-booked (<b>Realized</b>) and still-open
(<b>Unrealized</b>). As of {asof} &middot; USD/MXN {xn:.4f}.</p>
<div class="fxa-controls">
<div><span class="fxa-l">Mode</span><div class="fxa-seg" id="{prefix}-mode">
<button data-v="normal" class="on">Normal</button><button data-v="fx">FX&nbsp;Impact</button></div></div>
<div><span class="fxa-l">Currency</span><div class="fxa-seg" id="{prefix}-ccy">
<button data-v="MXN" class="on">MXN</button><button data-v="USD">USD</button></div></div>
</div>
<div class="fxa-ctlnote"><b>FX&nbsp;Impact</b> shows the currency-translation
component, and it applies <b>only to holdings not already denominated in the
selected base</b>: in the <b>MXN</b> view, dollar-denominated holdings carry the
USD&rarr;MXN translation (a stronger peso is a <span class="fxa-dneg">drag</span>);
in the <b>USD</b> view, peso-native holdings carry the MXN&rarr;USD translation
(a stronger peso is a <span class="fxa-dpos">tailwind</span>). Holdings already
in the base currency show no FX line.</div>
<div class="fxa-view" id="{prefix}-view"></div>
<div class="fxa-card">
<table class="fxa-tbl"><thead><tr>
<th>Ticker</th><th>Shares held</th><th>Realized</th><th>Unrealized</th><th>Total</th>
</tr></thead><tbody id="{prefix}-tbody"></tbody><tfoot id="{prefix}-tfoot"></tfoot></table></div>
<div class="fxa-foot">{foot}</div>
<style>{_css(prefix, t)}</style>
<script>{_js(prefix, data_json)}</script>
</section>"""


def build_standalone(data, scale=1.0, prefix="fxa", theme="light"):
    section = build_section(data, scale, prefix, title="Stock vs Peso — P&L Attribution",
                            theme=theme)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FX vs Stock Attribution</title>
<link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap" onload="this.onload=null;this.rel='stylesheet'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap"></noscript>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'IBM Plex Sans',Segoe UI,sans-serif;color:#161616;background:#f4f4f4;line-height:1.55}}
.container{{max-width:1100px;margin:0 auto;padding:0 32px}}
.shell{{background:#161616;position:sticky;top:0;z-index:50}}
.shell-in{{max-width:1100px;margin:0 auto;padding:0 32px;height:48px;display:flex;align-items:center;gap:16px}}
.brand{{color:#fff;font-size:14px;font-weight:300}}.brand b{{font-weight:600}}
.hero{{background:linear-gradient(135deg,#161616,#21272a);color:#fff;padding:40px 0 44px;border-bottom:3px solid #0f62fe}}
.hero h1{{font-size:32px;font-weight:300;letter-spacing:-.6px}}
main{{padding:30px 0 64px}}
</style></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>P&amp;L Attribution</b></span></div></header>
<section class="hero"><div class="container"><h1>Stock vs Peso &mdash; where the P&amp;L came from</h1></div></section>
<main class="container">
{section}
</main></body></html>"""
