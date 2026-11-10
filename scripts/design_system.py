"""Design-system source of truth (Phase 0 of REDESIGN_PLAN).

`docs/_design_system/tokens.css` and `base.css` are BUILD OUTPUTS emitted from here,
exactly the way `docs/style.css` is emitted by `17_build_site.py`. They are never
hand-edited: anything under `docs/` that no generator emits is deleted by
`daily_refresh.ps1`'s `git clean -fd docs data` on the next weekday run.

Phase 0 is defined by its acceptance criterion -- NOTHING VISUALLY CHANGES. Two
mechanisms guarantee that, and both must survive future edits:

  1. `tokens.css` declares custom properties only. Declaring an unused `--fs-h1` cannot
     move a pixel. The colour/type/`--wrap` values are copied verbatim from the existing
     `style.css` `:root`, so even the *used* ones resolve identically.
  2. Every rule in `base.css` is scoped under `.ds-v2`, and no page carries that class
     yet (REDESIGN_PLAN 5.4). Phase 1 adds `<body class="ds-v2">` to the pilot page only;
     removing it reverts that one page and nothing else.

Both files are `<link>`ed BEFORE `style.css`. That ordering is load-bearing: `.grid`,
`.metrics`, `.block` and friends exist in both sheets at equal specificity, so the sheet
that loads LAST wins. `style.css` must keep winning until a page opts in.

Breakpoints live here as PYTHON constants, not only as CSS variables, because custom
properties cannot be used in `@media` queries -- `@media (max-width: var(--bp-sm))` works
in no browser. The Python constants are what actually keep the ten generators agreeing.
"""

# --- breakpoints: 360/560/820/880/1100 consolidated to 640/900/1200 -------------
# 1100 is NOT in this list: it survives as `--wrap`, a container width, not a breakpoint.
BP_SM, BP_MD, BP_LG = 640, 900, 1200

# --- chart geometry, mirrored into tokens.css so CSS and Plotly cannot drift ----
CHART = {
    "h_sm": 320, "h_lg": 420,          # standard charts
    "h_tall_sm": 420, "h_tall_lg": 640,  # heatmaps only
    "min_h": 280, "max_h": 460,        # the A4 gate bounds @375
}

FONTS = ("Inter", "Spectral", "JetBrains Mono")   # A9: nothing else may appear

# --- number presentation: ONE rule, enforced where every chart already passes ----
# A trace with no `hovertemplate` falls back to Plotly's default, which prints the raw
# float: GMEXICOB's return read `17.956999914853366%` in a tooltip on the live site.
# The 2026-09-22 audit found 289 such traces across 13 pages, 155 of them carrying
# >=5-decimal values. Fixing them one by one is 289 chances to forget, and the next
# chart added would reintroduce it.
#
# So the rule lives in `axis_formats(fig)`, which every generator calls from inside its
# own `div()` -- the single funnel every published chart already goes through. It sets
# `hoverformat` per axis and never overwrites one that was set deliberately.
#
# Date axes take a d3-TIME format; giving them a numeric one prints literal garbage.
# The axis type is usually left on "auto", so it is inferred from the data rather than
# read off the layout.
# --- ONE chart palette, shared by every generator ------------------------------
# Before 2026-09-22 each generator carried its own constants and `GOLD` was in fact a
# grey (#6b7280), so "gold" and "grey" rendered identically while reading as two
# different things in the source. Worse, `RED` did double duty: a semantic negative-P/L
# marker in one place and an ordinary categorical series colour in another, which spends
# the site's only alarm colour on things that are not alarming.
#
# The split that matters: SEQ is for telling categories apart and carries no meaning;
# POS/NEG are semantic and appear ONLY where a number's sign is the point.
NAVY    = "#0a2540"     # primary — this book, the main series
SLATE   = "#5b7c99"     # secondary series
TEAL    = "#0f766e"     # the single accent: utilisation, offsetting correlation
BENCH   = "#9aa5b1"     # benchmarks and reference lines — deliberately recessive
MUTED   = "#b6bec8"     # "behind the reference" fill
GRIDLN  = "#e5e5e5"
POS, NEG = "#0a5d3a", "#7c2d12"       # SEMANTIC ONLY — never a categorical series
SEQ = (NAVY, TEAL, SLATE, BENCH, "#7e97b3", "#7fb3ad")   # categorical ramp, in order
CORR_SCALE = [[0.0, TEAL], [0.25, "#7fb3ad"], [0.5, "#f4f4f2"],
              [0.75, "#7e97b3"], [1.0, NAVY]]

MAX_DP = 2                                  # site-wide ceiling on displayed decimals
NUM_HOVER = f",.{MAX_DP}f"                  # 1,234.57
# Axis TICKS get the same ceiling with trailing zeros trimmed (d3 "~"): 20,000,000 not
# 20,000,000.00, 2.5 not 2.50, 10 not 10.00. The fixed ",.2f" on ticks (2026-09-24) made
# every axis on the site read "0.00 / 5.00 / 10.00" and a peso axis "20,000,000.00" --
# the single most "something is off here" detail of the 2026-10-01 audit. Tooltips keep
# the fixed 2 dp (NUM_HOVER): a reading is a figure, a tick is a ruler mark.
NUM_TICK = f",.{MAX_DP}~f"
DATE_HOVER = "%d %b %Y"


def _is_date_axis(fig, letter):
    import datetime as _dt
    import numpy as _np
    for tr in fig.data:
        vals = getattr(tr, letter, None)
        if vals is None or len(vals) == 0:
            continue
        # 2026-09-29: a pandas DatetimeIndex reaches the figure as a numpy datetime64
        # array, whose elements are NOT datetime.date. This check used to miss it, so
        # every date axis built from a DataFrame index got the numeric ",.2f" and the
        # live portfolio chart printed ",.2f" five times along its x axis.
        if getattr(getattr(vals, "dtype", None), "kind", "") == "M":
            return True
        v = vals[0]
        if isinstance(v, (_dt.date, _dt.datetime, _np.datetime64)):
            return True
        if isinstance(v, str) and len(v) >= 8 and v[:4].isdigit() and v[4] in "-/":
            return True
        return False           # first trace with data decides; mixed axes do not exist here
    return False


def _is_category_axis(fig, letter):
    for tr in fig.data:
        vals = getattr(tr, letter, None)
        if vals is None or len(vals) == 0:
            continue
        v = vals[0]
        return isinstance(v, str) and not (len(v) >= 8 and v[:4].isdigit())
    return False


def axis_formats(fig):
    """Give every axis a hover format so no raw float can reach a tooltip.

    Idempotent, and deliberately non-destructive: an axis that already carries a
    `hoverformat` was set on purpose (percentages, basis points) and is left alone.
    """
    for letter, axis in (("x", "xaxis"), ("y", "yaxis")):
        ax = getattr(fig.layout, axis, None)
        if ax is None or ax.hoverformat is not None:
            continue
        if _is_category_axis(fig, letter):
            continue                                   # tickers, asset names: not numbers
        _isdate = _is_date_axis(fig, letter)
        _upd = dict(hoverformat=DATE_HOVER if _isdate else NUM_HOVER)
        if ax.type == "log":
            # plotly 2.35 labels a log axis's MAJOR ticks with its hoverformat when it has
            # no tickformat ("100.00", "1,000.00") and every minor digit 5-9 under D1.
            # Trimmed hover (still <= 2 dp) and 2/5 minors only.
            # 2026-10-09: "D2" labels its minor ticks with the bare digit, so a growth-of-100
            # axis read "5 ... 100 ... 2 ... 5 ... 1,000" (Carlos, from a phone). An explicit
            # 1-2-5 ladder prints each value whole (50, 200, 500); Plotly drops the rungs
            # outside the visible range, so the start-date slider's re-base still works.
            _ladder = [m * 10 ** e for e in range(0, 6) for m in (1, 2, 5)]
            _upd = dict(hoverformat=NUM_TICK, tickmode="array", tickvals=_ladder,
                        ticktext=[f"{v:,}" for v in _ladder])
        # 2026-09-24: el techo tambien va a las ETIQUETAS DE EJE, no solo al tooltip.
        # Mismo criterio no-destructivo: un tickformat puesto a mano (porcentajes, bps,
        # miles) se respeta; un eje de fecha nunca recibe formato numerico.
        # A LOG axis is left to Plotly's own decade labels: a tickformat there labels every
        # minor tick, and strategies.html stacked "1,000.00 900.00 800.00 700.00..." 12px apart.
        if not _isdate and ax.tickformat is None and ax.type != "log":
            _upd["tickformat"] = NUM_TICK
        fig.update_layout(**{axis: _upd})
    return fig


# --- entities are HTML, and a Plotly hovertemplate is NOT HTML ------------------
# Plotly renders a small HTML subset inside hover text but does not decode named
# entities, so `&middot;` reaches the user as the seven literal characters. Shipped
# that way in a9a5361 and caught on the live site the same day. Write the character.
BAD_ENTITIES = ("&middot;", "&amp;", "&nbsp;", "&ndash;", "&mdash;", "&rsquo;", "&times;")


def assert_no_entities(fig, name=""):
    """Abort if a hovertemplate or trace name carries an HTML entity."""
    for tr in fig.data:
        for attr in ("hovertemplate", "name", "texttemplate"):
            v = getattr(tr, attr, None)
            if isinstance(v, str):
                for ent in BAD_ENTITIES:
                    if ent in v:
                        raise SystemExit(
                            f"CHART GUARD: {name or fig.layout.title.text!r} has the literal "
                            f"HTML entity {ent!r} in .{attr} -- Plotly does not decode "
                            f"entities in hover text. Write the character itself.")
        for attr in ("hovertemplate", "texttemplate"):
            v = getattr(tr, attr, None)
            if isinstance(v, str) and _TPL_SIGN.search(v):
                raise SystemExit(
                    f"CHART GUARD: {name or fig.layout.title.text!r} .{attr}={v!r} uses the "
                    f"d3 sign flag '+' -- plotly.js 2.35 then ignores the WHOLE format and "
                    f"prints the raw float (13.23208182587156%). Drop the '+'.")
    return fig


# --- the sign flag silently disables a hovertemplate format ----------------------
# 2026-09-29, measured on a clean page with plotly-2.35.0: `%{y:.2f}%` -> 9.68%, but
# `%{y:+.2f}%` -> 9.676637895645811%. The format is not applied partially, it is dropped,
# and nothing warns. Five portfolio traces carried it, so the MAX_DP rule never reached
# them even though every one "had a hovertemplate". Signs in hover come from the data.
import re as _re
_TPL_SIGN = _re.compile(r"%\{[^}:]*:\+[^}]*\}")
_TIME_DIRECTIVE = _re.compile(r"%-?[a-zA-Z]")
_ISO_DATE = _re.compile(r"^\d{4}-\d{2}-\d{2}")


def _plotly_calls(html):
    """Yield (div_id, data, layout) for every Plotly.newPlot call in a rendered page."""
    import json
    dec = json.JSONDecoder()
    for m in _re.finditer(r'Plotly\.newPlot\(\s*"([^"]+)"\s*,\s*', html):
        data, end = dec.raw_decode(html, m.end())
        end = _re.compile(r"\s*,\s*").match(html, end).end()
        layout, _ = dec.raw_decode(html, end)
        yield m.group(1), data, layout


def _kind(vals):
    if isinstance(vals, dict):                       # {"dtype": "f8", "bdata": ...}
        return "num"
    if not isinstance(vals, list) or not vals:
        return None
    v = next((x for x in vals if x is not None), None)
    if isinstance(v, str):
        return "date" if _ISO_DATE.match(v) else "cat"
    return "num" if isinstance(v, (int, float)) else None


def guard_plotly_html(html, page):
    """Scan the FINAL page bytes -- not the figure objects -- for the three hover/axis
    defects Carlos has caught on the live site. Returns the number of charts checked;
    raises SystemExit on any hit. A guard that only ever sees green is unverified, so
    the self-test below feeds it each defect first."""
    bad, n = [], 0
    for did, data, layout in _plotly_calls(html):
        n += 1
        axes = {}
        for tr in data:
            for attr in ("hovertemplate", "texttemplate"):
                v = tr.get(attr)
                if isinstance(v, str) and _TPL_SIGN.search(v):
                    bad.append(f"{did}: {attr} {v!r} has the '+' sign flag (format ignored)")
            for letter in ("x", "y"):
                ref = tr.get(f"{letter}axis", letter)
                key = f"{letter}axis{ref[1:]}"
                k = _kind(tr.get(letter))
                if k:
                    axes.setdefault(key, set()).add(k)
            # a trace with no template, on a numeric axis with no hoverformat, prints raw
            if tr.get("type", "scatter") in ("scatter", "bar", "scattergl") \
                    and tr.get("hoverinfo") not in ("skip", "none") and not tr.get("hovertemplate"):
                vl = "x" if tr.get("orientation") == "h" else "y"
                key = f"{vl}axis{tr.get(vl + 'axis', vl)[1:]}"
                if _kind(tr.get(vl)) == "num" and not (layout.get(key) or {}).get("hoverformat"):
                    bad.append(f"{did}: trace {tr.get('name')!r} has no hovertemplate and "
                               f"{key} no hoverformat -> raw float in tooltip")
        for key, kinds in axes.items():
            ax = layout.get(key) or {}
            if "date" in kinds or ax.get("type") == "date":
                for f in ("tickformat", "hoverformat"):
                    v = ax.get(f)
                    if v and not _TIME_DIRECTIVE.search(v):
                        bad.append(f"{did}: date axis {key}.{f}={v!r} is a NUMBER format "
                                   f"-> the literal '{v}' is printed as tick/hover text")
    if bad:
        raise SystemExit(f"PLOTLY HTML GUARD FAILED on {page} ({len(bad)}):\n  "
                         + "\n  ".join(bad))
    return n


def _selftest_guard():
    """Prove the HTML guard FINDS each defect before trusting its green."""
    tpl = ('<script>Plotly.newPlot("t", [{0}], {1}, {{}})</script>')
    cases = {
        "sign": tpl.format('{"x":["2026-01-01"],"y":[1.5],"hovertemplate":"%{y:+.2f}%"}',
                           '{"xaxis":{"hoverformat":"%d %b %Y"}}'),
        "datefmt": tpl.format('{"x":["2026-01-01"],"y":[1.5],"hovertemplate":"%{y:.2f}"}',
                              '{"xaxis":{"tickformat":",.2f"}}'),
        "raw": tpl.format('{"x":["2026-01-01"],"y":{"dtype":"f8","bdata":"AA=="}}',
                          '{"xaxis":{"hoverformat":"%d %b %Y"}}'),
    }
    for k, h in cases.items():
        try:
            guard_plotly_html(h, f"selftest:{k}")
        except SystemExit:
            continue
        raise SystemExit(f"PLOTLY HTML GUARD self-test: defect {k!r} was NOT detected")
    ok = tpl.format('{"x":["2026-01-01"],"y":[1.5],"hovertemplate":"%{y:.2f}%"}',
                    '{"xaxis":{"hoverformat":"%d %b %Y","tickformat":"%b %Y"}}')
    assert guard_plotly_html(ok, "selftest:ok") == 1
    return len(cases)


if __name__ == "__main__" and len(__import__("sys").argv) > 1:
    # python scripts/design_system.py docs/*.html  -- sweep the published pages
    import sys, pathlib
    _selftest_guard()
    fails = 0
    for p in sys.argv[1:]:
        try:
            print(f"  {p}: {guard_plotly_html(pathlib.Path(p).read_text(encoding='utf-8'), p)} charts OK")
        except SystemExit as e:
            fails += 1
            print(e)
    sys.exit(1 if fails else 0)

TOKENS = """/* GENERATED by scripts/design_system.py -- do not edit under docs/. */
:root{
  /* ---- colour: the Editorial Terminal values (2026-11-10), the same as the :root of the
     ET layer that 17_build_site.py appends to style.css (style.css loads last and wins) ---- */
  --bg:#F6F5F1; --panel:#FFFFFF;
  --ink:#0E1726; --sec:#4A5568; --muted:#667085;
  --line:#E3E1DA; --line-strong:#C9C6BC; --chip:#EFEDE6;
  --accent:#0A2540;                     /* Oxford blue, NOT #252D5D (open item 2) */
  --accent-tint:rgba(10,37,64,.05); --accent-line:rgba(10,37,64,.28);
  --amber:#B45309; --up:#0F5E9C; --down:#C2410C;
  --pos:#0a5d3a; --neg:#7c2d12;
  --st-green:#0a5d3a; --st-blue:#1e3a8a; --st-purple:#5b21b6; --st-gray:#6b7280;

  /* ---- type stacks: copied verbatim ---- */
  --serif:'Spectral',Charter,"Iowan Old Style",Cambria,Georgia,serif;
  --sans:'Inter',system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,"SF Mono",Menlo,Consolas,monospace;

  --wrap:min(1100px,92vw);

  /* ---- NEW: fluid type scale, no per-breakpoint overrides ---- */
  --fs-h1:clamp(26px,4.2vw,40px);
  --fs-h2:clamp(19px,2.2vw,25px);
  --fs-h3:clamp(16px,1.6vw,19px);
  --fs-body:clamp(15px,1.05vw,16.5px);
  --fs-sm:clamp(13px,1vw,14px);
  --fs-xs:12px;                         /* HARD FLOOR for prose */
  --fs-label:11px;                      /* uppercase .06em labels only */

  /* ---- NEW: spacing, 4px base ---- */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px;
  --sp-6:24px; --sp-8:32px; --sp-12:48px; --sp-16:64px;

  /* ---- NEW: breakpoints. Documentation + JS only; @media cannot read these. ---- */
  --bp-sm:%(sm)dpx; --bp-md:%(md)dpx; --bp-lg:%(lg)dpx;

  /* ---- NEW: chart heights, mirrored from design_system.CHART ---- */
  --chart-h-sm:%(csm)dpx; --chart-h-lg:%(clg)dpx;
  --chart-h-tall-sm:%(tsm)dpx; --chart-h-tall-lg:%(tlg)dpx;

  --gutter-sm:14px; --gutter-lg:24px;
}
""" % {"sm": BP_SM, "md": BP_MD, "lg": BP_LG,
       "csm": CHART["h_sm"], "clg": CHART["h_lg"],
       "tsm": CHART["h_tall_sm"], "tlg": CHART["h_tall_lg"]}


BASE = """/* GENERATED by scripts/design_system.py -- do not edit under docs/.
   EVERY rule is scoped under .ds-v2. No page carries that class until Phase 1 opts
   one in (REDESIGN_PLAN 5.4), so this sheet is inert by construction. Adding an
   unscoped rule here silently ends that guarantee -- don't. */

/* min-width:0 is BUILT IN, not remembered per-site: this is the 2026-08-11 .tile
   blowout encoded as a component invariant. A grid/flex item defaults to
   min-width:auto, so one wide table or one long mono string blows out the track. */
.ds-v2 .card, .ds-v2 .tile, .ds-v2 .btcard, .ds-v2 .scard{ min-width:0; overflow:hidden; }

.ds-v2 .grid{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr);
              gap:var(--sp-6); }
.ds-v2 .grid--1{ grid-template-columns:minmax(0,1fr); }
.ds-v2 .metrics{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
                 gap:var(--sp-6); }

/* chart height comes from a token, never from Plotly's 450px default */
.ds-v2 .chart-container{ min-width:0; width:100%%; height:var(--chart-h-lg); }
.ds-v2 .chart-container--tall{ height:var(--chart-h-tall-lg); }

/* the scroll box is a COMPONENT with a fade affordance, not bare overflow */
.ds-v2 .data-table-wrap{ overflow-x:auto; -webkit-overflow-scrolling:touch;
  scrollbar-width:thin;
  -webkit-mask-image:linear-gradient(to right,#000 calc(100%% - 18px),transparent);
          mask-image:linear-gradient(to right,#000 calc(100%% - 18px),transparent); }
.ds-v2 .data-table-wrap>table{ margin:0; }

/* prose floor: nothing below --fs-xs, which is the A5 gate's reason to exist */
.ds-v2 .lede{ font-size:var(--fs-body); }
.ds-v2 .caption,.ds-v2 .note{ font-size:var(--fs-sm); }

@media (max-width:%(sm)dpx){
  .ds-v2 .grid{ grid-template-columns:minmax(0,1fr); gap:var(--sp-4); }
  .ds-v2 .chart-container{ height:var(--chart-h-sm); }
  .ds-v2 .chart-container--tall{ height:var(--chart-h-tall-sm); }
}
@media (min-width:%(sm)dpx) and (max-width:%(md)dpx){
  .ds-v2 .metrics{ grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }
}
""" % {"sm": BP_SM, "md": BP_MD}


# --- mobile chart tuning (relocated from glossary._MOBILE_CHARTS_JS, 2026-08-31) ---
# Moved verbatim so NAV stops being where structural JS lives. `glossary.NAV` imports
# this, so every generated page keeps the same tuner. The ONLY edit is that the
# breakpoint is read from --bp-sm instead of hardcoded -- and the token resolves to
# 640, the previous literal, so behaviour is unchanged today and cannot drift later.
#
# Plotly neither wraps nor shrinks a title and has no 'font size at this breakpoint'
# option. At a 283px mobile plot width a 45-char title renders ~350-410px wide and is
# silently CLIPPED by `.tile{overflow:hidden}` -- which is why the site passed the
# 375px no-overflow gate while every chart read as truncated: the gate measures the
# DOCUMENT, the clipping happens inside a tile. So the breakpoint is applied from JS.
#
# Desktop is untouched by construction: above the breakpoint the tuner returns early
# before it ever calls relayout. Originals are stashed on first sight and restored on
# the way back up, so a desktop<->mobile resize round-trip is lossless.
MOBILE_CHARTS_JS = """<script>(function(){
var MOB=640,st=new WeakMap();
/* read the breakpoint from --bp-sm so CSS and JS cannot drift; 640 is the fallback
   and the token resolves to that same 640, so both paths agree today. */
try{var _bp=parseInt(getComputedStyle(document.documentElement)
  .getPropertyValue('--bp-sm'),10);if(_bp>0)MOB=_bp;}catch(_e){}
function wrap(t,cpl){
  if(!t)return t;
  var w=String(t).split(' '),ln=[],c='';
  for(var i=0;i<w.length;i++){var n=c?c+' '+w[i]:w[i];
    if(n.length>cpl&&c){ln.push(c);c=w[i];}else{c=n;}}
  if(c)ln.push(c);
  return ln.join('<br>');
}
function tune(){
  if(!window.Plotly)return;
  var mob=window.innerWidth<=MOB;
  document.querySelectorAll('.plotly-graph-div').forEach(function(d){
    if(!d._fullLayout)return;                       /* not rendered yet; a later retry gets it */
    var rect=d.getBoundingClientRect();
    if(!rect.width)return;
    /* re-tune when the width BUCKET changes, not on every pixel: 375->414 must
       re-wrap the title, but a scroll-driven 1px reflow must not relayout. */
    var key=(mob?'m':'d')+Math.round(rect.width/30);
    if(d.__tk===key)return;
    var first=!d.__tk; d.__tk=key;
    var o=st.get(d);
    if(!o){var L=d.layout||{},FL=d._fullLayout;
      o={t:(L.title&&L.title.text)||'',
         ts:(FL.title&&FL.title.font&&FL.title.font.size)||15,
         m:{l:FL.margin.l,r:FL.margin.r,t:FL.margin.t,b:FL.margin.b},
         lg:(L.legend?JSON.parse(JSON.stringify(L.legend)):{}),
         h:FL.height,dt:(L.yaxis&&L.yaxis.dtick)||null,sh:d.style.height,
         an:(FL.annotations||[]).map(function(a){return a.visible!==false;}),
         md:(d.data||[]).map(function(t){return t.mode;})};
      st.set(d,o);}
    /* Per-point text labels are unreadable once the plot is 283px wide: the
       risk/return map packs 24 asset labels into that space and 22 of the 24
       pairs overlap. Traces that carry many labels drop to markers-only on
       mobile -- the class legend still identifies them and a tap still shows
       the name on hover. The cutoff is 3, not 6: the 4-label Real Asset trace
       still self-overlapped twice at 283px. */
    function modes(mob){
      var chg=false,arr=(d.data||[]).map(function(t,i){
        var m=o.md[i];
        if(!mob||!m||m.indexOf('text')<0)return m;
        if(!t.text||t.text.length<=3)return m;
        chg=true;return m.replace('+text','').replace('text+','').replace('text','markers');});
      if(mob&&!chg)return;
      if(!mob&&!(o.md||[]).some(function(m){return m&&m.indexOf('text')>=0;}))return;
      try{Plotly.restyle(d,{mode:arr});}catch(e){}
    }
    /* Above the breakpoint a chart can still be narrow: the two-up grid puts a 405px
       chart on a 1024px screen, and "Equity expected return across the valuation-
       reversion dial" ran off its right edge, cropped by the tile (audit 2026-10-01;
       same on regime-line at 864px). Wrap the title against the chart's OWN width.
       Titles carrying markup are left alone -- wrap() splits on spaces. */
    var dw=null;
    if(!mob&&o.t&&o.t.indexOf('<')<0){
      var avail=rect.width-o.m.l-14,pxc=o.ts*0.52;
      if(o.t.length*pxc>avail){dw=wrap(o.t,Math.max(20,Math.floor(avail/pxc)));}
    }
    if(!mob){
      if(first&&!dw)return;                         /* first sight on desktop, fits: nothing to do */
      var dmt=o.m.t+(dw?(dw.split('<br>').length-1)*Math.round(o.ts*1.3):0);
      if(first){                                    /* only the title moves; nothing else to undo */
        try{Plotly.relayout(d,{'title.text':dw,'margin.t':dmt});}catch(e){}
        return;}
      var back={'title.text':dw||o.t,'title.font.size':o.ts,
        'margin.l':o.m.l,'margin.r':o.m.r,'margin.b':o.m.b,
        'margin.t':dmt,
        'legend.font.size':(o.lg.font&&o.lg.font.size)||null,
        'legend.orientation':o.lg.orientation||null,
        'legend.x':(o.lg.x===undefined?null:o.lg.x),
        'legend.xanchor':o.lg.xanchor||null,
        'legend.y':(o.lg.y===undefined?null:o.lg.y),
        'legend.yanchor':o.lg.yanchor||null};
      if(d._fullLayout.xaxis){back['xaxis.tickfont.size']=null;back['xaxis.title.font.size']=null;}
      if(d._fullLayout.yaxis){back['yaxis.tickfont.size']=null;back['yaxis.title.font.size']=null;
        if(d._fullLayout.yaxis.type==='log')back['yaxis.dtick']=o.dt;}
      if(o.h)back['height']=o.h;
      d.style.height=o.sh;
      o.an.forEach(function(v,i){back['annotations['+i+'].visible']=v;});
      modes(false);
      try{Plotly.relayout(d,back);Plotly.Plots.resize(d);}catch(e){}
      return;}
    /* SCALE the generator's margins, never replace them -- the correlation
       heatmap carries 130px left/bottom margins for its asset labels, and a
       flat 44px left margin would clip them off the chart entirely.
       Margins resolve FIRST because the title is left-anchored at margin.l:
       wrapping against the full div width let every title start 35px in and then
       run 12-23px past the right edge, clipped by .tile{overflow:hidden}. */
    var mL=Math.max(34,Math.round(o.m.l*0.72)),mR=Math.max(10,Math.round(o.m.r*0.5));
    /* ~6.3px per char for Inter at 12.5px; the 8px pad keeps it off the edge. */
    var cpl=Math.max(14,Math.floor((rect.width-mL-8)/6.3));
    var txt=wrap(o.t,cpl),lines=txt?txt.split('<br>').length:0;
    var up={'title.text':txt,'title.font.size':12.5,
      'margin.l':mL,'margin.r':mR,
      'margin.t':(lines>1?26+lines*15:Math.max(34,Math.round(o.m.t*0.8))),
      'margin.b':Math.max(34,Math.round(o.m.b*0.82)),
      'legend.font.size':9.5,'legend.orientation':'h',
      'legend.x':0,'legend.xanchor':'left','legend.y':-0.24,'legend.yanchor':'top'};
    if(d._fullLayout.xaxis){up['xaxis.tickfont.size']=10;up['xaxis.title.font.size']=10.5;}
    if(d._fullLayout.yaxis){up['yaxis.tickfont.size']=10;up['yaxis.title.font.size']=10.5;}
    /* config responsive:true only fires on window-resize EVENTS. A page loaded
       straight into a 375px viewport therefore kept Plotly's default 700px SVG,
       visually clipped to the 283px tile, ticks landing 360px past its right
       edge. (Keep this comment free of `name=number` -- confscan greps it.) */
    /* hline annotations ("stress threshold +0.5", "fed funds 3.63%") are drawn
       INSIDE the plot area and sit on top of the data. At 283px they cover the
       series they annotate. The dotted line itself stays -- only its caption is
       hidden, and the surrounding prose already names the thresholds. This is
       the one defect class the clip check cannot see: it never leaves the div. */
    o.an.forEach(function(_,i){up['annotations['+i+'].visible']=false;});
    /* A log y-axis renders minor decade labels (8, 9) that collide once the
       plot is ~340px tall. Decades only on mobile. */
    if(d._fullLayout.yaxis&&d._fullLayout.yaxis.type==='log')up['yaxis.dtick']=1;
    /* Cap height so a chart is not a full portrait screen -- EXCEPT horizontal
       bar charts with many categories, where the height IS the category axis and
       shrinking it makes the labels collide instead. */
    var hbar=(d.data||[]).some(function(t){return t.type==='bar'&&t.orientation==='h';});
    var ncat=hbar?Math.max.apply(null,(d.data||[]).map(function(t){return (t.y||[]).length;})):0;
    if(o.h&&o.h>360&&!(hbar&&ncat>8))up['height']=340;
    modes(true);
    /* to_html writes the layout height INLINE on the div (style height 640px for the
       heatmap). relayout shrinks the SVG, not that box, so the tile kept 300px of blank
       under the matrix on phones (audit 2026-10-01). Move the box with the figure. */
    if(up['height'])d.style.height=up['height']+'px';
    try{Plotly.relayout(d,up);Plotly.Plots.resize(d);}catch(e){}
  });
}
/* Plotly renders from inline scripts and settles asynchronously (the 40x
   under-report the old iframe gate hit), so poll a few times rather than
   trusting one DOMContentLoaded pass. */
function retry(){[0,250,900,2000,3500].forEach(function(ms){setTimeout(tune,ms);});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',retry);else retry();
var tid;function later(){clearTimeout(tid);tid=setTimeout(tune,160);}
window.addEventListener('resize',later);window.addEventListener('orientationchange',later);
})();</script>"""



# --- <link> tags: ONE definition, referenced at every generator's <head> ----------
# Order is load-bearing (see module docstring): tokens, base, THEN style.css.
CSS_LINKS = ('<link rel="stylesheet" href="_design_system/tokens.css">'
             '<link rel="stylesheet" href="_design_system/base.css">')


def emit(docs_dir):
    """Write tokens.css + base.css under `docs_dir/_design_system/`.

    Called from 17_build_site.py beside the existing style.css write, so the files are
    regenerated on every build and `git clean -fd docs` can never orphan them.
    """
    import os
    out = os.path.join(docs_dir, "_design_system")
    os.makedirs(out, exist_ok=True)
    for name, body in (("tokens.css", TOKENS), ("base.css", BASE)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    return out


# =====================================================================================
# 2026-11-10 remake: "Editorial Terminal" (Carlos approved the design canvas, written,
# 2026-11-10 ~01:00: "El diseno quedo muy bien, hazle push, pero manten varias de las
# pestanas ... intenta conseguir imagenes de mejor resolucion").
#
# Decision (DEPLOY_NOTES "why not .ds-v2"): the new look is a site-wide OVERRIDE LAYER
# appended to style.css by 17_build_site.py (ET_CSS below), not a per-page `.ds-v2` opt-in.
# Carlos approved one look for every page at once; the opt-in would need a `<body>` edit in
# every generator, including 19/20/25 which cannot be rendered offline. The Phase-0
# invariants still hold: base.css stays fully scoped and inert (ds_gate S1/S2), the sheets
# keep their order (S4), fonts stay Inter / Spectral / JetBrains Mono (A9), chart code and
# chart heights are untouched, and every new @media rule uses BP_SM / BP_MD / BP_LG.
# Light theme only in this wave (dark mode is not provably safe for every Plotly chart).
# =====================================================================================
ET = {
    "ground": "#F6F5F1", "card": "#FFFFFF", "line": "#E3E1DA", "line_strong": "#C9C6BC",
    "ink": "#0E1726", "sec": "#4A5568", "muted": "#667085", "chip": "#EFEDE6",
    "accent": "#0A2540",               # Oxford blue, kept (REDESIGN_PLAN open item 2)
    "amber": "#B45309",                # highlight: kickers, a hike, the one number to look at
    "up": "#0F5E9C", "down": "#C2410C",  # new components only: bought/up vs sold/down (colour-blind safe)
}
AMBER, UP, DOWN = ET["amber"], ET["up"], ET["down"]
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
# The header's own breakpoint: below it the 7 main tabs + brand + the Research corner no longer fit on one row
# (measured 2026-11-10, Inter loaded: brand 356 px + tabs 634 px + corner 116 px + 2 gaps of 14 px = 1134 px of the
# 1152 px row at the 1200 px content cap, i.e. from 1280 px wide with 18 px to spare), so the header wraps to two
# rows and the tabs scroll with a fade where one is cut. The only breakpoint outside 640 / 900 / 1200.
NAV_BP = 1279


# --- number formats shared by the home summary (17) and Market Intel (30) (round 1, P1) -----------------------
# One definition: 17 must not import 30_market_intel.py as a module (a Market Intel change could then abort the
# load-bearing home build), and the Market Intel tests copy this module with 30, so 30 imports them from here.
def pc(x):
    """A probability as a whole percent, half up: 0.795 -> '80%' (the Fed-path table, the hero stats)."""
    from decimal import ROUND_HALF_UP, Decimal
    return str((Decimal(str(x)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) + "%"


def money(x):
    """A dollar amount in the Congress tables' style: $1.2M / $350K."""
    return f"${x / 1e6:,.1f}M" if abs(x) >= 1e6 else f"${x / 1e3:,.0f}K"


def cma_firm(p):
    """The firm a consensus document belongs to (several documents can share a firm)."""
    return p.get("firm") or p["publisher"]


def cma_firms(publishers):
    """The distinct firms in the Street consensus (the Market Intel lede's 'N asset managers and banks')."""
    return sorted({cma_firm(p) for p in publishers})

# --- image assets: source of truth in <repo>/assets (committed), emitted into docs/ ---------
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
ASSET_SRC = _os.path.join(_ROOT, "assets", "img")
ASSET_URL = "assets/img"                     # relative to docs/ (every page sits at docs/ root)
HERO_KEYS = ("cliffs", "cliffs_detail", "pillars", "pillars_base")
# Round 1 (2026-11-10 review, V3/V13): phones get 9:16 PORTRAIT crops (hero_<k>_p720/p1080.webp): their heroes are
# portrait boxes, and a 960 px 16:9 source was stretched 3.2-3.8x there. Larger screens get 16:9 WebP 1600-3840, with
# a 2880 step for 1440-1512 px screens at 2x (they took the 3840 file before). The 960 WebP is no longer published.
HERO_PORTRAIT = (720, 1080)                  # phone srcset (portrait, 9:16)
HERO_WEBP = (1600, 2560, 2880, 3840)         # srcset widths published per hero (landscape, 16:9)
HERO_JPG = (960, 1600, 2560)                 # fallback; the 3840 JPEGs stay out (pillars > 1.2 MB)
# A 16:9 image covering a hero box that is taller than 16:9 (tablets) is drawn wider than the viewport: ask for more.
HERO_SIZES = f"(max-width: {BP_MD}px) 150vw, 100vw"
PHOTO = ("carlos_duarte_640x800.jpg", "carlos_duarte_1200x1500.jpg")


def _credits():
    import json
    try:
        with open(_os.path.join(_ROOT, "assets", "credits.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def hero_files(key):
    return ([f"hero_{key}_p{w}.webp" for w in HERO_PORTRAIT] + [f"hero_{key}_{w}.webp" for w in HERO_WEBP]
            + [f"hero_{key}_{w}.jpg" for w in HERO_JPG])


def all_asset_names():
    """Every image file the site publishes (the deploy emits exactly these; ds_gate R4 checks the same set)."""
    return [n for k in HERO_KEYS for n in hero_files(k)] + list(PHOTO)


def emit_assets(docs_dir, names):
    """Copy assets/img/<name> -> docs/assets/img/<name>, byte-identical and idempotent (a file whose
    bytes already match is not rewritten, so a re-render changes nothing in git). Called by EVERY
    generator whose page references an image, so one job's render (e.g. the 07:00 consensus job,
    which runs 30_market_intel.py alone) is self-sufficient. Returns True only when every source
    exists; False -> the caller renders its hero without an image (CI / test sandboxes)."""
    import shutil
    ok = True
    out = _os.path.join(docs_dir, *ASSET_URL.split("/"))
    for n in names:
        src = _os.path.join(ASSET_SRC, n)
        if not _os.path.isfile(src):
            ok = False
            continue
        dst = _os.path.join(out, n)
        try:
            with open(src, "rb") as a, open(dst, "rb") as b:
                if a.read() == b.read():
                    continue
        except OSError:
            pass
        _os.makedirs(out, exist_ok=True)
        tmp = dst + ".tmp"
        shutil.copyfile(src, tmp)
        _os.replace(tmp, dst)
    return ok


def _esc(s):
    import html
    return html.escape(str(s), quote=True)


def hero_credit(key):
    """'Image: <title>, cropped · <credit> · CC BY 4.0' with links to the source page and the licence."""
    c = (_credits().get("heroes") or {}).get(key)
    if not c:
        return ""
    return (f'Image: <a href="{_esc(c["source"])}" rel="noopener">{_esc(c["title"])}</a>, cropped &middot; '
            f'{_esc(c["credit"])} &middot; <a href="{LICENSE_URL}" rel="noopener license">{_esc(c["license"])}</a>')


def hero(key, inner, docs_dir, pos="center 40%", cls=""):
    """An image hero: JWST crop under a ~64% dark layer, never behind a chart, credit line visible.
    <picture>: phones get a 9:16 portrait WebP (720 / 1080; their hero box is portrait), larger screens
    the 16:9 WebP 1600-3840, JPEG fallback 960-2560. Without the source files (test sandbox) it degrades
    to a plain dark hero with the same text and no credit. `inner` is the hero's own HTML (h1, lede, as-of
    chip ...)."""
    have = bool(_credits().get("heroes", {}).get(key)) and emit_assets(docs_dir, hero_files(key))
    if not have:
        return (f'<section class="hero hero--img hero--plain {cls}" data-hero="{key}">'
                f'<div class="container hero-in">{inner}</div></section>')
    u = lambda w, ext: f"{ASSET_URL}/hero_{key}_{w}.{ext}"
    por = ", ".join(f"{u(f'p{w}', 'webp')} {w}w" for w in HERO_PORTRAIT)
    webp = ", ".join(f"{u(w, 'webp')} {w}w" for w in HERO_WEBP)
    jpg = ", ".join(f"{u(w, 'jpg')} {w}w" for w in HERO_JPG)
    return (f'<section class="hero hero--img {cls}" data-hero="{key}">'
            f'<picture class="hero-bg">'
            f'<source type="image/webp" media="(max-width: {BP_SM}px)" srcset="{por}" sizes="100vw">'
            f'<source type="image/webp" srcset="{webp}" sizes="{HERO_SIZES}">'
            f'<img src="{u(1600, "jpg")}" srcset="{jpg}" sizes="{HERO_SIZES}" width="1600" height="900" alt="" '
            f'fetchpriority="high" decoding="async" style="object-position:{pos}"></picture>'
            f'<div class="hero-shade" aria-hidden="true"></div>'
            f'<div class="container hero-in">{inner}</div>'
            f'<p class="container hero-credit"><span>{hero_credit(key)}</span></p></section>')


def credits_footer(*keys):
    """The footer line every page with an image carries (CC BY 4.0 wants it findable, not only on the image)."""
    parts = [hero_credit(k) for k in keys if hero_credit(k)]
    return (f'<p class="credits">{" &middot; ".join(parts)}</p>' if parts else "")


def photo(docs_dir, cls="about-photo"):
    """Carlos's portrait (EXIF-free 4:5 copies), lazy, with intrinsic size so nothing shifts on load."""
    if not emit_assets(docs_dir, PHOTO):
        return ""
    a, b = PHOTO
    return (f'<img class="{cls}" src="{ASSET_URL}/{a}" srcset="{ASSET_URL}/{a} 640w, {ASSET_URL}/{b} 1200w" '
            f'sizes="(max-width: {BP_SM}px) 70vw, 260px" width="640" height="800" alt="Carlos Duarte" '
            f'loading="lazy" decoding="async">')


# --- the override layer (appended to style.css by 17_build_site.py) ------------------------
ET_CSS = r"""
/* ============================================================================
   EDITORIAL TERMINAL (2026-11-10). GENERATED by scripts/design_system.py ET_CSS and
   appended by 17_build_site.py: it overrides the legacy rules above, so removing this
   block restores the previous look. Light theme only. Warm ground, white cards with
   soft corners, Oxford-blue accent, amber highlight, Spectral / Inter / JetBrains Mono.
   ============================================================================ */
:root{
  --bg:#F6F5F1; --panel:#FFFFFF; --ink:#0E1726; --sec:#4A5568; --muted:#667085;
  --line:#E3E1DA; --line-strong:#C9C6BC; --chip:#EFEDE6;
  --accent:#0A2540; --accent-tint:rgba(10,37,64,.05); --accent-line:rgba(10,37,64,.28);
  --amber:#B45309; --up:#0F5E9C; --down:#C2410C;
  --r-card:16px; --r-sm:12px; --lift:0 8px 22px rgba(14,23,38,.08);
  --wrap:min(1200px,94vw);
}
body{background:var(--bg);color:var(--ink)}
::selection{background:rgba(180,83,9,.16)}
a:focus-visible,button:focus-visible,summary:focus-visible,input:focus-visible,select:focus-visible,[tabindex]:focus-visible{
  outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}
/* the sticky header's height (JS keeps --hdr exact; these are the no-JS / first-paint values): anchors land below
   it (scroll-padding: #sources, #about, #summary ...), and sticky table heads sit under it, not behind it */
:root{--hdr:65px}
html{scroll-padding-top:calc(var(--hdr) + 14px)}
.ptable thead th{top:calc(var(--hdr) - 1px)}
/* while the page boots, the header does not animate (the active tab / corner state is set by the script) */
.js:not(.ready) .shell *{transition:none!important}

/* ---- header: brand, the main tabs, the Research corner ---- */
.shell{background:var(--bg);border-bottom:1px solid var(--line)}
.shell-in{max-width:var(--wrap);min-height:64px;gap:8px 14px;flex-wrap:nowrap}
.brand{display:inline-flex;align-items:center;gap:10px;white-space:nowrap;font-size:16.5px;letter-spacing:.02em}
.brand::before{content:"CD";display:inline-flex;align-items:center;justify-content:center;flex:none;
  width:30px;height:30px;border-radius:8px;background:var(--accent);color:#fff;
  font:500 15px/1 var(--serif);letter-spacing:0}
.brand b{color:var(--sec);font-weight:400}
nav.tabs{display:flex;gap:0;margin-left:auto;flex-wrap:nowrap;min-width:0;overflow-x:auto;
  scrollbar-width:none;-ms-overflow-style:none}
nav.tabs::-webkit-scrollbar{display:none}
nav.tabs a{flex:0 0 auto;white-space:nowrap;min-height:44px;padding:0 9px;font-size:13.5px;font-weight:500;
  color:var(--sec);border-bottom:2px solid transparent;letter-spacing:.005em}
nav.tabs a:hover{color:var(--ink);border-bottom-color:var(--line-strong)}
nav.tabs a.active{color:var(--ink);border-bottom-color:var(--accent)}
nav.tabs a:focus-visible{outline-offset:-3px}
/* the fade says "more tabs this way": set by the header script whenever the row can scroll (fl / fr = a tab is cut
   on the left / right); without JS the right-edge fade below the header breakpoint stays */
nav.tabs.fr{-webkit-mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent);
  mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent)}
nav.tabs.fl{-webkit-mask-image:linear-gradient(to left,#000 calc(100% - 28px),transparent);
  mask-image:linear-gradient(to left,#000 calc(100% - 28px),transparent)}
nav.tabs.fl.fr{-webkit-mask-image:linear-gradient(to right,transparent,#000 28px,#000 calc(100% - 28px),transparent);
  mask-image:linear-gradient(to right,transparent,#000 28px,#000 calc(100% - 28px),transparent)}
.rcn{flex:none;display:block}
.rc{position:relative}
.rc>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:8px;min-height:44px;
  padding:0 14px 0 12px;border:1px solid var(--accent-line);border-radius:999px;background:var(--panel);
  color:var(--accent);font-size:13.5px;font-weight:500;white-space:nowrap;user-select:none;
  transition:background .15s ease-out,color .15s ease-out,border-color .15s ease-out}
.rc>summary::-webkit-details-marker{display:none}
.rc>summary::marker{content:""}
.rc>summary svg{flex:none}
.rc>summary .car{transition:transform .15s ease-out}
.rc[open]>summary .car{transform:rotate(180deg)}
.rc>summary:hover{border-color:var(--accent)}
.rc[open]>summary,.rc.active>summary{background:var(--accent);color:#fff;border-color:var(--accent)}
/* the menu scrolls inside itself when the viewport is short (landscape phones): every link stays reachable */
.rc-menu{position:absolute;right:0;top:calc(100% + 8px);width:min(390px,calc(100vw - 32px));z-index:90;
  background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:10px;
  box-shadow:0 18px 44px rgba(14,23,38,.16);max-height:calc(100vh - var(--hdr) - 16px);
  max-height:calc(100dvh - var(--hdr) - 16px);overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
.rc-k{margin:4px 10px 8px;font-size:11.5px;font-weight:500;letter-spacing:.09em;text-transform:uppercase;color:var(--amber)}
.rc-menu a{display:block;padding:9px 10px;border-radius:10px;text-decoration:none;color:var(--ink);border-bottom:0}
.rc-menu a b{display:block;font-size:14.5px;font-weight:500}
.rc-menu a span{display:block;font-size:12.5px;color:var(--sec);line-height:1.4;margin-top:1px}
.rc-menu a:hover,.rc-menu a[aria-current="page"]{background:var(--accent-tint)}
.rc-menu a[aria-current="page"] b::after{content:" \00b7  you are here";font-weight:400;font-size:12px;color:var(--amber)}
.rc-menu a.rc-src{border-top:1px solid var(--line);border-radius:0 0 10px 10px;margin-top:6px;padding-top:11px}
@media(max-height:520px) and (min-width:560px){
  .rc-menu{width:min(640px,calc(100vw - 32px));display:grid;grid-template-columns:1fr 1fr;column-gap:6px}
  .rc-k{grid-column:1 / -1}
  .rc-menu a{padding:7px 10px}
  .rc-menu a.rc-src{grid-column:1 / -1;border-radius:0 0 10px 10px}
}
@media(max-width:__NAV__px){
  :root{--hdr:105px}
  .shell-in{flex-wrap:wrap;padding:8px 20px 0;min-height:0}
  .brand{order:1}
  .rcn{order:2;margin-left:auto}
  nav.tabs{order:3;width:100%;margin:0 -4px}
  html:not(.js) nav.tabs{-webkit-mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent);
            mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent)}
}
@media(max-width:__SM__px){
  .shell-in{padding:8px 16px 0;gap:6px 10px}
  .brand{font-size:14.5px;gap:8px}
  .brand::before{width:26px;height:26px;font-size:13px;border-radius:7px}
  .rc>summary{padding:0 11px 0 10px;font-size:13px}
  nav.tabs a{font-size:13px;padding:0 8px}
}
@media(max-width:400px){.brand{font-size:0;gap:8px}.brand::after{content:"Carlos Duarte";font:500 14.5px var(--serif);letter-spacing:.02em}}
@media(max-width:340px){:root{--hdr:135px}}

/* ---- heroes: plain (warm ground) and image (JWST under a dark layer) ---- */
.hero{background:var(--bg);border-bottom:1px solid var(--line)}
.hero .container,.hero-in{max-width:var(--wrap)}
.hero h1{font-weight:500}
.hero .asof{display:inline-block;margin-top:1.4rem;padding:6px 14px;border:1px solid var(--line);border-radius:14px;
  background:var(--chip);color:var(--sec);font-size:12px;line-height:1.6;max-width:100%}
.hero .asof::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--up);
  margin-right:8px;vertical-align:0}
.hero--img{position:relative;overflow:hidden;background:#05070d;color:#F3F5F9;border-bottom:0;
  padding:clamp(64px,9vw,112px) 0 0}
.hero--img .hero-bg,.hero--img .hero-bg img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
/* the ~64% layer, a little deeper under the text column (left): small text keeps >= 4.5:1 even over a bright star */
.hero-shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(5,8,16,.26),rgba(5,8,16,.18) 55%,
  rgba(5,8,16,0) 85%),rgba(5,8,16,.64)}
.hero--img .hero-in{position:relative;z-index:1;padding-bottom:8px}
.hero--img h1{color:#F3F5F9}
.hero--img .lede{color:#D9DFEA;text-shadow:0 1px 2px rgba(0,0,0,.55)}
.hero--img .lede a,.hero--img .hero-in a:not(.btn){color:#BFD4FF}
.hero--img .asof{background:rgba(5,8,16,.62);border-color:rgba(255,255,255,.22);color:#DCE2EC}
.hero--img .asof::before{background:#7CC4FF}
.hero--plain{padding-bottom:36px}
.hero--img+main{padding-top:clamp(36px,5vw,56px)}
.hero-credit{position:relative;z-index:1;margin:26px auto 0;padding-bottom:12px;text-align:right;
  font-size:11.5px;line-height:1.45;color:#C9D1DD}
.hero-credit>span{background:rgba(5,8,16,.66);padding:2px 8px;border-radius:6px;-webkit-box-decoration-break:clone;
  box-decoration-break:clone}
.hero-credit a{color:#E1E6EE;text-decoration:underline;text-underline-offset:2px}
.kicker{margin:0 0 .5rem;font-size:12px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:var(--amber)}
.hero--img .kicker{color:#F7C47A;text-shadow:0 1px 2px rgba(0,0,0,.6)}
.hero-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr));gap:12px;margin-top:28px}
.hero-stat{background:rgba(8,12,22,.74);border:1px solid rgba(255,255,255,.18);border-radius:14px;padding:14px 16px;
  text-decoration:none;color:#F3F5F9;display:block}
a.hero-stat:hover{border-color:rgba(255,255,255,.45)}
.hero-stat .v{display:block;font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:28px;font-weight:500;line-height:1.15}
.hero-stat .v.amb{color:#F5B860}.hero-stat .v.up{color:#7CC4FF}
.hero-stat .l{display:block;font-size:13px;color:#CBD3E1;margin-top:3px;line-height:1.4}
.cta{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}
.btn{border-radius:10px;border:1px solid var(--accent)}
.btn-ghost{background:transparent;color:#F3F5F9;border:1px solid rgba(255,255,255,.4)}
.btn-ghost:hover{background:rgba(255,255,255,.08)}
.hero--img .btn:not(.btn-ghost){background:#F3F5F9;color:var(--accent);border-color:#F3F5F9}
.hero--img .btn:not(.btn-ghost):hover{background:#fff}

/* ---- blocks, cards, tiles ---- */
main{padding-top:3.2rem}
.block>h2{font-size:clamp(20px,2.1vw,25px);border-bottom-color:var(--line)}
.note{color:var(--sec)}
body .tile,body .twonote>div,body .odd,body .dv,body .prelim,body .archive-note{border-radius:var(--r-card);border-color:var(--line)}
body .metric,body .scard,body .btcard,body .proj-card{border-radius:14px;border-color:var(--line)}
body .btcard{border-top-width:3px}
.metric,.scard,.btcard,.proj-card,.xcard{transition:transform .15s ease-out,border-color .15s ease-out,
  box-shadow .15s ease-out,background .15s ease-out}
.metric:hover,.scard:hover,.btcard:hover,.proj-card:hover,a.xcard:hover,.xcard.hov:hover{
  transform:translateY(-2px);border-color:var(--accent-line);box-shadow:var(--lift);background:var(--panel)}
.mk{color:var(--sec)}
.mh{color:var(--sec)}
.asof{color:var(--muted)}
.caption{color:var(--sec)}
.ccy-toggle,.btranges{border-radius:999px;overflow:hidden;border-color:var(--line-strong)}
.ccy-toggle button,.btr{min-height:36px}
.ccy{border-radius:999px;border-color:var(--line)}
.tsearch{border-radius:10px}
.pill{border-radius:999px}
.ptable th{color:var(--sec)}
.shell-foot{background:var(--bg);color:var(--sec)}
.shell-foot .credits{margin-top:.6rem;font-size:12px;color:var(--muted)}
.shell-foot .credits a{color:var(--sec)}

/* ---- generic new components (summary cards, tabs in a page, bars) ---- */
.xgrid{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr))}
.xcard{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-card);padding:22px;
  display:flex;flex-direction:column;gap:12px;min-width:0;color:var(--ink);text-decoration:none}
.xcard .xk{display:flex;align-items:center;gap:10px;margin:0;font-size:12.5px;font-weight:500;letter-spacing:.06em;
  text-transform:uppercase;color:var(--sec)}
.xcard .xk i{font-style:normal;width:26px;height:26px;border-radius:50%;background:var(--chip);color:var(--ink);
  display:inline-flex;align-items:center;justify-content:center;font:500 12px var(--mono);letter-spacing:0}
.xcard .xh{margin:0;font-family:var(--serif);font-size:19px;line-height:1.35}
.xcard .xn{margin:0;font-size:12.5px;color:var(--sec)}
.xcard .xbig{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:28px;font-weight:500;color:var(--accent);line-height:1.1}
.xcard .xgo{margin-top:auto;font-size:14px;font-weight:500;color:var(--accent)}
.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.kpi{border:1px solid var(--line);border-radius:12px;padding:12px;min-width:0}
.kpi b{display:block;font:500 20px/1.15 var(--mono);font-variant-numeric:tabular-nums}
.kpi span{display:block;margin-top:3px;font-size:11px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;color:var(--sec)}
.brow{display:grid;grid-template-columns:minmax(0,9.5em) minmax(0,1fr) 3.6em;gap:10px;align-items:center;font-size:13px}
.brow .lb{color:var(--sec);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.brow .v{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.bar{height:8px;border-radius:5px;background:var(--chip);overflow:hidden}
.bar i{display:block;height:100%;border-radius:5px;background:var(--accent)}
.bar i.mute{background:#9AA5B4}
.bars{display:flex;flex-direction:column;gap:8px}
.wline{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding-bottom:10px;border-bottom:1px solid var(--line)}
.wline span{font-size:13px;color:var(--sec)}
.wline b{font:500 21px/1.1 var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.wline b.amb{color:var(--amber)}
.wline b.sm{font-size:16px}
.gauge{position:relative;height:10px;border-radius:6px;margin-top:8px;
  background:linear-gradient(90deg,#0F5E9C,#9AA5B4 50%,#C2410C)}
.gauge i{position:absolute;top:-4px;width:4px;height:18px;border-radius:2px;background:var(--ink);margin-left:-2px}
.gends{display:flex;justify-content:space-between;font-size:11px;color:var(--sec);margin-top:4px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:clamp(18px,3vw,28px)}
.ptabs{display:flex;flex-wrap:wrap;gap:8px}
.ptabs [role="tab"],.vtabs a,.chipbtn{font:500 14px var(--sans);min-height:44px;padding:0 18px;border-radius:999px;
  border:1px solid var(--line-strong);background:transparent;color:var(--sec);cursor:pointer;text-decoration:none;
  display:inline-flex;align-items:center;white-space:nowrap}
.ptabs [role="tab"]:hover,.vtabs a:hover,.chipbtn:hover{border-color:var(--ink);color:var(--ink)}
.ptabs [role="tab"][aria-selected="true"],.vtabs a[aria-selected="true"],.chipbtn[aria-pressed="true"]{
  background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chipbtn{min-height:44px;padding:0 14px;font-size:13px}
.tpanel{margin-top:22px}
.tpanel>h3.tph{font:500 15px var(--sans);margin:0 0 12px;color:var(--ink)}
.js .tpanel>h3.tph{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.mtiles{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(170px,100%),1fr))}
.mtile{border:1px solid var(--line);border-radius:14px;padding:16px;min-width:0}
.mtile .k{margin:0;font-size:11px;font-weight:500;letter-spacing:.07em;text-transform:uppercase;color:var(--sec)}
.mtile .v{margin:6px 0 2px;font:500 25px/1.15 var(--mono);font-variant-numeric:tabular-nums}
.mtile .d{margin:0;font-size:12px;color:var(--sec)}
.fed{display:flex;flex-direction:column;gap:12px}
.fedrow{display:grid;grid-template-columns:minmax(0,7em) minmax(0,1fr) minmax(0,8.5em);gap:12px;align-items:center}
.fedrow .m{font-size:14px;font-weight:500}
.fedrow .t{font:400 12.5px var(--mono);color:var(--sec);text-align:right;white-space:nowrap}
.stack{display:flex;height:24px;border-radius:8px;overflow:hidden;background:var(--chip)}
.stack i{display:block;height:100%}
.stack .c,.lg .c{background:var(--up)}.stack .h,.lg .h{background:#9AA5B4}.stack .k,.lg .k{background:var(--amber)}
.lg{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;color:var(--sec)}
.lg span{display:inline-flex;align-items:center;gap:6px}
.lg span i{width:12px;height:12px;border-radius:3px;display:inline-block}
.flow{display:grid;grid-template-columns:minmax(0,10em) minmax(0,1fr) minmax(0,1fr) 5.2em;gap:8px;align-items:center;font-size:13px}
.flow .lb{color:var(--sec);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.flow .n,.flow .p{display:flex;height:14px}
.flow .n{justify-content:flex-end}
.flow .n i{background:var(--down);border-radius:4px 0 0 4px;display:block}
.flow .p i{background:var(--up);border-radius:0 4px 4px 0;display:block}
.flow .v{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.picks5{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(170px,100%),1fr))}
.pick{border:1px solid var(--line);border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:3px;text-decoration:none;color:var(--ink)}
.pick .r{font:400 12px var(--mono);color:var(--sec)}
.pick .t{font:500 21px var(--mono)}
.pick .s{font-size:13px;color:var(--sec)}
.about-flex{display:flex;flex-wrap:wrap;gap:28px;align-items:flex-start}
.about-photo{flex:0 0 auto;width:min(240px,70vw);height:auto;aspect-ratio:4/5;object-fit:cover;border-radius:18px;
  border:1px solid var(--line);background:var(--chip)}
.about-text{flex:999 1 420px;min-width:0}
.vtabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 1.8rem}
.vtabs .vt-out{border-style:dashed}
.js .vgroup[hidden]{display:none}
.sidefilter{margin:0 0 10px}
@media(max-width:__SM__px){
  /* phones: the text spans the whole hero, so the layer is uniform and a little deeper; the hero stays about one
     screen tall (stats 2 x 2, CTAs side by side, the as-of chip in the sans at 11.5 px) */
  .hero-shade{background:rgba(5,8,16,.72)}
  .hero--img{padding-top:34px}
  .hero--img h1{font-size:25px}
  .hero--img .lede{font-size:15px;margin-top:.8rem}
  .hero .asof{margin-top:1rem;padding:5px 11px;font-family:var(--sans);font-size:11.5px;line-height:1.5;letter-spacing:0}
  .hero-stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:18px}
  .hero-stat{padding:10px 12px}
  .hero-stat .v{font-size:21px}
  .hero-stat .l{font-size:12px}
  .cta{gap:6px;margin-top:18px;flex-wrap:nowrap}
  .cta .btn{display:inline-flex;align-items:center;justify-content:center;flex:1 1 auto;min-height:44px;padding:4px 8px;
    font-size:13.5px;line-height:1.25;white-space:normal;text-align:center}
  .hero-credit{margin-top:16px;font-size:11px}
  /* the home's "my book vs the S&P" panel restates the Hold card that opens the page right below the hero: on a
     phone it would push the page a full screen down, so it is shown from 641 px up only */
  .hero-panel{display:none}
  .xcard{padding:18px}
  .fedrow{grid-template-columns:minmax(0,5.6em) minmax(0,1fr);row-gap:4px}
  .fedrow .t{grid-column:1 / -1;text-align:left}
  .flow{grid-template-columns:minmax(0,7.5em) minmax(0,1fr) minmax(0,1fr) 4.6em;font-size:12px}
  .brow{grid-template-columns:minmax(0,7.5em) minmax(0,1fr) 3.4em}
  .about-photo{width:min(220px,64vw)}
}
.hero-grid{display:flex;flex-wrap:wrap;gap:28px 40px;align-items:flex-end}
.hero-main{flex:999 1 520px;min-width:0}
.hero-main h1{max-width:20em}
.hero-panel{flex:1 1 300px;min-width:0;background:rgba(8,12,22,.74);border:1px solid rgba(255,255,255,.18);
  border-radius:16px;padding:20px;color:#F3F5F9}
.hero-panel .hp-k{display:flex;justify-content:space-between;gap:10px;margin:0;font-size:12px;font-weight:500;
  letter-spacing:.08em;text-transform:uppercase;color:#CBD3E1}
.hero-panel .hp-big{margin:12px 0 2px;font:500 40px/1.05 var(--mono);font-variant-numeric:tabular-nums;color:#7CC4FF}
.hero-panel .hp-big.neg{color:#FFB07C}
.hero-panel .hp-sub{margin:0 0 14px;font-size:14px;color:#CBD3E1}
.hero-panel .hp-row{display:flex;justify-content:space-between;font-size:13px;margin-top:10px}
.hero-panel .hp-row b{font:500 13px var(--mono)}
.hero-panel .hp-bar{height:10px;border-radius:6px;background:rgba(255,255,255,.1);margin-top:6px;overflow:hidden}
.hero-panel .hp-bar i{display:block;height:100%;border-radius:6px;background:#8DB8FF}
.hero-panel .hp-bar i.b{background:#6B7891}
.hero-panel .hp-foot{margin:14px 0 0;font-size:12px;color:#CBD3E1}
.hero-panel .hp-foot b{font:500 12px var(--mono);color:#F3F5F9}
.jsonly{display:none!important}
.js .jsonly{display:inline-flex!important}
.today-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:16px}
.today-head h2{margin:0;font:500 clamp(22px,2.4vw,30px)/1.2 var(--serif);border:0;padding:0}
.sec-h{margin:0 0 18px}
.sec-h h2{margin:0;font:500 clamp(24px,2.8vw,34px)/1.2 var(--serif);border:0;padding:0}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}
  .metric:hover,.scard:hover,.btcard:hover,.proj-card:hover,a.xcard:hover,.xcard.hov:hover{transform:none}
}
@media print{.rcn,.rc,.ptabs,.vtabs,.hero-bg,.hero-shade{display:none!important}
  .hero--img{background:#fff;color:#111}.hero--img h1,.hero--img .lede{color:#111}}
""".replace("__SM__", str(BP_SM)).replace("__MD__", str(BP_MD)).replace("__LG__", str(BP_LG)).replace(
    "__NAV__", str(NAV_BP))


# --- in-page tabs (the home's "Today" panel, Market Intel's views). Progressive: without JS every panel is
# shown, each under its own heading; with JS one panel at a time, ARIA tablist + arrow keys / Home / End.
# A tablist with data-tabs="hash" uses anchors as tabs: a deep link (#outlook) or an in-page link opens the
# view that holds the target. Every tab carries aria-controls = its panel's id.
TABS_JS = r"""<script>(function(){function wire(tl){var tabs=[].slice.call(tl.querySelectorAll('[role="tab"]'));
var hash=tl.getAttribute('data-tabs')==='hash';function pan(t){return document.getElementById(t.getAttribute('aria-controls'));}
function sel(t,focus){tabs.forEach(function(x){var on=x===t;x.setAttribute('aria-selected',on?'true':'false');x.tabIndex=on?0:-1;
var p=pan(x);if(p)p.hidden=!on;});if(focus)t.focus();}
function byTarget(id){var el=id&&document.getElementById(id);if(!el)return null;
for(var i=0;i<tabs.length;i++){var p=pan(tabs[i]);if(p&&p.contains(el))return tabs[i];}return null;}
tabs.forEach(function(t,i){t.addEventListener('click',function(ev){ev.preventDefault();sel(t);
if(hash){try{history.replaceState(null,'',t.getAttribute('href'));}catch(_e){}}});
t.addEventListener('keydown',function(ev){var j=-1;if(ev.key==='ArrowRight')j=(i+1)%tabs.length;
else if(ev.key==='ArrowLeft')j=(i-1+tabs.length)%tabs.length;else if(ev.key==='Home')j=0;else if(ev.key==='End')j=tabs.length-1;
if(j>=0){ev.preventDefault();sel(tabs[j],true);}});});
var init=(hash&&byTarget(decodeURIComponent(location.hash.slice(1))))||tabs[0];sel(init);
if(hash){window.addEventListener('hashchange',function(){var id=decodeURIComponent(location.hash.slice(1)),t=byTarget(id);
if(t){sel(t);var el=document.getElementById(id);if(el&&el.scrollIntoView)el.scrollIntoView();}});}}
[].forEach.call(document.querySelectorAll('[role="tablist"][data-tabs]'),wire);})();</script>"""
