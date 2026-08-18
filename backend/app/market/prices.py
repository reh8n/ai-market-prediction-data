"""Daily OHLCV bars and quote metadata via yfinance.

yfinance wraps Yahoo's unofficial endpoints. It is free and needs no key, but
it can break without notice - every call here is defensive and the pipeline
treats price data as optional enrichment, never a hard dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Quote:
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    market_cap: float | None = None
    currency: str | None = None


class PriceError(RuntimeError):
    pass


def fetch_quote(ticker: str) -> Quote:
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as exc:
        raise PriceError(f"Quote lookup failed for {ticker}: {exc}") from exc

    if not info.get("longName") and not info.get("shortName"):
        raise PriceError(f"No quote data returned for {ticker}")

    return Quote(
        ticker=ticker.upper(),
        name=info.get("longName") or info.get("shortName"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        exchange=info.get("fullExchangeName") or info.get("exchange"),
        market_cap=info.get("marketCap"),
        currency=info.get("currency"),
    )


def fetch_daily_bars(ticker: str, period: str = "5y") -> list[Bar]:
    """Daily bars. `period` accepts yfinance shorthand: 1y, 5y, max, ..."""
    import yfinance as yf

    try:
        frame = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
    except Exception as exc:
        raise PriceError(f"Price history failed for {ticker}: {exc}") from exc

    if frame is None or frame.empty:
        raise PriceError(f"No price history returned for {ticker}")

    bars: list[Bar] = []
    for index, row in frame.iterrows():
        bars.append(
            Bar(
                day=index.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        )
    return bars


def window_return(bars: list[Bar], start: date, end: date) -> float | None:
    """Percent close-to-close return between the first and last bar in a window."""
    inside = [b for b in bars if start <= b.day <= end]
    if len(inside) < 2:
        return None
    first, last = inside[0].close, inside[-1].close
    if not first:
        return None
    return round(((last - first) / first) * 100, 2)


def trailing_return(bars: list[Bar], days: int) -> float | None:
    if len(bars) < 2:
        return None
    window = bars[-days:] if len(bars) > days else bars
    first, last = window[0].close, window[-1].close
    if not first:
        return None
    return round(((last - first) / first) * 100, 2)


def realized_volatility(bars: list[Bar], days: int = 252) -> float | None:
    """Annualized close-to-close volatility, as a percentage."""
    window = bars[-days:] if len(bars) > days else bars
    if len(window) < 3:
        return None

    returns = []
    for previous, current in zip(window, window[1:]):
        if previous.close:
            returns.append((current.close - previous.close) / previous.close)
    if len(returns) < 2:
        return None

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return round((variance**0.5) * (252**0.5) * 100, 2)
