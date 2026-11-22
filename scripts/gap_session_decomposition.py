"""Split the first held bar's gross P&L into overnight-gap and intraday-session parts.

The close-based pipeline decides at the close of bar t-1 and is assumed filled at
that same close, so the first bar it holds runs close(t-1) -> close(t). That bar
carries roughly 40% of GOOG/GOOGL's gross P&L and 61% of V/MA's. It decomposes:

    close(t-1) -> open(t)    overnight gap     (the position is held across it)
    open(t)    -> close(t)   intraday session

    gap + session = the whole first-bar move, by construction.

A fill at the next open forfeits exactly the gap component and keeps the session
component, which is what makes this the diagnostic for the execution-timing
result. Both legs are moved together, so each component is a spread move under the
fold's own (alpha, beta): s_open(t) is the fold's cointegrating vector applied to
open prices.

The same decomposition is run on the extreme-z PLACEBO population of Section 4.6
(every bar where |z| > entry_z, ignoring the state machine, signed so the trade is
against the excursion). If the gap dominance is a property of the spread's
overnight behaviour rather than of the entry rule, the placebo shows it too.
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
from src.backtest import fold_oos_eval
from src.signals import rolling_zscore
from open_based_pipeline import open_frame

BPS = 1e4


def collect(pair, cfg, folds_meta):
    """Per-fold entry events with their gap/session split, rule and placebo."""
    legs = list(pair.legs)
    wfc = cfg["backtest"]["walk_forward"]
    TW, STEP = int(wfc["train_window_days"]), int(wfc["step_days"])
    cost = float(cfg["costs"]["baseline_round_trip_bps"])
    op_lvl = open_frame(pair, cfg)
    op_df = np.log(op_lvl) if cfg["data"].get("input_space", "log") == "log" else op_lvl

    rule_rows, plac_rows = [], []
    for k, f in enumerate(folds_meta):
        tr = pair.df.loc[f["train_start"]:f["train_end"]].index
        oo = pair.df.loc[f["oos_start"]:f["oos_end"]].index
        fit = fit_cointegrating_vector(
            pair.df.loc[tr], legs, pair.pair_id, cfg,
            force_ordering=select_ordering(pair.df.iloc[0:k * STEP + TW], legs))

        full = tr.append(oo)
        s_close = compute_spread(pair.df.loc[full], fit)
        s_open = compute_spread(op_df.loc[full], fit)      # same vector, open prices

        _, pos, z = fold_oos_eval(s_close, tr, oo, float(f["entry_z"]),
                                  float(f["stop_z"]), int(f["lookback"]), cost)

        # The entry decision is made at the close of bar t-1; the first held bar is t.
        pv = pos.fillna(0).astype(int)
        prev = pv.shift(1).fillna(0).astype(int)
        entry_bars = pv.index[(pv != 0) & (prev == 0)]

        for d in entry_bars:
            i = oo.get_loc(d)
            if i + 1 >= len(oo):
                continue                      # no held bar inside this fold
            t = oo[i + 1]
            side = int(pv.loc[d])             # position established at close of d
            gap = side * (s_open.loc[t] - s_close.loc[d])
            ses = side * (s_close.loc[t] - s_open.loc[t])
            rule_rows.append(dict(fold=k, entry=d.date(), held=t.date(), side=side,
                                  z_entry=float(z.loc[d]), gap=gap, session=ses,
                                  total=gap + ses))

        # Placebo: every OOS bar with |z| > entry_z, traded against the excursion.
        zz = z.dropna()
        thr = float(f["entry_z"])
        for d, zv in zz[zz.abs() > thr].items():
            i = oo.get_loc(d)
            if i + 1 >= len(oo):
                continue
            t = oo[i + 1]
            side = int(-np.sign(zv))
            gap = side * (s_open.loc[t] - s_close.loc[d])
            ses = side * (s_close.loc[t] - s_open.loc[t])
            plac_rows.append(dict(fold=k, entry=d.date(), held=t.date(), side=side,
                                  z_entry=float(zv), gap=gap, session=ses,
                                  total=gap + ses))

    return pd.DataFrame(rule_rows), pd.DataFrame(plac_rows)


def summarize(df, label):
    n = len(df)
    g, s, t = df["gap"], df["session"], df["total"]
    print(f"\n  {label}  (n = {n})")
    print(f"    {'':22s} {'sum':>12s} {'mean bps':>10s} {'% of total':>11s} "
          f"{'sd bps':>9s} {'% > 0':>7s}")
    for name, x in [("overnight gap", g), ("intraday session", s), ("TOTAL first bar", t)]:
        pct = 100 * x.sum() / t.sum() if t.sum() != 0 else np.nan
        print(f"    {name:22s} {x.sum():>12.6f} {x.mean()*BPS:>10.2f} {pct:>10.1f}% "
              f"{x.std(ddof=1)*BPS:>9.2f} {100*(x > 0).mean():>6.1f}%")
    # is the gap doing the work, per trade?
    print(f"    gap beats session on {100*(g > s).mean():.1f}% of events; "
          f"corr(gap, session) = {g.corr(s):+.3f}")


def main() -> None:
    cfg = load_config()
    pairs = load_universe(cfg, refresh=False)
    s4 = json.loads((ROOT / "results" / "stage4_walkforward.json").read_text())

    print("=" * 100)
    print("FIRST HELD BAR: OVERNIGHT GAP vs INTRADAY SESSION")
    print("=" * 100)
    print("Entry decided at close(t-1) and filled there; first held bar is t.")
    print("  gap     = side * (spread_open(t)  - spread_close(t-1))")
    print("  session = side * (spread_close(t) - spread_open(t))")

    out = {}
    for pid in ["GOOG_GOOGL", "V_MA"]:
        rule, plac = collect(pairs[pid], cfg, s4[pid]["folds"])
        print(f"\n{'-'*100}\n{pid}\n{'-'*100}")
        summarize(rule, "RULE entries")
        summarize(plac, "PLACEBO population (|z| > entry_z, state ignored)")
        rule.to_csv(ROOT / "results" / f"gap_session_rule__{pid}.csv", index=False)
        plac.to_csv(ROOT / "results" / f"gap_session_placebo__{pid}.csv", index=False)
        out[pid] = (rule, plac)

    print("\n" + "=" * 100)
    print("SUMMARY: share of first-bar gross earned overnight")
    print("=" * 100)
    rows = []
    for pid, (rule, plac) in out.items():
        for lab, d in [("rule", rule), ("placebo", plac)]:
            rows.append(dict(pair=pid, population=lab, n=len(d),
                             gap_sum=d["gap"].sum(), session_sum=d["session"].sum(),
                             total=d["total"].sum(),
                             gap_share_pct=100 * d["gap"].sum() / d["total"].sum()))
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda v: f"{v: .4f}"))
    df.to_csv(ROOT / "results" / "gap_session_summary.csv", index=False)
    print("\nwrote results/gap_session_*.csv")


if __name__ == "__main__":
    main()
