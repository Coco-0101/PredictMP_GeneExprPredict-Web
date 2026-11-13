"""
measure_upload.py
------------------
Run this on your LOCAL Windows machine (not on the remote Linux server).
It drives a real browser to open the PredictMP web app, upload a VCF file,
and measures how long the browser-side upload actually takes -- then
optionally waits for prediction to finish and reports total time.

Every run also appends a row to a local CSV log file (default:
upload_log.csv, next to this script) so you can compare timings across
multiple runs later, even after closing the terminal. The row includes
the Session UUID, so you can match a log entry back to its results in
the web app (paste the UUID into "Load UUID" in the sidebar).

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
    --log-file     Path to the CSV log file (default: upload_log.csv next to
                   this script). Rows are appended, one per run.
"""

import argparse
import csv
import datetime
import os
import re
import time

from playwright.sync_api import sync_playwright

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def append_log(log_path: str, row: dict):
    """Append one run's timing to a CSV log, writing the header if new."""
    fieldnames = [
        "timestamp", "url", "file", "file_size_mb", "session_uuid",
        "upload_seconds", "predict_seconds", "total_seconds", "status",
    ]
    file_exists = os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="e.g. http://192.168.1.50:8503")
    ap.add_argument("--file", required=True, help="Local path to the VCF file to upload")
    ap.add_argument("--headless", action="store_true", help="Run without a visible browser window")
    ap.add_argument("--wait-predict", action="store_true", help="Also wait for prediction to complete")
    ap.add_argument(
        "--log-file",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "upload_log.csv"),
        help="CSV file to append timing results to (default: upload_log.csv next to this script)",
    )
    args = ap.parse_args()

    file_size_mb = os.path.getsize(args.file) / 1024 / 1024

    log_row = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "url": args.url,
        "file": args.file,
        "file_size_mb": f"{file_size_mb:.1f}",
        "session_uuid": "",
        "upload_seconds": "",
        "predict_seconds": "",
        "total_seconds": "",
        "status": "started",
    }

    try:
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
            log_row["upload_seconds"] = f"{upload_seconds:.1f}"
            log_row["status"] = "uploaded"
            print(f"\n✅ Upload complete in {upload_seconds:.1f}s "
                  f"({upload_seconds/60:.1f} min)\n")

            # Grab the Session UUID from the sidebar (shown in an info box
            # right below "Session UUID") so it's saved alongside the
            # timing -- lets you match a log row back to its results later.
            try:
                uuid_locator = page.get_by_text(UUID_PATTERN)
                uuid_locator.first.wait_for(state="visible", timeout=15_000)
                match = UUID_PATTERN.search(uuid_locator.first.inner_text())
                session_uuid = match.group(0) if match else ""
            except Exception:
                session_uuid = ""
            log_row["session_uuid"] = session_uuid
            if session_uuid:
                print(f"Session UUID: {session_uuid}\n")
            else:
                print("Session UUID: (could not be read from the page)\n")

            # If auto-run already kicked in, "Processing Progress" will
            # already be visible -- in that case do NOT also click Run
            # Prediction: the button can still appear clickable in the DOM
            # while the server is mid-run (Streamlit doesn't repaint
            # widget-disabled state until the script finishes), so clicking
            # it here would queue a second, overlapping analysis run.
            already_running = page.get_by_text("Processing Progress", exact=False).count() > 0

            # exact=True avoids Playwright's substring matching from also
            # catching the sidebar's "Help for Auto-run prediction after
            # upload completes" tooltip button (its aria-label happens to
            # contain the substring "run prediction").
            run_button = page.get_by_role("button", name="Run Prediction", exact=True)
            if not already_running and run_button.count() > 0 and run_button.is_visible() and run_button.is_enabled():
                print("[5/5] Auto-run not detected yet -- clicking 'Run Prediction'...")
                run_button.click()
            else:
                print("[5/5] Auto-run already started -- not clicking Run Prediction again.")

            if args.wait_predict:
                print("Waiting for prediction to finish (this can take a while for large files)...")
                page.get_by_text("Prediction complete!", exact=False).wait_for(state="visible", timeout=0)
                t_predict_done = time.time()
                total_seconds = t_predict_done - t_start
                predict_seconds = t_predict_done - t_upload_done
                log_row["predict_seconds"] = f"{predict_seconds:.1f}"
                log_row["total_seconds"] = f"{total_seconds:.1f}"
                log_row["status"] = "completed"
                print(f"\n✅ Prediction complete. "
                      f"Total time (upload + prediction): {total_seconds:.1f}s "
                      f"({total_seconds/60:.1f} min)\n")

            if not args.headless:
                print("Browser left open -- close it manually, or press Enter to close now.")
                input()

            browser.close()

    except Exception as e:
        log_row["status"] = f"error: {e}"
        raise
    finally:
        append_log(args.log_file, log_row)
        print(f"Logged this run to: {args.log_file}")


if __name__ == "__main__":
    main()
