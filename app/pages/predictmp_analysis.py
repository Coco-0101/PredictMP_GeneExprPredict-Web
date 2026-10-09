"""
PredictMP Analysis - percentile rank of PrediXcan results against gnomAD v4.1 reference populations
"""

import json

import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO

from core.storage import is_valid_session_id, new_session_id, session_dir
from core.tissues import TISSUE_NAME_TO_CODE, TISSUES, POPULATION_MAP, POPULATIONS
from ui import paginate_dataframe, retention_notice

try:
    from PredictMP import rankcal
except ImportError:
    rankcal = None

RESULT_FILE = "predictmp_results.csv"
META_FILE = "predictmp_meta.json"   # tissue / population chosen for the run


COLUMN_DESCRIPTIONS = {
    "FID": "Family ID from the user's data",
    "IID": "Individual ID from the user's data",
    "gene": "Ensembl gene ID",
    "expression": "Predicted gene expression from the user's data",
    "percentile.rank": "Percentile ranks of user's gene expression compared to the reference",
    "N.snps": "Number of variants used in predicting gene expression",
    "mean": "Average value of the reference",
    "sd": "Standard deviation of the reference",
    "ks.test": "Significance indicator of the Kolmogorov-Smirnov test",
}

def get_column_descriptions(population_code):
    """Get column descriptions with dynamic population comparison"""
    descriptions = COLUMN_DESCRIPTIONS.copy()
    pop_label = population_code.upper()
    descriptions[f"NFE.{pop_label}.mean.diff"] = f"Mean differences between {pop_label} and NFE reference populations"
    return descriptions

st.set_page_config(
    page_title="PredictMP Analysis",
    page_icon="📊",
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

# Initialize session state
if "predictmp_uuid" not in st.session_state:
    st.session_state.predictmp_uuid = None
if "predictmp_results" not in st.session_state:
    st.session_state.predictmp_results = None
if "predictmp_auto_run_done_key" not in st.session_state:
    st.session_state.predictmp_auto_run_done_key = None

# ─────────────────────────────────────────────────
# Sidebar Configuration
# ─────────────────────────────────────────────────
with st.sidebar:
    # Session UUID header with native Streamlit help icon
    st.subheader(
        "Session UUID",
        help="Leave blank to generate a new UUID for this analysis, or paste a previous UUID to reload previous results"
    )
    retention_notice()

    # Display current UUID if exists
    if st.session_state.predictmp_uuid:
        st.info(f"{st.session_state.predictmp_uuid}")
        st.caption(":red[**Copy and save this UUID to reload results later.**]")

    uuid_input = st.text_input(
        "UUID",
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        label_visibility="collapsed"
    )

    if st.button("Load UUID", width="stretch"):
        if uuid_input:
            if is_valid_session_id(uuid_input):
                st.session_state.predictmp_uuid = uuid_input.strip().lower()
                st.session_state.predictmp_results = None
                st.rerun()
            else:
                st.error("Invalid UUID format")

    st.divider()

    st.subheader("Input")
    uploaded_file = st.file_uploader(
        "Upload PrediXcan result (.txt / .csv)",
        type=["txt", "csv"],
        accept_multiple_files=False
    )

    # Auto-generate UUID when file is uploaded (if no UUID exists)
    if uploaded_file and not st.session_state.predictmp_uuid:
        st.session_state.predictmp_uuid = new_session_id()
        st.rerun()

    auto_run = st.checkbox(
        "Auto-run analysis after upload completes",
        value=False,
        help="When enabled, analysis starts automatically as soon as the file finishes uploading, using the tissue type and population selected below -- no need to click Run PredictMP"
    )

    st.divider()
    st.subheader("Configuration")

    tissue_type = st.selectbox(
        "Tissue Type",
        TISSUES,
        help="GTEx tissue of the PrediXcan model that produced your predicted expression"
    )

    population = st.selectbox(
        "Reference Population",
        POPULATIONS,
        help="gnomAD v4.1 population whose simulated distribution is used for percentile ranks"
    )

    st.divider()

    run_button_disabled = not uploaded_file or not st.session_state.predictmp_uuid
    manual_run = st.button(
        "Run PredictMP",
        width="stretch",
        type="primary",
        disabled=run_button_disabled,
        help="Select a PrediXcan result file first" if run_button_disabled else "Click to start"
    )

# Run either when the button is clicked, or when auto-run is on and this
# upload has not been analysed yet (so it does not re-run on every rerun).
# The upload is only marked as analysed once a run finishes or fails: if the
# user changes a setting mid-run, Streamlit interrupts the run, and the rerun
# auto-runs again with the new setting instead of silently dropping it.
# Keys are prefixed so they do not collide with the GA page's session state.
file_key = f"{uploaded_file.name}_{uploaded_file.size}" if uploaded_file else None
should_auto_run = (
    auto_run
    and file_key is not None
    and st.session_state.predictmp_uuid is not None
    and file_key != st.session_state.predictmp_auto_run_done_key
)
run_analysis = manual_run or should_auto_run

# ─────────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────────
st.title("PredictMP")
st.write("**Predict Multi-Population**")

# Show file selection status (hide when running analysis)
if uploaded_file and not run_analysis:
    if auto_run:
        st.info(f"PrediXcan result selected: {uploaded_file.name} ({uploaded_file.size / 1024 / 1024:.1f} MB)\n\nAuto-run has already analysed this file. Change the settings and click **Run PredictMP** to run again.")
    else:
        st.info(f"PrediXcan result selected: {uploaded_file.name} ({uploaded_file.size / 1024 / 1024:.1f} MB)\n\nClick **Run PredictMP** button in the sidebar to start")
elif not uploaded_file and not run_analysis:
    st.info("Use the sidebar to upload analysis data, select tissue type and population, then click **Run PredictMP**.")

if run_analysis and uploaded_file:
    if rankcal is None:
        st.error("PredictMP package not found. Please check installation.")
        st.stop()

    try:
        # Get tissue code
        tissue_code = TISSUE_NAME_TO_CODE.get(tissue_type)
        if not tissue_code:
            st.error(f"Unknown tissue: {tissue_type}")
            st.stop()

        # Get population code
        pop_code = POPULATION_MAP.get(population)
        if not pop_code:
            st.error(f"Unknown population: {population}")
            st.stop()

        # Run analysis
        st.subheader("Processing")
        progress_text = st.empty()

        progress_text.write(f"Loading file and running PredictMP...")

        # Read uploaded file as DataFrame (PrediXcan output is tab-separated; .csv is comma-separated)
        stringio = StringIO(uploaded_file.getvalue().decode("utf8"))
        sep = "," if uploaded_file.name.lower().endswith(".csv") else "\t"
        input_df = pd.read_csv(stringio, sep=sep)

        progress_text.write(f"Running PredictMP with tissue={tissue_code}, population={pop_code}...")

        # Call PredictMP rankcal (pass DataFrame, not file path)
        result_df = rankcal(
            data=input_df,
            tissue=tissue_code,
            population=pop_code
        )

        progress_text.success("Analysis complete!")

        # Save results to CSV for later reload
        work_dir = session_dir(st.session_state.predictmp_uuid, create=True)
        result_df.to_csv(work_dir / RESULT_FILE, index=False)
        meta = {
            "tissue": tissue_type,
            "tissue_code": tissue_code,
            "population": population,
            "population_code": pop_code,
        }
        (work_dir / META_FILE).write_text(json.dumps(meta))

        # Store results in session state
        st.session_state.predictmp_results = {
            **meta,
            "uuid": st.session_state.predictmp_uuid,
            "dataframe": result_df,
        }
        st.session_state.predictmp_auto_run_done_key = file_key

    except Exception as e:
        st.session_state.predictmp_auto_run_done_key = file_key
        st.error(f"Analysis failed: {str(e)}")
        st.stop()

# Try to load results from disk if UUID is set but results not in memory
if st.session_state.predictmp_uuid and not st.session_state.predictmp_results:
    work_dir = session_dir(st.session_state.predictmp_uuid)
    result_csv = work_dir / RESULT_FILE
    if result_csv.exists():
        try:
            loaded_df = pd.read_csv(result_csv)
            meta_path = work_dir / META_FILE
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
            else:
                # Sessions saved before the meta file existed: the population can
                # be recovered from the "NFE.{POP}.mean.diff" column (absent for
                # NFE itself); the tissue cannot.
                diff_cols = [c for c in loaded_df.columns if c.startswith("NFE.") and c.endswith(".mean.diff")]
                pop_code = diff_cols[0].split(".")[1].lower() if diff_cols else "nfe"
                code_to_pop = {code: name for name, code in POPULATION_MAP.items()}
                meta = {
                    "tissue": "Unknown",
                    "population": code_to_pop.get(pop_code, pop_code.upper()),
                    "population_code": pop_code,
                }
            st.session_state.predictmp_results = {
                **meta,
                "uuid": st.session_state.predictmp_uuid,
                "dataframe": loaded_df,
            }
            st.success("✅ Results loaded from previous analysis")
        except Exception as e:
            st.warning(f"Could not load results: {e}")

# Display results
if st.session_state.predictmp_results:
    results = st.session_state.predictmp_results
    df = results["dataframe"]

    st.divider()

    # Title with tissue, population and timestamp (same pattern as the download file name)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    pop_display = results['population'].split(' ')[0]  # e.g., "AFR (African)" -> "AFR"
    st.subheader(f"Predict_{results['tissue']}_{pop_display}_{timestamp}.csv")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    n_subjects = df[["FID", "IID"]].drop_duplicates().shape[0]
    n_genes = df["gene"].nunique()
    median_percentile = df["percentile.rank"].median() if "percentile.rank" in df.columns else None
    # ks.test is per gene (same for every subject), so count unique genes, not rows
    ks_significant = df.loc[df["ks.test"] == "Sig.", "gene"].nunique() if "ks.test" in df.columns else None

    with col1:
        st.metric("Genes", f"{n_genes:,}")
    with col2:
        st.metric("Subjects", n_subjects)
    with col3:
        if median_percentile is not None:
            st.metric("Median percentile rank", f"{median_percentile:.1f}")
        else:
            st.metric("Median percentile rank", "N/A")
    with col4:
        if ks_significant is not None:
            st.metric("KS Significant genes", f"{ks_significant:,} / {n_genes:,}")
        else:
            st.metric("KS Significant genes", "N/A (NFE reference)")

    # Filter results
    with st.expander("Filter results", expanded=True):
        col_filter1, col_filter2 = st.columns(2)

        subjects = sorted(df["IID"].unique())

        with col_filter1:
            st.write("**Filter by Subject (IID)**")
            selected_subject = st.selectbox(
                "Subject",
                ["All subjects"] + list(subjects),
                label_visibility="collapsed"
            )

        with col_filter2:
            st.write("**Search gene**")
            search_gene = st.text_input(
                "Gene ID",
                placeholder="e.g. ENSG0000000457",
                label_visibility="collapsed"
            )

        # Apply filters
        filtered_df = df.copy()
        if selected_subject != "All subjects":
            filtered_df = filtered_df[filtered_df["IID"] == selected_subject]
        if search_gene:
            filtered_df = filtered_df[filtered_df["gene"].str.contains(search_gene, case=False, na=False)]

    # Results table with help
    st.write("**Results**")

    # Display dataframe with column descriptions as tooltips
    pop_code = results.get("population_code", "nfe")
    column_descriptions = get_column_descriptions(pop_code)

    col_configs = {}
    for col in filtered_df.columns:
        if col in column_descriptions:
            col_configs[col] = st.column_config.TextColumn(
                col,
                help=column_descriptions[col]
            )

    # Paginate: show 500 rows per page instead of the whole table
    page_df, page_num, total_pages = paginate_dataframe(
        filtered_df, key="predictmp", page_size=500
    )
    st.dataframe(
        page_df,
        column_config=col_configs,
        width="stretch",
        height=400,
        hide_index=False
    )

    # Download section -- downloads only the currently displayed page,
    # not the full dataset
    st.divider()
    st.write(f"**Download** (page {page_num} of {total_pages})")

    st.download_button(
        label=f"Download Results — Page {page_num} (CSV)",
        data=page_df.to_csv(index=False),
        file_name=f"Predict_{results['tissue']}_{pop_display}_page{page_num}_{timestamp}.csv",
        mime="text/csv",
        width="stretch",
        on_click="ignore",  # downloading must not rerun the (large) page
    )
