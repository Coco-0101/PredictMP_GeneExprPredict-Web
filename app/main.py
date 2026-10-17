"""Custom navigation entrypoint for the PredictMP and GA application."""

from __future__ import annotations

import streamlit as st

from core.upload_cleanup import start_upload_cleanup

# Free uploads left in memory by closed or refreshed sessions
start_upload_cleanup()

pages = [
    st.Page(
        "views/predictmp_analysis.py",
        title="PredictMP Analysis",
        icon="📊",
    ),
    st.Page(
        "views/ga_predict.py",
        title="GA-Calibrated Gene Expression Prediction",
        icon="🧬",
    ),
    st.Page(
        "views/privacy.py",
        title="Privacy & Data Retention",
        icon="🔒",
    ),
]

navigation = st.navigation(pages, position="sidebar")

# Hide the Deploy button and the uploaders' "size per file • types" line, and
# replace Streamlit's animated "running man" status icon with a plain spinner
st.html("""
<style>
    [data-testid="stAppDeployButton"],
    [data-testid="stFileUploaderDropzoneInstructions"] {
        display: none !important;
    }
    [data-testid="stStatusWidgetRunningIcon"] > * {
        display: none !important;
    }
    [data-testid="stStatusWidgetRunningIcon"]::after {
        content: "";
        display: block;
        width: 1.25rem;
        height: 1.25rem;
        box-sizing: border-box;
        border: 2px solid rgba(128, 128, 128, 0.25);
        border-top-color: rgba(128, 128, 128, 0.9);
        border-radius: 50%;
        animation: status-spin 0.8s linear infinite;
    }
    @keyframes status-spin {
        to { transform: rotate(360deg); }
    }
</style>
""")

navigation.run()
