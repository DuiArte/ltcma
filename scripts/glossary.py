"""Shared site components: the navigation bar, the plain-language glossary,
and the currency badge. Imported by 17/18/19 so there is one source of truth.
"""

# --- navigation (single source of truth across all pages) ---
NAV = ('<nav><a href="index.html">Dashboard</a>'
       '<a href="report.html">Full Report</a>'
       '<a href="portfolio.html">Portfolio</a>'
       '<a href="stocks.html">Stock Analysis</a>'
       '<a href="glossary.html">Glossary</a>'
       '<a href="index.html#about">About</a></nav>')


def ccy_badge(currency, note=""):
    """A small badge stating which currency the figures on this step are in."""
    extra = f" &middot; {note}" if note else ""
    return (f'<span class="ccy">Currency: <b>{currency}</b>{extra}</span>')


# --- glossary: plain-language definitions, grouped by area ---
# Each entry: (term, plain-English explanation -- no math, no jargon).
GLOSSARY = {
    "Returns & Valuation": [
        ("Expected return",
         "Our best estimate of how much an investment earns per year, on "
         "average, over the next 12 years. It is an estimate, not a promise."),
        ("Building-block model",
         "Instead of guessing returns from past performance, we add up the "
         "pieces that actually drive a return — income, growth, inflation and "
         "any change in how expensive the asset is."),
        ("Valuation reversion (the lambda dial)",
         "Expensive markets tend to cool off and cheap ones to catch up. "
         "'Lambda' is a dial from 0 to 1 setting how strongly we assume that "
         "happens — 0 = not at all, 1 = fully."),
        ("CAPE",
         "A way to judge how expensive a stock market is, comparing today's "
         "price to ten years of earnings so one unusual year doesn't distort "
         "it. A high CAPE means the market is expensive."),
        ("Dividend yield",
         "The cash a company pays its shareholders each year, as a percentage "
         "of the share price."),
        ("Buyback yield",
         "When a company buys back its own shares, each remaining share owns a "
         "bigger slice of the business — effectively another form of return."),
        ("Equity risk premium",
         "The extra return investors expect for holding stocks instead of "
         "safe government bonds, to compensate for the bumpier ride."),
        ("Base currency",
         "The currency every figure in a section is expressed in. Returns on "
         "foreign assets are converted into this currency."),
    ],
    "Risk": [
        ("Volatility",
         "How much an investment's value swings up and down. Higher volatility "
         "means a bumpier ride — bigger gains but also bigger drops."),
        ("Correlation",
         "Whether two investments tend to move together or apart. Things that "
         "move apart cushion each other; things that move together don't."),
        ("Diversification",
         "Spreading money across investments that don't all move the same way, "
         "so a bad patch in one is softened by others."),
        ("Ledoit-Wolf shrinkage",
         "A statistical clean-up step that makes the table of how assets move "
         "together more reliable, by pulling noisy estimates toward a sensible "
         "average."),
        ("Sharpe ratio",
         "How much return you get for the risk you take. Higher is better — "
         "more reward per unit of bumpiness."),
        ("Drawdown",
         "The drop from an investment's peak value to its low point — a "
         "measure of the worst stretch an investor would have lived through."),
    ],
    "Simulation": [
        ("Monte Carlo simulation",
         "Running tens of thousands of possible futures for an investment to "
         "see the whole range of where it could end up, not just one guess."),
        ("Market regime",
         "A stretch of time with a distinct mood — a 'calm' regime versus a "
         "'stress' regime where markets are jumpier and move together more."),
        ("Fat tails",
         "Real markets produce extreme good and bad outcomes more often than a "
         "simple bell curve suggests. Modelling 'fat tails' takes that "
         "seriously."),
        ("Percentile",
         "A way to describe a range of outcomes. The 5th percentile is a bad "
         "case (only 5% of outcomes are worse); the 95th is a good case."),
        ("CVaR (conditional value at risk)",
         "The average result across only the worst outcomes — a more honest "
         "picture of the downside than a single worst-case number."),
        ("Probability of loss",
         "The share of simulated futures in which the investment ends up worth "
         "less than it started."),
    ],
    "Markets & Rates": [
        ("Yield",
         "The annual income a bond pays, as a percentage of its price."),
        ("Yield curve",
         "Interest rates for bonds of different lengths, plotted together. Its "
         "shape hints at what the market expects the economy to do."),
        ("Forward rate",
         "The interest rate the market currently expects to apply in the "
         "future — read out of today's bond prices."),
        ("Breakeven inflation",
         "The rate of inflation the bond market is currently expecting, "
         "derived by comparing ordinary and inflation-protected bonds."),
        ("Basis point",
         "One hundredth of a percent (0.01%). A rate moving from 4.00% to "
         "4.25% has moved 25 basis points."),
        ("GPR — Geopolitical Risk index",
         "A measure built from newspaper text of how much geopolitical tension "
         "(wars, conflict) is in the news."),
        ("EPU — Economic Policy Uncertainty",
         "A newspaper-based measure of how uncertain government and central-"
         "bank policy looks right now."),
        ("Priced in",
         "Something the market already expects, so it is reflected in current "
         "prices. A forecast only matters where it differs from what's "
         "priced in."),
    ],
    "Stock Analysis": [
        ("P/E ratio",
         "Price-to-earnings: the share price divided by earnings per share. "
         "Roughly, how many years of profit you are paying for."),
        ("P/B ratio",
         "Price-to-book: the share price versus the company's accounting net "
         "worth per share."),
        ("EV/EBITDA",
         "Compares a company's whole value (including debt) to its cash "
         "earnings — a way to value firms regardless of how they're financed."),
        ("ROE — return on equity",
         "How much profit a company generates on the money its shareholders "
         "have invested. Higher is generally better."),
        ("ROA — return on assets",
         "How much profit a company generates on all the assets it controls."),
        ("DuPont decomposition",
         "Breaking ROE into its three causes — profit margin, how hard assets "
         "are worked, and borrowing — to see why a company earns what it "
         "earns."),
        ("Profit margin",
         "The share of every sales dollar that survives as profit."),
        ("CAPM — required return",
         "A standard way to estimate the return an investor should demand from "
         "a stock, given its risk: a safe rate plus a premium for risk."),
        ("DDM — dividend discount model",
         "Values a share as the worth, in today's money, of all the dividends "
         "it is expected to pay in the future."),
        ("Justified P/E",
         "The price-to-earnings ratio a company's fundamentals actually "
         "support. Comparing it to the real P/E shows if the market is "
         "optimistic or cautious."),
        ("Beta",
         "How much a stock tends to move when the whole market moves. Above 1 "
         "= more jumpy than the market; below 1 = steadier."),
    ],
    "Portfolio": [
        ("Holding",
         "A single investment owned in the portfolio — one stock or fund."),
        ("Allocation (weight)",
         "How much of the portfolio is in a given holding, as a percentage."),
        ("Cost basis",
         "What was originally paid for a holding — the benchmark for measuring "
         "gain or loss."),
        ("Unrealized profit / loss",
         "The gain or loss on a holding that is still owned — it becomes real "
         "only when sold."),
    ],
}
