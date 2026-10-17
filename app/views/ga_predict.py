"""
GA-Calibrated Gene Expression Prediction
Upload a genotype.vcf -> predict expression using GA-calibrated weights
"""

import os
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

from core.ga_pipeline import GAPipeline, load_results, EXPR_FILE, SUMMARY_FILE
from core.storage import is_valid_session_id, new_session_id, session_dir
from ui import paginate_dataframe, retention_consent

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

def format_size(n_bytes):
    """File size with two decimals in the largest fitting unit, e.g. 412.35 KB."""
    size = float(n_bytes)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{n_bytes:,} bytes" if unit == "bytes" else f"{size:.2f} {unit}"
        size /= 1024


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
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "ga_reset_controls" not in st.session_state:
    st.session_state.ga_reset_controls = False

# After each prediction the confirmation and auto-run boxes start unticked
# again, so every new analysis needs a fresh confirmation. Widget values can
# only be changed before the widgets are drawn, hence the flag set by the
# previous run.
if st.session_state.ga_reset_controls:
    st.session_state.ga_consent = False
    st.session_state.ga_auto_run = False
    st.session_state.ga_reset_controls = False

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

    # Filled in once we know whether this run switches to a new UUID
    uuid_box = st.container()

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

    # Every newly uploaded file starts a new session: a fresh UUID (so earlier
    # results are never overwritten) and no results from the previous file.
    file_key = f"{vcf_file.name}_{vcf_file.size}" if vcf_file is not None else None
    if file_key != st.session_state.upload_seen_key:
        st.session_state.upload_seen_key = file_key
        if file_key:
            st.session_state.ga_uuid = new_session_id()
            st.session_state.ga_results = None

    st.divider()
    st.subheader("Configuration")

    # Weight Type selector (先選擇權重類型)
    weight_type_display = ["GA-Calibrated Weights", "Original PrediXcan Weights"]
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
    consent = retention_consent("ga_consent")

    # Auto-run is only available once the retention notice is confirmed;
    # unticking the notice also unticks auto-run.
    if not consent:
        st.session_state.ga_auto_run = False
    auto_run = st.checkbox(
        "Auto-run prediction after upload completes",
        key="ga_auto_run",
        disabled=not consent,
        help="When enabled, prediction starts automatically as soon as the file finishes uploading, using the weights selected above -- no need to click Run Prediction"
            if consent else "Confirm the data retention notice first"
    )

    manual_run = st.button(
        "Run Prediction",
        width="stretch",
        type="primary",
        disabled=not vcf_file or not consent or st.session_state.is_processing,
        help=(
            "Select a VCF file first" if not vcf_file
            else "Confirm the data retention notice first" if not consent
            else "Prediction already running" if st.session_state.is_processing
            else "Click to start"
        )
    )

# Determine whether to run: either the user clicked the button, or auto-run
# is ticked and a file is there. Auto-run does not repeat on every rerun
# because the boxes are cleared once a run finishes or fails. Also refuse to start a new run while one is already in flight for this
# UUID -- this is the key guard against duplicate/overlapping pipeline
# runs stepping on each other's temp files.
current_file_key = st.session_state.upload_seen_key
should_auto_run = (
    auto_run
    and consent
    and vcf_file is not None
    and current_file_key is not None
)
run_analysis = (manual_run or should_auto_run) and not st.session_state.is_processing

# Running again in a session that already has results (another run on the same
# file, or a reloaded UUID) moves to a new UUID so those results are kept
if run_analysis and vcf_file:
    if (session_dir(st.session_state.ga_uuid) / EXPR_FILE).exists():
        st.session_state.ga_uuid = new_session_id()
    st.session_state.ga_results = None

with uuid_box:
    if st.session_state.ga_uuid:
        st.info(f"{st.session_state.ga_uuid}")
        st.caption(":red[**Copy and save this UUID to reload results later.**]")

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

# Outcome of the prediction that just finished (shown once, after the rerun
# that resets the sidebar)
flash = st.session_state.pop("ga_flash", None)
if flash:
    getattr(st, flash[0])(flash[1])

# Show file selection status (hide while running and once results are shown)
show_status = not run_analysis and not st.session_state.ga_results
if vcf_file and show_status:
    if auto_run:
        st.info(f"VCF file selected: **{vcf_file.name}** ({format_size(vcf_file.size)})\n\nAuto-run is enabled — prediction should start automatically. If it doesn't, click **Run Prediction**.")
    else:
        st.info(f"VCF file selected: **{vcf_file.name}** ({format_size(vcf_file.size)})\n\nClick **Run Prediction** button in the sidebar to start")
elif not vcf_file and show_status:
    st.info("Use the sidebar to upload analysis data, select weights configuration, then click **Run Prediction**.")

if run_analysis and vcf_file:
    # Always release the processing lock and delete the uploaded VCF on the way
    # out, however this block exits (success, error, or an early st.stop()):
    # only the results are kept in the session folder
    vcf_path = None
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

        # Create pipeline with selected configuration, then run the prediction.
        # The outcome is kept in ga_flash and shown after the rerun below.
        try:
            pipeline = GAPipeline(
                weights_db=selected_weight_db,
                plink2_cmd=PLINK2_CMD,
                weight_col=selected_weight_col,
            )
        except Exception as e:
            pipeline = None
            st.session_state.ga_flash = ("error", f"Failed to initialize pipeline: {e}")

        if pipeline is not None:
            st.subheader("Processing Progress")

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

                # Load results
                expr_df, summary_df = load_results(expr_path, summary_path)
                st.session_state.ga_results = {
                    "expr_path": expr_path,
                    "summary_path": summary_path,
                    "expr_df": expr_df,
                    "summary_df": summary_df,
                    "session_uuid": st.session_state.ga_uuid,
                }
                st.session_state.ga_flash = ("success", "Prediction complete!")

            except Exception as e:
                st.session_state.ga_results = None
                st.session_state.error = str(e)
                st.session_state.ga_flash = ("error", f"Prediction failed: {e}")
    finally:
        if vcf_path:
            Path(vcf_path).unlink(missing_ok=True)
        st.session_state.is_processing = False

    # Finished (either way): redraw the page with the confirmation and auto-run
    # boxes cleared
    st.session_state.ga_reset_controls = True
    st.rerun()

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
    # Time the prediction finished, i.e. when its output file was written;
    # used in the download file names
    completed_at = datetime.fromtimestamp(os.path.getmtime(results["expr_path"])).strftime('%Y-%m-%d_%H-%M-%S')

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

        timestamp = completed_at

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

        timestamp = completed_at

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
