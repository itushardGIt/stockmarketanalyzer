"""Swappable market-price provider boundary for Phase 2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import pandas as pd
import yfinance as yf


@dataclass(frozen=True, slots=True)
class Quote:
    """Latest delayed quote returned by a market data provider."""

    symbol: str
    exchange: str
    price: float
    previous_close: float | None
    day_change_pct: float | None
    fetched_at: datetime


class PriceProvider(Protocol):
    """Contract implemented by public or paid price providers."""

    def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Return the latest quote for an exchange symbol."""

    def get_history(self, symbol: str, exchange: str, period: str, interval: str) -> pd.DataFrame:
        """Return OHLC history for an exchange symbol."""


class YFinanceProvider:
    """Yahoo Finance-backed provider using NSE/BSE ticker suffixes."""

    @staticmethod
    def _ticker(symbol: str, exchange: str) -> str:
        """Build a Yahoo Finance ticker from a broker symbol."""
        suffix = {"NSE": ".NS", "BSE": ".BO"}.get(exchange.upper())
        if suffix is None:
            raise ValueError(f"Unsupported exchange: {exchange}")
        return f"{symbol.strip().upper()}{suffix}"

    def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Fetch a delayed quote and calculate the local day-change percentage."""
        history = self.get_history(symbol, exchange, period="5d", interval="1d")
        closes = history["Close"].dropna()
        if closes.empty:
            raise ValueError(f"No quote returned for {exchange}:{symbol}")
        price = float(closes.iloc[-1])
        previous_close = float(closes.iloc[-2]) if len(closes) > 1 else None
        day_change_pct = ((price - previous_close) / previous_close * 100) if previous_close else None
        return Quote(symbol.upper(), exchange.upper(), price, previous_close, day_change_pct, datetime.now())

    def get_history(self, symbol: str, exchange: str, period: str, interval: str) -> pd.DataFrame:
        """Fetch OHLC history from Yahoo Finance for one symbol."""
        return yf.Ticker(self._ticker(symbol, exchange)).history(period=period, interval=interval, auto_adjust=False)