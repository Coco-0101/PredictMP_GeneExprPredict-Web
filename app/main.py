"""Custom navigation entrypoint for the PredictMP and GA application."""

from __future__ import annotations

import streamlit as st

from core.storage import RETENTION_DAYS


pages = [
    st.Page(
        "pages/predictmp_analysis.py",
        title="PredictMP Analysis",
        icon="📊",
    ),
    st.Page(
        "pages/ga_predict.py",
        title="GA-Calibrated Gene Expression Prediction",
        icon="🧬",
    ),
    st.Page(
        "pages/privacy.py",
        title="Privacy & Data Retention",
        icon="🔒",
    ),
]

navigation = st.navigation(pages, position="sidebar")

with st.sidebar:
    st.caption(
        f"🔒 Uploaded files and results are deleted automatically after "
        f"{RETENTION_DAYS:g} days. See *Privacy & Data Retention*."
    )

navigation.run()
