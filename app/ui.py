"""Streamlit UI helpers shared by the pages."""

import pandas as pd
import streamlit as st

from core.storage import RETENTION_DAYS


def retention_consent(key: str) -> bool:
    """Checkbox the user must tick before running an analysis."""
    return st.checkbox(
        f"I understand that results are deleted automatically after {RETENTION_DAYS:g} days "
        f"and uploaded files are not kept.",
        key=key,
        help="See *Privacy & Data Retention* for what is stored and how it is removed",
    )


def paginate_dataframe(df: pd.DataFrame, key: str, page_size: int = 500):
    """Show a page-number control and return (page_df, page_num, total_pages)."""
    total_rows = len(df)
    total_pages = max(1, -(-total_rows // page_size))  # ceil division

    # The page lives in session state (starting at 1). Filtering can shrink the
    # table below the page the user was on, so clamp it to the new maximum.
    page_key = f"{key}_page"
    st.session_state[page_key] = min(st.session_state.get(page_key, 1), total_pages)

    col1, col2 = st.columns([1, 3])
    with col1:
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            step=1,
            key=page_key,
        )
    start = (page - 1) * page_size
    end = min(start + page_size, total_rows)
    with col2:
        st.caption(f"Showing rows {start + 1:,}-{end:,} of {total_rows:,} (page {page:,} of {total_pages:,})")

    return df.iloc[start:end], page, total_pages
