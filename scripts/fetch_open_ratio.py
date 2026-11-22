"""Fetch the same-day Open/Close ratio so next-open execution can be priced.

Why a ratio and not an open price. The 2026-05-30 parquet snapshot in data/raw is
the basis of every number in the paper, and Appendix A pins it. yfinance serves
BACKWARD-adjusted history: any distribution after the snapshot restates the whole
adjusted series, which is exactly the limitation Section 5 discloses. Re-fetching
the close would therefore silently re-base the paper.

    r[t] = Open[t] / Close[t]

is taken within a single bar, so whatever per-date adjustment factor the source
applies cancels. Open and Close come from ONE download call so both carry the same
auto_adjust setting and the ratio is correct under either. The reconstructed open,

    open[t] = cached_adj_close[t] * r[t]

therefore lives in the cached snapshot's price space and leaves it untouched.

Writes data/raw_open/<TICKER>__<fetch_date>.parquet. The 2026-05-30 files are
never opened for writing.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config_io import load_config
from src.data import _latest_cached, _cache_path      # noqa: F401  (path helpers)

RATIO_LO, RATIO_HI = 0.90, 1.10


def fetch_open_close(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Open and Close from a single yfinance call, so both share auto_adjust."""
    import yfinance as yf

    end_pad = (pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat()
    df = yf.download(ticker, start=start, end=end_pad, progress=False,
                     auto_adjust=False, actions=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned empty Open/Close for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        o = df[("Open", ticker)] if ("Open", ticker) in df.columns \
            else df.xs("Open", axis=1, level=0).iloc[:, 0]
        c = df[("Close", ticker)] if ("Close", ticker) in df.columns \
            else df.xs("Close", axis=1, level=0).iloc[:, 0]
    else:
        o, c = df["Open"], df["Close"]
    out = pd.DataFrame({"open": o.values, "close": c.values},
                       index=pd.to_datetime(o.index).tz_localize(None))
    return out.dropna()


def main() -> None:
    cfg = load_config()
    cache_dir = ROOT / cfg["data"]["cache_dir"]
    out_dir = ROOT / "data" / "raw_open"
    out_dir.mkdir(parents=True, exist_ok=True)
    fetch_date = date.today().isoformat()

    tickers = sorted({t for p in cfg["universe"] for t in p["legs"]})
    start = cfg["data"]["start_date"]
    end = cfg["data"]["end_date"]
    if end == "auto":
        end = date.today().isoformat()

    problems = []
    for tk in tickers:
        cached_files = sorted(cache_dir.glob(f"{tk}__*.parquet"))
        if not cached_files:
            raise RuntimeError(f"no cached snapshot for {tk}")
        cached = pd.read_parquet(cached_files[-1]).iloc[:, 0]
        cached.index = pd.to_datetime(cached.index)
        snap_lo, snap_hi = cached.index.min(), cached.index.max()

        oc = fetch_open_close(tk, start, end)
        r = (oc["open"] / oc["close"]).rename("ratio")

        # Restrict to the snapshot's own window before comparing indices.
        r_win = r.loc[(r.index >= snap_lo) & (r.index <= snap_hi)]

        missing = cached.index.difference(r_win.index)
        extra = r_win.index.difference(cached.index)
        if len(missing) or len(extra):
            problems.append(
                f"{tk}: date index mismatch vs snapshot - {len(missing)} missing, "
                f"{len(extra)} extra. first missing: "
                f"{missing[0].date() if len(missing) else '-'}")
            continue

        bad = r_win[(r_win <= RATIO_LO) | (r_win >= RATIO_HI)]
        if len(bad):
            problems.append(f"{tk}: {len(bad)} bars with Open/Close outside "
                            f"({RATIO_LO}, {RATIO_HI}): "
                            + ", ".join(f"{d.date()}={v:.4f}"
                                        for d, v in list(bad.items())[:8]))

        open_recon = (cached * r_win.reindex(cached.index)).rename(tk)
        path = out_dir / f"{tk}__{fetch_date}.parquet"
        pd.DataFrame({"ratio": r_win.reindex(cached.index),
                      "open_recon": open_recon}).to_parquet(path)
        (out_dir / f"{tk}__{fetch_date}.meta.json").write_text(json.dumps({
            "ticker": tk, "fetch_date": fetch_date,
            "snapshot_used": cached_files[-1].name,
            "n_bars": int(len(open_recon)),
            "ratio_min": float(r_win.min()), "ratio_max": float(r_win.max()),
            "note": "open_recon = cached_adj_close * (Open/Close) from a single "
                    "yfinance call; adjustment-invariant by construction",
        }, indent=2))
        print(f"  {tk:6s} n={len(open_recon):5d}  ratio in "
              f"[{r_win.min():.4f}, {r_win.max():.4f}]  -> {path.name}")

    if problems:
        print("\nPROBLEMS (reported, not clipped, not filled):")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print(f"\nOK. Wrote {len(tickers)} files to {out_dir}. "
          f"Snapshot in {cache_dir} untouched.")


if __name__ == "__main__":
    main()
