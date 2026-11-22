"""Stage 5: capacity hard-cap from ADV.

This is a PARTICIPATION ceiling, not a profitability ceiling. The number we report
is the AUM at which the average per-trade leg notional reaches the 1%-ADV
participation limit on the smaller leg. ABOVE THIS SIZE YOU ARE BREACHING THE
PARTICIPATION CAP - it is NOT a statement that the strategy stops working.

The two claims (size limit vs profitability limit) are different and the original
report conflated them when it printed a $0 capacity headline. We label them
distinctly to head that off.

Convention for the unit-spread book in log-price space (consistent with stage 3/4):
  position = +1  ⇔  long $1 of leg_y, short $|β| of leg_x  (in dollar notional)
At AUM K (per unit spread), each round-trip moves K dollars on leg_y and K|β| on
leg_x. So the binding constraint is whichever leg's per-trade dollar size first hits
1% × ADV at that leg:

  K_max = min(  0.01 · ADV_y,   0.01 · ADV_x / |β|  )

ADV_y, ADV_x are 20-day mean dollar volumes (close × volume) on the unadjusted
close, evaluated at the END of the study window (i.e., the current liquidity
profile - the constraint binds NOW, not historically).
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class CapacityResult:
    pair_id: str
    y_leg: str                 # canonical legs[0] - the leg long $1 per spread unit
    x_leg: str                 # canonical legs[1] - the leg short $|β| per spread unit
    beta_canonical: float
    adv_y_usd: float           # 20-day mean $ volume at end of window, leg_y
    adv_x_usd: float           # 20-day mean $ volume at end of window, leg_x
    participation_cap: float   # 0.01 = 1%
    binding_leg: str
    capacity_aum_usd: float    # K_max = min(0.01·ADV_y, 0.01·ADV_x/|β|)


def adv_usd_end_of_window(volume_df: pd.DataFrame, window_days: int = 20) -> float:
    """volume_df has columns ['close', 'volume'] indexed by date.
    Returns mean of (close × volume) over the LAST window_days available bars.
    """
    dv = (volume_df["close"] * volume_df["volume"]).dropna()
    if len(dv) < window_days:
        return float(dv.mean()) if len(dv) else float("nan")
    return float(dv.iloc[-window_days:].mean())


def pair_capacity(
    pair_id: str,
    legs: tuple[str, str],            # (legs[0], legs[1]) - canonical order
    beta_canonical: float,            # legs[0] = α + β · legs[1] hedge ratio
    volume_data: dict,                # ticker -> volume_df
    participation_cap: float = 0.01,
    adv_window: int = 20,
) -> CapacityResult:
    y_leg, x_leg = legs[0], legs[1]
    adv_y = adv_usd_end_of_window(volume_data[y_leg], adv_window)
    adv_x = adv_usd_end_of_window(volume_data[x_leg], adv_window)
    abs_beta = abs(beta_canonical) if np.isfinite(beta_canonical) and beta_canonical != 0 else float("nan")
    cap_y = participation_cap * adv_y
    cap_x = participation_cap * adv_x / abs_beta if np.isfinite(abs_beta) else float("nan")
    if np.isfinite(cap_x) and cap_x < cap_y:
        binding = f"{x_leg} (short |beta|*notional)"
        K = cap_x
    else:
        binding = f"{y_leg} (long $1 notional)"
        K = cap_y
    return CapacityResult(
        pair_id=pair_id,
        y_leg=y_leg, x_leg=x_leg,
        beta_canonical=float(beta_canonical),
        adv_y_usd=adv_y, adv_x_usd=adv_x,
        participation_cap=participation_cap,
        binding_leg=binding,
        capacity_aum_usd=K,
    )
