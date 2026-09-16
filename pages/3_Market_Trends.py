"""Interactive multi-timeframe stock chart and technical context."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.market_data.provider import YFinanceProvider
from core.market_data.universe import load_nse_stock_directory
from core.storage.database import create_database
from core.storage.models import HoldingSnapshot
from core.ui import market_progress

st.header("Chart")
st.caption("Explore price action, trend, momentum, and volume using delayed public data. Indicators are research aids, not advice.")

database_path = Path("data/portfolio.db")
with create_database(database_path)() as session:
    snapshot = session.query(HoldingSnapshot).filter_by(is_current=True).first()
    held_symbols = [(holding.symbol, holding.exchange) for holding in snapshot.holdings] if snapshot else []

exchange = st.selectbox("Exchange", ["NSE", "BSE"], key="chart_exchange")
directory = pd.DataFrame(columns=["symbol", "name"])
if exchange == "NSE":
    try:
        directory = st.cache_data(ttl=3600, show_spinner=False)(load_nse_stock_directory)()
    except Exception:
        pass
held_directory = pd.DataFrame(held_symbols, columns=["symbol", "exchange"])
if not held_directory.empty:
    held_directory["name"] = held_directory["symbol"]
    directory = pd.concat([directory, held_directory[["symbol", "name"]]], ignore_index=True).drop_duplicates("symbol")
stock_options = {
    f"{str(row['symbol'])} | {str(row['name'])}": str(row["symbol"])
    for _, row in directory.iterrows()
}
default_symbol = st.session_state.get("selected_research_stock", "")
option_labels = list(stock_options)
default_index = next((index for index, label in enumerate(option_labels) if stock_options[label] == default_symbol), None)
selected_label = st.selectbox(
    f"{exchange} Stock",
    option_labels,
    index=default_index,
    placeholder="Search company name or symbol...",
    key=f"chart_stock_search_{exchange}",
    help="Type to filter, use arrow keys to navigate, and press Enter to select.",
    accept_new_options=True,
)
selected_symbol = stock_options.get(selected_label, str(selected_label).split(" | ", 1)[0].strip().upper()) if selected_label else ""

period_options = {"1D": ("1d", "5m"), "1W": ("5d", "30m"), "1M": ("1mo", "1d"), "3M": ("3mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1d")}
period_label = st.selectbox("History", list(period_options), index=2)
chart_type = st.radio("Chart type", ["Candle", "Line", "Bar"], horizontal=True)
show_averages = st.checkbox("Show 20/50-period moving averages", value=True)
load_col, reset_col = st.columns(2)
with load_col:
    load_history = st.button("Load chart", type="primary", disabled=not selected_symbol, use_container_width=True)
with reset_col:
    reset_chart = st.button("Reset", use_container_width=True)

if reset_chart:
    for key in ("chart_history", "chart_loaded_symbol", "chart_loaded_exchange", "chart_stock_search_NSE", "chart_stock_search_BSE"):
        st.session_state.pop(key, None)
    st.rerun()

if load_history:
    period, interval = period_options[period_label]
    with market_progress(f"Loading {selected_symbol} chart data"):
        try:
            history = YFinanceProvider().get_history(selected_symbol, exchange, period, interval)
        except Exception as error:
            st.error(f"Market data request failed: {error}")
            st.stop()
    if history.empty:
        st.warning("No historical data was returned for this stock and period.")
        st.stop()
    st.session_state["chart_history"] = history
    st.session_state["chart_loaded_symbol"] = selected_symbol
    st.session_state["chart_loaded_exchange"] = exchange

history = st.session_state.get("chart_history")
if history is None:
    st.info("Type a stock symbol and select Load chart to begin.")
    st.stop()

loaded_symbol = st.session_state["chart_loaded_symbol"]
close = history["Close"].dropna().astype(float)
volume = history["Volume"].dropna().astype(float) if "Volume" in history else pd.Series(dtype=float)
latest = float(close.iloc[-1])
previous = float(close.iloc[-2]) if len(close) > 1 else None
change = ((latest - previous) / previous * 100) if previous else None
sma20 = close.rolling(20).mean()
sma50 = close.rolling(50).mean()
returns = close.pct_change().dropna()
volatility = float(returns.std() * (252**0.5) * 100) if len(returns) > 1 else None
delta = close.diff()
gains = delta.clip(lower=0).rolling(14).mean()
losses = -delta.clip(upper=0).rolling(14).mean()
rsi = 100 - (100 / (1 + gains / losses.replace(0, pd.NA)))
latest_rsi = float(rsi.dropna().iloc[-1]) if not rsi.dropna().empty else None

metrics = st.columns(5)
metrics[0].metric("Last price", f"₹{latest:,.2f}")
metrics[1].metric("Period change", f"{change:+.2f}%" if change is not None else "Unavailable")
metrics[2].metric("Trend", "Above SMA20" if pd.notna(sma20.iloc[-1]) and latest > sma20.iloc[-1] else "Below SMA20" if pd.notna(sma20.iloc[-1]) else "Unavailable")
metrics[3].metric("RSI (14)", f"{latest_rsi:.1f}" if latest_rsi is not None else "Unavailable")
metrics[4].metric("Volatility", f"{volatility:.1f}%" if volatility is not None else "Unavailable")

figure = go.Figure()
if chart_type == "Candle":
    figure.add_trace(go.Candlestick(x=history.index, open=history["Open"], high=history["High"], low=history["Low"], close=history["Close"], name=loaded_symbol))
elif chart_type == "Bar":
    figure.add_trace(go.Bar(x=history.index, y=history["Close"], name=loaded_symbol, marker_color="#4fa99d"))
else:
    figure.add_trace(go.Scatter(x=history.index, y=history["Close"], mode="lines", name=loaded_symbol, line={"color": "#4fa99d", "width": 2}))
if show_averages:
    figure.add_trace(go.Scatter(x=history.index, y=sma20, mode="lines", name="SMA 20", line={"color": "#e47d47", "width": 1.5}))
    figure.add_trace(go.Scatter(x=history.index, y=sma50, mode="lines", name="SMA 50", line={"color": "#b9f5df", "width": 1.5}))
figure.update_layout(template="plotly_dark", height=580, xaxis_rangeslider_visible=False, hovermode="x unified", legend={"orientation": "h"})
st.plotly_chart(figure, use_container_width=True)

if not volume.empty:
    st.subheader("Volume context")
    volume_figure = go.Figure(go.Bar(x=volume.index, y=volume, name="Volume", marker_color="#2d5961"))
    volume_figure.update_layout(template="plotly_dark", height=180, margin={"t": 10, "b": 10}, showlegend=False)
    st.plotly_chart(volume_figure, use_container_width=True)

st.subheader("Reading the chart")
signals: list[str] = []
if pd.notna(sma20.iloc[-1]) and latest > sma20.iloc[-1]:
    signals.append("price is above the 20-period average")
elif pd.notna(sma20.iloc[-1]):
    signals.append("price is below the 20-period average")
if pd.notna(sma20.iloc[-1]) and pd.notna(sma50.iloc[-1]):
    signals.append("short-term trend is above the 50-period trend" if sma20.iloc[-1] > sma50.iloc[-1] else "short-term trend is below the 50-period trend")
if latest_rsi is not None:
    signals.append("RSI is elevated" if latest_rsi >= 70 else "RSI is weak" if latest_rsi <= 30 else "RSI is in a neutral range")
st.info("; ".join(signals).capitalize() + ". Confirm with fundamentals, valuation, news, and risk tolerance before making a decision.")
