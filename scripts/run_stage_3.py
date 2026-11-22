"""Stage 3 orchestrator: spread + half-life + signal grid + single-split backtest.

For each pair we:
  1. Fit the cointegrating vector on the TRAINING window only (lower-AIC ordering).
  2. Apply it to compute the full-sample log-spread.
  3. Compute OU/AR(1) half-life on the training spread; flag pathological values.
  4. Grid-search the 12-cell signal grid on NET training Sharpe at the 3 bps baseline.
  5. Apply the chosen params unchanged to the test window; report train/test/full Sharpe,
     annualized return, and entry counts.

Sanity-check anchors (per stage-2 approval directive):
  - GOOG/GOOGL half-life must be short (days, not months).
  - Any pair with HL > test_window or HL < floor flags and we stop for review.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from src.spread import fit_cointegrating_vector, compute_spread
from src.backtest import run_pair_stage3, SingleSplitResult
from src.plotting import apply_style, PALETTE


def _load_stage2(results_dir: Path) -> dict:
    payload = json.loads((results_dir / "stage2_cointegration.json").read_text())
    return {pid: bool(v["cointegrated"]) for pid, v in payload.items()}


def render_pair_detail(pair, fit, spread, params, artifacts, split_ts, fig_path: Path):
    z = artifacts["z"]
    pnl = artifacts["pnl"]
    pos = artifacts["position"]

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    title = (f"{pair.pair_id}  |  {fit.y_var} = a + b * {fit.x_var}  "
             f"|  a={fit.alpha:.4f}, b={fit.beta:.4f}  |  HL={fit.half_life_days:.1f}d  "
             f"|  entry_z={params['entry_z']}, stop_z={params['stop_z']}, lookback={params['lookback']}")
    fig.suptitle(title, y=0.995, fontsize=10)

    ax = axes[0]
    ax.plot(spread.index, spread.values, color=PALETTE["spread"], lw=0.8, label="log-spread")
    ax.axhline(0, color="black", lw=0.6, alpha=0.4)
    ax.axhline(fit.train_residual_std * params["entry_z"], color=PALETTE["leg1"], lw=0.6, ls="--", alpha=0.5,
               label=f"+/-{params['entry_z']}*sigma_train")
    ax.axhline(-fit.train_residual_std * params["entry_z"], color=PALETTE["leg1"], lw=0.6, ls="--", alpha=0.5)
    ax.axvline(split_ts, color=PALETTE["muted"], lw=0.8, ls="--")
    ax.set_ylabel("log-spread")
    ax.legend(loc="upper left")

    ax = axes[1]
    ax.plot(z.index, z.values, color=PALETTE["spread"], lw=0.7)
    ax.axhline(params["entry_z"], color=PALETTE["leg1"], lw=0.6, ls="--", alpha=0.6,
               label=f"+/-entry_z={params['entry_z']}")
    ax.axhline(-params["entry_z"], color=PALETTE["leg1"], lw=0.6, ls="--", alpha=0.6)
    ax.axhline(params["stop_z"], color=PALETTE["neg"], lw=0.6, ls=":", alpha=0.7,
               label=f"+/-stop_z={params['stop_z']}")
    ax.axhline(-params["stop_z"], color=PALETTE["neg"], lw=0.6, ls=":", alpha=0.7)
    ax.axhline(0, color="black", lw=0.4, alpha=0.4)
    ax.axvline(split_ts, color=PALETTE["muted"], lw=0.8, ls="--")
    ax.set_ylabel("z-score")
    ax.legend(loc="upper left")

    ax = axes[2]
    cum_net = pnl["net_pnl"].fillna(0).cumsum()
    ax.plot(cum_net.index, cum_net.values, color=PALETTE["pos"], lw=1.0, label="cumulative net P&L (log-return units)")
    ax.axhline(0, color="black", lw=0.4, alpha=0.4)
    ax.axvline(split_ts, color=PALETTE["muted"], lw=0.8, ls="--", label="train/test split")
    ax.set_ylabel("cumulative net P&L")
    ax.set_xlabel("date")
    ax.legend(loc="upper left")

    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)


def render_grid_cumpnl(pairs, results, artifacts_all, split_ts, fig_path: Path):
    apply_style()
    n = len(pairs)
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, 2, figsize=(11, 2.2 * nrows), sharex=False)
    axes = np.array(axes).reshape(-1)
    for ax, pid in zip(axes, pairs.keys()):
        pnl = artifacts_all[pid]["pnl"]["net_pnl"].fillna(0).cumsum()
        r = results[pid]
        color = PALETTE["pos"] if r.cointegrated else PALETTE["muted"]
        ax.plot(pnl.index, pnl.values, color=color, lw=1.0)
        ax.axhline(0, color="black", lw=0.4, alpha=0.4)
        ax.axvline(split_ts, color=PALETTE["muted"], lw=0.8, ls="--")
        cointegrated = "coint" if r.cointegrated else "not-coint"
        ax.set_title(f"{pid}  ({cointegrated})  S_train={r.sharpe_train_net:.2f}  S_test={r.sharpe_test_net:.2f}",
                     loc="left", fontsize=9)
    for ax in axes[n:]:
        ax.set_visible(False)
    fig.suptitle("Stage 3: cumulative net P&L at chosen params (3 bps baseline cost)", y=1.005)
    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)


def main():
    cfg = load_config()
    print(f"Loaded config (author={cfg['project']['author']})")
    pairs = load_universe(cfg, refresh=False)

    results_dir = ROOT / "results"
    fig_dir = ROOT / "figures" / "stage3"
    fig_dir.mkdir(parents=True, exist_ok=True)
    stage2_coint = _load_stage2(results_dir)
    split_ts = pd.Timestamp(cfg["data"]["train_test_split_date"])

    apply_style()
    results: dict[str, SingleSplitResult] = {}
    artifacts_all = {}
    surfaces = {}
    fits = {}

    print("\n========== STAGE 3: SPREAD + SIGNAL + SINGLE-SPLIT ==========")
    for pid, pair in pairs.items():
        print(f"  {pid:12s} fitting alpha/beta, computing HL, grid-searching ...", flush=True)
        fit = fit_cointegrating_vector(pair.train, pair.legs, pid, cfg)
        spread = compute_spread(pair.df, fit)
        result, surface, artifacts = run_pair_stage3(
            pair, fit, spread, cfg, cointegrated=stage2_coint.get(pid, False)
        )
        results[pid] = result
        surfaces[pid] = surface
        artifacts_all[pid] = artifacts
        fits[pid] = fit

        # Per-pair detail figure
        render_pair_detail(
            pair, fit, spread,
            params={"entry_z": result.entry_z, "stop_z": result.stop_z, "lookback": result.lookback},
            artifacts=artifacts,
            split_ts=split_ts,
            fig_path=fig_dir / f"{pid}_detail.png",
        )

    # Save results
    payload = {pid: asdict(r) for pid, r in results.items()}
    def _native(o):
        if isinstance(o, (np.bool_,)): return bool(o)
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.floating,)): return float(o)
        return o
    payload_clean = {k: {kk: _native(vv) for kk, vv in v.items()} for k, v in payload.items()}
    (results_dir / "stage3_singlesplit.json").write_text(json.dumps(payload_clean, indent=2, default=str))

    # Build the headline table
    rows = []
    for pid, r in results.items():
        rows.append({
            "pair_id": pid,
            "y~x":          f"{r.y_var}~{r.x_var}",
            "beta":         r.beta,
            "HL_days":      r.half_life_days,
            "entry_z":      r.entry_z,
            "lookback":     r.lookback,
            "n_train":      r.n_entries_train,
            "n_test":       r.n_entries_test,
            "S_train_gross": r.sharpe_train_gross,
            "S_train_net":  r.sharpe_train_net,
            "S_test_gross": r.sharpe_test_gross,
            "S_test_net":   r.sharpe_test_net,
            "AnnRet_train": r.annret_train_net,
            "AnnRet_test":  r.annret_test_net,
            "cointegrated": r.cointegrated,
            "HL_flag":      r.half_life_flag or "ok",
        })
    table = pd.DataFrame(rows).set_index("pair_id")
    table.to_csv(results_dir / "stage3_singlesplit.csv")

    # Save surfaces
    surf_dir = results_dir / "stage3_param_surfaces"
    surf_dir.mkdir(parents=True, exist_ok=True)
    for pid, s in surfaces.items():
        s.to_csv(surf_dir / f"{pid}.csv", index=False)

    # Render grid figure
    render_grid_cumpnl(pairs, results, artifacts_all, split_ts,
                       fig_path=fig_dir / "00_cum_pnl_grid.png")

    # Print headlines
    print("\n========== STAGE 3 HEADLINE (cost = %.1f bps round-trip) ==========" %
          cfg["costs"]["baseline_round_trip_bps"])
    disp = table.copy()
    for c in ["beta", "HL_days", "S_train_gross", "S_train_net",
              "S_test_gross", "S_test_net", "AnnRet_train", "AnnRet_test"]:
        disp[c] = disp[c].map(lambda v: f"{v:.3f}" if pd.notna(v) else "nan")
    print(disp.to_string())

    # Sanity-check anchors
    print("\n========== STAGE 3 SANITY CHECKS ==========")
    stop_flags = []
    soft_flags = []
    for pid, r in results.items():
        flag = r.half_life_flag
        if not flag:
            print(f"  ok:        {pid}  HL={r.half_life_days:.1f} d  (raw={r.half_life_raw_days:.1f})")
        elif flag in ("non_mean_reverting", "above_test_window", "below_floor"):
            stop_flags.append((pid, r.half_life_days, flag))
            print(f"  STOP FLAG: {pid}  HL={r.half_life_days}  reason={flag}")
        else:
            soft_flags.append((pid, r.half_life_raw_days, flag))
            print(f"  soft:      {pid}  HL={r.half_life_days:.1f} d  reason={flag}")

    goog = results.get("GOOG_GOOGL")
    if goog is not None:
        days_or_months = "days" if goog.half_life_days < 60 else "MONTHS"
        print(f"\n  GOOG/GOOGL HL = {goog.half_life_days:.1f} d  ->  {days_or_months}")
        if goog.half_life_days >= 60:
            stop_flags.append(("GOOG_GOOGL", goog.half_life_days, "GOOG_GOOGL_HL_not_short"))

    if stop_flags:
        print("\n!! STAGE 3 STOP FLAGS DETECTED - stopping for review before stage 4 !!")
    elif soft_flags:
        print(f"\nStage 3 stop-anchors OK. {len(soft_flags)} soft flag(s) for transparency.")
    else:
        print("\nStage 3 anchors OK.")
    print("\n========== STAGE 3 COMPLETE - STOP FOR APPROVAL ==========")


if __name__ == "__main__":
    main()
