"""Transactional persistence for confirmed holdings uploads."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from core.ingestion.schemas import ParsedHoldings
from core.storage.database import create_database
from core.storage.models import ChangeType, Holding, HoldingSnapshot, SnapshotDiff, StatementType, UploadBatch, UploadStatus


def confirm_holdings_upload(parsed: ParsedHoldings, content: bytes, database_path: Path) -> UUID:
    """Persist a reviewed holdings upload and return its snapshot identifier."""
    session_factory = create_database(database_path)
    now = datetime.now(timezone.utc)
    with session_factory.begin() as session:
        previous = session.query(HoldingSnapshot).filter_by(is_current=True).order_by(HoldingSnapshot.created_at.desc()).first()
        if previous:
            previous.is_current = False
        batch = UploadBatch(
            statement_type=StatementType.HOLDINGS,
            source_filename=parsed.source_filename,
            source_format=Path(parsed.source_filename).suffix.lower().lstrip("."),
            content_hash=sha256(content).hexdigest(),
            uploaded_at=now,
            confirmed_at=now,
            row_count=len(parsed.rows),
            status=UploadStatus.CONFIRMED,
        )
        snapshot = HoldingSnapshot(upload_batch=batch, as_of_date=date.today(), created_at=now, is_current=True)
        snapshot.total_cost_value = sum((row.quantity * row.avg_cost for row in parsed.rows), start=Decimal("0"))
        for row in parsed.rows:
            snapshot.holdings.append(
                Holding(
                    symbol=row.symbol,
                    exchange=row.exchange,
                    quantity=row.quantity,
                    average_cost=row.avg_cost,
                    cost_value=row.quantity * row.avg_cost,
                    instrument_name=None,
                    broker_symbol=row.symbol,
                    raw_data=row.model_dump(mode="json"),
                )
            )
        session.add(snapshot)
        session.flush()
        previous_positions = {(item.exchange, item.symbol): item for item in previous.holdings} if previous else {}
        current_positions = {(item.exchange, item.symbol): item for item in snapshot.holdings}
        for identity in previous_positions.keys() | current_positions.keys():
            before = previous_positions.get(identity)
            after = current_positions.get(identity)
            if before is None:
                change = ChangeType.NEW
            elif after is None:
                change = ChangeType.EXITED
            elif before.quantity != after.quantity:
                change = ChangeType.QUANTITY_CHANGED
            elif before.average_cost != after.average_cost:
                change = ChangeType.COST_CHANGED
            else:
                change = ChangeType.UNCHANGED
            snapshot.diffs.append(
                SnapshotDiff(
                    symbol=identity[1],
                    change_type=change,
                    previous_quantity=before.quantity if before else None,
                    current_quantity=after.quantity if after else None,
                    previous_average_cost=before.average_cost if before else None,
                    current_average_cost=after.average_cost if after else None,
                )
            )
        return snapshot.id