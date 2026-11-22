# Phase 1 measurement report - fold-seam accounting fix

Branch `seam-accounting-fix`, off `paper-final-pass`.
No manuscript file was touched. Every number below is measurement only.

---

## Task 1 - beta reconciliation

**Result: no defect. Everything reproduces exactly.**

`beta_canonical = beta` when `y_var == legs[0]`, else `1/beta`
(`src/backtest.py:442-444`). Recomputing it from raw beta plus the retained
orientation matches the stored column to 1e-12 on all 140 pair-folds.

Table 3's `beta-rng` column is the **canonical** span, and it reproduces:

| Pair | Table 3 beta-rng | Canonical span | Table 3 LHS sw. | Recomputed | Raw span |
|---|---|---|---|---|---|
| GOOG/GOOGL | 0.09 | 0.0853 | 2 | 2 | 0.0845 |
| V/MA | 0.85 | 0.8492 | 1 | 1 | 0.3976 |
| XOM/CVX | 3.67 | 3.6717 | 5 | 5 | 1.5403 |
| KO/PEP | 14.85 | 14.8529 | 6 | 6 | 1.4243 |
| HD/LOW | 1.28 | 1.2843 | 1 | 1 | 0.6115 |
| GLD/GDX | 0.82 | 0.8215 | 1 | 1 | 2.4593 |
| SPY/QQQ | 0.47 | 0.4681 | 5 | 5 | 1.2517 |

Section 4.7's GLD/GDX `[0.236, 1.057]` and V/MA `[0.745, 1.594]` both reproduce
as canonical ranges, as does Section 4.5's KO/PEP "-10.88 to +3.98".

**Which beta the seam analysis should quote.** The raw as-fitted beta together
with the retained orientation, because `compute_spread` uses exactly
`(y_var, x_var, alpha, beta)` and the canonical value never enters a spread. The
earlier seam run's GLD/GDX `[0.236, 2.461]` was the raw span; GLD/GDX flips
orientation, and `1/2.4593 = 0.4066` sits inside the published canonical range.
Both numbers were correct descriptions of different quantities.

**Consequence for the Phase 3 mechanism paragraph.** Contamination is driven by
how far the *spread definition* moves at a seam, which has two components: refit
of (alpha, beta) inside a fixed orientation, and an orientation switch, which
swaps LHS and RHS and redefines the spread outright. The three pairs with 5-6
switches (KO/PEP, SPY/QQQ, XOM/CVX) are the three largest Sharpe movements under
the fix. Quote canonical span *and* switch count; neither alone carries it.

---

## Task 2 - fold-seam P&L (the bug)

`src/backtest.py` now has `compute_composite_pnl`, which differences gross inside
each fold and concatenates. Costs are unchanged, still charged on `|delta position|`
over the concatenated position series.

This is the **minimal fix that preserves the Section 3.5 contract** (position
resets to flat at each boundary, prior position unwound). The first OOS bar of
each fold has no within-fold predecessor and the fold is entered flat, so its
gross is zero.

Three further call sites reconstructed composites the same buggy way and were
also fixed: `src/costs.py` (the breakeven solver and cost sweep),
`scripts/compute_dsr.py` (all 84 trial composites), and
`scripts/robustness_orientation.py`. `compute_pnl` now carries a docstring
warning; its three remaining callers are all single-fit and correct.

### Assertions

| Assertion | Result |
|---|---|
| A. Within-fold gross bit-identical; only first OOS bar of folds 1-19 changes | PASS, all 7 pairs |
| B. GOOG/GOOGL seams carrying an open position (Sec 4.4 says six) | 6 |
| C. Total composite cost unchanged | PASS, identical to 1e-15, all 7 pairs |

### Primary specification: composite net Sharpe

| Pair | Before (buggy) | After (per-fold) | Move |
|---|---|---|---|
| GOOG/GOOGL | 1.2853 | **1.3752** | +0.090 |
| V/MA | 0.3868 | **0.3653** | -0.022 |
| XOM/CVX | 0.0763 | **-0.1245** | -0.201 |
| KO/PEP | 0.5353 | **-0.0215** | -0.557 |
| HD/LOW | -0.1572 | **-0.3291** | -0.172 |
| GLD/GDX | 0.5314 | **0.3498** | -0.182 |
| SPY/QQQ | 0.1940 | **-0.1436** | -0.338 |

Under the fix the two cointegrated pairs are ranked first and second, and four of
the five non-cointegrated pairs are negative. Before the fix, KO/PEP (0.54) and
GLD/GDX (0.53) both outranked V/MA (0.39).

### Sensitivity, NOT ADOPTED: hold across the seam, rebalance by |d beta|

Reported because it is the more realistic desk behaviour, but it changes the
Section 3.5 contract and is therefore disclosed rather than adopted.

| Pair | Buggy | Per-fold (adopted) | Hold + rebalance |
|---|---|---|---|
| GOOG/GOOGL | 1.2853 | 1.3752 | 1.3622 |
| V/MA | 0.3868 | 0.3653 | 0.3586 |
| XOM/CVX | 0.0763 | -0.1245 | -0.2014 |
| KO/PEP | 0.5353 | -0.0215 | -0.0010 |
| HD/LOW | -0.1572 | -0.3291 | -0.3153 |
| GLD/GDX | 0.5314 | 0.3498 | 0.3886 |
| SPY/QQQ | 0.1940 | -0.1436 | -0.1322 |

The two conventions agree closely everywhere, which is the useful part: the
finding does not depend on which seam contract is chosen. The rebalancing charge
itself is negligible (1e-5 to 5e-4 log-return per pair over twenty folds).

---

## Task 3 - execution conventions

### Data

`scripts/fetch_open_ratio.py`. The 2026-05-30 close snapshot is **not** touched.
Open and Close come from one yfinance call; `r[t] = Open[t]/Close[t]` is
adjustment-invariant within the bar; `open[t] = cached_adj_close[t] * r[t]`.
New files carry their own date stamp in `data/raw_open/`.

- Date index matches the snapshot exactly: **3057 bars for all 14 tickers**, zero
  missing, zero extra, over 2014-04-03 to 2026-05-29.
- Ratio guard `r in (0.90, 1.10)` fired on **13 bars across 8 tickers**. Reported,
  not clipped, not filled. Every one is a real gap day: 2020-03-13/16/17/18/20
  (COVID), 2020-11-09 (LOW, vaccine announcement), 2025-04-09 (QQQ and SPY,
  tariff reversal). GDX is the worst at 0.7448 on 2020-03-16.

### Composite net Sharpe by convention (seam fix applied)

| Pair | Same close (as built) | Next open | Next close |
|---|---|---|---|
| GOOG/GOOGL | 1.3752 | **0.5671** | 0.4832 |
| V/MA | 0.3653 | **0.2085** | 0.1069 |
| XOM/CVX | -0.1245 | 0.0114 | 0.0940 |
| KO/PEP | -0.0215 | -0.0636 | -0.0160 |
| HD/LOW | -0.3291 | -0.4731 | -0.5598 |
| GLD/GDX | 0.3498 | 0.2545 | 0.2587 |
| SPY/QQQ | -0.1436 | 0.0322 | -0.0082 |

### Breakeven round-trip cost (bps), cointegrated pairs

| Pair | Same close | Next open | Next close |
|---|---|---|---|
| GOOG/GOOGL | 15.43 | **9.63** | 7.64 |
| V/MA | 26.14 | **17.31** | 9.88 |

### Gross P&L by days since entry (same close)

| Days held | GOOG/GOOGL % of gross | V/MA % of gross |
|---|---|---|
| 1 | **39.6%** | **60.8%** |
| 2 | 6.0% | -2.9% |
| 3 | 11.0% | 1.3% |
| 4 | 9.7% | -23.9% |
| 5 | 7.7% | -3.1% |
| 6+ | 25.9% | 67.8% |

The first bar after entry earns a mean of 6.15e-4 for GOOG/GOOGL against
1.1e-4 to 2.5e-4 on every later bar. That single bar is what a one-bar execution
delay forfeits, and it is why next-open costs 59% of the headline Sharpe.

---

## Task 4 - everything downstream

### Table 3

| Pair | S_net old -> new | AnnRet old -> new | BE old -> new | %folds+ | S std | beta-rng | LHS sw | Cap $M |
|---|---|---|---|---|---|---|---|---|
| GOOG/GOOGL | 1.29 -> **1.38** | +2.3% -> **+2.4%** | 14.9 -> **15.4** | 85% | 1.50 | 0.09 | 2 | 84.2 |
| V/MA | 0.39 -> **0.37** | +2.8% -> **+2.6%** | 27.9 -> **26.1** | 65% | 1.45 | 0.85 | 1 | 20.7 |
| XOM/CVX | 0.08 -> **-0.12** | +1.4% -> **-1.5%** | 15.9 -> **0.0** | 45% | 1.23 | 3.67 | 5 | 14.8 |
| KO/PEP | 0.54 -> **-0.02** | +8.5% -> **-0.2%** | 60.0 -> **1.0** | 50% | 1.09 | 14.85 | 6 | 12.1 |
| HD/LOW | -0.16 -> **-0.33** | -2.4% -> **-4.1%** | 0.0 -> 0.0 | 50% | 1.20 | 1.28 | 1 | 6.8 |
| GLD/GDX | 0.53 -> **0.35** | +9.4% -> **+5.2%** | 60.0 -> **50.9** | 65% | 1.60 | 0.82 | 1 | 25.0 |
| SPY/QQQ | 0.19 -> **-0.14** | +2.5% -> **-0.9%** | 27.0 -> **0.0** | 60% | 1.57 | 0.47 | 5 | 363.7 |

%folds+, per-fold S std, beta-rng, LHS switches and capacity are all **unchanged**:
per-fold results use a single fit and never crossed a seam, and capacity depends
on median canonical beta, which the fix does not touch.

### Table 4 (cost sweep)

| Cost bps | GOOG/GOOGL old -> new | V/MA old -> new |
|---|---|---|
| 0 | 1.60 -> **1.69** | 0.43 -> **0.41** |
| 2 | 1.39 -> **1.48** | 0.40 -> **0.38** |
| 4 | 1.18 -> **1.27** | 0.37 -> **0.35** |
| 6 | 0.96 -> **1.05** | 0.34 -> **0.32** |
| 8 | 0.75 -> **0.83** | 0.31 -> **0.29** |
| 10 | 0.53 -> **0.61** | 0.28 -> **0.26** |
| 12 | 0.31 -> **0.38** | 0.25 -> **0.22** |
| 15 | -0.01 -> **0.05** | 0.20 -> **0.18** |
| 20 | -0.55 -> **-0.51** | 0.12 -> **0.10** |
| 25 | -1.08 -> **-1.04** | 0.05 -> **0.02** |
| 30 | -1.58 -> **-1.56** | -0.03 -> **-0.06** |
| Breakeven | 14.9 -> **15.4** | 27.9 -> **26.1** |

Derived quantities in the same paragraph: gross Sharpe ratio 3.7x -> **4.11x**;
cost-tolerance ratio 0.53 -> **0.59**; GOOG/GOOGL sheds 0.107 -> **0.110** Sharpe
per bp, V/MA 0.016 -> **0.016** (unchanged).

### The Section 4.4 identity - HOLDS

| Pair | Round trips | Gross capture / RT | Breakeven | Identity |
|---|---|---|---|---|
| GOOG/GOOGL | 197.0 | 15.43 bps | 15.43 bps | exact |
| V/MA | 111.0 | 26.14 bps | 26.14 bps | exact |

The identity survives the fix at full precision. The paired values move from
(14.9, 27.9) to **(15.4, 26.1)**. The 197-vs-196 reconciliation also reproduces:
197 round trips by turnover, 196 flat-to-non-flat entries, difference is the one
cross-seam reversal.

### Table 5 (orientation robustness)

| Pair | S as built old -> new | S range old -> new | BE range old -> new |
|---|---|---|---|
| GOOG/GOOGL | 1.29 -> **1.38** | 1.07-1.29 -> **1.15-1.38** | 13.7-15.0 -> **14.3-15.6** |
| V/MA | 0.39 -> **0.37** | 0.13-0.39 -> **0.13-0.37** | 11.6-28.8 -> **11.1-26.1** |
| XOM/CVX | 0.08 -> **-0.12** | -0.15-0.09 -> **-0.12-0.05** | 0.0-20.1 -> **0.0-11.8** |
| KO/PEP | 0.54 -> **-0.02** | -0.04-0.54 -> **-0.21-0.12** | 0.0-60.0 -> **0.0-14.3** |
| HD/LOW | -0.16 -> **-0.33** | -0.16-0.00 -> **-0.33-0.11** | 0.0-2.6 -> **0.0-15.4** |
| GLD/GDX | 0.53 -> **0.35** | 0.33-0.57 -> **0.20-0.35** | 56.2-60.0 -> **26.7-50.9** |
| SPY/QQQ | 0.19 -> **-0.14** | -0.22-0.19 -> **-0.18--0.14** | 0.0-27.0 -> **0.0-0.0** |

Median ADF gaps and switch counts unchanged.

### Table 6 (DSR)

Candidate: as-built composite, annualized Sharpe **1.375** (was 1.29)

| Row | K | sqrt(V) old -> new | SR0 old -> new | DSR old -> new |
|---|---|---|---|---|
| 84 walk-forward composites (reported) | 84 | 0.42 -> **0.44** | 1.05 -> **1.08** | 0.77 -> **0.82** |
| 12 walk-forward composites, this pair only | 12 | 0.29 -> **0.31** | 0.48 -> **0.51** | 0.99 -> **1.00** |
| 84 stage-3 single-split grid Sharpes (legacy) | 84 | 0.37 -> **0.37** | 0.91 -> **0.91** | 0.88 -> **0.93** |

Candidate: band floor of Section 4.8, annualized Sharpe **1.154** (was 1.07)

| Row | K | sqrt(V) old -> new | SR0 old -> new | DSR old -> new |
|---|---|---|---|---|
| 84 walk-forward composites, pinned orientation | 84 | 0.40 -> **0.40** | 0.98 -> **1.00** | 0.61 -> **0.69** |
| 12 walk-forward composites, this pair only | 12 | 0.31 -> **0.32** | 0.52 -> **0.53** | 0.96 -> **0.97** |

The legacy row's trial variance is unchanged (stage 3 is single-split and never
crossed a seam); its DSR moves only because the candidate moved.

**The disclosed vulnerability survives.** DSR on the full budget is still below
0.95 (0.82, and 0.69 at the band floor), so Section 5's honesty paragraph keeps
its point. It is no longer as close to the line.

### Fourth (trailing-504) orientation convention

| Pair | As built | Trailing |
|---|---|---|
| GOOG/GOOGL | 1.3752 | **1.3783** |
| V/MA | 0.3653 | **0.1940** |
| XOM/CVX | -0.1245 | -0.0242 |
| KO/PEP | -0.0215 | -0.2164 |
| HD/LOW | -0.3291 | -0.1111 |
| GLD/GDX | 0.3498 | 0.1766 |
| SPY/QQQ | -0.1436 | -0.3716 |

### Section 4.3 distribution statistics

| Quantity | Old | New |
|---|---|---|
| GOOG/GOOGL daily net observations | 2,519 | **2,520** |
| GOOG/GOOGL drop-two-best composite | 1.04 | **1.08** |
| GOOG/GOOGL max drawdown | 2.75 pp | 2.75 pp |
| GOOG/GOOGL worst / best day | -0.94 / +0.82 | -0.94 / +0.82 |
| GOOG/GOOGL skew | -0.01 | **+0.22** |
| GOOG/GOOGL kurtosis | 14.3 | **13.7** |
| GOOG/GOOGL annualized vol | 1.8% | 1.78% |
| V/MA max drawdown | 13.8 pp | **12.97 pp** |
| V/MA skew | -0.33 | **-0.35** |
| GLD/GDX drop-two-best composite | 0.36 | **0.06** |
| GLD/GDX max drawdown | 38.1 pp | **46.29 pp** |
| GLD/GDX skew | +4.6 | **-0.17** |
| GLD/GDX kurtosis | 113 | **27.8** |
| GLD/GDX best single session | +24.6 pp | **+11.24 pp** |

### Event study and half-lives - UNCHANGED

Rule entries 196 (GOOG/GOOGL), 111 (V/MA), 307 pooled; placebo 523 / 388 / 911;
disjoint placebo 604. Longest CI separation 0 days on all three panels; pooled max
mean-curve gap 0.179, disjoint 0.270, GOOG/GOOGL-alone 0.181. Per-fold half-lives
range 2.99 to 50.91 with median 15.05 across forty pair-folds; entry-weighted
effective 12.5 days at t+20 and 16.7 days at t+60. The event study operates on
per-fold z-scores and never crossed a seam.

### Lo (2002) adjusted Sharpe

GOOG/GOOGL naive 1.375 -> Lo **1.651** (factor 19.06), rho_1 -0.161.
V/MA naive 0.365 -> Lo **0.410** (factor 17.83), rho_1 -0.035.

---

## Task 5 - cost denominator

**Confirmed in code.** `src/backtest.py:40` charges
`pos_change * (cost_bps / 2.0) / 10_000.0`, with no `|beta|` term. Three bps is an
all-in **pair-level** round-trip charge across both legs. A flat-to-long move of 1
pays 1.5 bps; a long-to-short move of 2 pays 3 bps. Cost code unchanged.

Sensitivity, costs scaled by `(1 + |beta|)`:

| Pair | median abs beta | Pair-level (as built) | Per-leg (1+abs beta) |
|---|---|---|---|
| GOOG/GOOGL | 0.990 | 1.3752 | **1.0532** |
| V/MA | 0.810 | 0.3653 | **0.3265** |
| XOM/CVX | 0.598 | -0.1245 | -0.1391 |
| KO/PEP | 0.704 | -0.0215 | -0.0442 |
| HD/LOW | 0.860 | -0.3291 | -0.3466 |
| GLD/GDX | 1.234 | 0.3498 | **0.3223** |
| SPY/QQQ | 1.080 | -0.1436 | -0.1931 |

GOOG/GOOGL is the pair the assumption matters for, because it turns over most.

---

## Sentences in `paper/pairs_stat_arb.md` that the new numbers falsify

Quoted with section. This list is the gate on Phase 2 and Phase 3.

### Abstract

1. "GOOG/GOOGL earns a composite net Sharpe of **1.29**" - now 1.38.
2. "A non-cointegrated pair, GLD/GDX, posts **0.53**---above the second
   cointegrated pair's **0.39**" - now 0.35 against 0.37. **The comparison
   reverses.** The sentence's rhetorical work (a failed pair outranking a passed
   one) no longer holds on these two numbers.
3. "the composite deflates to **0.77** against the full 84-cell selection budget
   (**0.99** against the per-pair budget)" - now 0.82 and 1.00.
4. "it ranges from **1.07 to 1.29** across defensible conventions" - now 1.15 to 1.38.
5. "Charged both at once---deflated at the bottom of that band---it falls to
   **0.61**" - now 0.69.
6. "breaking even at **14.9** bps round-trip against V/MA's **27.9**" - now 15.4
   and 26.1.

### Section 3.4 (execution convention)

7. "At the daily horizon and spread widths studied here **the difference is
   small**" - falsified. Next-open is 0.567 against 1.375, next-close 0.483.
8. "Round-trip costs are charged on |delta position_t|" - true but incomplete;
   Section 3.4's per-leg buildup language implies a denominator the code does not use.

### Section 4.3

9. "GOOG/GOOGL posts the highest composite net Sharpe (**1.29**)" - now 1.38.
10. "the composite over the remaining 18 folds is **1.04**" - now 1.08.
11. "On GOOG/GOOGL's **2,519** daily net observations" - now 2,520.
12. "the distribution is essentially symmetric (**skew -0.01**) with fat tails
    (**kurtosis 14.3**)" - now skew +0.22, kurtosis 13.7. The argument that a
    stopped rule would show pronounced negative skew survives and is slightly
    stronger, but both figures change.
13. "V/MA drops **13.8** points at worst with skew **-0.33**" - now 12.97 and -0.35.
14. "GLD/GDX is the contrast that makes the point---a **38.1**-point drawdown,
    skew **+4.6**, kurtosis **113**, and a single session worth **+24.6** points"
    - now 46.29, -0.17, 27.8, and +11.24. **See the surprises section: the +24.6
    session was itself a seam artifact.**
15. "Composite net Sharpe is **0.53**, which on its own reads as a respectable
    edge---above V/MA's **0.39**" - now 0.35 against 0.37; the ranking reverses.
16. "drop them and it falls to **0.36**, against GOOG/GOOGL's **1.04**" - now 0.06
    against 1.08.
17. "For GOOG/GOOGL, the walk-forward composite (**1.29**) sits well above the
    single-split test result (0.40). For V/MA the composite (**0.39**) ... For
    GLD/GDX the composite (**0.53**)" - now 1.38, 0.37, 0.35. Single-split values
    unchanged.
18. "KO/PEP posts a composite of **0.54** and a **60 bps** breakeven---on those two
    numbers alone the second-best pair in the universe, better than V/MA on both."
    - now -0.02 and 1.0 bps. **This paragraph's entire premise is gone.** KO/PEP no
    longer outranks anything, so the LHS-switch column is no longer needed to
    explain away a flattering composite.
19. "HD/LOW, with one switch, is a genuine small negative at **-0.16**" - now -0.33.
20. "SPY/QQQ's composite is **+0.19**. ... it comes out at **-0.22, -0.18, +0.18,
    and +0.19**---**noise in both directions** around zero" - now -0.14, and the
    four conventions are -0.37, -0.18, -0.14, -0.14. All four are negative, so
    "noise in both directions" is false. "Indistinguishable from zero" survives
    against the 0.32 standard error.

### Section 4.4

21. "Dotted verticals mark each pair's breakeven cost (**14.9 and 27.9** bps)"
    (Figure 3 caption) - now 15.4 and 26.1.
22. Table 4, all 22 sweep cells and both breakeven cells.
23. "GOOG/GOOGL has **3.7x** the gross Sharpe of V/MA (**1.60 vs 0.43**) but only
    **0.53** of V/MA's cost-tolerance: it sheds about **0.107** Sharpe per basis
    point" - now 4.11x, 1.69 vs 0.41, 0.59, and 0.110.
24. "Realized gross capture averages **14.9** bps per round trip for GOOG/GOOGL
    against **27.9** bps for V/MA" - now 15.43 and 26.14. The identity itself holds.
25. "a stronger caveat on V/MA's **27.9** bps breakeven than on GOOG/GOOGL's
    **14.9**" - now 26.1 and 15.4.

### Section 4.5

26. "the **14.9** bps round-trip breakeven, the **1.29** composite walk-forward net
    Sharpe at 3 bps, and the **+2.3%** annualized net return" - now 15.4, 1.38, +2.4%.
27. "**KO / PEP** at beta-range 14.85 and six LHS switches ... It posts the
    **second-highest composite in the universe (0.54)** and the **joint-highest
    breakeven** ... The composite column, taken alone, would rank the
    textbook-failed pair second" - now -0.02 and 1.0 bps. The whole bullet inverts.
28. "**V / MA** ... The compensating attribute is cost-tolerance: a **27.9** bps
    breakeven, **nearly twice** GOOG/GOOGL's" - now 26.1 against 15.4, a factor of
    1.69 rather than 1.87. "Nearly twice" is still defensible but the number moves.

### Section 4.7

29. Figure 1 caption: "the dashed line marks the composite net Sharpe" - the
    dashed line has moved on every panel. Figure regenerated.
30. Figure 2 caption is unaffected (beta panels unchanged).

### Section 4.8

31. Table 5, every S and breakeven-range cell.
32. "the honest headline is a Sharpe near **1.1 to 1.3**" - now 1.15 to 1.38.
33. "GOOG/GOOGL's breakeven moves only between **13.7 and 15.0** bps across
    conventions" - now 14.3 to 15.6.
34. "only two switches and one of the **narrowest bands at 0.2**" - now 0.22.
35. "KO/PEP, with a mid-range gap of 0.308 but six switches, **spans 0.6**;
    SPY/QQQ, five switches, **spans 0.4**" - now 0.34 and 0.04. SPY/QQQ is now the
    *narrowest* band in the universe, which inverts the sentence's use of it.
36. "XOM/CVX, on five switches, has a band **no wider than V/MA's** on a single
    switch" - now 0.18 against V/MA's 0.24, so still true, but check after rewrite.
37. Any sentence reporting the discarded trailing convention at **+1.381** and
    "**4 of 7** pairs, including **both cointegrated**, score higher under it" -
    now +1.3783, and only 3 of 7 score higher, with V/MA now scoring *lower*.
    **This claim inverts and it was load-bearing**: it was the evidence that the
    committed rule is not the flattering one.

### Section 5 / Table 6

38. Table 6, both candidate Sharpe labels (1.29, 1.07) and all fifteen numeric cells.
39. Any prose quoting DSR **0.77 / 0.99 / 0.88 / 0.61 / 0.96**.

### Conclusion

40. "earns a **1.29** composite net Sharpe across twenty folds" - now 1.38.
41. "breaking even at a **14.9** bps round-trip" - now 15.4.
42. "the composite deflates to **0.77** ... clearing the 0.95 bar only on the
    narrower per-pair budget (**0.99**)" - now 0.82 and 1.00.
43. "ranging from **1.07 to 1.29**" - now 1.15 to 1.38.
44. "leaves **0.61** on the full budget and **0.96** on the per-pair one" - now
    0.69 and 0.97.
45. "moving only between **13.7 and 15.0** bps across the same conventions" - now
    14.3 to 15.6.

### Appendix A

46. The committed `results/` artifacts and both figures were regenerated. Any
    checksum or file listing in Appendix A needs refreshing.

---

## Surprises, and things I could not verify

**1. GLD/GDX's "+24.6 point single session" was itself a seam artifact.** Section
4.3 cites it as evidence that GLD/GDX's composite is "a different kind of object."
The 2024-04-09 seam contributed +0.2399 in log-return, which is that session. Under
the fix the best session is +11.24 pp and the skew flips from +4.6 to -0.17. The
*conclusion* survives and strengthens (drop-two now takes GLD/GDX from 0.35 to
0.06, against GOOG/GOOGL's 1.38 to 1.08), but the evidence cited for it has to be
replaced wholesale.

**2. The bug was helping the non-cointegrated pairs and hurting the headline.**
Contamination was +284% of composite P&L for XOM/CVX, +133% for SPY/QQQ, +100% for
KO/PEP, and only -3.8% for GOOG/GOOGL. The fix therefore raises the headline pair
and sinks four of the five controls. The paper's central claim comes out stronger,
which is an uncomfortable direction for a bug fix to run and should be stated
plainly rather than presented as a win.

**3. Execution timing is now the widest single specification dimension**, wider
than the orientation band that Section 4.8 is built around. Orientation spans
1.15-1.38; execution spans 0.48-1.38. Section 4.8's framing that orientation is
*the* arbitrary choice will need to accommodate that.

**4. `dspread` in the returned frame.** I made it within-fold to match, so the
first bar of each fold is now NaN in that column rather than a cross-seam
difference. Nothing consumes it; flagging in case something external does.

**5. Could not verify: next-open before 2014.** Not needed, but the ratio series is
only fetched over the study window, so the reconstructed opens inherit the
snapshot's window exactly and cannot be extended without a new fetch.

**6. Could not verify: whether the 13 ratio-guard violations are the *complete*
set of genuine gap days**, or whether some legitimate gaps sit just inside the
(0.90, 1.10) band. The threshold was specified, not derived. GDX at 0.7448 is far
outside; QQQ at 0.8918 is marginal.

**7. Not attempted, per the non-goals list:** point-in-time cointegration gating,
2-of-3 size calibration, adaptive-estimator DSR null, executable placebo, factor
attribution, TLS/Johansen primary estimator, universe expansion. No locked value in
`config.yaml` was changed; the fingerprint assertion in `load_config` still passes.

---

## Verification

- `load_config()` config-hash assertion passes.
- `scripts/run_stage_5.py` 1e-6 reproduction assertion passes for all seven pairs
  under the new code (stage 5 ran to completion; the assertion is upstream of that).
- Stage 4 and stage 5 regenerated; figures 1-4 regenerated.
- DSR rebuilt under both the expanding and the pinned-first orientation.
- Orientation robustness rebuilt.
