"""Parser contract tests."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest

from core.ingestion.parser import UploadParseError, parse_holdings


def test_valid_csv_is_normalized() -> None:
    """A valid broker-shaped CSV yields normalized Pydantic rows."""
    result = parse_holdings(BytesIO(b"Trading Symbol,Exchange,Quantity,Average Price\nINFY,NSE,2,1500"), "holdings.csv")
    assert result.rows[0].symbol == "INFY"
    assert result.rows[0].avg_cost == 1500


def test_zerodha_xlsx_statement_is_normalized() -> None:
    """A Zerodha statement workbook yields equity holdings from its table section."""
    path = Path(__file__).parents[1] / "sample_data" / "holdings-CPZ956.xlsx"
    result = parse_holdings(path.read_bytes(), path.name)

    assert len(result.rows) == 15
    assert result.rows[0].symbol == "ADANIPOWER"
    assert result.rows[0].exchange == "NSE"
    assert result.rows[0].quantity == 300
    assert result.rows[0].avg_cost == Decimal("195.0762")
    assert result.rows[0].sector == "ENERGY"


def test_missing_required_column_is_rejected() -> None:
    """A missing required field blocks confirmation."""
    with pytest.raises(UploadParseError, match="avg_cost"):
        parse_holdings(BytesIO(b"Symbol,Exchange,Quantity\nINFY,NSE,2"), "holdings.csv")


def test_duplicate_symbol_is_rejected() -> None:
    """Two positions with the same exchange and symbol cannot be accepted."""
    content = b"Symbol,Exchange,Quantity,Average Price\nINFY,NSE,2,1500\nINFY,NSE,1,1600"
    with pytest.raises(UploadParseError, match="duplicate position"):
        parse_holdings(BytesIO(content), "holdings.csv")