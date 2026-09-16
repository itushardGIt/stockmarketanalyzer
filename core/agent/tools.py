"""Exact relational and cached-market tools exposed to the agent."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from core.storage.database import create_database
from core.storage.models import HoldingSnapshot, PriceCache


def get_current_holdings(database_path: Path) -> list[dict[str, str | float]]:
    """Read the latest confirmed holdings snapshot from SQLite."""
    session_factory = create_database(database_path)
    with session_factory() as session:
        snapshot = session.query(HoldingSnapshot).filter_by(is_current=True).first()
        if snapshot is None:
            return []
        return [
            {
                "symbol": holding.symbol,
                "exchange": holding.exchange,
                "quantity": float(holding.quantity),
                "average_cost": float(holding.average_cost),
                "cost_value": float(holding.cost_value),
            }
            for holding in snapshot.holdings
        ]


def make_tools(database_path: Path) -> list:
    """Build tools bound to the application's SQLite database."""

    @tool
    def get_holdings() -> list[dict[str, str | float]]:
        """Return current holdings with exact quantity, average cost, and invested value."""
        return get_current_holdings(database_path)

    @tool
    def get_price(
        symbol: Annotated[str, "Exchange symbol, for example INFY"],
        exchange: Annotated[str, "NSE or BSE"],
    ) -> dict[str, str | float] | None:
        """Return the latest cached delayed price for one held symbol."""
        session_factory = create_database(database_path)
        with session_factory() as session:
            quote = session.query(PriceCache).filter_by(symbol=symbol.upper(), exchange=exchange.upper()).first()
            if quote is None:
                return None
            return {
                "symbol": quote.symbol,
                "exchange": quote.exchange,
                "price": float(quote.ltp),
                "previous_close": float(quote.previous_close) if quote.previous_close is not None else None,
                "day_change_pct": float(quote.day_change_pct) if quote.day_change_pct is not None else None,
                "fetched_at": quote.fetched_at.isoformat(),
            }

    @tool
    def get_pnl_summary() -> dict[str, float | str] | None:
        """Return exact invested value and cached market value when available."""
        session_factory = create_database(database_path)
        with session_factory() as session:
            snapshot = session.query(HoldingSnapshot).filter_by(is_current=True).first()
            if snapshot is None:
                return None
            market_value = 0.0
            for holding in snapshot.holdings:
                quote = session.query(PriceCache).filter_by(symbol=holding.symbol, exchange=holding.exchange).first()
                if quote is not None:
                    market_value += float(holding.quantity) * float(quote.ltp)
            invested = float(snapshot.total_cost_value or 0)
            return {"invested_value": invested, "market_value": market_value, "pnl": market_value - invested}

    @tool
    def get_stock_details(
        symbol: Annotated[str, "NSE or BSE stock symbol"],
        exchange: Annotated[str, "NSE or BSE"],
    ) -> dict:
        """Return delayed quote, sector, fundamentals, and trend indicators for a stock."""
        from core.market_data.analytics import get_stock_details as load_stock_details

        return load_stock_details(symbol, exchange)

    @tool
    def get_stock_recommendations(
        symbol: Annotated[str, "NSE or BSE stock symbol"],
        exchange: Annotated[str, "NSE or BSE"],
    ) -> dict:
        """Return a transparent trend screen; never present it as personalized advice."""
        from core.market_data.analytics import get_stock_recommendation

        return get_stock_recommendation(symbol, exchange)

    @tool
    def get_index_recommendations(
        index_name: Annotated[str, "Supported Indian index name, for example NIFTY 50"],
    ) -> list[dict]:
        """Return the top 20 public momentum candidates for an Indian index."""
        from core.market_data.universe import load_index_recommendations

        table, _ = load_index_recommendations(index_name)
        return table.to_dict(orient="records")

    @tool
    def get_ipo_research() -> list[dict]:
        """Return public ongoing, upcoming, and recently listed IPO research rows."""
        from core.market_data.ipo import load_ipo_snapshot

        return load_ipo_snapshot().to_dict(orient="records")

    return [
        get_holdings,
        get_price,
        get_pnl_summary,
        get_stock_details,
        get_stock_recommendations,
        get_index_recommendations,
        get_ipo_research,
    ]