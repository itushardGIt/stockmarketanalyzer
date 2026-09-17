"""Market-data service tests using a deterministic fake provider."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from core.market_data.provider import Quote
from core.market_data.service import refresh_quotes
from core.market_data.ipo import _extract_iposcanner_rows, parse_ipo_snapshot
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
    assert result.loc[0, "Research signal"] == "Subscribe / strong demand"


def test_parse_ipo_snapshot_sorts_latest_listing_first() -> None:
    """The dashboard starts with the latest available IPO listing date."""
    tables = [
        pd.DataFrame(
            {
                "Company Name": ["Older IPO", "Latest IPO"],
                "Listing Date": ["10 Sep 26", "17 Sep 26"],
                "Total Subscription": ["0.8x", "2.0x"],
            }
        )
    ]

    result = parse_ipo_snapshot(tables)

    assert result.loc[0, "Company"] == "Latest IPO"
    assert result.loc[0, "Research signal"] == "Review / moderate demand"


def test_extract_iposcanner_rows() -> None:
    """IPOScanner's embedded feed is normalized into the scanner schema."""
    page = (
        r'\"company\":\"Example IPO\",\"offerPriceRange\":[100,110],'
        r'\"subscribedTimes\":6.5,\"expectedPremium\":{\"percent\":12.5},'
        r'\"offerStart\":\"2026-09-17\",\"offerEnd\":\"2026-09-21\",'
        r'\"listingDate\":\"2026-09-24\"'
    )

    rows = _extract_iposcanner_rows(page)

    assert rows[0]["Company"] == "Example IPO"
    assert rows[0]["Issue price"] == "₹ 100 - ₹ 110"
    assert rows[0]["Research signal"] == "Subscribe / strong demand"