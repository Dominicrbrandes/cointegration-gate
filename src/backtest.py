"""Single-split backtest + training-Sharpe grid search.

P&L convention (log-return space):
    pnl_t = position_{t-1} * (spread_t - spread_{t-1})
This is a log-return approximation because the analysis frame is in log-prices,
so Δspread is a difference of log-prices and bps costs (in 1e-4 units) are
directly commensurable. See memory note on the log-prices methodology.

Round-trip cost convention:
    Each unit of |Δposition| pays half the round-trip in bps.
    Long->flat or flat->long change of 1 pays RT/2 bps.
    Long->short (change of 2) pays the full RT bps.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List
from itertools import product

import numpy as np
import pandas as pd

from .signals import rolling_zscore, generate_positions
from .spread import SpreadFit, fit_cointegrating_vector, compute_spread, select_ordering


# ---------- P&L primitives ----------

def compute_pnl(position: pd.Series, spread: pd.Series, cost_bps: float) -> pd.DataFrame:
    """Return a frame with gross_pnl, cost, net_pnl indexed identically to spread.

    Valid ONLY when `spread` is defined under a single (alpha, beta) fit throughout.
    Do not call this on a spread concatenated across walk-forward folds: .diff()
    would straddle two fits at every seam and book the model redefinition as P&L.
    Use compute_composite_pnl for that.
    """
    spread_change = spread.diff()
    gross = position.shift(1) * spread_change
    pos_change = position.diff().fillna(0.0).abs()
    cost = pos_change * (cost_bps / 2.0) / 10_000.0     # log-return units
    net = gross - cost
    out = pd.concat([
        spread.rename("spread"),
        spread_change.rename("dspread"),
        position.rename("position"),
        gross.rename("gross_pnl"),
        cost.rename("cost"),
        net.rename("net_pnl"),
    ], axis=1)
    return out


def compute_composite_pnl(
    position_parts: list[pd.Series],
    spread_parts: list[pd.Series],
    cost_bps: float,
) -> pd.DataFrame:
    """Composite P&L across walk-forward folds, differenced WITHIN each fold.

    Differencing the concatenated spread would subtract a spread defined under
    fold k's (alpha, beta) from one defined under fold k+1's. Where fold k ended
    with an open position that books the model redefinition as P&L, and it has no
    tradable counterpart. Gross is therefore computed per fold, on that fold's own
    spread series, and the pieces are concatenated.

    The first OOS bar of each fold has no predecessor inside its own fold, and
    Section 3.5 states that the position resets to flat at every boundary, so the
    fold is entered holding nothing and that bar's gross is zero.

    Costs are deliberately still charged on the CONCATENATED position series: the
    boundary unwind is a real trade and must be paid, and a seam that closes one
    position and opens the opposite still pays a full round trip.
    """
    gross_parts, dspread_parts = [], []
    for pos_f, spread_f in zip(position_parts, spread_parts):
        d = spread_f.diff()
        g = pos_f.shift(1) * d
        if len(g):
            d.iloc[0] = np.nan     # no within-fold predecessor
            g.iloc[0] = 0.0        # entered the fold flat
        gross_parts.append(g)
        dspread_parts.append(d)
    gross = pd.concat(gross_parts)
    gross = gross[~gross.index.duplicated(keep="first")]
    dspread = pd.concat(dspread_parts)
    dspread = dspread[~dspread.index.duplicated(keep="first")]

    position = pd.concat(position_parts)
    position = position[~position.index.duplicated(keep="first")]
    spread = pd.concat(spread_parts)
    spread = spread[~spread.index.duplicated(keep="first")]

    pos_change = position.diff().fillna(0.0).abs()
    cost = pos_change * (cost_bps / 2.0) / 10_000.0     # log-return units
    net = gross - cost
    return pd.concat([
        spread.rename("spread"),
        dspread.rename("dspread"),
        position.rename("position"),
        gross.rename("gross_pnl"),
        cost.rename("cost"),
        net.rename("net_pnl"),
    ], axis=1)


def sharpe(pnl: pd.Series, freq: int = 252) -> float:
    p = pnl.dropna()
    if len(p) < 2:
        return float("nan")
    sd = p.std(ddof=1)
    if sd == 0 or not np.isfinite(sd):
        return float("nan")
    return float(p.mean() / sd * np.sqrt(freq))


def lo_annualization(pnl: pd.Series, freq: int = 252, max_lag: int = 20) -> dict:
    """Autocorrelation-adjusted Sharpe annualization (Lo 2002).

    The sqrt(freq) convention assumes serially uncorrelated returns. A mean-reversion
    strategy holding positions across multi-day reversion windows violates that by
    construction, so the naive factor overstates the annualized Sharpe when the daily
    P&L is positively autocorrelated. Lo's factor replaces sqrt(q) with

        q / sqrt( q + 2 * sum_{k=1..q-1} (q - k) * rho_k )

    which for rho = 0 collapses back to sqrt(q). The sum is truncated at `max_lag`
    (20 is standard for daily data); the truncation is reported alongside the result.

    Returns the naive and adjusted factors, the adjusted Sharpe, and rho_1..rho_5.
    """
    p = pnl.dropna()
    naive = float(np.sqrt(freq))
    if len(p) < max_lag + 2:
        return {"factor_naive": naive, "factor_lo": float("nan"),
                "sharpe_naive": float("nan"), "sharpe_lo": float("nan"),
                "rho": [], "max_lag": max_lag}
    x = p.values - p.mean()
    denom = float(np.dot(x, x))
    rho = [float(np.dot(x[:-k], x[k:]) / denom) for k in range(1, max_lag + 1)]

    q = float(freq)
    s = sum((q - k) * rho[k - 1] for k in range(1, max_lag + 1))
    var_ratio = q + 2.0 * s
    factor_lo = float(q / np.sqrt(var_ratio)) if var_ratio > 0 else float("nan")

    sr_daily = float(p.mean() / p.std(ddof=1)) if p.std(ddof=1) > 0 else float("nan")
    return {
        "factor_naive": naive,
        "factor_lo": factor_lo,
        "sharpe_naive": sr_daily * naive,
        "sharpe_lo": sr_daily * factor_lo,
        "rho": rho[:5],
        "max_lag": max_lag,
    }


def annualized_return(pnl: pd.Series, freq: int = 252) -> float:
    p = pnl.dropna()
    if len(p) == 0:
        return float("nan")
    return float(p.mean() * freq)


def n_entries(position: pd.Series) -> int:
    """Count entry events (transitions from flat to non-flat)."""
    cur = position.fillna(0).astype(int)
    prev = cur.shift(1).fillna(0).astype(int)
    entries = ((cur != 0) & (prev == 0)).sum()
    return int(entries)


# ---------- Backtest one parameter cell ----------

@dataclass
class SingleSplitResult:
    pair_id: str
    legs: List[str]

    # cointegrating vector (from training)
    y_var: str
    x_var: str
    alpha: float
    beta: float
    train_residual_std: float
    half_life_days: float
    half_life_raw_days: float
    half_life_b: float

    # chosen signal params (max train net Sharpe)
    entry_z: float
    stop_z: float
    lookback: int

    # backtest stats at chosen params (baseline cost)
    cost_bps: float
    sharpe_train_gross: float
    sharpe_train_net: float
    sharpe_test_gross: float
    sharpe_test_net: float
    sharpe_full_net: float
    annret_train_net: float
    annret_test_net: float
    n_entries_train: int
    n_entries_test: int

    # diagnostic flags
    half_life_flag: str       # one of "" | "above_test_window" | "below_floor" | "non_mean_reverting"
    cointegrated: bool        # carried through from stage 2 for the report


def backtest_one_cell(
    spread: pd.Series,
    train_idx: pd.Index,
    test_idx: pd.Index,
    entry_z: float,
    stop_z: float,
    lookback: int,
    cost_bps: float,
) -> dict:
    z = rolling_zscore(spread, lookback)
    pos = generate_positions(z, entry_z, stop_z)
    full = compute_pnl(pos, spread, cost_bps)

    train_pnl = full.loc[train_idx, "net_pnl"]
    test_pnl = full.loc[test_idx, "net_pnl"]
    train_gross = full.loc[train_idx, "gross_pnl"]
    test_gross = full.loc[test_idx, "gross_pnl"]
    train_pos = full.loc[train_idx, "position"]
    test_pos = full.loc[test_idx, "position"]

    return {
        "entry_z": entry_z,
        "stop_z": stop_z,
        "lookback": lookback,
        "cost_bps": cost_bps,
        "sharpe_train_gross": sharpe(train_gross),
        "sharpe_train_net": sharpe(train_pnl),
        "sharpe_test_gross": sharpe(test_gross),
        "sharpe_test_net": sharpe(test_pnl),
        "sharpe_full_net": sharpe(full["net_pnl"]),
        "annret_train_net": annualized_return(train_pnl),
        "annret_test_net": annualized_return(test_pnl),
        "n_entries_train": n_entries(train_pos),
        "n_entries_test": n_entries(test_pos),
        "_z": z,
        "_pos": pos,
        "_pnl": full,
    }


# ---------- Grid search ----------

def grid_search_train_sharpe(
    spread: pd.Series,
    train_idx: pd.Index,
    test_idx: pd.Index,
    grid: dict,
    cost_bps: float,
) -> tuple[dict, pd.DataFrame]:
    """Evaluate every cell. Pick the cell with the highest NET training Sharpe.

    Selection on net (post-cost) training Sharpe - selecting on gross would
    favor high-turnover params that look great pre-cost.
    """
    cells = []
    light_rows = []
    for entry_z, stop_z, lookback in product(grid["entry_z"], grid["stop_z"], grid["lookback"]):
        result = backtest_one_cell(spread, train_idx, test_idx,
                                    entry_z, stop_z, lookback, cost_bps)
        cells.append(result)
        light_rows.append({k: v for k, v in result.items() if not k.startswith("_")})
    surface = pd.DataFrame(light_rows)
    # Tie-break: if multiple cells tie on Sharpe (e.g., all NaN), pick the one with the
    # most training entries (the more active selection); ultimate fallback: first row.
    sortable = surface.copy()
    sortable["_sharpe_safe"] = sortable["sharpe_train_net"].fillna(-np.inf)
    best_idx = int(sortable.sort_values(
        by=["_sharpe_safe", "n_entries_train"], ascending=[False, False]
    ).index[0])
    best = cells[best_idx]
    return best, surface


# ---------- Driver per pair ----------

def half_life_flag(hl: float, hl_raw: float, test_window_days: int, floor_days: float, ceil_days: float) -> str:
    """STOP-level flags only: non-mean-reverting, above-test-window, below-floor.
    Soft-flag clipped_at_ceiling is included for transparency but is not a stop.
    """
    if hl is None or (isinstance(hl, float) and (not np.isfinite(hl))):
        return "non_mean_reverting"
    if hl >= test_window_days:
        return "above_test_window"
    if hl <= floor_days:
        return "below_floor"
    if hl_raw is not None and np.isfinite(hl_raw) and hl_raw > ceil_days:
        return f"clipped_at_ceiling(raw={hl_raw:.0f}d)"
    return ""


def run_pair_stage3(
    pair, fit: SpreadFit, spread: pd.Series, cfg: dict, cointegrated: bool
) -> tuple[SingleSplitResult, pd.DataFrame, dict]:
    grid = cfg["signal"]["grid"]
    cost_bps = float(cfg["costs"]["baseline_round_trip_bps"])
    floor_days = float(cfg["spread"]["half_life"]["floor_days"])
    ceil_days = float(cfg["spread"]["half_life"]["ceil_days"])
    train_idx = pair.train.index
    test_idx = pair.test.index

    best, surface = grid_search_train_sharpe(spread, train_idx, test_idx, grid, cost_bps)

    flag = half_life_flag(fit.half_life_days, fit.half_life_raw_days,
                          test_window_days=len(test_idx),
                          floor_days=floor_days, ceil_days=ceil_days)

    result = SingleSplitResult(
        pair_id=pair.pair_id,
        legs=list(pair.legs),
        y_var=fit.y_var,
        x_var=fit.x_var,
        alpha=fit.alpha,
        beta=fit.beta,
        train_residual_std=fit.train_residual_std,
        half_life_days=fit.half_life_days,
        half_life_raw_days=fit.half_life_raw_days,
        half_life_b=fit.half_life_b,
        entry_z=float(best["entry_z"]),
        stop_z=float(best["stop_z"]),
        lookback=int(best["lookback"]),
        cost_bps=cost_bps,
        sharpe_train_gross=best["sharpe_train_gross"],
        sharpe_train_net=best["sharpe_train_net"],
        sharpe_test_gross=best["sharpe_test_gross"],
        sharpe_test_net=best["sharpe_test_net"],
        sharpe_full_net=best["sharpe_full_net"],
        annret_train_net=best["annret_train_net"],
        annret_test_net=best["annret_test_net"],
        n_entries_train=best["n_entries_train"],
        n_entries_test=best["n_entries_test"],
        half_life_flag=flag,
        cointegrated=bool(cointegrated),
    )
    artifacts = {
        "z": best["_z"],
        "position": best["_pos"],
        "pnl": best["_pnl"],
    }
    return result, surface, artifacts


# ---------- Stage 4: walk-forward (refit-both) ----------

@dataclass
class FoldResult:
    fold_idx: int
    train_start: str
    train_end: str
    oos_start: str
    oos_end: str
    # cointegrating vector refit this fold
    y_var: str
    x_var: str
    alpha: float
    beta: float                       # in the LHS-chosen direction
    beta_canonical: float             # always expressed as legs[0] = a + beta * legs[1]
    train_residual_std: float
    half_life_days: float
    half_life_raw_days: float
    # re-selected signal cell
    entry_z: float
    stop_z: float
    lookback: int
    sharpe_train_net: float           # the selection objective on this fold's train
    # OOS performance (this fold only, no cross-fold contamination)
    sharpe_oos_gross: float
    sharpe_oos_net: float
    annret_oos_net: float
    n_entries_oos: int
    n_oos_bars: int


@dataclass
class WalkForwardResult:
    pair_id: str
    legs: List[str]
    n_folds: int
    train_window_days: int
    test_window_days: int
    step_days: int
    cost_bps: float
    # composite OOS (concatenated, deduped) - the headline aggregate
    composite_sharpe_oos_gross: float
    composite_sharpe_oos_net: float
    composite_annret_oos_net: float
    composite_n_entries_oos: int
    composite_n_oos_bars: int
    pct_folds_positive_net: float
    # per-fold cell-stability diagnostic
    modal_entry_z: float
    modal_lookback: int
    pct_folds_at_modal_cell: float
    # everything else for downstream consumers
    folds: List[FoldResult]


def _fold_train_score(
    spread_full_fold: pd.Series,
    train_idx: pd.Index,
    entry_z: float,
    stop_z: float,
    lookback: int,
    cost_bps: float,
) -> tuple[float, int]:
    """Per-fold training-Sharpe for one cell. State machine runs on the train slice only,
    so warmup wastes ~lookback bars at the start of the training window (same as stage 3).
    """
    spread_train = spread_full_fold.loc[train_idx]
    z = rolling_zscore(spread_train, lookback)
    pos = generate_positions(z, entry_z, stop_z)
    pnl = compute_pnl(pos, spread_train, cost_bps)
    return sharpe(pnl["net_pnl"]), n_entries(pos)


def fold_oos_eval(
    spread_full_fold: pd.Series,
    train_idx: pd.Index,
    oos_idx: pd.Index,
    entry_z: float,
    stop_z: float,
    lookback: int,
    cost_bps: float,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Apply selected cell to OOS. Z is computed on (train ∪ oos) so the OOS window
    inherits warmed-up rolling stats from the train tail (no cold start). The position
    state machine is run on the OOS slice ALONE, so it starts from flat at the boundary
    - this is the refit-both contract (unwind under old fit, re-enter under new fit).

    A small caveat: this within-fold pnl does NOT charge the cost of unwinding any
    position open at the END of the OOS window. That position is closed at zero cost
    here; in the composite series the boundary unwind cost will be captured naturally
    because composite pnl is recomputed end-to-end on the concatenated position+spread.
    """
    z_full = rolling_zscore(spread_full_fold, lookback)
    z_oos = z_full.loc[oos_idx]
    pos_oos = generate_positions(z_oos, entry_z, stop_z)
    pnl_oos = compute_pnl(pos_oos, spread_full_fold.loc[oos_idx], cost_bps)
    return pnl_oos, pos_oos, z_oos


def run_pair_stage4_walkforward(pair, cfg: dict) -> WalkForwardResult:
    """Refit-both walk-forward over the FULL history of this pair.

    At each fold boundary we refit α/β on the trailing 504 bars and re-select
    (entry_z, lookback) by maximizing net training Sharpe on those 504 bars,
    then apply both unchanged to the next 126 OOS bars. Selection runs every
    fold by design - that's the walk-forward stress test of parameter stability.
    """
    grid = cfg["signal"]["grid"]
    cost_bps = float(cfg["costs"]["baseline_round_trip_bps"])
    wf = cfg["backtest"]["walk_forward"]
    train_w = int(wf["train_window_days"])
    test_w = int(wf["test_window_days"])
    step = int(wf["step_days"])
    floor_d = float(cfg["spread"]["half_life"]["floor_days"])
    ceil_d = float(cfg["spread"]["half_life"]["ceil_days"])

    legs = list(pair.legs)
    canon_y = legs[0]                 # canonical LHS for the beta-drift comparable

    idx = pair.df.index
    folds: list[FoldResult] = []
    oos_pos_parts: list[pd.Series] = []
    oos_spread_parts: list[pd.Series] = []

    fold_i = 0
    start_i = 0
    while start_i + train_w + test_w <= len(idx):
        train_slice_idx = idx[start_i : start_i + train_w]
        oos_slice_idx = idx[start_i + train_w : start_i + train_w + test_w]

        # 1) Refit cointegrating vector on this fold's training window.
        # The LHS orientation is selected on an EXPANDING window - every bar
        # available before this fold's OOS block, not just the trailing 504 - so it
        # uses maximal legitimate information and still admits no look-ahead. The
        # two orderings are frequently a near-tie on 504 bars (median gap 0.008 for
        # GOOG/GOOGL), and letting noise flip the orientation mid-run redefines the
        # spread and forces an unwind; the expanding window settles the choice.
        # alpha, beta, and the cell still refit on the trailing window every fold.
        ordering = select_ordering(pair.df.iloc[0:start_i + train_w], legs)
        train_df_slice = pair.df.loc[train_slice_idx]
        fit = fit_cointegrating_vector(train_df_slice, legs, pair.pair_id, cfg,
                                       force_ordering=ordering)
        full_fold_idx = train_slice_idx.append(oos_slice_idx)
        spread_full_fold = compute_spread(pair.df.loc[full_fold_idx], fit)

        # Canonical beta: express hedge ratio in legs[0]-as-LHS direction. With the
        # orientation now pinned this is a relabeling, not a flip correction, but it
        # is kept so per-fold betas stay comparable across pairs.
        if fit.y_var == canon_y:
            beta_canon = fit.beta
        else:
            beta_canon = float("nan") if fit.beta == 0 else 1.0 / fit.beta

        # 2) Re-select the (entry_z, lookback) cell on net training Sharpe @ baseline cost
        best_cell = None      # (sharpe_train_net, n_entries_train, entry_z, stop_z, lookback)
        for entry_z, stop_z, lookback in product(
            grid["entry_z"], grid["stop_z"], grid["lookback"]
        ):
            sh, n_ent = _fold_train_score(
                spread_full_fold, train_slice_idx,
                entry_z, stop_z, lookback, cost_bps,
            )
            sh_safe = -np.inf if not np.isfinite(sh) else sh
            cand = (sh_safe, n_ent, float(entry_z), float(stop_z), int(lookback))
            # Tie-break order matches stage 3: higher Sharpe, then more training entries.
            if best_cell is None or cand[:2] > best_cell[:2]:
                best_cell = cand

        sh_train_net, _, entry_z, stop_z, lookback = best_cell

        # 3) Apply selected cell to OOS (state machine reset to flat at boundary)
        pnl_oos, pos_oos, _ = fold_oos_eval(
            spread_full_fold, train_slice_idx, oos_slice_idx,
            entry_z, stop_z, lookback, cost_bps,
        )

        folds.append(FoldResult(
            fold_idx=fold_i,
            train_start=train_slice_idx[0].date().isoformat(),
            train_end=train_slice_idx[-1].date().isoformat(),
            oos_start=oos_slice_idx[0].date().isoformat(),
            oos_end=oos_slice_idx[-1].date().isoformat(),
            y_var=fit.y_var,
            x_var=fit.x_var,
            alpha=fit.alpha,
            beta=fit.beta,
            beta_canonical=beta_canon,
            train_residual_std=fit.train_residual_std,
            half_life_days=fit.half_life_days,
            half_life_raw_days=fit.half_life_raw_days,
            entry_z=entry_z,
            stop_z=stop_z,
            lookback=lookback,
            sharpe_train_net=float(sh_train_net) if np.isfinite(sh_train_net) else float("nan"),
            sharpe_oos_gross=sharpe(pnl_oos["gross_pnl"]),
            sharpe_oos_net=sharpe(pnl_oos["net_pnl"]),
            annret_oos_net=annualized_return(pnl_oos["net_pnl"]),
            n_entries_oos=n_entries(pos_oos),
            n_oos_bars=int(len(oos_slice_idx)),
        ))

        oos_pos_parts.append(pos_oos)
        oos_spread_parts.append(spread_full_fold.loc[oos_slice_idx])

        fold_i += 1
        start_i += step

    # 4) Composite: gross differenced within each fold, costs on the concatenated
    # position series so the boundary unwind is still charged. See
    # compute_composite_pnl for why the spread must not be differenced across a seam.
    composite_pnl = compute_composite_pnl(oos_pos_parts, oos_spread_parts, cost_bps)
    composite_pos = composite_pnl["position"]

    # Per-fold cell-stability diagnostic
    cell_counts = {}
    for f in folds:
        key = (f.entry_z, f.lookback)
        cell_counts[key] = cell_counts.get(key, 0) + 1
    if cell_counts:
        modal_key, modal_n = max(cell_counts.items(), key=lambda kv: kv[1])
        modal_entry_z, modal_lookback = modal_key
        pct_modal = modal_n / len(folds)
    else:
        modal_entry_z, modal_lookback, pct_modal = float("nan"), -1, float("nan")

    pos_folds = sum(1 for f in folds if np.isfinite(f.sharpe_oos_net) and f.sharpe_oos_net > 0)
    pct_pos = pos_folds / len(folds) if folds else float("nan")

    return WalkForwardResult(
        pair_id=pair.pair_id,
        legs=legs,
        n_folds=len(folds),
        train_window_days=train_w,
        test_window_days=test_w,
        step_days=step,
        cost_bps=cost_bps,
        composite_sharpe_oos_gross=sharpe(composite_pnl["gross_pnl"]),
        composite_sharpe_oos_net=sharpe(composite_pnl["net_pnl"]),
        composite_annret_oos_net=annualized_return(composite_pnl["net_pnl"]),
        composite_n_entries_oos=n_entries(composite_pos),
        composite_n_oos_bars=int(len(composite_pos)),
        pct_folds_positive_net=pct_pos,
        modal_entry_z=float(modal_entry_z),
        modal_lookback=int(modal_lookback),
        pct_folds_at_modal_cell=float(pct_modal),
        folds=folds,
    )
