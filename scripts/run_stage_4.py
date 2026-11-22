"""Stage 4 orchestrator: walk-forward, refit-both.

For each pair we slide a 504-day train / 126-day OOS window across the FULL history
(not just the post-2022 test window). At each fold boundary we refit α/β AND re-select
the (entry_z, lookback) cell on net training Sharpe @ baseline cost, then apply both
unchanged to the next 126 OOS bars.

Per pair, we report:
  - Per-fold OOS Sharpe series (the dispersion is the real readout, not the composite).
  - Composite OOS Sharpe (concatenated, boundary-unwind costs included).
  - Per-fold β (and a canonical-direction β so values are comparable across folds even
    when the AIC-preferred LHS flips).
  - Per-fold selected cell (a cell that clusters across folds is independent evidence of
    a structural edge; cells that scatter say stage 3's pick was a lucky draw).

User directive: stop after this and bring the table back before stage 5 (costs/capacity).

Methodological note on interpretation that ships with the table:
  Walk-forward composites will likely come in higher than stage-3 single-split tests.
  This reflects BOTH the refitting benefit AND that the full-history walk-forward folds
  back in 2020 and 2022 - both mean-reversion-friendly regimes - whereas the stage-3
  test window was the relentlessly trending 2023-2025 mega-cap regime. A higher composite
  is not on its own evidence that walk-forward is "more rigorous = better". The per-fold
  dispersion and the β drift are what tell you the edge is robust.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from src.backtest import run_pair_stage4_walkforward, WalkForwardResult


def _native(o):
    if isinstance(o, (np.bool_,)):   return bool(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)):return float(o)
    return o


def _load_stage2(results_dir: Path) -> dict:
    payload = json.loads((results_dir / "stage2_cointegration.json").read_text())
    return {pid: bool(v["cointegrated"]) for pid, v in payload.items()}


def _load_stage3(results_dir: Path) -> pd.DataFrame:
    return pd.read_csv(results_dir / "stage3_singlesplit.csv").set_index("pair_id")


def _fmt(v, n=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "nan"
    return f"{v:.{n}f}"


def main():
    cfg = load_config()
    print(f"Loaded config (author={cfg['project']['author']})")
    pairs = load_universe(cfg, refresh=False)

    results_dir = ROOT / "results"
    out_dir = results_dir / "stage4_walkforward"
    out_dir.mkdir(parents=True, exist_ok=True)
    stage2_coint = _load_stage2(results_dir)
    stage3 = _load_stage3(results_dir)

    print("\n========== STAGE 4: WALK-FORWARD (refit-both, full history) ==========")
    wf = cfg["backtest"]["walk_forward"]
    print(f"  train={wf['train_window_days']}d  test={wf['test_window_days']}d  "
          f"step={wf['step_days']}d  cost={cfg['costs']['baseline_round_trip_bps']} bps")

    results: dict[str, WalkForwardResult] = {}
    for pid, pair in pairs.items():
        print(f"  {pid:12s} walk-forward refit-both ...", flush=True)
        results[pid] = run_pair_stage4_walkforward(pair, cfg)

    # ---- Save: per-pair fold tables, composite table, JSON payload ----
    composite_rows = []
    for pid, r in results.items():
        # Per-fold detail
        fold_rows = [{**asdict(f)} for f in r.folds]
        pd.DataFrame(fold_rows).to_csv(out_dir / f"{pid}__folds.csv", index=False)

        # Composite row
        s3_row = stage3.loc[pid] if pid in stage3.index else None
        composite_rows.append({
            "pair_id":              pid,
            "cointegrated":         stage2_coint.get(pid, False),
            "n_folds":              r.n_folds,
            "S_oos_gross":          r.composite_sharpe_oos_gross,
            "S_oos_net":            r.composite_sharpe_oos_net,
            "AnnRet_oos_net":       r.composite_annret_oos_net,
            "n_entries_oos":        r.composite_n_entries_oos,
            "pct_folds_positive":   r.pct_folds_positive_net,
            "modal_entry_z":        r.modal_entry_z,
            "modal_lookback":       r.modal_lookback,
            "pct_at_modal_cell":    r.pct_folds_at_modal_cell,
            "s3_entry_z":           float(s3_row["entry_z"]) if s3_row is not None else float("nan"),
            "s3_lookback":          int(s3_row["lookback"]) if s3_row is not None else -1,
            "s3_S_test_net":        float(s3_row["S_test_net"]) if s3_row is not None else float("nan"),
        })
    composite = pd.DataFrame(composite_rows).set_index("pair_id")
    composite.to_csv(results_dir / "stage4_walkforward.csv")

    payload = {pid: {
        "summary": {k: _native(v) for k, v in asdict(r).items() if k != "folds"},
        "folds": [{k: _native(v) for k, v in asdict(f).items()} for f in r.folds],
    } for pid, r in results.items()}
    (results_dir / "stage4_walkforward.json").write_text(
        json.dumps(payload, indent=2, default=str)
    )

    # ---- Print the composite headline ----
    print("\n========== STAGE 4 HEADLINE: per-pair composite OOS ==========")
    disp = composite.copy()
    for c in ["S_oos_gross", "S_oos_net", "AnnRet_oos_net",
              "pct_folds_positive", "pct_at_modal_cell",
              "s3_S_test_net"]:
        disp[c] = disp[c].map(lambda v: _fmt(v, 3 if "Ret" in c else 2))
    print(disp.to_string())

    # ---- Print per-fold detail for the two diagnostic anchors ----
    for anchor in ["GOOG_GOOGL", "GLD_GDX"]:
        if anchor not in results:
            continue
        r = results[anchor]
        print(f"\n---------- {anchor}: per-fold OOS detail ----------")
        rows = []
        for f in r.folds:
            rows.append({
                "fold":          f.fold_idx,
                "oos_window":    f"{f.oos_start} .. {f.oos_end}",
                "y_var":         f.y_var,
                "beta":          f.beta,
                "beta_canon":    f.beta_canonical,
                "HL_d":          f.half_life_days,
                "entry_z":       f.entry_z,
                "lookback":      f.lookback,
                "S_train_net":   f.sharpe_train_net,
                "S_oos_net":     f.sharpe_oos_net,
                "AnnRet_oos":    f.annret_oos_net,
                "n_entries":     f.n_entries_oos,
            })
        df = pd.DataFrame(rows)
        for c in ["beta", "beta_canon", "HL_d", "S_train_net", "S_oos_net", "AnnRet_oos"]:
            df[c] = df[c].map(lambda v: _fmt(v, 3))
        print(df.to_string(index=False))

    # ---- Diagnostic flags the user asked us to watch ----
    print("\n========== STAGE 4 DIAGNOSTIC ANCHORS ==========")
    goog = results.get("GOOG_GOOGL")
    if goog is not None:
        pos_folds = sum(1 for f in goog.folds
                        if np.isfinite(f.sharpe_oos_net) and f.sharpe_oos_net > 0)
        total = len(goog.folds)
        print(f"  GOOG_GOOGL: {pos_folds}/{total} folds positive OOS  "
              f"(target: most folds positive, not carried by 1-2)")
        print(f"  GOOG_GOOGL: modal cell entry_z={goog.modal_entry_z}, "
              f"lookback={goog.modal_lookback}  "
              f"({goog.pct_folds_at_modal_cell:.0%} of folds at modal)")

    gld = results.get("GLD_GDX")
    if gld is not None:
        oos_sharpes = [f.sharpe_oos_net for f in gld.folds if np.isfinite(f.sharpe_oos_net)]
        if oos_sharpes:
            arr = np.array(oos_sharpes)
            print(f"  GLD_GDX: per-fold OOS Sharpe  mean={arr.mean():.2f}  "
                  f"std={arr.std(ddof=1):.2f}  min={arr.min():.2f}  max={arr.max():.2f}")
            s3_test = stage3.loc["GLD_GDX", "S_test_net"] if "GLD_GDX" in stage3.index else float("nan")
            print(f"  GLD_GDX: stage-3 single-split S_test_net={s3_test:.2f}  "
                  f"composite walk-forward S_oos_net={gld.composite_sharpe_oos_net:.2f}  "
                  f"(target: dispersion makes the s3 outperformance look like regime luck)")

    print("\n========== STAGE 4 COMPLETE - STOP FOR APPROVAL ==========")


if __name__ == "__main__":
    main()
