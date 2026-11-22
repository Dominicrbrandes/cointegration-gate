"""Johansen lag-robustness check for the cointegration classification.

Run from the repo root:

    python scripts/robustness_johansen_lag.py

For each pair, recompute the Johansen trace statistic at k_ar_diff = 1..4 and
report whether the full 2-of-3 classification (EG and PO held fixed from stage 2)
changes with the lag. Also report the VAR lag order that BIC/HQIC select. This
backs the lag-sensitivity disclosure in Section 4.1: GOOG/GOOGL's Johansen
rejection holds only at the pre-registered single lag.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from statsmodels.tsa.api import VAR


def main() -> None:
    cfg = load_config()
    pairs = load_universe(cfg, refresh=False)
    stage2 = json.loads((ROOT / "results" / "stage2_cointegration.json").read_text())
    det_order = int(cfg["cointegration"]["johansen"]["det_order"])
    required = int(cfg["cointegration"]["decision_rule"]["static_tests_required"])

    print(f"{'pair':12s} {'BIC':>3s} {'HQIC':>4s}  "
          f"{'trace@1':>8s} {'@2':>7s} {'@3':>7s} {'@4':>7s}  {'cv5':>5s}  classification@[1..4]")
    any_flip = False
    for pid, pair in pairs.items():
        df = pair.df
        sel = VAR(df.values).select_order(maxlags=8)
        traces, cls = [], []
        cv5 = None
        for lag in (1, 2, 3, 4):
            res = coint_johansen(df.values, det_order, lag)
            ts, cv5 = float(res.lr1[0]), float(res.cvt[0, 1])
            traces.append(ts)
            joh_rej = ts > cv5
            passed = int(stage2[pid]["eg_reject"]) + int(joh_rej) + int(stage2[pid]["po_reject"])
            cls.append(passed >= required)
        flip = len(set(cls)) > 1
        any_flip = any_flip or flip
        print(f"{pid:12s} {int(sel.bic):>3d} {int(sel.hqic):>4d}  "
              f"{traces[0]:8.2f} {traces[1]:7.2f} {traces[2]:7.2f} {traces[3]:7.2f}  "
              f"{cv5:5.2f}  {cls}{'  <-- FLIPS' if flip else ''}")

    print(f"\nAny classification flips across lags 1-4: {any_flip}")
    print("(BIC/HQIC are VAR orders on the log-level system; k_ar_diff = order - 1.)")


if __name__ == "__main__":
    main()
