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
import copy
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
from glossary import NAV, bt_card  # noqa: E402

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">')

BADGE = {  # badge key -> (label fallback, accent colour)
    "green":  ("Deployable",        "#0a5d3a"),
    "yellow": ("Ensemble component", "#6b7280"),
    "red":    ("Pass / no edge",     "#7c2d12"),
}

PAGE_CSS = r"""
.bt-intro{color:#555;font-size:14px;max-width:880px;margin:-6px 0 28px;line-height:1.6}
.btgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1.5rem}
.btcard{background:#fff;border:1px solid #e5e5e5;border-top:3px solid #d4d4d4;
padding:24px 24px 20px;box-shadow:none;display:flex;flex-direction:column;transition:background .15s ease-out}
.btcard:hover{background:rgba(10,37,64,.045)}
.btcard.bt-green{border-top-color:#0a5d3a}
.btcard.bt-yellow{border-top-color:#6b7280}
.btcard.bt-red{border-top-color:#7c2d12}
.bt-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
.bt-badge{font-size:10.5px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;
color:#fff;padding:4px 10px;border-radius:0}
.bt-badge.bt-green{background:#0a5d3a}
.bt-badge.bt-yellow{background:#6b7280}
.bt-badge.bt-red{background:#7c2d12}
.bt-date{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:11.5px;color:#888}
.bt-name{font-family:'Spectral',Georgia,serif;font-size:19px;font-weight:500;color:#111;margin:0 0 6px;line-height:1.25}
.bt-tests{font-size:13px;color:#555;line-height:1.5;margin:0 0 16px}
.bt-metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:0;background:none;
border:1px solid #e5e5e5;margin-bottom:16px}
.bt-m{background:#fff;padding:11px 8px;text-align:center;border-right:1px solid #e5e5e5}
.bt-m:last-child{border-right:0}
.bt-mv{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:16px;font-weight:500;color:#111;letter-spacing:-.01em}
.bt-mv.neg{color:#7c2d12}.bt-mv.na{color:#888}
.bt-mk{font-size:9.5px;color:#888;margin-top:4px;letter-spacing:.06em;text-transform:uppercase}
.bt-verdict{font-size:13.5px;color:#333;line-height:1.55;margin:0 0 18px;flex:1}
.bt-xref{font-size:12.5px;color:#0a2540;line-height:1.5;margin:0 0 14px;
border-left:2px solid rgba(10,37,64,.20);padding-left:12px}
.bt-xref a{color:#0a2540;font-weight:500}
.bt-foot{display:flex;justify-content:space-between;align-items:center;gap:10px;
border-top:1px solid #e5e5e5;padding-top:14px}
.bt-span{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:11px;color:#888}
.bt-link{color:#0a2540;text-decoration:none;font-size:13px;font-weight:500;white-space:nowrap}
.bt-link:hover{text-decoration:underline}
.bt-method{background:none;border:1px solid #e5e5e5;border-left:2px solid rgba(10,37,64,.20);
padding:22px 26px;margin-top:8px}
.bt-method h3{font-family:'Spectral',Georgia,serif;font-size:16px;font-weight:500;text-transform:none;letter-spacing:0;color:#111;margin:0 0 12px}
.bt-method ol{margin:0 0 0 18px;padding:0}
.bt-method li{font-size:13px;color:#555;margin:5px 0;line-height:1.5}
.bt-method p{font-size:12.5px;color:#888;margin:12px 0 0;line-height:1.55}
.report .bt-back{display:inline-block;margin-bottom:14px;color:#0a2540;text-decoration:none;font-size:13px;font-weight:500}
@media(max-width:560px){.bt-metrics{grid-template-columns:repeat(3,1fr)}.bt-m:nth-child(3n){border-right:0}}
"""


def win_to_wsl(p):
    """C:\\Users\\carlo\\x -> /mnt/c/Users/carlo/x ; pass posix paths through."""
    if not p:
        return p
    if len(p) > 2 and p[1] == ":" and (p[2] == "\\" or p[2] == "/"):
        return "/mnt/" + p[0].lower() + "/" + p[3:].replace("\\", "/")
    return p.replace("\\", "/")


def resolve_path(p):
    """First existing form of p, trying the raw path (native Windows) then the
    WSL-mapped form (/mnt/c under WSL). Returns None if neither exists.

    win_to_wsl alone breaks on native Windows: it rewrites C:\\... into /mnt/c/...
    which does not exist outside WSL, so trying the raw path first is what lets
    the hub (and each REPORT.md) be found in both environments."""
    if not p:
        return None
    for cand in (p, win_to_wsl(p)):
        if cand and os.path.exists(cand):
            return cand
    return None


def load_catalog():
    for hub in HUB_CANDIDATES:
        wp = resolve_path(hub)
        if wp:
            with open(wp, encoding="utf-8") as fh:
                data = json.load(fh)
            try:  # refresh the committed fallback (web-safe: drop local paths,
                  # since this repo is public and the page never renders them)
                safe = copy.deepcopy(data)
                for s in safe.get("strategies", []):
                    s.pop("paths", None)
                os.makedirs(os.path.dirname(FALLBACK), exist_ok=True)
                with open(FALLBACK, "w", encoding="utf-8") as out:
                    json.dump(safe, out, indent=2, ensure_ascii=False)
            except OSError:
                pass
            return data, wp
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
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
{body}
<footer class="shell-foot"><div class="container"><p>Backtests run under a fixed
validation protocol on pessimistic retail costs. Verdicts are research findings,
not investment advice; past results do not guarantee future outcomes.</p></div></footer>
</body></html>"""


def render_report_page(strat):
    """Convert a strategy's REPORT.md to docs/bt_<key>.html. Returns the
    filename if written, else None."""
    md_path = resolve_path((strat.get("paths") or {}).get("report_md"))
    out_name = strat.get("report_html") or f"bt_{strat['key']}.html"
    if not md_path:
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


def _xref(strat):
    """Cross-reference each card to its deployment status on the Strategies page,
    so every successful backtest also points at the live systematic book."""
    badge = strat.get("badge", "red")
    if strat.get("gfc_test_passed"):
        return ('<b>Deployable, GFC-tested</b> — a validated building block of the live '
                'regime-adaptive book; also surfaced on the '
                '<a href="strategies.html">Strategies</a> page.')
    if badge == "green":
        return ('Deployable — a validated building block behind the live book; see the '
                '<a href="strategies.html">Strategies</a> page.')
    if badge == "yellow":
        return ('Ensemble component — used as one signal inside the live book; see the '
                '<a href="strategies.html">Strategies</a> page.')
    return ""


def card(strat, report_link):
    # Delegates to the shared glossary renderer (single source of truth for the
    # card markup) and adds the deployment cross-reference line.
    return bt_card(strat, report_link, _xref(strat))


def main():
    data, src = load_catalog()
    strats = data.get("strategies", [])
    asof = data.get("updated", "")

    # The website is a curated showcase: only positive-verdict strategies
    # (public:true) get a card and an on-site report page. Failures stay in the
    # internal Trading_Index ledger, not on the public site.
    public = [s for s in strats if s.get("public")]

    cards = ""
    for s in public:
        link = render_report_page(s)
        cards += card(s, link)

    # keep docs/ in sync: a strategy flipped to non-public should not leave its
    # report page publicly reachable (bounded to filenames declared in the JSON).
    for s in strats:
        if not s.get("public"):
            stale = os.path.join(DOCS, s.get("report_html") or f"bt_{s['key']}.html")
            if os.path.exists(stale):
                os.remove(stale)

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
<p class="bt-intro">A curated view of the strategies that earned a positive verdict. Color shows the call:
<b style="color:#0a5d3a">green</b> = deployable (survives the full protocol and beats the S&amp;P on
risk-adjusted terms), <b style="color:#6b7280">amber</b> = ensemble component (real edge, not
standalone-worthy). Metrics and verdicts are pulled verbatim from each backtest's report; the
full research ledger, including the ideas that failed, is kept internally. The deployable results
here are the validated building blocks behind the live book on the
<a href="strategies.html">Strategies</a> page. Performance metrics shown are real
and scale-invariant; strategy parameters, asset universes and entry/exit rules are
redacted for confidentiality.</p>
<div class="btgrid">{cards}</div></section>
{method}
</main>"""

    page = shell("LTCMA 2026 — Strategy Backtests", body)
    # inject page-specific CSS right before </head>
    page = page.replace('<link rel="stylesheet" href="style.css"></head>',
                        f'<link rel="stylesheet" href="style.css">\n<style>{PAGE_CSS}</style></head>')
    with open(os.path.join(DOCS, "backtests.html"), "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"  backtests.html  ({len(public)} public / {len(strats)} total, source: {src})")


if __name__ == "__main__":
    main()
