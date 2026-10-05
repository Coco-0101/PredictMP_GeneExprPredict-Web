#!/usr/bin/env bash
# Collect everything another host needs to run the web app into one folder.
#
#   bash tools/make_deploy_bundle.sh [OUT_DIR] [--no-image]
#
# OUT_DIR defaults to ../PredictMP_GeneExprPredict-Web_bundle_<date>.
# Paths below are this server's; override with env vars if they move.
set -euo pipefail

WEB_DIR=$(cd "$(dirname "$0")/.." && pwd)
REFERENCE_DATA=${REFERENCE_DATA:-/mnt/data_40T/betty0101/Project/PredictMP/data}
GA_WEIGHTS=${GA_WEIGHTS:-/mnt/data_40T/anywaycheng/UploadFile/GA/GA_Weight_DataBase}
IMAGE=${IMAGE:-predictmp_geneexprpredict-web:latest}

OUT=$WEB_DIR/../PredictMP_GeneExprPredict-Web_bundle_$(date +%Y%m%d)
WITH_IMAGE=1
for arg in "$@"; do
    case $arg in
        --no-image) WITH_IMAGE=0 ;;
        *)          OUT=$arg ;;
    esac
done

if [[ -e $OUT ]]; then
    echo "$OUT already exists; remove it or pass another OUT_DIR" >&2
    exit 1
fi
mkdir -p "$OUT"/reference_data/result_table "$OUT"/ga_weights
log() { echo "[$(date '+%T')] $*"; }

log "1/4 web app source (committed HEAD, no .env / sample_data)"
git -C "$WEB_DIR" archive --format=tar.gz --prefix=PredictMP_GeneExprPredict-Web/ -o "$OUT/web_app.tar.gz" HEAD

log "2/4 PredictAP reference data (tissue/, result_table/*.parquet, ks/)"
for d in tissue ks; do
    [[ -d $REFERENCE_DATA/$d ]] || { echo "missing $REFERENCE_DATA/$d (run 08_build_package_data.py)" >&2; exit 1; }
done
cp -r "$REFERENCE_DATA/tissue" "$REFERENCE_DATA/ks" "$OUT/reference_data/"
cp "$REFERENCE_DATA"/result_table/result_table_*.parquet "$OUT/reference_data/result_table/"

log "3/4 GA weight databases"
cp "$GA_WEIGHTS"/*.db "$OUT/ga_weights/"

if (( WITH_IMAGE )); then
    log "4/4 Docker image $IMAGE"
    docker save "$IMAGE" | gzip > "$OUT/docker_image.tar.gz"
else
    log "4/4 Docker image skipped (--no-image); build it on the new host"
fi

log "checksums"
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)

du -sh "$OUT"/* | sed 's/^/  /'
log "done -> $OUT   (see README: 部署到另一台主機)"
