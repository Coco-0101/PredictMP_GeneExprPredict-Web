"""
GA-Calibrated Gene Expression Prediction
Upload a genotype.vcf -> predict expression using GA-calibrated weights
"""

import os
import streamlit as st
import tempfile
from pathlib import Path
import uuid
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.genexpr_pipeline import GenexprPipeline, load_results

# ─────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────
WEIGHTS_DB = os.environ.get("GA_WEIGHTS_DB_PATH", "/ga_weights/V4_3Fold_Sign_weights.db")
WEIGHT_COL = os.environ.get("GA_WEIGHT_COLUMN", "GA_W")
RESULTS_DIR = os.environ.get("SAVE_TMP_DIR", "/app/save_tmp")
PLINK2_CMD = os.environ.get("PLINK2_CMD", "plink2")

# ─────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────
st.set_page_config(
    page_title="GA Gene Expression Prediction",
    page_icon="🧬",
    layout="wide",
)

# Hide the "+" button in file uploader
st.markdown("""
<style>
    [data-testid="fileUploadDropzone"] button {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

st.title("GA-Calibrated Gene Expression Prediction")

# Column descriptions for tables
EXPR_COLUMN_HELP = {
    "FID": "Family ID",
    "IID": "Individual ID",
}

QC_COLUMN_HELP = {
    "gene": "Ensembl gene ID",
    "n_snps_in_model": "Number of SNPs in the gene model",
    "n_snps_used": "Number of SNPs actually used in prediction",
    "pct_snps_used": "Percentage of model SNPs found in VCF",
    "pred_mean": "Mean of predicted expression",
    "pred_sd": "Standard deviation of predicted expression",
    "var_g": "Genetic variance explained",
    "status": "Prediction status indicator",
}

# Status code display mapping (internal code -> display name + help text)
STATUS_DISPLAY_MAP = {
    "OK": {
        "display_name": "PASS",
        "help": "SNP coverage ≥50%, high confidence"
    },
    "LOW_SNP_COVERAGE": {
        "display_name": "WARNING",
        "help": "SNP coverage <50%, use with caution"
    },
    "NO_SNPS_IN_VCF": {
        "display_name": "NO_DATA",
        "help": "No SNPs found in VCF"
    },
    "NO_MODEL_SNPS": {
        "display_name": "FILTERED",
        "help": "Gene pruned in GA stage, no usable weights"
    },
    "ZERO_VARIANCE": {
        "display_name": "NO_VARIANCE",
        "help": "Predicted values have no variance (no discriminative power)"
    },
}

# ─────────────────────────────────────────────────
# Initialize session state
# ─────────────────────────────────────────────────
if "ga_uuid" not in st.session_state:
    st.session_state.ga_uuid = None
if "ga_results" not in st.session_state:
    st.session_state.ga_results = None
if "error" not in st.session_state:
    st.session_state.error = None

# ─────────────────────────────────────────────────
# Get available weights databases
# ─────────────────────────────────────────────────
def get_available_weights():
    """List all available weight databases"""
    weights_dir = os.path.dirname(WEIGHTS_DB)
    if os.path.exists(weights_dir):
        db_files = sorted([f for f in os.listdir(weights_dir) if f.endswith('.db')])
        return db_files
    return []

def get_status_display_name(status_code: str) -> str:
    """Convert internal status code to display name"""
    return STATUS_DISPLAY_MAP.get(status_code, {}).get("display_name", status_code)

available_dbs = get_available_weights()
selected_weight_db = None
selected_weight_col = None

# ─────────────────────────────────────────────────
# Sidebar: Input & Configuration
# ─────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Session UUID")

    # Display current UUID if exists
    if st.session_state.ga_uuid:
        st.info(f"{st.session_state.ga_uuid}")

    uuid_input = st.text_input(
        "UUID",
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        label_visibility="collapsed"
    )

    if st.button("Load UUID", use_container_width=True):
        if uuid_input:
            st.session_state.ga_uuid = uuid_input
            st.rerun()

    st.divider()

    st.subheader("Input")
    vcf_file = st.file_uploader(
        "Upload VCF genotype file (.vcf / .vcf.gz)",
        type=["vcf", "gz"],
        accept_multiple_files=False
    )

    # Auto-generate UUID when file is uploaded (if no UUID exists)
    if vcf_file and not st.session_state.ga_uuid:
        st.session_state.ga_uuid = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.subheader("Configuration")

    # Weight Type selector (先選擇權重類型)
    weight_type_display = ["GA-Calibrated Weights", "Original PrediXcan Weight"]
    weight_type_values = ["GA_W", "PrediXcan_W"]

    selected_weight_col = st.radio(
        "Weight Type",
        options=weight_type_display,
        index=0,
        help="Select which weight model to use for prediction"
    )
    selected_weight_col = weight_type_values[weight_type_display.index(selected_weight_col)]

    # Weights Database selector (只在選擇 GA 時顯示)
    if selected_weight_col == "GA_W":
        if available_dbs:
            default_idx = 0
            if "V4_3Fold_Sign_weights.db" in available_dbs:
                default_idx = available_dbs.index("V4_3Fold_Sign_weights.db")

            selected_db_name = st.selectbox(
                "Weights Database",
                options=available_dbs,
                index=default_idx,
                help="Choose which GA weight database version to use"
            )
            weights_dir = os.path.dirname(WEIGHTS_DB)
            selected_weight_db = os.path.join(weights_dir, selected_db_name)
        else:
            st.warning(f"⚠️ No GA weights database found")
            selected_weight_db = WEIGHTS_DB
    else:
        # For PrediXcan_W, use the built-in database without selection
        st.info("✓ Using built-in Original PrediXcan Weight database")
        selected_weight_db = WEIGHTS_DB

    st.divider()

    # Run Analysis button (disabled if no file selected)
    run_analysis = st.button(
        "Run Prediction",
        use_container_width=True,
        type="primary",
        disabled=not vcf_file,
        help="Select a VCF file first" if not vcf_file else "Click to start"
    )


# ─────────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────────
st.markdown("""
Predict gene expression using GA-calibrated weights.
""")

st.info("Use the sidebar to upload analysis data, select weights configuration, and run the prediction.")

# Show status message (hide when running analysis)
if vcf_file and not run_analysis:
    st.info(f"VCF file selected: **{vcf_file.name}** ({vcf_file.size / 1024 / 1024:.1f} MB)\n\nClick **Run Prediction** button in the sidebar to start")

if run_analysis and vcf_file:
    if not selected_weight_db:
        st.error("❌ No weights database available. Please check configuration.")
        st.stop()

    st.divider()

    # Use session UUID for working directory
    work_dir = os.path.join(RESULTS_DIR, st.session_state.ga_uuid)
    os.makedirs(work_dir, exist_ok=True)

    vcf_path = os.path.join(work_dir, vcf_file.name)
    with open(vcf_path, "wb") as f:
        f.write(vcf_file.getbuffer())

    # Create pipeline with selected configuration
    try:
        pipeline = GenexprPipeline(
            weights_db=selected_weight_db,
            plink2_cmd=PLINK2_CMD,
            weight_col=selected_weight_col,
        )
    except Exception as e:
        st.error(f"Failed to initialize pipeline: {e}")
        st.stop()

    # Run prediction
    st.subheader("Processing Progress")
    progress_container = st.container()
    status_text = st.empty()
    progress_bar = st.progress(0)

    try:
        def update_progress(message: str, pct: int):
            status_text.write(message)
            progress_bar.progress(min(pct / 100, 0.99))

        expr_path, summary_path = pipeline.run(
            vcf_path=vcf_path,
            output_dir=work_dir,
            progress_callback=update_progress,
            assume_aligned=False,  # Always perform allele check for safety
        )
        progress_bar.progress(1.0)
        status_text.success("Prediction complete!")

        # Load results
        expr_df, summary_df = load_results(expr_path, summary_path)
        st.session_state.ga_results = {
            "expr_path": expr_path,
            "summary_path": summary_path,
            "expr_df": expr_df,
            "summary_df": summary_df,
            "session_uuid": st.session_state.ga_uuid,
        }

    except Exception as e:
        st.error(f"Prediction failed: {e}")
        st.session_state.error = str(e)
        st.stop()

# ─────────────────────────────────────────────────
# Try to load results from disk if UUID is set but results not in memory
# ─────────────────────────────────────────────────
if st.session_state.ga_uuid and not st.session_state.ga_results:
    work_dir = os.path.join(RESULTS_DIR, st.session_state.ga_uuid)
    expr_path = os.path.join(work_dir, "predicted_predicted_expression.csv")
    summary_path = os.path.join(work_dir, "predicted_summary.csv")

    if os.path.exists(expr_path) and os.path.exists(summary_path):
        try:
            expr_df, summary_df = load_results(expr_path, summary_path)
            st.session_state.ga_results = {
                "expr_path": expr_path,
                "summary_path": summary_path,
                "expr_df": expr_df,
                "summary_df": summary_df,
                "session_uuid": st.session_state.ga_uuid,
            }
            st.success("✅ Results loaded from previous analysis")
        except Exception as e:
            st.warning(f"Could not load results: {e}")

# ─────────────────────────────────────────────────
# Results Display
# ─────────────────────────────────────────────────
if st.session_state.ga_results:
    results = st.session_state.ga_results
    expr_df = results["expr_df"]
    summary_df = results["summary_df"]

    st.divider()

    # Show UUID if available
    if results.get("session_uuid"):
        st.caption(f"Session UUID: {results['session_uuid']} — save this to reload results later")

    st.subheader("Results Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Samples", expr_df.shape[0])
    with col2:
        n_genes_predicted = expr_df.shape[1] - 2  # FID, IID
        st.metric("Predicted Genes", n_genes_predicted)
    with col3:
        n_pass = (summary_df["status"] == "OK").sum()
        st.metric("PASS", n_pass)
    with col4:
        n_warning = (summary_df["status"] == "LOW_SNP_COVERAGE").sum()
        st.metric("WARNING", n_warning)

    # Status distribution
    st.subheader("Prediction Status Distribution")
    status_counts = summary_df["status"].value_counts()
    status_display = {status: get_status_display_name(status) for status in status_counts.index}
    status_counts_display = status_counts.rename(index=status_display)
    status_counts_display = status_counts_display.sort_index()
    st.bar_chart(status_counts_display)

    # Summary stats
    st.subheader("Detailed Results")
    tabs = st.tabs(["Predicted Expression", "Predicted Summary", "Status Codes"])

    with tabs[0]:
        st.write("**Predicted Expression Matrix** (first 5 rows)")
        # Apply column configuration with help tooltips
        col_configs = {}
        for col in expr_df.columns:
            if col in EXPR_COLUMN_HELP:
                col_configs[col] = st.column_config.TextColumn(
                    col,
                    help=EXPR_COLUMN_HELP[col]
                )
        st.dataframe(expr_df.head(), column_config=col_configs, use_container_width=True)

    with tabs[1]:
        st.write("**Gene QC Metrics** (first 10 rows)")
        display_cols = [
            "gene", "n_snps_in_model", "n_snps_used", "pct_snps_used",
            "pred_mean", "pred_sd", "var_g", "status"
        ]
        display_cols = [c for c in display_cols if c in summary_df.columns]

        # Apply column configuration with help tooltips
        col_configs = {}
        for col in display_cols:
            if col in QC_COLUMN_HELP:
                col_configs[col] = st.column_config.TextColumn(
                    col,
                    help=QC_COLUMN_HELP[col]
                )
        st.dataframe(summary_df[display_cols].head(10), column_config=col_configs, use_container_width=True)

    with tabs[2]:
        st.write("**Prediction Status Reference**")
        col1, col2 = st.columns([1, 3])

        for status_code, mapping in STATUS_DISPLAY_MAP.items():
            display_name = mapping["display_name"]
            help_text = mapping["help"]
            count = (summary_df["status"] == status_code).sum()

            with col1:
                st.write(f"**{display_name}** ({count})")
            with col2:
                st.caption(help_text)

    # Download section
    st.divider()
    st.subheader("Download Results")
    col1, col2 = st.columns(2)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    with col1:
        with open(results["expr_path"], "rb") as f:
            st.download_button(
                label="Download Predicted Expression (CSV)",
                data=f.read(),
                file_name=f"predicted_expression_{timestamp}.csv",
                mime="text/csv",
            )

    with col2:
        with open(results["summary_path"], "rb") as f:
            st.download_button(
                label="Download Predicted Summary (CSV)",
                data=f.read(),
                file_name=f"predicted_summary_{timestamp}.csv",
                mime="text/csv",
            )

    st.divider()
    st.markdown(f"<div style='background-color: #1e3a5f; padding: 15px; border-radius: 5px;'><span style='color: #ff4444; font-weight: bold;'>Session UUID: {st.session_state.ga_uuid}</span><br><span style='color: #88ccee;'>Save this to reload results later</span></div>", unsafe_allow_html=True)
