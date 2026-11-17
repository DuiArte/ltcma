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
# translucent fills of the palette above (areas under a line, distance below a running peak), named once so a
# theme can restyle them with the series they belong to (2026-11-10, portfolio entries chart)
TINT = {"navy": "rgba(10,37,64,0.07)",          # NAVY: the book's drawdown area (portfolio chart 1b)
        "navy_peak": "rgba(10,37,64,0.12)",     # NAVY: the book's below-its-peak area (portfolio entries chart)
        "bench": "rgba(154,165,177,0.20)",      # BENCH: the S&P 500's below-peak area
        "teal": "rgba(15,118,110,0.08)"}        # TEAL: capital deployed (area under the cost basis)
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
    """Write tokens.css + base.css (+ theme.css, the dark mode) under `docs_dir/_design_system/`.

    Called from 17_build_site.py beside the existing style.css write, so the files are
    regenerated on every build and `git clean -fd docs` can never orphan them.
    """
    import os
    out = os.path.join(docs_dir, "_design_system")
    os.makedirs(out, exist_ok=True)
    # theme.css (2026-11-10 wave r2): the dark values of every token; linked only by pages themed() rewrote
    for name, body in (("tokens.css", TOKENS), ("base.css", BASE), ("theme.css", THEME_CSS)):
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
# Dark mode (wave r2, 2026-11-10): see the THEME block at the end of this module (themed(), THEME_CSS,
# CHART_DARK, THEME_JS). The light theme is this layer, unchanged.
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
    """A dollar amount in the Congress tables' style: $1.2M / $350K; a sale total reads −$2.4M (a real minus
    sign before the dollar sign), a non-zero total under $500 "<$1K", none "$0" (wave r3, 2026-11-10: it printed
    "$-2.4M" and "$0K"). Shared by the home (17) and the Congress page (30), so the two always agree (R6)."""
    a = abs(x)
    if a == 0:
        return "$0"
    s = "<$1K" if a < 500 else (f"${a / 1e6:,.1f}M" if a >= 999_500 else f"${a / 1e3:,.0f}K")
    return "\u2212" + s if x < 0 else s


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
HERO_KEYS = ("cliffs", "pillars", "zs7", "hh4647", "ngc6822", "ngc6440", "earth_night")
# wave r3 (Carlos, written 2026-11-10 ~15:00, "Dale play a todo" on the hero plan): ONE photograph per page. The two
# second crops of the remake are retired (their files leave assets/img and docs/assets/img with the r3 deploy).
RETIRED_HERO_KEYS = ("cliffs_detail", "pillars_base")
# page -> (hero key, object-position). The generators call hero_for(page, ...); the deploy and the previews of the
# pages 19 / 20 / 25 render (they cannot run offline) put the same hero on a committed page with hero_retrofit().
# Every stock page (stock_<TICKER>.html) shares the Stock Research photograph (STOCK_PAGE). Reading pages stay plain.
PAGE_HEROES = {
    "index.html": ("cliffs", "center 38%"),
    "portfolio.html": ("zs7", "center 40%"),
    "ltcma-consensus.html": ("hh4647", "center 30%"),
    "congressional-activity.html": ("ngc6822", "center 40%"),
    "research-library.html": ("pillars", "center 40%"),
    "stocks.html": ("ngc6440", "center 40%"),
    "regime.html": ("earth_night", "center 50%"),
}
STOCK_PAGE = r"stock_[A-Za-z0-9.\-]+\.html"
STOCK_HERO = ("ngc6440", "center 40%")
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


def hero_widths(key):
    """(portrait, webp, jpg) widths published for a key: credits.json `widths` (wave r3: per key, never wider than the
    cut), else the remake's defaults."""
    w = ((_credits().get("heroes") or {}).get(key) or {}).get("widths") or {}
    return (tuple(w.get("portrait", HERO_PORTRAIT)), tuple(w.get("webp", HERO_WEBP)), tuple(w.get("jpg", HERO_JPG)))


def hero_files(key):
    por, webp, jpg = hero_widths(key)
    return ([f"hero_{key}_p{w}.webp" for w in por] + [f"hero_{key}_{w}.webp" for w in webp]
            + [f"hero_{key}_{w}.jpg" for w in jpg])


def page_hero(page):
    """(key, object-position) of the page's photograph, or None for a page without an image hero."""
    if page in PAGE_HEROES:
        return PAGE_HEROES[page]
    if _re.fullmatch(STOCK_PAGE, page or ""):
        return STOCK_HERO
    return None


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
    """'Image: <title>, cropped · <credit> · <licence>' with links to the source page and (when the licence has one:
    CC BY 4.0) the licence. Wave r3: the licence and its link come from credits.json per key (NASA media is public
    domain: no licence link; the credit is still shown)."""
    c = (_credits().get("heroes") or {}).get(key)
    if not c:
        return ""
    lu = c.get("license_url", LICENSE_URL if c.get("license") == "CC BY 4.0" else None)
    lic = (f'<a href="{_esc(lu)}" rel="noopener license">{_esc(c["license"])}</a>' if lu else _esc(c["license"]))
    return (f'Image: <a href="{_esc(c["source"])}" rel="noopener">{_esc(c["title"])}</a>, cropped &middot; '
            f'{_esc(c["credit"])} &middot; {lic}')


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
    pw, ww, jw = hero_widths(key)
    por = ", ".join(f"{u(f'p{w}', 'webp')} {w}w" for w in pw)
    webp = ", ".join(f"{u(w, 'webp')} {w}w" for w in ww)
    jpg = ", ".join(f"{u(w, 'jpg')} {w}w" for w in jw)
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


def hero_for(page, inner, docs_dir, cls=""):
    """The page's own photograph (PAGE_HEROES) as an image hero: what every generator with a hero calls (wave r3)."""
    key, pos = page_hero(page)
    return hero(key, inner, docs_dir, pos=pos, cls=cls)


def credits_for(page):
    """The footer credit of the page's photograph."""
    ph = page_hero(page)
    return credits_footer(ph[0]) if ph else ""


_HERO_IMG = _re.compile(r'<section class="hero hero--img ?([^"]*)" data-hero="([^"]+)">(.*?)</section>', _re.S)
_HERO_PLAIN = _re.compile(r'<section class="hero"><div class="container">(.*?)</div></section>', _re.S)
_FOOT = _re.compile(r'(<footer class="shell-foot"><div class="container">)(.*?)(</div></footer>)', _re.S)
_CREDITS = _re.compile(r'<p class="credits">.*?</p>', _re.S)


def hero_retrofit(html, page, docs_dir):
    """Wave r3: give a COMMITTED page (rendered by older code) the hero its generator now writes, without running the
    generator: the page's hero section (an image hero of another key, or the plain hero of the reading-page look) is
    rebuilt with hero_for(page, <its own inner HTML, byte for byte>, ...) and the footer's credit line follows. Used by
    the r3 deploy (commit 2: the committed pages; the retired photographs leave in the same commit) and by the staged
    previews of the pages 19 / 20 / 25 render. Idempotent; a page without an entry, or whose hero / footer is not
    found exactly once, is returned unchanged (the caller checks)."""
    ph = page_hero(page)
    if not ph:
        return html
    m = list(_HERO_IMG.finditer(html))
    p = list(_HERO_PLAIN.finditer(html))
    if len(m) + len(p) != 1:
        return html
    if m:
        cls, body = m[0].group(1), m[0].group(3)
        a = body.find('<div class="container hero-in">')
        b = body.rfind('</div><p class="container hero-credit">')
        if a < 0:
            return html
        if b < 0:                                           # hero--plain (rendered without its image)
            b = len(body) - len("</div>")
            if not body.endswith("</div>"):
                return html
            cls = cls.replace("hero--plain", "").strip()
        inner, span = body[a + len('<div class="container hero-in">'):b], m[0].span()
    else:
        inner, cls, span = p[0].group(1), "", p[0].span()
        if "<div" in inner:                                 # a plain hero with blocks of its own: not ours to rebuild
            return html
    new = hero_for(page, inner, docs_dir, cls=cls)
    out = html[:span[0]] + new + html[span[1]:]
    f = list(_FOOT.finditer(out))
    if len(f) != 1:
        return html
    head, mid, tail = f[0].groups()
    mid2 = _CREDITS.sub("", mid) + credits_for(page)
    return out[:f[0].start()] + head + mid2 + tail + out[f[0].end():]


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
   block restores the previous look. Light theme here; dark = _design_system/theme.css. Warm ground, white cards with
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
:root{--hdr:65px;--otph:0px}
html{scroll-padding-top:calc(var(--hdr) + var(--otph) + 14px)}
.ptable thead th{top:calc(var(--hdr) + var(--otph) - 1px)}
/* round 1 (review V8): a tile clips (overflow:hidden), which makes IT the sticky container: an offset of the header's
   height pushed the head 64 px down inside the tile, over the first rows (regime.html, every stock page). Inside a
   tile the head stays at the top of its table. */
.tile .ptable thead th{top:0}
/* wave r3 (bug a, 2026-11-10): with overflow:clip (17's .tile rule, where supported) a tile clips WITHOUT being a
   scroll container, so the head of a table sitting directly in a tile sticks below the site header again (regime,
   every stock page); a tile that scrolls sideways (inline overflow-x) keeps its head at the top of the table, and a
   browser without overflow:clip keeps the rule above (the tile is then still the sticky container). On phones
   (<= 560 px) 17's legacy layer makes the table itself scroll sideways (display:block; overflow-x:auto): the TABLE
   is then the sticky container, so its head stays at its own top there */
@supports (overflow:clip){.tile:not([style*="overflow"])>.ptable thead th{top:calc(var(--hdr) + var(--otph) - 1px)}
  @media(max-width:560px){.tile:not([style*="overflow"])>.ptable thead th{top:0}}}
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
.hero--img .btn:not(.btn-ghost){background:#F3F5F9;color:#0A2540;border-color:#F3F5F9}
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
/* round 1 (review V2): the pill clips (overflow:hidden) and the buttons fill it, so the global ring (outside, +2 px)
   was invisible: draw it inside, in the button's own text colour (white on the active fill, ink on the others) */
.ccy-toggle button:focus-visible,.btr:focus-visible{outline:2px solid currentColor;outline-offset:-4px;border-radius:999px}
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
/* round 1 (review V4): the three summary cards share a row height; each card's closing note (sources, links) sits at
   the bottom, so the space a shorter card has is between its figures and its note, not under it */
#summary .xcard>.xn:last-child{margin-top:auto}
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
/* round 1 (review V4): the home's Markets view has 8 tiles: 4 + 4 from 900 px (it laid out 6 + 2 at 1440) */
@media(min-width:__MD__px){.mtiles{grid-template-columns:repeat(4,minmax(0,1fr))}}
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
  /* the home's "my book vs the S&P" panel (dollar figures) is shown from 641 px up only: on a phone it would push the
     page a full screen down. The Hold card's dollar row is its phone twin (.ph-only, hidden from 641 px up), so
     every figure shows once per screen (wave "no repeats", 2026-11-10) */
  .xcard{padding:18px}
  .fedrow{grid-template-columns:minmax(0,5.6em) minmax(0,1fr);row-gap:4px}
  .fedrow .t{grid-column:1 / -1;text-align:left}
  .flow{grid-template-columns:minmax(0,7.5em) minmax(0,1fr) minmax(0,1fr) 4.6em;font-size:12px}
  .brow{grid-template-columns:minmax(0,7.5em) minmax(0,1fr) 3.4em}
  .about-photo{width:min(220px,64vw)}
}
/* the hero panel and its phone twin (.ph-only below) are hidden by complementary queries: <= 640.98 px / >= 641 px
   (round 1, review V13: at 640.5 px -- Windows zoom -- a plain 640 / 641 pair left both visible) */
@media(max-width:__SM__.98px){.hero-panel{display:none}}
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
/* wave "no repeats" (2026-11-10): a phone twin of a figure the hero panel shows from 641 px up; row captions in a
   card; the secondary odds under a Watch line */
@media(min-width:__SM1__px){.ph-only{display:none!important}}
.kcap{margin:2px 0 -4px;font-size:11.5px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;color:var(--sec)}
.kcap span{display:block;margin-top:2px;font-weight:400;letter-spacing:0;text-transform:none;color:var(--muted)}
.wline .wsub{display:block;margin-top:3px;font:400 12px var(--mono);font-style:normal;color:var(--muted)}
.jsonly{display:none!important}
/* the header's theme control (glossary.NAV): hidden unless the page is themed, its icons sized, HERE -- not only in
   theme.css -- so a page whose theme.css is missing never shows a bare button (round 1, review PIPE-3) */
.thm{display:none}
.thm svg{display:none;width:18px;height:18px}
.js .jsonly{display:inline-flex!important}
.today-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:16px}
.today-head h2{margin:0;font:500 clamp(22px,2.4vw,30px)/1.2 var(--serif);border:0;padding:0}
.sec-h{margin:0 0 18px}
.sec-h h2{margin:0;font:500 clamp(24px,2.8vw,34px)/1.2 var(--serif);border:0;padding:0}
/* ---- wave r3 (builder B): the sticky "On this page" bar of the long pages (otp_insert: stocks, Congress, the archived
   report, strategies, portfolio, where it carries the MXN | USD switch: one strip, not two). Under the header; the
   section links scroll sideways with an edge fade on narrow screens; the current section is underlined
   (aria-current="location", set by OTP_JS); without JS it is a plain sticky row of links. --otph = its height
   (OTP_JS keeps it exact; the :has() value is the no-JS one): anchors and sticky table heads clear it. On a landscape
   phone (<= 500 px tall) it scrolls with the page. */
:root:has(nav.otp){--otph:45px}
.otp{display:block;margin:0;position:sticky;top:var(--hdr);z-index:30;background:var(--bg);border-bottom:1px solid var(--line)}
.otp-in{display:flex;align-items:center;gap:6px 14px;min-height:44px;width:100%;box-sizing:border-box}
.otp-k{flex:none;font-size:11.5px;font-weight:500;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.otp-sc{flex:1 1 auto;min-width:0;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none;-webkit-overflow-scrolling:touch}
.otp-sc::-webkit-scrollbar{display:none}
.otp-l{display:flex;gap:2px;margin:0;padding:0;list-style:none;white-space:nowrap}
.otp-l li{margin:0;padding:0}
.otp-l a{display:inline-flex;align-items:center;min-height:44px;padding:0 10px;font-size:13.5px;font-weight:500;
  color:var(--sec);text-decoration:none;border-bottom:2px solid transparent;box-sizing:border-box}
.otp-l a:hover{color:var(--ink);border-bottom-color:var(--line-strong)}
.otp-l a[aria-current]{color:var(--ink);border-bottom-color:var(--accent)}
.otp-sc.fr{-webkit-mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent);
  mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent)}
.otp-sc.fl{-webkit-mask-image:linear-gradient(to left,#000 calc(100% - 28px),transparent);
  mask-image:linear-gradient(to left,#000 calc(100% - 28px),transparent)}
.otp-sc.fl.fr{-webkit-mask-image:linear-gradient(to right,transparent,#000 28px,#000 calc(100% - 28px),transparent);
  mask-image:linear-gradient(to right,transparent,#000 28px,#000 calc(100% - 28px),transparent)}
.otp .ccy-in{flex:none;display:inline-flex;align-items:center;gap:10px}
.otp .ccy-sub{display:none}
.otp .ccy-toggle{margin:0}
.otp .ccy-toggle button{min-height:44px;min-width:58px}
.otp+main{padding-top:clamp(30px,4vw,48px)}
@media(max-width:__SM__.98px){.otp-k{display:none}.otp-l a{padding:0 9px;font-size:13px}
  .otp .ccy-lbl,.otp .ccy-sub{display:none}.otp .ccy-toggle{padding:2px}
  .otp .ccy-toggle button{min-width:44px;min-height:40px;padding:0 9px;font-size:12.5px}}
@media(max-height:500px){.otp{position:static}:root:has(nav.otp){--otph:0px}}
@media print{.otp{display:none!important}}
/* ---- wave r3 (builder B): note() -- the explanatory notes in two roles. Disclosure: always visible, short, a thin
   amber rule. Method: a native <details> closed by default (no script needed; find-in-page opens it). */
.nt{max-width:52em;margin:0 0 1.1rem;font-size:14px;line-height:1.55;color:var(--sec)}
.nt-d{border-left:2px solid var(--amber);padding:.1rem 0 .1rem .85rem}
.nt-m{border:1px solid var(--line);border-radius:12px;background:var(--panel)}
.nt-m>summary{display:flex;align-items:center;gap:10px;min-height:44px;padding:0 14px;cursor:pointer;list-style:none;
  font-size:13.5px;font-weight:500;color:var(--ink)}
.nt-m>summary::-webkit-details-marker{display:none}
.nt-m>summary::before{content:"";flex:none;width:7px;height:7px;margin:0 2px;border-right:1.6px solid var(--sec);
  border-bottom:1.6px solid var(--sec);transform:rotate(-45deg);transition:transform .15s}
.nt-m[open]>summary::before{transform:rotate(45deg)}
.nt-m>summary:hover{color:var(--accent)}
.nt-b{padding:0 16px 12px 33px}
.nt-b>p{margin:.55rem 0 0}
.nt-b>p:first-child{margin-top:0}
.metrics+.nt,.tile+.nt{margin-top:1rem}
@media(max-width:__SM__.98px){.nt-b{padding:0 12px 12px 14px}}
/* ---- wave r3 (builder C): the Stock Research tables. Desktop: the Pick Tracker (table.ptrack.fit,
   picks_tracker.tracker_fit) lets a cell's lines wrap only where the tracker allows (after a separator, between plain
   words; a figure never leaves its label), so its 11 columns fit the 1,150 px tile at 1440 px; where it still scrolls
   (641-1,180 px) the +/ticker columns stay in view. .spk = the rank sparkline (rank 1 at the top, the band lines dashed,
   a dot on the latest ranking). Phones (<= __SM__ px): every row of a table in a .tile.pcw (design_system.card_tables) is
   a card: each cell's column header (data-label) on the left, its value on the right; the first cell (and the ticker
   of the picks / tracker tables) is the card's head; the tracker card lists its cells by priority (data-pri). Same
   markup, same data: no second copy. */
.spk{display:inline-block;vertical-align:-4px;margin-right:7px;overflow:visible}
.spk .b{fill:none;stroke:var(--line-strong);stroke-opacity:1;stroke-width:1;stroke-dasharray:2 2}
.spk .l{fill:none;stroke:var(--accent);stroke-width:1.4;stroke-linejoin:round;stroke-linecap:round}
.spk circle{fill:var(--accent)}
.ptrack .rk1,.ptrack .nw{white-space:nowrap}
.tile.pcw>table.ptrack.fit>thead th,.tile.pcw>table.ptrack.fit>tbody>tr:not(.pt-detail)>td{white-space:normal;padding:7px 6px}
@media(min-width:__SM1__px){
  .tile.pcw>table.ptrack.fit>thead th:nth-child(-n+2),
  .tile.pcw>table.ptrack.fit>tbody>tr:not(.pt-detail)>td:nth-child(-n+2){position:sticky;z-index:1;background:var(--panel)}
  .tile.pcw>table.ptrack.fit>thead th:nth-child(-n+2){z-index:3}
  .tile.pcw>table.ptrack.fit>thead th:first-child,
  .tile.pcw>table.ptrack.fit>tbody>tr:not(.pt-detail)>td:first-child{left:0;box-sizing:border-box;width:38px;min-width:38px}
  .tile.pcw>table.ptrack.fit>thead th:nth-child(2),
  .tile.pcw>table.ptrack.fit>tbody>tr:not(.pt-detail)>td:nth-child(2){left:38px}
}
@media(max-width:__SM__.98px){
  .tile.pcw{padding:0!important;overflow:visible!important;background:none;border:0;box-shadow:none;border-radius:0}
  .tile.pcw>table.ptable{display:block;width:100%;margin:0;font-size:13px;white-space:normal;overflow:visible}
  .tile.pcw>table.ptable>thead{display:none}
  .tile.pcw>table.ptable>tbody{display:block}
  .tile.pcw>table.ptable>tbody>tr{display:flex;flex-wrap:wrap;align-items:flex-start;gap:0 14px;margin:0 0 10px;
    padding:10px 14px 6px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
  .tile.pcw>table.ptable>tbody>tr[hidden]{display:none}
  .tile.pcw>table.ptable>tbody>tr:hover>td{background:none}
  .tile.pcw>table.ptable>tbody>tr>td{display:block;flex:1 1 calc(50% - 7px);box-sizing:border-box;min-width:0;
    max-width:100%;padding:6px 0 7px;border:0;border-top:1px solid var(--line);text-align:left;white-space:normal}
  .tile.pcw>table.ptable>tbody>tr>td::before{content:attr(data-label);display:block;margin:0 0 2px;
    font:500 11.5px/1.35 var(--sans);letter-spacing:.02em;color:var(--muted);white-space:normal}
  .tile.pcw>table.ptable>tbody>tr>td:not([data-label])::before{content:none}
  .tile.pcw>table.ptable>tbody>tr>td:first-child{flex:1 1 100%;padding:2px 0 8px;border-top:0;font-size:14.5px}
  .tile.pcw>table.ptable>tbody>tr>td:first-child::before{content:none}
  .tile.pcw>table.ptable td.chips,.tile.pcw>table.ptable td.cmt{flex-basis:100%;min-width:0}
  .tile.pcw>table.picks>tbody>tr>td.rk{flex:0 0 auto;width:auto;font-size:13px;padding-top:4px}
  .tile.pcw>table.picks>tbody>tr>td:nth-child(2){flex:1 1 calc(100% - 64px);padding:2px 0 8px;border-top:0}
  .tile.pcw>table.picks>tbody>tr>td:nth-child(2)::before{content:none}
  .tile.pcw>table.ptrack>tbody>tr:not(.pt-detail)>td:first-child{order:2;flex:0 0 auto;padding:0 0 6px}
  .tile.pcw>table.ptrack>tbody>tr:not(.pt-detail)>td:nth-child(2){order:1;flex:1 1 calc(100% - 68px);padding:8px 0;border-top:0;
    font-size:15px}
  .tile.pcw>table.ptrack>tbody>tr:not(.pt-detail)>td:nth-child(2)::before{content:none}
  .tile.pcw>table.ptrack>tbody>tr:not(.pt-detail)>td[data-pri="1"]:nth-child(n+3){order:3}
  .tile.pcw>table.ptrack>tbody>tr:not(.pt-detail)>td[data-pri="2"]{order:4}
  .tile.pcw>table.ptrack>tbody>tr:not(.pt-detail)>td[data-pri="3"]{order:5}
  .tile.pcw>table.ptrack .pt-x{width:40px;height:40px;line-height:36px}
  .tile.pcw>table.ptrack>tbody>tr.pt-detail{display:block;margin:-6px 0 10px;padding:4px 12px 10px}
  .tile.pcw>table.ptrack>tbody>tr.pt-detail[hidden]{display:none}
  .tile.pcw>table.ptrack>tbody>tr.pt-detail>td{display:block;flex:1 1 100%;max-width:100%;padding:0;border:0;overflow-x:auto}
  .tile.pcw .ptdet{position:static;max-width:100%;grid-template-columns:minmax(0,1fr)}
}
@media print{.tile.pcw{overflow:visible!important}}
/* ---- fix round 1 (r3 continuation, 2026-11-11) --------------------------------------------------------------------
   V2-1  phones and landscape phones: the Research menu hangs from the header row, 16 px in from its sides, right under
         the corner button (top:auto = its place in the flow, + 8 px; never a fixed offset: without JavaScript the
         button can sit on a second header row). With the theme control shown (JavaScript) theme.css does it
         (design_system._THEME_CONTROL_CSS, r2's rule); the rule below gives landscape phones the same menu without
         JavaScript (its width from the header row, not the viewport); portrait phones without JavaScript keep the
         corner-anchored menu, which fits there (no control right of the button).
   V2-7  a licence name ('CC BY 4.0') never breaks across two lines.
   RG-2  a tile that scrolls sideways (inline overflow-x:auto) is a scroll container in both axes in every browser
         (CSS Overflow 3: 'clip' next to 'auto' computes to 'hidden'; Chrome kept 'clip' and stuck those heads at the
         viewport top, under the opaque header): their heads scroll with their table, as in r2 -- a viewport-sticky
         head is not possible inside a sideways scroller.
   V2-11 smooth anchor scrolling only once the page has loaded and settled (html.sm, set by the r3 head script,
         design_system.SITE_JS): a cold #link lands under the header and the bar instead of chasing a moving target.
   V2-12 the "Skip to content" link (SITE_JS puts it first in <body>): off-screen until it has the focus.
   V2-8  the error page: its list inside the column, its first section clear of the hero. */
@media(max-height:520px) and (min-width:560px) and (max-width:__NAV__px){.shell-in{position:relative}.rc{position:static}
  .rc-menu{left:auto;right:16px;width:min(640px,calc(100% - 32px));top:auto;margin-top:8px}}
a[rel~="license"]{white-space:nowrap}
.tile[style*="overflow-x:auto"]{overflow-y:hidden}
.skip{position:absolute;left:12px;top:-80px;z-index:200;padding:10px 16px;border:2px solid var(--accent);
  border-radius:10px;background:var(--panel);color:var(--accent);font-size:14px;font-weight:500;text-decoration:none}
.skip:focus{top:10px}
main[tabindex="-1"]:focus{outline:none}
.nf-main{padding-top:clamp(36px,5vw,56px)}
.nf-list{padding-left:1.3rem}
.nf-list li{margin:0 0 .55rem;line-height:1.55}
/* ---- polish round (r3, 2026-11-11) ---------------------------------------------------------------------------------
   P1 (V-1 / RC2-1) phones narrower than 360 px with the theme control (JavaScript): the brand, the Research corner and
      the control stay on ONE header row down to 320 px. Below ~335 px the control used to wrap to a row of its own
      (the sticky header grew 103 -> 153 px) and the open menu, hanging under the corner, covered it. Here the corner
      shows its book icon and caret only (font-size 0 hides the word; its aria-label still names it): the row needs
      ~240 of the 269 px a 320 px phone gives it. Without JavaScript (no control) the header is unchanged. */
@media(max-width:359.98px){[data-theme-pref] .rc>summary{font-size:0;gap:2px;padding:0 10px}
  [data-theme-pref] .rc>summary>svg:first-child,[data-theme-pref] .rc>summary .car{display:block}}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}
  .metric:hover,.scard:hover,.btcard:hover,.proj-card:hover,a.xcard:hover,.xcard.hov:hover{transform:none}
}
@media print{.rcn,.rc,.ptabs,.vtabs,.hero-bg,.hero-shade,.hero-credit{display:none!important}
  .hero--img{background:#fff;color:#111}.hero--img h1,.hero--img .lede{color:#111}}
""".replace("__SM1__", str(BP_SM + 1)).replace("__SM__", str(BP_SM)).replace("__MD__", str(BP_MD)).replace(
    "__LG__", str(BP_LG)).replace("__NAV__", str(NAV_BP))


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
function here(){try{return decodeURIComponent(location.hash.slice(1));}catch(_e){return '';}}
var init=byTarget(here())||tabs[0];sel(init);
window.addEventListener('hashchange',function(){var id=here(),t=byTarget(id);
if(t){sel(t);var el=document.getElementById(id);if(el&&el.scrollIntoView)el.scrollIntoView();}});}
[].forEach.call(document.querySelectorAll('[role="tablist"][data-tabs]'),wire);})();</script>"""


# =====================================================================================
# 2026-11-10 wave r2, DARK MODE (Carlos, written, ~09:45: "Modo oscuro siguiente paso si").
#
# How it works (one place, every page):
#   * A page becomes dark-capable when its generator passes its final HTML through `themed()` (below). That swaps
#     the head's CSS_LINKS for HEAD_LINKS (a tiny boot script that sets data-theme BEFORE the first paint + the
#     link to _design_system/theme.css) and rewrites every colour literal in the page's <style> blocks and style=""
#     attributes to `var(--token, <the same literal>)`. The literal stays as the FALLBACK, so the light theme is the
#     old bytes' colour by construction (the tokens a light page resolves are either undefined -> the literal, or
#     an Editorial Terminal token whose light value IS that literal; tools/theme_gate.py proves it per page).
#   * theme.css (emitted by emit(), linked only by themed pages) defines the DARK value of every token, under
#     `@media screen and (prefers-color-scheme: dark) :root:not([data-theme="light"])` (no-JS + "Auto") and
#     `@media screen :root[data-theme="dark"]` (an explicit choice). Print never matches (screen only): it stays
#     light. A page that is NOT themed (a committed copy from an older generator, internal/freshness.html) does not
#     link theme.css, so it stays light whatever the system says: no page can ever go dark with unconverted CSS.
#   * The header control (glossary.NAV, THEME_BUTTON + THEME_JS) is a two-state toggle: each press shows the other
#     look (light <-> dark), and landing on the device's own look is Auto again (follow the device; polish round
#     2026-11-11: no Auto -> Dark -> Light cycle). It keeps the
#     choice per viewer in localStorage (every access in try/catch) and re-themes every Plotly chart through ONE
#     light->dark palette map (CHART_DARK): on load (Plotly.newPlot is wrapped, so a dark page never paints a light
#     chart), on a theme change, and after any later restyle / relayout (portfolio's currency switch, the backtest
#     range buttons, the mobile tuner), because each of those can put light colours back.
# =====================================================================================
THEME_KEY = "ltcma-theme"                     # localStorage key (per viewer)

# Dark counterpart of every Editorial Terminal token (ET above + the tokens.css / style.css :root names).
ET_DARK = {
    "bg": "#101317", "panel": "#171B21", "ink": "#E9E7E2", "sec": "#B9BFC8", "muted": "#959CA8",
    "line": "#2B3139", "line-strong": "#3D444E", "chip": "#20252D",
    "accent": "#9CBDEB",                      # Oxford blue's dark-safe variant (same hue, 8.96:1 on a card)
    "accent-tint": "rgba(156,189,235,.08)", "accent-line": "rgba(156,189,235,.38)",
    "amber": "#F0A65A", "up": "#74B6EE", "down": "#F4925F",
    "pos": "#5CC68F", "neg": "#F39673",
    "st-green": "#5CC68F", "st-blue": "#93AEF5", "st-purple": "#B79CF5", "st-gray": "#9AA1AD",
    "lift": "0 8px 22px rgba(0,0,0,.45)",
}

# Tokens that only the themed rewrite references. In LIGHT they are undefined, so `var(--t, literal)` resolves to
# the literal (the page's old colour); THEME_CSS gives each its dark value. name: (light literal(s), dark value)
THEME_TOKENS = {
    "on-accent": ("#fff", "#0C1420"),          # text on an accent / badge fill
    "accent-hover": ("#0d3055", "#B6CFF2"),
    "selection": ("rgba(180,83,9,.16)", "rgba(240,166,90,.30)"),
    "neutral": ("#9AA5B4", "#6E7886"),         # neutral bar / gauge middle / "hold"
    "teal": ("#0f766e", "#45BBAD"), "bench": ("#9aa5b1", "#8B96A4"), "slate": ("#5b7c99", "#94ABC2"),
    "warn": ("#8a5a00", "#E0B05A"),
    "c-violet": ("#8a3ffc", "#B58CFF"), "c-red": ("#fa4d56", "#E25083"), "c-cyan": ("#009d9a", "#2EC4C0"),
    # the legacy (pre-remake) greys page CSS still uses, one token per distinct light value
    "l-ink": ("#111", "#E9E7E2"), "l-ink2": ("#333", "#D7D9DD"), "l-ink25": ("#393939", "#D2D4D8"),
    "l-ink3": ("#444", "#C9CCD2"), "l-sec": ("#555", "#B9BFC8"), "l-sec6": ("#666", "#AEB4BE"),
    "l-muted": ("#888", "#9EA5B0"), "l-muted2": ("#9ca3af", "#8F96A1"), "l-faint": ("#c4c9cf", "#8A929D"),
    "l-line": ("#e5e5e5", "#2B3139"), "l-line2": ("#d4d4d4", "#3D444E"), "l-line3": ("#eee", "#262B33"),
    "l-line4": ("#f0f0f0", "#262B33"), "l-line5": ("#d8d5cf", "#3D444E"),
    "l-tot": ("#fbfaf8", "#1C2027"), "l-row": ("#fbfbfb", "#1C2027"), "l-dim": ("#fcfcfc", "#191D23"),
    "l-grp": ("#f4f4f2", "#1F242B"), "l-chip": ("#f4f4f4", "#222730"), "l-code": ("#f0f0f0", "#222730"),
    "l-track": ("#eef0f2", "#262B33"), "l-track2": ("#c7d3df", "#46505C"), "l-prelim": ("#f5f8fb", "#18212B"),
    "l-tint45": ("rgba(10,37,64,.045)", "rgba(156,189,235,.07)"),
    "l-tint35": ("rgba(10,37,64,.035)", "rgba(156,189,235,.06)"),
    "l-tint07": ("rgba(10,37,64,.07)", "rgba(156,189,235,.12)"),
    "l-tint-k": ("rgba(0,0,0,.05)", "rgba(255,255,255,.07)"),
    "l-accent-line20": ("rgba(10,37,64,.2)", "rgba(156,189,235,.32)"),
    "l-pos-line": ("rgba(10,93,58,.35)", "rgba(92,198,143,.45)"),
    "l-neg-line": ("rgba(124,45,18,.45)", "rgba(243,150,115,.5)"),
    "l-warn-line": ("rgba(138,90,0,.4)", "rgba(224,176,90,.5)"),
    "l-blue-line": ("rgba(30,58,138,.35)", "rgba(147,174,245,.45)"),
    "l-purple-line": ("rgba(91,33,182,.35)", "rgba(183,156,245,.45)"),
    "l-sh08": ("rgba(14,23,38,.08)", "rgba(0,0,0,.45)"), "l-sh16": ("rgba(14,23,38,.16)", "rgba(0,0,0,.55)"),
}

# (kind, light colour) -> token. kind = the property family the literal sits in: fg (color), bg (background),
# bd (border / outline), sh (shadow). A colour the table does not know is left as it is and reported
# (THEME_UNMAPPED); tools/theme_gate.py fails a page that still carries one outside the theme-invariant contexts.
_FG = {"#fff": "on-accent", "#111": "l-ink", "#333": "l-ink2", "#393939": "l-ink25", "#444": "l-ink3",
       "#555": "l-sec", "#666": "l-sec6", "#888": "l-muted", "#9ca3af": "l-muted2", "#c4c9cf": "l-faint",
       "#6b7280": "st-gray", "#0a2540": "accent", "#0a5d3a": "pos", "#7c2d12": "neg", "#0f766e": "teal",
       "#9aa5b1": "bench", "#1e3a8a": "st-blue", "#5b21b6": "st-purple", "#8a5a00": "warn",
       "#0f5e9c": "up", "#c2410c": "down", "#b45309": "amber"}
_BG = {"#fff": "panel", "#0a2540": "accent", "#0a5d3a": "pos", "#7c2d12": "neg", "#6b7280": "st-gray",
       "#5b7c99": "slate", "#8a3ffc": "c-violet", "#fa4d56": "c-red", "#009d9a": "c-cyan",
       "#fbfaf8": "l-tot", "#fbfbfb": "l-row", "#fcfcfc": "l-dim", "#f4f4f2": "l-grp", "#f4f4f4": "l-chip",
       "#f0f0f0": "l-code", "#eef0f2": "l-track", "#f5f8fb": "l-prelim", "#e5e5e5": "l-line",
       "#c7d3df": "l-track2", "#9aa5b4": "neutral", "#0d3055": "accent-hover", "#0f5e9c": "up",
       "#c2410c": "down", "#b45309": "amber", "#0f766e": "teal", "#555": "l-sec", "#888": "l-muted",
       "rgba(10,37,64,.045)": "l-tint45", "rgba(10,37,64,.05)": "accent-tint", "rgba(10,37,64,.035)": "l-tint35",
       "rgba(10,37,64,.07)": "l-tint07", "rgba(0,0,0,.05)": "l-tint-k", "rgba(180,83,9,.16)": "selection"}
_BD = {"#e5e5e5": "l-line", "#d4d4d4": "l-line2", "#eee": "l-line3", "#f0f0f0": "l-line4", "#d8d5cf": "l-line5",
       "#c7d3df": "l-track2", "#0a2540": "accent", "#0f766e": "teal", "#7c2d12": "neg", "#0a5d3a": "pos",
       "#6b7280": "st-gray", "#9ca3af": "l-muted2", "#fff": "panel",
       "rgba(10,37,64,.2)": "l-accent-line20", "rgba(10,93,58,.35)": "l-pos-line",
       "rgba(124,45,18,.45)": "l-neg-line", "rgba(138,90,0,.4)": "l-warn-line",
       "rgba(30,58,138,.35)": "l-blue-line", "rgba(91,33,182,.35)": "l-purple-line"}
_SH = {"rgba(14,23,38,.08)": "l-sh08", "rgba(14,23,38,.16)": "l-sh16"}

_HEX = _re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z])")
_COLOR = _re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z])|rgba?\([^)]*\)"
                     r"|(?<![\w-])(?:white|black)(?![\w-])", _re.I)
_NAMED = {"white": (255, 255, 255, 1.0), "black": (0, 0, 0, 1.0), "transparent": (0, 0, 0, 0.0)}


def canon(c):
    """A colour as (r, g, b, alpha rounded to 3 dp), or None: #abc, #aabbcc(dd), rgb(), rgba(), white / black."""
    s = str(c).strip().lower().replace(" ", "")
    if s in _NAMED:
        return _NAMED[s]
    if s.startswith("#"):
        h = s[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) == 6:
            h += "ff"
        if len(h) != 8 or not all(ch in "0123456789abcdef" for ch in h):
            return None
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), round(int(h[6:8], 16) / 255, 3))
    m = _re.match(r"^rgba?\(([^)]*)\)$", s)
    if not m:
        return None
    p = m.group(1).split(",")
    if len(p) < 3:
        return None
    try:
        return (round(float(p[0])), round(float(p[1])), round(float(p[2])), round(float(p[3]) if len(p) > 3 else 1.0, 3))
    except ValueError:
        return None


def _keyed(d):
    return {canon(k): v for k, v in d.items()}


_KIND_MAP = {"fg": _keyed(_FG), "bg": _keyed(_BG), "bd": _keyed(_BD), "sh": _keyed(_SH)}
THEME_UNMAPPED = []                            # (context, property, literal) the rewrite could not map (gate reads it)


def _prop_kind(prop):
    p = prop.strip().lower()
    if p.startswith("--") or "mask" in p:
        return None
    if p in ("color", "fill", "stroke", "caret-color", "text-decoration-color", "-webkit-text-fill-color"):
        return "fg"
    if p.startswith("background"):
        return "bg"
    if p.startswith("border") or p.startswith("outline") or p == "column-rule-color":
        return "bd"
    if p in ("box-shadow", "text-shadow"):
        return "sh"
    return None


# Theme-invariant contexts: the image heroes (dark in both themes, measured on the decoded pixels by
# hero_contrast.py) and print (always light). A rule there keeps its literal colours.
THEME_INVARIANT = _re.compile(r"\.hero--img|\.hero-shade|\.hero-credit|\.hero-stat|\.hero-panel|\.btn-ghost")


def _sub_value(value, kind, ctx):
    """Rewrite the colour literals of one declaration value (outside var(...)) to var(--token, literal). A var(...)
    span is left alone: a literal inside it is already a token's fallback."""
    segs, start, k = [], 0, 0
    while k < len(value):
        if value.startswith("var(", k):
            j, d = k + 4, 1
            while j < len(value) and d:
                d += {"(": 1, ")": -1}.get(value[j], 0)
                j += 1
            segs.append((value[start:k], True))
            segs.append((value[k:j], False))
            start = k = j
            continue
        k += 1
    segs.append((value[start:], True))

    def rep(m):
        lit = m.group(0)
        tok = _KIND_MAP[kind].get(canon(lit))
        if tok is None:
            THEME_UNMAPPED.append((ctx, kind, lit))
            return lit
        return f"var(--{tok},{lit})"
    return "".join(_COLOR.sub(rep, s) if live else s for s, live in segs)


def _decls(body, ctx):
    """Rewrite every declaration of one rule body; every other byte is kept."""
    parts = body.split(";")
    for n, d in enumerate(parts):
        if ":" not in d:
            continue
        prop, val = d.split(":", 1)
        kind = _prop_kind(prop)
        if kind and _COLOR.search(val):
            parts[n] = prop + ":" + _sub_value(val, kind, f"{ctx} {prop.strip()}")
    return ";".join(parts)


def themed_css(css, ctx="css"):
    """Tokenise one stylesheet (see the block comment above). Comments, at-rules, custom-property definitions,
    masks, theme-invariant selectors (THEME_INVARIANT) and @media print are kept byte for byte."""
    out, stack, pre, i, n = [], [], [], 0, len(css)
    while i < n:
        if css.startswith("/*", i):                  # a comment is copied, never read as a selector
            j = css.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(css[i:j])
            i = j
            continue
        c = css[i]
        if c == "{":
            sel = "".join(pre).strip()
            pre = []
            out.append(c)
            i += 1
            if sel.startswith("@"):                  # @media / @supports: its rules follow
                stack.append(sel)
                continue
            j = css.find("}", i)
            j = n if j < 0 else j
            body = css[i:j]
            skip = (THEME_INVARIANT.search(sel) is not None
                    or any(_re.search(r"\bprint\b", s) for s in stack if s.startswith("@media")))
            out.append(body if skip else _decls(body, f"{ctx} {sel[:60]}"))
            out.append(css[j:j + 1])                 # the rule's own '}' (it does not close an at-rule)
            i = j + 1
            continue
        if c in "};":
            if c == "}" and stack:
                stack.pop()
            pre = []
            out.append(c)
            i += 1
            continue
        pre.append(c)
        out.append(c)
        i += 1
    return "".join(out)


_SEG = _re.compile(r"(<script\b[^>]*>.*?</script\s*>|<style\b[^>]*>.*?</style\s*>)", _re.S | _re.I)
_STYLE_ATTR = _re.compile(r"""(\sstyle\s*=\s*)(?:"([^"]*)"|'([^']*)')""", _re.I)
THEME_MARK = "data-theme-pref"                # the boot script sets it; a page that carries it is themed


def themed(html, page="page"):
    """Make one generated page dark-capable (idempotent). Returns the page unchanged, with a WARN line, when its
    head does not carry CSS_LINKS exactly once: such a page then simply stays light (it never links theme.css)."""
    if HEAD_LINKS in html:
        return site_head(otp_insert(html, page), page)   # wave r3: the share head + Plotly bundle; the bar (B)
    if html.count(CSS_LINKS) != 1:
        print(f"WARN theme: {page}: CSS_LINKS found {html.count(CSS_LINKS)}x, page left light-only")
        return site_head(otp_insert(html, page), page)
    html = html.replace(CSS_LINKS, HEAD_LINKS, 1)
    out = []
    for k, seg in enumerate(_SEG.split(html)):
        if k % 2 == 1:
            if seg[:6].lower() == "<style":
                a = seg.index(">") + 1
                b = seg.lower().rindex("</style")
                seg = seg[:a] + themed_css(seg[a:b], page) + seg[b:]
            out.append(seg)
            continue

        def attr(m):
            q = '"' if m.group(2) is not None else "'"
            v = m.group(2) if m.group(2) is not None else m.group(3)
            return m.group(1) + q + _decls(v, f"{page} style=") + q
        out.append(_STYLE_ATTR.sub(attr, seg))
    return site_head(otp_insert("".join(out), page), page)


# --- the head: the boot script runs BEFORE the stylesheets, so the first paint already has the right theme ----
THEME_BOOT = ("<script>(function(){var d=document.documentElement,p='auto',m=false;"
              "try{p=localStorage.getItem('" + THEME_KEY + "')||'auto';}catch(e){}"
              "if(p!=='light'&&p!=='dark')p='auto';"
              "try{m=window.matchMedia('(prefers-color-scheme: dark)').matches;}catch(e){}"
              "d.setAttribute('data-theme-pref',p);"
              "d.setAttribute('data-theme',p==='dark'||(p==='auto'&&m)?'dark':'light');})();</script>")
HEAD_LINKS = THEME_BOOT + CSS_LINKS + '<link rel="stylesheet" href="_design_system/theme.css">'


# --- ONE light -> dark palette map for every Plotly chart (the colours the generators use; dark values are
# unique and never used as a light colour, so the map inverts exactly: theme_gate checks both, plus >= 3:1 on the
# dark card for every value a trace strokes or fills). Alpha variants of a mapped colour keep their alpha.
CHART_DARK = {
    "#ffffff": "#171B21",            # paper / plot ground ('white'), marker outlines -> the dark card
    "#111111": "#E9E7E2",            # chart text (INK)
    "#2a3f5f": "#D9DEE6",            # plotly_white template text, where a chart does not set its own
    NAVY: "#8DB4EC", SLATE: "#3D70D6", TEAL: "#3CB7A8", BENCH: "#808389", MUTED: "#6F7A8A",   # round 1: V1
    GRIDLN: "#2B3139", "#d4d4d4": "#3D444E", "#ebf0f8": "#343B45", "#c9c9c9": "#59616D",
    "#888888": "#A3A3A3", "#666666": "#AEB4BE", "#555555": "#B9BFC8", "#6b7280": "#8C93A0",
    POS: "#55C08A", NEG: "#F08A62",
    "#f1f1f1": "#22272F",            # "in cash, by choice" band
    "#f4f4f2": "#2A2F37", "#7fb3ad": "#2F6F68", "#7e97b3": "#4E6688",   # correlation scale (mid, ramp)
    "#8a3ffc": "#B58CFF", "#009d9a": "#2EC4C0", "#fa4d56": "#E25083",   # sector colours (c-red: round 1, V1)
    "#0f5e9c": "#74B6EE", "#c2410c": "#F4925F", "#b45309": "#F0A65A",   # up / down / amber
    "rgba(255,255,255,.97)": "rgba(31,36,44,.97)",                      # hover label ground
    "rgba(15,98,254,0.13)": "rgba(120,170,255,0.16)",
    TINT["navy"]: "rgba(141,180,236,0.10)", TINT["navy_peak"]: "rgba(141,180,236,0.16)",
    TINT["bench"]: "rgba(128,131,137,0.24)", "rgba(154,165,177,0.12)": "rgba(128,131,137,0.15)",
    TINT["teal"]: "rgba(60,183,168,0.11)",
}


def _css_vars(d):
    return ";".join(f"--{k}:{v}" for k, v in d.items())


_DARK_VARS = _css_vars({**ET_DARK, **{k: v[1] for k, v in THEME_TOKENS.items()}})
# dark-only component rules (things a token cannot express); written once, emitted under both dark contexts
_DARK_RULES = (".report img,.tile img:not(.about-photo){background:#FFFFFF;border-radius:8px}"   # white-ground figures
               "input::placeholder,textarea::placeholder{color:var(--muted);opacity:1}")       # round 1: V15
_THEME_CONTROL_CSS = (
    "[data-theme-pref] .thm{display:inline-flex}"
    ".thm{flex:none;align-items:center;justify-content:center;width:44px;height:44px;padding:0;margin:0;"
    "border:1px solid var(--accent-line);border-radius:999px;background:var(--panel);color:var(--accent);cursor:pointer;"
    "transition:border-color .15s ease-out,background .15s ease-out}"
    ".thm:hover{border-color:var(--accent)}"
    ".thm[data-mode=\"auto\"] .ti-a,.thm[data-mode=\"light\"] .ti-l,.thm[data-mode=\"dark\"] .ti-d{display:block}"
    ".thm:not([data-mode]) .ti-a{display:block}"
    ".thm-st{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
    f"@media(max-width:{NAV_BP}px){{.thm{{order:2}}}}"
    # the header row with the control (measured 2026-11-10, Inter loaded): at >= 1280 px brand 340 + tabs 592 +
    # corner 130 + control 44 + gaps 14 + 14 + 8 = 1142 of the 1152 px row (10 px to spare; without these the tabs
    # were cut by 40 px). Keyed on [data-theme-pref] (set by the boot script), so a page without the control keeps
    # the previous spacing, and the selectors outrank style.css (this sheet loads before it).
    # (one-row values first, the two-row / phone values restated below: a 1279.2 px viewport -- Windows at 125 % --
    # lays out on one row, so the one-row spacing must not hang on a min-width query)
    "[data-theme-pref] nav.tabs a{padding:0 6px}"
    "[data-theme-pref] .thm{margin-left:-6px}[data-theme-pref] .rc>summary{padding:0 13px 0 11px}"
    f"@media(max-width:{NAV_BP}px){{[data-theme-pref] nav.tabs a{{padding:0 9px}}[data-theme-pref] .thm{{margin-left:0}}"
    "[data-theme-pref] .rc>summary{padding:0 14px 0 12px}}"
    f"@media(max-width:{BP_SM}px){{[data-theme-pref] nav.tabs a{{padding:0 8px}}"
    "[data-theme-pref] .rc>summary{padding:0 11px 0 10px}}"
    # phones: brand + corner + control on one row down to 320 px (the short brand from 560 px down; below 400 px
    # the corner drops its book icon and the row gaps tighten, below 360 px its caret)
    f"@media(max-width:{BP_SM - 80}px){{[data-theme-pref] .brand{{font-size:0;gap:8px}}"
    "[data-theme-pref] .brand::after{content:\"Carlos Duarte\";font:500 14.5px var(--serif);letter-spacing:.02em}}"
    "@media(max-width:400px){[data-theme-pref] .rc>summary>svg:first-child{display:none}"
    "[data-theme-pref] .shell-in{gap:6px 8px}[data-theme-pref] .brand::after{font-size:14px}}"
    "@media(max-width:359px){[data-theme-pref] .rc>summary .car{display:none}}"
    # 2026-11-11 (r3 review V2-1, RC1-1, RC1-2): with the control to the right of the corner, the corner's right edge
    # moved ~54 px in, and the menu (anchored right:0 to the corner, up to 390 / 640 px wide) ran off the LEFT edge
    # on 340-470 px phones and on landscape phones. There it now hangs from the header row: 16 px in from its sides,
    # right under the corner (top:auto = its place in the flow, + the usual 8 px). Without JS (no control, so the
    # corner is the row's last item) the old anchoring stays.
    f"@media(max-width:{BP_SM}.98px){{[data-theme-pref] .shell-in{{position:relative}}[data-theme-pref] .rc{{position:static}}"
    "[data-theme-pref] .rc-menu{left:16px;right:16px;width:auto;top:auto;margin-top:8px}}"
    f"@media(max-height:520px) and (min-width:560px) and (max-width:{NAV_BP}px){{[data-theme-pref] .shell-in{{position:relative}}"
    "[data-theme-pref] .rc{position:static}"
    "[data-theme-pref] .rc-menu{left:auto;right:16px;width:min(640px,calc(100% - 32px));top:auto;margin-top:8px}}"
    "@media print{.thm{display:none!important}}")


def _scoped(prefix, rules):
    return "".join(",".join(f"{prefix} {x.strip()}" for x in sel.split(",")) + "{" + body + "}"
                   for sel, body in _re.findall(r"([^{}]+)\{([^{}]*)\}", rules))


THEME_CSS = (
    "/* GENERATED by scripts/design_system.py (THEME_CSS) -- do not edit under docs/. Linked only by pages a\n"
    "   generator passed through design_system.themed(): the dark value of every token (ET_DARK + THEME_TOKENS),\n"
    "   under the system preference (no JS, or the control on Auto) and under an explicit choice; screen only, so\n"
    "   print stays light. Light values: the tokens of style.css / the literal fallbacks in each var(). */\n"
    ":root{color-scheme:light;--thm-ok:1}\n" + _THEME_CONTROL_CSS + "\n"
    "@media screen and (prefers-color-scheme:dark){:root:not([data-theme=\"light\"]){color-scheme:dark;"
    + _DARK_VARS + "}" + _scoped(':root:not([data-theme="light"])', _DARK_RULES) + "}\n"
    "@media screen{:root[data-theme=\"dark\"]{color-scheme:dark;" + _DARK_VARS + "}"
    + _scoped(':root[data-theme="dark"]', _DARK_RULES) + "}\n")


# --- the header control (inside glossary.NAV, after the Research corner) -------------------------------------
_TI = ('<svg class="ti-{k}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
       'stroke-linecap="round" aria-hidden="true" focusable="false">{p}</svg>')
THEME_BUTTON = (
    '<button type="button" class="thm" id="thm" aria-label="Colour theme: Auto (follows your device). '
    'Activate to switch between light and dark." title="Theme: Auto (follows your device)">'
    + _TI.format(k="a", p='<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5v17A8.5 8.5 0 0 0 12 3.5z" '
                          'fill="currentColor" stroke="none"/>')
    + _TI.format(k="l", p='<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6'
                          'M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/>')
    + _TI.format(k="d", p='<path d="M20 14.6A8.5 8.5 0 0 1 9.4 4a8.5 8.5 0 1 0 10.6 10.6z"/>')
    + '</button><span class="thm-st" id="thm-st" role="status" aria-live="polite"></span>')

THEME_JS = r"""<script>(function(){
var d=document.documentElement;if(!d.hasAttribute('data-theme-pref'))return;   /* page not themed: stay light, control hidden */
var K='__KEY__',LB={auto:'Auto (follows your device)',light:'Light',dark:'Dark'},
MQ=null,PRINT=false;try{MQ=window.matchMedia('(prefers-color-scheme: dark)');}catch(e){}
function pref(){var p=d.getAttribute('data-theme-pref');return p==='light'||p==='dark'?p:'auto';}
function eff(p){return p==='dark'||(p==='auto'&&MQ&&MQ.matches)?'dark':'light';}
function sys(){return MQ&&MQ.matches?'dark':'light';}
/* the next look is always the other one; if that is the device's own, the choice is Auto again (follow the device) */
function nx(){var o=eff(pref())==='dark'?'light':'dark';return o===sys()?'auto':o;}
/* theme.css sets --thm-ok: if it did not load, the page is light and so are its charts */
function ok(){try{return getComputedStyle(d).getPropertyValue('--thm-ok').trim()==='1';}catch(e){return true;}}
function cur(){return PRINT||!ok()?'light':(d.getAttribute('data-theme')==='dark'?'dark':'light');}
function ui(){var b=document.getElementById('thm');if(!b)return;var p=pref(),n=nx(),lk=eff(n)==='dark'?'Dark':'Light';
b.setAttribute('data-mode',p);
b.setAttribute('aria-label','Colour theme: '+LB[p]+'. Activate for '+lk+(n==='auto'?' (follows your device)':'')+'.');
b.title='Theme: '+LB[p];}
function set(p,save,say){d.setAttribute('data-theme-pref',p);d.setAttribute('data-theme',eff(p));
if(save){try{localStorage.setItem(K,p);}catch(e){}}ui();all();
if(say){var s=document.getElementById('thm-st');if(s)s.textContent=LB[p].split(' (')[0]+' theme'+(p==='auto'?', now '+eff(p):'');}
try{window.dispatchEvent(new CustomEvent('ltcma-theme',{detail:{pref:p,theme:eff(p)}}));}catch(e){}}
/* ---- charts: ONE light->dark map (design_system.CHART_DARK), inverted for the way back ---- */
var MAP=__MAP__,NM={white:'255,255,255,1',black:'0,0,0,1',transparent:'0,0,0,0'},FW={},BW={};
function r3(a){return String(Math.round(a*1000)/1000);}
function cn(c){if(typeof c!=='string')return null;var s=c.replace(/\s+/g,'').toLowerCase(),m,h,p;if(NM[s])return NM[s];
if(s.charAt(0)==='#'){h=s.slice(1);if(h.length===3||h.length===4)h=h.replace(/./g,'$&$&');if(h.length===6)h+='ff';
if(!/^[0-9a-f]{8}$/.test(h))return null;return parseInt(h.substr(0,2),16)+','+parseInt(h.substr(2,2),16)+','+parseInt(h.substr(4,2),16)+','+r3(parseInt(h.substr(6,2),16)/255);}
m=/^rgba?\(([^)]*)\)$/.exec(s);if(!m)return null;p=m[1].split(',');if(p.length<3)return null;
return Math.round(+p[0])+','+Math.round(+p[1])+','+Math.round(+p[2])+','+r3(p.length>3?+p[3]:1);}
for(var k in MAP){var a=cn(k),b=cn(MAP[k]);if(a&&b){FW[a]=MAP[k];BW[b]=k;}}
function mc(c,T){var k=cn(c);if(k===null)return c;if(T[k]!==undefined)return T[k];var i=k.lastIndexOf(','),al=k.slice(i+1),t;
if(al!=='1'&&al!=='0'){t=T[k.slice(0,i)+',1'];if(t!==undefined){var q=cn(t).split(',');return 'rgba('+q[0]+','+q[1]+','+q[2]+','+al+')';}}return c;}
var RX=/(colou?r\s*:\s*)(#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\))/g;
function ms(s,T){return (typeof s==='string'&&s.indexOf('olo')>=0)?s.replace(RX,function(_,p,c){return p+mc(c,T);}):s;}
function mv(v,T,str){if(typeof v==='string')return str?ms(v,T):mc(v,T);
if(Array.isArray(v))return v.map(function(x){return (typeof x==='string'||Array.isArray(x))?mv(x,T,str):x;});return v;}
function eq(a,b){return a===b||JSON.stringify(a)===JSON.stringify(b);}
function gp(o,p){var s=p.split('.');for(var i=0;i<s.length;i++){if(o===null||o===undefined)return undefined;o=o[s[i]];}return o;}
var TC=['line.color','marker.color','marker.colors','marker.line.color','fillcolor','textfont.color','insidetextfont.color',
'outsidetextfont.color','error_x.color','error_y.color','hoverlabel.bgcolor','hoverlabel.bordercolor','hoverlabel.font.color',
'colorscale','marker.colorscale','connector.line.color','increasing.line.color','decreasing.line.color',
'increasing.marker.color','decreasing.marker.color','totals.marker.color','colorbar.tickfont.color','colorbar.title.font.color',
'marker.colorbar.tickfont.color','marker.colorbar.title.font.color','colorbar.bgcolor','colorbar.bordercolor','colorbar.outlinecolor'],
TS=['text','hovertext','hovertemplate','texttemplate'],TD=['line.color','marker.color','fillcolor'],
LF=['paper_bgcolor','plot_bgcolor','font.color'],AF=['gridcolor','linecolor','zerolinecolor','tickcolor','spikecolor'],
LU=['title.font.color','legend.bgcolor','legend.bordercolor','legend.font.color','legend.title.font.color','hoverlabel.bgcolor',
'hoverlabel.bordercolor','hoverlabel.font.color','coloraxis.colorbar.tickfont.color','coloraxis.colorbar.title.font.color'];
function th(g){if(!g||!g._fullLayout||!g.data||!window.Plotly)return;var T=cur()==='dark'?FW:BW,F=g._fullLayout,L=g.layout||{},lu={};
function put(p,v,str){if(v===undefined||v===null)return;var w=mv(v,T,str);if(!eq(w,v))lu[p]=w;}
LF.forEach(function(p){put(p,gp(F,p));});
Object.keys(F).forEach(function(ax){if(!/^[xy]axis\d*$/.test(ax))return;AF.forEach(function(p){put(ax+'.'+p,gp(F[ax],p));});
['tickfont.color','title.font.color'].forEach(function(p){put(ax+'.'+p,gp(L[ax],p));});put(ax+'.title.text',gp(L[ax],'title.text'),true);});
LU.forEach(function(p){put(p,gp(L,p));});put('title.text',gp(L,'title.text'),true);
(L.annotations||[]).forEach(function(a,i){['font.color','bgcolor','bordercolor','arrowcolor'].forEach(function(p){put('annotations['+i+'].'+p,gp(a,p));});
put('annotations['+i+'].text',a.text,true);});
(L.shapes||[]).forEach(function(s,i){['line.color','fillcolor','label.font.color'].forEach(function(p){put('shapes['+i+'].'+p,gp(s,p));});});
var ch={},idx=[],fd=g._fullData||[];
g.data.forEach(function(t,i){var f=null;fd.some(function(x){if(x.index===i){f=x;return true;}return false;});
function tr(p,str){var v=gp(t,p);if(v===undefined&&!str&&f&&f.visible!==false&&TD.indexOf(p)>=0)v=gp(f,p);
if(v===undefined||v===null)return;var w=mv(v,T,str);if(!eq(w,v)){(ch[p]=ch[p]||{})[i]=w;if(idx.indexOf(i)<0)idx.push(i);}}
TC.forEach(function(p){tr(p,false);});TS.forEach(function(p){tr(p,true);});});
if(!Object.keys(lu).length&&!idx.length)return;
var now=Date.now();if(!g.__thT||now-g.__thT>1500){g.__thT=now;g.__thN=0;}if(++g.__thN>6)return;   /* safety valve */
var tu={};Object.keys(ch).forEach(function(p){tu[p]=idx.map(function(i){return ch[p][i];});});
try{window.Plotly.update(g,tu,lu,idx.length?idx:undefined);}catch(e){}}
function hook(g){if(!g||g.__thh||!g.on)return;g.__thh=true;var q=false,f=function(){if(q)return;q=true;
Promise.resolve().then(function(){q=false;th(g);});};
['plotly_afterplot','plotly_restyle','plotly_relayout','plotly_update'].forEach(function(e){g.on(e,f);});}
function all(){[].forEach.call(document.querySelectorAll('.js-plotly-plot'),function(g){hook(g);th(g);});}
function wrap(){var P=window.Plotly;if(!P||P.__thw||!P.newPlot)return;P.__thw=true;var np=P.newPlot;
P.newPlot=function(g){var r=np.apply(this,arguments),el=typeof g==='string'?document.getElementById(g):g;
try{hook(el);if(el&&el._fullLayout)th(el);}catch(e){}if(r&&r.then)r.then(function(){try{hook(el);th(el);}catch(e){}});return r;};}
wrap();
function wire(){var b=document.getElementById('thm');if(b&&!b.__thw){b.__thw=true;b.addEventListener('click',function(){set(nx(),true,true);});}ui();}
wire();document.addEventListener('DOMContentLoaded',function(){wrap();wire();all();});window.addEventListener('load',all);
/* Auto follows the system: the MediaQueryList change event, and -- for a change that event missed (a tab in the
   background, some embedded browsers) -- a re-check whenever the page is focused or shown again */
var mf=function(){if(pref()==='auto'&&d.getAttribute('data-theme')!==eff('auto'))set('auto',false,false);else ui();};
if(MQ){if(MQ.addEventListener)MQ.addEventListener('change',mf);else if(MQ.addListener)MQ.addListener(mf);}
window.addEventListener('focus',mf);document.addEventListener('visibilitychange',function(){if(!document.hidden)mf();});
window.addEventListener('storage',function(e){if(e.key===K){var p=e.newValue;set(p==='light'||p==='dark'?p:'auto',false,false);}});
window.addEventListener('beforeprint',function(){PRINT=true;all();});window.addEventListener('afterprint',function(){PRINT=false;all();});
window.ltcmaTheme={set:function(p){set(p==='light'||p==='dark'?p:'auto',true,false);},pref:pref,theme:cur,apply:all,map:function(c,dk){return mc(c,dk?FW:BW);}};
})();</script>""".replace("__KEY__", THEME_KEY).replace("__MAP__", __import__("json").dumps(CHART_DARK, separators=(",", ":")))


# =====================================================================================================================
# 2026-11-10 wave r3 (Carlos, written ~15:00, "Dale play a todo" on the r3 package): pages ready to share, lighter
# pages, one Fed-odds vintage. Three entry points:
#   site_head(html, page) -- run by themed() on EVERY generated page (so 19 / 20 / 25 get it at their next render, and
#     the r3 deploy applies the SAME function to the committed copies, tools/deploy_docs_r3.py): the title pattern
#     "<Name> · Carlos Duarte", a description, canonical + Open Graph + Twitter-card meta (one 1200x630 typographic card
#     per main tab: page name, one line, the URL; no figure, no photo -- a JWST crop in a link preview would travel
#     without its CC BY credit), the favicon set (the header's CD mark), a font preconnect, and the Plotly bundle: the
#     OFFICIAL cartesian partial bundle of the same pinned version when every trace on the page is a cartesian type,
#     else the full bundle. Idempotent (the block is delimited and re-derived); a page it does not know (a redirect
#     stub) only gets the bundle rule. share_strip() undoes the block exactly (the rollback).
#   emit_share(docs_dir) -- 17 calls it beside emit(): the favicon / card files (source of truth assets/img, copied
#     byte-identically like the hero images), 404.html (GitHub Pages serves docs/404.html), sitemap.xml, robots.txt.
#     A `git clean -fd docs` + refresh therefore always re-creates them.
#   fed_path_newest(data_dir) -- ONE Fed-path vintage for the home (17) and Market Intel (30): the newer of the daily
#     file (fed_path_public.json, the 16:45 job) and the consensus run's own pull (consensus_public.json -> prediction).
# =====================================================================================================================
SITE_URL = "https://duiarte.github.io/ltcma"
SITE_NAME = "Carlos Duarte"
PLOTLY_FULL = "https://cdn.plot.ly/plotly-2.35.0.min.js"
PLOTLY_CARTESIAN = "https://cdn.plot.ly/plotly-cartesian-2.35.0.min.js"
# what the official plotly.js 2.35.0 cartesian bundle registers (lib/index-cartesian.js: scatter in the core + bar,
# box, contour, heatmap, histogram, histogram2d, histogram2dcontour, image, pie, scatterternary, violin); the r3
# browser probe reads Plotly.PlotSchema of the served file and asserts this set
CARTESIAN_TYPES = frozenset({"scatter", "bar", "box", "contour", "heatmap", "histogram", "histogram2d",
                             "histogram2dcontour", "image", "pie", "scatterternary", "violin"})
_PLOTLY_TAG = '<script src="{}"></script>'
FAVICONS = ("favicon.svg", "favicon_32.png", "apple_touch_180.png")
OG_KEYS = ("home", "portfolio", "stocks", "regime", "market_intel", "congress", "research")
SHARE_FILES = FAVICONS + tuple(f"og_{k}.png" for k in OG_KEYS)
# fix round 1 (r3 continuation, V2-9): what each 1200 x 630 card SHOWS (tools/make_share_assets.py CARDS: the page name
# and its one line, under the CD mark and "Carlos Duarte, Quantitative Research"), for og:image:alt -- an image's alt
# text describes the image, not the page it is attached to
OG_CARD_TEXT = {
    "home": ("Capital Market Assumptions", "A long-run model, my own live book and the markets around it"),
    "portfolio": ("Portfolio", "My own equity book, in pesos or dollars, against the S&P 500"),
    "stocks": ("Stock Research", "Composite picks, a pick tracker and CFA-style analyses of stocks"),
    "regime": ("Regime Tracker", "A composite stress index: economic, political, AI-cycle, environmental"),
    "market_intel": ("Market Intel", "What the Street expects, set against this site's own model"),
    "congress": ("Congress", "The trades members of Congress disclose, checked every weekday"),
    "research": ("Research", "The model, the research record, the strategies and the sources"),
}


def og_alt(card):
    n, line = OG_CARD_TEXT[card]
    return f"Card: {n}. {line}. Carlos Duarte, Quantitative Research."
_FONTS_HOST = "https://fonts.googleapis.com"
# page -> (name in the title, description (None = the page's own), card). Descriptions: <= 160 characters, no figure
# that can go stale, nothing that reads as advice.
PAGE_META = {
    "index.html": ("Capital Market Assumptions",
                   "A 12-year capital market assumptions model, my own live book against the S&P 500, the Fed path, "
                   "congressional trades and stock research on one page.", "home"),
    "portfolio.html": ("Portfolio",
                       "My own equity book in pesos or dollars: holdings, returns against the S&P 500, and every buy "
                       "and sell. Figures scaled; not a recommendation.", "portfolio"),
    "stocks.html": ("Stock Research",
                    "Composite stock picks, a pick tracker and CFA-style analyses of individual stocks, built from "
                    "public data. Research, not investment advice.", "stocks"),
    "regime.html": ("Regime Tracker",
                    "A composite stress index across economic, political, AI-cycle and environmental inputs, with its "
                    "history and recent regime changes.", "regime"),
    "ltcma-consensus.html": ("Market Intel",
                             "Long-run expected returns from the asset managers and banks that publish them, on one "
                             "grid against this site's model, with the market-implied Fed path.", "market_intel"),
    "street-ltcma.html": ("Street LTCMA",
                          "The Street's published capital market assumptions, aggregated by asset class.",
                          "market_intel"),
    "congressional-activity.html": ("Congress",
                                    "Trades that members of the U.S. Congress disclose under the STOCK Act, checked "
                                    "every weekday: signals, members, sectors and every filing.", "congress"),
    "research-library.html": ("Research Library", None, "research"),
    "research.html": ("Research Notes", "The research record behind this site's model and strategies, negative "
                      "results included.", "research"),
    "strategies.html": ("Strategies", "The strategy catalogue: systematic strategies with their backtest reports, "
                        "risks and limits. Research, not investment advice.", "research"),
    "projects.html": ("Projects", None, "research"),
    "glossary.html": ("Glossary", "Plain-language definitions of every term used on this site.", "research"),
    "404.html": ("Page not found", None, None),
}
_SHARE_RE = _re.compile(r'<!--share title0="([^"]*)"-->.*?<!--/share-->', _re.S)


def page_meta(page, html=""):
    """(title, description or None, card or None, canonical path) for a page, or None for a page this does not know."""
    import html as _h
    name = str(page).replace("\\", "/")
    if name in PAGE_META:
        lab, desc, card = PAGE_META[name]
        path = "" if name == "index.html" else name
        return f"{lab} · {SITE_NAME}", desc, card, path
    m = _re.fullmatch(r"stock_([A-Z][A-Z0-9.\-]*)\.html", name)
    if m:
        t = m.group(1)
        return (f"{t} · Stock Research · {SITE_NAME}",
                f"A CFA-style analysis of {t} from public data: valuation multiples, 12-month targets by method and "
                "price history. Research, not investment advice.", "stocks", name)
    if _re.fullmatch(r"bt_[a-z0-9_]+\.html", name):
        t0 = _re.search(r"<title>(.*?)</title>", html, _re.S)
        lab = _h.unescape(t0.group(1)) if t0 else name
        lab = _re.sub(r"\s+[—-]\s+Backtest Report\s*$", "", lab).strip()
        return (f"{_h.escape(lab, quote=False)} · Backtest report · {SITE_NAME}",
                "A backtest report from the strategy catalogue: method, results, risks and limits. Research, not "
                "investment advice.", "research", name)
    m = _re.fullmatch(r"archive/report_[0-9\-]+\.html", name)
    if m:
        t0 = _re.search(r"\((archived [^)]+)\)", html[:4000])
        tag = f" ({t0.group(1)})" if t0 else " (archived edition)"
        return (f"Full Report{tag} · {SITE_NAME}",
                "The 12-year capital market assumptions model: method, return tables and limits, as archived.",
                "research", name)
    return None


def _plotly_bundle(html):
    """The pinned full bundle -> the official cartesian bundle of the same version when every trace type on the page
    is cartesian (and back, when a page gains a non-cartesian trace). A page whose figures cannot be read keeps the
    bundle it has."""
    full, cart = _PLOTLY_TAG.format(PLOTLY_FULL), _PLOTLY_TAG.format(PLOTLY_CARTESIAN)
    if full not in html and cart not in html:
        return html
    try:
        types = {tr.get("type", "scatter") for _d, data, _l in _plotly_calls(html) for tr in data}
    except (ValueError, AttributeError):
        return html
    want = cart if types and types <= CARTESIAN_TYPES else full
    other = full if want == cart else cart
    return html.replace(other, want)


def _attr(s):
    import html as _h
    return _h.escape(_h.unescape(str(s)), quote=True)


def _enc_t0(t):
    """The page's own title, kept inside the share block's opening comment (lossless; no '"' and no '--' in it)."""
    return t.replace("%", "%25").replace('"', "%22").replace("--", "-%2D")


def _dec_t0(t):
    return t.replace("-%2D", "--").replace("%22", '"').replace("%25", "%")


def share_strip(html):
    """Remove the share block and put the page's own <title> back (exact inverse of site_head's head part)."""
    m = _SHARE_RE.search(html)
    if not m:
        return html
    t0 = _dec_t0(m.group(1))
    html = html[:m.start()] + html[m.end():]
    return _re.sub(r"<title>.*?</title>", lambda _m: f"<title>{t0}</title>", html, count=1, flags=_re.S)


def site_head(html, page="page"):
    """The r3 head for one generated page (see the block comment above). Idempotent."""
    html = _plotly_bundle(html)
    if "<!--share" in html:
        html = share_strip(html)
    pm = page_meta(page, html)
    if pm is None or html.count("<title>") != 1 or html.count("</head>") != 1 or 'http-equiv="refresh"' in html:
        return html
    title, desc, card, path = pm
    m = _re.search(r"<title>(.*?)</title>", html, _re.S)
    t0 = m.group(1)
    own = _re.search(r'<meta name="description" content="([^"]*)">', html)
    url = f"{SITE_URL}/{path}"
    out = [f'<!--share title0="{_enc_t0(t0)}"-->']
    if page == "404.html":
        out.append('<meta name="robots" content="noindex">')
    else:
        if own:                                   # the page's own description wins (merge, never two)
            desc = own.group(1)
        elif desc:
            out.append(f'<meta name="description" content="{_attr(desc)}">')
        out.append(f'<link rel="canonical" href="{url}">')
        out.append('<meta property="og:type" content="website">'
                   f'<meta property="og:site_name" content="{SITE_NAME} · Quantitative Research">'
                   f'<meta property="og:title" content="{_attr(title)}">'
                   + (f'<meta property="og:description" content="{_attr(desc)}">' if desc else "")
                   + f'<meta property="og:url" content="{url}">')
        if card:
            img = f"{SITE_URL}/{ASSET_URL}/og_{card}.png"
            out.append(f'<meta property="og:image" content="{img}">'
                       '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
                       f'<meta property="og:image:alt" content="{_attr(og_alt(card) if card in OG_CARD_TEXT else title)}">'
                       '<meta name="twitter:card" content="summary_large_image">'
                       f'<meta name="twitter:image" content="{img}">')
        out.append(f'<meta name="twitter:title" content="{_attr(title)}">'
                   + (f'<meta name="twitter:description" content="{_attr(desc)}">' if desc else ""))
    out.append(f'<link rel="icon" href="{ASSET_URL}/favicon.svg" type="image/svg+xml">'
               f'<link rel="icon" href="{ASSET_URL}/favicon_32.png" sizes="32x32" type="image/png">'
               f'<link rel="apple-touch-icon" href="{ASSET_URL}/apple_touch_180.png">')
    if _FONTS_HOST in html:
        out.append(f'<link rel="preconnect" href="{_FONTS_HOST}">'
                   '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    out.append(SITE_JS)                           # fix round 1 (r3 continuation): V2-11 / V2-12
    out.append("<!--/share-->")
    return html[:m.start()] + f"<title>{title}</title>" + "\n".join(out) + html[m.end():]


ROBOTS_TXT = f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"
# fix round 1 (r3 continuation, 2026-11-11): one small script in the r3 head (the share block), so every page -- generated,
# or committed and transformed by the deploy's commit 2 -- carries it, and share_strip takes it out again:
#   V2-11 a cold load with #id: once the page has loaded, again when the fonts are in and once more at 1.2 s, the target
#         is aligned under the sticky header / bar (scroll-padding-top), unless the viewer scrolled, clicked or pressed a
#         key meanwhile; smooth anchor scrolling (html.sm, style.css) starts only after that, so the browser's own
#         fragment scroll never animates towards a position the late layout (fonts, charts) moves
#   V2-12 a "Skip to content" link, the first Tab stop (style.css .skip: off-screen until focused): focus to <main>
# polish round (r3, 2026-11-11, V-5): once the web fonts are in, every Plotly chart is redrawn. Plotly measures a text
#   once and caches its width by the text + its style, so a chart drawn before Inter arrived keeps the fallback font's
#   widths (the regime legend's text ran past its box, the track-record legend items touched): a redraw alone hits the
#   same cache. The redraw sets font.weight 400 (= normal: the same look, a new style string, so Plotly measures
#   again); a second pass (399: still the regular face, none lighter is loaded) runs only if a font face finished
#   loading in the 1.5 s after the first. A chart that sets its own weight keeps it. The theme script re-maps the
#   colours after any relayout and finds nothing to change; the currency switch and the mobile tuner never set the
#   weight, so they keep it. (No `name=number` literal in the script: scripts/confscan.sh lists those on the research
#   pages, and a counter like that would be a new hit.)
SITE_JS = ("<script>(function(){var d=document.documentElement,mv=false;"
           "['wheel','touchstart','keydown','mousedown'].forEach(function(k){addEventListener(k,function(){mv=true;},"
           "{passive:true,once:true});});"
           "function fix(){var h=location.hash.slice(1),t=null;if(h){try{t=document.getElementById(decodeURIComponent(h));}"
           "catch(e){}}if(t&&!mv)t.scrollIntoView({block:'start'});}"
           "var FW=[400,399],FQ=FW.slice(),late=false;"
           "function rf(){var P=window.Plotly,w=FQ.shift();if(!P||!P.relayout||w===undefined)return;"
           "[].forEach.call(document.querySelectorAll('.js-plotly-plot'),function(g){if(!g._fullLayout)return;"
           "var o=g.layout&&g.layout.font&&g.layout.font.weight;if(o!==undefined&&o!=='normal'&&FW.indexOf(o)<0)return;"
           "try{var r=P.relayout(g,{'font.weight':w});if(r&&r.catch)r.catch(function(){});}catch(e){}});}"
           "addEventListener('load',function(){fix();try{document.fonts.ready.then(function(){rf();"
           "document.fonts.addEventListener('loadingdone',function(){late=true;});"
           "setTimeout(function(){if(late)rf();},1500);setTimeout(fix,250);});}"
           "catch(e){}setTimeout(function(){fix();d.classList.add('sm');},1200);});"
           "document.addEventListener('DOMContentLoaded',function(){var m=document.querySelector('main');"
           "if(!m||document.querySelector('a.skip'))return;if(!m.id&&!document.getElementById('site-main'))m.id='site-main';"
           "if(!m.id)return;if(!m.hasAttribute('tabindex'))m.tabIndex=-1;"
           "var a=document.createElement('a');a.className='skip';a.href='#'+m.id;a.textContent='Skip to content';"
           "a.addEventListener('click',function(e){e.preventDefault();m.focus({preventScroll:true});"
           "m.scrollIntoView({block:'start'});});document.body.insertBefore(a,document.body.firstChild);});})();</script>")


def sitemap_xml(docs_dir):
    """Every public page that exists in docs/: the main tabs, the Research corner, then the stock / backtest /
    archived-report sub-pages. Redirect stubs, internal/ and the AI copies are not listed; no lastmod (a date here
    would be one more stamp to keep true)."""
    import glossary as _g          # lazy: glossary imports this module
    names, seen = [], set()
    for h in [h for h, _t in _g.MAIN_TABS] + [h for h, _t, _d in _g.RESEARCH_LINKS]:
        n = h.split("#")[0]
        if n not in seen:
            seen.add(n)
            names.append(n)
    subs = []
    for rx, _par in _g.SUBPAGES:
        base = rx.split("/")[0] if "/" in rx else ""
        d = _os.path.join(docs_dir, base) if base else docs_dir
        if _os.path.isdir(d):
            for f in sorted(_os.listdir(d)):
                rel = f"{base}/{f}" if base else f
                if _re.fullmatch(rx, rel):
                    subs.append(rel)
    urls = []
    for n in names + subs:
        p = _os.path.join(docs_dir, *n.split("/"))
        if not _os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            if 'http-equiv="refresh"' in fh.read(3000):
                continue
        urls.append(f"{SITE_URL}/" + ("" if n == "index.html" else n))
    body = "".join(f"<url><loc>{u}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")


def page_404():
    """docs/404.html: GitHub Pages serves it for any missing path, at any depth, so every link and sheet resolves from
    the site root (<base href="/ltcma/">); noindex."""
    import glossary as _g          # lazy: glossary imports this module
    tabs = "".join(f'<a class="chipbtn" href="{h}">{t}</a>' for h, t in _g.MAIN_TABS)
    rc = "".join(f'<li><a href="{h}">{t}</a> &middot; {d}</li>' for h, t, d in _g.RESEARCH_LINKS)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<base href="/ltcma/">
<title>Page not found</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
{CSS_LINKS}<link rel="stylesheet" href="style.css"></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{_g.NAV}
</div></header>
<section class="hero"><div class="container"><p class="kicker">Page not found</p><h1>This page does not exist</h1>
<p class="lede">The address may be mistyped, or the page may have moved. Every page of the site is one click away:
the tabs above, or the links below.</p></div></section>
<main class="container nf-main">
<section class="block"><h2>The tabs</h2><div class="nf-tabs" style="display:flex;flex-wrap:wrap;gap:8px">{tabs}</div></section>
<section class="block"><h2>The Research corner</h2><ul class="sumlist nf-list">{rc}</ul></section>
</main>
<footer class="shell-foot"><div class="container"><p>Research and education, not investment advice.</p></div></footer>
</body></html>"""
    return themed(html, "404.html")


def emit_share(docs_dir):
    """Write the share files into docs/ (17 calls it on every build, beside emit()): the favicon set and the cards from
    assets/img (byte-identical, idempotent), 404.html, sitemap.xml, robots.txt (rewritten only when they change).
    Returns True when every image source exists (False in a sandbox without assets/: the pages still name them)."""
    ok = emit_assets(docs_dir, SHARE_FILES)
    for name, body in (("404.html", page_404()), ("sitemap.xml", sitemap_xml(docs_dir)), ("robots.txt", ROBOTS_TXT)):
        p = _os.path.join(docs_dir, name)
        try:
            with open(p, encoding="utf-8") as fh:            # text mode both ways (CRLF on Windows, as the pages)
                if fh.read() == body:
                    continue
        except OSError:
            pass
        with open(p, "w", encoding="utf-8") as fh:            # text mode, as every page
            fh.write(body)
    return ok


def emit_sitemap(docs_dir):
    """Fix round 1 (r3 continuation, PIPE2-2): docs/sitemap.xml = sitemap_xml(docs_dir), rewritten only when it changes.
    17 writes it first (emit_share); 31_research_library.py, the refresh's last page generator, calls this so a page
    added after 17 in the same refresh (a new bt_*.html from 24) is listed the same day. Returns True when written."""
    body, p = sitemap_xml(docs_dir), _os.path.join(docs_dir, "sitemap.xml")
    try:
        with open(p, encoding="utf-8") as fh:
            if fh.read() == body:
                return False
    except OSError:
        pass
    with open(p, "w", encoding="utf-8") as fh:            # text mode, as emit_share writes it
        fh.write(body)
    return True


def fed_path_newest(data_dir):
    """The Fed path ONE vintage of which every Fed figure on a page is drawn from (wave r3: Market Intel showed the
    next FOMC's odds from two pulls at once). The newer by taken_at of data/market_intel/fed_path_public.json (written
    by the 16:45 market-intel-daily job) and the consensus run's own pull (consensus_public.json -> prediction.fed_path,
    taken at prediction.taken_at). Same shape as fed_path_public.json plus "_source" ("daily" | "consensus"); None when
    neither file carries meetings."""
    import json
    mi = _os.path.join(data_dir, "market_intel")
    best = None
    try:
        with open(_os.path.join(mi, "fed_path_public.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict) and d.get("meetings"):
            best = dict(d, _source="daily")
    except (OSError, ValueError):
        pass
    try:
        with open(_os.path.join(mi, "consensus_public.json"), encoding="utf-8") as fh:
            pm = (json.load(fh) or {}).get("prediction") or {}
        fp, t = pm.get("fed_path") or {}, str(pm.get("taken_at") or "")
        if isinstance(fp, dict) and fp.get("meetings") and t and \
                (best is None or t[:19] > str(best.get("taken_at") or "")[:19]):
            best = dict(fp, taken_at=t, _source="consensus")
    except (OSError, ValueError, AttributeError):
        pass
    return best


# =====================================================================================================================
# Wave r3 (builder B, Carlos written 2026-11-10 ~15:00 "Dale play a todo"): the sticky "On this page" bar and note().
# =====================================================================================================================
# The long pages' sections: (id, short label). A link is drawn only when its id is on the page (a section a generator
# leaves out on a data gap simply has no link); ids are the pages' own (never renamed): 18 / 23 gained ids for their
# sections that had none. The archived report (<base href="../">) links through its own path.
PAGE_SECTIONS = {
    "portfolio.html": (("performance", "Performance"), ("entries", "Entries & exits"), ("value", "Value vs cost"),
                       ("fxa-root", "FX"), ("holdings", "Holdings"), ("realized", "Realized"),
                       ("relative", "vs holdings")),
    "stocks.html": (("picks", "Picks"), ("tracker", "Pick Tracker"), ("track-record", "Track record"),
                    ("signals", "Macro signals"), ("companies", "Company reports")),
    "congressional-activity.html": (("alerts", "Signals"), ("members", "Members"), ("sectors", "Sectors"),
                                    ("trades", "Trades"), ("method", "Method")),
    "strategies.html": (("growth", "Growth of 100"), ("drawdown", "Drawdown"), ("mexico", "Mexico vs IPC"),
                        ("indicators", "Indicators"), ("ember", "EMBER"), ("rotation-family", "Rotation family"),
                        ("backtests", "Backtests")),
}
REPORT_PAGE = r"archive/report_[0-9\-]+\.html"
REPORT_SECTIONS = (("1-executive-summary", "Summary"), ("2-methodology", "Method"),
                   ("3-macro-backdrop-fundamentals-grid", "Macro"), ("4-priced-in-indicators", "Priced in"),
                   ("5-expected-returns", "Returns"), ("6-risk-volatility-correlation", "Risk"),
                   ("7-news-regimes-monte-carlo-simulation", "Regimes & simulation"),
                   ("8-strategic-edge-scan", "Edge scan"), ("9-sample-portfolios", "Portfolios"),
                   ("10-systematic-strategy-layer-dynamic-regime-overlays", "Strategy layer"),
                   ("11-assumptions-limitations-sources", "Assumptions"))
OTP_MARK = '<nav class="otp" aria-label="On this page">'
# portfolio.html: r2's sticky currency bar (18 still writes it as the first block of <main>); its switch moves into
# the bar's right end, so the page has ONE sticky strip
_CCY_BAR = _re.compile(r'<div class="ccy-bar">(<div class="ccy-in" role="group"[^>]*>.*?</button></div></div>)</div>\n?',
                       _re.S)
OTP_JS = r"""<script>(function(){var n=document.querySelector('nav.otp');if(!n)return;var d=document.documentElement,
sc=n.querySelector('.otp-sc'),as=[].slice.call(n.querySelectorAll('.otp-l a')),secs=[],last=-2;
function look(){secs=as.map(function(a){var h=a.getAttribute('href');return document.getElementById(decodeURIComponent(h.slice(h.indexOf('#')+1)));});}
function hgt(){var st=getComputedStyle(n).position==='sticky';d.style.setProperty('--otph',(st?n.offsetHeight:0)+'px');}
function fade(){var l=sc.scrollLeft>2,r=sc.scrollLeft+sc.clientWidth<sc.scrollWidth-2;sc.classList.toggle('fl',l);sc.classList.toggle('fr',r);}
function cur(){if(!secs.length||!secs[secs.length-1])look();
var top=(parseFloat(getComputedStyle(d).getPropertyValue('--hdr'))||0)+n.offsetHeight+24,k=-1;
for(var i=0;i<secs.length;i++){if(secs[i]&&secs[i].getBoundingClientRect().top<=top)k=i;}
if(k===last)return;last=k;
as.forEach(function(a,i){if(i===k)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});
if(k>=0&&sc.scrollWidth>sc.clientWidth&&!n.contains(document.activeElement)){var ar=as[k].getBoundingClientRect(),
sr=sc.getBoundingClientRect();if(ar.left<sr.left||ar.right>sr.right)sc.scrollLeft+=ar.left-sr.left-24;}}
var raf=null;function tick(){if(!raf)raf=requestAnimationFrame(function(){raf=null;cur();});}
sc.addEventListener('scroll',fade,{passive:true});window.addEventListener('scroll',tick,{passive:true});
n.addEventListener('focusin',function(e){var a=e.target;if(!a||!sc.contains(a))return;var ar=a.getBoundingClientRect(),
sr=sc.getBoundingClientRect();if(ar.left<sr.left+28)sc.scrollLeft-=sr.left+28-ar.left;
else if(ar.right>sr.right-28)sc.scrollLeft+=ar.right-(sr.right-28);});
window.addEventListener('resize',function(){hgt();fade();tick();});hgt();fade();
function go(){look();cur();window.addEventListener('load',tick);
if(window.ResizeObserver)new ResizeObserver(tick).observe(document.body);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go();})();</script>"""


def page_sections(page):
    if page in PAGE_SECTIONS:
        return PAGE_SECTIONS[page]
    if _re.fullmatch(REPORT_PAGE, page or ""):
        return REPORT_SECTIONS
    return None


def section_nav(page, html, right=""):
    """The bar for `page`: the sections whose id is on `html` (in the table's order), the optional right-hand control
    (portfolio: the currency switch). '' when fewer than two sections are on the page."""
    secs = page_sections(page) or ()
    have = [(i, lab) for i, lab in secs if f'id="{i}"' in html]
    if len(have) < 2:
        return ""
    pre = page if "<base href=" in html[:4000] else ""          # the archived report resolves links against ../
    lis = "".join(f'<li><a href="{_esc(pre)}#{_esc(i)}">{_esc(lab)}</a></li>' for i, lab in have)
    return (f'{OTP_MARK}<div class="container otp-in"><span class="otp-k" aria-hidden="true">On this page</span>'
            f'<div class="otp-sc"><ul class="otp-l">{lis}</ul></div>{right}</div>{OTP_JS}</nav>\n')


def otp_insert(html, page="page"):
    """Wave r3: put the sticky "On this page" bar on a long page (PAGE_SECTIONS / the archived report), right before
    <main>. Run by themed() on every generated page (like site_head), by the r3 deploy on the committed pages and so by
    the previews. Idempotent: a page that already has the bar is returned unchanged. On portfolio.html the currency
    switch of r2's .ccy-bar moves into the bar (one sticky strip)."""
    if OTP_MARK in html or not page_sections(page):
        return html
    right, out = "", html
    if page == "portfolio.html":
        m = list(_CCY_BAR.finditer(out))
        if len(m) == 1:
            right = m[0].group(1)
            out = out[:m[0].start()] + out[m[0].end():]
    nav = section_nav(page, out, right)
    # the one <main> start tag outside <script> / <style> (a comment or a string may name it)
    pos, at = [], 0
    for k, seg in enumerate(_SEG.split(out)):
        if k % 2 == 0:
            pos += [at + mm.start() for mm in _re.finditer(r"<main[\s>]", seg)]
        at += len(seg)
    if not nav or len(pos) != 1:
        return html
    return out[:pos[0]] + nav + out[pos[0]:]


def note(body, role="method", summary="How these figures are built", cls=""):
    """Wave r3: the one component for the explanatory notes. role="disclosure": always visible, at most two sentences,
    a thin amber rule (e.g. the portfolio's scaling disclosure, kept above the first money figure). role="method": a
    native <details> closed by default, `summary` naming what is inside (works without JavaScript; find-in-page opens
    it). `body` is HTML (paragraphs allowed in a method note)."""
    c = f" {cls}" if cls else ""
    if role == "disclosure":
        return f'<p class="nt nt-d{c}">{body}</p>'
    return f'<details class="nt nt-m{c}"><summary>{summary}</summary><div class="nt-b">{body}</div></details>'


# =====================================================================================================================
# Wave r3 (builder C, Carlos written 2026-11-10 ~15:00 "Dale play a todo"): the Stock Research tables become cards on
# phones. card_tables() is pure markup on a page (no text changes): every table.ptable that sits in its scrolling tile
# (<div class="tile" style="...overflow-x:auto">) gets the tile class `pcw`, and every body cell of that table (not the
# cells of a nested table, e.g. the Pick Tracker's detail drawers) its column's header text as data-label. style.css
# (ET_CSS, "wave r3 (builder C)") draws each row as a card below BP_SM px: the label on the left, the value on the right,
# the row's first cell (+ the ticker cell of the picks / tracker tables) as the card's head. Desktop is unchanged. 25 runs
# it on stocks.html (25_stock_picks.main); the staged preview runs the SAME function on the committed page. Idempotent.
# =====================================================================================================================
CARD_WRAP = "pcw"
_CARD_TILE = _re.compile(r'<div class="tile"( style="[^"]*overflow-x:auto[^"]*">)(\s*)(<table class="ptable(?: [^"]*)?">)')
_CARD_TAG = _re.compile(r"<(/?)(table|thead|tbody|tr|td|th)\b([^>]*)>", _re.I)
_COLSPAN = _re.compile(r'\bcolspan="(\d+)"')


def _cell_text(s):
    import html as _h
    return _re.sub(r"\s+", " ", _h.unescape(_re.sub(r"<[^>]+>", " ", s))).strip()


def _table_end(html, start):
    """index just past the </table> that closes the <table> starting at `start` (nested tables counted), or -1"""
    depth = 0
    for m in _re.finditer(r"<(/?)table\b[^>]*>", html[start:], _re.I):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start + m.end()
    return -1


def card_labels(table):
    """One '<table>...</table>' string: each body <td> of the OUTER table gets data-label = its column's header text
    (the outer <thead>'s first row; colspan honoured). A cell spanning several columns, a cell under an empty header
    and every cell of a nested table get none; a cell that already has a data-label keeps it."""
    heads, depth, sect, col, out, last = [], 0, "", 0, [], 0
    for t in _CARD_TAG.finditer(table):
        close, tag, attrs = t.group(1), t.group(2).lower(), t.group(3)
        if tag == "table":
            depth += -1 if close else 1
            continue
        if depth != 1:
            continue
        if tag in ("thead", "tbody"):
            sect = "" if close else tag
            continue
        if tag == "tr" and not close:
            col = 0
            continue
        if close or tag not in ("td", "th"):
            continue
        sp = _COLSPAN.search(attrs)
        n = int(sp.group(1)) if sp else 1
        if sect == "thead":
            if tag == "th":
                end = table.find("</th>", t.end())
                heads += [_cell_text(table[t.end():end]) if n == 1 else ""] * n
            continue
        if tag == "td" and n == 1 and "data-label=" not in attrs and col < len(heads) and heads[col]:
            out.append(table[last:t.end() - 1] + f' data-label="{_esc(heads[col])}"')
            last = t.end() - 1
        col += n
    out.append(table[last:])
    return "".join(out)


def card_tables(html):
    """Wave r3 (builder C): the phone cards of every table.ptable in a scrolling tile (see the block comment above)."""
    out, pos = [], 0
    for m in _CARD_TILE.finditer(html):
        if m.start() < pos:
            continue                                          # inside a table already handled
        t0 = m.start(3)
        t1 = _table_end(html, t0)
        if t1 < 0:
            continue
        out.append(html[pos:m.start()])
        out.append(f'<div class="tile {CARD_WRAP}"' + m.group(1) + m.group(2) + card_labels(html[t0:t1]))
        pos = t1
    out.append(html[pos:])
    return "".join(out)
