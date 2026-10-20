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

# Hide the Deploy button, show the upload limit next to each Upload button in
# place of Streamlit's "size per file • types" line, and replace Streamlit's
# animated "running man" status icon with a plain spinner
max_upload_mb = st.get_option("server.maxUploadSize")
max_upload_label = (f"Max file size: {max_upload_mb / 1024:g} GB" if max_upload_mb >= 1024
                    else f"Max file size: {max_upload_mb:g} MB")
st.html("""
<style>
    [data-testid="stAppDeployButton"],
    [data-testid="stFileUploaderDropzoneInstructions"] > div {
        display: none !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        flex-direction: row !important;
        align-items: center !important;
        gap: 0.75rem;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        margin: 0 !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"]::after {
        content: "MAX_UPLOAD_LABEL";
        font-size: 0.875rem;
        opacity: 0.6;
        white-space: nowrap;
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
""".replace("MAX_UPLOAD_LABEL", max_upload_label))

navigation.run()
