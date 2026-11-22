"""Cointegrating regression (training only) + Ornstein-Uhlenbeck half-life.

The hedge ratio (alpha, beta) is fit on the TRAINING window only and applied
unchanged to the test window. The spread is computed in log-price space (the
canonical analysis frame from src/data.py when input_space="log").

Both LHS orderings of the regression are evaluated; we retain the one whose
Engle-Granger residual ADF t-statistic is more negative on the training window
(config: spread.preferred_ordering).

Selecting on OLS AIC would be invalid here. AIC = 2k - 2 ln(L), and the two
orderings have different dependent variables, so their likelihoods are densities
over different random variables and are not on a common scale. The EG residual
ADF statistic is comparable across orderings and selects the orientation whose
residual is most convincingly stationary - the quantity actually of interest.
The AIC of each ordering is still recorded on the fit for transparency, but it
no longer drives the choice.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint


@dataclass
class SpreadFit:
    pair_id: str
    legs: List[str]
    y_var: str                  # LHS variable in the regression
    x_var: str                  # RHS variable in the regression
    alpha: float                # constant
    beta: float                 # hedge ratio
    train_residual_std: float
    aic: float                  # recorded only; NOT the selection criterion (see module docstring)
    eg_adf_stat: float          # EG residual ADF t-stat for the retained ordering; the criterion
    eg_adf_stat_rejected: float # same statistic for the ordering not retained
    half_life_days: float       # clipped to [floor_days, ceil_days]
    half_life_raw_days: float   # pre-clip; inf when b >= 0
    half_life_b: float          # the AR(1) coefficient b in Δs = a + b·s_{t-1} + ε
    train_n: int


# ---------- Internals ----------

def _ols_with_const(y: pd.Series, x: pd.Series):
    X = sm.add_constant(x.values, has_constant="add")
    return sm.OLS(y.values, X).fit()


def half_life_OU_AR1(spread_train: pd.Series, floor_days: float, ceil_days: float) -> tuple[float, float, float]:
    """Returns (half_life_clipped, half_life_raw, b_coefficient).

    Δs_t = a + b * s_{t-1} + ε
    b is the mean-reversion rate (negative for stationary). HL_raw = -ln(2)/ln(1+b).
    HL_clipped applies [floor_days, ceil_days] for downstream consumption; HL_raw
    is exposed so the report can note explicitly when clipping occurred.
    """
    s = pd.Series(spread_train).dropna()
    if len(s) < 30:
        return float("nan"), float("nan"), float("nan")
    ds = s.diff()
    s_lag = s.shift(1)
    df = pd.concat([ds, s_lag], axis=1).dropna()
    df.columns = ["ds", "s_lag"]
    res = _ols_with_const(df["ds"], df["s_lag"])
    b = float(res.params[1])
    if b >= 0:
        return float("inf"), float("inf"), b
    one_plus_b = 1.0 + b
    if one_plus_b <= 0:
        return float(floor_days), float(floor_days), b
    hl_raw = -np.log(2.0) / np.log(one_plus_b)
    if not np.isfinite(hl_raw):
        return float("nan"), float("nan"), b
    return float(np.clip(hl_raw, floor_days, ceil_days)), float(hl_raw), b


# ---------- Public ----------

def _eg_adf_stat(y: pd.Series, x: pd.Series) -> float:
    """Engle-Granger residual ADF t-statistic for the regression of y on x.

    More negative means the residual is more convincingly stationary. Returns
    +inf on failure so a broken ordering never wins the comparison.
    """
    try:
        stat, _, _ = coint(y.values, x.values, trend="c", autolag="aic")
        return float(stat)
    except Exception:
        return float("inf")


def select_ordering(train_df: pd.DataFrame, legs: List[str]) -> tuple[str, str]:
    """Return the (y_var, x_var) ordering with the more negative EG residual ADF
    t-statistic on this window.

    Exposed separately so the walk-forward can choose the window the orientation
    is selected on independently of the window alpha and beta are fit on. The
    walk-forward re-evaluates the orientation at every fold, on an expanding
    window that runs from the first bar to the end of that fold's training
    block, and passes the result to fit_cointegrating_vector as force_ordering.
    The two orderings are often a near-tie (for GOOG/GOOGL the median gap across
    folds is 0.008), so selecting on the trailing 504-bar window alone would let
    noise flip the orientation mid-run and force an unwind at each flip; the
    expanding window uses all available history to settle it. Alpha and beta
    still refit every fold on the trailing window.
    """
    a = _eg_adf_stat(train_df[legs[0]], train_df[legs[1]])
    b = _eg_adf_stat(train_df[legs[1]], train_df[legs[0]])
    return (legs[0], legs[1]) if a <= b else (legs[1], legs[0])


def fit_cointegrating_vector(
    train_df: pd.DataFrame, legs: List[str], pair_id: str, cfg: dict,
    *, force_ordering: tuple[str, str] | None = None,
) -> SpreadFit:
    """Fit y = alpha + beta * x on TRAINING data; retain the ordering whose EG
    residual ADF t-statistic is more negative.

    `force_ordering` pins (y_var, x_var) instead of selecting on this window -
    used by the walk-forward to hold the orientation fixed across folds.
    """
    floor_days = float(cfg["spread"]["half_life"]["floor_days"])
    ceil_days = float(cfg["spread"]["half_life"]["ceil_days"])

    candidates = []
    for y_var, x_var in [(legs[0], legs[1]), (legs[1], legs[0])]:
        res = _ols_with_const(train_df[y_var], train_df[x_var])
        alpha = float(res.params[0])
        beta = float(res.params[1])
        resid = train_df[y_var].values - alpha - beta * train_df[x_var].values
        train_resid_std = float(np.std(resid, ddof=1))
        candidates.append({
            "y_var": y_var, "x_var": x_var,
            "alpha": alpha, "beta": beta,
            "train_residual_std": train_resid_std,
            "aic": float(res.aic),
            "eg_adf_stat": _eg_adf_stat(train_df[y_var], train_df[x_var]),
            "resid_train": pd.Series(resid, index=train_df.index, name="spread_train"),
        })

    if force_ordering is None:
        chosen = min(candidates, key=lambda c: c["eg_adf_stat"])
    else:
        chosen = next(c for c in candidates
                      if (c["y_var"], c["x_var"]) == tuple(force_ordering))
    rejected = [c for c in candidates if c is not chosen][0]
    hl, hl_raw, b_coef = half_life_OU_AR1(chosen["resid_train"], floor_days, ceil_days)

    return SpreadFit(
        pair_id=pair_id,
        legs=list(legs),
        y_var=chosen["y_var"],
        x_var=chosen["x_var"],
        alpha=chosen["alpha"],
        beta=chosen["beta"],
        train_residual_std=chosen["train_residual_std"],
        aic=chosen["aic"],
        eg_adf_stat=chosen["eg_adf_stat"],
        eg_adf_stat_rejected=rejected["eg_adf_stat"],
        half_life_days=hl,
        half_life_raw_days=hl_raw,
        half_life_b=b_coef,
        train_n=len(train_df),
    )


def compute_spread(df: pd.DataFrame, fit: SpreadFit) -> pd.Series:
    """Apply the train-fitted vector to the full sample: spread = y - alpha - beta*x."""
    s = df[fit.y_var] - fit.alpha - fit.beta * df[fit.x_var]
    s.name = "spread"
    return s
