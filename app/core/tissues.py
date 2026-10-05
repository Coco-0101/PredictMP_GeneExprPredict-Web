"""GTEx v8 tissue codes and gnomAD v4.1 reference populations used by PredictAP."""

# x1..x49 = GTEx v8 tissues in alphabetical order (same order as PredictMP/data/tissue_index.txt)
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
TISSUE_NAME_TO_CODE = {v: k for k, v in TISSUE_INDEX.items()}
TISSUES = sorted(TISSUE_INDEX.values())

# Display label -> PredictAP population code
POPULATION_MAP = {
    "AFR (African)": "afr",
    "AMI (Amish)": "ami",
    "AMR (Admixed American)": "amr",
    "ASJ (Ashkenazi Jewish)": "asj",
    "EAS (East Asian)": "eas",
    "FIN (Finnish)": "fin",
    "MID (Middle Eastern)": "mid",
    "NFE (Non-Finnish European)": "nfe",
    "SAS (South Asian)": "sas",
}
POPULATIONS = list(POPULATION_MAP)
