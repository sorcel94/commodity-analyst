import pandas as pd
import streamlit as st
import yfinance as yf
from fredapi import Fred

from commodity_analyst.config import FRED_API_KEY

_MMBTU_PER_MWH = 3.412


def _download_yfinance(ticker: str, period: str) -> pd.DataFrame:
    raw: pd.DataFrame = yf.download(ticker, period=period, progress=False)  # pyright: ignore[reportAssignmentType]
    if raw.empty:
        return pd.DataFrame({"close": pd.Series(dtype="float64"), "change": pd.Series(dtype="float64")})
    # yfinance returns MultiIndex columns: (Price, Ticker) - flatten
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = pd.DataFrame({"close": raw["Close"]})
    df["change"] = df["close"].diff()
    df.index.name = "date"
    return df


def _get_eurusd() -> float:
    """Fetch latest EUR/USD exchange rate from yfinance."""
    raw: pd.DataFrame = yf.download("EURUSD=X", period="5d", progress=False)  # pyright: ignore[reportAssignmentType]
    if raw.empty:
        return 1.08
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return float(raw["Close"].iloc[-1])


@st.cache_data(ttl=300)
def get_ttf(period: str = "1y") -> pd.DataFrame:
    """Fetch TTF front-month futures (EUR/MWh). Columns: close, change."""
    return _download_yfinance("TTF=F", period)


@st.cache_data(ttl=300)
def get_henry_hub(period: str = "1y") -> pd.DataFrame:
    """Fetch Henry Hub front-month futures (USD/MMBtu). Columns: close, change."""
    return _download_yfinance("NG=F", period)


@st.cache_data(ttl=86400)
def get_jkm() -> pd.DataFrame:
    """Fetch JKM proxy (Japan/Korea LNG import price) from FRED, converted to EUR/MWh.

    Source is FRED PNGASJPUSDM in USD/MMBtu (monthly).
    Converted using live EUR/USD rate and energy equivalence (3.412 MMBtu/MWh).
    Columns: close (EUR/MWh), close_usd_mmbtu (original).
    """
    f = Fred(api_key=FRED_API_KEY)
    series = f.get_series("PNGASJPUSDM")
    eurusd = _get_eurusd()
    df = pd.DataFrame({"close_usd_mmbtu": series})
    df["close"] = df["close_usd_mmbtu"] * _MMBTU_PER_MWH / eurusd
    df.index.name = "date"
    return df
