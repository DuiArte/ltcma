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
underneath; removing the appended layer restores the previous look on every page at once. Light theme only (dark
mode deferred: not provably safe for every Plotly chart).

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
  the home's performance panel shows from 641 px up, since the Hold card restates it right below).
- **Photo:** the About section shows Carlos's portrait (EXIF-free copies only; never the original in Pictures).
- **Charts:** unchanged in this wave (palette, heights, hovers, guards).
