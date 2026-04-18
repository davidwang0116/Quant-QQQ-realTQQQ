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
    start: str = "1993-01-01",
    end: str | None = None,
    column: str = "Close",
    force_refresh: bool = False,
) -> pd.Series:
    """
    Return a daily adjusted-close price Series for `ticker`.

    Data is cached as Parquet; cache is refreshed if it is >1 day old
    or if `force_refresh=True`.

    Parameters
    ----------
    ticker        : Yahoo Finance ticker symbol
    start         : ISO date string for the start of history
    end           : ISO date string (defaults to today)
    column        : which OHLCV column to return
    force_refresh : bypass the cache
    """
    end = end or datetime.today().strftime("%Y-%m-%d")
    cache = _cache_path(ticker)

    # Load from cache if fresh
    if cache.exists() and not force_refresh:
        age = datetime.now() - datetime.fromtimestamp(cache.stat().st_mtime)
        if age < timedelta(hours=20):
            logger.info(f"[cache] Loading {ticker} from {cache}")
            df = pd.read_parquet(cache)
            return df[column].loc[start:end]

    # Download from Yahoo Finance
    logger.info(f"[yfinance] Downloading {ticker} {start} → {end}")
    raw = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'. Check the symbol.")

    # Flatten MultiIndex columns that yfinance sometimes returns
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    raw.index = pd.to_datetime(raw.index)
    raw.to_parquet(cache)
    logger.info(f"[cache] Saved {ticker} → {cache}  ({len(raw)} rows)")

    return raw[column].loc[start:end]


def fetch_multiple(
    tickers: list[str],
    start: str = "1993-01-01",
    end: str | None = None,
    column: str = "Close",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Convenience wrapper — returns a DataFrame with one column per ticker."""
    return pd.DataFrame(
        {t: fetch_prices(t, start, end, column, force_refresh) for t in tickers}
    )


def clear_cache(ticker: str | None = None) -> None:
    """Delete cached Parquet files. Pass ticker=None to clear all."""
    if ticker:
        p = _cache_path(ticker)
        if p.exists():
            p.unlink()
            logger.info(f"Cleared cache for {ticker}")
    else:
        for f in CACHE_DIR.glob("*.parquet"):
            f.unlink()
        logger.info("Cleared all cached data")
