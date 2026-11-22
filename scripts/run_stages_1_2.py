"""Stages 1 and 2 orchestrator.

Stage 1 - Data layer
    Fetch (or load cached) every ticker in the universe via yfinance/Stooq.
    Align each pair on NYSE sessions. Validate invariants. Serialize per-pair
    parquet plus a summary frame. Render per-pair raw-price plots.

Stage 2 - Cointegration
    Run Engle-Granger (both LHS orderings), Johansen (trace + max-eig), and
    Phillips-Ouliaris Z_t on the full sample for every pair. Compute the
    rolling 126-bar EG p-value as a stability diagnostic. Serialize results,
    render a rolling-EG panel, print the cointegration table.

Stop. Downstream stages await approval of the cointegration table.
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
from src.data import load_universe, validate_universe, write_processed, _resolve_end_date
from src.cointegration import run_cointegration, results_to_dataframe, CointResult
from src.plotting import apply_style, PALETTE


def stage1_data(cfg: dict, refresh: bool = False):
    print("\n========== STAGE 1: DATA LAYER ==========")
    end_resolved = _resolve_end_date(cfg["data"]["end_date"])
    print(f"Study window: {cfg['data']['start_date']} -> {end_resolved}  "
          f"(end_date config = '{cfg['data']['end_date']}')")
    print(f"Train/test split: {cfg['data']['train_test_split_date']}")
    print(f"Calendar: {cfg['data']['calendar']}; drop_if_any_missing={cfg['data']['drop_if_any_missing']}")

    pairs = load_universe(cfg, refresh=refresh)

    summary = validate_universe(pairs, cfg)
    print("\nPer-pair data summary:")
    print(summary.to_string())

    # Serialize processed data + summary
    processed_dir = ROOT / "data" / "processed"
    write_processed(pairs, processed_dir)

    results_dir = ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(results_dir / "stage1_data_summary.csv")
    (results_dir / "stage1_meta.json").write_text(json.dumps({
        "end_date_resolved": end_resolved,
        "start_date": cfg["data"]["start_date"],
        "train_test_split_date": cfg["data"]["train_test_split_date"],
        "n_pairs": len(pairs),
    }, indent=2))

    # Per-pair raw price plots
    apply_style()
    fig_dir = ROOT / "figures" / "data"
    fig_dir.mkdir(parents=True, exist_ok=True)
    split_ts = pd.Timestamp(cfg["data"]["train_test_split_date"])

    n = len(pairs)
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, 2, figsize=(11, 2.4 * nrows), sharex=False)
    axes = np.array(axes).reshape(-1)
    for ax, (pid, p) in zip(axes, pairs.items()):
        ax2 = ax.twinx()
        lv = p.df_levels
        ax.plot(lv.index, lv[p.legs[0]], color=PALETTE["leg0"], label=p.legs[0])
        ax2.plot(lv.index, lv[p.legs[1]], color=PALETTE["leg1"], label=p.legs[1])
        ax.set_title(f"{pid}  ({p.legs[0]} vs {p.legs[1]})", loc="left")
        ax.axvline(split_ts, color=PALETTE["muted"], lw=0.8, ls="--")
        ax.set_ylabel(p.legs[0], color=PALETTE["leg0"])
        ax2.set_ylabel(p.legs[1], color=PALETTE["leg1"])
        ax.tick_params(axis="y", colors=PALETTE["leg0"])
        ax2.tick_params(axis="y", colors=PALETTE["leg1"])
        ax2.grid(False)
    for ax in axes[len(pairs):]:
        ax.set_visible(False)
    fig.suptitle("Stage 1: Adjusted-close raw price series (dashed line = train/test split)", y=1.005)
    fig.tight_layout()
    fig.savefig(fig_dir / "01_raw_prices_grid.png")
    plt.close(fig)
    print(f"\nSaved raw-price grid -> {fig_dir / '01_raw_prices_grid.png'}")
    print(f"Analysis frame is in {next(iter(pairs.values())).input_space}-space "
          f"(downstream tests, spread, signal, P&L).")
    return pairs


def stage2_cointegration(cfg: dict, pairs: dict):
    print("\n========== STAGE 2: COINTEGRATION ==========")
    print(f"Input space for tests: {cfg['data'].get('input_space', 'log')}-prices")
    apriori = {entry["id"]: entry.get("a_priori") for entry in cfg["universe"]}
    results: dict[str, CointResult] = {}
    rolling_all: dict[str, pd.Series] = {}
    for pid, p in pairs.items():
        print(f"  {pid:12s} running EG(x2) + Johansen + PO + rolling EG ...", flush=True)
        res, rolling = run_cointegration(
            p.df, pid, p.legs, cfg,
            input_space=p.input_space,
            a_priori=apriori.get(pid),
            df_for_corr_levels=p.df_levels,
        )
        results[pid] = res
        rolling_all[pid] = rolling

    # Serialize
    results_dir = ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    df = results_to_dataframe(results)
    df.to_csv(results_dir / "stage2_cointegration.csv")
    # JSON copy for the report's prose to read
    payload = {pid: asdict(r) for pid, r in results.items()}
    # numpy/np.bool_ to native types
    def _native(o):
        if isinstance(o, (np.bool_, )):
            return bool(o)
        if isinstance(o, (np.integer, )):
            return int(o)
        if isinstance(o, (np.floating, )):
            return float(o)
        return o
    payload = {k: {kk: _native(vv) for kk, vv in v.items()} for k, v in payload.items()}
    (results_dir / "stage2_cointegration.json").write_text(json.dumps(payload, indent=2, default=str))

    # Save rolling series
    rolling_dir = results_dir / "rolling_eg"
    rolling_dir.mkdir(parents=True, exist_ok=True)
    for pid, s in rolling_all.items():
        if len(s):
            s.to_frame().to_parquet(rolling_dir / f"{pid}.parquet")

    # Render rolling-EG panel
    apply_style()
    fig_dir = ROOT / "figures" / "cointegration"
    fig_dir.mkdir(parents=True, exist_ok=True)
    n = len(pairs)
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, 2, figsize=(11, 2.2 * nrows), sharex=False, sharey=True)
    axes = np.array(axes).reshape(-1)
    for ax, pid in zip(axes, pairs.keys()):
        s = rolling_all[pid]
        ax.plot(s.index, s.values, color=PALETTE["spread"], lw=0.9)
        ax.axhline(cfg["cointegration"]["alpha"], color=PALETTE["alpha_line"], lw=0.8, ls="--",
                   label=f"α={cfg['cointegration']['alpha']:.2f}")
        ax.set_ylim(0, 1)
        ax.set_title(f"{pid}  rolling EG p (worse of two)", loc="left")
        ax.legend(loc="upper right")
    for ax in axes[n:]:
        ax.set_visible(False)
    fig.suptitle("Stage 2: Rolling 126-bar Engle-Granger p-value on log-prices (diagnostic only)", y=1.005)
    fig.tight_layout()
    fig.savefig(fig_dir / "01_rolling_eg_grid.png")
    plt.close(fig)
    print(f"Saved rolling-EG grid -> {fig_dir / '01_rolling_eg_grid.png'}")

    # Print headline tables
    print("\nCOINTEGRATION TABLE - STATIC TESTS (full sample, log-prices):")
    static = df[[
        "eg_p_01", "eg_p_10", "eg_p_worse",
        "joh_trace_stat", "joh_trace_cv_5", "joh_trace_reject",
        "joh_maxeig_stat", "joh_maxeig_cv_5", "joh_maxeig_reject",
        "po_stat", "po_pvalue", "po_reject",
        "static_tests_passed", "cointegrated",
    ]].copy()
    for c in ["eg_p_01", "eg_p_10", "eg_p_worse", "po_pvalue"]:
        static[c] = static[c].map(lambda v: f"{v:.3f}")
    for c in ["joh_trace_stat", "joh_trace_cv_5", "joh_maxeig_stat", "joh_maxeig_cv_5", "po_stat"]:
        static[c] = static[c].map(lambda v: f"{v:.2f}")
    print(static.to_string())

    print("\nCONTEXT + DIAGNOSTICS:")
    ctx = df[[
        "n_obs", "rolling_pct_below_alpha", "corr_levels", "corr_logreturns", "notes",
    ]].copy()
    for c in ["rolling_pct_below_alpha", "corr_levels", "corr_logreturns"]:
        ctx[c] = ctx[c].map(lambda v: f"{v:.2f}")
    print(ctx.to_string())
    return results


def main():
    cfg = load_config()
    print(f"Loaded config (author={cfg['project']['author']}, seed={cfg['project']['master_seed']})")
    pairs = stage1_data(cfg, refresh=False)
    _ = stage2_cointegration(cfg, pairs)
    print("\n========== STAGES 1+2 COMPLETE - STOP FOR APPROVAL ==========")


if __name__ == "__main__":
    main()
