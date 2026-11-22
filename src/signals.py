"""Rolling z-score signal + entry / zero-cross-exit / hard-stop state machine.

No look-ahead:
  z_t numerator   = spread_t (current)
  z_t moments     = spread.shift(1).rolling(lookback)   (lagged)
Position decisions are made from z_t at the close of bar t; P&L of that
position is realized one bar later (the position.shift(1) * Δspread
convention enforced in src/backtest.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_zscore(spread: pd.Series, lookback: int) -> pd.Series:
    """z_t = (spread_t - mu_lookback_{t-1}) / sigma_lookback_{t-1}.

    mu and sigma are computed from spread.shift(1).rolling(lookback), so they
    use bars strictly before t. The numerator uses the current bar; the no-look
    ahead is enforced jointly with the position.shift(1) in P&L (see backtest).
    """
    shifted = spread.shift(1)
    mu = shifted.rolling(lookback, min_periods=lookback).mean()
    sd = shifted.rolling(lookback, min_periods=lookback).std()
    z = (spread - mu) / sd
    z.name = "z"
    return z


def generate_positions(z: pd.Series, entry_z: float, stop_z: float) -> pd.Series:
    """State machine: flat / long / short. Stops are hard exits to flat.

    Long means long-spread (long y_var, short beta * x_var).
    Entry: z < -entry_z -> long;   z > +entry_z -> short.
    Exit at zero crossing (spread returns to mean).
    Hard stop at |z| > stop_z (the spread blew further away).
    """
    state = 0
    out = np.zeros(len(z), dtype=np.int8)
    z_vals = z.values
    for i in range(len(z_vals)):
        zi = z_vals[i]
        if np.isnan(zi):
            out[i] = 0
            state = 0
            continue
        if state == 0:
            if zi < -entry_z:
                state = 1
            elif zi > entry_z:
                state = -1
        elif state == 1:        # long spread
            if zi >= 0.0:
                state = 0       # zero-crossing exit
            elif zi < -stop_z:
                state = 0       # hard stop (spread blew further out)
        elif state == -1:       # short spread
            if zi <= 0.0:
                state = 0       # zero-crossing exit
            elif zi > stop_z:
                state = 0       # hard stop
        out[i] = state
    return pd.Series(out, index=z.index, name="position")
