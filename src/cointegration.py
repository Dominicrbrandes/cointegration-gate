"""Triangulated cointegration tests + rolling EG diagnostic.

For each pair we compute:
  * Engle-Granger (augmented) p-value with leg_0 as LHS    (eg_p_01)
  * Engle-Granger (augmented) p-value with leg_1 as LHS    (eg_p_10)
  * EG worse p-value across orderings                       (eg_p_worse)
  * Johansen trace + max-eig statistics with 5% critical    (joh_trace_stat, joh_trace_cv_5)
  * Phillips-Ouliaris Z_t p-value (arch.unitroot)           (po_pvalue)
  * static_tests_passed (count out of {EG_worse, Joh_trace, PO_Zt} rejecting at 5%)
  * cointegrated boolean: static_tests_passed >= required
  * Rolling 126-bar EG p-value (worse ordering) - DIAGNOSTIC ONLY
  * % of rolling windows with p<0.05                        (rolling_pct_below_alpha)

Hedge ratio (alpha, beta) is computed in src/spread.py from the TRAINING window only.
The static cointegration tests here run on the FULL sample so the classification
question - "does the pair cointegrate over the sample we are studying?" - is
answered against all available evidence; the universe was pre-specified, so
running the test on the full sample is not data-snooping.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from statsmodels.tsa.stattools import coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from arch.unitroot.cointegration import phillips_ouliaris


# ---------- Result types ----------

@dataclass
class CointResult:
    pair_id: str
    legs: List[str]
    input_space: str
    n_obs: int

    # Engle-Granger, both orderings (LHS shown first)
    eg_p_01: float    # LHS = legs[0]
    eg_stat_01: float
    eg_p_10: float    # LHS = legs[1]
    eg_stat_10: float
    eg_p_worse: float

    # Johansen
    joh_trace_stat: float
    joh_trace_cv_5: float
    joh_trace_reject: bool
    joh_maxeig_stat: float
    joh_maxeig_cv_5: float
    joh_maxeig_reject: bool

    # Phillips-Ouliaris Z_t
    po_stat: float
    po_pvalue: float
    po_reject: bool

    # Aggregate
    eg_reject: bool         # EG worse-of-two < alpha
    static_tests_passed: int
    cointegrated: bool

    # Rolling EG diagnostic (NOT part of the gate)
    rolling_window: int
    rolling_pct_below_alpha: float
    rolling_n_windows: int

    # Pearson correlation
    corr_levels: float            # raw adjusted-close levels
    corr_logreturns: float        # log-return correlation

    # Disagreements among tests / a-priori notes (transparent, reported in the table)
    notes: str


# ---------- Individual tests ----------

def engle_granger_both(df: pd.DataFrame, legs: List[str]) -> Tuple[float, float, float, float]:
    """Run EG with each leg as LHS. Returns (p_01, stat_01, p_10, stat_10)."""
    y0 = df[legs[0]].values
    y1 = df[legs[1]].values
    stat_01, p_01, _ = coint(y0, y1, trend="c", autolag="aic")
    stat_10, p_10, _ = coint(y1, y0, trend="c", autolag="aic")
    return float(p_01), float(stat_01), float(p_10), float(stat_10)


def johansen_test(df: pd.DataFrame, det_order: int, k_ar_diff: int) -> Tuple[float, float, float, float]:
    """Returns (trace_stat_r0, trace_cv_5_r0, maxeig_stat_r0, maxeig_cv_5_r0).

    coint_johansen.cvt / .cvm have shape (k, 3) for (10%, 5%, 1%) critical values.
    Row 0 is the null r=0; we care about that null only (2-variable system).
    """
    res = coint_johansen(df.values, det_order, k_ar_diff)
    trace_stat = float(res.lr1[0])
    trace_cv_5 = float(res.cvt[0, 1])
    maxeig_stat = float(res.lr2[0])
    maxeig_cv_5 = float(res.cvm[0, 1])
    return trace_stat, trace_cv_5, maxeig_stat, maxeig_cv_5


def phillips_ouliaris_test(df: pd.DataFrame, legs: List[str], trend: str = "c",
                            test_type: str = "Zt", kernel: str = "bartlett") -> Tuple[float, float]:
    """Run PO with leg_0 as LHS, leg_1 as regressor. Returns (stat, pvalue)."""
    y = df[legs[0]]
    x = df[[legs[1]]]
    res = phillips_ouliaris(y, x, trend=trend, test_type=test_type, kernel=kernel)
    return float(res.stat), float(res.pvalue)


def rolling_engle_granger(
    df: pd.DataFrame, legs: List[str], window: int
) -> pd.Series:
    """Rolling EG p-value (worse-of-two orderings) over fixed-size windows.

    Returns a Series indexed by the LAST date of each window (so the value is
    available only after the window closes - no look-ahead).
    """
    if len(df) < window + 1:
        return pd.Series(dtype="float64")
    y0 = df[legs[0]].values
    y1 = df[legs[1]].values
    out_idx = []
    out_val = []
    for i in range(window, len(df) + 1):
        a = y0[i - window:i]
        b = y1[i - window:i]
        try:
            _, p01, _ = coint(a, b, trend="c", autolag="aic")
            _, p10, _ = coint(b, a, trend="c", autolag="aic")
            p = max(float(p01), float(p10))
        except Exception:
            p = np.nan
        out_idx.append(df.index[i - 1])
        out_val.append(p)
    return pd.Series(out_val, index=pd.DatetimeIndex(out_idx), name="rolling_eg_p")


# ---------- Driver ----------

_MARGIN_P = 0.02              # ±2pp p-value band counts as "marginal" for EG / PO
_MARGIN_JOH = 1.5             # Johansen stat within 1.5 of the 5% critical counts as "marginal"


def _build_notes(eg_p_worse: float, eg_reject: bool,
                 trace_stat: float, trace_cv5: float, joh_trace_reject: bool,
                 maxeig_stat: float, maxeig_cv5: float, joh_maxeig_reject: bool,
                 po_p: float, po_reject: bool,
                 alpha: float, a_priori: str | None) -> str:
    """Compose a short, factual notes string. Reported in the headline table."""
    parts: list[str] = []
    # EG marginal flag
    if abs(eg_p_worse - alpha) <= _MARGIN_P:
        parts.append(f"EG marginal (p={eg_p_worse:.3f})")
    # Johansen trace marginal flag
    if abs(trace_stat - trace_cv5) <= _MARGIN_JOH:
        side = "above" if joh_trace_reject else "below"
        parts.append(f"Johansen trace marginal ({trace_stat:.2f} vs cv {trace_cv5:.2f}, {side})")
    # PO marginal flag
    if abs(po_p - alpha) <= _MARGIN_P:
        parts.append(f"PO marginal (p={po_p:.3f})")
    # Echo a-priori expectation when the result is borderline (0/3 or 1/3 etc.)
    if a_priori:
        parts.append(f"a-priori: {a_priori}")
    return "; ".join(parts)


def run_cointegration(
    df: pd.DataFrame,
    pair_id: str,
    legs: List[str],
    config: dict,
    *,
    input_space: str = "log",
    a_priori: str | None = None,
    df_for_corr_levels: pd.DataFrame | None = None,
) -> Tuple[CointResult, pd.Series]:
    """Run the full triangulation + rolling EG for one pair.

    `df` is the analysis frame (log-prices when input_space='log'); all tests run on it.
    `df_for_corr_levels` (optional) is the raw-level frame used only to compute the
    Pearson correlation of LEVELS (a context number for the report, e.g. SPY/QQQ ~1.00).
    """
    cc = config["cointegration"]
    alpha = float(cc["alpha"])
    rolling_window = int(cc["rolling_window"])
    det_order = int(cc["johansen"]["det_order"])
    k_ar_diff = int(cc["johansen"]["k_ar_diff"])
    po_trend = cc["phillips_ouliaris"]["trend"]
    po_test = cc["phillips_ouliaris"]["test_type"]
    po_kernel = cc["phillips_ouliaris"]["kernel"]
    required = int(cc["decision_rule"]["static_tests_required"])

    # Static tests on full sample (in the analysis frame)
    eg_p_01, eg_stat_01, eg_p_10, eg_stat_10 = engle_granger_both(df, legs)
    eg_p_worse = max(eg_p_01, eg_p_10)
    eg_reject = eg_p_worse < alpha

    trace_stat, trace_cv5, maxeig_stat, maxeig_cv5 = johansen_test(df, det_order, k_ar_diff)
    joh_trace_reject = trace_stat > trace_cv5
    joh_maxeig_reject = maxeig_stat > maxeig_cv5

    po_stat, po_p = phillips_ouliaris_test(df, legs, trend=po_trend, test_type=po_test, kernel=po_kernel)
    po_reject = po_p < alpha

    static_passed = int(eg_reject) + int(joh_trace_reject) + int(po_reject)
    cointegrated = static_passed >= required

    # Rolling EG diagnostic
    rolling = rolling_engle_granger(df, legs, rolling_window)
    if len(rolling):
        pct_below = float((rolling < alpha).mean()) * 100.0
    else:
        pct_below = float("nan")

    # Correlations
    if df_for_corr_levels is not None:
        corr_levels = float(df_for_corr_levels[legs[0]].corr(df_for_corr_levels[legs[1]]))
        log_ret = np.log(df_for_corr_levels).diff().dropna()
        corr_logret = float(log_ret[legs[0]].corr(log_ret[legs[1]]))
    else:
        corr_levels = float(df[legs[0]].corr(df[legs[1]]))
        d_ret = df.diff().dropna()
        corr_logret = float(d_ret[legs[0]].corr(d_ret[legs[1]]))

    notes = _build_notes(
        eg_p_worse, eg_reject,
        trace_stat, trace_cv5, joh_trace_reject,
        maxeig_stat, maxeig_cv5, joh_maxeig_reject,
        po_p, po_reject,
        alpha, a_priori,
    )

    result = CointResult(
        pair_id=pair_id,
        legs=list(legs),
        input_space=input_space,
        n_obs=len(df),
        eg_p_01=eg_p_01,
        eg_stat_01=eg_stat_01,
        eg_p_10=eg_p_10,
        eg_stat_10=eg_stat_10,
        eg_p_worse=eg_p_worse,
        joh_trace_stat=trace_stat,
        joh_trace_cv_5=trace_cv5,
        joh_trace_reject=bool(joh_trace_reject),
        joh_maxeig_stat=maxeig_stat,
        joh_maxeig_cv_5=maxeig_cv5,
        joh_maxeig_reject=bool(joh_maxeig_reject),
        po_stat=po_stat,
        po_pvalue=po_p,
        po_reject=bool(po_reject),
        eg_reject=bool(eg_reject),
        static_tests_passed=static_passed,
        cointegrated=bool(cointegrated),
        rolling_window=rolling_window,
        rolling_pct_below_alpha=pct_below,
        rolling_n_windows=len(rolling),
        corr_levels=corr_levels,
        corr_logreturns=corr_logret,
        notes=notes,
    )
    return result, rolling


def results_to_dataframe(results: Dict[str, CointResult]) -> pd.DataFrame:
    rows = [asdict(r) for r in results.values()]
    df = pd.DataFrame(rows)
    df = df.set_index("pair_id")
    return df
