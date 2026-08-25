"""Custom navigation entrypoint for the PredictAP and GA application."""

from __future__ import annotations

import streamlit as st


pages = [
    st.Page(
        "pages/PredictMP_Analysis.py",
        title="PredictMP Analysis",
        icon="📊",
    ),
    st.Page(
        "pages/GA_GeneExpression_Predict.py",
        title="GA-Calibrated Gene Expression Prediction",
        icon="🧬",
    ),
]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
