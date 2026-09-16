"""Market-data service tests using a deterministic fake provider."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from core.market_data.provider import Quote
from core.market_data.service import refresh_quotes
from core.market_data.ipo import parse_ipo_snapshot
from core.market_data.universe import parse_moneycontrol_rankings
from core.storage.database import create_database
from core.storage.models import PriceCache


class FakeProvider:
    """Provider double that never calls Yahoo Finance."""

    def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Return a stable quote for service testing."""
        return Quote(symbol, exchange, 1500.0, 1480.0, 1.3514, datetime(2026, 9, 11))


def test_refresh_quotes_persists_price_cache(tmp_path: Path) -> None:
    """Successful quotes are persisted and returned."""
    database_path = tmp_path / "portfolio.db"
    quotes = refresh_quotes([("INFY", "NSE")], FakeProvider(), database_path)
    with create_database(database_path)() as session:
        cached = session.query(PriceCache).one()
    assert quotes[0].price == 1500.0
    assert cached.day_change_pct == Decimal("1.3514")


def test_parse_moneycontrol_rankings() -> None:
    """Moneycontrol's combined price/change cell becomes numeric ranking data."""
    frame = pd.DataFrame(
        {
            "Stock Name": ["Example CorpVol Shocker"],
            "Price": ["1,382.3058.80 (4.44%)"],
        }
    )

    result = parse_moneycontrol_rankings(frame)

    assert result.to_dict("records") == [{"Rank": 1, "Stock": "Example Corp", "Price": 1382.30, "Change %": 4.44}]


def test_parse_ipo_snapshot_keeps_public_statistics() -> None:
    """Named IPO rows retain issue, subscription, and listing fields."""
    tables = [
        pd.DataFrame(
            {
                "Company Name": ["Example Technologies IPO"],
                "Unnamed: 1": ["Mainline"],
                "Issue Price": ["₹ 100"],
                "Total Subscription": ["12.5x"],
                "Listing Gain": ["18.00%"],
                "Issue Size": ["₹ 500 Cr"],
                "Listing Date": ["18 Sep 26"],
            }
        )
    ]

    result = parse_ipo_snapshot(tables)

    assert result.loc[0, "Company"] == "Example Technologies IPO"
    assert result.loc[0, "Subscription"] == "12.5x"
    assert result.loc[0, "Issue size"] == "₹ 500 Cr"