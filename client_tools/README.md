# Client-side Tools

Scripts in this folder run on **your local machine** (e.g. Windows), not on the server.
They are not included in the Docker image (see `Dockerfile` — only `app/` is copied).

## measure_upload.py

Drives a real browser to upload a VCF file to the PredictAP web app and measures the
actual browser-side upload time (file selected → server confirms receipt), plus
optionally the total time including prediction.

### Setup (Windows PowerShell)

```powershell
pip install playwright
playwright install chromium
```

### Usage

```powershell
python measure_upload.py --url http://<server-ip>:8503 --file "C:\path\to\big.vcf.gz"

# Also wait for prediction to finish and report total time:
python measure_upload.py --url http://<server-ip>:8503 --file "C:\path\to\big.vcf.gz" --wait-predict

# Run without opening a visible browser window:
python measure_upload.py --url http://<server-ip>:8503 --file "C:\path\to\big.vcf.gz" --headless
```

Replace `<server-ip>` with however you normally reach the web app from your Windows
machine (IP address, hostname, or SSH tunnel address).

### Logging

Every run appends one row to `upload_log.csv` (created next to this script) with
columns: `timestamp, url, file, file_size_mb, session_uuid, upload_seconds,
predict_seconds, total_seconds, status`. This lets you compare timings across
multiple runs even after closing the terminal, and `session_uuid` lets you match
a log row back to its results in the app (paste it into "Load UUID" in the sidebar).

```powershell
# Use a custom log file path:
python measure_upload.py --url http://<server-ip>:8503 --file "C:\path\to\big.vcf.gz" --wait-predict --log-file "C:\logs\ga_uploads.csv"
```
