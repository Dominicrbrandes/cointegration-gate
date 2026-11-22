"""Robustness of the walk-forward composite to the LHS orientation convention.

Motivation. The cointegrating regression must put one leg on the left-hand side,
and for a near-symmetric pair the data barely identifies which. On GOOG/GOOGL the
two orderings differ by 0.008 of Engle-Granger residual ADF t-statistic (median
across folds) and their betas agree to 6.4e-3, so the two spreads are the same
object to any economic reading. The composite net Sharpe nonetheless differs by
0.21, because the per-fold (entry_z, lookback) selection is a discrete argmax over
a grid with near-ties: a ~1e-3 perturbation of the spread tips which cell wins in
a handful of folds, and one fold can carry a 1.9 Sharpe swing on its own.

This script quantifies that sensitivity rather than hiding it. For each pair it
recomputes the full walk-forward under both orientations held fixed, and reports
the resulting band alongside the number the paper actually uses.

    python scripts/robustness_orientation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.backtest as bt
from src.config_io import load_config
from src.data import load_universe
from src.backtest import run_pair_stage4_walkforward, fold_oos_eval
from src.spread import fit_cointegrating_vector, compute_spread, _eg_adf_stat
from src.costs import breakeven_cost_bps


def _pin(ordering):
    def _f(*args, **kwargs):
        return ordering
    return _f


def composite_positions(pair, ordering, wf_result, cfg):
    """Rebuild PER-FOLD OOS positions/spreads under a pinned orientation, reusing
    the cells that fold selection chose under that same orientation.

    Returned unconcatenated because gross P&L must be differenced inside each fold;
    see src.backtest.compute_composite_pnl."""
    wf = cfg["backtest"]["walk_forward"]
    tw, ow, step = int(wf["train_window_days"]), int(wf["test_window_days"]), int(wf["step_days"])
    cost = float(cfg["costs"]["baseline_round_trip_bps"])
    idx = pair.df.index
    pos_parts, spr_parts, s0, k = [], [], 0, 0
    while s0 + tw + ow <= len(idx):
        tr, oo = idx[s0:s0 + tw], idx[s0 + tw:s0 + tw + ow]
        fit = fit_cointegrating_vector(pair.df.loc[tr], list(pair.legs), pair.pair_id,
                                       cfg, force_ordering=ordering)
        spread_full = compute_spread(pair.df.loc[tr.append(oo)], fit)
        f = wf_result.folds[k]
        _, pos_oos, _ = fold_oos_eval(spread_full, tr, oo,
                                      f.entry_z, f.stop_z, f.lookback, cost)
        pos_parts.append(pos_oos)
        spr_parts.append(spread_full.loc[oo])
        s0 += step
        k += 1
    return pos_parts, spr_parts


def main() -> None:
    cfg = load_config()
    pairs = load_universe(cfg, refresh=False)
    stage4 = json.loads((ROOT / "results" / "stage4_walkforward.json").read_text())
    be_range = tuple(cfg["costs"]["breakeven_search_bps"])
    be_built = json.loads((ROOT / "results" / "stage5_summary.json").read_text())["breakeven_bps"]
    tw = int(cfg["backtest"]["walk_forward"]["train_window_days"])

    rows = []
    original = bt.select_ordering
    for pid, pair in pairs.items():
        legs = list(pair.legs)

        # As-built number (expanding-window orientation, what the paper reports)
        s_built = stage4[pid]["summary"]["composite_sharpe_oos_net"]
        ys = [f["y_var"] for f in stage4[pid]["folds"]]
        switches = sum(1 for a, b in zip(ys, ys[1:]) if a != b)

        # Median ADF gap between orderings across the fold training windows
        gaps = []
        for f in stage4[pid]["folds"]:
            w = pair.df.loc[f["train_start"]:f["train_end"]]
            gaps.append(abs(_eg_adf_stat(w[legs[0]], w[legs[1]])
                            - _eg_adf_stat(w[legs[1]], w[legs[0]])))

        variants = {}
        for ordering in [(legs[0], legs[1]), (legs[1], legs[0])]:
            bt.select_ordering = _pin(ordering)
            try:
                r = run_pair_stage4_walkforward(pair, cfg)
                ppar, spar = composite_positions(pair, ordering, r, cfg)
                variants[f"{ordering[0]}~{ordering[1]}"] = (
                    r.composite_sharpe_oos_net, breakeven_cost_bps(ppar, spar, be_range)
                )
            finally:
                bt.select_ordering = original

        sharpes = [v[0] for v in variants.values()] + [s_built]
        bes = [v[1] for v in variants.values()] + [be_built[pid]]
        rows.append({
            "pair_id": pid,
            "S_as_built": s_built,
            "S_min": min(sharpes), "S_max": max(sharpes),
            "S_band": max(sharpes) - min(sharpes),
            "BE_as_built": be_built[pid],
            "BE_min": min(bes), "BE_max": max(bes),
            "ordering_switches": switches,
            "median_adf_gap": float(np.median(gaps)),
        })

    out = pd.DataFrame(rows).set_index("pair_id")
    out.to_csv(ROOT / "results" / "robustness_orientation.csv")

    print("Walk-forward composite under both LHS orientations held fixed")
    print("(S_as_built uses the expanding-window orientation rule of section 3.2)\n")
    disp = out.copy()
    for c in ["S_as_built", "S_min", "S_max", "S_band", "median_adf_gap"]:
        disp[c] = disp[c].map(lambda v: f"{v:.2f}" if c != "median_adf_gap" else f"{v:.3f}")
    for c in ["BE_as_built", "BE_min", "BE_max"]:
        disp[c] = disp[c].map(lambda v: f"{v:.1f}")
    print(disp.to_string())
    print(f"\nwrote results/robustness_orientation.csv")


if __name__ == "__main__":
    main()
