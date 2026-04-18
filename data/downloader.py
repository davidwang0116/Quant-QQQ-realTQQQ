"""
Data Layer — download & cache historical price data via yfinance.
All data is stored locally as Parquet files to avoid re-downloading.
"""

from __future__ import annotations
import logging
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker.upper()}.parquet"


def fetch_prices(
    ticker: str,
    start:         str  = "1993-01-01",
    end:           str | None = None,
    column:        str  = "Close",
    force_refresh: bool = False,
) -> pd.Series:
    """
    Return a daily adjusted-close price Series for `ticker`.
    Data is cached as Parquet; refreshed if >20 hours old or force_refresh=True.
    """
    end   = end or datetime.today().strftime("%Y-%m-%d")
    cache = _cache_path(ticker)

    if cache.exists() and not force_refresh:
        age = datetime.now() - datetime.fromtimestamp(cache.stat().st_mtime)
        if age < timedelta(hours=20):
            logger.info(f"[cache] {ticker} loaded from {cache}")
            df = pd.read_parquet(cache)
            return df[column].loc[start:end]

    logger.info(f"[yfinance] Downloading {ticker}  {start} → {end}")
    raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)

    if raw.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'.")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw.index = pd.to_datetime(raw.index)
    raw.to_parquet(cache)
    logger.info(f"[cache] {ticker} saved → {cache}  ({len(raw)} rows)")
    return raw[column].loc[start:end]


def clear_cache(ticker: str | None = None) -> None:
    if ticker:
        p = _cache_path(ticker)
        if p.exists():
            p.unlink()
    else:
        for f in CACHE_DIR.glob("*.parquet"):
            f.unlink()
