"""Stage 5: cost sweep + breakeven solver under FIXED stage-4 cells.

The question this module answers is "how fragile is the as-built pipeline to a wrong
cost assumption?" - so the cells are LOCKED at the stage-4 walk-forward choices and
we vary cost ONLY inside the P&L calculation. Re-selecting cells at each cost would
answer a different (self-flattering) question by silently re-optimizing against the
variable we're stress-testing.

Inputs are the concatenated walk-forward OOS position+spread series for one pair.
That position series carries the boundary-unwind structure already (positions reset
to flat at each fold start in stage 4), so recomputing P&L end-to-end at a new cost
naturally re-charges the boundary unwind at the new rate.
"""
from __future__ import annotations

from typing import List
import numpy as np
import pandas as pd

from .backtest import compute_composite_pnl, sharpe, annualized_return


def composite_pnl_at_cost(
    position_parts: List[pd.Series], spread_parts: List[pd.Series], cost_bps: float
) -> pd.DataFrame:
    """Inputs are the PER-FOLD OOS position and spread series, not concatenated ones.

    Gross must be differenced inside each fold; differencing a concatenated spread
    straddles two (alpha, beta) fits at every seam. See compute_composite_pnl.
    """
    return compute_composite_pnl(position_parts, spread_parts, cost_bps)


def cost_sweep(
    position_parts: List[pd.Series], spread_parts: List[pd.Series], cost_bps_list: List[float]
) -> pd.DataFrame:
    rows = []
    for c in cost_bps_list:
        pnl = composite_pnl_at_cost(position_parts, spread_parts, c)
        rows.append({
            "cost_bps":     float(c),
            "sharpe_gross": sharpe(pnl["gross_pnl"]),
            "sharpe_net":   sharpe(pnl["net_pnl"]),
            "annret_net":   annualized_return(pnl["net_pnl"]),
        })
    return pd.DataFrame(rows)


def breakeven_cost_bps(
    position_parts: List[pd.Series],
    spread_parts: List[pd.Series],
    search_range_bps: tuple[float, float] = (0.0, 60.0),
    tol_bps: float = 0.01,
    max_iter: int = 60,
) -> float:
    """Find the round-trip cost (bps) at which composite net Sharpe crosses zero.

    Sharpe is monotonically decreasing in cost (more cost subtracts a positive amount
    from each turn). Bisection on Sharpe(cost) = 0 is valid; if Sharpe at the lower
    bound is already <= 0, the pair has no edge at any nonneg cost → return that bound.
    """
    lo, hi = float(search_range_bps[0]), float(search_range_bps[1])
    s_lo = sharpe(composite_pnl_at_cost(position_parts, spread_parts, lo)["net_pnl"])
    if not np.isfinite(s_lo) or s_lo <= 0:
        return lo
    s_hi = sharpe(composite_pnl_at_cost(position_parts, spread_parts, hi)["net_pnl"])
    if np.isfinite(s_hi) and s_hi > 0:
        # Edge survives even at the search ceiling - return the ceiling as ">=" indicator.
        return hi
    for _ in range(max_iter):
        if hi - lo < tol_bps:
            break
        mid = 0.5 * (lo + hi)
        s_mid = sharpe(composite_pnl_at_cost(position_parts, spread_parts, mid)["net_pnl"])
        if not np.isfinite(s_mid):
            hi = mid
            continue
        if s_mid > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
