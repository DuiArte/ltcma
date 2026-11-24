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
- **Image heroes: one photograph per page** (wave r3, Carlos 2026-11-10 "Dale play a todo": supersedes the remake's
  five-page list). The table is `design_system.PAGE_HEROES`; generators call `hero_for(page, ...)` /
  `credits_for(page)`: Dashboard = Cosmic Cliffs, Portfolio = ZS7 field, Market Intel = Herbig-Haro 46/47, Congress =
  NGC 6822, Research Library = Pillars of Creation, Stock Research + every stock page = NGC 6440 (one shared
  photograph), Regime Tracker = NASA "Space Station View of Earth at Night". Reading pages (report, research notes,
  strategies, projects, glossary, backtests) stay plain. No two pages share a photograph (the stock pages share Stock
  Research's); a page with an entry must show its own (ds_gate R3). Retired: `cliffs_detail`, `pillars_base`
  (`RETIRED_HERO_KEYS`; their files are gone from assets/ and docs/). Under a 64% dark layer (a little deeper under
  the text column, 72% on phones; small text over a hero sits on its own dark backdrop: worst-pixel contrast
  >= 4.5:1, measured by hero_contrast on the real page, both themes), never behind a chart.
- **Credits:** in the hero AND the footer, the same line: title (linked to the source page), "cropped", the source
  page's credit **verbatim** (`assets/credits.json` `credit`), the licence (CC BY 4.0 linked to the licence; NASA
  media: "public domain (NASA media)", no licence link, the credit still shown). Sources only on esawebb.org or
  nasa.gov (ds_gate R3 reads every field from credits.json). No NASA insignia in a crop.
- **Files:** `assets/img/` (committed, no EXIF / XMP / ICC / comment) emitted byte-identically into
  `docs/assets/img/` by each generator that shows one. Per key in credits.json: the 16:9 and 9:16 crop boxes in the
  original's pixels and the published widths -- never wider than the cut (no upscaling: NGC 6440 has no 3840),
  fewer widths where a dense star field cannot meet the budget (NGC 6822: WebP 1600 / 2560, JPEG 960 / 1600, phone
  720). No image > 1.2 MB; phones get a 9:16 WebP of its own crop (720 / 1080 px, <= 250 KB), larger screens the 16:9
  WebP 1600 / 2560 / 2880 / 3840 where published (tablets ask for 150vw: a 16:9 image covering a taller box is drawn
  wider than the screen). On phones the heroes stay about one screen tall (stats 2 x 2, CTAs side by side;
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
  a two-state toggle -- every press shows the other look (light <-> dark); landing on the device's own look means Auto
  again (follow the device; there is no Auto -> Dark -> Light cycle),
  so no press is ever invisible (review round 1). `aria-label` names the current mode and the next one, a polite
  status line announces the change; theme.css sets `--thm-ok` and the script keeps charts light if it did not load; hidden without JS (the media query then follows the system). The header still fits one row
  from 1280 px (control 44 px; tab padding 6 px there; 10 px to spare); below that, two rows (brand + corner + control,
  then the tabs) down to 320 px -- below 360 px the corner shows its book icon and caret only (polish round 2026-11-11).
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


## 2026-11-10 wave r3 (Carlos, written ~15:00: "Dale play a todo")

- **The head of every page is `design_system.site_head()`**, run by `themed()` for every generator (and applied by the
  r3 deploy to the committed copies): title `<Name> · Carlos Duarte` (the home: `Capital Market Assumptions · Carlos
  Duarte`; stock pages `<TICKER> · Stock Research · Carlos Duarte`; backtests `<strategy> · Backtest report · Carlos
  Duarte`), a description of 50-160 characters with no figure and nothing that reads as advice (a page's own
  description wins), canonical + Open Graph + Twitter card, the favicon set, a font preconnect. New page: add it to
  `design_system.PAGE_META` (ds_gate R10 fails a page without an entry). Pass the FILE name to `themed(html, "x.html")`.
- **Share cards** (`assets/img/og_<tab>.png`, 1200 x 630, drawn by `tools/make_share_assets.py`): typographic, warm ground,
  the CD mark, the page name, one line, the URL. No figure (preview caches keep it for weeks) and no photograph (a JWST
  crop in a link preview travels without its CC BY credit). The favicon is the header's CD mark (an SVG with a dark
  variant + 32 px and 180 px PNGs).
- **Plotly**: pages load the official **cartesian** bundle of the pinned version (`plotly-cartesian-2.35.0.min.js`,
  same CDN) whenever every trace on the page is cartesian (scatter, bar, heatmap, box, histogram*, contour, image, pie,
  scatterternary, violin); `site_head` picks it from the page's own figures, so a chart of another type brings the full
  bundle back by itself. R10 fails a cartesian page with another trace type.
- **Money in the Congress tables** (`design_system.money`): `−$2.4M` (a real minus sign before the dollar sign),
  `<$1K` under $500, `$0` for none; dollar totals that add range midpoints say so (`≈` in the header + a note).
- **Rate moves** on the home's market tiles are in **basis points** (`▲ +2 bp`); levels stay in %.
- **One Fed-odds vintage per page**: the home and Market Intel draw every Fed figure from
  `design_system.fed_path_newest()` (the newer of the 16:45 daily pull and the consensus run's own pull); Market
  Intel's "Next FOMC decision" card and Summary never restate an older pull's odds.
- **Print**: the footer prints (the disclaimer and the image credit); the hero image and its credit line do not.
- **Sticky table heads**: a tile clips with `overflow:clip`, so a table sitting directly in a tile keeps its head
  under the site header (desktop / tablet); a table that scrolls sideways keeps its head on its own top.
- **docs/404.html, sitemap.xml, robots.txt** are written by 17 (`design_system.emit_share`) on every build.

## 2026-11-10 wave r3, builder B: photographs, the "On this page" bar, note()

- **One photograph per page**: see "Image heroes" above (`PAGE_HEROES`, `hero_for`, credits from credits.json, R3).
  A committed page a generator keeps (19 / 25 on a Yahoo block, 20 on a FRED block) gets its photograph from the r3
  deploy (`design_system.hero_retrofit`: the committed hero text kept byte for byte, exactly what `hero_for` writes).
- **The sticky "On this page" bar** (`design_system.PAGE_SECTIONS`, `otp_insert`, run by `themed()` on every page like
  the share head): on the long pages -- Portfolio, Stock Research, Congress, Strategies and the archived Full Report --
  a thin bar right under the header lists the page's sections with short labels (only ids the page carries; never a
  renamed anchor: 18 / 23 gained ids where a section had none). The current section is underlined
  (`aria-current="location"`); on phones the links scroll sideways with the tabs' edge fade and a focused link is
  kept in view; without JS it is a plain sticky row of links; on a landscape phone it scrolls with the page. Anchors
  and sticky table heads clear it (`--otph`). **Portfolio: one strip** -- r2's MXN | USD switch sits at the bar's right
  end (18 still writes r2's `.ccy-bar`; `otp_insert` moves its switch into the bar). Congress' old jump row is the bar.
  ds_gate R11 checks one bar per long page, right before `<main>`, every link resolving once, the table's order, the
  portfolio switch inside it.
- **note()** (`design_system.note`): the explanatory notes in two roles. *Disclosure*: always visible, at most two
  sentences, a thin amber rule (`--amber`). *Method*: a native `<details>` closed by default, its `<summary>` naming
  what is inside (works without JavaScript; find-in-page opens it; it does not print open). Used for the portfolio's
  top, the Stock Research Composite Picks and Pick Tracker intros, the Congress coverage box (its summary keeps the
  chambers covered visible).
- **Portfolio leads with its numbers**: hero, the bar, Performance heading + stamp, the scaling disclosure (visible,
  above the first money figure, wording unchanged, no factor), the tiles, then one closed "How these figures are
  built" note holding the currency-switch help, the source / accounting text and the two-measures paragraph, word for
  word (R11 checks the disclosure: visible, above the tiles, no number).

## 2026-11-10 wave r3, builder C: tables that fit (Congress by filing, the Pick Tracker, phone cards)

- **Congress trades, grouped by filing** (30 `render_congress`, `congress_filings`, `CONG_JS`): one `<tbody>` per filing,
  newest first; its header row names the member, the chamber, the filing date and the filing's link once, and sums its
  trades up (how many, the sides, the tickers, the largest disclosed band, so a large trade cannot hide inside a
  group); the filing's trades follow with their own facts. The page holds every filing that has a trade among the
  newest `CG_MAXROWS` (400) trades, WHOLE (a filing is never cut in two). With JavaScript the filings start collapsed
  to their header rows, 50 filings and 50 trades of a filing at a time ("Show 50 more"), and a filter (ticker or asset
  text, member, chamber, side; an `aria-live` count line) opens the filings that match. **Without JavaScript every
  filing and every trade shows** and the filter bar / buttons are hidden (`.jsonly`); no row carries `hidden` in the
  HTML; print shows every trade. A ticker with a CFA report links to its `stock_X.html`. The weekly / daily congress
  job renders the page with the same script, so its page is the refresh's page. ds_gate R12 re-derives the filings from
  `data/market_intel/congress_public.json`.
- **Pick Tracker fits 1440 px** (`picks_tracker.tracker_fit`, run by 25 on its own section; the staged preview runs the
  same function on the committed page): no cell's text changes; a cell's lines wrap only after a `&middot;` / ` / `
  separator, before `(` and between plain words (other spaces are no-break; a piece with a minus sign or an en dash
  stays on one line), so the 11 columns fit the 1,150 px tile; from 641 px up the `+` and ticker columns stay in view
  when the table still scrolls sideways (641-1,180 px). Column priority `data-pri` (`TRACK_PRI`: 1 the list's own
  figures, 2 entry date / target / earnings, 3 the analyst / insider / congress context) orders a phone card.
- **Rank sparkline** (`picks_tracker.rank_sparks`): each name's rank at every daily ranking of the page's own history
  (`data/picks_history.csv`, ranks only; partial rankings are gaps), rank 1 at the top, the band lines (15, 25) dashed,
  a dot on the latest ranking; 60 x 20 px inline SVG before today's rank, colours through tokens (`--accent`,
  `--line-strong`), an `aria-label` + hover text with the first / latest / best / worst rank. No `<title>` element in
  it (a page has one `<title>`, R10).
- **Phone cards** (`design_system.card_tables`, run by 25 on stocks.html before `themed()`): every `table.ptable` in a
  scrolling tile becomes, below 641 px, a column of cards -- the same markup (each body cell carries its column header
  as `data-label`, style.css draws it), no second copy of the data; the first cell (with the ticker on the picks and
  tracker tables) is the card's head, the other cells two to a row, long text (chips, commentary) full width. Desktop
  is unchanged. A table added to stocks.html in a tile gets cards by itself; R12 checks every label against its header.

## 2026-11-11 wave r3, fix round 1 (the reviews of r3; nothing new to look at, things that were wrong)

- **Research corner on phones**: below 641 px and on landscape phones the menu hangs from the header row, 16 px in from
  its sides, right under the corner button (`top:auto` + 8 px, its place in the flow; never a fixed offset: without
  JavaScript the button can sit on a second header row) -- never from the button's own right edge (the theme control
  sits right of it). With the control shown, theme.css does it (`design_system._THEME_CONTROL_CSS`, r2's two
  `[data-theme-pref]` rules); landscape phones without JavaScript get the same menu from style.css; portrait phones
  without JavaScript keep the corner-anchored menu, which fits there. `ds_gate` R12 checks the rules in style.css and
  theme.css and fails a `.rc-menu` rule with a fixed `top` in px.
- **Congress filing header**: as wide as its scroller's visible width (`.mi-wrap.cgw` is a size container; the header's
  `max-width:calc(100cqi - 20px)`, `94vw - 52px` where container units are missing); a filing date and a dollar band
  sit in `<span class="nw">` (never broken at the hyphen); the party-district label is `--sec` on the header's chip
  ground (>= 4.5:1). "Show 50 more" moves the focus to the first row (or filing) it reveals.
- **Pick Tracker line breaks**: a signed figure that ends its piece stays with its slash (`+54 / -2`); the line may
  break before the pair instead (`targets` | `+54 / -2`).
- **Licence names** (`a[rel~="license"]`) never break across lines.
- **Sticky table heads**: a table directly in a `.tile` (clip, not a scroll container) sticks below the header + bar; a
  table in a tile that scrolls sideways (inline `overflow-x:auto`) cannot stick to the viewport (CSS Overflow 3) and
  scrolls with its table -- such a tile is a scroll container in both axes (`overflow-y:hidden`), so no browser sticks
  its head under the header.
- **The r3 head script** (`design_system.SITE_JS`, inside the share block on every page): a cold `#link` is aligned under
  the sticky header / bar once the page has loaded and settled (smooth anchor scrolling, `html.sm`, starts only then);
  the first Tab stop is a "Skip to content" link (off-screen until focused) that moves the focus to `<main>`.
- **og:image:alt** says what the card shows (`design_system.OG_CARD_TEXT`, the text `tools/make_share_assets.py` draws).
- **One Fed vintage, the whole page**: when the Fed path's pull is newer than the consensus run, EVERY piece of the
  run's prose on Market Intel (Summary, divergences) goes through `_fomc_fix`: a clause quoting the run's next-FOMC odds
  points at the Fed path; any other next-FOMC percentage is dated with the run's own pull ("(prices of 10 Nov 2026
  07:17)"); two pulls of the same day are told apart by their time. R10 fails an undated next-FOMC percentage in that
  state (`fed_vintage_problems`; the dated snapshot cards and event outlook are left out).
- **Sitemap**: 31 (the refresh's last page generator) writes `docs/sitemap.xml` once more (`design_system.emit_sitemap`,
  only when it changes), so a page added after 17 is listed the same day.
- **Layout gate, browser half** (`tools/layout_browser_check.js`; the static half is R12's CSS check): serve `docs/` on
  127.0.0.1 under `/ltcma/`, open any page, load the script (`var s=document.createElement('script');
  s.src='<url>';document.head.appendChild(s)`), then `await window.ltcmaLayoutCheck({pages:[...], widths:[1440,375]})`:
  every `table.ptable` head sits on its table at rest and, scrolled, sticks right below the header + bar (or, only in a
  sideways scroller, leaves with its table); no headline figure or numeric cell is clipped or off-screen (unless a
  sideways scroller holds it); no `@media print` rule hides the footer. `report.fails` must be 0, in both themes.

## 2026-11-11 wave r3, decisions pass (Carlos's written answers of 11 Nov)

- **Composite Picks on phones open on "Picks (★)"** (25 `FILTER_JS`): when the page loads on a viewport of at most
  640.98 px (the card layout), the Picks pill is selected and the 20 picks show as cards; desktop opens on "All (40)" as
  before. The HTML keeps "All" as the selected pill, so without JavaScript every row shows, the picks starred.
- **Kept as built**: the 3840 px WebP photographs (repo weight accepted); Congress filings start collapsed (with
  JavaScript; without it every filing and trade shows).

## 2026-11-11 wave r3, polish round (the r2 live verification's lows + the decisions-pass recheck's)

- **One header row with the theme control down to 320 px** (style.css, `[data-theme-pref]`, below 360 px): the Research
  corner shows its book icon and caret only (the word is hidden with font-size 0; the button's `aria-label` keeps its
  name), so brand + corner + control never wrap; the open menu hangs under the row and never covers the control.
  Without JavaScript (no control) the header is unchanged. `ds_gate` R12 checks the rule.
- **Charts redraw once the web fonts are in** (`design_system.SITE_JS`): Plotly caches every text width by its text +
  style, so a chart drawn before Inter arrived kept the fallback font's widths (legend text clipped, legend items
  touching). After `document.fonts.ready` every chart is relaid out with `font.weight` 400 (= normal: same look, new
  cache key), once more (399, the same regular face) only if a face finished loading within 1.5 s. A generator never
  sets `layout.font.weight` (a chart that does keeps its own). R10 checks the script is in every share block.
- **Chart notes stay clear of the axis labels**: a note anchored at the plot's left edge is shifted in by pixels
  (`xshift`: "in cash, by choice", 10 px, on the entries chart and on the decisions chart, where it is the cash band's
  vrect annotation, `annotation_xshift`), never left touching a tick label. R12 checks every such note.
- **Filter pills say which one is on**: a pill group that filters rows carries `aria-pressed` (the selected pill
  `true`, the others `false`) in the markup, and its script keeps it in sync with the `on` class (25 `FILTER_JS`, the
  phone default included). R12 checks the Composite Picks pills.
- **Stock pages, CFA View**: below a 30% payout the justified P/E is "n/m"; a 0% payout says "n/m (no dividend)", any
  other "n/m (payout X% < 30%)"; at 30% or more the trailing P/E is compared with it (19 `verdict_html`). R12 fails a
  clause that does not match the page's payout.

## 2026-11-17 wave r3s: the retail broker and its trading platform in general words (Carlos, 2026-11-17)

- **The retail broker and its trading platform in general words.** Some backtests and the archived report used
  intraday FX / CFD prices from a retail broker, exported from a retail trading platform. Pages say exactly that,
  in those words: "retail-broker M5 data", "the retail-broker CSVs", "a retail trading platform",
  "broker-data window".
- **Neutral, never false.** Do not name another vendor in its place. Do not suggest exchange data. Keep every
  attribution a source's licence asks for.
- **Where it happens.** Text the site writes itself is neutral in the source (the home's skills list). Text it
  publishes from elsewhere (the strategy catalogue, the backtest REPORT.md files, the hand-written report) goes
  through `scripts/vendor_names.py` `scrub()` at render time. A new phrasing that reads badly gets a phrase rule
  there, with a test line in the private term list.
- **Gate.** ds_gate R2, the load-bearing `guard_vendor_names.py` and confscan read every public file under `docs/`
  and `data/` (what git publishes). A PDF there fails (it cannot be read); an image's metadata is read, text
  drawn inside a picture is checked by eye. A name joined to other letters or digits fails too, and so does a long
  name in any spelling but the brand's own (spaced, dashed, other capitals: such words may be ordinary words, and
  a rewrite could be untrue), and so do the platform's short name outside the skills list and the server names,
  its scripting language in any form but its own capitals with a version in one piece (no version, a plural, a
  separator, other capitals) and a file kind with its dot anywhere but right after a file name in the list's
  spelling (alone, or in other capitals); the short name and the language are also ordinary acronyms elsewhere.
  The scrub rewrites none of these, so the text or a phrase rule needs a fix.
  `data/fx_monthly.csv`'s header line is KNOWN while that file is public (Carlos to decide; `vendor_names.KNOWN`);
  the same words anywhere else fail.
- **The term list is private.** It lives outside every repo (`Documents\LTCMA_private\vendor_terms.txt`), with
  the self-test's cases. `scripts/vendor_names.py` holds only the scrub and the scan and spells no term (its
  self-test checks its own source). A finding names the kind of term and the line, never the spelling: keep it
  that way in logs, commit messages and notes. Without the list the gate and the generators stop (fail closed;
  in the refresh, 17_build_site.py stops first).
