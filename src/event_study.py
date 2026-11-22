"""Stage 5: signal-decay event study.

For each entry event (rule or placebo), align by sign so all events point the same
direction and the expected post-entry trajectory is "toward zero" if the spread
mean-reverts. The y-axis is the SIGNED z-score with sign flipped so entries are
positive:

    aligned_z(t) = sign(z_entry) · z(t_entry + t)

At t=0 aligned_z = |z_entry|; if the spread reverts, aligned_z → 0; if it diverges
further, aligned_z grows.

Three reference curves go on the same chart:
  1. REALIZED rule entries (state machine fires): mean across events ± 95% CI from
     stationary-block bootstrap (B=2000, mean block 10) on the panel.
  2. PLACEBO entries (every bar where |z| > entry_z, ignoring state): same treatment.
  3. OU CLOSED-FORM baseline: E[z(t) | z(0)] = z(0) · exp(-t / τ), where
     τ = half_life / ln(2). The half-life is FOLD-specific, not pair-specific:
     each event uses the OU fit from its own 504-bar walk-forward training window,
     not the pair-level fit over the full single-split training sample. The two
     differ substantially (3-50 days per fold against 25-60 at pair level), so do
     not describe this baseline as pair-level in the writeup.
     For the pooled panel, the baseline at event-time t is the entry-weighted mean
     of per-event OU curves anchored at each event's |z_entry|.

The headline epistemic standard: write "the rule beats placebo" ONLY when the rule's
mean curve sits OUTSIDE the placebo's CI band (or vice versa) over a contiguous
post-entry interval. If they overlap, the writeup says "rule and placebo are
indistinguishable at the n we have" - which is itself a real finding for a pair
whose spread mean-reverts cleanly on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import numpy as np
import pandas as pd


# ---------- Event identification ----------

def rule_entry_events(position: pd.Series, z: pd.Series) -> pd.DataFrame:
    """Entries are bars where position transitions from flat (0) to non-flat (±1).
    z_entry is the z-score AT the entry bar (not lagged), because that's what the
    state machine saw when it decided to enter.
    """
    pos = position.fillna(0).astype(int)
    prev = pos.shift(1).fillna(0).astype(int)
    mask = (pos != 0) & (prev == 0)
    out = pd.DataFrame({
        "date":     position.index[mask],
        "z_entry":  z.values[mask],
        "side":     pos.values[mask],            # +1 long-spread, -1 short-spread
    }).reset_index(drop=True)
    return out


def placebo_entry_events(z: pd.Series, entry_z_threshold: float) -> pd.DataFrame:
    """Every bar where |z| > threshold is an entry, regardless of state.

    This is the "extreme-z without rule" placebo - it isolates the contribution of
    the state machine + exit logic over a naive "buy any extreme z" strategy.
    Consecutive bars in the same excursion count as separate events; that's
    intentional (no state means no debounce).
    """
    z_clean = z.dropna()
    mask = z_clean.abs() > entry_z_threshold
    return pd.DataFrame({
        "date":     z_clean.index[mask],
        "z_entry":  z_clean.values[mask],
        "side":     -np.sign(z_clean.values[mask]).astype(int),   # short when z > +, long when z < -
    }).reset_index(drop=True)


# ---------- Event panel construction ----------

@dataclass
class EventPanel:
    event_times: np.ndarray           # t in [t_lo, ..., t_hi] (integers, trading days)
    panel: np.ndarray                 # shape (n_events, n_event_times); aligned z-scores
    event_meta: pd.DataFrame          # date, z_entry, side, pair_id

    @property
    def n_events(self) -> int:
        return self.panel.shape[0]

    def mean_curve(self) -> np.ndarray:
        return np.nanmean(self.panel, axis=0)


def disjoint_placebo_events(placebo_ev: pd.DataFrame, rule_ev: pd.DataFrame) -> pd.DataFrame:
    """Placebo events with every rule-entry bar removed.

    The headline placebo is a strict superset of the rule entries, so the two mean
    curves are mechanically correlated and the comparison is biased toward finding
    them similar - which is the direction of the reported null result. Removing the
    rule bars gives a disjoint comparison population, so a null on THIS placebo is
    not an artifact of overlap.
    """
    if len(placebo_ev) == 0 or len(rule_ev) == 0:
        return placebo_ev.reset_index(drop=True)
    rule_dates = set(pd.to_datetime(rule_ev["date"]))
    keep = ~pd.to_datetime(placebo_ev["date"]).isin(rule_dates)
    return placebo_ev.loc[keep].reset_index(drop=True)


def build_event_panel(
    z: pd.Series, events: pd.DataFrame, window: tuple[int, int],
    pair_id: str | None = None,
) -> EventPanel:
    """Returns aligned z-scores in a (n_events, n_event_times) matrix.
    NaN where the requested event-time falls outside the available z series.
    """
    t_lo, t_hi = int(window[0]), int(window[1])
    event_times = np.arange(t_lo, t_hi + 1)
    idx_array = z.index
    rows = []
    used = []
    for _, ev in events.iterrows():
        try:
            i0 = idx_array.get_loc(ev["date"])
        except KeyError:
            continue
        row = np.full(len(event_times), np.nan, dtype=float)
        for k, t in enumerate(event_times):
            ii = i0 + int(t)
            if 0 <= ii < len(idx_array):
                row[k] = z.iloc[ii]
        # Align by sign so aligned_z(0) = |z_entry|, post-entry decreases when reverting
        # side = +1  ⇔ entered long because z_entry < -threshold ⇒ sign(z_entry) = -1
        # side = -1  ⇔ entered short because z_entry > +threshold ⇒ sign(z_entry) = +1
        # aligned_z(t) = sign(z_entry) · z(t). With sign(z_entry) = -side, this is -side·z.
        aligned = -ev["side"] * row
        rows.append(aligned)
        used.append(ev.to_dict())
    if not rows:
        return EventPanel(
            event_times=event_times,
            panel=np.zeros((0, len(event_times))),
            event_meta=pd.DataFrame(columns=list(events.columns) + ["pair_id"]),
        )
    meta = pd.DataFrame(used)
    if pair_id is not None:
        meta["pair_id"] = pair_id
    return EventPanel(event_times=event_times, panel=np.array(rows), event_meta=meta)


def pool_event_panels(panels: Sequence[EventPanel]) -> EventPanel:
    """Stack rows across panels. Assumes identical event_times across panels."""
    panels = [p for p in panels if p.n_events > 0]
    if not panels:
        return EventPanel(np.array([]), np.zeros((0, 0)), pd.DataFrame())
    ref_times = panels[0].event_times
    for p in panels:
        assert np.array_equal(p.event_times, ref_times), "panels must share event_times"
    stacked = np.vstack([p.panel for p in panels])
    meta = pd.concat([p.event_meta for p in panels], ignore_index=True)
    return EventPanel(event_times=ref_times, panel=stacked, event_meta=meta)


# ---------- OU closed-form baseline ----------

def ou_baseline_curve(
    z_entry_magnitudes: np.ndarray,
    half_lives_per_event: np.ndarray,
    event_times: np.ndarray,
) -> np.ndarray:
    """Per-event OU expected reversion, then average across events.

    For a single event with entry magnitude |z(0)| and fold-specific half-life HL
    (the fit from the fold the event falls in, supplied by the caller):
        E[aligned_z(t)] = |z(0)| · exp(-t · ln(2) / HL)   for t >= 0
    For t < 0, OU expectation isn't well-defined as a forecast (we'd need conditional
    expectation given the prior path), so we leave pre-entry as NaN.
    """
    out = np.full(len(event_times), np.nan, dtype=float)
    pos_t = event_times[event_times >= 0]
    if len(pos_t) == 0:
        return out
    decay = np.zeros((len(z_entry_magnitudes), len(pos_t)))
    for i in range(len(z_entry_magnitudes)):
        hl = half_lives_per_event[i]
        if not np.isfinite(hl) or hl <= 0:
            decay[i, :] = np.nan
            continue
        decay[i, :] = abs(z_entry_magnitudes[i]) * np.exp(-pos_t * np.log(2.0) / hl)
    mean_pos = np.nanmean(decay, axis=0)
    pos_mask = event_times >= 0
    out[pos_mask] = mean_pos
    return out


# ---------- Stationary block bootstrap on the event panel ----------

def stationary_block_bootstrap_ci(
    panel: np.ndarray,
    B: int = 2000,
    mean_block_len: float = 10.0,
    ci_level: float = 0.95,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Stationary block bootstrap on the EVENT axis (rows).

    Rows of the panel are events in chronological order; sampling consecutive blocks
    of rows preserves any clustering across event time (e.g., regime-correlated
    entries). Block lengths are geometric with mean = mean_block_len. Standard
    Politis-Romano stationary bootstrap.

    Returns (lo_curve, hi_curve), each shape = panel.shape[1].
    """
    n_events, n_times = panel.shape
    if n_events == 0:
        return np.full(n_times, np.nan), np.full(n_times, np.nan)
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block_len
    boot_means = np.empty((B, n_times))
    for b in range(B):
        rows = np.empty(n_events, dtype=np.int64)
        i = 0
        while i < n_events:
            start = rng.integers(0, n_events)
            # Geometric block length (>=1).
            block_len = rng.geometric(p)
            take = min(block_len, n_events - i)
            for k in range(take):
                rows[i + k] = (start + k) % n_events
            i += take
        boot_means[b, :] = np.nanmean(panel[rows, :], axis=0)
    alpha = (1.0 - ci_level) / 2.0
    lo = np.nanpercentile(boot_means, 100 * alpha, axis=0)
    hi = np.nanpercentile(boot_means, 100 * (1.0 - alpha), axis=0)
    return lo, hi


# ---------- Separation diagnostic ----------

def curves_separate(
    rule_mean: np.ndarray, rule_lo: np.ndarray, rule_hi: np.ndarray,
    plac_mean: np.ndarray, plac_lo: np.ndarray, plac_hi: np.ndarray,
    event_times: np.ndarray,
    min_consecutive_days: int = 5,
) -> dict:
    """Test whether rule and placebo curves separate beyond their bootstrap CIs over
    a contiguous post-entry interval of at least min_consecutive_days.

    Reports:
      - max gap between mean curves over t >= 0
      - longest contiguous run (t >= 0) where the two CI bands do not overlap
      - days where separation holds (for the table)

    The honest read: if longest_separation_days < min_consecutive_days, we write
    "rule and placebo are indistinguishable at this sample size." Otherwise we report
    the separated interval explicitly.
    """
    pos_mask = event_times >= 0
    rm = rule_mean[pos_mask]
    rl, rh = rule_lo[pos_mask], rule_hi[pos_mask]
    pm = plac_mean[pos_mask]
    pl, ph = plac_lo[pos_mask], plac_hi[pos_mask]
    # Separation at each t: CIs don't overlap.
    sep = (rh < pl) | (rl > ph)
    sep = sep & np.isfinite(rm) & np.isfinite(pm)
    # Longest contiguous True run
    longest = 0
    cur = 0
    for s in sep:
        if s:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    diff = rm - pm
    return {
        "longest_separation_days":   int(longest),
        "separation_threshold_days": int(min_consecutive_days),
        "rule_beats_placebo":        bool(longest >= min_consecutive_days),
        "max_abs_mean_gap":          float(np.nanmax(np.abs(diff))) if len(diff) else float("nan"),
        "mean_gap_at_t5":            float(diff[5]) if len(diff) > 5 else float("nan"),
        "mean_gap_at_t10":           float(diff[10]) if len(diff) > 10 else float("nan"),
        "mean_gap_at_t20":           float(diff[20]) if len(diff) > 20 else float("nan"),
    }
