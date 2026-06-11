"""LTCMA — Step 27: Research Notes page (docs/research.html + research.ai.txt).
The public brutal-honesty research record: the discovery funnel, the 14-batch
negative streak, and all 18 load-bearing findings as filterable note cards.
Negative results are the expensive part of quantitative research; publishing
them is the point. Every card body is written public-safe (statistics stay —
they are scale-invariant; tickers, parameters, thresholds and paths do not
appear) and additionally routed through the _bt_redact backstop.
Static content: update the FINDINGS / BATCHES blocks when STRATEGY_LOG gains
a new finding, then re-run (the daily refresh also re-runs this).
"""
import os
import pandas as pd
from glossary import NAV, _bt_redact

from paths import DOCS_S as DOCS  # repo-anchored (2026-06-10)
ASOF = pd.Timestamp.today().strftime("%d %b %Y")

# ── the funnel (headline numbers — keep in sync with STRATEGY_LOG tally) ─────
FUNNEL = [
    ("14", "discovery batches — every one negative"),
    ("~181", "signals & strategies tested"),
    ("1", "durable feature-level edge found"),
    ("3", "strategies that cleared the survival bar"),
    ("18", "load-bearing findings published"),
]

# ── the batch record (axis tested · trials · outcome) ────────────────────────
BATCHES = [
    ("v0.5", "May 2026", "Baseline daily weak-signal library — trend, mean-reversion, volatility and range families on a 27-instrument universe", "~20",
     "One feature retained as a model input (a 5-day mean-reversion effect); nothing deployable standalone."),
    ("v0.6", "Jun 2026", "Machine-learned price-path forecast features", "2",
     "No edge beyond what the simple features already carry."),
    ("v0.7-T1", "Jun 2026", "Synthetic-path Monte Carlo robustness features", "—",
     "Negative; synthetic paths add no conditioning information."),
    ("v0.7-T3", "Jun 2026", "Valuation-cycle (earnings, valuation level) conditioners on the surviving edge", "8",
     "0/8 — the gates delete trades in proportion, not noise. Finding #9 extended to fundamental conditioners."),
    ("v0.8", "Jun 2026", "Macro / cross-asset standalone directional signals", "8",
     "0/8 — a single macro orientation cannot fit a heterogeneous cross-section. Finding #10."),
    ("v0.9", "Jun 2026", "Cross-sectional rank momentum · calendar / seasonal · daily-bar microstructure", "9",
     "0/9 — the only edge-ish features were the known survivor re-expressed. Finding #11."),
    ("v1.0", "Jun 2026", "Intraday microstructure at hourly and 5-minute resolution", "11",
     "0/11 — the gross edge is real and broad; spread + slippage consumes all of it. Finding #12."),
    ("v2.0-vol", "Jun 2026", "Options / volatility structure — variance premium, term structure, vol-of-vol", "30",
     "0/30 — the variance risk premium is real and repriced below the bar since 2018. Finding #13."),
    ("v2.0-exec", "Jun 2026", "Passive / maker execution study over the intraday gross edge (8 execution regimes)", "—",
     "The cost wall stands: passive fills convert explicit spread into adverse selection. Finding #12, extension."),
    ("v2.1", "Jun 2026", "Defined-risk option spreads · volatility futures carry · post-earnings drift · MX momentum", "4 pilots",
     "0/4 — premium thinness is wrapper-independent; free option-chain data is crash-blind. Finding #14."),
    ("v2.2", "Jun 2026", "MX momentum re-tested on a point-in-time universe (delisted names restored)", "1",
     "Dead — survivorship was roughly half the measured edge. Finding #15."),
    ("v2.3-A", "Jun 2026", "Event / macro-calendar premia — pre-FOMC drift, payrolls-day, CPI-day", "20",
     "0/20 — the premia replicate with the right sign and are below cost per event. Finding #16."),
    ("v2.3-B", "Jun 2026", "Crypto funding / basis carry and momentum (first touch of the asset class)", "20",
     "0/20 — the funding carry was a real premium and has been institutionalized away. Finding #17."),
    ("v2.3-C", "Jun 2026", "Slow fundamental — valuation-sorted rotation, real-rate FX carry, term-premium switching", "13",
     "0/13 — the formal passers were index beta in disguise. Finding #18."),
]

# ── the findings (public-safe rewrites; tag ∈ closed/method/positive) ────────
# tag labels: closed = an axis tested and closed · method = a protocol rule the
# program now enforces · positive = a result that strengthened the book.
FINDINGS = [
    ("#1", "closed", "2026-05-28", "Double-gating is the dominant failure mode",
     "Strategies that already carry internal regime detection lose edge when an "
     "external regime gate is layered on top — the signal gets trimmed twice. "
     "Observed across four sleeves at −0.14 to −0.55 Sharpe each. Rule: regime "
     "adaptation lives in exactly one layer."),
    ("#2", "method", "2026-05-28", "Partial-window winners are usually rally artifacts",
     "A precious-metals momentum system that looked deployable on an eight-year "
     "window collapsed on the full 23-year history: its profits clustered inside "
     "two secular rallies and the signal was dead everywhere else. Rule: any "
     "momentum-on-metals result must survive the full multi-decade window before "
     "deployment."),
    ("#3", "method", "2026-05-28", "Macro feature stores are circuit breakers, not overlays",
     "A 121-column macro / valuation / credit feature store improved no strategy "
     "as a per-bar gate. The only working pattern is a rare hard kill-switch that "
     "fires on well under 1% of bars and goes flat across all sleeves in genuine "
     "crisis. Conditioning everything on macro state sounds rigorous and measures "
     "worse."),
    ("#4", "positive", "2026-05-28", "Regime-aware weighting beats per-strategy gating",
     "Leaving each sleeve ungated and adapting portfolio weights by regime "
     "preserves each sleeve's native edge while still adapting to macro state. "
     "(Later sharpened by Finding #9: when sleeves defend themselves internally, "
     "even portfolio-level down-weighting can invert.)"),
    ("#5", "method", "2026-05-28", "Check the fire-rate before you gate",
     "Several proposed gating conditions essentially never fire on realized "
     "history — their 'off' state dominates and any strategy gated on them is "
     "unchanged. Rule: compute the historical fire-rate first; below ~1% of bars "
     "the gate is dead weight or an untestable promise."),
    ("#6", "method", "2026-05-28", "Verify the model that verified the result",
     "Two verification runs produced confident-but-vague metrics and were traced "
     "to an ambiguous model tier in the AI tooling. Load-bearing verdicts are "
     "re-run on the flagship configuration before anything ships. Honesty "
     "discipline applies to the tooling, not just the results."),
    ("#7", "method", "2026-05-29", "Research continuity must be written, not remembered",
     "A research program operated with AI agents is stateless between sessions: "
     "only the standing logs survive. Every protocol, verdict and open question "
     "lives in the written record — if it isn't written down, the next session "
     "doesn't know it. This page is part of that record."),
    ("#8", "positive", "2026-05-30", "The gold-decomposition stress test",
     "Any ensemble that holds gold must be re-run with gold stripped before "
     "promotion. The flagship allocation passed cleanly — positive Sharpe in "
     "every gold-bear cohort — refuting the rally-artifact hypothesis for it. "
     "Gold's role there is diversification insurance, not the engine. This test "
     "is now standard for every gold-holding candidate."),
    ("#9", "closed", "2026-05-31", "External regime-gating harms self-defended sleeves",
     "When a sleeve already carries an internal trend / regime filter, an external "
     "regime-conditional weight that down-weights it in stress is architecturally "
     "inverted — it pulls capital away precisely when the internal filter is doing "
     "the most defending. The ungated allocation strictly dominated the gated one "
     "in an extended GFC analog, passing the sub-10% drawdown bar where the gated "
     "version failed. Confirmed five times since, most recently on a carry stream."),
    ("#10", "closed", "2026-06-03", "Macro state has no usable directional form on this data",
     "A single risk-on / risk-off macro orientation cannot fit a heterogeneous "
     "cross-section — the same state implies opposite correct signs across "
     "instruments — and as a conditioner it adds no information either. Across "
     "eight macro and cross-asset features, none cleared the discovery bar. Macro "
     "variables are conditioner axes, not standalone signals; and conditioning "
     "also fails (#9)."),
    ("#11", "closed", "2026-06-04", "The daily horizon is exhausted: one edge",
     "Three independent new signal families — cross-sectional rank momentum, "
     "calendar / seasonal, daily-bar microstructure — were tested for a broadly "
     "replicating edge uncorrelated to the known mean-reversion survivor. None "
     "passed: the genuinely-new axes have no edge, and the only edge-ish streams "
     "are the survivor re-expressed in different coordinates. The honest reading: "
     "this dataset and the daily horizon are exhausted for single-name directional "
     "alpha."),
    ("#12", "closed", "2026-06-04", "The cost wall: a real gross edge that cannot be executed",
     "Intraday microstructure signals carry genuine gross edge — broad enough to "
     "clear the discovery bar at zero cost — but spread plus slippage consumes all "
     "of it at any hold inside four hours, and finer bars are strictly worse. A "
     "follow-up execution study with empirically-measured passive fills closed the "
     "remaining exit: maker tactics convert the explicit spread into adverse "
     "selection of nearly the same size. Rule: per-trade gross edge below a few "
     "basis points cannot be engineered into profitability by any execution "
     "tactic."),
    ("#13", "closed", "2026-06-09", "The variance risk premium is real — and repriced",
     "The equity-index variance risk premium is the one robust full-period edge "
     "found since the survivor: harvesting it in contango netted Sharpe ≈ 0.8 in "
     "every perturbation tested. But the February-2018 volatility event repriced "
     "it below the deployment bar, and it loses together with long equity exactly "
     "in crash tails — adding it raises tail risk instead of diversifying. Also a "
     "reusable lesson: never compute a Sharpe on overlapping multi-day strips; "
     "book at settlement or mark daily."),
    ("#14", "closed", "2026-06-10", "Premium thinness is wrapper-independent",
     "Re-expressing the variance premium as defined-risk option spreads fixes the "
     "tail profile (crash-correlation turns slightly negative) but cannot "
     "manufacture premium that is no longer there: three independent wrappers — "
     "ETP carry, volatility futures, option spreads — give one structural answer. "
     "Data trap worth publishing: free option-chain boards go blind exactly when "
     "volatility explodes, so every free-chain short-vol backtest is an upper "
     "bound. Check strike coverage through the crash windows before trusting any "
     "chain dataset."),
    ("#15", "method", "2026-06-10", "Survivorship is ~half the measured edge in small markets",
     "The program's one momentum pulse died when re-tested on a point-in-time "
     "universe with the delisted and suspended names restored: the clean number "
     "was roughly half the survivor-list number. Rule: in small markets, "
     "backtests start from the point-in-time panel; survivor-list results are "
     "upper bounds inflated by ~0.3–0.4 Sharpe."),
    ("#16", "closed", "2026-06-10", "Announcement premia replicate — and are unharvestable",
     "The published macro-calendar premia (pre-FOMC drift, the payrolls-day "
     "premium) replicate in our data with the right sign, decaying after 2015 "
     "exactly as the literature reports — and their per-event edge is single-digit "
     "basis points, below realistic cost. The cost-wall rule (#12) extends from "
     "microstructure to the event calendar. CPI-day textbook logic is wrong-signed "
     "at the daily horizon: by the close the market has already absorbed and "
     "partly mean-reverted the print."),
    ("#17", "closed", "2026-06-10", "Crypto funding carry: a Sharpe-4 premium, institutionalized away",
     "The delta-neutral funding harvest was genuinely real — roughly 10% a year at "
     "2% volatility for several years, nearly uncorrelated to everything else in "
     "the book. It is gone: excess returns turned negative as ETF-era arbitrage "
     "capital compressed funding below the risk-free rate. The same pattern the "
     "2018 vol event left on the variance premium, on a new asset class. A "
     "re-entry trigger is monitored quarterly. Reusable lesson: any accrual-yield "
     "stream must be marked with both legs daily before its Sharpe means anything "
     "— the smooth-accrual artifact printed Sharpe 8 before it was caught."),
    ("#18", "method", "2026-06-10", "The beta knife is mandatory",
     "Any long-only absolute-return 'pass' must be decomposed against the passive "
     "benchmark over the same window before it counts. A valuation-sorted sector "
     "rotation formally passed every bar in the protocol and was the index in "
     "disguise: beta ≈ 1.0, excess-of-benchmark Sharpe ≈ 0.2–0.3, with an index-"
     "sized drawdown. Absolute significance tests on long-equity streams in a "
     "bull decade are uninformative; report excess-of-benchmark Sharpe and beta "
     "alongside every long-only result."),
]

TAG_LABEL = {"closed": "Axis closed", "method": "Protocol rule", "positive": "Positive result"}
TAG_COLOR = {"closed": "#7c2d12", "method": "#0a2540", "positive": "#0a5d3a"}

# ── render ───────────────────────────────────────────────────────────────────
funnel_html = "".join(
    f'<div class="metric"><div class="mv">{v}</div><div class="mk">{k}</div></div>'
    for v, k in FUNNEL)

batch_rows = ""
for code, date, axis, trials, outcome in BATCHES:
    batch_rows += (f'<tr><td>{code}</td><td>{date}</td>'
                   f'<td class="ax">{_bt_redact(axis)}</td><td>{trials}</td>'
                   f'<td class="neg" style="text-align:center">0</td>'
                   f'<td class="ax">{_bt_redact(outcome)}</td></tr>')

cards = ""
for num, tag, date, title, body in FINDINGS:
    fid = "f" + num.replace("#", "")
    cards += (
        f'<article id="{fid}" data-tag="{tag}" class="btcard fcard fcard-{tag}">'
        f'<div class="bt-head"><span class="bt-badge" style="background:{TAG_COLOR[tag]}">'
        f'{TAG_LABEL[tag]}</span><span class="bt-date">{num} &middot; {date}</span></div>'
        f'<h3 class="bt-name">{_bt_redact(title)}</h3>'
        f'<p class="bt-tests" style="flex:1;margin-bottom:0">{_bt_redact(body)}</p>'
        f'</article>')

PILLS = ('<div class="pills" data-group="findings">'
         '<button class="pill on" data-f="all">All 18</button>'
         '<button class="pill" data-f="closed">Axes closed</button>'
         '<button class="pill" data-f="method">Protocol rules</button>'
         '<button class="pill" data-f="positive">Positive results</button>'
         '</div>')

CSS = r"""
.toc{display:flex;flex-wrap:wrap;gap:0;border:1px solid #d4d4d4;margin:0 0 2.6rem;width:fit-content;max-width:100%}
.toc a{font:500 12.5px 'Inter',sans-serif;color:#555;text-decoration:none;padding:8px 16px;
border-right:1px solid #d4d4d4;letter-spacing:.01em;transition:background .12s,color .12s}
.toc a:last-child{border-right:0}
.toc a:hover{background:rgba(10,37,64,.05);color:#111}
.pills{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 22px}
.pill{font:500 12px 'Inter',sans-serif;letter-spacing:.02em;color:#0a2540;background:#fff;
border:1px solid #d4d4d4;padding:6px 14px;cursor:pointer;transition:all .12s}
.pill:hover{background:rgba(10,37,64,.05)}
.pill.on{background:#0a2540;color:#fff;border-color:#0a2540}
.btgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:1.5rem}
.btcard{background:#fff;border:1px solid #e5e5e5;border-top:3px solid #d4d4d4;
padding:24px 24px 20px;display:flex;flex-direction:column;transition:background .15s ease-out}
.btcard:hover{background:rgba(10,37,64,.045)}
.fcard-closed{border-top-color:#7c2d12}
.fcard-method{border-top-color:#0a2540}
.fcard-positive{border-top-color:#0a5d3a}
.bt-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}
.bt-badge{font-size:10.5px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;color:#fff;padding:4px 10px}
.bt-date{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums;font-size:11.5px;color:#888}
.bt-name{font-family:'Spectral',Georgia,serif;font-size:19px;font-weight:500;color:#111;margin:0 0 6px;line-height:1.25}
.bt-tests{font-size:13.5px;color:#444;line-height:1.6;margin:0}
.ptable td.ax{font-family:'Inter',sans-serif;font-weight:400;text-align:left;color:#444;
font-size:12.5px;line-height:1.5;white-space:normal;min-width:200px}
.survive{border-left:2px solid rgba(10,37,64,.2);padding:.7rem 1.2rem;margin:.9rem 0;font-size:14.5px;color:#333;line-height:1.6;max-width:56em}
.survive b{color:#0a2540}
@media(max-width:560px){
  .toc{width:100%}.toc a{flex:1 1 auto;text-align:center;padding:8px 8px}
  .ptable td.ax{min-width:160px}
}
"""

FILTER_JS = r"""<script>
document.querySelectorAll('.pills').forEach(function(grp){
  grp.querySelectorAll('.pill').forEach(function(b){
    b.addEventListener('click',function(){
      grp.querySelectorAll('.pill').forEach(function(x){x.classList.remove('on');});
      b.classList.add('on');var f=b.getAttribute('data-f');
      document.querySelectorAll('.btgrid .btcard').forEach(function(c){
        c.style.display=(f==='all'||c.getAttribute('data-tag')===f)?'':'none';
      });
    });
  });
});
</script>"""

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carlos Duarte — Research Notes</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="style.css"><style>{CSS}</style></head>
<body><header class="shell"><div class="shell-in">
<span class="brand">Carlos Duarte&nbsp;·&nbsp;<b>Quantitative Research</b></span>{NAV}
</div></header>
<section class="hero"><div class="container">
<h1>Research Notes — the full record</h1>
<p class="lede">What was tested, what failed, and the little that survived.
Roughly 181 signals and strategies across 14 discovery batches have produced
exactly one durable feature-level edge and three deployable strategies — and
every batch since the first has promoted nothing. That is the honest base rate
of systematic-edge discovery, and hiding it would misstate how hard this is.
The 18 load-bearing findings below are the working capital of the program.</p>
<p class="asof">As of {ASOF} &middot; negative results published by design</p>
</div></section>
<main class="container">
<div class="toc"><a href="#funnel">The funnel</a><a href="#batches">Batch record</a>
<a href="#findings">The 18 findings</a><a href="#survives">What survives</a></div>

<section class="block" id="funnel"><h2>The discovery funnel</h2>
<p class="note">Most ideas die. The protocol is built so they die in research,
not in the account: smart-search &rarr; walk-forward &rarr; deflated Sharpe &rarr;
Monte Carlo &rarr; held-out window &rarr; benchmark gate &rarr; sub-10% drawdown bar.
What the funnel has produced so far:</p>
<div class="metrics" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">{funnel_html}</div></section>

<section class="block" id="batches"><h2>The batch record — 14 consecutive negatives</h2>
<p class="note">Each batch is a pre-registered set of trials on one axis, run
under the full protocol with pessimistic retail costs. A batch "promotes" a
signal only if it clears every bar. None has. Each negative closed an axis or
hardened a rule — the lessons compound even when the P&amp;L column doesn't.</p>
<div class="tile" style="padding:0 16px 8px;overflow-x:auto">
<table class="ptable"><thead><tr><th style="text-align:left">Batch</th>
<th style="text-align:left">Date</th><th style="text-align:left">Axis tested</th>
<th>Trials</th><th>Promoted</th><th style="text-align:left">Outcome</th></tr></thead>
<tbody>{batch_rows}</tbody></table></div></section>

<section class="block" id="findings"><h2>The 18 findings</h2>
<p class="note">Written so a reader (or the next research agent) can act on them
without re-deriving anything. <span style="color:#7c2d12;font-weight:600">Red</span>
= an axis tested and closed &middot; <span style="color:#0a2540;font-weight:600">blue</span>
= a protocol rule the program now enforces &middot;
<span style="color:#0a5d3a;font-weight:600">green</span> = a result that strengthened
the book. Statistics shown are scale-invariant; parameters, tickers and
mechanics stay internal.</p>
{PILLS}
<div class="btgrid">{cards}</div></section>

<section class="block" id="survives"><h2>What survives</h2>
<p class="note">After 14 batches, the program's honest position:</p>
<div class="survive"><b>Three deployable strategies</b> cleared the full survival
protocol — led by the flagship <b>Static Drift-Weight 50/30/20</b> (Sharpe 1.33,
GFC-tested, sub-10% drawdown with headroom). Curves, drawdowns and the complete
indicator set are on the <a href="strategies.html">Strategies</a> page, alongside
every archived failure with its lesson.</div>
<div class="survive"><b>One durable feature-level edge</b> — a 5-day mean-reversion
effect that replicates broadly across the universe. It is used as a model input,
never deployed standalone, and every attempt to gate, condition or improve it has
made it worse (#9, #10).</div>
<div class="survive"><b>The conclusion the record supports:</b> harvest the
flagship; the next discovery batch needs a new data axis or a new market, not
another pass over this dataset. Two monitored re-entry triggers (the variance
premium re-fattening; crypto funding clearing the risk-free rate by a margin)
would reopen closed axes if the world changes.</div></section>
</main>
<footer class="shell-foot"><div class="container"><p>Research record, not
investment advice. Negative results are published by design.</p></div></footer>
{FILTER_JS}
</body></html>"""

open(f"{DOCS}/research.html", "w", encoding="utf-8").write(HTML)

# ── low-token AI companion ───────────────────────────────────────────────────
ai = ["RESEARCH NOTES — AI COPY (low-token)",
      f"asof={ASOF}; funnel: 14 batches all negative | ~181 trials | 1 durable edge "
      "(5d mean-reversion, input only) | 3 deployable strategies | 18 findings",
      "fields: finding|tag|date|title|gist"]
for num, tag, date, title, body in FINDINGS:
    gist = body.split(". ")[0][:160]
    ai.append("|".join([num, tag, date, title, gist]))
ai.append("batches: " + "; ".join(f"{c}={t} trials,0 promoted" for c, _, _, t, _ in BATCHES))
open(f"{DOCS}/research.ai.txt", "w", encoding="utf-8").write("\n".join(ai) + "\n")

print(f"research.html built ({len(FINDINGS)} findings, {len(BATCHES)} batches) + research.ai.txt")
