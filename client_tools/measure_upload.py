"""
measure_upload.py
------------------
Run this on your LOCAL Windows machine (not on the remote Linux server).
It drives a real browser to open the PredictAP web app, upload a VCF file,
and measures how long the browser-side upload actually takes -- then
optionally waits for prediction to finish and reports total time.

Setup (on Windows, PowerShell or cmd):
    pip install playwright
    playwright install chromium

Usage:
    python measure_upload.py --url http://<server-ip>:8503 --file "C:\\path\\to\\big.vcf.gz"

Options:
    --url          Web app URL (required)
    --file         Path to the VCF file to upload, on THIS machine (required)
    --headless     Run without opening a visible browser window
    --wait-predict Also wait for "Prediction complete!" and report total time
                   (only useful if Auto-run is enabled in the app sidebar)
"""

import argparse
import time

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="e.g. http://192.168.1.50:8503")
    ap.add_argument("--file", required=True, help="Local path to the VCF file to upload")
    ap.add_argument("--headless", action="store_true", help="Run without a visible browser window")
    ap.add_argument("--wait-predict", action="store_true", help="Also wait for prediction to complete")
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()

        print(f"[1/5] Opening {args.url} ...")
        page.goto(args.url, wait_until="networkidle")

        # This app has two pages under st.navigation (see app/main.py).
        # "PredictMP Analysis" is listed first and loads by default at the
        # root URL, so we must explicitly switch to the GA page via the
        # sidebar nav link before touching the file uploader -- otherwise
        # we'd upload into the wrong page's uploader.
        print("[2/5] Switching to GA-Calibrated Gene Expression Prediction page...")
        ga_nav_link = page.get_by_role("link", name="GA-Calibrated Gene Expression Prediction")
        ga_nav_link.wait_for(state="visible", timeout=15_000)
        ga_nav_link.click()
        page.wait_for_load_state("networkidle")

        # Streamlit's file_uploader renders a real <input type="file">.
        # Scope to the GA page's own uploader by anchoring on its label
        # text, in case both pages' DOM are ever present at once.
        file_input = page.locator('input[type="file"]').first
        file_input.wait_for(state="attached", timeout=30_000)

        print(f"[3/5] Selecting file: {args.file}")
        t_start = time.time()
        file_input.set_input_files(args.file)

        # Wait for the app's own confirmation that the file was fully
        # received server-side -- it shows "VCF file selected: **name**"
        # (or, if auto-run is on, the Processing Progress section appears
        # almost immediately after, so watch for either).
        print("[4/5] Waiting for server to confirm upload is complete...")
        page.get_by_text("VCF file selected", exact=False).or_(
            page.get_by_text("Processing Progress", exact=False)
        ).first.wait_for(state="visible", timeout=0)  # no timeout -- large files can take a while

        t_upload_done = time.time()
        upload_seconds = t_upload_done - t_start
        print(f"\n✅ Upload complete in {upload_seconds:.1f}s "
              f"({upload_seconds/60:.1f} min)\n")

        # If auto-run isn't on, click Run Prediction ourselves
        run_button = page.get_by_role("button", name="Run Prediction")
        if run_button.is_visible() and run_button.is_enabled():
            print("[5/5] Auto-run not detected yet -- clicking 'Run Prediction'...")
            run_button.click()

        if args.wait_predict:
            print("Waiting for prediction to finish (this can take a while for large files)...")
            page.get_by_text("Prediction complete!", exact=False).wait_for(state="visible", timeout=0)
            t_predict_done = time.time()
            print(f"\n✅ Prediction complete. "
                  f"Total time (upload + prediction): {t_predict_done - t_start:.1f}s "
                  f"({(t_predict_done - t_start)/60:.1f} min)\n")

        if not args.headless:
            print("Browser left open -- close it manually, or press Enter to close now.")
            input()

        browser.close()


if __name__ == "__main__":
    main()
