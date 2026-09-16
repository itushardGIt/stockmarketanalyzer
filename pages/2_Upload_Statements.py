"""Statement upload and explicit confirmation workflow."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from core.ingestion.parser import UploadParseError, parse_holdings
from core.storage.database import create_database
from core.storage.models import HoldingSnapshot
from core.ui import market_progress
from core.storage.repositories import confirm_holdings_upload
from sqlalchemy import select
from sqlalchemy.orm import selectinload

st.header("Upload statements")
st.caption("Review the normalized holdings before they become the current portfolio.")
uploaded = st.file_uploader("Holdings export", type=["csv", "xlsx"], help="Use the structured Zerodha Console export.")

if uploaded is None:
    st.info("Upload a CSV or XLSX Holdings export to begin review.")
    st.stop()

content = uploaded.getvalue()
try:
    parsed = parse_holdings(content, uploaded.name)
except UploadParseError as error:
    st.error(str(error))
    st.stop()

total_cost = sum((row.quantity * row.avg_cost for row in parsed.rows), start=0)
st.success(f"Parsed {len(parsed.rows)} positions from {parsed.source_filename}.")
summary = st.columns(3)
summary[0].metric("Valid positions", len(parsed.rows))
summary[1].metric("Invested value", f"₹{total_cost:,.2f}")
summary[2].metric("Parsed at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

st.subheader("Review before confirmation")
review_table = pd.DataFrame(
    [
        {
            "Symbol": row.symbol,
            "Exchange": row.exchange,
            "Quantity": float(row.quantity),
            "Average cost": float(row.avg_cost),
            "Sector": row.sector or "",
        }
        for row in parsed.rows
    ]
)
st.dataframe(review_table, use_container_width=True, hide_index=True)

session_factory = create_database(Path("data/portfolio.db"))
with session_factory() as session:
    previous_snapshots = session.scalars(
        select(HoldingSnapshot)
        .options(selectinload(HoldingSnapshot.holdings))
        .order_by(HoldingSnapshot.created_at.desc())
        .limit(2)
    ).all()
previous = previous_snapshots[0] if previous_snapshots else None
if previous:
    previous_positions = {(item.exchange, item.symbol): item for item in previous.holdings}
    current_positions = {(row.exchange, row.symbol): row for row in parsed.rows}
    diff_rows = []
    for identity in sorted(previous_positions.keys() | current_positions.keys()):
        before = previous_positions.get(identity)
        after = current_positions.get(identity)
        if before is None:
            change = "New"
        elif after is None:
            change = "Exited"
        elif before.quantity != after.quantity:
            change = "Quantity changed"
        elif before.average_cost != after.avg_cost:
            change = "Cost changed"
        else:
            change = "Unchanged"
        diff_rows.append({"Symbol": identity[1], "Exchange": identity[0], "Change": change})
    diff_table = pd.DataFrame(diff_rows)
    st.subheader("What changes from the current snapshot")
    diff_metrics = st.columns(4)
    for column, label in zip(diff_metrics, ["New", "Exited", "Quantity changed", "Cost changed"]):
        column.metric(label, int((diff_table["Change"] == label).sum()))
    selected_changes = st.multiselect("Show changes", sorted(diff_table["Change"].unique()), default=sorted(diff_table["Change"].unique()))
    st.dataframe(diff_table[diff_table["Change"].isin(selected_changes)], use_container_width=True, hide_index=True)
else:
    st.info("This is the first upload, so there is no previous snapshot to compare.")

st.warning("Confirmation replaces the current holdings snapshot. Check symbols, exchanges, quantities, and average costs carefully.")
reviewed = st.checkbox("I reviewed the parsed statement and approve this replacement.")
if st.button("Confirm and replace current holdings", type="primary", disabled=not reviewed):
    with market_progress("Saving holdings snapshot"):
        snapshot_id = confirm_holdings_upload(parsed, content, Path("data/portfolio.db"))
    st.success(f"Holdings confirmed. Snapshot {snapshot_id} is now current.")
    st.rerun()