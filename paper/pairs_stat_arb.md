---
title: "A cointegration gate is useful but not sufficient: walk-forward evidence from seven U.S.-listed pairs"
author: |
  | Dominic Brandes\vspace{1em}
  | Department of Electrical and Computer Engineering, San Diego State University
  | dbrandes0746@sdsu.edu
date: "This version: November 2026"
geometry: margin=1in
fontsize: 11pt
papersize: letter
linkcolor: black
urlcolor: black
citecolor: black
bibliography: references.bib
csl: chicago-author-date.csl
link-citations: true
---

## Abstract

I test seven U.S.-listed pairs, chosen ex ante on economic grounds, for cointegration in log-price space, and evaluate a z-score mean-reversion strategy on each under walk-forward validation with realistic transaction costs. Two pairs (GOOG/GOOGL and V/MA) classify as cointegrated under a ≥2-of-3 rule across Engle-Granger, Johansen, and Phillips-Ouliaris. The negative-control candidate SPY/QQQ fails all three despite a level correlation of 0.997, because its log-spread trends rather than reverts. The dual-class pair is mixed evidence rather than a clean pass: Phillips-Ouliaris rejects decisively, Engle-Granger does not reject, and Johansen rejects at the pre-specified lag but not at the BIC-selected one.

Across twenty walk-forward folds GOOG/GOOGL earns a composite net Sharpe of 1.38, with a hedge ratio stable to a 0.09 range and 17 of 20 folds positive. No other pair clears two composite standard errors of zero. GOOG/GOOGL clears four, before the adjustments below. What separates the cointegrated pairs from the rest is not the composite but its composition: removing each pair's two best folds costs GOOG/GOOGL a fifth of its result and GLD/GDX five-sixths of its own.

Three things limit the headline. GOOG/GOOGL is the most cost-fragile pair in the sample, breaking even at 15.4 bps round-trip against V/MA's 26.1, because a tight spread leaves little to harvest. The composite deflates to 0.82 against the full 84-cell selection budget, and it moves between 1.15 and 1.38 depending on which leg is the dependent variable in the hedge regression. Most important, 1.38 assumes each trade fills at the closing price that generated the signal. Daily changes in the GOOG/GOOGL spread are negatively autocorrelated (-0.19), and a one-day reversal rule with no parameters and no cointegration fit earns a higher gross Sharpe than the full pipeline under that assumption. With fills at the next open the composite is 0.57, which is not clearly different from zero, and the breakeven falls to 9.6 bps. An event study also finds the entry rule indistinguishable from a buy-any-extreme-z placebo. A cointegration gate is useful but not sufficient: the pair that passes it most clearly does not show an edge that survives realistic fills.

*Keywords:* pairs trading, cointegration, statistical arbitrage, walk-forward validation, transaction costs, deflated Sharpe ratio

*JEL classification:* G11, G12, G14, C32, C58

## 1. Introduction

Pairs trading rests on a single statistical premise: that some linear combination of two asset prices is stationary; that a spread, however the two legs wander individually, reliably pulls back toward a mean [@gatev2006; @avellaneda2010; @krauss2017]. The premise has a precise name, cointegration [@engle1987], and a precise failure mode that is easy to mistake for success. Two assets can move together almost perfectly and still have no stationary spread between them. Correlation measures the co-movement of returns, while cointegration is a property of the price levels, and the two come apart exactly where it matters most for a mean-reversion trade.

That distinction is the subject of this study. I take seven U.S.-listed pairs, fix the universe and the economic rationale for each before running any test, and ask two questions of each: does it genuinely cointegrate, and if it does, does the resulting edge survive realistic costs? The universe is built so the answer can be checked. It contains a pair that must cointegrate on economic grounds---GOOG and GOOGL, two share classes of the same company---and a pair that should not, despite looking like an obvious candidate by correlation: SPY and QQQ, two broad-equity ETFs whose prices track each other almost exactly but whose relationship is overlapping market beta, not a stationary spread. These two anchors are economically motivated controls: a positive-control candidate and a negative-control candidate, chosen so that the pipeline's verdicts can be read against a prior expectation before its verdicts on the ambiguous pairs are trusted. The controls make the design checkable; they do not establish the data-generating process, and Section 4.1 is explicit that the positive control does not in fact classify cleanly.

Where overfitting usually enters, the methodology is deliberately conservative. Cointegration is judged by agreement across three tests with different small-sample properties rather than a single p-value. The signal's parameters are chosen from a small, pre-committed grid. The headline performance number comes from walk-forward validation across the full sample, which re-selects parameters on every fold and therefore stress-tests the selection step itself rather than trusting one lucky split. The cost assumption is stated and then swept, and every capacity figure is reported as a participation limit rather than a profitability claim.

Four findings come out of the study. The cleanest is that correlation is not cointegration, demonstrated directly on the two anchors. The second is that walk-forward dispersion and hedge-ratio stability, not the composite Sharpe, are what separate a stable relationship from a result that is really two lucky regimes. The third, and the one that bears most on whether any of this is tradeable, is that passing a cointegration test is not sufficient: among the pairs that pass the gate, the edge that remains is jointly bounded by how wide the spread is, how often it presents an entry, and how much of each reversion the cost of trading consumes. The fourth came out of checking the headline: most of GOOG/GOOGL's backtested edge depends on filling at the signal's own closing price and largely disappears one bar later (Section 4.10).

## 2. Data and universe

Seven U.S.-listed pairs, committed ex ante in `config.yaml` with the rationale and a-priori expectation for each documented at commit time, make up the universe. Five are nominally tradeable candidates, one is a borderline case selected because it should fail in an instructive way (GLD/\allowbreak GDX), and one is an explicit negative control (SPY/\allowbreak QQQ): both legs are broad equity beta with a correlation that rounds to 1.00 but no cointegrating relationship in log-price space.

Each pair carries a brief economic rationale. GOOG/GOOGL are claims on the same company (GOOGL carries voting rights, GOOG does not), so they must cointegrate if anything does. V/MA share the same payment-network duopoly business model and macro drivers. XOM/CVX share commodity exposure and sector shocks. KO/PEP is the classic textbook pair with common demand drivers. HD/LOW is a home-improvement duopoly tied to the same housing and consumer cycle. GLD/GDX pairs bullion against gold miners, which are levered gold exposure with a leverage that is known to drift. SPY/QQQ overlap heavily, but QQQ is a tech-tilted, higher-beta subset of SPY, so its log-spread should trend with the technology sector's relative weight rather than revert.

| Pair | Category | A-priori expectation |
|---|---|---|
| GOOG / GOOGL | Dual-class shares | Strongest cointegration case |
| V / MA | Payment networks | Likely cointegrated |
| XOM / CVX | Integrated oil | Plausible, regime-dependent |
| KO / PEP | Beverages | Often fails in modern data |
| HD / LOW | Home improvement | Borderline |
| GLD / GDX | Gold vs gold miners | Loose, unstable beta |
| SPY / QQQ | Negative control | Should fail all tests |

Prices cover 2014-04-03 through 2026-05-29, with the start date set by the GOOG/GOOGL C-share creation, the binding constraint on the longest-running pair. Daily adjusted close is fetched from yfinance with Stooq as fallback, cached to parquet with the fetch date stamped into the filename so that re-running on a different day cannot silently change prior results. Forward-fill is not allowed; any internal gap drops the affected bar from the pair via inner-join. The training-test split is 2022-12-31, chosen so that the test window is the 2023-2025 mega-cap trending bull regime and its 2026 continuation. That regime is structurally adverse for mean-reversion strategies, which makes it a deliberately hostile out-of-sample period; the walk-forward analysis later complements it with the more regime-balanced pre-2023 history.

All cointegration testing, the cointegrating regression, the spread, the z-score signal, and per-bar P&L are computed in **log-price space**. The motivation is mechanical. Log-prices put both legs in proportional-return space; residual variance is approximately homoscedastic, so Engle-Granger and Phillips-Ouliaris small-sample power is not distorted; the cointegrating β is an elasticity rather than a scale-dependent dollar ratio; and Δ(log-spread) is a log-return approximation directly commensurable with round-trip costs quoted in basis points. Raw levels are retained only for the raw-price plots in the data section and for dollar capacity scaling in the capacity analysis.

The inner join is taken across all seven pairs, so every pair carries the same 3,057 daily bars over 2014-04-03 to 2026-05-29 with no missing observations, well above the configured minimum of 1,500. The common start is set by GOOGL, which began trading in its current form in April 2014.

## 3. Methodology

### 3.1 Cointegration: a three-test decision rule with diagnostics

A pair is classified as genuinely cointegrated if and only if at least two of three static tests reject the no-cointegration null at the 5% level. The three tests were chosen for their different small-sample power profiles:

1. **Engle-Granger residual ADF** [@engle1987] on both LHS orderings, taking the worse p-value of the two, with p-values from the MacKinnon response surfaces [@mackinnon1996]. EG is the most widely used test; running both orderings removes any dependence on which leg is regressed on.
2. **Johansen trace** [@johansen1991] with rank $r = 0$ as the null, a constant term, one lag of differences; critical values follow @mackinnon1999. The lag was pre-committed at one difference and not tuned; because the finite-sample trace statistic is sensitive to that choice, the robustness of every classification to lags one through four is examined directly in Section 4.1. Johansen has higher power than EG when there are multiple cointegrating relations, not the relevant regime here, but it also handles the bidirectional dependence between the legs without privileging an LHS choice.
3. **Phillips-Ouliaris Z\_t** [@phillips1990] with a constant and no trend, Bartlett kernel, automatic bandwidth. PO is the most direct "is the residual stationary in its own right" test.

No test was run until the ≥ 2-of-3 rule was locked. It is conservative on type-I error, and triangulating over three power profiles means the classification does not hinge on the small-sample quirks of any single test. Disagreements among tests are reported transparently: a "marginal" note appears in the per-pair row of the cointegration table whenever one of the three p-values sits within 0.02 of the 5% threshold, or the Johansen statistic sits within 1 of its 5% critical value.

A rolling 126-bar Engle-Granger p-value is also computed and reported as a stability diagnostic. **It is not a classification gate.** Folding it into the decision rule would require a tunable rejection-fraction threshold, another free parameter, so classification rests on the static tests alone.

The three tests are static full-sample tests, so the classification uses information from the entire 2014-2026 window, including periods that later serve as walk-forward out-of-sample blocks. This does not contaminate any reported P&L: the walk-forward in §3.5 is run on all seven pairs regardless of classification, and no fold's trading depends on the gate. What the full-sample gate does affect is which pair the cross-section foregrounds, a selection effect on the narrative rather than on the returns. The gate is a full-sample structural classification; the walk-forward is a separate procedure evaluated conditionally on it. Section 4.1's rolling 126-bar Engle-Granger diagnostic is the closest thing here to a point-in-time view of the classification, and it is reported for every pair.

### 3.2 Spread construction, hedge ratio, half-life

For each pair classified as cointegrated, the cointegrating vector is fit in the standard cointegration-based pairs framework [@vidyamurthy2004]: OLS regression of one log-leg on the other plus a constant ($y_t = \alpha + \beta x_t + \varepsilon_t$) on the training window only. The chosen α, β are applied unchanged to the test window. The spread is $s_t = y_t - \alpha - \beta x_t$.

Both LHS orderings are fit; the ordering retained is the one whose Engle-Granger residual ADF statistic is more negative; that is, the orientation whose residual is most convincingly stationary. (Selecting on OLS AIC would be invalid here: the two orderings have different dependent variables, so their likelihoods are densities over different random variables and are not on a common scale.) The orientation is selected on every bar available before the evaluation window opens: the full training window in the single split, and an expanding window ending at each fold's out-of-sample boundary in the walk-forward. Neither uses future information. The asymmetry with the 504-day trailing window used for α and β is deliberate: the hedge ratio should track structural drift and therefore wants a recent window, whereas the orientation is a binary choice that should not flip on recent noise and therefore wants all available history. The expanding window matters because the two orderings are frequently a near-tie---on GOOG/GOOGL the median gap across fold training windows is 0.008 of ADF t-statistic---and selecting on a 504-day trailing window alone lets noise flip the orientation mid-run, redefining the spread and forcing an unwind at each flip. Section 4.8 reports what that sensitivity is worth in Sharpe terms; it is not negligible, and it is the reason the criterion is specified this precisely.

Half-life estimation follows the Ornstein-Uhlenbeck convention: fit $\Delta s_t = a + b\,s_{t-1} + \varepsilon_t$ on the training spread and set $\mathrm{HL} = -\ln 2 / \ln(1 + b)$. The raw half-life is reported alongside a value clipped to a $[2, 252]$ trading-day envelope for downstream consumption; the clipping prevents a pathological negative coefficient or a near-zero $b$ from propagating through the signal and P&L modules as a numerical inf. Any pair whose clipped HL hits the ceiling carries a \texttt{clipped\_\allowbreak at\_\allowbreak ceiling} annotation through the rest of the paper.

### 3.3 Signal: a pre-specified 12-cell grid

Entries and exits are governed by a rolling z-score state machine. The z-score is $z_t = (s_t - \mu_{t-1}) / \allowbreak\sigma_{t-1}$, where the rolling moments $\mu_{t-1}$ and $\sigma_{t-1}$ are computed through bar $t-1$ (\texttt{spread.\allowbreak shift(1).\allowbreak rolling(lookback)} in the implementation); the no-look-ahead convention is mechanical at the rolling-window level. The state machine is flat → ±1 → flat: enter long-spread when $z_t < -z_{\text{entry}}$, short-spread when $z_t > +z_{\text{entry}}$, exit on zero-crossing, hard-stop at $|z_t| > z_{\text{stop}}$.

Re-entry after a hard stop is unrestricted, and it is the kind of detail that silently changes turnover. Following a stop-out the machine returns to flat, and the entry condition is evaluated again on the very next bar. If the z-score still exceeds $z_{\text{entry}}$---which it usually does, since the stop fires at $|z| > 3.5$ and entry triggers at 1.5---the position is immediately re-established. A single large excursion can therefore produce repeated entry-and-stop cycles, each paying a round trip. An alternative design would require a zero-crossing to re-arm. The implementation used here does not, so the reported trade counts and cost drag include whatever re-entry churn the sample produced; no separate re-arm parameter was introduced after the fact.

Twelve cells make up the parameter grid: $z_{\text{entry}} \in \{1.5, 2.0, 2.5\}$, $z_{\text{stop}} = 3.5$, and lookback $\in \{15, 20, 30, 40\}$ bars (`entry_z`, `stop_z`, and `lookback` in `config.yaml`). Selection is by net training Sharpe at the 3 bps baseline cost. The grid is intentionally small. A large sweep is where backtest overfitting enters [@bailey2014pseudo], and keeping the selection budget explicit and bounded (7 pairs × 12 cells = 84 candidate configurations across the whole study) makes the multiple-testing exposure straightforward to account for under a deflated-Sharpe correction [@bailey2014deflated].

### 3.4 Backtest convention and round-trip cost accounting

P&L is computed in log-return space because the analysis frame is in log-prices:

\begin{equation}
\pi_t = \text{position}_{t-1} \cdot (s_t - s_{t-1})
\end{equation}

No look-ahead enters by construction: the `shift(1)` on position means the decision made at the close of bar t-1 is realized in bar t's return. Round-trip costs are charged on $|\Delta \text{position}_t|$. A long-to-flat or flat-to-long change of 1 pays half the round-trip in bps; a long-to-short change of 2 pays the full round-trip. Costs in basis points (1e-4) are subtracted from gross log-return-space P&L; the units are commensurable because Δ(log-spread) ≈ log-return. All Sharpe ratios in this paper are computed on daily net P&L. The headline figures are annualized by √252, the convention in the pairs-trading literature, but that factor assumes serially uncorrelated returns, an assumption a mean-reversion strategy has no particular reason to satisfy, since positions are held across multi-day reversion windows. Section 4.3 comes back to this. The small-sample caveats on Sharpe estimation apply with particular force to the per-fold figures, each computed on a 126-bar window.

**The cost denominator is the pair, not the leg.** The 3 bps round-trip baseline is an institutional assumption built from roughly half-spread on each leg of a mega-cap U.S.-listed name plus commission at prime-brokerage rates, for an order small relative to displayed size, but the charge the code applies is all-in across both legs of the pair, not per leg. A flat-to-long move pays 1.5 bps in total and a long-to-short move pays 3 bps in total, and neither is scaled by the hedge ratio, so a reader should not multiply by $(1 + |\beta|)$ to recover the position's gross notional. Readers who prefer a per-leg reading of the same buildup can take the 6 bps row of Table 4 as their baseline instead; the sweep is there so that the cost regime is a dial rather than a claim.

**Execution timing: the fill convention and what it is worth.** A position decided at the close of bar t-1 is assumed filled at that same close, the price that generated the signal. This is the standard vector-backtest convention, and it is optimistic, because the closing print is not known until it is set. The size of the assumption is measurable rather than arguable. Re-running the locked pipeline with fills moved one bar later gives a composite of 0.567 at the next open and 0.483 at the next close, against 1.375 as built. That 0.892 of decay decomposes almost entirely into the overnight gap: 0.808 of it is lost between the same close and the next open, and only 0.084 more between the next open and the next close.

This assumption matters more than any other choice in the paper. Section 4.10 shows that most of the difference between the same-close and next-open results comes from noise in the closing price reversing by the next print, not from an edge a real order could capture. I therefore treat the same-close composite as an upper bound and report the next-open figure next to it. Under next-open fills GOOG/GOOGL's breakeven cost falls from 15.43 bps to 9.63 bps.

Three single-fit constants in the test window are forbidden by construction: α and β are fit on the training window only, σ for the z-score is the trailing-rolling estimate at each bar, and the $(z_{\text{entry}}, \text{lookback})$ cell is selected on training Sharpe with the test window touched exactly once per pair.

### 3.5 Walk-forward (refit-both) over the full history

Walk-forward evaluation covers the entire 2014-2026 sample with a 504-day train block and a 126-day OOS block, stepping 126 days at a time. At each fold boundary both the cointegrating vector (α, β) and the $(z_{\text{entry}}, \text{lookback})$ cell are refit on the trailing 504-day window and applied to the next 126-day OOS window. Twenty folds result.

Refitting **both** the structural fit and the signal cell at every fold is a methodological choice, not just a nod to deployment realism. Walk-forward's distinctive contribution over a single train-test split is that it repeats parameter selection K times, each on a fresh out-of-sample block. The OOS blocks are disjoint by construction, so per-fold OOS Sharpes are close to independent draws. The 504-day training windows, stepping 126 days, overlap by 378 days, so consecutive folds' parameter selections are serially dependent, and the modal-cell stability reported in §4.3 should be read as evidence about a smoothly-varying selection surface rather than as twenty independent votes. A real edge picks a similar cell on most folds and the composite Sharpe holds up; an overfit picks a different "best" each fold and the composite collapses. Fixing the cell at the stage-3 train-window value would remove the selection step from the very procedure whose purpose is to stress-test selection. It would also bake mild look-ahead into the pre-2023 folds: the stage-3 cell was chosen with knowledge of the entire 2014-2022 window, so trading it across those years is not OOS.

Within each fold the rolling z-score is computed on the union of train and OOS bars, so the OOS block inherits warmed-up rolling statistics from the train tail. The position state machine is run on the OOS slice alone, so the position resets to flat at every fold boundary. This matches the refit-both contract: under the new fit, any position held under the old fit is unwound, and re-entry happens under the new spread definition.

That contract has a consequence for how composite P&L must be assembled. Gross P&L is differenced **within** each fold, on that fold's own spread series, and the resulting pieces are concatenated. It is never differenced across a fold boundary, because the spread on either side of a boundary is defined under a different (α, β) and the difference between them is a change of model rather than a move in the market. The first OOS bar of each fold has no predecessor inside its own fold and the book is entered flat, so that bar contributes no gross P&L. Costs are charged on the *concatenated* position series, which is what makes the boundary unwind a real charge: a seam at which one position closes and the opposite opens pays a full round trip. An earlier internal version of the code differenced the concatenated spread across fold boundaries, which books the change in (α, β) at each refit as P&L. That inflated the composites of pairs with unstable hedge ratios (KO/PEP read +0.54 instead of -0.02). It was corrected before the paper was first posted, and `CHANGELOG.md` has the details.

A reproducibility check enforced in the cost-sweep module re-derives the per-fold positions from the saved walk-forward JSON and verifies that the composite net Sharpe at the baseline 3 bps cost matches the stage-4 output to within 1e-6 for all seven pairs. Any drift is a hard failure.

### 3.6 Cost sweep, capacity, signal-decay

For the cost sweep, the locked stage-4 cells are held fixed and composite OOS net Sharpe is re-evaluated at round-trip costs of 0, 2, 4, 6, 8, 10, 12, 15, 20, 25, 30 basis points. The breakeven cost is solved by bisection in the [0, 60] bps interval for the round-trip cost at which composite net Sharpe crosses zero.

Fixing the cells while varying the cost answers the relevant question: how sensitive is the pipeline as built to a wrong cost assumption. The alternative---re-selecting cells at each cost level---would re-optimize against the very variable being stress-tested, produce a smoother and more flattering curve, and answer a different question ("what is the best pipeline at this cost").

Capacity is reported as a participation ceiling. The number is the AUM at which the average per-trade leg notional reaches a 1%-of-ADV participation limit on the smaller of the two legs. In the unit-spread book convention used throughout, holding `position = +1` is long $1 of leg `y` and short $|β| of leg `x` in dollar notional. The hard cap is therefore:

\begin{equation}
K_\text{max} = \min\!\left( 0.01 \cdot \text{ADV}_y,\; \frac{0.01 \cdot \text{ADV}_x}{|\beta|} \right)
\end{equation}

ADV is the 20-day mean of (unadjusted close × volume) at the end of the study window; the constraint binds now, not historically. The median canonical β across walk-forward folds is used so that the capacity number is robust to fold-to-fold β drift.

**Every capacity number in this paper is a participation ceiling.** Above the reported AUM the average trade breaches the 1%-ADV participation limit on the binding leg. That is a statement about market footprint and price-discovery presence, not about whether the edge persists at scale; the two claims are kept separate throughout.

In the spirit of the event-study literature [@mackinlay1997], the signal-decay analysis identifies rule entries as state-machine transitions from flat to non-flat on the *concatenated* walk-forward OOS position series rather than within each fold separately (so a fold seam at which one position closes and the opposite opens contributes turnover but no entry; see Appendix C), and placebo entries as every bar where $|z|$ exceeds the fold's selected $z_{\text{entry}}$, regardless of state. For each event the post-entry trajectory of the sign-aligned z-score is collected over a window of [-10, +60] trading days; the alignment flips the sign so all entries point in the same direction, and the expected post-entry trajectory is toward zero if the spread mean-reverts. The mean curve across events is bracketed by a 95% percentile confidence interval from a stationary block bootstrap [@politis1994], the dependent-data extension of Efron's [-@efron1979] resampling procedure (B = 2000 resamples, geometric mean block length 10 events). A closed-form Ornstein-Uhlenbeck baseline $\mathbb{E}[z(t) \mid z(0)] = z(0) \cdot e^{-t \ln 2 / \mathrm{HL}}$ is overlaid using each event's fold-specific training-window half-life and entry threshold, as the "what a clean mean-reverter would do" reference.

**A pre-specified criterion governs the rule-vs-placebo comparison.** The paper writes "the rule beats placebo" only when the rule and placebo bootstrap CI bands are disjoint over a contiguous post-entry interval of at least five trading days. If the bands overlap, the paper says "indistinguishable at this sample size" and reports the longest separation interval explicitly. The reasoning is set out in Section 4.6.

Because rule entries are by construction a subset of the extreme-z placebo population, the identical criterion is also run against a **disjoint placebo**: the extreme-z bars that are not rule entries. That comparison has no sample overlap, so it cannot inherit the bias-toward-similarity that the nested comparison carries.

## 4. Results

### 4.1 Cointegration classification: correlation is not cointegration

Two of the seven pairs classify as cointegrated under the locked ≥ 2-of-3 rule: GOOG/GOOGL and V/MA. Table 1 gives the static-test triplet and the rolling-EG diagnostic.

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 1.} Cointegration classification, full sample 2014-2026.

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{lrrrlclr}
\toprule
Pair & EG p & Johansen trace & PO p & Tests passing & Decision & Marginal & Rolling EG \% \\
\midrule
GOOG / GOOGL & 0.277 & 16.98 & 0.003 & 2 (Joh, PO) & cointegrated & none & 24.4\% \\
V / MA       & 0.043 & 15.05 & 0.039 & 2 (EG, PO)  & cointegrated & EG, PO, Joh &  5.3\% \\
XOM / CVX    & 0.785 &  5.39 & 0.757 & 0           & not cointegrated      & none &  4.6\% \\
KO / PEP     & 0.940 &  5.49 & 0.954 & 0           & not cointegrated      & none &  3.1\% \\
HD / LOW     & 0.218 & 13.15 & 0.169 & 0           & not cointegrated      & none &  2.6\% \\
GLD / GDX    & 0.090 & 15.47 & 0.064 & 0           & not cointegrated      & PO, Joh &  6.2\% \\
SPY / QQQ    & 0.425 &  8.39 & 0.246 & 0           & not cointegrated (NC) & none &  7.6\% \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

*EG p is the worse of the two LHS orderings. The Johansen trace 5% critical value is 15.49 for all pairs. The Marginal column applies the §3.1 rule mechanically: a test is flagged when its p-value sits within 0.02 of the 5% threshold, or when the Johansen statistic sits within 1 of its critical value. Rolling EG % is the fraction of rolling 126-bar windows in which EG rejects at 5%, a stability diagnostic, not a classification input.*

The Marginal column earns its place on the V/MA row. That pair clears the ≥ 2-of-3 gate on three simultaneously borderline tests---EG at 0.007 from the threshold, PO at 0.011, Johansen at 0.44 below its critical value---which the Decision column alone conceals entirely.

Three observations stand out.

**SPY / QQQ, the negative control, passes correlation and fails cointegration cleanly.** The Pearson correlation of daily log-returns is 0.93 and of levels is 0.997; by any correlation-based screen this pair would look like a candidate. None of the three cointegration tests reject the null at 5%, the EG p-value is 0.425, and the rolling-EG fraction sits at 7.6%, against 24.4% for the dual-class pair, the same order as the other non-cointegrated pairs and nowhere near the positive-control candidate. The log-spread visibly trends. That is the structural reason a constant-β linear combination cannot be stationary: QQQ is a tech-tilted, higher-beta subset of SPY, and the leverage differential drifts with the technology sector's relative weight in the broad market. A pair with correlation effectively 1 fails all three tests, on the same data and the same code that detects cointegration in the dual-class pair.

**GOOG / GOOGL fails Engle-Granger but passes Johansen and Phillips-Ouliaris.** This is a direct demonstration of EG's well-documented low power in finite samples, and it is the strongest argument in the paper for the three-test triangulation. A single-LHS EG run on the dual-class pair would have classified the positive-control candidate as not cointegrated, the false negative the decision rule is designed to avoid. The inference has to be stated carefully, because the obvious version of it is circular: GOOG/GOOGL is not *required* to cointegrate. The two classes carry different voting rights and the premium can drift, which is this section's own explanation for the EG failure. So the EG non-rejection is evidence about EG's finite-sample power only to the extent one is willing to assume the relationship is there, and that assumption is exactly what a control is supposed to test rather than supply. The two more powerful tests catch it: PO at p = 0.003 and Johansen trace at 16.98 against a 5% critical value of 15.49, a clear pass, 1.49 above the threshold. The rolling-EG diagnostic at 24.4% confirms that the pair rejects EG often, just not on the full-sample static run, consistent with a structurally cointegrated relationship whose finite-sample t-statistic happens to fall short of the static critical value. The economic mechanism behind the full-sample miss is the GOOGL voting premium, which drifted over multi-year stretches of the sample (downward over 2017-2019, upward over roughly 2023-2026) rather than oscillating around a fixed level; Alphabet's buyback program is one plausible driver of that drift. A slow trend in a very tight spread depresses the full-sample ADF statistic even when shorter windows reject, which is exactly the pattern the rolling diagnostic shows.

One fragility in this verdict: the Johansen rejection for GOOG/GOOGL holds only at the pre-specified single lag. At two, three, and four lagged differences the trace statistic falls to 14.3, 12.6, and 11.9---all below the 15.49 critical value---and an information criterion (BIC and HQIC both) selects two lags on this pair. At the selected lag GOOG/GOOGL would pass only Phillips-Ouliaris (p = 0.003), one test short of the ≥ 2-of-3 rule. The reported classification therefore rests on the locked lag-1 Johansen pass together with the decisive PO rejection and the 24.4% rolling-EG fraction; it is the one place in the study where the dual-class verdict is genuinely lag-dependent. No other pair's classification changes across lags one through four, so the fragility is confined to this single lag-sensitive Johansen statistic rather than the gate as a whole.

**GLD / GDX and V / MA are the marginal cases, in opposite directions.** V/MA passes EG at p = 0.043 and PO at p = 0.039, both marginal, while Johansen trace sits at 15.05, just below the 15.49 critical value (marginal fail). The pair clears the ≥ 2-of-3 gate, but only barely. GLD/GDX has the opposite profile: EG at p = 0.090 (fail), Johansen trace at 15.47 against 15.49 (marginal fail), PO at p = 0.064 (marginal fail). Zero of three tests reject at the locked 5% level. **GLD/GDX does not classify as cointegrated under the rule, and its strong-looking single-split backtest result later in the paper decomposes into regime luck rather than structural edge**, a clean illustration of why the cointegration gate matters and why a result is not validated by its Sharpe.

Four textbook failures (XOM/CVX, KO/PEP, HD/LOW, GLD/GDX) confirm what a practitioner would expect of modern data on these names: the easy economic-link argument does not translate into a statistically cointegrating log-spread on this window. KO/PEP especially---the pair every introductory pairs-trading text uses---has Engle-Granger and Phillips-Ouliaris p-values of 0.94 and 0.95. The textbook example is not a tradable pair in 2014-2026.

### 4.2 Single-split (in-sample / 2023-2026 OOS) backtest

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 2.} Single-split backtest, all seven pairs. Sharpes are net of the 3 bps baseline round-trip cost.

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{4pt}
\begin{tabular}{lrrrrrrrrr}
\toprule
y \(\sim\) x & \(\beta\) & HL (days) & \(z_{\text{entry}}\) & LB & Entries (tr) & Entries (te) & Train S & Test S & Test AnnRet \\
\midrule
GOOGL\textasciitilde GOOG & 0.976 &  25.7         & 1.5 & 20 & 168 & 66 & 1.38 & \phantom{$-$}0.40 & \phantom{$-$}+0.7\% \\
V\textasciitilde MA       & 0.844 &  60.7         & 1.5 & 20 & 155 & 61 & 0.69 & \phantom{$-$}0.57 & \phantom{$-$}+4.7\% \\
XOM\textasciitilde CVX    & 0.647 & 252 (clipped) & 2.5 & 15 & 109 & 36 & 0.48 & \phantom{$-$}0.14          & \phantom{$-$}+1.4\% \\
PEP\textasciitilde KO     & 1.259 &  45.1         & 1.5 & 30 & 109 & 39 & 0.44 & $-$0.51                    & $-$7.5\%            \\
HD\textasciitilde LOW     & 0.953 & 122.1         & 2.5 & 15 &  99 & 36 & 0.44 & $-$0.60                    & $-$5.0\%            \\
GDX\textasciitilde GLD    & 1.468 &  55.1         & 1.5 & 15 & 157 & 66 & 0.25 & \phantom{$-$}0.98 & +17.1\% \\
QQQ\textasciitilde SPY    & 1.454 & 122.3         & 2.0 & 15 & 144 & 52 & 0.36 & $-$0.34                    & $-$1.9\%            \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

*The LHS ordering is the one selected by the §3.2 criterion on the training window, which is why four rows read in the reverse direction from the pair label. XOM/CVX's half-life is clipped to the 252-day ceiling from a raw OU fit of 408.7 days; the clip is masking a spread that does not revert on this window, not a marginally slow one. The entry columns count trade entries, not observations: the underlying windows hold 2,203 and 854 daily bars for every pair. β is the raw regression coefficient under the retained orientation, so it is not directly comparable to the canonical β under the opposite orientation quoted in §4.8, where 1/1.0241 ≈ 0.976.*

By construction, the single-split OOS window (2023-01-03 → 2026-05-29, 854 bars) is the most adversarial test the universe gets: the 2023-2025 mega-cap trending bull regime and its 2026 continuation, structurally hostile to mean-reversion. Four pairs survive with positive net OOS Sharpe: GLD/GDX at 0.98, V/MA at 0.57, GOOG/GOOGL at 0.40, and XOM/CVX at 0.14. The three that don't include both failure modes the universe was built to contain: the textbook-failed pairs at deep negatives, and SPY/QQQ as the negative control below zero.

Two features of Table 2 are flagged here and resolved in the walk-forward section. First, **the single-split test, taken on its own, would rank GLD/GDX as the strongest tradeable pair in the universe by a wide margin**, a 0.98 net OOS Sharpe on a +17.1% annualized return, more than double GOOG/GOOGL's. Section 4.3 shows this ranking is regime luck rather than structural edge. Second, GOOG/GOOGL's OOS Sharpe of 0.40 is unimpressive on its own, and well below its training Sharpe of 1.38. The walk-forward over the full history gives a fuller picture.

### 4.3 Walk-forward (refit-both): stable relationship vs regime luck

Twenty walk-forward folds per pair, refit-both, full 2014-2026 history. The composite net Sharpe is the natural aggregate, but the shape of the per-fold distribution and the per-fold β stability are the diagnostics that distinguish a stable relationship from regime luck, subject to the qualification developed in §4.7, that β range and β ratio diverge on one pair and the ratio is the one to read where they do. A stable β across folds is independent evidence that the cointegrating relationship is structural; a drifting β is evidence that the composite Sharpe is a mean over different regimes. For GOOG/GOOGL this is a weaker check than it looks, because two share classes of one company should trade at a ratio near 1 whatever the regression does.

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 3.} Walk-forward (refit-both), twenty folds per pair, 2014-2026.

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{4pt}
\begin{tabular}{lcrrrrrrrr}
\toprule
Pair & Coint & \(S_\text{net}\) & AnnRet & \% folds + & S std & \(\beta\)-rng & LHS sw. & BE (bps) & Cap (\$M) \\
\midrule
GOOG / GOOGL   & Yes & \phantom{$-$}1.38 & \phantom{$-$}+2.4\% & 85\% & 1.50 & 0.09  & 2 & 15.4 & 84.2 \\
V / MA         & Yes & \phantom{$-$}0.37 & \phantom{$-$}+2.6\% & 65\% & 1.45 & 0.85  & 1 & 26.1 & 20.7 \\
XOM / CVX      & No  & $-$0.12           & $-$1.5\%            & 45\% & 1.23 & 3.67  & 5 &  0.0 & 14.8 \\
KO / PEP       & No  & $-$0.02           & $-$0.2\%            & 50\% & 1.09 & 14.85 & 6 &  1.0 & 12.1 \\
HD / LOW       & No  & $-$0.33           & $-$4.1\%            & 50\% & 1.20 & 1.28  & 1 &  0.0 & 6.8 \\
GLD / GDX      & No  & \phantom{$-$}0.35 & \phantom{$-$}+5.2\% & 65\% & 1.60 & 0.82  & 1 & 50.9 & 25.0 \\
SPY / QQQ (NC) & No  & $-$0.14           & $-$0.9\%            & 60\% & 1.57 & 0.47  & 5 &  0.0 & 363.7 \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

*$S_\text{net}$ is the composite out-of-sample net Sharpe; S std is the standard deviation of the twenty per-fold Sharpes; β-rng is the max-minus-min canonical hedge ratio across folds; BE is the breakeven round-trip cost. AnnRet is the annualized net return on the composite OOS series at 3 bps. LHS sw. counts how many times the §3.2 orientation criterion switched across the twenty folds. A breakeven of 0.0 means the composite is already at or below zero at zero cost. Cap is the 1%-ADV participation ceiling in millions of dollars, a participation ceiling, not a profitability ceiling (see §4.5). Composite P&L is differenced within each fold (§3.5).*

One calibration makes the dispersion column readable. A Sharpe estimated on a 126-bar window and annualized by √252 has a standard error of approximately √(252/126) ≈ 1.41 under the null of no edge. Every per-fold std in Table 3 sits between 1.09 and 1.60, so that column is, on its own, indistinguishable from noise for all seven pairs. It is reported for completeness, but the discriminating evidence in Table 3 is the β-range column and the shape of the per-fold distribution in Figure 1, not the dispersion statistic. The same calibration applies to the composite: with 2,520 concatenated OOS bars the null standard error is √(252/2520) ≈ 0.32, so only GOOG/GOOGL's 1.38 sits more than two standard errors from zero (at next-open fills it is 0.57, which does not; Section 4.10).

Daily net P&L on the GOOG/GOOGL composite is negatively autocorrelated ($\rho_1$ = -0.161). Section 4.10 traces this to noise in closing prices, so I do not apply an autocorrelation adjustment to the Sharpe. The naive √252 figure is used throughout.

Two figures render the cross-section's argument visually. They compare GOOG/GOOGL against GLD/GDX, the pair whose single-split outperformance the walk-forward exists to decompose.

![Per-fold out-of-sample net Sharpe across the twenty walk-forward folds. Filled bars are positive folds, open bars are negative; the dashed line marks the composite net Sharpe. Panel A: GOOG/GOOGL is positive in 17 of 20 folds with no single carrier; the negative folds are the COVID crash (fold 7) and the recent trending regime (folds 16 and 18). Panel B: GLD/GDX's composite is carried by two folds (fold 9 at +4.28, fold 14 at +3.54); the rest of the distribution is centered roughly on zero with a single severe negative (fold 4 at -2.99).](../figures/stage5/per_fold_sharpe_panel.png){ width=100% }

![Per-fold canonical hedge ratio β. Identical y-axis on both panels; the shaded band spans each panel's min-max range and the dotted line marks β = 1. Panel A: GOOG/GOOGL's β sits in a 0.09-wide band around 1.0 across the full twelve-year history; the hedge ratio stays close to 1, as expected for two share classes of one company. Panel B: GLD/GDX's β drifts from 0.24 to 1.06 across folds, a more than fourfold swing reflecting the regime-dependent leverage of the miners-to-bullion relationship; the composite Sharpe is therefore a mean over fundamentally different relationships.](../figures/stage5/per_fold_beta_panel.png){ width=100% }

GOOG/GOOGL posts the highest composite net Sharpe (1.38) and the tightest β-range (0.09) in the universe, with 17 of 20 folds positive and no single carrier in the positive set. The three negative folds are the COVID crash (fold 7, S = -1.19) and the recent trending regime (folds 16 and 18). Drop the two largest positive folds (5 at +4.30, 11 at +3.43) and the composite over the remaining 18 folds is 1.08; the result survives removing its two best contributions, losing roughly a fifth of its magnitude, which is the quantitative form of the no-single-carrier claim. The 12-cell parameter grid is selected at (1.5, 15) on 45% of folds and clusters in the short-lookback / extreme-entry region rather than pinning to one cell or scattering across the grid; the stage-3 train-window selection of (1.5, 20) sits inside that cluster.

Sharpe is a poor sole summary for a stopped, bounded process, so the composite's distribution and drawdown belong alongside it. On GOOG/GOOGL's 2,520 daily net observations the maximum drawdown is 2.75 percentage points, the worst single day costs 0.94 and the best gains 0.82, and the distribution is close to symmetric (skew +0.22) with fat tails (kurtosis 13.7). The near-symmetry matters: a mean-reversion rule with a hard stop can manufacture a high Sharpe out of many small gains and rare large losses, and that signature would show up as pronounced *negative* skew. It does not appear here, on either cointegrated pair; V/MA drops 13.0 points at worst with skew -0.35, mild by comparison. The annualized volatility of the GOOG/GOOGL composite is 1.8%, so the 2.75-point drawdown is about 1.5 times annual vol, which is what a Sharpe near 1.4 on a bounded process should look like.

GLD/GDX is the structural counterexample. Composite net Sharpe is 0.35, and the per-fold distribution is where it comes apart. Fold 9 (2020-10 → 2021-04) contributes +4.28 of OOS Sharpe, fold 14 (2023-04 → 2023-10) contributes +3.54, and together those two folds carry essentially the whole composite (GLD fell about 9% in each of the two windows): drop them and it falls to 0.06, against GOOG/GOOGL's 1.08 under the same treatment. That is the sharpest single contrast in the cross-section. GOOG/GOOGL retains four-fifths of its composite when its two best folds are removed; GLD/GDX retains a sixth. Per-fold OOS Sharpe std is 1.60, close to GOOG/GOOGL's 1.50, but the distribution behind that std is qualitatively different: two large positives against seven negative folds rather than a broad positive spread. The β-range is 0.82, with the canonical hedge ratio drifting between 0.24 and 1.06 across the twenty folds. The mining-vs-bullion relationship is structurally regime-dependent: a miner's equity is a levered claim on the spread between the gold price and its cost of extraction, so its beta to bullion rises as gold rises relative to costs and compresses as that margin narrows. The cointegration tests caught this in Section 4.1 by failing GLD/GDX on the full sample.

For GOOG/GOOGL, the walk-forward composite (1.38) sits well above the single-split test result (0.40). For V/MA the composite (0.37) sits below the single-split test (0.57). For GLD/GDX the composite (0.35) sits well below the single-split test (0.98).

The non-cointegrated pairs sit at or below zero. KO/PEP posts a composite of -0.02 on a hedge ratio whose canonical value ranges over 14.85, running from -10.88 to +3.98, and whose orientation criterion switched six times across twenty folds. Those are not the diagnostics of a relationship; they are what a regression looks like when there is no stable cointegrating vector to estimate and the fit is chasing noise. XOM/CVX (five switches, β-range 3.67) at -0.12 and SPY/QQQ (five switches) at -0.14 sit in the same category. HD/LOW, with one switch, is a straightforward negative at -0.33.

**The negative control does what a negative control should do.** SPY/QQQ's composite is -0.14, well within one standard error (0.32) of zero, and it stays within about one standard error of zero under every orientation convention in §4.8. That is what a pair with no cointegrating relationship should look like.

### 4.4 Cost sweep and breakeven

![Cost-fragility under fixed stage-4 cells. The cells are held at their walk-forward train-window selection; only the round-trip cost varies in the P&L re-computation, so the curve answers "how fragile is the as-built pipeline to a wrong cost assumption" rather than "what is the optimal pipeline at this cost." Dotted verticals mark each pair's breakeven cost (15.4 and 26.1 bps); the light vertical marks the 3 bps baseline assumption.](../figures/stage5/cost_sweep__cointegrated.png){ width=85% }

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 4.} Composite walk-forward net Sharpe as a function of the assumed round-trip cost, cells held at their as-built stage-4 selection.

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{6pt}
\begin{tabular}{lrr}
\toprule
Cost (bps) & GOOG/GOOGL \(S_\text{net}\) & V/MA \(S_\text{net}\) \\
\midrule
0          & \phantom{$-$}1.69 & \phantom{$-$}0.41 \\
2          & \phantom{$-$}1.48 & \phantom{$-$}0.38 \\
4          & \phantom{$-$}1.27 & \phantom{$-$}0.35 \\
6          & \phantom{$-$}1.05 & \phantom{$-$}0.32 \\
8          & \phantom{$-$}0.83 & \phantom{$-$}0.29 \\
10         & \phantom{$-$}0.61 & \phantom{$-$}0.26 \\
12         & \phantom{$-$}0.38 & \phantom{$-$}0.22 \\
15         & \phantom{$-$}0.05 & \phantom{$-$}0.18 \\
20         & $-$0.51           & \phantom{$-$}0.10 \\
25         & $-$1.04           & \phantom{$-$}0.02 \\
30         & $-$1.56           & $-$0.06 \\
\midrule
Breakeven  & 15.4 bps & 26.1 bps \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

Economically, the cost-fragility contrast is one of the more interesting results in the paper. GOOG/\allowbreak GOOGL has 4.1× the gross Sharpe of V/MA (1.69 vs 0.41) but only 0.59 of V/MA's cost-tolerance: it sheds about 0.108 Sharpe per basis point of round-trip cost, V/MA only 0.016. The structural explanation is direct. GOOG/GOOGL trades a very tight spread---the dual-class pair's log-spread σ on the training residuals is roughly 0.003---so each round-trip captures a small log-return that a fixed-bps cost takes a large bite out of. V/MA's spread is wider and the per-trade log-return larger; the same cost is a smaller fraction of each trade.

The arithmetic behind those breakevens is worth making checkable. Realized gross capture averages 15.43 bps per round trip for GOOG/GOOGL against 26.14 bps for V/MA, over 197 and 111 round trips respectively in the composite OOS series. Those are precisely the two breakeven figures, and necessarily so: the breakeven cost is by construction the round-trip charge that consumes the whole of the average round-trip capture. Under next-open fills the breakevens are 9.6 bps for GOOG/GOOGL and 17.3 bps for V/MA (Section 4.10).

Appendix C reconciles the trade counts and gives the share of round trips that are immediate re-entries after a stop.

The naive estimate a reader might form from a 1.5σ entry on a 0.003 log-spread---roughly 45 bps if every trade reverted fully to the mean---overstates GOOG/GOOGL's realized capture by a factor of three, because trades exit on zero-crossing rather than full reversion, some are stopped out at $|z| > 3.5$ and re-entered immediately (§3.3), and fold boundaries force unwinds.

**The strongest cointegration in the universe is the most cost-fragile.** This is the bridge into the capacity section: high statistical confidence in mean-reversion does not entail an edge that survives realistic costs. The opposite, in fact: the tighter the relationship, the smaller the per-trade mispricing the strategy gets to harvest.

### 4.5 Capacity

Three numbers bound the economics of GOOG/GOOGL under the same-close convention: an $84.2M participation ceiling at 1% of ADV on the binding leg (GOOG), a 15.4 bps breakeven, and a +2.4% annualized net return at 3 bps.

- Liquidity is not the constraint. Combined daily dollar volume across GOOG and GOOGL is about $20B, and the strategy at the ceiling is 0.41% of that.
- The per-dollar edge is thin. At the ceiling, 2.4% is about $2.1M of expected P&L per year. Under next-open fills (Section 4.10) the return is 1.3%, about $1.1M.
- The result is fragile to costs and fills. Moving from 3 to 8 bps costs 40% of the composite (1.38 to 0.83). Moving the fill to the next open costs 59% (1.38 to 0.57).

The capacity figure is a participation ceiling, not a profitability claim. Above it the average trade exceeds 1% of ADV on the binding leg. It says nothing about whether the edge persists at that size.

### 4.6 Signal-decay event study: the rule does not beat extreme-z placebo

Pooled across GOOG/GOOGL and V/MA, the walk-forward identifies 307 rule entries (196 from GOOG/GOOGL, 111 from V/MA) and 911 placebo events over the same OOS windows (523 GOOG/GOOGL, 388 V/MA). The placebo population is every OOS bar where $|z|$ exceeds the fold's selected $z_{\text{entry}}$, regardless of state. This is the most stringent of the three plausible placebos (sign-randomized, pair-permuted, extreme-z-without-rule) because it isolates the contribution of the state machine and exit logic over the choice of entry signal itself. One consequence of that design: rule entries are by construction a subset of the placebo population, so the two samples overlap and their mean curves are mechanically correlated. The overlap biases the comparison toward similarity, so the identical test is also run against a disjoint placebo---the 604 extreme-z bars that are not rule entries---which removes the overlap entirely.

![Pooled signal-decay event study, GOOG/GOOGL + V/MA. Aligned z-score (sign-flipped so all entries point up; 0 = mean-reverted) over a [-10, +60] trading-day window around entry. The solid line is the rule mean with its 95% CI as the shaded band; the dashed line is the placebo mean with its 95% CI as the hatched band (both CIs from a stationary-block bootstrap, B = 2000, mean block length 10 events). The dotted curve is the closed-form OU baseline from each event's fold-specific training-window half-life (the 504-bar fold fit, not the pair-level fit in Table 2), the "clean mean-reverter" reference. The rule and placebo bands overlap throughout the post-entry window.](../figures/stage5/event_study__pooled.png){ width=85% }

Statistically, the rule's mean post-entry trajectory and the placebo's are indistinguishable. The 95% CI bands overlap throughout the [0, +60] post-entry window; the longest contiguous run of CI-band separation is zero days. The maximum absolute gap between the two mean curves is 0.179 in aligned-z units, against a mean entry magnitude of 2.61, well within the per-event variation captured by the bootstrap. The gap pattern (rule slightly more reverted at t+5 and t+10, slightly less at t+20) has a benign mechanical explanation: the placebo population includes consecutive bars deep into the same z excursion, biasing toward bars where reversion has already started, while the rule enters on the first extreme bar of each excursion. The pattern is not separable from noise at this sample size.

The disjoint placebo settles the overlap objection rather than arguing around it. Restricting the comparison population to the 604 extreme-z bars that are *not* rule entries removes the nesting entirely, and the pre-specified criterion returns the same verdict: longest contiguous CI-band separation of zero days, maximum mean-curve gap 0.270 aligned-z units. Because that comparison carries no mechanical correlation between the two samples, the null result is not an artifact of the sample overlap; it survives the test designed to break it.

**The entry rule does not add measurable value over "trade any extreme z" on these pairs.** Both the rule and the placebo revert quickly after entry: half of the entry z-score is gone in 3 to 4 days. That is much faster than the OU baseline, because conditioning on an extreme z selects states that are about to revert. The reversion comes from the spread, not from the timing of the rule.

Applied to the single-pair GOOG/GOOGL panel, the same criterion reaches the same verdict: 196 rule entries vs 523 placebo events, longest CI-band separation again zero days, maximum mean-curve gap 0.181 aligned-z units. GOOG/GOOGL supplies 196 of the 307 pooled rule entries, so the pooled curve is largely this pair's curve.

### 4.7 Cross-section synthesis

Table 3 collects the columns the paper's argument turns on---classification, walk-forward composite, per-fold dispersion, β-range---alongside the two columns that bound the practical economics, breakeven cost and participation ceiling. The two diagnostics that do the analytical work, taken together, are β-range and the shape of the per-fold distribution in Figure 1. Per-fold Sharpe std is reported alongside them but, as §4.3 establishes, every pair's value sits within noise of the 1.41 null, so it discriminates nothing on its own:

- **GOOG / GOOGL** at β-range 0.09 and 85% folds positive: the stable case. Stable hedge ra`\-`{=latex}tio, broad distribution of positive contributors, no single fold carrying the composite. That 17 of 20 folds are positive while the per-fold std is 1.50 says the fold-to-fold variation is in magnitude rather than direction, a claim the distribution's shape supports and the dispersion statistic alone could not. The limiting factors are cost and fill (Sections 4.4 and 4.10).
- **V / MA** at β-range 0.85 and 65% folds positive: the marginal cointegrated case, marginal on all three gate tests simultaneously (§4.1). The hedge ratio drifts more, which is why the walk-forward composite (0.37) sits below the single-split test (0.57): the refitting cannot fully track the structural drift in real time. The compensating attribute is cost-tolerance: a 26.1 bps breakeven, roughly 1.7 times GOOG/GOOGL's, because its wider spread yields more capture per round trip.
- **GLD / GDX** at β-range 0.82 and 65% folds positive: the regime-luck case the cross-section exists to flag. Its composite of 0.35 is indistinguishable from V/MA's 0.37; the standard error is 0.32.

  Two diagnostics do separate them. The first is leave-two-out. Remove GLD/GDX's folds 9 and 14 and its composite falls from 0.35 to 0.06, a loss of five-sixths; remove V/MA's folds 19 and 4 and it falls from 0.37 to 0.14, a loss of three-fifths; remove GOOG/GOOGL's two best and it falls from 1.38 to 1.08, a loss of a fifth. That ordering is the cross-section's cleanest quantitative statement, and it puts the two marginal pairs on opposite sides of a real line rather than a rounding error: GLD/GDX is a composite assembled from two regimes, V/MA is a thin edge spread across many folds. The second is the β ratio rather than the β range. Range points the wrong way---GLD/GDX's 0.82 is marginally tighter than V/MA's 0.85---but β is a scale-free elasticity, and GLD/GDX's runs 0.236 to 1.057, a 4.5-fold swing, against V/MA's 0.745 to 1.594, or 2.1-fold. A 0.8-wide range sitting around 1.0 and one sitting around 0.5 are not the same object, and where range and ratio disagree the ratio is the one to read. Table 3 reports the range because it is the simpler statistic and because for the pairs that matter most the two agree; this is the one row where they do not.

  The rest of the per-fold cross-section stays silent. Both pairs are positive in exactly 13 of 20 folds, and both per-fold standard deviations sit inside the 1.41 null band. The decisive column remains the one fixed before any P&L existed: GLD/GDX rejects on zero of three cointegration tests and V/MA on two. The gate leads and the post-hoc diagnostics corroborate, which is the order the paper's thesis requires.
- **KO / PEP** at β-range 14.85 and six LHS switches is the same warning in a starker form. Its composite is -0.02 on a hedge ratio that ranges from -10.88 to +3.98 across folds. No reading of those β values describes a stable relationship, and the composite agrees.
- The remaining non-cointegrated pairs are XOM/CVX at -0.12, HD/LOW at -0.33, and the SPY/QQQ control at -0.14, none of them as much as 1.1 composite standard errors from zero. None is defensible as a tradeable edge at any cost level the analysis covers.

Put together, the claim is that a cointegration gate is a useful filter for a mean-reversion edge, and that among the pairs that pass the cointegration gate, the edge is jointly bounded by spread magnitude (how much can be harvested per trade), entry frequency (how often that harvest happens), and cost-fragility (the fraction of the harvest that survives execution). GOOG/GOOGL is the highest-statistical-confidence cointegration in the universe and the most cost-fragile; V/MA is the marginal cointegration with the most cost-robust signal. The two are complementary expressions of the same point about what "tradeable" means in modern equity markets.

### 4.8 How much of the headline is a specification choice?

The cointegrating regression has to put one leg on the left-hand side, and for a near-symmetric pair the data barely identifies which. This section reports what that choice is worth, because on the headline pair the answer is larger than it has any right to be.

On GOOG/GOOGL the two orderings are, by every economic measure, the same object. Their Engle-Granger residual ADF statistics differ by a median of 0.008 across the twenty fold training windows. Their per-fold hedge ratios agree to within 0.0064 at the widest fold; on the full sample the orientation-invariant total-least-squares estimate is 1.024 against OLS values of 1.0237 and 1.0241, a gap of 0.0004. Nothing in the spread distinguishes them at any precision an economic argument could use.

The composite net Sharpe nonetheless depends on which is retained: 1.154 against 1.375, a difference of 0.22.

The mechanism is worth naming exactly, because it is not about cointegration at all. The per-fold selection of $(z_{\text{entry}}, \text{lookback})$ is a discrete argmax over a twelve-cell grid, and the training-Sharpe surface has near-ties. A perturbation of the spread on the order of $10^{-3}$ is enough to tip which cell wins. It does so in three of the twenty folds, and one of those three (fold 10) swings 1.88 of OOS Sharpe on its own, from -0.78 under cell (1.5, 40) to +1.10 under cell (2.5, 15). The other seventeen folds are essentially unchanged. A discrete selection step sitting on top of a continuous surface will do this whenever the surface is flat near its maximum, and a twelve-cell grid over a noisy objective is flat near its maximum most of the time.

Table 5 applies the same treatment across the universe.

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 5.} Sensitivity of the walk-forward composite to the LHS orientation convention.

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{6pt}
\begin{tabular}{lrccrr}
\toprule
Pair & \(S\) as built & \(S\) range & breakeven range (bps) & LHS switches & median ADF gap \\
\midrule
GOOG / GOOGL   & \phantom{$-$}1.38 & 1.15 to 1.38    & 14.3 to 15.6 & 2 & 0.008 \\
V / MA         & \phantom{$-$}0.37 & 0.13 to 0.37    & 11.1 to 26.1 & 1 & 0.117 \\
XOM / CVX      & $-$0.12           & $-$0.12 to 0.05 &  0.0 to 11.8 & 5 & 0.439 \\
KO / PEP       & $-$0.02           & $-$0.21 to 0.12 &  0.0 to 14.3 & 6 & 0.308 \\
HD / LOW       & $-$0.33           & $-$0.33 to 0.11 &  0.0 to 15.4 & 1 & 0.292 \\
GLD / GDX      & \phantom{$-$}0.35 & 0.20 to 0.35    & 26.7 to 50.9 & 1 & 0.308 \\
SPY / QQQ (NC) & $-$0.14           & $-$0.18 to $-$0.14 &  0.0 to 0.0 & 5 & 0.165 \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

*Range spans the composite under each LHS ordering held fixed for all twenty folds, together with the as-built expanding-window rule of §3.2: three conventions in all. Median ADF gap is the median absolute difference between the two orderings' Engle-Granger residual ADF statistics across fold training windows, a measure of how weakly the data identifies the orientation. Band widths quoted in the text are computed from the unrounded composites, so they may differ by 0.01 from the difference of the rounded endpoints shown here.*

Two things follow. First, the headline result is directionally robust but not precise: GOOG/GOOGL is positive and materially the largest composite in the universe under every convention, but quoting 1.38 to two decimals implies a precision the procedure does not have. Under same-close fills the composite is better read as 1.2 to 1.4. Second, cost-fragility is more robust than the Sharpe: GOOG/GOOGL's breakeven moves only between 14.3 and 15.6 bps across conventions (orientation conventions; it falls to 9.6 bps under next-open fills), so the conclusion that the pair is cost-fragile does not depend on the specification, even though its exact Sharpe does.

The orientation is not the largest sensitivity. Fill timing moves the composite from 1.38 to 0.57 (Section 4.10). The walk-forward block sizes matter too. Holding everything else fixed, seven train/\allowbreak OOS choices from 252/\allowbreak 126 to 756/\allowbreak 126 give composites between 0.70 and 1.38. All are positive, and the pre-specified 504/126 is tied for the highest (\texttt{results/\allowbreak window\_\allowbreak sensitivity.\allowbreak csv}).

The orientation sensitivity is a limitation of grid-based parameter selection under walk-forward generally, not of this implementation. Any procedure that re-selects a discrete parameter cell on every fold inherits it. Reporting the band is a minimum; a smoother selection rule---cell averaging, or shrinkage toward a prior cell---would reduce the sensitivity, and is the first thing a production version of this pipeline should adopt.

### 4.9 Robustness: the same pipeline on opening prices

The execution-timing sensitivity in §3.4 varies where a trade fills while leaving the fit, the z-score, and the signal on closing prices. A stronger check is to move the entire pipeline onto a different print. Stages 3 through 5 were therefore rebuilt end to end on opening prices---cointegrating fit, spread, rolling z-score, entry and exit rule, and P&L all computed open-to-open---holding the 12-cell grid, the 504/126/126 blocks, the expanding-window orientation rule, the 3 bps cost, and the within-fold differencing of §3.5 exactly as specified. Opening prices are reconstructed as the cached adjusted close times the same-day open-to-close ratio, which is invariant to the vendor's backward adjustment, so the price snapshot underlying every other number in this paper is not disturbed.

**One scope limit governs how the table should be read.** The cointegration gate was *not* re-derived in open space. The classification is the close-based one from §4.1, carried over. What the table shows is therefore the close-based classification applied to open-based trading, not a self-contained open-based study.

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 6.} Walk-forward composite net Sharpe and breakeven cost, close-based (as reported) against a pipeline rebuilt entirely on opening prices.

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{6pt}
\begin{tabular}{lcrrrr}
\toprule
Pair & Coint & \(S\) close & \(S\) open & BE close & BE open \\
\midrule
GOOG / GOOGL   & Yes & \phantom{$-$}1.38 & \phantom{$-$}1.88 & 15.4 & 26.3 \\
V / MA         & Yes & \phantom{$-$}0.37 & \phantom{$-$}0.69 & 26.1 & 45.1 \\
XOM / CVX      & No  & $-$0.12           & $-$0.31           &  0.0 &  0.0 \\
KO / PEP       & No  & $-$0.02           & $-$0.20           &  1.0 &  0.0 \\
HD / LOW       & No  & $-$0.33           & $-$0.23           &  0.0 &  0.0 \\
GLD / GDX      & No  & \phantom{$-$}0.35 & \phantom{$-$}0.13 & 50.9 & 21.8 \\
SPY / QQQ (NC) & No  & $-$0.14           & $-$0.00           &  0.0 &  2.8 \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

*Coint is the close-based classification of §4.1, not re-derived on opens. Both columns use the within-fold differencing of §3.5.*

The ranking survives the change of print: the two cointegrated pairs stay on top, with GOOG/\allowbreak GOOGL at 1.88 and V/MA at 0.69, and both breakevens roughly double. The non-cointegrated column moves in both directions and stays near zero: GLD/GDX falls from 0.35 to 0.13, but HD/LOW rises from -0.33 to -0.23 and SPY/QQQ from -0.14 to essentially zero. That two-directional movement around zero is what the control story predicts and is reported in full here for that reason; featuring only GLD/GDX's decline would be a selective reading of a column whose message is noise.

**The open-based numbers are not adopted, and the reason matters.** Two considerations, in order of weight. First, the close-based convention is the pre-specified one; switching to the print that yields the larger number *after* seeing both is precisely the researcher degree of freedom that §4.8 and the deflated-Sharpe analysis in §5 exist to police, and it would be incoherent to spend two sections policing it and then exercise it. Second, the open is the noisier print, and microstructure bounce at the open induces negative serial correlation that a mean-reversion rule will harvest as alpha it could not capture at scale. That reading is consistent with the composite rule entries of §4.6, which rise from 196 to 207 on GOOG/GOOGL and from 111 to 139 on V/MA on an underlying relationship that has not changed; it is offered as the likely explanation rather than a demonstrated one. Section 4.10 finds the same thing in closing prices at smaller size: the autocorrelation of daily spread changes is -0.30 at the open and -0.19 at the close. The higher open-based numbers are therefore more likely extra noise than extra edge, and I report them as a check on the ranking, not as a result.

### 4.10 What the same-close number measures

The headline composite assumes each trade fills at the same closing price that produced the signal. Section 3.4 shows the composite falls from 1.38 to 0.57 when the fill moves to the next open. This section checks whether that gap is an edge that is hard to capture or noise in the closing price.

I ran two simple rules on the log price ratio of GOOGL to GOOG with the hedge ratio fixed at 1, so there is no regression, no refit and no walk-forward. The first is the paper's own z-score rule at its most common cell (entry 1.5, lookback 15). The second has no parameters: each day, bet against whatever the ratio did that day.

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 7.} GOOG/GOOGL net Sharpe at 3 bps on the 2,520 walk-forward OOS bars, by fill convention. The simple rules use a hedge ratio fixed at 1 and no fitting.

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{6pt}
\begin{tabular}{lrrr}
\toprule
Rule & Same close & Next open & Next close \\
\midrule
Walk-forward pipeline (as built)                    & 1.38 & 0.57 & 0.48 \\
Same z-score rule, cell (1.5, 15), ratio fixed at 1 & 1.57 & 0.69 & 0.45 \\
One-day reversal, ratio fixed at 1 (gross)          & 2.57 & 0.97 & 0.49 \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

*The one-day reversal rule changes position almost every day, so its gross Sharpe is shown; net of 3 bps it is 0.99, -0.31 and -1.11.*

Filled at the same close, the simple z-score rule beats the full pipeline (1.57 against 1.38) and the reversal rule beats it before costs. Both lose most of that one bar later. The one-day reversal rule earns a gross Sharpe of 2.57 at the same close, more than the pipeline's 1.69 gross, without using anything about cointegration. The reason is that daily changes in the ratio are negatively autocorrelated: -0.19 at the close and -0.30 at the open. A move in the closing price tends to partly reverse by the next print. A backtest that trades at the signal close books that reversal as profit, but an order placed after seeing the close would not get that price. Consistent with this, about half (51.9%) of the gross P&L on the first day a GOOG/GOOGL position is held arrives between the close and the next open. V/MA shows the same pattern at smaller size: autocorrelation of -0.07, and the one-day reversal rule earns 0.84 gross at the same close and -0.09 at the next open. V/MA's own composite falls from 0.37 to 0.21 at the next open, with a breakeven of 17.3 bps.

So I read 1.38 as an upper bound. The figure closer to tradeable is the next-open one: 0.57 at 3 bps, with a breakeven of 9.6 bps. That is less than two standard errors from zero (the standard error is 0.32) before any adjustment for parameter selection. Daily data cannot say how much of the difference an order in the closing auction could recover. That needs intraday prices.

It also means the hedge-ratio regression adds little for this pair. Two share classes of one company should trade at a ratio near 1, and fixing it at 1 gives the same result.

## 5. Limitations

Several restrictions on the scope of this study are recorded explicitly so that readers can judge what the results do and do not establish.

**Single asset class, single sample.** The seven pairs are U.S.-listed instruments on a 2014-2026 sample: four of the fourteen legs are ETFs (SPY, QQQ, GLD, GDX), so the universe is not purely equity. The cointegration-not-correlation conclusion is well supported on this universe by the explicit anchors (GOOG/GOOGL and SPY/QQQ), but the cross-section's economic conclusions about cost-fragility, capacity, and breakeven are conditional on the cost structure and liquidity profile of this market segment in this decade. A pre-decimalization sample, a different asset class, or a less liquid corner of the same market would produce different breakeven and capacity numbers.

**Small N of walk-forward folds.** Twenty folds is the maximum the 2014-2026 sample supports under the configured 504/126 block sizes; per-fold Sharpe distributions are evaluated at this N, and the per-fold std numbers should be read in that context. The cross-section's per-fold dispersion column inherits the small-N limitation of the walk-forward.

**The event-study bootstrap resamples events, not calendar time.** Blocks are drawn over consecutive *events* rather than blocks of calendar time. Because entries cluster, several may fall within a single spread excursion, with heavily overlapping [-10, +60] windows, while others are separated by months, a fixed block length in event space corresponds to a variable and sometimes small amount of calendar-time dependence. Post-entry windows also overlap substantially, so the effective sample size is materially below the nominal 307 rule entries. Both effects mean the reported confidence bands are, if anything, narrower than a fully rigorous treatment would produce. That cuts against the indistinguishability finding rather than toward it: wider bands would only reinforce the overlap the null result already reports.

**Prices are backward-adjusted, which is not what a trader saw at the time.** The series are yfinance adjusted close, and a backward-adjusted series is restated at every distribution: $\log(\text{adj}) = \log(\text{raw}) + \log(F)$, where the cumulative factor $F$ is a backward step function that changes whenever a dividend is paid. The historical levels in the snapshot are therefore not the levels that were observable on those dates, which is the standard objection to any yfinance backtest. Its effect on a *spread* is narrower than on a single series, because the factor enters the spread as $\log(F_y) - \beta \log(F_x)$ and cancels when the two legs distribute identically. GOOG and GOOGL pay the same dividend on the same dates, so for the headline pair the factors are equal and the residual contamination is $(1 - \beta)\log(F)$ with β within 0.05 of 1 across all twenty folds, and Alphabet paid no dividend at all before 2024. The exposure is real but negligible exactly where the paper's claims are strongest. It is largest for GLD/GDX, where GDX distributes and GLD does not, so no cancellation occurs, and that pair fails the cointegration gate and carries no claim in this study. A production version would work from unadjusted prices with an explicit dividend and corporate-action ledger rather than inheriting the vendor's restatements.

**Cost is treated as constant.** The cost sweep varies the round-trip rate but treats the rate as time-invariant within each evaluation. Real cost structure includes a time-of-day component, an order-size component, and a volatility-state component. The model also excludes short-borrow fees and financing costs on the short leg; for the general-collateral mega-caps in this universe borrow is negligible, but the omission would matter materially in a hard-to-borrow universe. The breakeven number is the right-magnitude answer for the platform-average cost regime; it is not a forecast of the cost for a specific execution venue or order type.

**The 1%-ADV cap is not a market impact model.** Section 4.5 covers the labeling distinction; the limitation here is that even the participation discipline is a static cap. A more rigorous treatment would model temporary and permanent impact separately and solve for the AUM at which marginal impact equals marginal alpha. That treatment would depend on impact-coefficient calibration that is itself stylized; the participation-cap framing is more defensible at the cost of less precision.

**The pre-specified universe was committed before testing began, but it was selected from a finite set of obvious candidates.** This is the standard researcher-degrees-of-freedom concern. The mitigations: the universe is documented in `config.yaml` with an audit trail, both anchors (a positive-control candidate and a negative-control candidate) are present and behave broadly as expected, and no pair has been added, removed, or relabeled mid-study. The selection budget is explicit at 7 pairs × 12 cells = 84 cells. Deflating GOOG/GOOGL's composite walk-forward net Sharpe against this full budget---the deflated Sharpe ratio of @bailey2014deflated---gives DSR = 0.82. The trial variance is estimated from 84 walk-forward composites, one per (pair, cell), each computed with that cell held fixed across all twenty folds. That matters: the statistic being deflated is the walk-forward composite, so the trial distribution has to be the distribution of that same estimator. At 0.82 the composite sits below the conventional 0.95 bar: charged the whole-study budget it is better read as suggestive than as established, and it clears 0.95 (DSR = 1.00) only when the budget is scoped to the twelve cells that actually competed for this pair. The two acknowledged weaknesses of the study also compose. Deflating at the floor of the Section 4.8 specification band rather than at the headline---candidate Sharpe 1.15 instead of 1.38, with the trial distribution rebuilt under the same pinned orientation---gives DSR = 0.69 against the full budget and 0.97 against the per-pair budget. Selection risk and specification risk are therefore not independent taxes on the same result: charging both at once leaves the whole-study figure below 0.7, and leaves the per-pair figure clearing the 0.95 bar only narrowly. Table 8 reports all four variants side by side. All four deflate the same-close composite. The next-open composite of 0.57 is not deflated here; it is already within two standard errors of zero before any selection adjustment (Section 4.10).

\begin{center}
\begin{minipage}{\linewidth}
\centering
\textbf{Table 8.} Deflated Sharpe ratio for GOOG/GOOGL's same-close composite. \(T\) = 2,520 daily observations. The as-built candidate has skew \(+0.22\) and raw kurtosis 13.71. \(\sqrt{V}\) and \(SR_0\) are annualized by \(\sqrt{252}\).

\vspace{0.4em}
{\footnotesize
\setlength{\tabcolsep}{6pt}
\begin{tabular}{llrrr}
\toprule
Trial distribution & \(K\) & \(\sqrt{V}\) (ann) & \(SR_0\) (ann) & DSR \\
\midrule
\multicolumn{5}{l}{\emph{Candidate: as-built composite, annualized Sharpe 1.38}} \\
84 walk-forward composites (reported)         & 84 & 0.44 & 1.08 & 0.82 \\
12 walk-forward composites, this pair only    & 12 & 0.31 & 0.51 & 1.00 \\
\midrule
\multicolumn{5}{l}{\emph{Candidate: band floor of Section 4.8, annualized Sharpe 1.15}} \\
84 walk-forward composites, pinned orientation & 84 & 0.40 & 1.00 & 0.69 \\
12 walk-forward composites, this pair only     & 12 & 0.32 & 0.53 & 0.97 \\
\bottomrule
\end{tabular}
}
\end{minipage}
\end{center}

*Within each block both rows use walk-forward composites as the trial distribution and differ only in the size of the selection budget.*

The same correction is decisive for the rest of the cross-section. Charged the same 84-cell budget, every other pair deflates essentially to zero---the second cointegrated pair V/MA to 0.012, GLD/\allowbreak GDX to 0.010, and the remaining four below 0.001---so under same-close fills GOOG/\allowbreak GOOGL is the only pair that is not deflated to zero.

**The signal-decay event study is pooled across two pairs.** Pooling brought entry counts up to a level where the bootstrap CIs are informative, at the cost of washing out any pair-specific signal-decay structure. The pooling matters only for bootstrap power, not for the rule-vs-placebo conclusion: the single-pair GOOG/GOOGL panel reaches the same indistinguishable-from-placebo verdict.

**Six extensions are named here rather than attempted, because each is a study in its own right.** Naming a gap is not the same as closing it, and a reader should treat each of these as open.

- *The cointegration gate is applied on the full sample.* Section 3.1 explains why no reported P&L is contaminated by this, but the point stands that the classification is not one a researcher could have held at each fold. A point-in-time gate, re-derived on each fold's training window, is the natural extension and answers a question this design cannot.
- *The size of the ≥ 2-of-3 rule is not calibrated.* The three tests run on the same two series and are therefore highly dependent, so the joint rejection rate under the null is not the product of three marginal rates and is not known here. Establishing it would take a simulation study on data generated to match these pairs' second moments.
- *The DSR trial distribution is not a distribution of the candidate's own estimator.* The 84 trials each hold one cell fixed across all twenty folds, whereas the candidate re-selects a cell on every fold. Those are not the same statistic, so the deflation in Table 8 is approximate in a direction that is not signed.
- *Overlapping confidence bands are not a formal test of curve equality.* Section 4.6's criterion---bands failing to overlap over five contiguous days---is a pre-specified decision rule, not a hypothesis test with a calibrated size; bootstrapping the difference between the two mean curves directly would be the formal version. Separately, the event study compares the decay of the z-score, which is not the net P&L of an executable placebo strategy.
- *Unit-root tests on the individual legs are assumed rather than reported.* Cointegration presumes both legs are I(1). That is overwhelmingly likely for log prices of these fourteen instruments and is not tested here, so the classification inherits an unverified premise.
- *Fill timing is bounded, not measured.* Section 4.10 gives a same-close upper bound and a next-open figure. Where a closing-auction order would land between them needs intraday data.

## 6. Conclusion

The cointegration gate did the work it was built to do. Of seven economically motivated pairs, two passed (GOOG/GOOGL and V/MA), and the two economically motivated controls behaved broadly as expected: the dual-class pair was caught despite failing the most commonly cited test, and the broad-equity control was rejected despite a level correlation of 0.997. Every pair the gate failed either looked implausible from the start or, in the case of GLD/GDX, produced a strong-looking backtest that the walk-forward then exposed as regime luck. A result is not validated by its Sharpe; it is validated by whether the relationship underneath it holds across regimes, and the per-fold hedge ratio is where that shows up, stable at a 0.09 range for GOOG/GOOGL and drifting more than fourfold for GLD/GDX, though for two share classes of one company a ratio near 1 is expected in any case.

What survives the gate is thin, and thinner than the headline suggests. GOOG/GOOGL earns a 1.38 composite net Sharpe across twenty folds if trades fill at the signal close, and breaks even at 15.4 bps. With fills at the next open it earns 0.57 and breaks even at 9.6 bps. Section 4.10 shows the difference is mostly closing-price noise that a parameter-free reversal rule also captures. On this evidence I cannot claim a tradeable edge for the pair.

Four qualifiers belong with these headlines, all developed above. The dual-class classification is mixed evidence rather than a clean pass: one strong rejection from Phillips-Ouliaris, one non-rejection from Engle-Granger, and a Johansen result that holds at the pre-specified lag and fails at the BIC-selected one. The composite deflates to 0.82 against the full 84-cell budget, clearing the 0.95 bar only on the narrower per-pair budget (1.00). It is specification-sensitive, ranging from 1.15 to 1.38 depending on which leg is placed on the left-hand side of a regression the data cannot distinguish; charging that together with the selection budget---deflating at the bottom of the band against a trial distribution rebuilt under the same convention---leaves 0.69 on the full budget and 0.97 on the per-pair one. And it depends on the fill, as above: 0.57 at the next open and 0.48 at the next close.

The study is equally explicit about what it could not show. The entry rule, tested against a placebo that simply buys any extreme z, added no measurable value: the spread's own reversion does the work, and the timing logic decides only when to start watching.

A production version would extend in the directions the limitations name: a point-in-time universe drawn from index constituents as of each trade date rather than a fixed list chosen with hindsight, a separable temporary-and-permanent impact model in place of the participation cap, a smoother parameter-selection rule in place of the per-fold discrete argmax that §4.8 measures, and intraday data to replace the assumed fill with an observed one, which §4.10 identifies as the largest single source of specification uncertainty in the study. None of those would change the central finding, which is methodological before it is empirical: a cointegration gate gets a pair into the game, and cost and fill decide whether it can play.

## Version note

v1.1, November 2026. Adds Section 4.10 on closing-price noise and reads the same-close composite as an upper bound. Corrects several descriptive errors. Shortens Sections 4.5 to 4.8 and the appendices, and removes a section describing an internal accounting bug that was fixed before the paper was first posted. No configured value and no previously reported table value changed. The July 2026 version is superseded.

## Disclosure

**Use of AI assistance.** I used large language model assistance (Anthropic's Claude) in producing this work: implementing and reviewing Python for the pipeline, editorial revision of the manu`\-`{=latex}script, and adversarial review of the analysis, which surfaced several errors that are corrected in the text. Every methodological choice this study turns on was fixed by me before any test was run and is recorded in `config.yaml`, with the single subsequent amendment logged in `CHANGELOG.md`: the universe, the ≥ 2-of-3 decision rule, the 12-cell parameter grid, the walk-forward design, and the cost and capacity conventions. Every number reported here is produced by the committed code from the committed data snapshot and is reproducible by the procedure in Appendix A. Responsibility for the content, including any remaining errors, is mine.

**Funding and competing interests.** This research received no external funding. I hold no position in any security named in this study and have no financial interest in the results.

## References

::: {#refs}
:::

---

## Appendix A: Reproducibility

### Data availability

The repository is at <https://github.com/Dominicrbrandes/pairs-stat-arb>. Every number and figure in this paper is regenerable from the commit tagged `v1.1-paper` on the `master` branch.

This study runs end-to-end from the cached parquet snapshot stamped `2026-05-30`:

```
data/raw/<ticker>__<fetch_date>.parquet       14 files
data/volumes/<ticker>__<fetch_date>.parquet   14 files
data/raw_open/<ticker>__<fetch_date>.parquet  14 files
```

All randomness is seeded from `project.master_seed = 42` in `config.yaml`; the stationary block bootstrap uses a `seed_offset = 1` (so its effective seed is 43).

### Code availability

To rebuild every result and figure from source:

```bash
# data, cointegration, spread, walk-forward, costs, figures
python scripts/run_stages_1_2.py
python scripts/run_stage_3.py
python scripts/run_stage_4.py
python scripts/run_stage_5.py
python scripts/make_paper_figures.py

# deflated Sharpe (Sec 5): as built, then at the band floor
python scripts/compute_dsr.py
python scripts/compute_dsr.py --orientation first

# robustness (Sec 4.1 lag, Sec 4.8 LHS orientation)
python scripts/robustness_johansen_lag.py
python scripts/robustness_orientation.py

# execution and open-based rebuild (Sec 3.4, 4.9, 4.10)
python scripts/fetch_open_ratio.py
python scripts/execution_conventions.py
python scripts/gap_session_decomposition.py
python scripts/open_based_pipeline.py

# closing-price noise and window sensitivity (Sec 4.8, 4.10)
python scripts/closing_print_noise.py
python scripts/window_sensitivity.py
```

`fetch_open_ratio.py` is the only script that touches the network; the three that follow it and `closing_print_noise.py` depend on its output. The remaining stages run entirely from the committed snapshot.

Each script writes serialized results to `results/` and figures to `figures/`.

`run_stage_5.py` asserts that the walk-forward composites recomputed from saved per-fold results match stage 4 to 1e-6, and `load_config` asserts a fingerprint of the methodology-bearing config values. Any change to a locked value is recorded in `CHANGELOG.md`.

### Computational environment

The load-bearing versions are Python 3.13.3, `pandas` 2.3.3, `numpy` 2.4.6, `statsmodels` 0.14.6, and `scipy` 1.17.1; the cointegration tests and the OU fits are the components most likely to drift across `statsmodels` releases, so that pin is the one to respect if the results are being reproduced. The PDF is built from the markdown source by `scripts/render_paper.py` (pandoc and xelatex).

## Appendix B: Per-fold walk-forward details

The pipeline writes per-fold tables for all seven pairs to \texttt{results/\allowbreak stage4\_\allowbreak walkforward/\allowbreak <pair>\_\_\allowbreak folds.\allowbreak csv}, and the results directory is not committed. Each row records the fold's training window, OOS window, refit cointegrating vector (α, β, residual σ, canonical β), training-window OU half-life, selected (entry_z, lookback), training-net Sharpe, OOS gross/net Sharpe, OOS annualized return, OOS entry count, and OOS bar count. The summary JSON at \texttt{results/\allowbreak stage4\_\allowbreak walkforward.\allowbreak json} mirrors this content in nested form. The single-split detail tables for stage 3 live at \texttt{results/\allowbreak stage3\_\allowbreak singlesplit.\allowbreak csv} and \texttt{results/\allowbreak stage3\_\allowbreak param\_\allowbreak surfaces/\allowbreak <pair>.\allowbreak csv} (the full 12-cell grid surface per pair).

## Appendix C: Trade-count reconciliation and re-entry churn

| Count | GOOG/GOOGL | V/MA |
|---|---|---|
| Per-fold entries | 198 | 112 |
| Composite rule entries | 196 | 111 |
| Composite round trips | 197 | 111 |

*Per-fold entries* are counted inside each fold's own state series. *Composite rule entries* are flat-to-non-flat transitions on the concatenated out-of-sample series, the convention stated in §3.6. *Composite round trips* count turnover on the same concatenated series.

Immediate re-entry after a hard stop (§3.3) accounts for 13 of GOOG/GOOGL's 197 round trips (6.6%) and 18 of V/MA's 111 (16.2%).
