"""SQLAlchemy 2.0 models for Phase 1 portfolio data."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""


class StatementType(StrEnum):
    """Supported broker statement types."""

    HOLDINGS = "holdings"
    TRADEBOOK = "tradebook"
    TAX_PNL = "tax_pnl"


class UploadStatus(StrEnum):
    """Lifecycle status of an uploaded statement."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    FAILED = "failed"


class ChangeType(StrEnum):
    """Meaning of a position-level snapshot change."""

    NEW = "new"
    EXITED = "exited"
    QUANTITY_CHANGED = "quantity_changed"
    COST_CHANGED = "cost_changed"
    UNCHANGED = "unchanged"


class UploadBatch(Base):
    """Audit record for one parsed statement upload."""

    __tablename__ = "upload_batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    statement_type: Mapped[StatementType] = mapped_column(Enum(StatementType), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_format: Mapped[str] = mapped_column(String(10), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[UploadStatus] = mapped_column(Enum(UploadStatus), nullable=False)
    parse_errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    snapshots: Mapped[list["HoldingSnapshot"]] = relationship(back_populates="upload_batch")


class HoldingSnapshot(Base):
    """A confirmed point-in-time holdings snapshot."""

    __tablename__ = "holding_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    upload_batch_id: Mapped[UUID] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    total_cost_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    total_market_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    upload_batch: Mapped[UploadBatch] = relationship(back_populates="snapshots")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")
    diffs: Mapped[list["SnapshotDiff"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class Holding(Base):
    """One position belonging to a holdings snapshot."""

    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("snapshot_id", "exchange", "symbol", name="uq_holding_snapshot_position"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("holding_snapshots.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    instrument_name: Mapped[str | None] = mapped_column(String(255))
    broker_symbol: Mapped[str | None] = mapped_column(String(40))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    snapshot: Mapped[HoldingSnapshot] = relationship(back_populates="holdings")


class Trade(Base):
    """Normalized tradebook row reserved for the next ingestion increment."""

    __tablename__ = "trades"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    upload_batch_id: Mapped[UUID] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    transaction_type: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    charges: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    trade_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    trade_id: Mapped[str | None] = mapped_column(String(100))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class TaxPnlEntry(Base):
    """Zerodha-computed realized P&L row reserved for tax statement ingestion."""

    __tablename__ = "tax_pnl_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    upload_batch_id: Mapped[UUID] = mapped_column(ForeignKey("upload_batches.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    buy_date: Mapped[date | None] = mapped_column(Date)
    sell_date: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    buy_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    sell_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    holding_period_days: Mapped[int | None] = mapped_column(Integer)
    tax_category: Mapped[str | None] = mapped_column(String(10))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class SnapshotDiff(Base):
    """Position-level comparison between adjacent holdings snapshots."""

    __tablename__ = "snapshot_diffs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("holding_snapshots.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType), nullable=False)
    previous_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    current_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    previous_average_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    current_average_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    snapshot: Mapped[HoldingSnapshot] = relationship(back_populates="diffs")


class PriceCache(Base):
    """Latest public-market quote cached for one exchange symbol."""

    __tablename__ = "price_cache"
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_price_cache_position"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    ltp: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    previous_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    day_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)