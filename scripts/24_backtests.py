#!/usr/bin/env python3
"""Build docs/backtests.html (+ per-strategy report pages) from the canonical
strategy catalog at Trading_Index/strategies.json.

Data source order: the Trading_Index hub on the Windows side (authoritative,
where Carlos edits) -> a committed repo fallback (data/backtests_strategies.json)
so a clean clone / CI can still build. When the hub is reachable we refresh the
repo fallback from it, keeping the two in sync.

Styling: reuses the site shell (style.css + the shared NAV); the few card/badge
rules are inlined here because 17_build_site.py owns (overwrites) style.css.

Run from the scripts/ dir (the daily refresh does `cd scripts && python3 ...`).
Failures are non-fatal to the pipeline: the daily refresh guards this with `|| echo`.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
FALLBACK = os.path.join(REPO, "data", "backtests_strategies.json")
HUB_CANDIDATES = [
    "/mnt/c/Users/carlo/Trading_Index/strategies.json",
    r"C:\Users\carlo\Trading_Index\strategies.json",
]

sys.path.insert(0, HERE)
from glossary import NAV  # noqa: E402

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Sans:wght@300;400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">')

BADGE = {  # badge key -> (label fallback, accent colour)
    "green":  ("Deployable",        "#198038"),
    "yellow": ("Ensemble component", "#b28600"),
    "red":    ("Pass / no edge",     "#da1e28"),
}

PAGE_CSS = """
.bt-intro{color:#525252;font-size:14px;max-width:880px;margin:-6px 0 28px;line-height:1.6}
.btgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:18px}
.btcard{background:#fff;border:1px solid #e0e0e0;border-top:4px solid #c6c6c6;
padding:24px 24px 20px;box-shadow:0 1px 4px rgba(22,22,22,.06);display:flex;flex-direction:column;
transition:box-shadow .18s}
.btcard:hover{box-shadow:0 4px 16px rgba(22,22,22,.12)}
.btcard.bt-green{border-top-color:#198038}
.btcard.bt-yellow{border-top-color:#b28600}
.btcard.bt-red{border-top-color:#da1e28}
.bt-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
.bt-badge{font-size:11px;font-weight:600;letter-spacing:.4px;text-transform:uppercase;
color:#fff;padding:5px 11px;border-radius:2px}
.bt-badge.bt-green{background:#198038}
.bt-badge.bt-yellow{background:#b28600}
.bt-badge.bt-red{background:#da1e28}
.bt-date{font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:#8d8d8d}
.bt-name{font-size:19px;font-weight:600;color:#161616;margin:0 0 6px;line-height:1.25}
.bt-tests{font-size:13px;color:#525252;line-height:1.5;margin:0 0 16px}
.bt-metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:#e0e0e0;
border:1px solid #e0e0e0;margin-bottom:16px}
.bt-m{background:#fafafa;padding:11px 8px;text-align:center}
.bt-mv{font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:500;color:#0f62fe;letter-spacing:-.3px}
.bt-mv.neg{color:#da1e28}.bt-mv.na{color:#8d8d8d}
.bt-mk{font-size:9.5px;color:#525252;margin-top:4px;letter-spacing:.2px;text-transform:uppercase}
.bt-verdict{font-size:13.5px;color:#262626;line-height:1.55;margin:0 0 18px;flex:1}
.bt-foot{display:flex;justify-content:space-between;align-items:center;gap:10px;
border-top:1px solid #e0e0e0;padding-top:14px}
.bt-span{font-family:'IBM Plex Mono',monospace;font-size:11px;color:#8d8d8d}
.bt-link{color:#0f62fe;text-decoration:none;font-size:13px;font-weight:600;white-space:nowrap}
.bt-link:hover{text-decoration:underline}
.bt-method{background:#fff;border:1px solid #e0e0e0;border-left:4px solid #0f62fe;
padding:22px 26px;margin-top:8px}
.bt-method h3{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.3px;color:#161616;margin:0 0 12px}
.bt-method ol{margin:0 0 0 18px;padding:0}
.bt-method li{font-size:13px;color:#393939;margin:5px 0;line-height:1.5}
.bt-method p{font-size:12.5px;color:#525252;margin:12px 0 0;line-height:1.55}
.report .bt-back{display:inline-block;margin-bottom:14px;color:#0f62fe;text-decoration:none;font-size:13px;font-weight:600}
@media(max-width:560px){.bt-metrics{grid-template-columns:repeat(3,1fr)}}
"""


def win_to_wsl(p):
    """C:\\Users\\carlo\\x -> /mnt/c/Users/carlo/x ; pass posix paths through."""
    if not p:
        return p
    if len(p) > 2 and p[1] == ":" and (p[2] == "\\" or p[2] == "/"):
        return "/mnt/" + p[0].lower() + "/" + p[3:].replace("\\", "/")
    return p.replace("\\", "/")


def load_catalog():
    for hub in HUB_CANDIDATES:
        wp = win_to_wsl(hub)
        if os.path.exists(wp):
            with open(wp, encoding="utf-8") as fh:
                data = json.load(fh)
            try:  # refresh the committed fallback so a clean clone can rebuild
                os.makedirs(os.path.dirname(FALLBACK), exist_ok=True)
                with open(FALLBACK, "w", encoding="utf-8") as out:
                    json.dump(data, out, indent=2, ensure_ascii=False)
            except OSError:
                pass
            return data, hub
    if os.path.exists(FALLBACK):
        with open(FALLBACK, encoding="utf-8") as fh:
            return json.load(fh), FALLBACK
    raise SystemExit("24_backtests: no strategies.json found (hub or fallback)")


def fmt(key, val):
    """Render a key_metrics value into (text, css-class)."""
    if val is None:
        return "n/a", "na"
    if isinstance(val, str):
        return val, ("na" if val.strip().lower() in ("n/a", "na", "") else "")
    pct = key in ("max_dd_pct", "cagr_pct", "held_out_sharpe")
    neg = isinstance(val, (int, float)) and val < 0
    if key in ("max_dd_pct", "cagr_pct"):
        return f"{val:+.1f}%", ("neg" if neg else "")
    return f"{val:.2f}", ("neg" if neg else "")


METRIC_ROW = [
    ("best_raw_sharpe", "Raw Sharpe"),
    ("dsr", "DSR"),
    ("pbo", "PBO"),
    ("max_dd_pct", "Max DD"),
    ("cagr_pct", "CAGR"),
]


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def shell(title, body, plot=False):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
{FONTS}
<link rel="stylesheet" href="style.css"></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;/&nbsp;<b>LTCMA&nbsp;2026</b></span>{NAV}
</div></header>
{body}
<footer class="shell-foot"><div class="container"><p>Backtests run under a fixed
validation protocol on pessimistic retail costs. Verdicts are research findings,
not investment advice; past results do not guarantee future outcomes.</p></div></footer>
</body></html>"""


def render_report_page(strat):
    """Convert a strategy's REPORT.md to docs/bt_<key>.html. Returns the
    filename if written, else None."""
    md_path = win_to_wsl((strat.get("paths") or {}).get("report_md"))
    out_name = strat.get("report_html") or f"bt_{strat['key']}.html"
    if not md_path or not os.path.exists(md_path):
        return None
    try:
        import markdown
        html = markdown.markdown(
            open(md_path, encoding="utf-8").read(),
            extensions=["tables", "fenced_code", "sane_lists"])
    except Exception:
        raw = open(md_path, encoding="utf-8").read()
        html = "<pre>" + esc(raw) + "</pre>"
    body = (f'<main class="container"><article class="tile report">'
            f'<a class="bt-back" href="backtests.html">&larr; All backtests</a>'
            f'{html}</article></main>')
    out = shell(f"{esc(strat['name'])} — Backtest Report", body)
    with open(os.path.join(DOCS, out_name), "w", encoding="utf-8") as fh:
        fh.write(out)
    return out_name


def card(strat, report_link):
    badge = strat.get("badge", "red")
    label = strat.get("verdict") or BADGE.get(badge, ("", ""))[0]
    km = strat.get("key_metrics", {})
    tiles = ""
    for k, lbl in METRIC_ROW:
        txt, cls = fmt(k, km.get(k))
        tiles += (f'<div class="bt-m"><div class="bt-mv {cls}">{esc(txt)}</div>'
                  f'<div class="bt-mk">{lbl}</div></div>')
    dates = strat.get("dates", {})
    run = dates.get("run", "")
    span = dates.get("data_span", "")
    if report_link:
        link = f'<a class="bt-link" href="{report_link}">Full report &rarr;</a>'
    else:
        link = '<span class="bt-span">report on local disk</span>'
    return (
        f'<article class="btcard bt-{badge}">'
        f'<div class="bt-head"><span class="bt-badge bt-{badge}">{esc(label)}</span>'
        f'<span class="bt-date">{esc(run)}</span></div>'
        f'<h3 class="bt-name">{esc(strat["name"])}</h3>'
        f'<p class="bt-tests">{esc(strat.get("what_it_tests",""))}</p>'
        f'<div class="bt-metrics">{tiles}</div>'
        f'<p class="bt-verdict">{esc(strat.get("verdict_line",""))}</p>'
        f'<div class="bt-foot"><span class="bt-span">{esc(span)}</span>{link}</div>'
        f'</article>')


def main():
    data, src = load_catalog()
    strats = data.get("strategies", [])
    asof = data.get("updated", "")

    cards = ""
    for s in strats:
        link = render_report_page(s)
        cards += card(s, link)

    method = (
        '<section class="block"><h2>Methodology</h2>'
        '<div class="bt-method"><h3>The standing validation protocol</h3>'
        '<ol>'
        '<li><b>Optuna smart-search</b> &mdash; ~5k&ndash;20k informed evals; structural priors fixed, not searched.</li>'
        '<li><b>Walk-forward + purged cross-validation</b> with embargoed gaps (Bailey/L&oacute;pez de Prado).</li>'
        '<li><b>Deflated Sharpe Ratio (DSR)</b> reported alongside raw Sharpe (multiple-testing correction).</li>'
        '<li><b>Monte Carlo 100k&ndash;500k</b> &mdash; trade-sequence bootstrap, entry jitter, +50% spread &amp; slippage.</li>'
        '<li><b>Held-out test</b> on the most recent slice (post-2024), never touched during selection.</li>'
        '<li><b>PBO</b> (Probability of Backtest Overfitting, CSCV) alongside DSR.</li>'
        '<li><b>S&amp;P 500 gate</b> &mdash; must close-or-beat the index on at least one risk-adjusted axis.</li>'
        '<li><b>Survival bar</b> &mdash; maximum drawdown under 10%.</li>'
        '</ol>'
        '<p>Cost model is pessimistic retail (FxPro embedded per-bar spread as the floor, '
        'plus markup and stop slippage). Sizing is 1% fixed-fractional; under R-multiple '
        'accounting the Sharpe ratio is sizing-invariant. "n/a" means the metric was not '
        'computed in that report &mdash; it is never guessed.</p></div></section>')

    body = f"""<section class="hero"><div class="container">
<h1>Strategy Backtests</h1>
<p class="lede">Every completed strategy backtest, run under one fixed validation
protocol &mdash; smart-search, walk-forward, deflated Sharpe, Monte Carlo, a held-out
window and an S&amp;P 500 gate &mdash; with the honest verdict for each.</p>
<p class="asof">As of {esc(asof)} &middot; pessimistic retail costs &middot; 1% fixed-fractional sizing</p>
</div></section>
<main class="container">
<section class="block"><h2>Completed Backtests</h2>
<p class="bt-intro">Color shows the verdict: <b style="color:#198038">green</b> = deployable
(clears the &lt;10% drawdown survival bar and beats the S&amp;P), <b style="color:#b28600">amber</b>
= ensemble component (real edge, not standalone-worthy), <b style="color:#da1e28">red</b>
= pass / no edge (failed the cost-adjusted tests). Metrics and verdicts are pulled
verbatim from each backtest's report.</p>
<div class="btgrid">{cards}</div></section>
{method}
</main>"""

    page = shell("LTCMA 2026 — Strategy Backtests", body)
    # inject page-specific CSS right before </head>
    page = page.replace('<link rel="stylesheet" href="style.css"></head>',
                        f'<link rel="stylesheet" href="style.css">\n<style>{PAGE_CSS}</style></head>')
    with open(os.path.join(DOCS, "backtests.html"), "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"  backtests.html  ({len(strats)} strategies, source: {src})")


if __name__ == "__main__":
    main()
