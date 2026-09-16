"""Stock details and transparent technical screening."""

from pathlib import Path

import pandas as pd
import streamlit as st

from core.market_data.analytics import get_stock_details, get_stock_recommendation
from core.market_data.universe import load_nse_stock_directory
from core.storage.database import create_database
from core.storage.models import HoldingSnapshot
from core.ui import market_progress

st.header("Stock details")
st.caption("Public delayed data for research. Screening signals are not investment advice.")


def reset_stock_details() -> None:
    """Clear the stock search and any previously loaded analysis."""
    st.session_state.pop("stock_details", None)
    st.session_state.pop("stock_recommendation", None)
    st.session_state["stock_search_query"] = ""
    st.session_state.pop("stock_search_match", None)

exchange = st.selectbox("Exchange", ["BSE", "NSE"], index=0, key="stock_exchange")
with create_database(Path("data/portfolio.db"))() as session:
    snapshot = session.query(HoldingSnapshot).filter_by(is_current=True).first()
    held_symbols = [(holding.symbol, holding.exchange) for holding in snapshot.holdings] if snapshot else []

directory = pd.DataFrame(columns=["symbol", "name"])
if exchange == "NSE":
    try:
        directory = st.cache_data(ttl=3600, show_spinner=False)(load_nse_stock_directory)()
    except Exception:
        pass
held_directory = pd.DataFrame(held_symbols, columns=["symbol", "exchange"])
if not held_directory.empty:
    held_directory["name"] = held_directory["symbol"]
    directory = pd.concat([directory, held_directory.loc[held_directory["exchange"] == exchange, ["symbol", "name"]]], ignore_index=True).drop_duplicates("symbol")
search_query = st.text_input(
    f"{exchange} Stock",
    key="stock_search_query",
    placeholder="Start typing a company name or symbol...",
    help="Enter at least one character to search the live stock directory.",
).strip().upper()
matching_rows = directory.iloc[0:0]
if search_query:
    matching_rows = directory[
        directory["symbol"].str.contains(search_query, na=False)
        | directory["name"].str.upper().str.contains(search_query, na=False)
    ].head(20)

stock_options = {
    f"{str(row['symbol'])} | {str(row['name'])}": str(row["symbol"])
    for _, row in matching_rows.iterrows()
}
selected_label = None
if stock_options:
    selected_label = st.selectbox(
        "Matching stocks",
        list(stock_options),
        index=None,
        placeholder="Select a matching stock...",
        key="stock_search_match",
    )
symbol = stock_options.get(selected_label, search_query) if selected_label else search_query
load_col, reset_col = st.columns(2)
with load_col:
    load_details = st.button("Load details", type="primary", disabled=not symbol, use_container_width=True)
with reset_col:
    st.button("Reset", use_container_width=True, on_click=reset_stock_details)

if load_details:
    with market_progress(f"Loading {symbol} details and indicators"):
        try:
            st.session_state["stock_details"] = get_stock_details(symbol, exchange)
            st.session_state["stock_recommendation"] = get_stock_recommendation(symbol, exchange)
        except Exception as error:
            st.error(f"Stock data request failed: {error}")
            st.stop()

details = st.session_state.get("stock_details")
recommendation = st.session_state.get("stock_recommendation")
if details is None or recommendation is None:
    st.info("Enter a stock symbol and select Load details to begin.")
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
