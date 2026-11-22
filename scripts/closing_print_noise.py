"""Closing-price noise: how much of the same-close result needs no cointegration fit.

Section 4.10 of the paper. The headline composite assumes each trade fills at the
close that generated the signal. This script checks whether the gap between that
convention and a next-open fill is an edge or noise in the closing price, using
two rules that involve no regression, no refit and no walk-forward.

The hedge ratio is fixed at 1, so the spread is just the log price ratio:

  GOOG_GOOGL   log GOOGL - log GOOG
  V_MA         log V - log MA

Rules, both decided on the close of bar t:

  z-rule      the paper's own state machine (src.signals) at cell (1.5, 15),
              stop 3.5, on the fixed-ratio spread
  reversal    pos = -sign(ds_close): bet against whatever the ratio did that
              day. No parameters.

Fill conventions match scripts/execution_conventions.py:

  same close  gross[u] = pos[u-1] * ds_close[u]
  next open   gross[u] = pos[u-2] * ds_open[u]
  next close  gross[u] = pos[u-2] * ds_close[u]

Costs are the baseline round trip, charged on |d position| as everywhere else.
Sharpes are evaluated on the walk-forward's 2,520 OOS bars (index positions 504
to 3023) so they are comparable with the composite. The lag-1 autocorrelation
of the daily spread change is taken over the full sample.

Open prices come from data/raw_open (see scripts/fetch_open_ratio.py), so the
close snapshot is untouched.

Usage:
    python scripts/closing_print_noise.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from src.signals import rolling_zscore, generate_positions
from src.backtest import sharpe

PAIRS = ["GOOG_GOOGL", "V_MA"]
CONVENTIONS = ["same_close", "next_open", "next_close"]

# (long leg, short leg) of the fixed-ratio spread, as stated in the docstring.
SPREAD_LEGS = {"GOOG_GOOGL": ("GOOGL", "GOOG"), "V_MA": ("V", "MA")}

# The z-rule cell: the walk-forward's most common selection on GOOG/GOOGL.
ENTRY_Z, LOOKBACK = 1.5, 15


def load_open_frame(pair, cfg) -> pd.DataFrame:
    """Reconstructed open log-prices, aligned to the pair's analysis frame."""
    out_dir = ROOT / "data" / "raw_open"
    cols = {}
    for leg in pair.legs:
        files = sorted(out_dir.glob(f"{leg}__*.parquet"))
        if not files:
            raise RuntimeError(f"no open-ratio file for {leg}; run fetch_open_ratio.py")
        d = pd.read_parquet(files[-1])
        cols[leg] = d["open_recon"]
    frame = pd.DataFrame(cols)
    frame.index = pd.to_datetime(frame.index)
    frame = frame.reindex(pair.df.index)
    if cfg["data"].get("input_space", "log") == "log":
        frame = np.log(frame)
    return frame


def gross_by_convention(pos: pd.Series, ds_close: pd.Series, ds_open: pd.Series) -> dict:
    return {
        "same_close": pos.shift(1) * ds_close,
        "next_open": pos.shift(2) * ds_open,
        "next_close": pos.shift(2) * ds_close,
    }


def evaluate(pos: pd.Series, ds_close: pd.Series, ds_open: pd.Series,
             oos: pd.Index, cost_bps: float) -> dict:
    """Gross and net Sharpe on the OOS bars under each fill convention."""
    cost = pos.diff().fillna(0.0).abs() * (cost_bps / 2.0) / 1e4
    out = {}
    for conv, g in gross_by_convention(pos, ds_close, ds_open).items():
        out[conv] = {"gross": sharpe(g.loc[oos]), "net": sharpe((g - cost).loc[oos])}
    return out


def run_pair(pair, cfg) -> list[dict]:
    if cfg["data"].get("input_space", "log") != "log":
        raise RuntimeError("closing_print_noise assumes the log-price analysis frame")

    wfc = cfg["backtest"]["walk_forward"]
    train_w, test_w = int(wfc["train_window_days"]), int(wfc["test_window_days"])
    n_folds = (len(pair.df) - train_w) // test_w
    oos = pair.df.index[train_w:train_w + n_folds * test_w]

    cost_bps = float(cfg["costs"]["baseline_round_trip_bps"])
    (stop_z,) = (float(v) for v in cfg["signal"]["grid"]["stop_z"])

    long_leg, short_leg = SPREAD_LEGS[pair.pair_id]
    open_frame = load_open_frame(pair, cfg)
    s_close = pair.df[long_leg] - pair.df[short_leg]
    s_open = open_frame[long_leg] - open_frame[short_leg]
    ds_close, ds_open = s_close.diff(), s_open.diff()

    rules = {
        "z_rule": generate_positions(rolling_zscore(s_close, LOOKBACK), ENTRY_Z, stop_z),
        "reversal": -np.sign(ds_close).fillna(0.0),
    }

    rows = [
        {"pair": pair.pair_id, "quantity": "autocorr_lag1_dspread", "rule": "",
         "convention": "close", "value": float(ds_close.autocorr(1)), "n_bars": len(ds_close) - 1},
        {"pair": pair.pair_id, "quantity": "autocorr_lag1_dspread", "rule": "",
         "convention": "open", "value": float(ds_open.autocorr(1)), "n_bars": len(ds_open) - 1},
    ]
    for rule, pos in rules.items():
        res = evaluate(pos.astype(float), ds_close, ds_open, oos, cost_bps)
        for conv in CONVENTIONS:
            for kind in ("gross", "net"):
                rows.append({"pair": pair.pair_id, "quantity": f"sharpe_{kind}", "rule": rule,
                             "convention": conv, "value": res[conv][kind], "n_bars": len(oos)})
    return rows


def main() -> None:
    cfg = load_config()
    pairs = load_universe(cfg, refresh=False)

    rows = []
    for pid in PAIRS:
        rows.extend(run_pair(pairs[pid], cfg))
    df = pd.DataFrame(rows)

    def val(pid, quantity, rule, conv):
        m = df[(df.pair == pid) & (df.quantity == quantity) & (df.rule == rule)
               & (df.convention == conv)]
        return float(m["value"].iloc[0])

    n_oos = int(df.loc[df.quantity == "sharpe_net", "n_bars"].iloc[0])
    print("=" * 96)
    print(f"CLOSING-PRICE NOISE, hedge ratio fixed at 1. Sharpes on {n_oos:,} OOS bars.")
    print("=" * 96)
    hdr = f"{'':58s}{'GOOG/GOOGL':>18s}{'V/MA':>20s}"
    print(hdr)
    print(f"{'lag-1 autocorr of daily spread change, close, full sample':58s}"
          + "".join(f"{val(p, 'autocorr_lag1_dspread', '', 'close'):>19.2f}" for p in PAIRS))
    print(f"{'same, open':58s}"
          + "".join(f"{val(p, 'autocorr_lag1_dspread', '', 'open'):>19.2f}" for p in PAIRS))

    def triple(pid, rule, kind):
        return " / ".join(f"{val(pid, f'sharpe_{kind}', rule, c):.2f}" for c in CONVENTIONS)

    print()
    print("same close / next open / next close")
    for label, rule, kind in [
        (f"z-rule ({ENTRY_Z}, {LOOKBACK}, stop 3.5), net S", "z_rule", "net"),
        (f"z-rule ({ENTRY_Z}, {LOOKBACK}, stop 3.5), gross S", "z_rule", "gross"),
        ("one-day reversal pos = -sign(ds), gross S", "reversal", "gross"),
        ("one-day reversal pos = -sign(ds), net S", "reversal", "net"),
    ]:
        print(f"{label:46s}" + "".join(f"{triple(p, rule, kind):>25s}" for p in PAIRS))

    out = ROOT / "results" / "closing_print_noise.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nwrote {out.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
