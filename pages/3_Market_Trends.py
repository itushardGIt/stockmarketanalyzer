"""Historical chart for a held symbol."""

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from core.market_data.provider import YFinanceProvider
from core.storage.database import create_database
from core.storage.models import HoldingSnapshot
from core.ui import market_progress

st.header("Chart")
database_path = Path("data/portfolio.db")
query_symbol = st.session_state.get("selected_research_stock", st.query_params.get("symbol", "")).strip().upper()
query_exchange = st.session_state.get("selected_research_exchange", st.query_params.get("exchange", "NSE")).strip().upper()
with create_database(database_path)() as session:
    snapshot = session.query(HoldingSnapshot).filter_by(is_current=True).first()
    symbols = [(holding.symbol, holding.exchange) for holding in snapshot.holdings] if snapshot else []

if query_symbol:
    symbols = [(query_symbol, query_exchange)]
if not symbols:
    st.info("Confirm a holdings upload before viewing charts.")
    st.stop()

labels = [f"{symbol} ({exchange})" for symbol, exchange in symbols]
selected_label = st.selectbox("Symbol", labels)
selected_symbol, selected_exchange = symbols[labels.index(selected_label)]
period = st.selectbox("History", ["1mo", "3mo", "6mo", "1y"], index=1)
chart_type = st.radio("Chart type", ["Candle", "Line", "Bar"], horizontal=True)

if st.button("Load history", type="primary"):
    with market_progress(f"Loading {selected_symbol} chart data"):
        try:
            history = YFinanceProvider().get_history(selected_symbol, selected_exchange, period, "1d")
        except Exception as error:
            st.error(f"Market data request failed: {error}")
            st.stop()
    if history.empty:
        st.warning("No historical data was returned for this symbol.")
        st.stop()
    if chart_type == "Candle":
        trace = go.Candlestick(
            x=history.index,
            open=history["Open"],
            high=history["High"],
            low=history["Low"],
            close=history["Close"],
            name=selected_symbol,
        )
    elif chart_type == "Bar":
        trace = go.Bar(x=history.index, y=history["Close"], name=selected_symbol)
    else:
        trace = go.Scatter(x=history.index, y=history["Close"], mode="lines", name=selected_symbol)
    figure = go.Figure(data=[trace])
    figure.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
    st.plotly_chart(figure, use_container_width=True)