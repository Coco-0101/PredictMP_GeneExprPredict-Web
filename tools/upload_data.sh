#!/usr/bin/env bash
# Upload the data the web app needs (not in git) to cloud storage with rclone,
# so another host can download it.
#
#   bash tools/upload_data.sh gdrive:PredictMP_GeneExprPredict-Web
#   POPS="eas nfe" bash tools/upload_data.sh gdrive:...    # only some populations' tissue tars
#
# Layout on the remote:
#   reference_data/ks/*.parquet, reference_data/result_table/*.parquet   (small, file by file)
#   reference_data_tar/tissue_<pop>.tar                                  (49 parquet files per population)
#   ga_weights/*.db
#
# Google Drive is slow with many medium files (~1 MB/s) but fast with large ones (~20 MB/s),
# so tissue/ is streamed as one tar per population: no local tar is written, and the
# remote MD5 is checked against the MD5 of the streamed bytes. Local files are only read.
# Paths below are this server's; override with env vars if they move.
set -euo pipefail

REMOTE=${1:?usage: bash tools/upload_data.sh <rclone-remote:path>}
REFERENCE_DATA=${REFERENCE_DATA:-/mnt/data_40T/betty0101/Project/PredictMP/data}
GA_WEIGHTS=${GA_WEIGHTS:-/mnt/data_40T/anywaycheng/UploadFile/GA/GA_Weight_DataBase}
POPS=${POPS:-afr ami amr asj eas fin mid nfe sas}
OPTS=(--progress --checksum --drive-chunk-size 64M)

for d in tissue ks result_table; do
    [[ -d $REFERENCE_DATA/$d ]] || { echo "missing $REFERENCE_DATA/$d (run 08_build_package_data.py)" >&2; exit 1; }
done

echo "== ks/, result_table/ -> $REMOTE/reference_data"
rclone copy "$REFERENCE_DATA" "$REMOTE/reference_data" "${OPTS[@]}" --transfers 8 \
    --include "ks/*.parquet" --include "result_table/*.parquet"
rclone check "$REFERENCE_DATA" "$REMOTE/reference_data" --one-way \
    --include "ks/*.parquet" --include "result_table/*.parquet"

echo "== tissue/ -> $REMOTE/reference_data_tar (one tar per population)"
md5_tmp=$(mktemp)
trap 'rm -f "$md5_tmp"' EXIT
for pop in $POPS; do
    name=tissue_$pop.tar
    mapfile -t files < <(cd "$REFERENCE_DATA" && ls tissue/"${pop}"_x*.parquet | sort -V)
    echo "[$(date +%T)] $name: ${#files[@]} files"
    (cd "$REFERENCE_DATA" && tar --sort=name -cf - "${files[@]}") \
        | tee >(md5sum | cut -d' ' -f1 > "$md5_tmp") \
        | rclone rcat "$REMOTE/reference_data_tar/$name" --drive-chunk-size 64M
    sleep 2
    local_md5=$(cat "$md5_tmp")
    remote_md5=$(rclone md5sum "$REMOTE/reference_data_tar/$name" | cut -d' ' -f1)
    if [[ "$local_md5" != "$remote_md5" ]]; then
        echo "MD5 mismatch for $name: local=$local_md5 remote=$remote_md5" >&2
        exit 1
    fi
    echo "[$(date +%T)] $name OK md5=$local_md5"
done

echo "== GA weight databases -> $REMOTE/ga_weights"
rclone copy "$GA_WEIGHTS" "$REMOTE/ga_weights" "${OPTS[@]}" --transfers 6 --include "*.db"
rclone check "$GA_WEIGHTS" "$REMOTE/ga_weights" --one-way --include "*.db"

rclone size "$REMOTE"
