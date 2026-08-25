"""
PredictMP Analysis - Multi-Population Prediction
"""

import streamlit as st
import pandas as pd
import uuid
import tempfile
import os
from datetime import datetime
import sys

# Add PredictAP package to path
sys.path.insert(0, os.environ.get("PREDICTAP_PACKAGE_MOUNT", "/pkg/PredictAP_python"))

try:
    from PredictAP import rankcal
except ImportError:
    rankcal = None

# Tissue index mapping (from GTEx v8, 49 tissues)
TISSUE_INDEX = {
    "x1": "Adipose_Subcutaneous", "x2": "Adipose_Visceral_Omentum",
    "x3": "Adrenal_Gland", "x4": "Artery_Aorta",
    "x5": "Artery_Coronary", "x6": "Artery_Tibial",
    "x7": "Brain_Amygdala", "x8": "Brain_Anterior_cingulate_cortex_BA24",
    "x9": "Brain_Caudate_basal_ganglia", "x10": "Brain_Cerebellar_Hemisphere",
    "x11": "Brain_Cerebellum", "x12": "Brain_Cortex",
    "x13": "Brain_Frontal_Cortex_BA9", "x14": "Brain_Hippocampus",
    "x15": "Brain_Hypothalamus", "x16": "Brain_Nucleus_accumbens_basal_ganglia",
    "x17": "Brain_Putamen_basal_ganglia", "x18": "Brain_Spinal_cord_cervical_c-1",
    "x19": "Brain_Substantia_nigra", "x20": "Breast_Mammary_Tissue",
    "x21": "Cells_Cultured_fibroblasts", "x22": "Cells_EBV-transformed_lymphocytes",
    "x23": "Colon_Sigmoid", "x24": "Colon_Transverse",
    "x25": "Esophagus_Gastroesophageal_Junction", "x26": "Esophagus_Mucosa",
    "x27": "Esophagus_Muscularis", "x28": "Heart_Atrial_Appendage",
    "x29": "Heart_Left_Ventricle", "x30": "Kidney_Cortex",
    "x31": "Liver", "x32": "Lung",
    "x33": "Minor_Salivary_Gland", "x34": "Muscle_Skeletal",
    "x35": "Nerve_Tibial", "x36": "Ovary",
    "x37": "Pancreas", "x38": "Pituitary",
    "x39": "Prostate", "x40": "Skin_Not_Sun_Exposed_Suprapubic",
    "x41": "Skin_Sun_Exposed_Lower_leg", "x42": "Small_Intestine_Terminal_Ileum",
    "x43": "Spleen", "x44": "Stomach",
    "x45": "Testis", "x46": "Thyroid",
    "x47": "Uterus", "x48": "Vagina",
    "x49": "Whole_Blood",
}

# Reverse mapping: tissue name -> tissue code
TISSUE_NAME_TO_CODE = {v: k for k, v in TISSUE_INDEX.items()}

TISSUES = sorted(TISSUE_INDEX.values())

# Population mapping
POPULATION_MAP = {
    "AFR (African)": "afr",
    "AMI (Amish)": "ami",
    "AMR (Admixed American)": "amr",
    "ASJ (Ashkenazi Jewish)": "asj",
    "EAS (East Asian)": "eas",
    "FIN (Finnish)": "fin",
    "MID (Middle Eastern)": "mid",
    "NFE (Non-Finnish European)": "nfe",
    "SAS (South Asian)": "sas"
}

POPULATIONS = list(POPULATION_MAP.keys())

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
    descriptions[f"NFE.{pop_label}.mean.diff"] = f"Mean differences between NFE and {pop_label} reference populations"
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

# ─────────────────────────────────────────────────
# Sidebar Configuration
# ─────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Session UUID")

    # Display current UUID if exists
    if st.session_state.predictmp_uuid:
        st.info(f"{st.session_state.predictmp_uuid}")

    uuid_input = st.text_input(
        "UUID",
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        label_visibility="collapsed"
    )

    if st.button("Load UUID", use_container_width=True):
        if uuid_input:
            st.session_state.predictmp_uuid = uuid_input
            # Try to load results from saved CSV files
            results_dir = os.path.join(RESULTS_DIR, uuid_input)
            if os.path.exists(results_dir):
                # Find CSV files matching this UUID
                csv_files = [f for f in os.listdir(results_dir) if f.endswith('.csv')]
                if csv_files:
                    st.success(f"✅ Found {len(csv_files)} result file(s) for this UUID")
            st.rerun()

    st.divider()

    st.subheader("New Analysis")

    st.write("**Upload PrediXcan result (.txt / .csv)**")
    uploaded_file = st.file_uploader(
        "Upload file",
        type=["txt", "csv"],
        label_visibility="collapsed",
        accept_multiple_files=False
    )

    # Auto-generate UUID when file is uploaded (if no UUID exists)
    if uploaded_file and not st.session_state.predictmp_uuid:
        st.session_state.predictmp_uuid = str(uuid.uuid4())
        st.rerun()

    if uploaded_file:
        st.caption(f"{uploaded_file.name} ({uploaded_file.size / 1024 / 1024:.1f} MB)")

    st.write("**Tissue type**")
    tissue_type = st.selectbox(
        "Select tissue",
        TISSUES,
        label_visibility="collapsed"
    )

    st.write("**Reference population**")
    population = st.selectbox(
        "Select population",
        POPULATIONS,
        label_visibility="collapsed"
    )

    st.divider()

    run_button_disabled = not uploaded_file or not st.session_state.predictmp_uuid
    run_analysis = st.button(
        "Run PredictMP",
        use_container_width=True,
        type="primary",
        disabled=run_button_disabled,
        help="Upload file first" if run_button_disabled else "Click to run analysis"
    )

# ─────────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────────
st.title("PredictMP")
st.write("**Predict Multi-Population**")

# Show file selection status (hide when running analysis)
if uploaded_file and not run_analysis:
    st.info(f"PrediXcan result selected: {uploaded_file.name} ({uploaded_file.size / 1024 / 1024:.1f} MB)\n\nClick **Run PredictMP** button in the sidebar to start")
elif not uploaded_file and not run_analysis:
    st.info("Use the sidebar to upload analysis data, select tissue type and population, then click **Run PredictMP**.")

if run_analysis and uploaded_file:
    if rankcal is None:
        st.error("PredictAP package not found. Please check installation.")
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

        progress_text.write(f"Loading file and running PredictAP...")

        # Read uploaded file as DataFrame
        from io import StringIO
        stringio = StringIO(uploaded_file.getvalue().decode("utf8"))
        input_df = pd.read_csv(stringio, sep='\t')

        progress_text.write(f"Running PredictAP with tissue={tissue_code}, population={pop_code}...")

        # Call PredictAP rankcal (pass DataFrame, not file path)
        result_df = rankcal(
            data=input_df,
            tissue=tissue_code,
            population=pop_code
        )

        progress_text.success("Analysis complete!")

        # Save results to CSV for later reload
        results_dir = os.path.join(RESULTS_DIR, st.session_state.predictmp_uuid)
        os.makedirs(results_dir, exist_ok=True)
        result_csv = os.path.join(results_dir, "predictmp_results.csv")
        result_df.to_csv(result_csv, index=False)

        # Store results in session state
        st.session_state.predictmp_results = {
            "tissue": tissue_type,
            "tissue_code": tissue_code,
            "population": population,
            "population_code": pop_code,
            "uuid": st.session_state.predictmp_uuid,
            "dataframe": result_df,
        }

    except Exception as e:
        st.error(f"Analysis failed: {str(e)}")
        st.stop()

# Try to load results from disk if UUID is set but results not in memory
if st.session_state.predictmp_uuid and not st.session_state.predictmp_results:
    results_dir = os.path.join(RESULTS_DIR, st.session_state.predictmp_uuid)
    result_csv = os.path.join(results_dir, "predictmp_results.csv")
    if os.path.exists(result_csv):
        try:
            loaded_df = pd.read_csv(result_csv)
            st.session_state.predictmp_results = {
                "tissue": "Unknown",
                "population": "Unknown",
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

    # Title with timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    st.subheader(f"Predict_{results['tissue']}_{timestamp}.csv")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    n_subjects = df[["FID", "IID"]].drop_duplicates().shape[0]
    n_genes = df["gene"].nunique()
    median_percentile = df["percentile.rank"].median() if "percentile.rank" in df.columns else None
    ks_significant = (df["ks.test"] == "Sig.").sum() if "ks.test" in df.columns else 0

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
        st.metric("KS Significant genes", f"{ks_significant:,} / {n_genes:,}")

    # UUID info with red color
    st.markdown(f"<div style='background-color: #1e3a5f; padding: 15px; border-radius: 5px;'><span style='color: #ff4444; font-weight: bold;'>Session UUID: {results['uuid']}</span><br><span style='color: #88ccee;'>Save this to reload results later</span></div>", unsafe_allow_html=True)

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

    # Results message
    n_total = len(df)
    n_displayed = len(filtered_df)
    st.info(f"Showing {min(n_displayed, 5000):,} of {n_total:,} rows. Use filters above to narrow down, or download for the full dataset.")

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

    st.dataframe(
        filtered_df.head(5000),
        column_config=col_configs,
        use_container_width=True,
        hide_index=False
    )

    # Download button
    st.divider()
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    csv = df.to_csv(index=False)
    # Extract population name (remove description)
    pop_display = results['population'].split(' ')[0]  # e.g., "AFR (African)" -> "AFR"
    st.download_button(
        label="Download Results (CSV)",
        data=csv,
        file_name=f"Predict_{results['tissue']}_{pop_display}_{timestamp}.csv",
        mime="text/csv"
    )
