# Website Style Guide — Carlos Duarte · Quantitative Research

Institutional editorial identity. Reference: FT research / Bridgewater Daily
Observations. **Restraint is the design constraint — when in doubt, remove decoration.**

> **2026-11-10: superseded in part by "Editorial Terminal"** (Carlos approved the design canvas: "El diseno quedo
> muy bien, hazle push, pero manten varias de las pestanas"). The section at the END of this file wins where it
> disagrees with the older rules below (palette, card corners, shadows on hover, image heroes, the header).

## Source of truth
- Tokens live in `scripts/17_build_site.py` → `CSS` var → written to `docs/style.css`.
  Every page `<link>`s `style.css`; edit the CSS var, not per-page.
- Shared nav/brand/glossary: `scripts/glossary.py` (`NAV` incl. active-state JS).
- Backtest-card CSS (`.bt-*`): `scripts/24_backtests.py` → `PAGE_CSS` (injected inline).
- Plotly per-script constants: `INK="#111111"`, `BLUE="#0a2540"` (accent), `GOLD→#6b7280`,
  `GREEN→#0a5d3a`, `RED→#7c2d12`, `GREY→#888888`. Chart font family = Inter.

## Color (monochrome + ONE accent)
| token | hex | use |
|---|---|---|
| `--bg` | `#fafafa` | page background |
| `--panel` | `#ffffff` | tiles, cards |
| `--ink` | `#111111` | text, numbers |
| `--sec` | `#555555` | secondary text |
| `--muted` | `#888888` | labels, captions |
| `--line` | `#e5e5e5` | hairline borders, chart grid |
| `--line-strong` | `#d4d4d4` | header rules |
| `--accent` | `#0a2540` | Oxford blue — links + key data ONLY |
| `--accent-tint` | `rgba(10,37,64,.045)` | hover background |
| `--pos` / `--neg` | `#0a5d3a` / `#7c2d12` | forest / oxblood |
| status | `#0a5d3a` `#1e3a8a` `#5b21b6` `#6b7280` | desaturated green/blue/purple/gray |

## Type
- Serif (headings, brand): `Spectral` → `Charter, Cambria, Georgia, serif`.
- Sans (body): `Inter` 400/500 → `system-ui, "Segoe UI", Roboto`.
- Mono (figures, repo handles): `JetBrains Mono` → `ui-monospace, Consolas`.
- `font-variant-numeric: tabular-nums` on EVERY table cell + tile metric.
- Line-height 1.55 body / 1.25 headings. No weight > 600 (h1 caps at 600).
- CDN: `Spectral:400;500;600 + Inter:400;500 + JetBrains+Mono:400;500`.

## Layout
- Page width `min(1100px,92vw)`. Section padding `4rem 0` (mobile `3rem`).
- Tile/grid gap `1.5rem`. No shadows — hairline 1px borders + hover bg tint only.
- No gradients, glass, blur, neon. Transitions ≤ 150ms ease-out, color/bg only.

## Components
- **Hero**: editorial — serif h1, sec lede, mono `asof`. No bg image/gradient/glow.
- **Tiles**: hairline border, no shadow; `.mv` large mono ink number; `.mk` label
  `uppercase .06em 11px var(--muted)` below.
- **Tables** (`.ptable`/`.report`): no zebra, hairline row rules, tabular-nums,
  numeric cols right-aligned, header = small uppercase muted, no dark fill.
- **Cards** (`.btcard`/`.scard`): 1px border, no shadow, hover = accent tint.
  Status shown via desaturated 3px top-border + square badge.
- **Footer**: minimal, hairline top, `0.85rem` muted, single accent link.
- **Nav**: flat, no dropdowns; active = 2px accent underline (set by `NAV` JS),
  not a filled pill. Brand = serif 500, tracking `.03em`.

## Charts (plotly)
- Primary series accent `#0a2540`; secondary muted `#888888`. No fills/gradients.
- Grid `#e5e5e5` (single weight). Font Inter; mono tick/axis where tabular.
- Already-embedded charts inherit new fonts/accent on next full `daily_refresh`.
- ⚠️ **`font.family` must name a family the page actually `<link>`s** — Spectral, Inter or
  JetBrains Mono. A missing family is a silent browser fallback, not an error: from at least
  2026-06 to 2026-08-12 `18_portfolio.py` asked for `"IBM Plex Sans"`, which no page has ever
  loaded, so its charts rendered in the generic sans beside Inter body text. Grep
  `scripts/*.py` for stray `family=` values.
- **Numbers are mono, labels are sans** — set `tickfont` and `hoverlabel.font` to the
  JetBrains Mono stack so figures match `.asof` / `.mv`; leave `font` / `title_font` Inter.
- **No in-plot `title` when an HTML `<h2>` sits above the chart**, and no `xaxis_title` on a
  date axis. Carry the vintage in a mono `<p class="asof">` under the heading instead.
- **One meaning per colour per chart.** `GREEN #0a5d3a` = buy / positive; if a line is also
  green, move the line (cost basis → `GREY #888888`).
- Hover: `hovermode="x unified"` + `xaxis.hoverformat` prints the date header itself — don't
  repeat it in the trace text. Multi-line bodies use `<br>`; whitespace alignment does not
  survive HTML. Separator `·` U+00B7, never `•` U+2022.
- ⚠️ **Hover `text` is public surface.** Anything scaled elsewhere on the page must be scaled
  in the hover too, and guarded — see `WEBSITE_DEPLOY.md § Chart hovers are public surface`.

## Apply / verify
- Regen via WSL `daily_refresh.sh` (hub `~/LTCMA`). On native Windows, edit the
  CSS var in `17_build_site.py` and re-run renderers, or transform `docs/*.html`.
- Verify computed styles with a static server + DOM inspect (screenshots block on
  the slow Fonts CDN `load` event; inspect/eval are reliable).

## 2026-11-10: Editorial Terminal (binding since the remake; wins over the rules above)
Source of truth: `scripts/design_system.py` (`ET` tokens, `ET_CSS` appended to `docs/style.css` by
`17_build_site.py`, `hero()`, `photo()`, `credits_footer()`, `TABS_JS`). The legacy rules above stay in `style.css`
underneath; removing the appended layer restores the previous look on every page at once. Dark mode: see
"2026-11-10 wave r2: dark mode" below.

| token | hex | use |
|---|---|---|
| ground `--bg` | `#F6F5F1` | page background (warm) |
| card `--panel` | `#FFFFFF` | tiles, cards |
| line / strong | `#E3E1DA` / `#C9C6BC` | hairlines, pill borders |
| ink / secondary / muted | `#0E1726` / `#4A5568` / `#667085` | text (every text pair >= 4.5:1) |
| chip | `#EFEDE6` | as-of chip, bar tracks |
| accent | `#0A2540` | Oxford blue, unchanged: links, the active tab, primary series |
| **amber** `--amber` | `#B45309` | NEW, highlight only: kicker labels, a hike, the one number to look at |
| up / down `--up` `--down` | `#0F5E9C` / `#C2410C` | NEW components only: bought / up vs sold / down (colour-blind safe). Existing `--pos` / `--neg` and the chart `POS` / `NEG` are unchanged in this wave |

- **Type:** unchanged families (Spectral display, Inter body/UI, JetBrains Mono for every number; ds_gate A9).
  Weights stay <= 500 in shared CSS (the pages load Inter 400/500).
- **Header:** brand (CD monogram) + the main tabs (underline, sticky: Dashboard, Portfolio, Stock Research, Regime
  Tracker, Market Intel, Congress, About) + the **Research corner** at the right end (`<details>` menu inside its own
  "Research" navigation landmark: Research Library, Full Report, Research Notes, Strategies, Projects, Glossary,
  Sources). Defined once in `glossary.NAV`; works without JS, with the keyboard (focus leaving the menu closes it)
  and on touch; the menu scrolls inside itself on short screens. One row from 1280 px (`design_system.NAV_BP` =
  1279: below it the header wraps to two rows and the tabs scroll, with a fade on the side where a tab is cut).
  Every page under `docs/` must be a main tab, a corner page, a `glossary.SUBPAGES` sub-page or a redirect stub
  (ds_gate R1). Anchors and sticky table heads clear the header (`--hdr`, `scroll-padding-top`).
- **Cards:** radius 14-18 px, hairline border, hover lifts 2 px with a soft shadow and the accent border (150 ms);
  `prefers-reduced-motion` turns motion off. One big number per card; kicker label in amber, uppercase.
- **Pill tabs / toggles / chips / the Research button:** min-height 44 px, selected = ink fill. In-page tabs use
  `design_system.TABS_JS` (ARIA tablist, arrows / Home / End; without JS every panel shows).
- **One as-of chip per page** (the hero's `.asof` line renders as the chip; the text is unchanged because the
  freshness guards and the market-intel jobs read it).
- **Image heroes (JWST):** only on Dashboard (Cosmic Cliffs), Portfolio and the Research Library (Cliffs detail),
  Market Intel (Pillars), Congress (Pillars, lower detail). Under a 64% dark layer (a little deeper under the text
  column, 72% on phones; small text over a hero sits on its own dark backdrop: worst-pixel contrast >= 4.5:1), never
  behind a chart, credit line visible in the hero AND in the footer (title, "cropped", credit, CC BY 4.0 + links).
  Images live in `assets/img/` (committed, EXIF-free) and are emitted byte-identically into `docs/assets/img/` by
  each generator that shows one. No image > 1.2 MB; phones get a 9:16 portrait WebP (720 / 1080 px, <= 250 KB),
  larger screens the 16:9 WebP 1600 / 2560 / 2880 / 3840 (tablets ask for 150vw: a 16:9 image covering a taller box
  is drawn wider than the screen). On phones the heroes stay about one screen tall (stats 2 x 2, CTAs side by side;
  the home's performance panel shows from 641 px up; the Hold card's dollar row is its phone twin, `.ph-only`).
- **Photo:** the About section shows Carlos's portrait (EXIF-free copies only; never the original in Pictures).
- **Charts:** palette, heights, hovers and guards unchanged by the remake; dark mode maps them (below).
- **One figure, one place (2026-11-10, Carlos: "intenta que no se repita info en la misma pestana").** A headline
  figure (hero stat or panel, tile, card, badge, bar list, lede) is shown ONCE per page and viewport: prose names
  the tile instead of restating it, a bar list draws its bars inside its own table, a summary card shows what the
  page below does not. A copy shown only <= 640 px and another only >= 641 px is one place (`.ph-only` / the hero
  panel). Tables, charts, chips, legends, the as-of chip and footers are not counted. ds_gate R8
  (`scripts/fig_repeats.py`, run in the refresh by `guard_site_rules.py`) fails a repeat unless `fig_repeats.ALLOW`
  lists it with a reason.
- **One currency at a time (portfolio.html, 2026-11-10, Carlos: "se pueda segmentar entre mxn y usd, no que los
  dos esten encimados").** One MXN | USD switch (sticky under the header, `aria-pressed`, remembered per viewer in
  localStorage) drives every figure and every chart; no chart draws both currencies. Pesos without JavaScript
  (the book's currency). The currency's share of a return is stated once, in FX Attribution.

## 2026-11-10 wave r2: dark mode (Carlos: "Modo oscuro siguiente paso si")
- **Mechanics (one place: the THEME block of `scripts/design_system.py`).** A page is dark-capable when its generator
  writes it through `design_system.themed()`: the head gets `HEAD_LINKS` (a boot script that sets `data-theme` on
  `<html>` BEFORE the first paint from the viewer's choice in localStorage `ltcma-theme`, every access in
  try/catch, plus the link to `_design_system/theme.css`) and every colour literal in the page's `<style>` blocks and
  `style=""` attributes becomes `var(--token, <the same literal>)`. `17` writes `style.css` through `themed_css()`.
  The literal stays as the fallback, so the light theme renders the old colour by construction. `theme.css`
  (`THEME_CSS`, emitted by `design_system.emit()` from 17) holds the dark value of every token, twice: under
  `@media screen and (prefers-color-scheme: dark)` for `:root:not([data-theme="light"])` (no JS, or the control on
  Auto) and under `@media screen` for `:root[data-theme="dark"]` (an explicit choice). Print never matches: it stays
  light. A page that is not themed (an older committed copy, `internal/freshness.html`) does not link theme.css, so
  it stays light whatever the system says: no page can go dark with unconverted CSS.
- **The control** (`THEME_BUTTON` + `THEME_JS`, inside `glossary.NAV`, right of the Research corner): one 44 px button,
  every press flips the look (light <-> dark); picking the device's own look means Auto again (follow the device),
  so no press is ever invisible (review round 1). `aria-label` names the current mode and the next one, a polite
  status line announces the change; theme.css sets `--thm-ok` and the script keeps charts light if it did not load; hidden without JS (the media query then follows the system). The header still fits one row
  from 1280 px (control 44 px; tab padding 6 px there; 10 px to spare) and two rows down to 350 px.
- **Charts:** ONE light -> dark map, `design_system.CHART_DARK` (alpha variants keep their alpha; it inverts exactly
  for the way back). `THEME_JS` wraps `Plotly.newPlot` (a dark page never paints a light chart) and re-applies the map
  after any restyle / relayout (the portfolio currency switch, the backtest range buttons, the mobile tuner) and on a
  theme change: paper / plot ground, fonts, grid / zero / spike lines, legend, hover labels, annotations, shapes,
  colour bars, every trace colour and inline `color:` in hover / text strings. Never style a chart for dark by hand:
  add the light colour to CHART_DARK (theme_gate T5 fails a trace colour that is unmapped and below 3:1 on the dark
  card, and two trace colours that share a chart and are >= 15 CIEDE2000 apart in light but not in dark: the
  secondary series and the benchmark must not merge with the book's blue).
- **Hero images** are dark in both themes and theme-invariant (their rules keep literals; the browser check compares
  every hero element's computed colours between the themes).
- **Rules:** never hard-code a colour a theme cannot reach: a literal in page CSS must be in the `design_system`
  `_FG` / `_BG` / `_BD` / `_SH` tables (which give it a token) or in a theme-invariant context (image hero, print);
  a script never sets a literal colour, nor writes one into an HTML fragment (use `var(--token, literal)`); a colour
  a generator can emit only on some days (25's sector chips) is mapped too (theme_gate reads its palette); a new token needs a dark value with text
  >= 4.5:1 and graphics >= 3:1 on the dark ground / card / chip. Gates: `tools/theme_gate.py` (T1-T7, also ds_gate
  R9 in the refresh) and the real-browser half `tools/theme_browser_check.js` (computed contrast of every text node
  and every chart at 1440 / 375 in both themes, hero invariance, palette left over from the other theme).
- **Light theme: unchanged.** Its pre-existing contrast gaps (legacy greys `#888` / `#9ca3af` on white, white text
  on the red / cyan sector chips, the recessive benchmark grey `#9aa5b1` and the muted bars `#b6bec8` in charts) are
  measured and listed in the wave notes; changing them is Carlos's call.

| token | light | dark | dark text contrast |
|---|---|---|---|
| `--bg` | `#F6F5F1` | `#101317` |  |
| `--panel` | `#FFFFFF` | `#171B21` |  |
| `--ink` | `#0E1726` | `#E9E7E2` | 12.46:1 (worst of ground / card / chip) |
| `--sec` | `#4A5568` | `#B9BFC8` | 8.32:1 (worst of ground / card / chip) |
| `--muted` | `#667085` | `#959CA8` | 5.57:1 (worst of ground / card / chip) |
| `--line` | `#E3E1DA` | `#2B3139` |  |
| `--line-strong` | `#C9C6BC` | `#3D444E` |  |
| `--chip` | `#EFEDE6` | `#20252D` |  |
| `--accent` | `#0A2540` | `#9CBDEB` | 7.99:1 (worst of ground / card / chip) |
| `--accent-tint` | `rgba(10,37,64,.05)` | `rgba(156,189,235,.08)` |  |
| `--accent-line` | `rgba(10,37,64,.28)` | `rgba(156,189,235,.38)` |  |
| `--amber` | `#B45309` | `#F0A65A` | 7.56:1 (worst of ground / card / chip) |
| `--up` | `#0F5E9C` | `#74B6EE` | 7.09:1 (worst of ground / card / chip) |
| `--down` | `#C2410C` | `#F4925F` | 6.69:1 (worst of ground / card / chip) |
| `--pos` | `#0a5d3a` | `#5CC68F` | 7.28:1 (worst of ground / card / chip) |
| `--neg` | `#7c2d12` | `#F39673` | 6.91:1 (worst of ground / card / chip) |
| `--st-green` | `#0a5d3a` | `#5CC68F` | 7.28:1 (worst of ground / card / chip) |
| `--st-blue` | `#1e3a8a` | `#93AEF5` | 7.05:1 (worst of ground / card / chip) |
| `--st-purple` | `#5b21b6` | `#B79CF5` | 6.66:1 (worst of ground / card / chip) |
| `--st-gray` | `#6b7280` | `#9AA1AD` | 5.92:1 (worst of ground / card / chip) |
| `--lift` | `0 8px 22px rgba(14,23,38,.08)` | `0 8px 22px rgba(0,0,0,.45)` |  |

Tokens only the themed rewrite references (undefined in light, so the literal fallback applies; light -> dark):
`--on-accent` #fff -> #0C1420, `--accent-hover` #0d3055 -> #B6CFF2, `--selection` rgba(180,83,9,.16) -> rgba(240,166,90,.30), `--neutral` #9AA5B4 -> #6E7886, `--teal` #0f766e -> #45BBAD, `--bench` #9aa5b1 -> #8B96A4, `--slate` #5b7c99 -> #94ABC2, `--warn` #8a5a00 -> #E0B05A, `--c-violet` #8a3ffc -> #B58CFF, `--c-red` #fa4d56 -> #E25083, `--c-cyan` #009d9a -> #2EC4C0, `--l-ink` #111 -> #E9E7E2, `--l-ink2` #333 -> #D7D9DD, `--l-ink25` #393939 -> #D2D4D8, `--l-ink3` #444 -> #C9CCD2, `--l-sec` #555 -> #B9BFC8, `--l-sec6` #666 -> #AEB4BE, `--l-muted` #888 -> #9EA5B0, `--l-muted2` #9ca3af -> #8F96A1, `--l-faint` #c4c9cf -> #8A929D, `--l-line` #e5e5e5 -> #2B3139, `--l-line2` #d4d4d4 -> #3D444E, `--l-line3` #eee -> #262B33, `--l-line4` #f0f0f0 -> #262B33, `--l-line5` #d8d5cf -> #3D444E, `--l-tot` #fbfaf8 -> #1C2027, `--l-row` #fbfbfb -> #1C2027, `--l-dim` #fcfcfc -> #191D23, `--l-grp` #f4f4f2 -> #1F242B, `--l-chip` #f4f4f4 -> #222730, `--l-code` #f0f0f0 -> #222730, `--l-track` #eef0f2 -> #262B33, `--l-track2` #c7d3df -> #46505C, `--l-prelim` #f5f8fb -> #18212B, `--l-tint45` rgba(10,37,64,.045) -> rgba(156,189,235,.07), `--l-tint35` rgba(10,37,64,.035) -> rgba(156,189,235,.06), `--l-tint07` rgba(10,37,64,.07) -> rgba(156,189,235,.12), `--l-tint-k` rgba(0,0,0,.05) -> rgba(255,255,255,.07), `--l-accent-line20` rgba(10,37,64,.2) -> rgba(156,189,235,.32), `--l-pos-line` rgba(10,93,58,.35) -> rgba(92,198,143,.45), `--l-neg-line` rgba(124,45,18,.45) -> rgba(243,150,115,.5), `--l-warn-line` rgba(138,90,0,.4) -> rgba(224,176,90,.5), `--l-blue-line` rgba(30,58,138,.35) -> rgba(147,174,245,.45), `--l-purple-line` rgba(91,33,182,.35) -> rgba(183,156,245,.45), `--l-sh08` rgba(14,23,38,.08) -> rgba(0,0,0,.45), `--l-sh16` rgba(14,23,38,.16) -> rgba(0,0,0,.55).

Chart palette map (`CHART_DARK`, light -> dark): `#ffffff` -> `#171B21`, `#111111` -> `#E9E7E2`, `#2a3f5f` -> `#D9DEE6`, `#0a2540` -> `#8DB4EC`, `#5b7c99` -> `#3D70D6`, `#0f766e` -> `#3CB7A8`, `#9aa5b1` -> `#808389`, `#b6bec8` -> `#6F7A8A`, `#e5e5e5` -> `#2B3139`, `#d4d4d4` -> `#3D444E`, `#ebf0f8` -> `#343B45`, `#c9c9c9` -> `#59616D`, `#888888` -> `#A3A3A3`, `#666666` -> `#AEB4BE`, `#555555` -> `#B9BFC8`, `#6b7280` -> `#8C93A0`, `#0a5d3a` -> `#55C08A`, `#7c2d12` -> `#F08A62`, `#f1f1f1` -> `#22272F`, `#f4f4f2` -> `#2A2F37`, `#7fb3ad` -> `#2F6F68`, `#7e97b3` -> `#4E6688`, `#8a3ffc` -> `#B58CFF`, `#009d9a` -> `#2EC4C0`, `#fa4d56` -> `#E25083`, `#0f5e9c` -> `#74B6EE`, `#c2410c` -> `#F4925F`, `#b45309` -> `#F0A65A`, `rgba(255,255,255,.97)` -> `rgba(31,36,44,.97)`, `rgba(15,98,254,0.13)` -> `rgba(120,170,255,0.16)`, `rgba(10,37,64,0.07)` -> `rgba(141,180,236,0.10)`, `rgba(10,37,64,0.12)` -> `rgba(141,180,236,0.16)`, `rgba(154,165,177,0.20)` -> `rgba(128,131,137,0.24)`, `rgba(154,165,177,0.12)` -> `rgba(128,131,137,0.15)`, `rgba(15,118,110,0.08)` -> `rgba(60,183,168,0.11)`.
