# Changelog

`config.yaml` asks that no value be changed after the first run without recording
the change here. This file is that record.

## 2026-11-09 - v1.1: the same-close headline is an upper bound; cuts and factual fixes

**No `config.yaml` value changed, stages 1 to 5 were not re-run, and no result
moved.** No number in Tables 1 to 5 or the open-price table changed and no figure
was regenerated. Two new scripts add numbers the paper did not report before.

**Substantive correction (Part 2 of the edit brief).** Section 3.4 argued that the
same-close fill convention is "defensible" because the edge arrives overnight,
after the fill. That statement is withdrawn. Daily changes in the GOOG/GOOGL log
ratio are negatively autocorrelated (-0.19 at the close, -0.30 at the open), so
part of each closing price is noise that reverses by the next print, and a
backtest that fills at the signal's own close books that reversal as profit.
`scripts/closing_print_noise.py` shows it with the hedge ratio fixed at 1 and no
fitting: the paper's z-score rule at cell (1.5, 15) earns a net Sharpe of
1.57 / 0.69 / 0.45 at same close / next open / next close, against the
pipeline's 1.38 / 0.57 / 0.48, and a parameter-free one-day reversal rule earns
2.57 / 0.97 / 0.49 gross. V/MA shows the same pattern at smaller size. The paper
now reads 1.38 as an upper bound and reports the next-open figure (0.57,
breakeven 9.6 bps) next to it. This is the new Section 4.10 and Table 7; the
abstract, Section 1, Section 3.4, Section 4.4 and the conclusion were changed to
match. The autocorrelation-adjusted Sharpe of Section 4.3 (1.65) is no longer
reported, because the negative autocorrelation it rewarded is the same noise.

`scripts/window_sensitivity.py` reports the GOOG/GOOGL composite under seven
walk-forward block sizes (Section 4.8): 0.70 to 1.38, all positive.

**Factual fixes (Part 3).**

- Johansen critical values are MacKinnon, Haug and Michelis (1999), which is
  what statsmodels' `coint_johansen` uses, not Osterwald-Lenum (1992).
- KO/PEP: Johansen reports a statistic, not a p-value, so "three-of-three
  p-values above 0.94" became the two p-values that exist (0.94 and 0.95).
- GLD/GDX's two carrying folds were described as gold-bull windows. GLD fell
  about 9% in each.
- Fold 9 of GLD/GDX is not inside the stage-3 test window; only fold 14 is. The
  sentence that said both were is deleted.
- Visa was described as the smaller market cap of the V/MA duopoly. It has been
  the larger company throughout the sample.
- Four of the fourteen legs are ETFs (SPY, QQQ, GLD, GDX), not three plus one.
- The paper claimed genuine cointegration is necessary for a tradeable edge
  (Section 4.7). It does not show necessity; the claim is now that the gate is a
  useful filter.
- A stable hedge ratio on GOOG/GOOGL is a weaker check than the text implied,
  since two share classes of one company should trade near a ratio of 1.
- Appendix B said the per-fold tables "are at" `results/`. That directory is
  git-ignored, so they are written there when the pipeline is run.

**Cuts (Part 4).** The section on the fold-seam accounting error and its table
are removed, with a short account kept in Section 3.5; the bug was fixed before
the first public version, and the 2026-07 entries below remain the record of
it. Sections 4.5 to 4.8, the open-price section, the DSR table and its caption,
and Appendices A and C are shortened. The legacy stage-3 row is dropped from the
DSR table (`compute_dsr.py` still prints it). Snapshot hashes, the pandoc
command and the font notes moved from Appendix A to `README.md`.

**Numbering.** The open-price section is now 4.9 and the new section is 4.10.
Tables read 1 to 8 in order of appearance: the open-price table is Table 6, the
closing-price noise table is Table 7 and the DSR table is Table 8.

**Code and docs, no behaviour change.** `compute_dsr.py` and `select_ordering`
docstrings corrected; `README.md` layout and rebuild list brought in line with
the files that exist.

**Consistency pass (round 2).** Thirty wording edits bring the rest of the paper
in line with Section 4.10: "structural" claims about GOOG/GOOGL become "stable",
the introduction no longer says cointegration is necessary, the open-price
results are reported as a check on the ranking rather than as corroboration, and
the conclusion counts four qualifiers. V/MA's next-open composite (0.21,
breakeven 17.3 bps) is now stated in Section 4.10. Still no `config.yaml` value
changed and no result moved. In code: the two new scripts create `results/`
before writing, `compute_dsr.py` drops the legacy stage-3 comparison, the unused
`lo2002` reference is removed, and the README no longer describes a fallback
renderer that does not exist.

## 2026-07-29 - Trade-count reconciliation, §4.9 cross-section, two table notes

**No `config.yaml` value changed, no pipeline was re-run, and no result moved.**
All three corrections are to labels and claims, resolved against existing
artifacts.

**Trade counts.** The paper reported 198/112, 197/111 and 196/111 for the two
cointegrated pairs without saying they count different populations, and §4.10
used 197 and 112 as entry-count baselines when neither is an entry count. The
three populations, confirmed against `stage4_walkforward/<pair>__folds.csv`,
`stage4_walkforward.csv`, `gap_session_rule__<pair>.csv` and
`stage5/event_study.json`:

    per-fold entries          198 / 112   each fold's own state series
    composite rule entries    196 / 111   flat-to-non-flat, concatenated
    composite round trips     197 / 111   turnover units, concatenated

Per-fold entry sums match the gap/session row counts exactly (198 and 112, no
tail drops in any fold). The event study reports 196 and 111, and `entries_open`
in `open_based_pipeline.csv` uses the same composite estimator, so 196 and 111
are the correct baselines for the open-based rise to 207 and 139. Appendix C
was extended from the 197-versus-196 case to all three counts; §3.4 and §4.10
now name the population they cite.

The previous Appendix C sentence "Counted per fold, that seam would register as
an entry in fold 7 and the two figures would agree at 197" was wrong: per-fold
counting gives 198, not 197. Removed.

**§4.9 cross-section.** Dropped "very nearly sorted by β-range with it."
Spearman ρ between absolute contamination and β range is 0.54 (p = 0.22, n = 7),
and SPY/QQQ contradicts it directly, holding the second tightest β range in the
universe at 0.47 alongside the second largest contamination at 133%. The
mechanism and the two extremes are retained, SPY/QQQ is named as the pair where
orientation switching rather than β drift does the work, and the same n = 7
power caveat §4.8 carries is now stated here. The two sections hold the same
standard.

**Table notes.** Table 5's note claimed band widths are quoted to one decimal;
the text quotes two. It now states that text band widths are computed from
unrounded composites and may differ from the rounded endpoints by 0.01, which
is the case on three of seven pairs. Table 7's note said rows are ordered by
contamination; they ascend by absolute contamination (4, 9, 38, 68, 100, 133,
284) and the note now says so. Table 7's β-rng is described as the candidate
explanatory variable rather than the explanatory variable, consistent with §4.9.

## 2026-07-28 - Margin overruns and a verification check that could not see them

**No `config.yaml` value changed and no result moved.** Typesetting and one prose
count; recorded here because it corrects a false claim made in the v1.0-paper
release notes.

**The defect.** Six pages carried content past the right text edge. Page 33 was
the worst at 76.8pt, far enough that the trailing comments in the Appendix A
command block ran off the physical page and were clipped mid-word. Also affected:
Table 1 (29.7pt), the Table 2 header (5.9pt), the reproduction file listing
(40.0pt), and two Appendix paragraphs whose long repository paths could not be
broken (48.0pt and 40.1pt).

**Why nothing caught it.** The v1.0-paper verification reported "no overfull
boxes". Nothing had been measured. `scripts/render_paper.py` drives xelatex
through pandoc, which runs the engine in a temp directory and deletes it, so the
`.log` holding every `Overfull \hbox` warning was gone before any check could
read it. The check inspected the finished PDF for things it expected to find and
passed.

**The fix.** `scripts/check_pdf.py` rebuilds via pandoc to standalone `.tex`,
runs xelatex into `build/`, and parses the retained log. Two independent
detectors: the log parse for TeX's own overrun measurement, and a geometric scan
of every text span against the text block for the true page number. Neither
subsumes the other; the log reported boxes the PDF renders invisibly, and the
scan caught the 76.8pt clipping the log never reported at all. The build is
validated as non-empty first, because every detector reports clean on a
zero-page PDF.

Content changes: column padding reduced on Tables 1 and 2 (no font scaling);
Appendix A command comments regrouped above each stage rather than trailing;
`\allowbreak` inserted at path separators in five inline repository paths. One
prose correction found while editing: Appendix A said "the four that follow it
depend on its output" where three scripts follow `fetch_open_ratio.py`.

**Em-dash density.** Reduced from 146 to 68, a 53% cut. The source contains no
literal em-dash characters; it uses the markdown `---` form, which pandoc's smart
typography converts on render, so the density was invisible to any check reading
the source. Rule applied: keep the dash where it does genuine parenthetical work,
particularly where the aside carries its own commas and a comma pair would be
ambiguous; convert the rest per sentence to a comma, semicolon, colon, or
parentheses. No mechanical replacement was used, since a blind substitution
produces comma splices and spaced hyphens.

Two overruns remain, both below the 5pt failure threshold and both deliberate:
a 4.9pt prose line on page 22, and the 64-character SHA-256 digests at 3.1pt,
which are left unbroken so they stay copy-pastable as single tokens.

## 2026-07-27 - Fold-seam P&L accounting (BUG FIX, not a methodology amendment)

**No `config.yaml` value changed.** This entry is recorded here anyway because it
moves every composite number in the paper, and the file is the place a reader
looks for that. `LOCKED_CONFIG_SHA256` is untouched and the fingerprint assertion
still passes.

**The defect.** Composite walk-forward gross P&L was computed as
`concat_position.shift(1) * concat_spread.diff()`. At the first out-of-sample bar
of each fold, `.diff()` subtracted a spread defined under fold k's (alpha, beta)
from a spread defined under fold k+1's. Where the prior fold ended with an open
position, that booked a model-redefinition jump as P&L. It has no tradable
counterpart, and no reproducibility assertion in the pipeline could detect it:
every check recomputed the same quantity the same wrong way.

**The fix.** `src/backtest.compute_composite_pnl` differences gross inside each
fold and concatenates the pieces. Cost accounting is deliberately unchanged and
still charges `|delta position|` over the concatenated position series, so the
boundary unwind is still paid and a seam that closes one position and opens the
opposite still pays a full round trip. Total cost per pair is identical to 1e-15
before and after.

**Why this is a bug fix and not a change of method.** Section 3.5 already states
that the position resets to flat at every fold boundary and any position held
under the old fit is unwound. The old code did not implement that; the new code
does. The alternative of holding across the seam under the old fit and rebalancing
the hedge would have been a genuine methodology change, and it is reported in the
paper as a disclosed sensitivity rather than adopted.

**Resulting movement in composite out-of-sample net Sharpe:**

| Pair | Before | After |
|---|---|---|
| GOOG/GOOGL | 1.2853 | 1.3752 |
| V/MA | 0.3868 | 0.3653 |
| XOM/CVX | 0.0763 | -0.1245 |
| KO/PEP | 0.5353 | -0.0215 |
| HD/LOW | -0.1572 | -0.3291 |
| GLD/GDX | 0.5314 | 0.3498 |
| SPY/QQQ | 0.1940 | -0.1436 |

Contamination scaled with hedge-ratio instability across seams: it was +284% of
composite P&L for XOM/CVX, +133% for SPY/QQQ and +100% for KO/PEP, against -3.8%
for GOOG/GOOGL, whose beta moves within a 0.09 canonical range. The pairs with no
stable cointegrating vector to estimate were the ones whose apparent P&L was
largely refit artifact.

The same defect was present in three further call sites that rebuilt composites
independently: the breakeven solver and cost sweep in `src/costs.py`, all 84
trial composites in `scripts/compute_dsr.py`, and
`scripts/robustness_orientation.py`. All four now share one implementation.

Full before/after for every affected table and figure is in `CHANGES.md`.

## 2026-07-24 - LHS ordering selection: AIC replaced by Engle-Granger residual ADF

**Changed:** `spread.preferred_ordering`, `"by_aic"` -> `"by_eg_adf_tstat"`.

**Why.** The cointegrating regression was fit in both LHS orderings and the one
with lower OLS AIC on the training residuals was retained. That comparison is not
valid. AIC = 2k - 2 ln(L), and the two orderings have different dependent
variables (`log(y) ~ log(x)` versus `log(x) ~ log(y)`), so their likelihoods are
densities over different random variables and are not on a common scale. The
ordering determines alpha and beta, which determine the spread, which determines
every P&L number downstream, so the criterion is load-bearing and was invalid.

**Replacement.** The retained ordering is the one whose Engle-Granger residual ADF
t-statistic is more negative - the orientation whose residual is most convincingly
stationary. The statistic is comparable across orderings and was already being
computed elsewhere in the pipeline.

**Second change, forced by the first.** Selecting per fold on the trailing 504-day
window made the orientation unstable: on GOOG/GOOGL the two orderings differ by a
median of 0.008 of ADF t-statistic across folds, so noise decided the orientation
and it flipped at 11 of 19 fold boundaries, redefining the spread mid-run. The
orientation is now selected on an EXPANDING window - every bar available before
each fold's OOS block - which uses maximal information without look-ahead and
reduces switching to 2 (GOOG/GOOGL) and 1 (V/MA). Alpha, beta, and the
`(entry_z, lookback)` cell still refit on the trailing window every fold. The same
"select on all pre-evaluation data" rule applies in stage 3.

**Numbers that moved** (composite walk-forward net Sharpe / breakeven bps):

| Pair | before | after |
|---|---|---|
| GOOG/GOOGL | 1.28 / 15.0 | 1.29 / 14.9 |
| V/MA | 0.42 / 37.4 | 0.39 / 27.9 |
| XOM/CVX | 0.05 / 10.5 | 0.08 / 15.9 |
| KO/PEP | 0.16 / 21.4 | 0.54 / 60.0 |
| HD/LOW | 0.10 / 16.5 | -0.16 / 0.0 |
| GLD/GDX | 0.57 / 58.5 | 0.53 / 60.0 |
| SPY/QQQ | -0.18 / 0.0 | 0.19 / 27.0 |

The two cointegrated pairs and GLD/GDX are essentially unchanged. The pairs that
move most (KO/PEP, SPY/QQQ, XOM/CVX) are the ones whose orientation is least
identified - 5 to 6 switches each even on the expanding window - which is itself a
symptom of the absent cointegrating relationship. `scripts/robustness_orientation.py`
quantifies the resulting band per pair; see the robustness subsection of the paper.

**Not changed, deliberately.** The state machine still re-enters immediately after a
hard stop rather than requiring a zero-crossing to re-arm. This is documented in
section 3.3 rather than fixed, because changing it would alter every reported
number and break the ex-ante methodology lock.
