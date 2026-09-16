"""Shared Streamlit feedback controls."""

from contextlib import contextmanager
from typing import Iterator

import streamlit as st


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
