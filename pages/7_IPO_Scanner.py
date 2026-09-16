"""Public IPO calendar and research screen."""

import streamlit as st

from core.market_data.ipo import IPO_SOURCE_URL, load_ipo_snapshot
from core.ui import market_progress

st.header("IPO scanner")
st.caption("Public IPO data for research only. Read the prospectus and assess valuation, risk, and suitability before applying.")
st.link_button("Open IPO source", IPO_SOURCE_URL)

if st.button("Refresh IPO data", type="primary"):
    with market_progress("Loading current IPO calendar and subscription data"):
        try:
            table = load_ipo_snapshot()
        except Exception as error:
            st.error(f"IPO data request failed: {error}")
            st.stop()
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.info("Research screen: subscription multiples and listing gains describe demand or past performance; they do not predict returns or guarantee allotment.")
else:
    st.info("Select Refresh IPO data to load current public IPO rows.")
