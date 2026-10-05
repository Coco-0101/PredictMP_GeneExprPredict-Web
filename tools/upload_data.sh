#!/usr/bin/env bash
# Upload the data the web app needs (not in git) to cloud storage with rclone,
# so another host can download it. Re-running only sends changed files.
#
#   bash tools/upload_data.sh gdrive:PredictMP_GeneExprPredict-Web
#
# Uploads to <remote>/reference_data/{tissue,ks,result_table}/ and <remote>/ga_weights/.
# Paths below are this server's; override with env vars if they move.
set -euo pipefail

REMOTE=${1:?usage: bash tools/upload_data.sh <rclone-remote:path>}
REFERENCE_DATA=${REFERENCE_DATA:-/mnt/data_40T/betty0101/Project/PredictMP/data}
GA_WEIGHTS=${GA_WEIGHTS:-/mnt/data_40T/anywaycheng/UploadFile/GA/GA_Weight_DataBase}
OPTS=(--progress --transfers 16 --checksum --drive-chunk-size 32M)   # Drive finalizes each file slowly; many parallel transfers hide that wait

for d in tissue ks result_table; do
    [[ -d $REFERENCE_DATA/$d ]] || { echo "missing $REFERENCE_DATA/$d (run 08_build_package_data.py)" >&2; exit 1; }
done

echo "== PredictMP reference data -> $REMOTE/reference_data"
rclone copy "$REFERENCE_DATA" "$REMOTE/reference_data" "${OPTS[@]}" \
    --include "tissue/*.parquet" --include "ks/*.parquet" --include "result_table/*.parquet"

echo "== GA weight databases -> $REMOTE/ga_weights"
rclone copy "$GA_WEIGHTS" "$REMOTE/ga_weights" "${OPTS[@]}" --include "*.db"

echo "== verify"
rclone check "$REFERENCE_DATA" "$REMOTE/reference_data" --one-way \
    --include "tissue/*.parquet" --include "ks/*.parquet" --include "result_table/*.parquet"
rclone check "$GA_WEIGHTS" "$REMOTE/ga_weights" --one-way --include "*.db"
rclone size "$REMOTE"
