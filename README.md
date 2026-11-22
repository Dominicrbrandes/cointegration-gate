# A Cointegration Gate Is Useful but Not Sufficient

Code for the paper *A Cointegration Gate Is Useful but Not Sufficient: Walk-Forward Evidence from Seven U.S.-Listed Pairs* ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7204658)), a cointegration-based statistical-arbitrage study across a pre-specified universe of economically-linked U.S. equity pairs.

**Author:** Dominic Brandes

## Research question

Among a pre-specified set of economically-linked U.S. equity pairs, which exhibit genuine (not spurious) cointegration, and does any resulting mean-reversion edge survive realistic transaction costs and capacity constraints?

## Pre-specified universe (committed in `config.yaml` ex ante)

| Pair | Category | Economic rationale | A-priori expectation |
|---|---|---|---|
| GOOG / GOOGL | Dual-class shares | Claims on the same company; GOOGL has voting rights, GOOG does not | Strongest cointegration case |
| V / MA | Payment networks | Same duopoly business model, same macro drivers | Likely cointegrated |
| XOM / CVX | Integrated oil majors | Same commodity exposure, same sector shocks | Plausible, regime-dependent |
| KO / PEP | Beverages | Classic textbook pair; same demand drivers | Often fails in modern data - instructive |
| HD / LOW | Home improvement | Duopoly, same housing / consumer cycle | Borderline |
| GLD / GDX | Gold vs gold miners | Miners are levered gold exposure | Loose, unstable beta - interesting borderline |
| **SPY / QQQ** | **Negative control** | Both broad equity beta; QQQ is a tech-tilted, higher-beta subset; log-spread trends | **Should fail all tests** |

## Reproducibility

- Data: yfinance (primary) / Stooq (fallback), adjusted close, cached to `data/raw/` with fetch date stamped per ticker.
- Random seeds: every Monte Carlo / bootstrap step is seeded from `project.master_seed` (42) in `config.yaml`.
- No look-ahead: z-score uses `spread.shift(1).rolling(lookback)`; P&L uses `position.shift(1) * spread_change`. Cointegrating vector (α, β) fit on training window only, applied unchanged to test.

### Data snapshot

**The price data is not included in this repository.** It was downloaded from Yahoo Finance through `yfinance`, whose terms do not allow redistributing it. The loaders in `src/data.py` download any price or volume series missing from `data/raw/` or `data/volumes/` on first run, and `scripts/fetch_open_ratio.py` rebuilds `data/raw_open/`. A fresh download will not reproduce the hashes below exactly: Yahoo restates adjusted closes after every later dividend or split, which is the backward-adjustment issue discussed in Section 5 of the paper. Expect small differences from the published numbers for that reason.

The study runs from the cached parquet snapshot stamped `2026-05-30`. The snapshot is fixed. SHA-256 over the fourteen `data/raw` files concatenated in sorted filename order is

```
bd8995e94092e29c184a16d28b7f24cfa5b794d8597c6b9f6ae40f27c7df0828
```

and over the fourteen `data/volumes` files by the same procedure,

```
cec7b7fa2d839684adc6859d056ea144dd595c32d798dece979f83bc04254b1f
```

The `data/raw_open` files carry a later fetch stamp and are used only by the execution-timing, open-based and closing-price-noise results (Sections 3.4, 4.9 and 4.10 of the paper). They hold the same-day open-to-close ratio and the open series reconstructed from it; they do not modify the close snapshot, which is deliberate, because a fresh fetch of adjusted closes would restate the entire history at any distribution occurring after 2026-05-30 and silently re-base every number in the paper (see the backward-adjustment limitation in Section 5).

## Decision rule for "genuinely cointegrated" (locked ex ante)

A pair is classified genuinely cointegrated iff **at least 2 of the 3** static tests reject the no-cointegration null at the 5% level:

1. Engle-Granger (worse p-value across the two LHS orderings)
2. Johansen trace (rank = 0, det_order = 0, k_ar_diff = 1)
3. Phillips-Ouliaris Z_t (constant trend)

The rolling 126-bar Engle-Granger p-value fraction is reported as a stability **diagnostic**, not a classification gate.

## Repo layout

```
pairs-stat-arb/
  config.yaml            # all pre-specified choices
  requirements.txt
  src/
    config_io.py         # config loader and methodology-lock fingerprint
    data.py              # fetch, align, validate, cache
    cointegration.py     # EG (both orderings), Johansen, Phillips-Ouliaris, rolling EG
    spread.py            # cointegrating vector, OU half-life
    signals.py           # rolling z-score, entry/exit/stop
    backtest.py          # P&L, walk-forward
    costs.py             # cost sweep, breakeven
    capacity.py          # participation ceiling
    event_study.py       # event study, placebo, OU baseline, bootstrap CIs
    plotting.py          # shared matplotlib style
  scripts/
    run_stages_1_2.py    # data + cointegration
    ...
  data/raw/              # parquet cache with fetch_date stamp
  results/               # serialized result objects (git-ignored, regenerated)
  figures/
  paper/
```

## Paper

The research note lives at `paper/pairs_stat_arb.md` (markdown source-of-truth) and `paper/pairs_stat_arb.pdf` (build artifact). The PDF is committed for convenience but regenerated from one command - any difference between the two is a bug.

To regenerate the PDF after editing the markdown:

```bash
python scripts/render_paper.py
```

`scripts/render_paper.py` is the authoritative form of the build. It runs, in outline:

```bash
pandoc paper/pairs_stat_arb.md \
       -o paper/pairs_stat_arb.pdf \
       --pdf-engine=xelatex \
       --citeproc \
       --resource-path=.:figures \
       -V mainfont="TeX Gyre Pagella" \
       -V monofont="TeX Gyre Cursor" \
       -V header-includes='\usepackage{booktabs}' \
       -V header-includes='\usepackage{fancyhdr}...'
```

The two font flags are required, not optional: α, β, μ, and σ appear throughout the prose, and the default Latin Modern body font has no glyphs for them, so omitting the flags silently drops those characters. The `booktabs` and `fancyhdr` preamble injections supply the table rules and the running heads; `scripts/render_paper.py` holds the full text of both.

Rendering requires `pandoc` (with `--citeproc` for the bibliography), `references.bib` and `chicago-author-date.csl` in the repo root, a TeX engine providing `xelatex` (TinyTeX is sufficient), and three CTAN packages installed once via `tlmgr install tex-gyre booktabs fancyhdr`: `tex-gyre` supplies body and monospace fonts with Greek coverage, the other two the table rules and running heads. The CSL file is the standard Chicago author-date style from the Citation Style Language repository.

The Python environment is pinned in `requirements-lock.txt` at the repository root, generated from the virtual environment that produced the results. The cointegration tests and the OU fits are the components most likely to drift across `statsmodels` releases, so that pin is the one to respect if the results are being reproduced.

The render script needs `pandoc` and `xelatex`. If either is missing or the build fails, it exits non-zero and leaves the existing PDF untouched; there is no fallback renderer. Install pandoc and a TeX distribution:

```bash
# Windows (winget)
winget install JohnMacFarlane.Pandoc
winget install MiKTeX.MiKTeX

# macOS (homebrew)
brew install pandoc basictex
```

## End-to-end rebuild

```bash
python scripts/run_stages_1_2.py     # data + cointegration
python scripts/run_stage_3.py        # spread + signal + single-split
python scripts/run_stage_4.py        # walk-forward (refit-both)
python scripts/run_stage_5.py        # costs, capacity, event study, synthesis
python scripts/make_paper_figures.py # cross-section figures for the paper

python scripts/closing_print_noise.py  # closing-price noise (Sec 4.10)
python scripts/window_sensitivity.py   # walk-forward block sizes (Sec 4.8)

python scripts/render_paper.py       # markdown -> PDF
```

`closing_print_noise.py` reads `data/raw_open`, so `scripts/fetch_open_ratio.py` must have been run once. Appendix A of the paper lists the remaining robustness scripts.

A reproducibility check inside `run_stage_5.py` re-derives the walk-forward composite net Sharpe at the baseline 3 bps cost for all seven pairs and asserts the value matches the stage-4 output to within 1e-6. Any drift is a hard failure.
