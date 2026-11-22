"""Task 3: composite net Sharpe under three execution conventions.

The signal is always formed on the CLOSE of bar t, which is the only price a
daily-close pipeline observes. What varies is where the resulting trade fills.

  same close  fill at the close of the signal bar   gross[u] = pos[u-1] * ds_close[u]
  next open   fill at the open of bar t+1           gross[u] = pos[u-2] * ds_open[u]
  next close  fill at the close of bar t+1          gross[u] = pos[u-2] * ds_close[u]

Same-close is the standard vector-backtest convention and the one the paper is
built on; it is mildly optimistic because it fills at the price that generated the
signal. Next-close is the fully conservative bound. Next-open sits between and is
the closest of the three to how the trade would actually be worked.

Open prices come from data/raw_open (cached adjusted close times the same-day
Open/Close ratio), so the 2026-05-30 close snapshot is untouched. See
scripts/fetch_open_ratio.py.

The alpha/beta and the selected cells are the LOCKED stage-4 values; only the fill
price moves. Gross is differenced within folds throughout (see compute_composite_pnl).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import load_universe
from src.spread import fit_cointegrating_vector, compute_spread, select_ordering
from src.backtest import fold_oos_eval, sharpe, annualized_return

ANN = np.sqrt(252)
CONVENTIONS = ["same_close", "next_open", "next_close"]


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


def composite_pnl_by_convention(pair, cfg, folds_meta, cost_bps, convention):
    """Per-fold gross on the chosen fill series; costs on the concatenated position."""
    legs = list(pair.legs)
    wfc = cfg["backtest"]["walk_forward"]
    TW, STEP = int(wfc["train_window_days"]), int(wfc["step_days"])
    open_frame = load_open_frame(pair, cfg) if convention == "next_open" else None

    gross_parts, pos_parts = [], []
    for k, f in enumerate(folds_meta):
        tr = pair.df.loc[f["train_start"]:f["train_end"]].index
        oo = pair.df.loc[f["oos_start"]:f["oos_end"]].index
        fit = fit_cointegrating_vector(
            pair.df.loc[tr], legs, pair.pair_id, cfg,
            force_ordering=select_ordering(pair.df.iloc[0:k * STEP + TW], legs))
        sp_close = compute_spread(pair.df.loc[tr.append(oo)], fit)
        _, pos, _ = fold_oos_eval(sp_close, tr, oo, float(f["entry_z"]),
                                  float(f["stop_z"]), int(f["lookback"]), cost_bps)

        if convention == "same_close":
            fill, lag = sp_close.loc[oo], 1
        elif convention == "next_close":
            fill, lag = sp_close.loc[oo], 2
        else:
            fill, lag = compute_spread(open_frame.loc[oo], fit), 2

        g = pos.shift(lag) * fill.diff()
        g.iloc[:lag] = 0.0        # entered the fold flat
        gross_parts.append(g)
        pos_parts.append(pos)

    gross = pd.concat(gross_parts)
    gross = gross[~gross.index.duplicated(keep="first")]
    position = pd.concat(pos_parts)
    position = position[~position.index.duplicated(keep="first")]
    cost = position.diff().fillna(0.0).abs() * (cost_bps / 2.0) / 1e4
    return pd.DataFrame({"gross_pnl": gross, "cost": cost, "net_pnl": gross - cost,
                         "position": position})


def breakeven(pair, cfg, folds_meta, convention, lo=0.0, hi=60.0, tol=0.01):
    f = lambda c: sharpe(composite_pnl_by_convention(
        pair, cfg, folds_meta, c, convention)["net_pnl"])
    if not np.isfinite(f(lo)) or f(lo) <= 0:
        return lo
    if f(hi) > 0:
        return hi
    for _ in range(60):
        if hi - lo < tol:
            break
        mid = 0.5 * (lo + hi)
        s = f(mid)
        if not np.isfinite(s):
            hi = mid
        elif s > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def days_since_entry_decomposition(pnl_frame, max_day=6):
    pos = pnl_frame["position"].fillna(0).astype(int)
    prev = pos.shift(1).fillna(0).astype(int)
    dse, k = [], 0
    for t in pos.index:
        if pos.loc[t] != 0 and prev.loc[t] == 0:
            k = 1
        elif pos.loc[t] != 0:
            k += 1
        else:
            k = 0
        dse.append(k)
    held = pd.Series(dse, index=pos.index).shift(1)
    g = pnl_frame["gross_pnl"].dropna()
    tbl = pd.DataFrame({"g": g, "d": held.reindex(g.index)})
    tbl = tbl[tbl.d > 0]
    agg = tbl.groupby(tbl.d.clip(upper=max_day)).g.agg(["count", "mean", "sum"])
    agg["pct_of_gross"] = 100 * agg["sum"] / g.sum()
    return agg


def main() -> None:
    cfg = load_config()
    pairs = load_universe(cfg, refresh=False)
    cost = float(cfg["costs"]["baseline_round_trip_bps"])
    s4 = json.loads((ROOT / "results" / "stage4_walkforward.json").read_text())

    rows = []
    for pid, pair in pairs.items():
        fm = s4[pid]["folds"]
        rec = {"pair": pid}
        for conv in CONVENTIONS:
            p = composite_pnl_by_convention(pair, cfg, fm, cost, conv)
            rec[f"S_{conv}"] = sharpe(p["net_pnl"])
            rec[f"AnnRet_{conv}"] = annualized_return(p["net_pnl"])
        rows.append(rec)

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print("=" * 104)
    print("COMPOSITE NET SHARPE BY EXECUTION CONVENTION (seam fix applied)")
    print("=" * 104)
    print(df[["pair"] + [f"S_{c}" for c in CONVENTIONS]].to_string(
        index=False, float_format=lambda v: f"{v: .4f}"))
    print()
    print(df[["pair"] + [f"AnnRet_{c}" for c in CONVENTIONS]].to_string(
        index=False, float_format=lambda v: f"{v: .4f}"))

    print("\n" + "=" * 104)
    print("BREAKEVEN ROUND-TRIP COST (bps), cointegrated pairs")
    print("=" * 104)
    be_rows = []
    for pid in ["GOOG_GOOGL", "V_MA"]:
        r = {"pair": pid}
        for conv in CONVENTIONS:
            r[f"BE_{conv}"] = breakeven(pairs[pid], cfg, s4[pid]["folds"], conv)
        be_rows.append(r)
    be = pd.DataFrame(be_rows)
    print(be.to_string(index=False, float_format=lambda v: f"{v: .2f}"))

    print("\n" + "=" * 104)
    print("GROSS P&L BY DAYS SINCE ENTRY (same-close convention)")
    print("=" * 104)
    for pid in ["GOOG_GOOGL", "V_MA"]:
        p = composite_pnl_by_convention(pairs[pid], cfg, s4[pid]["folds"], cost, "same_close")
        print(f"\n{pid}")
        print(days_since_entry_decomposition(p).to_string(
            float_format=lambda v: f"{v: .6f}"))

    df.to_csv(ROOT / "results" / "execution_conventions.csv", index=False)
    be.to_csv(ROOT / "results" / "execution_conventions_breakeven.csv", index=False)
    print("\nwrote results/execution_conventions*.csv")


if __name__ == "__main__":
    main()
