"""Holdings dashboard for the latest confirmed snapshot."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.storage.database import create_database
from core.storage.models import HoldingSnapshot
from core.market_data.analytics import get_stock_recommendation
from core.ui import market_progress

st.header("Dashboard")
database_path = Path("data/portfolio.db")
session_factory = create_database(database_path)
with session_factory() as session:
    snapshot = session.query(HoldingSnapshot).filter_by(is_current=True).order_by(HoldingSnapshot.created_at.desc()).first()
    holdings = list(snapshot.holdings) if snapshot else []

if not holdings:
    st.info("No confirmed holdings yet. Upload a Holdings statement to populate the dashboard.")
    st.stop()

metrics = st.columns(3)
total_cost = sum((holding.cost_value for holding in holdings), start=0)
metrics[0].metric("Invested value", f"₹{total_cost:,.2f}")
metrics[1].metric("Positions", len(holdings))
metrics[2].metric("Snapshot date", snapshot.as_of_date.isoformat())

table = pd.DataFrame(
    [
        {
            "Symbol": item.symbol,
            "Exchange": item.exchange,
            "Quantity": float(item.quantity),
            "Average cost": float(item.average_cost),
            "Cost value": float(item.cost_value),
        }
        for item in holdings
    ]
)
left, right = st.columns([1.5, 1], gap="small")
with left:
    st.subheader("Holdings")
    st.dataframe(table, use_container_width=True, hide_index=True)

with right:
    st.subheader("Allocation by position")
    figure = go.Figure(
        go.Pie(
            labels=table["Symbol"],
            values=table["Cost value"],
            hole=0.58,
            sort=False,
            textinfo="label+percent",
            marker={"colors": ["#2f8f83", "#4fa99d", "#78c4b7", "#a5ddd3", "#c8eee8", "#e4f7f3"]},
        )
    )
    figure.update_layout(
        template="plotly_dark",
        height=420,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        legend={"orientation": "h", "y": -0.08},
        paper_bgcolor="#171d21",
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})

st.subheader("Current holding recommendations")
st.caption("Trend screen based on moving averages and momentum. Research only, not a buy instruction.")
if st.button("Refresh holding recommendations", type="primary"):
    with market_progress("Refreshing trend signals"):
        rows = []
        unavailable = []
        for holding in holdings:
            try:
                rows.append(get_stock_recommendation(holding.symbol, holding.exchange))
            except Exception:
                unavailable.append(f"{holding.exchange}:{holding.symbol}")
    if rows:
        recommendation_table = pd.DataFrame(rows)
        def screen_style(value: object) -> str:
            colors = {"BUY CANDIDATE": "#1f9d74", "WATCH": "#d99a2b", "WAIT": "#c45454"}
            return f"background-color: {colors.get(str(value), '#43545b')}; color: white; font-weight: 700; border-radius: 12px; text-align: center;"
        st.dataframe(recommendation_table.style.map(screen_style, subset=["Screen"]), use_container_width=True, hide_index=True)
    if unavailable:
        st.warning("Unavailable: " + ", ".join(unavailable))