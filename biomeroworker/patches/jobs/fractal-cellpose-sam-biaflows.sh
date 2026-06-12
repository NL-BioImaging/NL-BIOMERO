#!/bin/bash
#SBATCH --job-name=fractal-cellpose-sam-biaflows
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --mem=32GB
#SBATCH --output=omero-%4j.log
set -eo pipefail

BIOMERO_ENV_FILE="${1:-}"
if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then
    . "$BIOMERO_ENV_FILE"
fi

echo "Running Fractal Cellpose SAM BIAFLOWS Job w/ $IMAGE_PATH | $SINGULARITY_IMAGE | $DATA_PATH"

GPU_FLAG=""
case "${USE_GPU:-}" in
  true|True|TRUE|1|yes|Yes|YES|y|Y|on|On|ON) GPU_FLAG="--nv" ;;
esac

singularity run $GPU_FLAG "$IMAGE_PATH/$SINGULARITY_IMAGE" \
    --infolder "$DATA_PATH/data/in" \
    --outfolder "$DATA_PATH/data/out" \
    --gtfolder "$DATA_PATH/data/gt" \
    --local \
    -nmc \
    --nuc_channel "${NUC_CHANNEL:-0}" \
    --diameter "${DIAMETER:-200}" \
    --prob_threshold "${PROB_THRESHOLD:-0.5}" \
    --flow_threshold "${FLOW_THRESHOLD:-0.4}" \
    --min_size "${MIN_SIZE:-15}" \
    --use_gpu "${USE_GPU:-False}" \
    --cp_model "${CP_MODEL:-cpsam}" \
    --label_name "${LABEL_NAME:-fractal_cellpose_sam_segmentation}" \
    --exclude_on_edges "${EXCLUDE_ON_EDGES:-False}" \
    --do_3D "${DO_3D:-False}" \
    --anisotropy "${ANISOTROPY:-1.0}" \
    --normalize "${NORMALIZE:-True}"

. "${SCRIPT_PATH:-$(dirname "$0")}/jobs/biomero_job_helpers.sh"
nl_biomero_verify_outputs

