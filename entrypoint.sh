#!/bin/bash
set -euo pipefail

app_path="${PREDICTMP_APP_PATH:-/app/app/main.py}"
streamlit_port="${STREAMLIT_PORT:-8501}"
max_upload_mb="${STREAMLIT_MAX_UPLOAD_MB:-10240}"

if ! python -c "import PredictMP" 2>/dev/null; then
    echo "PredictMP package is not installed in the image." >&2
    echo "Build the wheel into wheels/ and rebuild (see README)." >&2
    exit 1
fi

if [[ ! -f "$app_path" ]]; then
    echo "Streamlit app not found at $app_path" >&2
    exit 1
fi

export PYTHONPATH="/app/app${PYTHONPATH:+:$PYTHONPATH}"

# Delete session folders older than RESULTS_RETENTION_DAYS (default 7), once an hour
(
    cd /app/app
    while true; do
        python -m core.storage || true
        sleep 3600
    done
) &

exec python -m streamlit run "$app_path" \
    --server.port="$streamlit_port" \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.maxUploadSize="$max_upload_mb" \
    --client.toolbarMode=auto \
    --browser.gatherUsageStats=false
