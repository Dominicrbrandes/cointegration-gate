"""Stage 5 orchestrator: costs / capacity / signal-decay / cross-section synthesis.

Pipeline contract (locked):
  - Walk-forward cells from stage 4 are FIXED. Stage 5 does not re-select.
  - Cost varies ONLY inside the P&L re-computation (cost-fragility, not re-optimization).
  - Capacity is reported as a PARTICIPATION CEILING (1%-ADV hard cap), not a profitability ceiling.
  - Event-study epistemic standard: "rule beats placebo" is asserted ONLY if the rule and
    placebo bootstrap CI bands fail to overlap over a contiguous run of >= 5 post-entry days.
    Otherwise the writeup says "indistinguishable at this sample size."

Deliverables produced (per the stage-4 directive):
  1. Per-cointegrated-pair cost sweep table + breakeven bps.
  2. Pooled GOOG/GOOGL+V/MA event-study chart with realized rule, placebo, OU-closed-form;
     plus GOOG/GOOGL-alone version.
  3. Seven-pair synthesis table with: classification, S_oos_net, %folds+, per-fold Sharpe std,
     β-drift range, breakeven bps, capacity $M.
  4. Per-pair capacity ceilings.
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

from src.config_io import load_config, verify_config_lock
from src.data import load_universe, load_volumes
from src.spread import fit_cointegrating_vector, compute_spread, select_ordering
from src.backtest import (
    fold_oos_eval, sharpe, annualized_return, n_entries,
    lo_annualization,
)
from src.signals import rolling_zscore
from src.costs import cost_sweep, breakeven_cost_bps, composite_pnl_at_cost
from src.capacity import pair_capacity, adv_usd_end_of_window
from src.event_study import (
    rule_entry_events, placebo_entry_events, disjoint_placebo_events,
    build_event_panel, pool_event_panels,
    ou_baseline_curve, stationary_block_bootstrap_ci, curves_separate,
)
from src.plotting import apply_style, PALETTE
from make_paper_figures import render_cost_sweep, render_event_study


COINTEGRATED_HEADLINE = ["GOOG_GOOGL", "V_MA"]


def _native(o):
    if isinstance(o, (np.bool_,)):    return bool(o)
    if isinstance(o, (np.integer,)):  return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    return o


def _fmt(v, n=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "nan"
    return f"{v:.{n}f}"


def _fmt_money(v: float) -> str:
    if not np.isfinite(v):
        return "nan"
    if abs(v) >= 1e9: return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6: return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3: return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


# -------------------- Per-pair reproduction of stage-4 OOS positions --------------------

def reproduce_pair_walkforward(pair, folds_meta: list[dict], cfg: dict):
    """Re-derive the per-fold positions, spreads, and z-series using the LOCKED cells
    from stage 4. We re-fit α/β to confirm reproducibility (and assert it matches
    the saved fit), so any silent drift between stage-4-time and now would surface.

    Returns:
      composite_position : pd.Series   (concatenated OOS positions)
      composite_spread   : pd.Series   (concatenated OOS spreads under per-fold fits)
      pos_parts          : list[pd.Series]   (per-fold OOS positions, unconcatenated)
      spr_parts          : list[pd.Series]   (per-fold OOS spreads, unconcatenated)
      per_fold_z         : list[pd.Series]   (OOS z, one per fold)
      per_fold_pos       : list[pd.Series]
      per_fold_entry_z   : list[float]
      per_fold_half_life : list[float]
    """
    composite_pos_parts, composite_spr_parts = [], []
    per_fold_z, per_fold_pos = [], []
    per_fold_entry_z, per_fold_hl = [], []
    cost_bps = float(cfg["costs"]["baseline_round_trip_bps"])

    # Mirror stage 4's expanding-window orientation rule exactly; anything else
    # trips the y_var assertion below.
    wf = cfg["backtest"]["walk_forward"]
    train_w, step_w = int(wf["train_window_days"]), int(wf["step_days"])

    for k, f in enumerate(folds_meta):
        train_idx = pair.df.loc[f["train_start"]:f["train_end"]].index
        oos_idx = pair.df.loc[f["oos_start"]:f["oos_end"]].index
        train_df_slice = pair.df.loc[train_idx]
        ordering = select_ordering(pair.df.iloc[0:k * step_w + train_w], list(pair.legs))
        fit = fit_cointegrating_vector(train_df_slice, pair.legs, pair.pair_id, cfg,
                                       force_ordering=ordering)

        # Reproducibility assertion: re-fit must match the saved fit exactly.
        assert abs(fit.alpha - f["alpha"]) < 1e-10, \
            f"{pair.pair_id} fold {f['fold_idx']}: alpha drift {fit.alpha} vs {f['alpha']}"
        assert abs(fit.beta - f["beta"]) < 1e-10, \
            f"{pair.pair_id} fold {f['fold_idx']}: beta drift {fit.beta} vs {f['beta']}"
        assert fit.y_var == f["y_var"], \
            f"{pair.pair_id} fold {f['fold_idx']}: y_var drift {fit.y_var} vs {f['y_var']}"

        full_fold_idx = train_idx.append(oos_idx)
        spread_full = compute_spread(pair.df.loc[full_fold_idx], fit)

        # Apply LOCKED cell (no re-selection)
        pnl_oos, pos_oos, z_oos = fold_oos_eval(
            spread_full, train_idx, oos_idx,
            float(f["entry_z"]), float(f["stop_z"]), int(f["lookback"]),
            cost_bps,
        )
        composite_pos_parts.append(pos_oos)
        composite_spr_parts.append(spread_full.loc[oos_idx])
        per_fold_z.append(z_oos)
        per_fold_pos.append(pos_oos)
        per_fold_entry_z.append(float(f["entry_z"]))
        per_fold_hl.append(float(f["half_life_days"]))

    composite_pos = pd.concat(composite_pos_parts)
    composite_spr = pd.concat(composite_spr_parts)
    composite_pos = composite_pos[~composite_pos.index.duplicated(keep="first")]
    composite_spr = composite_spr[~composite_spr.index.duplicated(keep="first")]
    return (composite_pos, composite_spr, composite_pos_parts, composite_spr_parts,
            per_fold_z, per_fold_pos, per_fold_entry_z, per_fold_hl)


# Chart rendering lives in make_paper_figures.py (shared with the fast
# re-render path) so the paper figures have exactly one style source.


# -------------------- Main --------------------

def main():
    cfg = load_config()
    # Methodology lock. The per-fold assertions below re-fit under whatever config
    # is loaded, so they verify internal consistency and cannot detect a config
    # change: a clone with a mutated config.yaml regenerates the whole chain
    # self-consistently and passes them all, on numbers that do not match the
    # paper. This fingerprint is the check that catches that.
    fingerprint = verify_config_lock(cfg)
    print(f"Loaded config (author={cfg['project']['author']})")
    print(f"Config fingerprint verified: {fingerprint[:16]}...")

    pairs = load_universe(cfg, refresh=False)
    results_dir = ROOT / "results"
    stage5_dir = results_dir / "stage5"
    stage5_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = ROOT / "figures" / "stage5"
    fig_dir.mkdir(parents=True, exist_ok=True)

    stage4 = json.loads((results_dir / "stage4_walkforward.json").read_text())
    stage3 = pd.read_csv(results_dir / "stage3_singlesplit.csv").set_index("pair_id")
    stage2 = json.loads((results_dir / "stage2_cointegration.json").read_text())
    stage2_coint = {pid: bool(v["cointegrated"]) for pid, v in stage2.items()}

    # ----- Step A: reproduce per-pair walk-forward positions -----
    print("\n========== STAGE 5A: reproducing walk-forward positions (locked cells) ==========")
    reproduced = {}
    for pid, pair in pairs.items():
        folds_meta = stage4[pid]["folds"]
        cp, cs, ppar, spar, fz, fpos, fentry, fhl = reproduce_pair_walkforward(
            pair, folds_meta, cfg)
        # Sanity check: composite Sharpe at baseline cost must reproduce stage 4 net.
        s4_net = stage4[pid]["summary"]["composite_sharpe_oos_net"]
        s5_net = sharpe(composite_pnl_at_cost(ppar, spar, cfg["costs"]["baseline_round_trip_bps"])["net_pnl"])
        delta = abs(s4_net - s5_net)
        flag = "OK" if delta < 1e-6 else f"DRIFT {delta:.2e}"
        print(f"  {pid:12s}  S4 net={s4_net:.4f}  S5 net={s5_net:.4f}  {flag}")
        assert delta < 1e-6, f"{pid}: reproduction drift {delta}"
        reproduced[pid] = {
            "composite_position": cp, "composite_spread": cs,
            "pos_parts": ppar, "spr_parts": spar,
            "per_fold_z": fz, "per_fold_pos": fpos,
            "per_fold_entry_z": fentry, "per_fold_half_life": fhl,
        }

    # ----- Step B: cost sweep + breakeven (cointegrated pairs only for headline) -----
    print("\n========== STAGE 5B: cost sweep + breakeven ==========")
    sweep_tables, breakevens = {}, {}
    sweep_cost_grid = list(cfg["costs"]["sweep_bps"])
    breakeven_range = tuple(cfg["costs"]["breakeven_search_bps"])

    # Run sweep for ALL 7 pairs so the synthesis column is honest, but headline only for coint.
    breakeven_all = {}
    for pid in pairs:
        ppar, spar = reproduced[pid]["pos_parts"], reproduced[pid]["spr_parts"]
        df = cost_sweep(ppar, spar, sweep_cost_grid)
        sweep_tables[pid] = df
        be = breakeven_cost_bps(ppar, spar, breakeven_range)
        breakeven_all[pid] = be
        df.to_csv(stage5_dir / f"cost_sweep__{pid}.csv", index=False)
    for pid in COINTEGRATED_HEADLINE:
        breakevens[pid] = breakeven_all[pid]

    print("\n  Cost-sweep tables (cointegrated pairs - headline):")
    for pid in COINTEGRATED_HEADLINE:
        df = sweep_tables[pid].copy()
        for c in ["sharpe_gross", "sharpe_net", "annret_net"]:
            df[c] = df[c].map(lambda v: _fmt(v, 3))
        print(f"\n    {pid}    breakeven_round_trip = {breakevens[pid]:.2f} bps")
        print(df.to_string(index=False))

    render_cost_sweep(
        {pid: sweep_tables[pid] for pid in COINTEGRATED_HEADLINE},
        breakevens,
        fig_dir / "cost_sweep__cointegrated.png",
    )

    # ----- Step C: capacity (all 7 pairs; participation ceiling) -----
    print("\n========== STAGE 5C: capacity (participation ceiling, 1%-ADV hard cap) ==========")
    tickers = sorted({t for p in cfg["universe"] for t in p["legs"]})
    vol_cache = ROOT / "data" / "volumes"
    volumes = load_volumes(tickers, cfg["data"]["start_date"],
                           pd.Timestamp.today().date().isoformat(),
                           vol_cache, refresh=False)
    cap_results = {}
    cap_rows = []
    for pid, pair in pairs.items():
        # Use median canonical β across walk-forward folds - robust to drift.
        beta_canon_per_fold = [f["beta_canonical"] for f in stage4[pid]["folds"]]
        median_beta = float(np.nanmedian(beta_canon_per_fold))
        res = pair_capacity(
            pid, (pair.legs[0], pair.legs[1]),
            beta_canonical=median_beta,
            volume_data=volumes,
            participation_cap=float(cfg["capacity"]["participation_cap"]),
            adv_window=int(cfg["capacity"]["adv_window_days"]),
        )
        cap_results[pid] = res
        cap_rows.append({
            "pair_id":          pid,
            "y_leg":            res.y_leg, "x_leg": res.x_leg,
            "median_beta":      res.beta_canonical,
            "adv_y_usd":        res.adv_y_usd,
            "adv_x_usd":        res.adv_x_usd,
            "binding_leg":      res.binding_leg,
            "capacity_aum_usd": res.capacity_aum_usd,
        })
    cap_df = pd.DataFrame(cap_rows).set_index("pair_id")
    cap_df.to_csv(stage5_dir / "capacity_participation_ceiling.csv")
    disp = cap_df.copy()
    for c in ["adv_y_usd", "adv_x_usd", "capacity_aum_usd"]:
        disp[c] = disp[c].map(_fmt_money)
    disp["median_beta"] = disp["median_beta"].map(lambda v: _fmt(v, 3))
    print(disp.to_string())
    print("\n  >> Reported as PARTICIPATION ceiling, not profitability ceiling. <<")
    print("  >> 'Above this AUM the average trade breaches 1%-ADV on the binding leg.' <<")

    # ----- Step D: event study (pooled cointegrated; GOOG/GOOGL alone) -----
    print("\n========== STAGE 5D: signal-decay event study ==========")
    window = tuple(cfg["event_study"]["window"])
    boot = cfg["event_study"]["bootstrap"]

    # Build per-pair rule+placebo panels by concatenating per-fold OOS z-series.
    pair_panels_rule, pair_panels_plac, pair_panels_disj = {}, {}, {}
    pair_panels_meta_hl_rule, pair_panels_meta_hl_plac = {}, {}   # half-lives per event row
    for pid in COINTEGRATED_HEADLINE:
        pair = pairs[pid]
        fz_list = reproduced[pid]["per_fold_z"]
        fpos_list = reproduced[pid]["per_fold_pos"]
        fentry_list = reproduced[pid]["per_fold_entry_z"]
        fhl_list = reproduced[pid]["per_fold_half_life"]

        # Per-pair concatenated OOS z (one long series), with each segment from its fold
        full_z = pd.concat(fz_list)
        full_pos = pd.concat(fpos_list)
        full_z = full_z[~full_z.index.duplicated(keep="first")]
        full_pos = full_pos[~full_pos.index.duplicated(keep="first")]

        # RULE events: state machine transitions in the composite OOS series
        rule_ev = rule_entry_events(full_pos, full_z)
        # Tag each rule event with its fold's half-life (look up by fold the event date falls in)
        rule_hl = []
        for _, ev in rule_ev.iterrows():
            for k, fz in enumerate(fz_list):
                if len(fz) and fz.index.min() <= ev["date"] <= fz.index.max():
                    rule_hl.append(fhl_list[k])
                    break
            else:
                rule_hl.append(np.nan)

        # PLACEBO events: per-fold scan with that fold's entry_z, then concat
        plac_ev_parts, plac_hl_parts = [], []
        for k, fz in enumerate(fz_list):
            ev_k = placebo_entry_events(fz, fentry_list[k])
            plac_ev_parts.append(ev_k)
            plac_hl_parts.extend([fhl_list[k]] * len(ev_k))
        plac_ev = pd.concat(plac_ev_parts, ignore_index=True) if plac_ev_parts else pd.DataFrame()

        # DISJOINT placebo: extreme-z bars that are NOT rule entries. Removes the
        # mechanical overlap that biases the headline comparison toward similarity.
        plac_disj_ev = disjoint_placebo_events(plac_ev, rule_ev)

        # Build panels (event paths on the per-pair concatenated z series)
        panel_rule = build_event_panel(full_z, rule_ev, window, pair_id=pid)
        panel_plac = build_event_panel(full_z, plac_ev, window, pair_id=pid)
        panel_disj = build_event_panel(full_z, plac_disj_ev, window, pair_id=pid)
        pair_panels_rule[pid] = panel_rule
        pair_panels_plac[pid] = panel_plac
        pair_panels_disj[pid] = panel_disj
        pair_panels_meta_hl_rule[pid] = np.array(rule_hl)
        pair_panels_meta_hl_plac[pid] = np.array(plac_hl_parts)

        print(f"  {pid:12s}  rule entries: {panel_rule.n_events}   "
              f"placebo events: {panel_plac.n_events}")

    # POOLED panel (GOOG/GOOGL + V/MA)
    pooled_rule = pool_event_panels([pair_panels_rule[p] for p in COINTEGRATED_HEADLINE])
    pooled_plac = pool_event_panels([pair_panels_plac[p] for p in COINTEGRATED_HEADLINE])
    pooled_rule_hl = np.concatenate([pair_panels_meta_hl_rule[p] for p in COINTEGRATED_HEADLINE])
    pooled_plac_hl = np.concatenate([pair_panels_meta_hl_plac[p] for p in COINTEGRATED_HEADLINE])

    print(f"\n  POOLED       rule entries: {pooled_rule.n_events}   "
          f"placebo events: {pooled_plac.n_events}")

    # Bootstrap CIs
    print("  bootstrapping CIs ...")
    rule_lo_pooled, rule_hi_pooled = stationary_block_bootstrap_ci(
        pooled_rule.panel, B=int(boot["B"]),
        mean_block_len=float(boot["mean_block_len_days"]),
        ci_level=float(boot["ci_level"]),
        seed=int(cfg["project"]["master_seed"]) + int(boot["seed_offset"]),
    )
    plac_lo_pooled, plac_hi_pooled = stationary_block_bootstrap_ci(
        pooled_plac.panel, B=int(boot["B"]),
        mean_block_len=float(boot["mean_block_len_days"]),
        ci_level=float(boot["ci_level"]),
        seed=int(cfg["project"]["master_seed"]) + int(boot["seed_offset"]) + 1,
    )

    # OU closed-form baseline curves
    ou_rule_pooled = ou_baseline_curve(
        z_entry_magnitudes=np.abs(pooled_rule.event_meta["z_entry"].values),
        half_lives_per_event=pooled_rule_hl,
        event_times=pooled_rule.event_times,
    )

    sep_pooled = curves_separate(
        pooled_rule.mean_curve(), rule_lo_pooled, rule_hi_pooled,
        pooled_plac.mean_curve(), plac_lo_pooled, plac_hi_pooled,
        pooled_rule.event_times, min_consecutive_days=5,
    )
    print(f"\n  POOLED separation diagnostic:")
    for k, v in sep_pooled.items():
        print(f"    {k:32s} {v}")

    render_event_study(
        pooled_rule.event_times,
        pooled_rule.mean_curve(), rule_lo_pooled, rule_hi_pooled, pooled_rule.n_events,
        pooled_plac.mean_curve(), plac_lo_pooled, plac_hi_pooled, pooled_plac.n_events,
        ou_rule_pooled,
        fig_dir / "event_study__pooled.png",
    )

    # ----- Disjoint-placebo robustness run (identical criterion, no overlap) -----
    pooled_disj = pool_event_panels([pair_panels_disj[p] for p in COINTEGRATED_HEADLINE])
    disj_lo, disj_hi = stationary_block_bootstrap_ci(
        pooled_disj.panel, B=int(boot["B"]),
        mean_block_len=float(boot["mean_block_len_days"]),
        ci_level=float(boot["ci_level"]),
        seed=int(cfg["project"]["master_seed"]) + int(boot["seed_offset"]) + 2,
    )
    sep_disjoint = curves_separate(
        pooled_rule.mean_curve(), rule_lo_pooled, rule_hi_pooled,
        pooled_disj.mean_curve(), disj_lo, disj_hi,
        pooled_rule.event_times, min_consecutive_days=5,
    )
    print(f"\n  POOLED disjoint-placebo separation diagnostic "
          f"({pooled_disj.n_events} events, rule bars removed):")
    for k, v in sep_disjoint.items():
        print(f"    {k:32s} {v}")

    # Single-pair GOOG/GOOGL version
    panel_g_rule = pair_panels_rule["GOOG_GOOGL"]
    panel_g_plac = pair_panels_plac["GOOG_GOOGL"]
    g_rule_hl = pair_panels_meta_hl_rule["GOOG_GOOGL"]
    rule_lo_g, rule_hi_g = stationary_block_bootstrap_ci(
        panel_g_rule.panel, B=int(boot["B"]),
        mean_block_len=float(boot["mean_block_len_days"]),
        ci_level=float(boot["ci_level"]),
        seed=int(cfg["project"]["master_seed"]) + int(boot["seed_offset"]) + 10,
    )
    plac_lo_g, plac_hi_g = stationary_block_bootstrap_ci(
        panel_g_plac.panel, B=int(boot["B"]),
        mean_block_len=float(boot["mean_block_len_days"]),
        ci_level=float(boot["ci_level"]),
        seed=int(cfg["project"]["master_seed"]) + int(boot["seed_offset"]) + 11,
    )
    ou_g = ou_baseline_curve(
        z_entry_magnitudes=np.abs(panel_g_rule.event_meta["z_entry"].values),
        half_lives_per_event=g_rule_hl,
        event_times=panel_g_rule.event_times,
    )
    sep_g = curves_separate(
        panel_g_rule.mean_curve(), rule_lo_g, rule_hi_g,
        panel_g_plac.mean_curve(), plac_lo_g, plac_hi_g,
        panel_g_rule.event_times, min_consecutive_days=5,
    )
    print(f"\n  GOOG_GOOGL single-pair separation diagnostic:")
    for k, v in sep_g.items():
        print(f"    {k:32s} {v}")
    render_event_study(
        panel_g_rule.event_times,
        panel_g_rule.mean_curve(), rule_lo_g, rule_hi_g, panel_g_rule.n_events,
        panel_g_plac.mean_curve(), plac_lo_g, plac_hi_g, panel_g_plac.n_events,
        ou_g,
        fig_dir / "event_study__GOOG_GOOGL.png",
    )

    # Persist event-study summary
    event_summary = {
        "pooled": {
            "n_rule_events":      pooled_rule.n_events,
            "n_placebo_events":   pooled_plac.n_events,
            "separation":         sep_pooled,
            "mean_curve_rule":    pooled_rule.mean_curve().tolist(),
            "ci_lo_rule":         rule_lo_pooled.tolist(),
            "ci_hi_rule":         rule_hi_pooled.tolist(),
            "mean_curve_placebo": pooled_plac.mean_curve().tolist(),
            "ci_lo_placebo":      plac_lo_pooled.tolist(),
            "ci_hi_placebo":      plac_hi_pooled.tolist(),
            "ou_curve":           ou_rule_pooled.tolist(),
            "event_times":        pooled_rule.event_times.tolist(),
        },
        "pooled_disjoint_placebo": {
            "n_events":           pooled_disj.n_events,
            "separation":         sep_disjoint,
            "mean_curve":         pooled_disj.mean_curve().tolist(),
            "ci_lo":              disj_lo.tolist(),
            "ci_hi":              disj_hi.tolist(),
        },
        "GOOG_GOOGL": {
            "n_rule_events":      panel_g_rule.n_events,
            "n_placebo_events":   panel_g_plac.n_events,
            "separation":         sep_g,
        },
    }
    (stage5_dir / "event_study.json").write_text(json.dumps(event_summary, indent=2, default=str))

    # ----- Step E: cross-section synthesis -----
    print("\n========== STAGE 5E: cross-section synthesis (all 7 pairs) ==========")
    syn_rows = []
    for pid, pair in pairs.items():
        s4 = stage4[pid]["summary"]
        folds = stage4[pid]["folds"]
        per_fold_S = np.array([f["sharpe_oos_net"] for f in folds], dtype=float)
        per_fold_S = per_fold_S[np.isfinite(per_fold_S)]
        per_fold_std = float(per_fold_S.std(ddof=1)) if len(per_fold_S) > 1 else float("nan")
        canon_betas = np.array([f["beta_canonical"] for f in folds], dtype=float)
        canon_betas = canon_betas[np.isfinite(canon_betas)]
        beta_min = float(canon_betas.min()) if len(canon_betas) else float("nan")
        beta_max = float(canon_betas.max()) if len(canon_betas) else float("nan")
        beta_range = beta_max - beta_min if np.isfinite(beta_max) and np.isfinite(beta_min) else float("nan")
        # Lo (2002) autocorrelation-adjusted annualization on the composite OOS net P&L.
        # sqrt(252) assumes serially uncorrelated returns, which a multi-day
        # mean-reversion hold violates by construction.
        ppar, spar = reproduced[pid]["pos_parts"], reproduced[pid]["spr_parts"]
        net = composite_pnl_at_cost(ppar, spar, cfg["costs"]["baseline_round_trip_bps"])["net_pnl"]
        lo = lo_annualization(net, max_lag=20)

        syn_rows.append({
            "pair_id":             pid,
            "cointegrated":        stage2_coint.get(pid, False),
            "S_oos_net":           s4["composite_sharpe_oos_net"],
            "S_oos_net_lo":        lo["sharpe_lo"],
            "lo_factor":           lo["factor_lo"],
            "rho1":                lo["rho"][0] if lo["rho"] else float("nan"),
            "AnnRet_oos_net":      s4["composite_annret_oos_net"],
            "pct_folds_positive":  s4["pct_folds_positive_net"],
            "per_fold_S_std":      per_fold_std,
            "beta_min":            beta_min,
            "beta_max":            beta_max,
            "beta_range":          beta_range,
            "breakeven_bps":       breakeven_all[pid],
            "capacity_aum_usd":    cap_results[pid].capacity_aum_usd,
        })
        if pid in COINTEGRATED_HEADLINE:
            print(f"  {pid:12s} Lo-adjusted: naive S={lo['sharpe_naive']:.3f} -> "
                  f"Lo S={lo['sharpe_lo']:.3f}  (factor {lo['factor_naive']:.2f} -> "
                  f"{lo['factor_lo']:.2f}, lags<=20)")
            print(f"               rho_1..rho_5 = "
                  + ", ".join(f"{r:+.4f}" for r in lo["rho"]))
    syn = pd.DataFrame(syn_rows).set_index("pair_id")
    syn.to_csv(stage5_dir / "cross_section_synthesis.csv")
    disp = syn.copy()
    for c in ["S_oos_net", "pct_folds_positive", "per_fold_S_std",
              "beta_min", "beta_max", "beta_range", "breakeven_bps"]:
        disp[c] = disp[c].map(lambda v: _fmt(v, 2 if c != "breakeven_bps" else 1))
    disp["capacity_aum_usd"] = disp["capacity_aum_usd"].map(_fmt_money)
    print(disp.to_string())
    print("\n  Framing footnotes (write these into the table caption verbatim):")
    print("   - Walk-forward and single-split diverge in direction depending on the pair's")
    print("     modal lookback and regime mix; do not write 'walk-forward higher across the board'.")
    print("   - Per-fold cell selection clusters in a region for the load-bearing pairs;")
    print("     stage-3 picks sit inside that cluster - cluster, not pin, not scatter.")
    print("   - Capacity numbers are PARTICIPATION ceilings (1%-ADV), NOT profitability ceilings.")

    # Persist a single JSON for downstream report consumption
    payload = {
        "config_sha256":  fingerprint,
        "cost_sweep":     {pid: sweep_tables[pid].to_dict(orient="records") for pid in pairs},
        "breakeven_bps":  {pid: float(v) for pid, v in breakeven_all.items()},
        "capacity":       {pid: {k: _native(v) for k, v in asdict(r).items()}
                           for pid, r in cap_results.items()},
        "event_study":    event_summary,
        "synthesis":      syn.reset_index().to_dict(orient="records"),
    }
    (results_dir / "stage5_summary.json").write_text(json.dumps(payload, indent=2, default=str))

    print("\n========== STAGE 5 COMPLETE - STOP FOR APPROVAL ==========")


if __name__ == "__main__":
    main()
