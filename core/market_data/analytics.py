"""Provider-backed stock details and transparent technical screening."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf

from core.market_data.provider import YFinanceProvider


def _number(value: Any) -> float | None:
    """Convert an optional provider value to a finite float."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _ticker(symbol: str, exchange: str) -> yf.Ticker:
    """Create a Yahoo Finance ticker for an Indian exchange symbol."""
    suffix = {"NSE": ".NS", "BSE": ".BO"}.get(exchange.upper())
    if suffix is None:
        raise ValueError(f"Unsupported exchange: {exchange}")
    return yf.Ticker(f"{symbol.strip().upper()}{suffix}")


def get_stock_details(symbol: str, exchange: str = "NSE") -> dict[str, Any]:
    """Return quote, fundamentals, and recent technical indicators for a stock."""
    normalized_symbol = symbol.strip().upper()
    ticker = _ticker(normalized_symbol, exchange)
    info = ticker.info
    history = YFinanceProvider().get_history(normalized_symbol, exchange, "1y", "1d")
    if history.empty or "Close" not in history:
        raise ValueError(f"No historical data returned for {exchange}:{normalized_symbol}")
    close = history["Close"].dropna().astype(float)
    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2]) if len(close) > 1 else None
    details = {
        "symbol": normalized_symbol,
        "exchange": exchange.upper(),
        "name": info.get("longName") or info.get("shortName") or normalized_symbol,
        "sector": info.get("sector") or "Unavailable",
        "industry": info.get("industry") or "Unavailable",
        "price": latest,
        "previous_close": previous,
        "day_change_pct": ((latest - previous) / previous * 100) if previous else None,
        "market_cap": _number(info.get("marketCap")),
        "pe_ratio": _number(info.get("trailingPE")),
        "forward_pe": _number(info.get("forwardPE")),
        "dividend_yield": _number(info.get("dividendYield")),
        "52_week_high": _number(info.get("fiftyTwoWeekHigh")),
        "52_week_low": _number(info.get("fiftyTwoWeekLow")),
        "sma_20": float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None,
        "sma_50": float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None,
        "return_1m_pct": float((latest / close.iloc[-22] - 1) * 100) if len(close) > 22 else None,
        "return_1y_pct": float((latest / close.iloc[0] - 1) * 100) if len(close) > 1 else None,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }
    return details


def get_stock_recommendation(symbol: str, exchange: str = "NSE") -> dict[str, Any]:
    """Score trend and momentum without presenting the result as investment advice."""
    details = get_stock_details(symbol, exchange)
    score = 0
    signals: list[str] = []
    if details["sma_20"] is not None and details["price"] > details["sma_20"]:
        score += 2
        signals.append("price above 20-day average")
    if details["sma_20"] is not None and details["sma_50"] is not None and details["sma_20"] > details["sma_50"]:
        score += 1
        signals.append("20-day trend above 50-day trend")
    if details["return_1m_pct"] is not None and details["return_1m_pct"] > 0:
        score += 1
        signals.append("positive one-month momentum")
    if details["return_1m_pct"] is not None and details["return_1m_pct"] < 0:
        score -= 1
        signals.append("negative one-month momentum")
    if details["day_change_pct"] is not None and details["day_change_pct"] < -3:
        score -= 1
        signals.append("large daily decline")
    label = "BUY CANDIDATE" if score >= 3 else "WATCH" if score >= 1 else "WAIT"
    return {
        "Symbol": details["symbol"],
        "Exchange": details["exchange"],
        "Sector": details["sector"],
        "Price": details["price"],
        "1M return %": details["return_1m_pct"],
        "Trend score": score,
        "Screen": label,
        "Signals": "; ".join(signals) or "no positive trend signal",
    }
