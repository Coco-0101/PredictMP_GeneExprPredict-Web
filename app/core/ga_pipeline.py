"""
GA-based gene expression prediction pipeline for the web UI.
Wraps VCF -> plink2 dosage -> ga_predict -> results.

Outputs in output_dir:
    ga_predicted_expression.csv   FID, IID, <gene_1>, <gene_2>, ...
    ga_summary.csv                one row per gene, QC metrics + status
"""

import os
import subprocess
import tempfile
import shutil
import sqlite3
from typing import Optional, Callable, Tuple

import pandas as pd

from core import ga_predict

OUTPUT_PREFIX = "ga"
EXPR_FILE = f"{OUTPUT_PREFIX}_predicted_expression.csv"
SUMMARY_FILE = f"{OUTPUT_PREFIX}_summary.csv"


class GAPipeline:
    """Orchestrates: VCF -> plink2 dosage -> ga_predict -> results"""

    def __init__(self, weights_db: str, plink2_cmd: str = "plink2", weight_col: str = "GA_W"):
        self.weights_db = weights_db
        self.plink2_cmd = plink2_cmd
        self.weight_col = weight_col
        self._verify_weights_db()

    def _verify_weights_db(self):
        if not os.path.exists(self.weights_db):
            raise FileNotFoundError(f"Weights DB not found: {self.weights_db}")
        try:
            conn = sqlite3.connect(self.weights_db)
            conn.execute("SELECT 1 FROM weights LIMIT 1")
            conn.close()
        except Exception as e:
            raise ValueError(f"Cannot read weights table from {self.weights_db}: {e}")

    def run(
        self,
        vcf_path: str,
        output_dir: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        assume_aligned: bool = False,
    ) -> Tuple[str, str]:
        """
        Run full pipeline: VCF -> dosage -> prediction.

        Args:
            vcf_path: Input VCF file path
            output_dir: Output directory (will be created)
            progress_callback: Optional callback(message, percentage) for progress updates
            assume_aligned: Skip allele flip check

        Returns:
            Tuple of (expression_csv_path, summary_csv_path)
        """
        os.makedirs(output_dir, exist_ok=True)
        # Use a unique tmp dir per invocation (not a fixed "tmp" name) so
        # that overlapping/duplicate runs on the same UUID (e.g. from a
        # stray double-trigger) can never delete files out from under
        # each other via the cleanup step below.
        tmp_dir = tempfile.mkdtemp(prefix="tmp_", dir=output_dir)

        try:
            # Step 1: Extract SNP list from weights DB
            self._progress(progress_callback, "Extracting SNP list from weights...", 10)
            snp_list_path = os.path.join(tmp_dir, "snps_to_extract.txt")
            self._extract_snp_list(snp_list_path)

            # Step 2: Run plink2 to compute dosage
            self._progress(progress_callback, "Computing SNP dosage with plink2...", 30)
            dosage_raw_path = os.path.join(tmp_dir, "dosage_matrix.raw")
            self._run_plink2(vcf_path, snp_list_path, dosage_raw_path)

            # Step 3: Predict expression
            self._progress(progress_callback, "Computing predicted expression...", 70)
            expr_prefix = os.path.join(output_dir, OUTPUT_PREFIX)
            self._run_prediction(dosage_raw_path, expr_prefix, assume_aligned)

            # Step 4: Finalize
            self._progress(progress_callback, "Generating summary report...", 95)
            expr_path = f"{expr_prefix}_predicted_expression.csv"
            summary_path = f"{expr_prefix}_summary.csv"

            if not os.path.exists(expr_path) or not os.path.exists(summary_path):
                raise RuntimeError("Prediction output files not created")

            self._progress(progress_callback, "Complete", 100)
            return expr_path, summary_path

        except Exception as e:
            raise RuntimeError(f"Pipeline failed: {e}") from e
        finally:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _progress(self, callback: Optional[Callable], message: str, pct: int):
        """Helper to emit progress updates"""
        if callback:
            callback(message, pct)

    def _extract_snp_list(self, output_path: str):
        """Extract all SNPs with non-zero weights from weights.db"""
        conn = sqlite3.connect(self.weights_db)
        snps = pd.read_sql(
            f"SELECT DISTINCT rsid FROM weights WHERE {self.weight_col} != 0;",
            conn
        )
        conn.close()

        if snps.empty:
            raise ValueError("No non-zero weights found in database")

        snps["rsid"].to_csv(output_path, index=False, header=False)

    def _run_plink2(self, vcf_path: str, snp_list_path: str, output_raw_path: str):
        """Run plink2 to extract dosage matrix"""
        output_prefix = output_raw_path.replace(".raw", "")
        cmd = [
            self.plink2_cmd,
            "--vcf", vcf_path,
            "--extract", snp_list_path,
            "--export", "A",
            "--out", output_prefix,
            "--threads", "4",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"plink2 failed: {result.stderr}")

        if not os.path.exists(output_raw_path):
            raise RuntimeError(f"plink2 did not produce {output_raw_path}")

    def _run_prediction(self, dosage_raw_path: str, output_prefix: str, assume_aligned: bool):
        """Run the ga_predict computation and write both output files"""
        weights_df, has_allele_info = ga_predict.load_weights(
            self.weights_db, "weights", self.weight_col
        )
        gene_summary_df = ga_predict.load_gene_summary(self.weights_db, "gene_summary")
        dosage, counted_allele, fid_iid = ga_predict.load_dosage_raw(dosage_raw_path)

        pred_df, w_annotated = ga_predict.predict(
            weights_df, has_allele_info, dosage, counted_allele, assume_aligned
        )

        # Write wide-format predicted expression
        wide = pred_df.T
        wide.index.name = "IID"
        wide = wide.reset_index().merge(fid_iid.drop_duplicates("IID"), on="IID", how="left")
        front = ["FID", "IID"]
        wide = wide[front + [c for c in wide.columns if c not in front]]
        expr_path = f"{output_prefix}_predicted_expression.csv"
        wide.to_csv(expr_path, index=False)

        # Write summary
        summary = ga_predict.build_summary(weights_df, w_annotated, pred_df, gene_summary_df)
        summary_path = f"{output_prefix}_summary.csv"
        summary.to_csv(summary_path, index=False)


def load_results(expr_path: str, summary_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load prediction results from CSV files"""
    expr_df = pd.read_csv(expr_path)
    summary_df = pd.read_csv(summary_path)
    return expr_df, summary_df
