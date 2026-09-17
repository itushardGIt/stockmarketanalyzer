"""Public IPO calendar and research screen."""

import streamlit as st

from core.market_data.ipo import IPO_SOURCE_URL, load_ipo_snapshot
from core.ui import market_progress, styled_table

st.header("IPO scanner")
st.caption("Public IPO data for research only. Read the prospectus and assess valuation, risk, and suitability before applying.")
source_col, refresh_col = st.columns(2)
with source_col:
    st.link_button("Open IPO source", IPO_SOURCE_URL, use_container_width=True)
with refresh_col:
    refresh_ipo = st.button("Refresh IPO data", type="primary", use_container_width=True)

if refresh_ipo:
    with market_progress("Loading current IPO calendar and subscription data"):
        try:
            table = load_ipo_snapshot()
        except Exception as error:
            st.error(f"IPO data request failed: {error}")
            st.stop()
    signal_colors = {
        "Subscribe / strong demand": ("#b7f0d4", "#123b2a"),
        "Review / moderate demand": ("#fff1b8", "#4a3700"),
        "Avoid / weak demand": ("#ffd6d6", "#5c1f1f"),
    }
    def signal_style(signal: object) -> str:
        background, foreground = signal_colors.get(str(signal), ("#f3f4f6", "#1f2937"))
        return f"background-color: {background}; color: {foreground}; font-weight: 700; text-align: center;"

    st.dataframe(
        styled_table(table, signal_style, ["Research signal"]),
        use_container_width=True,
        hide_index=True,
    )
    st.info("Research screen: subscription multiples and listing gains describe demand or past performance; they do not predict returns or guarantee allotment.")
else:
    st.info("Select Refresh IPO data to load current public IPO rows.")
