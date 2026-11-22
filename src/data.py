"""Data layer: fetch adjusted-close series, align on NYSE calendar, validate, cache.

Discipline:
- yfinance primary; Stooq fallback (via pandas-datareader) if yfinance returns empty.
- Adjusted close only (splits + dividends handled by source).
- Raw fetched series cached to parquet with the fetch date stamped in filename and
  inside the parquet's metadata, so re-running on a different day cannot silently
  alter prior results.
- Per-pair alignment: inner-join on the intersection of available dates restricted
  to the configured study window. Forward-fill is explicitly NOT allowed.
- Validation: zero internal gaps, monotonic index, n_obs >= min_obs_per_pair,
  GOOG/GOOGL bound at >= 2014-04-03.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from .config_io import load_config, repo_root


# ---------- Public types ----------

@dataclass
class TickerSeries:
    ticker: str
    series: pd.Series          # adjusted close, indexed by date
    source: str                # "yfinance" or "stooq"
    fetch_date: str            # YYYY-MM-DD when the data was fetched
    start: str
    end: str
    n_obs: int


@dataclass
class PairData:
    pair_id: str
    legs: List[str]
    df: pd.DataFrame           # canonical analysis frame (log-prices when input_space="log")
    df_levels: pd.DataFrame    # raw adjusted close; used for raw-price plots and dollar scaling
    input_space: str           # "log" or "level"
    start: str
    end: str
    n_obs: int
    missing_pct: float
    train: pd.DataFrame        # train slice of df (the analysis frame)
    test: pd.DataFrame         # test slice of df  (the analysis frame)


# ---------- Fetchers ----------

def _resolve_end_date(cfg_end: str) -> str:
    if cfg_end == "auto":
        return date.today().isoformat()
    return cfg_end


def _fetch_yfinance(ticker: str, start: str, end: str) -> pd.Series:
    import yfinance as yf

    # yfinance end is exclusive; pad by one day to include the requested end bar.
    end_pad = (pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat()
    df = yf.download(
        ticker,
        start=start,
        end=end_pad,
        progress=False,
        auto_adjust=False,
        actions=False,
        threads=False,
    )
    if df is None or df.empty:
        return pd.Series(dtype="float64", name=ticker)
    # yfinance >=0.2 returns MultiIndex columns when ticker is a single string in some versions.
    if isinstance(df.columns, pd.MultiIndex):
        # ('Adj Close', 'TICKER')
        if ("Adj Close", ticker) in df.columns:
            s = df[("Adj Close", ticker)]
        else:
            # Fallback to first level == 'Adj Close'
            adj = df.xs("Adj Close", axis=1, level=0)
            s = adj.iloc[:, 0]
    else:
        if "Adj Close" not in df.columns:
            return pd.Series(dtype="float64", name=ticker)
        s = df["Adj Close"]
    s = pd.Series(s.values, index=pd.to_datetime(s.index).tz_localize(None), name=ticker)
    s = s.dropna()
    return s


def _fetch_stooq(ticker: str, start: str, end: str) -> pd.Series:
    """Stooq fallback. Uses pandas-datareader; tickers append '.us'."""
    from pandas_datareader import data as pdr

    sym = f"{ticker}.us" if not ticker.endswith(".us") else ticker
    try:
        df = pdr.DataReader(sym, "stooq", start=start, end=end)
    except Exception:
        return pd.Series(dtype="float64", name=ticker)
    if df is None or df.empty:
        return pd.Series(dtype="float64", name=ticker)
    # Stooq returns descending dates and unadjusted close - best free fallback we have.
    df = df.sort_index()
    s = df["Close"].copy()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s.name = ticker
    s = s.dropna()
    return s


def fetch_ticker(ticker: str, start: str, end: str) -> TickerSeries:
    """Fetch one ticker. yfinance first, Stooq fallback if empty."""
    series = _fetch_yfinance(ticker, start, end)
    source = "yfinance"
    if series.empty:
        series = _fetch_stooq(ticker, start, end)
        source = "stooq"
    if series.empty:
        raise RuntimeError(f"Both yfinance and stooq returned empty data for {ticker}")
    # Clip to requested window (defensive - yfinance/stooq sometimes return extras).
    series = series.loc[(series.index >= pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]
    return TickerSeries(
        ticker=ticker,
        series=series,
        source=source,
        fetch_date=date.today().isoformat(),
        start=series.index.min().date().isoformat(),
        end=series.index.max().date().isoformat(),
        n_obs=len(series),
    )


# ---------- Caching ----------

def _cache_path(cache_dir: Path, ticker: str, fetch_date: str) -> Path:
    return cache_dir / f"{ticker}__{fetch_date}.parquet"


def _latest_cached(cache_dir: Path, ticker: str) -> Path | None:
    matches = sorted(cache_dir.glob(f"{ticker}__*.parquet"))
    return matches[-1] if matches else None


def load_or_fetch_ticker(
    ticker: str,
    start: str,
    end: str,
    cache_dir: Path,
    *,
    refresh: bool = False,
) -> TickerSeries:
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not refresh:
        cached = _latest_cached(cache_dir, ticker)
        if cached is not None:
            df = pd.read_parquet(cached)
            # Re-derive metadata
            meta_path = cached.with_suffix(".meta.json")
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
            else:
                meta = {}
            s = df.iloc[:, 0]
            s.index = pd.to_datetime(s.index).tz_localize(None)
            s.name = ticker
            # Truncate to requested window
            s = s.loc[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
            return TickerSeries(
                ticker=ticker,
                series=s,
                source=meta.get("source", "cache"),
                fetch_date=meta.get("fetch_date", cached.stem.split("__")[-1]),
                start=s.index.min().date().isoformat() if len(s) else start,
                end=s.index.max().date().isoformat() if len(s) else end,
                n_obs=len(s),
            )
    ts = fetch_ticker(ticker, start, end)
    out_path = _cache_path(cache_dir, ticker, ts.fetch_date)
    ts.series.to_frame().to_parquet(out_path)
    meta = {"ticker": ticker, "source": ts.source, "fetch_date": ts.fetch_date,
            "start": ts.start, "end": ts.end, "n_obs": ts.n_obs}
    out_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return ts


# ---------- Volume fetcher (separate cache for capacity analysis) ----------

def _fetch_yfinance_volume(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Returns a DataFrame with columns ['close', 'volume'] indexed by date.

    The price column here is the UNADJUSTED close (yfinance Close), because dollar
    volume = shares × the dollar price actually exchanged on the day, not the split-
    /dividend-adjusted price. Using Adj Close would inflate historical dollar volume.
    """
    import yfinance as yf

    end_pad = (pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat()
    df = yf.download(
        ticker, start=start, end=end_pad,
        progress=False, auto_adjust=False, actions=False, threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame(columns=["close", "volume"])
    if isinstance(df.columns, pd.MultiIndex):
        close = df[("Close", ticker)] if ("Close", ticker) in df.columns else df.xs("Close", axis=1, level=0).iloc[:, 0]
        vol = df[("Volume", ticker)] if ("Volume", ticker) in df.columns else df.xs("Volume", axis=1, level=0).iloc[:, 0]
    else:
        if "Close" not in df.columns or "Volume" not in df.columns:
            return pd.DataFrame(columns=["close", "volume"])
        close, vol = df["Close"], df["Volume"]
    out = pd.DataFrame({"close": close.values, "volume": vol.values},
                       index=pd.to_datetime(close.index).tz_localize(None))
    out = out.dropna()
    out = out.loc[(out.index >= pd.Timestamp(start)) & (out.index <= pd.Timestamp(end))]
    return out


def load_or_fetch_volume(
    ticker: str, start: str, end: str, cache_dir: Path, *, refresh: bool = False
) -> pd.DataFrame:
    """Volume cache lives in data/volumes/ - separate from the close-price cache so
    we don't have to invalidate the existing price parquets to add a column.
    Filename pattern matches the price cache: <ticker>__<fetch_date>.parquet.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not refresh:
        matches = sorted(cache_dir.glob(f"{ticker}__*.parquet"))
        if matches:
            df = pd.read_parquet(matches[-1])
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
            return df
    df = _fetch_yfinance_volume(ticker, start, end)
    if df.empty:
        raise RuntimeError(f"Volume fetch returned empty for {ticker}")
    fetch_date = date.today().isoformat()
    df.to_parquet(cache_dir / f"{ticker}__{fetch_date}.parquet")
    return df


def load_volumes(tickers: List[str], start: str, end: str, cache_dir: Path,
                 *, refresh: bool = False) -> Dict[str, pd.DataFrame]:
    return {t: load_or_fetch_volume(t, start, end, cache_dir, refresh=refresh) for t in tickers}


# ---------- Calendar alignment & validation ----------

def _nyse_sessions(start: str, end: str) -> pd.DatetimeIndex:
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=start, end_date=end)
    idx = sched.index
    # Normalize to tz-naive midnight
    return pd.DatetimeIndex(pd.to_datetime(idx).tz_localize(None).normalize())


def build_pair(
    pair_id: str,
    legs: List[str],
    ticker_data: Dict[str, TickerSeries],
    *,
    start: str,
    end: str,
    train_test_split_date: str,
    drop_if_any_missing: bool,
    input_space: str = "log",
) -> PairData:
    s1 = ticker_data[legs[0]].series
    s2 = ticker_data[legs[1]].series
    levels = pd.concat([s1, s2], axis=1, join="inner")
    levels.columns = legs
    # Restrict to the configured study window
    levels = levels.loc[(levels.index >= pd.Timestamp(start)) & (levels.index <= pd.Timestamp(end))]
    levels = levels.sort_index()

    if drop_if_any_missing:
        levels = levels.dropna(how="any")
    levels = levels[~levels.index.duplicated(keep="first")]

    # NYSE-session check: missing pct measured against expected sessions in the window
    expected_sessions = _nyse_sessions(
        levels.index.min().date().isoformat() if len(levels) else start,
        levels.index.max().date().isoformat() if len(levels) else end,
    )
    obs_idx = pd.DatetimeIndex(levels.index.normalize())
    missing = expected_sessions.difference(obs_idx)
    missing_pct = float(len(missing)) / max(len(expected_sessions), 1) * 100.0

    # Build analysis frame
    if input_space == "log":
        df = np.log(levels)
    elif input_space == "level":
        df = levels.copy()
    else:
        raise ValueError(f"Unknown input_space={input_space!r}; expected 'log' or 'level'")
    df.columns = legs  # preserve names through transform

    split_ts = pd.Timestamp(train_test_split_date)
    train = df.loc[df.index <= split_ts]
    test = df.loc[df.index > split_ts]

    return PairData(
        pair_id=pair_id,
        legs=list(legs),
        df=df,
        df_levels=levels,
        input_space=input_space,
        start=df.index.min().date().isoformat() if len(df) else start,
        end=df.index.max().date().isoformat() if len(df) else end,
        n_obs=len(df),
        missing_pct=missing_pct,
        train=train,
        test=test,
    )


def load_universe(config: dict, *, refresh: bool = False) -> Dict[str, PairData]:
    """Fetch (or load cached) all tickers, align each pair, return dict pair_id -> PairData."""
    start = config["data"]["start_date"]
    end = _resolve_end_date(config["data"]["end_date"])
    cache_dir = repo_root() / config["data"]["cache_dir"]
    split_date = config["data"]["train_test_split_date"]
    drop_missing = config["data"]["drop_if_any_missing"]
    input_space = config["data"].get("input_space", "log")

    # Collect unique tickers across the universe
    tickers: List[str] = []
    for pair in config["universe"]:
        for leg in pair["legs"]:
            if leg not in tickers:
                tickers.append(leg)

    ticker_data: Dict[str, TickerSeries] = {}
    for t in tickers:
        ticker_data[t] = load_or_fetch_ticker(t, start, end, cache_dir, refresh=refresh)

    pairs: Dict[str, PairData] = {}
    for pair in config["universe"]:
        pid = pair["id"]
        pairs[pid] = build_pair(
            pid,
            pair["legs"],
            ticker_data,
            start=start,
            end=end,
            train_test_split_date=split_date,
            drop_if_any_missing=drop_missing,
            input_space=input_space,
        )

    return pairs


# ---------- Validation report ----------

def validate_universe(pairs: Dict[str, PairData], config: dict) -> pd.DataFrame:
    """Return a summary frame and assert critical invariants."""
    rows = []
    min_obs = int(config["data"]["min_obs_per_pair"])
    for pid, p in pairs.items():
        rows.append({
            "pair_id": pid,
            "legs": "/".join(p.legs),
            "start": p.start,
            "end": p.end,
            "n_obs": p.n_obs,
            "n_train": len(p.train),
            "n_test": len(p.test),
            "missing_pct": round(p.missing_pct, 3),
        })
    summary = pd.DataFrame(rows).set_index("pair_id")

    # Hard invariants
    for pid, p in pairs.items():
        assert p.n_obs >= min_obs, f"{pid}: n_obs={p.n_obs} < min_obs_per_pair={min_obs}"
        if "GOOG" in p.legs or "GOOGL" in p.legs:
            assert p.start >= "2014-04-03", f"{pid}: start={p.start} predates GOOG/GOOGL C-share creation"
        assert p.df.index.is_monotonic_increasing, f"{pid}: index not monotonic"
        assert not p.df.isna().any().any(), f"{pid}: NaNs in analysis frame"
        assert not p.df_levels.isna().any().any(), f"{pid}: NaNs in levels frame"
        # Strictly positive levels (so log is well-defined)
        assert (p.df_levels > 0).all().all(), f"{pid}: non-positive levels (log undefined)"

    return summary


def write_processed(pairs: Dict[str, PairData], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for pid, p in pairs.items():
        p.df.to_parquet(out_dir / f"{pid}__analysis.parquet")
        p.df_levels.to_parquet(out_dir / f"{pid}__levels.parquet")
