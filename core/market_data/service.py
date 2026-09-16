"""Quote retrieval and SQLite price-cache persistence."""

from __future__ import annotations

from datetime import timezone
from decimal import Decimal
from pathlib import Path

from core.market_data.provider import PriceProvider, Quote
from core.storage.database import create_database
from core.storage.models import PriceCache


def refresh_quotes(symbols: list[tuple[str, str]], provider: PriceProvider, database_path: Path) -> list[Quote]:
    """Fetch quotes, persist successful results, and return them in input order."""
    session_factory = create_database(database_path)
    quotes: list[Quote] = []
    with session_factory.begin() as session:
        for symbol, exchange in symbols:
            quote = provider.get_quote(symbol, exchange)
            quotes.append(quote)
            cached = session.query(PriceCache).filter_by(symbol=quote.symbol, exchange=quote.exchange).first()
            if cached is None:
                cached = PriceCache(symbol=quote.symbol, exchange=quote.exchange)
                session.add(cached)
            cached.ltp = Decimal(str(quote.price))
            cached.previous_close = Decimal(str(quote.previous_close)) if quote.previous_close is not None else None
            cached.day_change_pct = Decimal(str(quote.day_change_pct)) if quote.day_change_pct is not None else None
            cached.fetched_at = quote.fetched_at.replace(tzinfo=timezone.utc) if quote.fetched_at.tzinfo is None else quote.fetched_at
    return quotes