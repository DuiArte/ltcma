# Website Style Guide — Carlos Duarte · Quantitative Research

Institutional editorial identity. Reference: FT research / Bridgewater Daily
Observations. **Restraint is the design constraint — when in doubt, remove decoration.**

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

## Apply / verify
- Regen via WSL `daily_refresh.sh` (hub `~/LTCMA`). On native Windows, edit the
  CSS var in `17_build_site.py` and re-run renderers, or transform `docs/*.html`.
- Verify computed styles with a static server + DOM inspect (screenshots block on
  the slow Fonts CDN `load` event; inspect/eval are reliable).
