#!/bin/bash
#SBATCH --job-name=spotcounting
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --mem=16GB
#SBATCH --output=omero-%4j.log
set -eo pipefail

BIOMERO_ENV_FILE="${1:-}"
if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then
    . "$BIOMERO_ENV_FILE"
fi

echo "Running SpotCounting Job w/ $IMAGE_PATH | $SINGULARITY_IMAGE | $DATA_PATH"

singularity run "$IMAGE_PATH/$SINGULARITY_IMAGE" \
    --infolder "$DATA_PATH/data/in" \
    --outfolder "$DATA_PATH/data/out" \
    --gtfolder "$DATA_PATH/data/gt" \
    --local \
    -nmc \
    --cell_mask_suffix "${CELL_MASK_SUFFIX:-_C}" \
    --aggregate_mask_suffix "${AGGREGATE_MASK_SUFFIX:-_A}" \
    --column_name_counts "${COLUMN_NAME_COUNTS:-counts}" \
    --column_name_cells "${COLUMN_NAME_CELLS:-cells}"

. "${SCRIPT_PATH:-$(dirname "$0")}/jobs/biomero_job_helpers.sh"
nl_biomero_verify_outputs

