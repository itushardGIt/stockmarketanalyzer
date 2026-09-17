"""Shared Streamlit feedback controls."""

from contextlib import contextmanager
from typing import Iterator

import pandas as pd
import streamlit as st


def styled_table(table: pd.DataFrame, style_fn=None, subset=None):
    """Apply consistent high-contrast table headers across the application."""
    styled = table.style.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("font-weight", "700"),
                    ("color", "#f8fafc"),
                    ("background-color", "#25313a"),
                    ("border-bottom", "2px solid #4fa99d"),
                ],
            }
        ]
    )
    if style_fn is not None and subset is not None:
        styled = styled.map(style_fn, subset=subset)
    return styled


@contextmanager
def market_progress(label: str) -> Iterator[None]:
    """Show a staged market progress bar while a blocking action runs."""
    progress = st.progress(5, text=f"🔍 {label} 5%")
    try:
        yield
    except Exception:
        progress.progress(100, text=f"🔍 {label} finished")
        raise
    else:
        progress.progress(100, text=f"🔍 {label} 100%")
