"""Sensitivity of the GOOG/GOOGL composite to the walk-forward block sizes.

Section 4.8 of the paper. The pre-specified walk-forward uses a 504-bar training
block and a 126-bar OOS block, stepping by the OOS block. This script re-runs the
locked stage-4 walk-forward on GOOG/GOOGL under six other (train, OOS) choices,
with everything else held fixed, and reports the composite net Sharpe for each.

Why the config is loaded with verify=False. The block sizes are locked values in
config.yaml, and this script exists to vary them. It mutates
backtest.walk_forward on a deep copy of the loaded config, so the fingerprint
check in load_config would be asserting a lock the script is about to depart
from on purpose. config.yaml itself is never written, and no result the paper
reports as its headline is produced here: the (504, 126) row is included only so
the output can be checked against the stage-4 composite.

Usage:
    python scripts/window_sensitivity.py
"""
from __future__ import annotations

import copy
import sys
import warnings
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from src.backtest import run_pair_stage4_walkforward

PAIR = "GOOG_GOOGL"

# (train_window_days, test_window_days). The step always equals the OOS block.
WINDOWS = [(504, 126), (378, 126), (630, 126), (756, 126), (252, 126), (504, 63), (504, 252)]


def main() -> None:
    warnings.filterwarnings("ignore")
    cfg = load_config(verify=False)
    pair = load_universe(cfg, refresh=False)[PAIR]

    rows = []
    for train_w, oos_w in WINDOWS:
        c = copy.deepcopy(cfg)
        c["backtest"]["walk_forward"].update(
            {"train_window_days": train_w, "test_window_days": oos_w, "step_days": oos_w})
        wf = run_pair_stage4_walkforward(pair, c)
        rows.append({
            "pair": PAIR,
            "train_window_days": train_w,
            "test_window_days": oos_w,
            "n_folds": wf.n_folds,
            "n_folds_positive": sum(1 for f in wf.folds if f.sharpe_oos_net > 0),
            "composite_n_oos_bars": wf.composite_n_oos_bars,
            "composite_sharpe_oos_gross": wf.composite_sharpe_oos_gross,
            "composite_sharpe_oos_net": wf.composite_sharpe_oos_net,
        })

    df = pd.DataFrame(rows)
    print("=" * 88)
    print(f"WALK-FORWARD WINDOW SENSITIVITY, {PAIR} (all else as locked)")
    print("=" * 88)
    for r in rows:
        print(f"train {r['train_window_days']:3d} / oos {r['test_window_days']:3d}: "
              f"folds {r['n_folds']:2d}  composite net S {r['composite_sharpe_oos_net']:5.2f}  "
              f"gross {r['composite_sharpe_oos_gross']:5.2f}  "
              f"+folds {r['n_folds_positive']}/{r['n_folds']}  "
              f"bars {r['composite_n_oos_bars']}")

    out = ROOT / "results" / "window_sensitivity.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nwrote {out.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
