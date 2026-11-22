"""Centralized matplotlib style. One style, same fonts and colors everywhere.

Working-paper figure conventions: serif text matching the TeX Gyre Pagella
body font of the paper, no in-figure titles or narrative text, grayscale-first
encoding (line style and fill, not hue, distinguish series), no grid.
Interpretation belongs in the caption, not inside the axes.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt


PALETTE = {
    "ink":   "#1a1a1a",   # primary series
    "gray":  "#5a5a5a",   # secondary series
    "band":  "#b0b0b0",   # CI bands, min-max envelopes
    "faint": "#cccccc",   # reference lines
    # legacy keys consumed by the stage 1-3 diagnostic figures
    "leg0": "#1a1a1a",
    "leg1": "#5a5a5a",
    "spread": "#444444",
    "pos": "#6e6e6e",
    "neg": "#ffffff",
    "muted": "#888888",
    "alpha_line": "#1a1a1a",
    "ok": "#6e6e6e",
    "fail": "#b0b0b0",
}


def apply_style() -> None:
    mpl.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "font.family": "serif",
        # Palatino chain: closest system matches to the paper's Pagella body.
        "font.serif": ["Palatino Linotype", "TeX Gyre Pagella", "Book Antiqua",
                       "Georgia", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "axes.unicode_minus": False,
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.titleweight": "normal",
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.linewidth": 0.7,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "hatch.linewidth": 0.5,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "lines.linewidth": 1.0,
    })
