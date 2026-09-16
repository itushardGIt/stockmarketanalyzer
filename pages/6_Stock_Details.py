"""Stock details and transparent technical screening."""

from pathlib import Path

import pandas as pd
import streamlit as st

from core.market_data.analytics import get_stock_details, get_stock_recommendation
from core.storage.database import create_database
from core.storage.models import HoldingSnapshot
from core.ui import market_progress

st.header("Stock details")
st.caption("Public delayed data for research. Screening signals are not investment advice.")

symbols: list[tuple[str, str]] = []
with create_database(Path("data/portfolio.db"))() as session:
    snapshot = session.query(HoldingSnapshot).filter_by(is_current=True).first()
    if snapshot:
        symbols = [(holding.symbol, holding.exchange) for holding in snapshot.holdings]

mode = st.radio("Symbol source", ["Search symbol", "Current holdings"], horizontal=True)
if mode == "Current holdings" and symbols:
    labels = [f"{symbol} ({exchange})" for symbol, exchange in symbols]
    selected_label = st.selectbox("Holding", labels)
    symbol, exchange = symbols[labels.index(selected_label)]
else:
    symbol = st.text_input(
        "NSE symbol",
        value=st.session_state.get("selected_research_stock", st.query_params.get("symbol", "INFY")),
    ).strip().upper()
    selected_exchange = st.session_state.get("selected_research_exchange", st.query_params.get("exchange", "NSE"))
    exchange = st.selectbox("Exchange", ["NSE", "BSE"], index=0 if selected_exchange == "NSE" else 1)

if st.button("Load details", type="primary", disabled=not symbol):
    with market_progress(f"Loading {symbol} details and indicators"):
        try:
            details = get_stock_details(symbol, exchange)
            recommendation = get_stock_recommendation(symbol, exchange)
        except Exception as error:
            st.error(f"Stock data request failed: {error}")
            st.stop()

    st.subheader(f"{details['name']} ({details['symbol']})")
    metrics = st.columns(4)
    metrics[0].metric("Price", f"₹{details['price']:,.2f}")
    metrics[1].metric("Day change", f"{details['day_change_pct']:+.2f}%" if details["day_change_pct"] is not None else "Unavailable")
    metrics[2].metric("Sector", str(details["sector"]))
    metrics[3].metric("Industry", str(details["industry"]))

    fundamentals = {
        "Market cap": details["market_cap"],
        "Trailing P/E": details["pe_ratio"],
        "Forward P/E": details["forward_pe"],
        "Dividend yield": details["dividend_yield"],
        "52-week high": details["52_week_high"],
        "52-week low": details["52_week_low"],
        "20-day average": details["sma_20"],
        "50-day average": details["sma_50"],
        "1-month return %": details["return_1m_pct"],
        "1-year return %": details["return_1y_pct"],
    }
    st.subheader("Fundamentals and trend")
    st.dataframe(pd.DataFrame([fundamentals]), use_container_width=True, hide_index=True)
    st.subheader("Trend screen")
    st.info(f"{recommendation['Screen']}: {recommendation['Signals']}")
    st.caption("The screen combines moving-average trend and momentum. It is not a personalized buy recommendation.")
