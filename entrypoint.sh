#!/bin/bash
set -euo pipefail

package_mount="${PREDICTAP_PACKAGE_MOUNT:-/pkg/PredictAP_python}"
app_path="${PREDICTAP_APP_PATH:-/app/app/main.py}"
streamlit_port="${STREAMLIT_PORT:-8501}"
max_upload_mb="${STREAMLIT_MAX_UPLOAD_MB:-500}"

if [[ ! -f "$package_mount/PredictAP/__init__.py" ]]; then
    echo "PredictAP package not found at $package_mount" >&2
    echo "Check PREDICTAP_PACKAGE_DIR in .env." >&2
    exit 1
fi

if [[ ! -f "$app_path" ]]; then
    echo "Streamlit app not found at $app_path" >&2
    exit 1
fi

# Match the old conda/PYTHONPATH launch without modifying the mounted package.
export PYTHONPATH="$package_mount:/app/app${PYTHONPATH:+:$PYTHONPATH}"

exec python -m streamlit run "$app_path" \
    --server.port="$streamlit_port" \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.maxUploadSize="$max_upload_mb" \
    --client.toolbarMode=auto \
    --browser.gatherUsageStats=false
