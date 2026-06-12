#!/bin/bash
#SBATCH --job-name=simple-zarr-plate-processor
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --mem=32GB
#SBATCH --output=omero-%4j.log
set -eo pipefail

BIOMERO_ENV_FILE="${1:-}"
if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then
    . "$BIOMERO_ENV_FILE"
fi

echo "Running Simple Zarr Plate Processor Job w/ $IMAGE_PATH | $SINGULARITY_IMAGE | $DATA_PATH"

singularity run "$IMAGE_PATH/$SINGULARITY_IMAGE" \
    --infolder "$DATA_PATH/data/in" \
    --outfolder "$DATA_PATH/data/out" \
    --gtfolder "$DATA_PATH/data/gt" \
    --local \
    -nmc \
    --gaussian_sigma "${GAUSSIAN_SIGMA:-1.0}" \
    --do_max_proj "${DO_MAX_PROJ:-True}" \
    --normalize_contrast "${NORMALIZE_CONTRAST:-True}" \
    --output_name "${OUTPUT_NAME:-processed}" \
    --max_workers "${MAX_WORKERS:-4}"

. "${SCRIPT_PATH:-$(dirname "$0")}/jobs/biomero_job_helpers.sh"
nl_biomero_verify_outputs

