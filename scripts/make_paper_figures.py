"""The four figures embedded in the paper, rendered from saved results.

Everything here reads stage-4/5 artifacts from results/ - no pipeline
re-computation - so the paper figures re-render in seconds after a style
change. run_stage_5.py imports render_cost_sweep and render_event_study from
this module, so a full stage-5 re-run produces identical styling.

Figure conventions follow the working-paper norm: no in-figure titles or
narrative text (interpretation lives in the markdown captions), panel labels
in the "Panel A." form, grayscale-safe encoding via line style and fill.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.plotting import apply_style, PALETTE


ANCHOR_LEFT  = "GOOG_GOOGL"
ANCHOR_RIGHT = "GLD_GDX"
COINTEGRATED_HEADLINE = ["GOOG_GOOGL", "V_MA"]


def _display(pid: str) -> str:
    return pid.replace("_", "/")


def render_per_fold_sharpe_panel(stage4: dict, out_path: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)

    for panel, ax, pid in zip("AB", axes, [ANCHOR_LEFT, ANCHOR_RIGHT]):
        folds = stage4[pid]["folds"]
        S = np.array([f["sharpe_oos_net"] for f in folds], dtype=float)
        idx = np.arange(len(S))
        composite = stage4[pid]["summary"]["composite_sharpe_oos_net"]

        # Positive folds gray-filled, negative folds open: survives grayscale.
        face = [PALETTE["pos"] if (np.isfinite(s) and s > 0) else "white" for s in S]
        ax.bar(idx, S, color=face, edgecolor="black", linewidth=0.5, width=0.72)
        ax.axhline(0, color="black", lw=0.7)
        ax.axhline(composite, color="black", lw=0.8, ls="--",
                   label=f"composite = {composite:.2f}")
        ax.set_xticks(idx)
        ax.set_xticklabels([str(i) for i in idx], fontsize=7)
        ax.set_xlabel("walk-forward fold")
        ax.set_title(f"Panel {panel}. {_display(pid)}", loc="left")
        ax.legend(loc="upper right")

    axes[0].set_ylabel("per-fold OOS Sharpe (net, 3 bps)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def render_per_fold_beta_panel(stage4: dict, out_path: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)

    for panel, ax, pid in zip("AB", axes, [ANCHOR_LEFT, ANCHOR_RIGHT]):
        folds = stage4[pid]["folds"]
        b = np.array([f["beta_canonical"] for f in folds], dtype=float)
        idx = np.arange(len(b))
        b_min, b_max = float(np.nanmin(b)), float(np.nanmax(b))

        ax.fill_between(idx, b_min, b_max, color=PALETTE["band"], alpha=0.25, lw=0)
        ax.plot(idx, b, marker="o", color=PALETTE["ink"], lw=1.1, markersize=3.5)
        ax.axhline(1.0, color=PALETTE["muted"], lw=0.7, ls=":")
        ax.set_xticks(idx)
        ax.set_xticklabels([str(i) for i in idx], fontsize=7)
        ax.set_xlabel("walk-forward fold")
        ax.set_title(f"Panel {panel}. {_display(pid)}", loc="left")

    # Identical y-axis on both - the whole point of the contrast.
    for ax in axes:
        ax.set_ylim(0.18, 1.10)
    axes[0].set_ylabel("canonical hedge ratio β")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def render_cost_sweep(sweep_tables: dict[str, pd.DataFrame],
                      breakevens: dict[str, float], fig_path: Path) -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(6.8, 3.9))
    styles = {
        "GOOG_GOOGL": dict(color=PALETTE["ink"], ls="-", marker="o"),
        "V_MA":       dict(color=PALETTE["gray"], ls="--", marker="s"),
    }
    for pid, df in sweep_tables.items():
        st = styles.get(pid, dict(color=PALETTE["muted"], ls="-", marker="."))
        ax.plot(df["cost_bps"], df["sharpe_net"], markersize=3.5, lw=1.1,
                label=_display(pid), **st)
        ax.axvline(breakevens[pid], color=st["color"], ls=":", lw=0.7)
    ax.axhline(0, color="black", lw=0.7)
    ax.axvline(3.0, color=PALETTE["faint"], lw=1.0, label="baseline (3 bps)")
    ax.set_xlabel("round-trip cost (bps)")
    ax.set_ylabel("composite walk-forward OOS Sharpe (net)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)


def render_event_study(event_times, rule_mean, rule_lo, rule_hi, n_rule,
                       plac_mean, plac_lo, plac_hi, n_plac,
                       ou_curve, fig_path: Path) -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    t = np.asarray(event_times, dtype=float)

    # Rule: solid band. Placebo: hatched band. Distinct without color.
    ax.fill_between(t, np.asarray(rule_lo, float), np.asarray(rule_hi, float),
                    color=PALETTE["band"], alpha=0.35, lw=0,
                    label=f"rule 95% CI (n = {n_rule})")
    ax.plot(t, np.asarray(rule_mean, float), color=PALETTE["ink"], lw=1.4,
            label="rule mean")
    ax.fill_between(t, np.asarray(plac_lo, float), np.asarray(plac_hi, float),
                    facecolor="none", edgecolor=PALETTE["gray"], hatch="///", lw=0,
                    label=f"placebo 95% CI (n = {n_plac})")
    ax.plot(t, np.asarray(plac_mean, float), color=PALETTE["gray"], lw=1.1, ls="--",
            label="placebo mean")
    ax.plot(t, np.asarray(ou_curve, float), color="black", lw=1.0, ls=":",
            label="OU closed-form baseline")

    ax.axhline(0, color="black", lw=0.5)
    ax.axvline(0, color=PALETTE["muted"], lw=0.7, ls="--")
    ax.set_xlabel("event time (trading days from entry)")
    ax.set_ylabel("aligned z-score")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)


def main():
    results_dir = ROOT / "results"
    fig_dir = ROOT / "figures" / "stage5"
    fig_dir.mkdir(parents=True, exist_ok=True)

    stage4 = json.loads((results_dir / "stage4_walkforward.json").read_text())
    stage5 = json.loads((results_dir / "stage5_summary.json").read_text())
    event = json.loads((results_dir / "stage5" / "event_study.json").read_text())

    render_per_fold_sharpe_panel(stage4, fig_dir / "per_fold_sharpe_panel.png")
    print(f"  wrote {fig_dir / 'per_fold_sharpe_panel.png'}")

    render_per_fold_beta_panel(stage4, fig_dir / "per_fold_beta_panel.png")
    print(f"  wrote {fig_dir / 'per_fold_beta_panel.png'}")

    sweep_tables = {pid: pd.DataFrame(stage5["cost_sweep"][pid])
                    for pid in COINTEGRATED_HEADLINE}
    breakevens = {pid: float(stage5["breakeven_bps"][pid])
                  for pid in COINTEGRATED_HEADLINE}
    render_cost_sweep(sweep_tables, breakevens, fig_dir / "cost_sweep__cointegrated.png")
    print(f"  wrote {fig_dir / 'cost_sweep__cointegrated.png'}")

    p = event["pooled"]
    render_event_study(p["event_times"],
                       p["mean_curve_rule"], p["ci_lo_rule"], p["ci_hi_rule"],
                       p["n_rule_events"],
                       p["mean_curve_placebo"], p["ci_lo_placebo"], p["ci_hi_placebo"],
                       p["n_placebo_events"],
                       p["ou_curve"], fig_dir / "event_study__pooled.png")
    print(f"  wrote {fig_dir / 'event_study__pooled.png'}")


if __name__ == "__main__":
    main()
