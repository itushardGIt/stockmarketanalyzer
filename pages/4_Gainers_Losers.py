"""Ranked NIFTY 500 day-change view from a public market table."""

import pandas as pd
import streamlit as st

from core.market_data.universe import load_moneycontrol_rankings
from core.ui import market_progress

st.header("Gainers / losers")
st.caption("Live NIFTY 500 top 50 rankings from Moneycontrol. Values are for analysis only and may be delayed.")
direction = st.radio("Show", ["Gainers", "Losers"], horizontal=True)
st.link_button("Open source page", "https://www.moneycontrol.com/stocks/market-stats/top-gainers-nse/?indexName=NIFTY%20500&id=7" if direction == "Gainers" else "https://www.moneycontrol.com/stocks/market-stats/top-losers-nse/?indexName=NIFTY%20500&id=7")

if st.button("Refresh rankings", type="primary"):
    with market_progress("Fetching live market rankings"):
        try:
            table = load_moneycontrol_rankings(direction)
        except Exception as error:
            st.error(f"Public market ranking request failed: {error}")
            st.stop()
    table["Change %"] = table["Change %"].map(lambda value: f"{value:+.2f}%")
    st.dataframe(table, use_container_width=True, hide_index=True)
else:
    st.info("Choose Gainers or Losers and select Refresh rankings to load the current top 50.")