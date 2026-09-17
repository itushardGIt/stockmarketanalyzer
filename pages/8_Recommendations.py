"""Index-based momentum research with sector context."""

import pandas as pd
import streamlit as st

from core.market_data.universe import MONEYCONTROL_INDEXES, load_index_recommendations
from core.ui import market_progress, styled_table

st.header("Recommendations")
st.caption("Top 20 index momentum candidates for research. This is not personalized investment advice.")

index_name = st.selectbox("Market index", list(MONEYCONTROL_INDEXES), help="Type to search the index list.")
st.caption("The list is ranked by today's percentage gain from Moneycontrol's public market table.")
if st.button("Load recommendations", type="primary"):
    with market_progress(f"Scanning {index_name} momentum"):
        try:
            table, source_url = load_index_recommendations(index_name)
        except Exception as error:
            st.error(f"Index recommendation request failed: {error}")
            st.stop()
    table["Suggestion"] = table["Change %"].map(
        lambda value: "Review momentum" if value > 0 else "Avoid momentum chase"
    )
    st.dataframe(styled_table(table), use_container_width=True, hide_index=True)
    source_col, = st.columns(1)
    with source_col:
        st.link_button("View full index ranking", source_url, use_container_width=True)
    selected_stock = st.selectbox("Inspect a shortlisted stock", table["Stock"].tolist())
    st.session_state["selected_research_stock"] = selected_stock
    st.session_state["selected_research_exchange"] = "NSE"
    detail_col, chart_col, yahoo_col = st.columns(3)
    with detail_col:
        st.page_link(
            "pages/6_Stock_Details.py",
            label=f"Open {selected_stock} details",
            icon=":material/search:",
        )
    with chart_col:
        st.page_link(
            "pages/3_Market_Trends.py",
            label=f"Open {selected_stock} chart",
            icon=":material/show_chart:",
        )
    with yahoo_col:
        st.link_button(
            f"View {selected_stock} on Yahoo Finance",
            f"https://finance.yahoo.com/quote/{str(selected_stock).replace(' ', '').upper()}.NS/",
            use_container_width=True,
        )
    st.info("Review momentum is a shortlist signal only. Check valuation, fundamentals, liquidity, risk, and official disclosures before investing.")
else:
    st.info("Select an index and load recommendations.")
