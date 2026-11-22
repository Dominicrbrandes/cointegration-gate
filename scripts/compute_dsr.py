"""Deflated Sharpe Ratio (Bailey and Lopez de Prado 2014) for the headline pair.

Run from the repo root AFTER stages 3-4 have been run:

    python scripts/compute_dsr.py
    python scripts/compute_dsr.py --orientation first    # band floor of Sec 4.8

`--orientation` pins the LHS convention instead of using the expanding-window
rule of Section 3.2. `first`/`second` put the first/second listed leg of each
pair on the left-hand side, held fixed across every fold and every pair. This
is what produces the bottom of the Section 4.8 specification band, and the
trial distribution is rebuilt under the same convention so that SR0 and the
candidate come from one coherent world rather than two.

It reconstructs GOOG/GOOGL's composite walk-forward daily net P&L the same way
run_stage_4 / the stage-5 reproducibility check do (so the annualized Sharpe
matches the paper's 1.38), then deflates it against the locked 84-cell selection
budget. The reported number in Section 5 is the conservative one: candidate =
walk-forward composite, K = 84 (whole-study budget), trial variance V = the
variance of 84 walk-forward composites, one per (pair, cell), each computed with
that cell held fixed across all twenty folds.

DSR = Phi( (SR_hat - SR0) * sqrt(T - 1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2) )
  SR_hat  daily Sharpe of the candidate series (NOT annualized)
  T       number of daily observations in the candidate series
  g3, g4  skewness and raw (non-excess, normal=3) kurtosis of the daily net P&L
  SR0     sqrt(V) * ((1-gamma)*Z(1-1/K) + gamma*Z(1-1/(K*e)))   expected max under null
  V       cross-trial variance of the (daily) Sharpe estimates over the K cells
  K       84  (7 pairs x 12 cells, the locked selection budget)
"""
from __future__ import annotations

import argparse
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from src.spread import fit_cointegrating_vector, compute_spread, select_ordering
from src.backtest import _fold_train_score, fold_oos_eval, compute_composite_pnl

EULER = 0.5772156649015329
ANN = np.sqrt(252)
K = 84  # 7 pairs x 12 cells, locked selection budget
HEADLINE = "GOOG_GOOGL"


def psr(sr_hat: float, sr_star: float, T: int, g3: float, g4: float) -> float:
    denom = np.sqrt(1.0 - g3 * sr_hat + ((g4 - 1.0) / 4.0) * sr_hat ** 2)
    return float(stats.norm.cdf((sr_hat - sr_star) * np.sqrt(T - 1) / denom))


def sr0_benchmark(V: float, K: int) -> float:
    z1 = stats.norm.ppf(1.0 - 1.0 / K)
    z2 = stats.norm.ppf(1.0 - 1.0 / (K * np.e))
    return float(np.sqrt(V) * ((1.0 - EULER) * z1 + EULER * z2))


def resolve_ordering(pair, convention: str, train_slice) -> tuple[str, str]:
    """Orientation for one fold under the requested convention.

    `expanding` reproduces Section 3.2 (select on all bars before the OOS block);
    `first`/`second` pin the ordering and ignore the window entirely.
    """
    legs = list(pair.legs)
    if convention == "first":
        return (legs[0], legs[1])
    if convention == "second":
        return (legs[1], legs[0])
    return select_ordering(train_slice, legs)


def wf_composite_net_pnl(pair, cfg: dict, convention: str = "expanding") -> pd.Series:
    """Reconstruct the refit-both walk-forward composite daily net P&L series."""
    legs = list(pair.legs)
    grid = cfg["signal"]["grid"]
    cost = float(cfg["costs"]["baseline_round_trip_bps"])
    wf = cfg["backtest"]["walk_forward"]
    tw, ow, step = int(wf["train_window_days"]), int(wf["test_window_days"]), int(wf["step_days"])
    idx = pair.df.index
    pos_parts, spr_parts, s0 = [], [], 0
    while s0 + tw + ow <= len(idx):
        tr = idx[s0:s0 + tw]
        oo = idx[s0 + tw:s0 + tw + ow]
        ordering = resolve_ordering(pair, convention, pair.df.iloc[0:s0 + tw])
        fit = fit_cointegrating_vector(pair.df.loc[tr], legs, pair.pair_id, cfg,
                                       force_ordering=ordering)
        spread_full = compute_spread(pair.df.loc[tr.append(oo)], fit)
        best = None
        for ez, sz, lb in product(grid["entry_z"], grid["stop_z"], grid["lookback"]):
            sh, ne = _fold_train_score(spread_full, tr, ez, sz, lb, cost)
            sh = -np.inf if not np.isfinite(sh) else sh
            cand = (sh, ne, float(ez), float(sz), int(lb))
            if best is None or cand[:2] > best[:2]:
                best = cand
        _, _, ez, sz, lb = best
        _, pos_oos, _ = fold_oos_eval(spread_full, tr, oo, ez, sz, lb, cost)
        pos_parts.append(pos_oos)
        spr_parts.append(spread_full.loc[oo])
        s0 += step
    return compute_composite_pnl(pos_parts, spr_parts, cost)["net_pnl"]


def wf_composite_fixed_cell(pair, cfg: dict, entry_z: float, stop_z: float,
                            lookback: int, convention: str = "expanding") -> float:
    """Walk-forward composite daily net Sharpe with ONE cell held fixed across all
    folds (alpha/beta still refit per fold). Running this for every cell and every
    pair gives the trial distribution of the statistic actually being deflated."""
    legs = list(pair.legs)
    cost = float(cfg["costs"]["baseline_round_trip_bps"])
    wf = cfg["backtest"]["walk_forward"]
    tw, ow, step = int(wf["train_window_days"]), int(wf["test_window_days"]), int(wf["step_days"])
    idx = pair.df.index
    pos_parts, spr_parts, s0 = [], [], 0
    while s0 + tw + ow <= len(idx):
        tr, oo = idx[s0:s0 + tw], idx[s0 + tw:s0 + tw + ow]
        ordering = resolve_ordering(pair, convention, pair.df.iloc[0:s0 + tw])
        fit = fit_cointegrating_vector(pair.df.loc[tr], legs, pair.pair_id, cfg,
                                       force_ordering=ordering)
        spread_full = compute_spread(pair.df.loc[tr.append(oo)], fit)
        _, pos_oos, _ = fold_oos_eval(spread_full, tr, oo, entry_z, stop_z, lookback, cost)
        pos_parts.append(pos_oos)
        spr_parts.append(spread_full.loc[oo])
        s0 += step
    p = compute_composite_pnl(pos_parts, spr_parts, cost)["net_pnl"].dropna()
    sd = p.std(ddof=1)
    return float(p.mean() / sd) if sd > 0 else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orientation", choices=["expanding", "first", "second"],
                    default="expanding",
                    help="LHS convention; 'expanding' is the Section 3.2 rule the "
                         "paper reports, 'first'/'second' pin it across all folds")
    args = ap.parse_args()
    convention = args.orientation

    cfg = load_config()
    pairs = load_universe(cfg, refresh=False)
    grid = cfg["signal"]["grid"]
    print(f"orientation convention: {convention}")

    # Trial dispersion V. The statistic being deflated is the walk-forward composite,
    # so the trial distribution must be the distribution of THAT estimator: 84
    # walk-forward composites, one per (pair, cell). Estimating V from the stage-3
    # single-split grid instead would mix estimators computed on different windows
    # under different refitting regimes - the DSR framework assumes they match.
    print(f"building trial distribution: {K} walk-forward composites ...")
    trial_rows = []
    for pid, pair in pairs.items():
        for ez, sz, lb in product(grid["entry_z"], grid["stop_z"], grid["lookback"]):
            trial_rows.append({
                "pair_id": pid, "entry_z": ez, "stop_z": sz, "lookback": lb,
                "sharpe_wf_daily": wf_composite_fixed_cell(pair, cfg, float(ez), float(sz),
                                                           int(lb), convention),
            })
    trial_df = pd.DataFrame(trial_rows)
    suffix = "" if convention == "expanding" else f"_{convention}"
    trial_df.to_csv(ROOT / "results" / f"dsr_trial_walkforward{suffix}.csv", index=False)
    trial = trial_df["sharpe_wf_daily"].dropna().values
    assert len(trial) == K, f"expected {K} trials, found {len(trial)}"
    V = float(np.var(trial, ddof=1))
    sr0 = sr0_benchmark(V, K)

    pnl = wf_composite_net_pnl(pairs[HEADLINE], cfg, convention).dropna()
    sr_daily = float(pnl.mean() / pnl.std(ddof=1))
    g3 = float(stats.skew(pnl))
    g4 = float(stats.kurtosis(pnl, fisher=False))
    T = len(pnl)

    dsr_84 = psr(sr_daily, sr0, T, g3, g4)
    # Narrower per-pair budget (only the 12 cells that competed for this pair)
    own = trial_df.loc[trial_df["pair_id"] == HEADLINE, "sharpe_wf_daily"].dropna().values
    dsr_12 = psr(sr_daily, sr0_benchmark(float(np.var(own, ddof=1)), 12), T, g3, g4)

    print(f"candidate  : {HEADLINE} walk-forward composite daily net P&L")
    print(f"  ann Sharpe : {sr_daily * ANN:.3f}")
    print(f"  T={T}  skew={g3:.3f}  kurt(non-excess)={g4:.3f}")
    print(f"trial V (daily, walk-forward composites, K=84) : {V:.3e}")
    print(f"SR0 (daily, K=84)                              : {sr0:.4f}  (ann {sr0 * ANN:.3f})")
    print(f"\nDSR (K=84, whole-study budget)   : {dsr_84:.4f}   <- reported in Section 5")
    print(f"DSR (K=12, per-pair budget)      : {dsr_12:.4f}")


if __name__ == "__main__":
    main()
