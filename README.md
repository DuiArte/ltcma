# LTCMA — Long-Term Capital Market Assumptions

A proprietary, fully reproducible **12-year forward outlook for global asset
classes** — building-block expected returns, a Ledoit-Wolf-shrunk risk model,
a regime-switching GPU Monte Carlo engine, a priced-in indicator dashboard, and
a methodology backtest. Built entirely on **free public data**.

**Live site:** `https://<your-username>.github.io/<repo-name>/`
*(enable GitHub Pages on the `main` branch, `/docs` folder — see below)*

The interactive dashboard auto-refreshes weekly via GitHub Actions.

## What's here

| Path | Contents |
|---|---|
| `scripts/` | The pipeline, `01`–`17` (data → returns → risk → simulation → site) |
| `data/` | Model inputs and outputs (small CSVs) |
| `report/` | The full written report — Markdown, Word, PDF, and figures |
| `docs/` | The published website (served by GitHub Pages) |
| `.github/workflows/` | The weekly auto-refresh workflow |

## How the auto-refresh works

`.github/workflows/refresh.yml` runs every Monday: it re-pulls live signals
(FRED yields/curve/breakevens/VIX, the GPR and EPU uncertainty indices),
rebuilds the site, and commits. The **live market snapshot** and **priced-in
dashboard** therefore stay current with no manual step.

The heavy layers — the GPU regime-switching Monte Carlo and the long-history
recalibration — are **not** in the weekly job (GitHub runners have no GPU).
Those are re-run locally and committed periodically; their outputs ship as CSVs.

## Reproducing locally

```
pip install -r requirements.txt   # + scikit-learn, weasyprint, python-docx for the full pipeline
python scripts/01_fetch_data.py   # ... through 17_build_site.py
```

The full pipeline expects the project at `~/LTCMA` and (for the simulation and
FX-ingest steps) the RAPIDS GPU stack. The weekly refresh needs only the lean
dependencies in `requirements.txt`.

## Data sources

Yahoo Finance, FRED (Federal Reserve), Damodaran/NYU Stern, Robert Shiller, the
Ken French Data Library, Siblis Research, the Caldara-Iacoviello GPR index, the
Baker-Bloom-Davis EPU index, and central-bank releases. All free and public.

## Scope

This repository contains **only** the capital-market-assumptions model — a
research framework over public data. It contains **no trading-strategy code,
no signals, and no proprietary alpha.**

## Disclaimer

Expected returns are forward-looking estimates, not guarantees; actual outcomes
will differ materially. This is research, **not investment advice**, and not a
solicitation to buy or sell any security.
