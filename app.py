"""Streamlit entry point for the portfolio application."""

from pathlib import Path

import streamlit as st

from core.config import AppCredentials
from core.storage.database import create_database
from core.storage.models import HoldingSnapshot

st.set_page_config(page_title="NiveshIQ", page_icon="data/market-icon.jpg", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
    [data-testid="stAppViewContainer"] { background: #0d1418; }
    [data-testid="stMainBlockContainer"] { padding-top: 10px; }
    [data-testid="stHeader"] { background: rgba(13, 20, 24, 0.94); }
    [data-testid="stSidebar"] { background: #16252b; border-right: 1px solid #2d5961; }
    [data-testid="stMetricValue"] { color: #b9f5df; }
    [data-testid="stMetricLabel"] { color: #9fc2c2; }
    h1, h2, h3 { color: #d9fff0; letter-spacing: 0; }
    div[data-testid="stDataFrame"] { border: 1px solid #2d5961; border-radius: 10px; }
    button[kind="primary"] { background: #e47d47; border-color: #e47d47; color: #fff; }
    button[kind="primary"]:hover { background: #f29a61; border-color: #f29a61; }
    button:disabled { opacity: 0.62; }
    [data-testid="stStatusWidget"] { background: #1b3438; }
    .nivesh-header { margin: 0; padding-top: 10px; }
    .nivesh-header h1 { margin: 0; color: #d9fff0; font-size: 3rem; line-height: 1.05; }
    .nivesh-subtitle { margin: 0 0 0.7rem; color: #9fc2c2; font-size: 1rem; }
    h2 { font-size: 1.65rem !important; margin-top: 0.4rem !important; }
</style>""", unsafe_allow_html=True)

st.markdown('<div class="nivesh-header"><h1>NiveshIQ</h1></div>', unsafe_allow_html=True)
st.markdown('<p class="nivesh-subtitle">See your holdings. Read the market. Invest with clarity.</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("AI integrations")
    st.caption("Keys remain in this browser session and are not stored by the application.")
    openai_key = st.text_input("OpenAI API key", type="password", key="openai_api_key")
    langsmith_enabled = st.toggle("Enable LangSmith tracing", value=False, key="langsmith_enabled")
    langsmith_key = st.text_input("LangSmith API key", type="password", key="langsmith_api_key")
    if not langsmith_enabled:
        st.caption("Tracing is off. A LangSmith key is optional.")
    credentials = AppCredentials(openai_key, langsmith_key, langsmith_enabled)
    if not credentials.is_complete:
        st.warning("Enter the OpenAI key to unlock the application.")

database_path = Path("data/portfolio.db")
with create_database(database_path)() as session:
    has_confirmed_holdings = session.query(HoldingSnapshot).filter_by(is_current=True).first() is not None

pages = {
    "Portfolio": [
        st.Page("pages/2_Upload_Statements.py", title="Upload statements", icon=":material/upload_file:"),
    ],
    "Market research": [
        st.Page("pages/6_Stock_Details.py", title="Stock details", icon=":material/search:"),
        st.Page("pages/8_Recommendations.py", title="Recommendations", icon=":material/insights:"),
        st.Page("pages/7_IPO_Scanner.py", title="IPO scanner", icon=":material/assignment:"),
    ],
}
if has_confirmed_holdings:
    pages["Portfolio"] = [
        st.Page("pages/2_Upload_Statements.py", title="Upload statements", icon=":material/upload_file:"),
        st.Page("pages/1_Dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        st.Page("pages/3_Market_Trends.py", title="Chart", icon=":material/show_chart:"),
        st.Page("pages/4_Gainers_Losers.py", title="Gainers / losers", icon=":material/leaderboard:"),
        st.Page("pages/5_Chat_Assistant.py", title="Chat assistant", icon=":material/chat:"),
    ]
st.navigation(pages).run()