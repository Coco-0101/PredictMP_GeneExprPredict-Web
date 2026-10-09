"""
GA-Calibrated Gene Expression Prediction
Upload a genotype.vcf -> predict expression using GA-calibrated weights
"""

import os
import time
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

from core.ga_pipeline import GAPipeline, load_results, EXPR_FILE, SUMMARY_FILE
from core.storage import is_valid_session_id, new_session_id, session_dir
from ui import paginate_dataframe, retention_notice

# ─────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────
WEIGHTS_DB = os.environ.get("GA_WEIGHTS_DB_PATH", "/ga_weights/V4_LOOCV_Sign_weights.db")
WEIGHT_COL = os.environ.get("GA_WEIGHT_COLUMN", "GA_W")
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
    "n_snps_in_model": "Number of SNPs with a non-zero weight in the selected model",
    "n_snps_used": "Number of SNPs actually used in prediction",
    "pct_snps_used": "Fraction of model SNPs found in the VCF (0–1); below 0.5 is flagged WARNING",
    "pred_mean": "Mean of predicted expression",
    "pred_sd": "Standard deviation of predicted expression",
    "var_g": "Variance of predicted expression across the uploaded samples (pred_sd²); 0 means NO_VARIANCE",
    "avg_confidence_score": "Mean confidence score of the model SNPs found in the VCF",
    "train_corr": "Gene's correlation in GA training",
    "corr_after_GA": "Gene's correlation after GA calibration",
    "n_snps": "SNPs for this gene in GA training, including pruned ones",
    "status": "Prediction status indicator",
}

# Status code display mapping (internal code -> display name + help text)
STATUS_DISPLAY_MAP = {
    "OK": {
        "display_name": "PASS",
        "help": "SNP coverage ≥50%"
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
if "upload_seen_key" not in st.session_state:
    st.session_state.upload_seen_key = None
if "upload_seen_time" not in st.session_state:
    st.session_state.upload_seen_time = None
if "auto_run_done_key" not in st.session_state:
    st.session_state.auto_run_done_key = None
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

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

available_dbs = get_available_weights()
selected_weight_db = None
selected_weight_col = None

# ─────────────────────────────────────────────────
# Sidebar: Input & Configuration
# ─────────────────────────────────────────────────
with st.sidebar:
    # Session UUID header with native Streamlit help icon
    st.subheader(
        "Session UUID",
        help="Leave blank to generate a new UUID for this analysis, or paste a previous UUID to reload previous results"
    )
    retention_notice()

    # Display current UUID if exists
    if st.session_state.ga_uuid:
        st.info(f"{st.session_state.ga_uuid}")
        st.caption(":red[**Copy and save this UUID to reload results later.**]")

    uuid_input = st.text_input(
        "UUID",
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        label_visibility="collapsed"
    )

    if st.button("Load UUID", width="stretch"):
        if uuid_input:
            if is_valid_session_id(uuid_input):
                st.session_state.ga_uuid = uuid_input.strip().lower()
                st.session_state.ga_results = None
                st.rerun()
            else:
                st.error("Invalid UUID format")

    st.divider()

    st.subheader("Input")
    vcf_file = st.file_uploader(
        "Upload VCF genotype file (.vcf / .vcf.gz)",
        type=["vcf", "gz"],
        accept_multiple_files=False
    )

    # Detect a newly-completed upload (server has fully received the file)
    # and record the timestamp -- this is the earliest point in the script
    # where we know the upload finished.
    if vcf_file is not None:
        file_key = f"{vcf_file.name}_{vcf_file.size}"
        if file_key != st.session_state.upload_seen_key:
            st.session_state.upload_seen_key = file_key
            st.session_state.upload_seen_time = time.time()

    # Auto-generate UUID when file is uploaded (if no UUID exists)
    if vcf_file and not st.session_state.ga_uuid:
        st.session_state.ga_uuid = new_session_id()
        st.rerun()

    auto_run = st.checkbox(
        "Auto-run prediction after upload completes",
        value=False,
        help="When enabled, prediction starts automatically as soon as the file finishes uploading -- no need to click Run Prediction"
    )

    st.divider()
    st.subheader("Configuration")

    # Weight Type selector (先選擇權重類型)
    weight_type_display = ["GA-Calibrated Weights", "Original PrediXcan Weight"]
    weight_type_values = ["GA_W", "PrediXcan_W"]

    selected_weight_col = st.radio(
        "Weight Selection",
        options=weight_type_display,
        index=0,
        help="Select which weight model to use for prediction"
    )
    selected_weight_col = weight_type_values[weight_type_display.index(selected_weight_col)]

    # Sign/Unsigned selector (只在選擇 GA 時顯示，使用邊框 + 縮進表示層級)
    if selected_weight_col == "GA_W":
        # 使用邊框容器顯示子選項
        with st.container(border=True):
            st.markdown("##### LOOCV Weight Type")

            sign_type_display = ["Sign-flipped (Recommended)", "Unsigned"]
            sign_type_values = ["Sign", "Unsign"]

            selected_sign_type = st.radio(
                "Select weight type:",
                options=sign_type_display,
                index=0,
                help="Sign-flipped: Recommended for most analyses | Unsigned: Alternative option",
                label_visibility="collapsed"
            )
            selected_sign_type = sign_type_values[sign_type_display.index(selected_sign_type)]

            # Build the database filename based on selection
            weights_dir = os.path.dirname(WEIGHTS_DB)
            if selected_sign_type == "Sign":
                db_filename = "V4_LOOCV_Sign_weights.db"
            else:
                db_filename = "V4_LOOCV_Unsign_weights.db"

            selected_weight_db = os.path.join(weights_dir, db_filename)

            # Display selected database info
            st.success(f"✓ Using: LOOCV {selected_sign_type} weights database")

            # Verify database exists
            if not os.path.exists(selected_weight_db):
                st.warning(f"⚠️ Database not found: {db_filename}")
                st.info(f"Available databases: {', '.join(available_dbs) if available_dbs else 'None'}")
    else:
        # For PrediXcan_W, use the original weights stored in the same database
        st.success("✓ Using original PrediXcan weights")
        selected_weight_db = WEIGHTS_DB

    st.divider()

    # Run Analysis button (disabled if no file selected, or already running --
    # prevents a stray click from re-triggering a second overlapping run)
    manual_run = st.button(
        "Run Prediction",
        width="stretch",
        type="primary",
        disabled=not vcf_file or st.session_state.is_processing,
        help=(
            "Select a VCF file first" if not vcf_file
            else "Prediction already running" if st.session_state.is_processing
            else "Click to start"
        )
    )

# Determine whether to run: either the user clicked the button, or
# auto-run is enabled and this specific upload hasn't been processed yet.
# Also refuse to start a new run while one is already in flight for this
# UUID -- this is the key guard against duplicate/overlapping pipeline
# runs stepping on each other's temp files.
current_file_key = st.session_state.upload_seen_key
should_auto_run = (
    auto_run
    and vcf_file is not None
    and current_file_key is not None
    and current_file_key != st.session_state.auto_run_done_key
)
run_analysis = (manual_run or should_auto_run) and not st.session_state.is_processing

if run_analysis and vcf_file:
    # The file is marked as processed (so auto-run doesn't re-trigger on every
    # rerun) only once the run finishes or fails. If the user changes a setting
    # mid-run, Streamlit interrupts the run and the rerun auto-runs again with
    # the new setting instead of silently dropping it.
    st.session_state.is_processing = True


# ─────────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────────
st.markdown("""
Predict gene expression using GA-calibrated weights.
""")

st.info("Use the sidebar to upload analysis data, select weights configuration, and run the prediction.")

# Show status message (hide when running analysis)
if vcf_file and not run_analysis:
    upload_elapsed = None
    if st.session_state.upload_seen_time:
        upload_elapsed = time.time() - st.session_state.upload_seen_time
    elapsed_note = f" — ready {upload_elapsed:.1f}s ago" if upload_elapsed is not None else ""
    if auto_run:
        st.info(f"VCF file selected: **{vcf_file.name}** ({vcf_file.size / 1024 / 1024:.1f} MB){elapsed_note}\n\nAuto-run is enabled — prediction should start automatically. If it doesn't, click **Run Prediction**.")
    else:
        st.info(f"VCF file selected: **{vcf_file.name}** ({vcf_file.size / 1024 / 1024:.1f} MB){elapsed_note}\n\nClick **Run Prediction** button in the sidebar to start")

if run_analysis and vcf_file:
    # Always release the processing lock on the way out, however this
    # block exits (success, error, or an early st.stop()).
    try:
        if not selected_weight_db:
            st.error("❌ No weights database available. Please check configuration.")
            st.stop()

        st.divider()

        # Use session UUID for working directory
        work_dir = str(session_dir(st.session_state.ga_uuid, create=True))

        vcf_path = os.path.join(work_dir, Path(vcf_file.name).name)
        with open(vcf_path, "wb") as f:
            f.write(vcf_file.getbuffer())

        # Create pipeline with selected configuration
        try:
            pipeline = GAPipeline(
                weights_db=selected_weight_db,
                plink2_cmd=PLINK2_CMD,
                weight_col=selected_weight_col,
            )
        except Exception as e:
            st.session_state.auto_run_done_key = current_file_key
            st.error(f"Failed to initialize pipeline: {e}")
            st.stop()

        # Run prediction
        st.subheader("Processing Progress")

        if st.session_state.upload_seen_time:
            upload_ready_ago = time.time() - st.session_state.upload_seen_time
            st.caption(f"File finished uploading {upload_ready_ago:.1f}s before prediction started")

        progress_container = st.container()
        status_text = st.empty()
        progress_bar = st.progress(0)

        pipeline_start_time = time.time()

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

            pipeline_elapsed = time.time() - pipeline_start_time
            timing_note = f" (prediction took {pipeline_elapsed:.1f}s"
            if st.session_state.upload_seen_time:
                total_elapsed = time.time() - st.session_state.upload_seen_time
                timing_note += f", {total_elapsed:.1f}s total since upload finished"
            timing_note += ")"
            status_text.success(f"Prediction complete!{timing_note}")

            # Load results
            expr_df, summary_df = load_results(expr_path, summary_path)
            st.session_state.ga_results = {
                "expr_path": expr_path,
                "summary_path": summary_path,
                "expr_df": expr_df,
                "summary_df": summary_df,
                "session_uuid": st.session_state.ga_uuid,
            }
            st.session_state.auto_run_done_key = current_file_key

        except Exception as e:
            st.session_state.auto_run_done_key = current_file_key
            st.error(f"Prediction failed: {e}")
            st.session_state.error = str(e)
            st.stop()
    finally:
        st.session_state.is_processing = False

# ─────────────────────────────────────────────────
# Try to load results from disk if UUID is set but results not in memory
# ─────────────────────────────────────────────────
if st.session_state.ga_uuid and not st.session_state.ga_results:
    work_dir = session_dir(st.session_state.ga_uuid)
    expr_path = str(work_dir / EXPR_FILE)
    summary_path = str(work_dir / SUMMARY_FILE)

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

    # Summary stats
    st.subheader("Detailed Results")
    tabs = st.tabs(["Predicted Expression", "Predicted Summary", "Status Codes"])

    with tabs[0]:
        st.write(f"**Predicted Expression Matrix** ({len(expr_df)} samples × {len(expr_df.columns)-2} genes)")

        # Transpose table: genes as rows, samples (IID) as columns.
        # FID is kept out of the column header (a MultiIndex there would
        # render as an extra "0" header row above IID) -- instead it's
        # shown as a caption if constant across samples, or as the first
        # data row (alongside the genes) if it actually varies, so no
        # information is lost either way.
        fid_by_iid = expr_df.set_index("IID")["FID"]
        expr_df_display = expr_df.drop(columns=["FID"]).set_index("IID").T
        expr_df_display.index.name = "gene"

        if fid_by_iid.nunique() <= 1:
            fid_value = fid_by_iid.iloc[0] if len(fid_by_iid) else ""
            st.caption(f"FID: {fid_value} (same for all samples)")
        else:
            fid_row = fid_by_iid.to_frame().T
            fid_row.index = ["FID"]
            expr_df_display = pd.concat([fid_row, expr_df_display])

        # Paginate: show 500 genes/rows per page instead of the whole table
        expr_page_display, expr_page_num, expr_total_pages = paginate_dataframe(
            expr_df_display, key="expr", page_size=500
        )
        st.dataframe(expr_page_display, width="stretch", height=400)

        # Download section for Predicted Expression -- downloads only the
        # currently displayed page, not the full dataset
        st.divider()
        st.write(f"**Download** (page {expr_page_num} of {expr_total_pages})")

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        csv_data = expr_page_display.to_csv()
        st.download_button(
            label=f"Download Predicted Expression — Page {expr_page_num} (CSV)",
            data=csv_data,
            file_name=f"predicted_expression_page{expr_page_num}_{timestamp}.csv",
            mime="text/csv",
            width="stretch",
            on_click="ignore",  # downloading must not rerun the (large) page
        )

    with tabs[1]:
        st.write(f"**Gene QC Metrics** ({len(summary_df)} genes)")
        display_cols = [
            "gene", "n_snps_in_model", "n_snps_used", "pct_snps_used",
            "pred_mean", "pred_sd", "var_g", "avg_confidence_score",
            "train_corr", "corr_after_GA", "n_snps", "status"
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
        # Paginate: show 500 genes/rows per page instead of the whole table
        summary_page, summary_page_num, summary_total_pages = paginate_dataframe(
            summary_df[display_cols], key="summary", page_size=500
        )
        st.dataframe(summary_page, column_config=col_configs, width="stretch", height=400)

        # Download section for Predicted Summary -- downloads only the
        # currently displayed page, not the full dataset
        st.divider()
        st.write(f"**Download** (page {summary_page_num} of {summary_total_pages})")

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        csv_data = summary_page.to_csv(index=False)
        st.download_button(
            label=f"Download Predicted Summary — Page {summary_page_num} (CSV)",
            data=csv_data,
            file_name=f"predicted_summary_page{summary_page_num}_{timestamp}.csv",
            mime="text/csv",
            width="stretch",
            on_click="ignore",  # downloading must not rerun the (large) page
        )

    with tabs[2]:
        st.write("**Prediction Status Reference**")

        # Build status reference table
        status_data = []
        for status_code, mapping in STATUS_DISPLAY_MAP.items():
            display_name = mapping["display_name"]
            help_text = mapping["help"]
            count = (summary_df["status"] == status_code).sum()
            status_data.append({
                "Status": f"{display_name} ({count})",
                "Description": help_text
            })

        # Display as table
        status_df = pd.DataFrame(status_data)
        st.dataframe(
            status_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(width="medium"),
                "Description": st.column_config.TextColumn(width="large"),
            }
        )
