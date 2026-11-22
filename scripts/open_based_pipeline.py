"""Stages 3-5 rebuilt end to end on an OPEN-based price series.

Everything moves into open space: the cointegrating fit, the spread, the rolling
z-score, the entry/exit signal, and the P&L. This is not the same experiment as
scripts/execution_conventions.py, which kept the fit and the signal on closes and
varied only the fill price. Here the pipeline never sees a closing price.

The open series is the cached adjusted close times the same-day Open/Close ratio
(see scripts/fetch_open_ratio.py), so the 2026-05-30 close snapshot that the paper
is based on is not re-fetched and not modified.

Held fixed against the close-based run: the 12-cell (entry_z, lookback) grid, the
504/126/126 walk-forward blocks, the expanding-window orientation rule, the 3 bps
round-trip cost, the 2022-12-31 single-split date, and the within-fold P&L
differencing of src.backtest.compute_composite_pnl.

NOT re-derived: the Section 4.1 cointegration gate. That is a stage-2 artifact and
the classification is carried over from the close-based run, so "cointegrated" in
the output below means "cointegrated on closes."
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from src.spread import fit_cointegrating_vector, compute_spread, select_ordering
from src.backtest import (
    run_pair_stage3, run_pair_stage4_walkforward, fold_oos_eval,
    compute_composite_pnl, sharpe, annualized_return,
)
from src.costs import breakeven_cost_bps


def open_frame(pair, cfg) -> pd.DataFrame:
    """Reconstructed open prices for this pair, in the configured analysis space."""
    out_dir = ROOT / "data" / "raw_open"
    cols = {}
    for leg in pair.legs:
        files = sorted(out_dir.glob(f"{leg}__*.parquet"))
        if not files:
            raise RuntimeError(f"no open-ratio file for {leg}; run fetch_open_ratio.py")
        cols[leg] = pd.read_parquet(files[-1])["open_recon"]
    f = pd.DataFrame(cols)
    f.index = pd.to_datetime(f.index)
    f = f.reindex(pair.df.index)
    if f.isna().any().any():
        raise RuntimeError(f"{pair.pair_id}: open frame has gaps after alignment")
    return f


def as_open_pair(pair, cfg):
    """A PairData whose analysis frame is open prices, aligned bar for bar."""
    lvl = open_frame(pair, cfg)
    df = np.log(lvl) if cfg["data"].get("input_space", "log") == "log" else lvl
    split = pd.Timestamp(cfg["data"]["train_test_split_date"])
    return replace(pair, df=df, df_levels=lvl,
                   train=df.loc[df.index <= split], test=df.loc[df.index > split])


def wf_parts(pair, cfg, folds_meta):
    """Per-fold OOS positions and spreads under the locked cells of `folds_meta`."""
    legs = list(pair.legs)
    wfc = cfg["backtest"]["walk_forward"]
    TW, STEP = int(wfc["train_window_days"]), int(wfc["step_days"])
    cost = float(cfg["costs"]["baseline_round_trip_bps"])
    pos_parts, spr_parts = [], []
    for k, f in enumerate(folds_meta):
        tr = pair.df.loc[f.train_start:f.train_end].index
        oo = pair.df.loc[f.oos_start:f.oos_end].index
        fit = fit_cointegrating_vector(
            pair.df.loc[tr], legs, pair.pair_id, cfg,
            force_ordering=select_ordering(pair.df.iloc[0:k * STEP + TW], legs))
        sp = compute_spread(pair.df.loc[tr.append(oo)], fit)
        _, pos, _ = fold_oos_eval(sp, tr, oo, f.entry_z, f.stop_z, f.lookback, cost)
        pos_parts.append(pos)
        spr_parts.append(sp.loc[oo])
    return pos_parts, spr_parts


def main() -> None:
    cfg = load_config()
    pairs = load_universe(cfg, refresh=False)
    cost = float(cfg["costs"]["baseline_round_trip_bps"])
    be_range = tuple(cfg["costs"]["breakeven_search_bps"])
    s2 = json.loads((ROOT / "results" / "stage2_cointegration.json").read_text())
    s3_close = pd.read_csv(ROOT / "results" / "stage3_singlesplit.csv").set_index("pair_id")
    s4_close = json.loads((ROOT / "results" / "stage4_walkforward.json").read_text())
    s5_close = json.loads((ROOT / "results" / "stage5_summary.json").read_text())

    rows = []
    for pid, pair in pairs.items():
        op = as_open_pair(pair, cfg)
        coint = bool(s2[pid]["cointegrated"])

        # ---- stage 3: single split, open-based ----
        fit3 = fit_cointegrating_vector(op.train, list(op.legs), pid, cfg)
        spread3 = compute_spread(op.df, fit3)
        r3, _, _ = run_pair_stage3(op, fit3, spread3, cfg, coint)

        # ---- stage 4: walk-forward, open-based ----
        r4 = run_pair_stage4_walkforward(op, cfg)

        # ---- stage 5: breakeven on the open-based composite ----
        pp, sp_ = wf_parts(op, cfg, r4.folds)
        be = breakeven_cost_bps(pp, sp_, be_range)
        pnl = compute_composite_pnl(pp, sp_, cost)

        betas = np.array([f.beta_canonical for f in r4.folds], dtype=float)
        ys = [f.y_var for f in r4.folds]

        rows.append(dict(
            pair=pid, coint_on_close=coint,
            S3_test_close=float(s3_close.loc[pid, "S_test_net"]),
            S3_test_open=r3.sharpe_test_net,
            S4_close=s4_close[pid]["summary"]["composite_sharpe_oos_net"],
            S4_open=r4.composite_sharpe_oos_net,
            BE_close=s5_close["breakeven_bps"][pid],
            BE_open=be,
            AnnRet_close=s4_close[pid]["summary"]["composite_annret_oos_net"],
            AnnRet_open=r4.composite_annret_oos_net,
            pctfolds_close=s4_close[pid]["summary"]["pct_folds_positive_net"],
            pctfolds_open=r4.pct_folds_positive_net,
            beta_rng_open=float(np.nanmax(betas) - np.nanmin(betas)),
            lhs_sw_open=sum(1 for a, b in zip(ys, ys[1:]) if a != b),
            entries_open=r4.composite_n_entries_oos,
        ))
        print(f"  {pid:12s} done  S4 close={rows[-1]['S4_close']:+.4f}  "
              f"open={rows[-1]['S4_open']:+.4f}")

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 260)

    print("\n" + "=" * 104)
    print("STAGES 3-5 ON AN OPEN-BASED PRICE SERIES (fit, z, signal, P&L all open-to-open)")
    print("=" * 104)
    print("\nWalk-forward composite net Sharpe and breakeven:")
    print(df[["pair", "coint_on_close", "S4_close", "S4_open", "BE_close", "BE_open"]]
          .to_string(index=False, float_format=lambda v: f"{v: .4f}"))
    print("\nSupporting columns:")
    print(df[["pair", "S3_test_close", "S3_test_open", "AnnRet_close", "AnnRet_open",
              "pctfolds_close", "pctfolds_open", "beta_rng_open", "lhs_sw_open",
              "entries_open"]].to_string(index=False, float_format=lambda v: f"{v: .4f}"))

    df.to_csv(ROOT / "results" / "open_based_pipeline.csv", index=False)
    print("\nwrote results/open_based_pipeline.csv")


if __name__ == "__main__":
    main()
