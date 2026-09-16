"""Index-based momentum research with sector context."""

import pandas as pd
import streamlit as st

from core.market_data.universe import MONEYCONTROL_INDEXES, load_index_recommendations
from core.ui import market_progress

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
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.link_button("View full index ranking", source_url)
    selected_stock = st.selectbox("Inspect a shortlisted stock", table["Stock"].tolist())
    st.session_state["selected_research_stock"] = selected_stock
    st.session_state["selected_research_exchange"] = "NSE"
    st.page_link(
        "pages/6_Stock_Details.py",
        label=f"Open {selected_stock} details",
        icon=":material/search:",
    )
    st.page_link(
        "pages/3_Market_Trends.py",
        label=f"Open {selected_stock} chart",
        icon=":material/show_chart:",
    )
    st.link_button(
        f"View {selected_stock} on Yahoo Finance",
        f"https://finance.yahoo.com/quote/{selected_stock.replace(' ', '').upper()}.NS/",
    )
    st.info("Review momentum is a shortlist signal only. Check valuation, fundamentals, liquidity, risk, and official disclosures before investing.")
else:
    st.info("Select an index and load recommendations.")
