"""Pydantic validation models for normalized holdings uploads."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HoldingRow(BaseModel):
    """Validated, normalized representation of one holdings row."""

    symbol: str = Field(min_length=1)
    exchange: Literal["NSE", "BSE"]
    quantity: Decimal = Field(gt=0)
    avg_cost: Decimal = Field(gt=0)
    sector: str | None = None

    @field_validator("symbol", "exchange", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        """Normalize broker-export text values before validation."""
        return str(value).strip().upper()


class ParsedHoldings(BaseModel):
    """Validated upload result shown in the confirmation gate."""

    rows: list[HoldingRow]
    warnings: list[str] = []
    source_filename: str