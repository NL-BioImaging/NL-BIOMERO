#!/bin/bash
#SBATCH --job-name=nuclei_measurements
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --mem=32GB
#SBATCH --output=omero-%4j.log
set -eo pipefail

BIOMERO_ENV_FILE="${1:-}"
if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then
    . "$BIOMERO_ENV_FILE"
fi

echo "Running Nuclei Measurements Job w/ $IMAGE_PATH | $SINGULARITY_IMAGE | $DATA_PATH"

singularity run "$IMAGE_PATH/$SINGULARITY_IMAGE" \
    --infolder "$DATA_PATH/data/in" \
    --outfolder "$DATA_PATH/data/out" \
    --gtfolder "$DATA_PATH/data/gt" \
    --local \
    -nmc \
    --nuclei_mask_suffix "${NUCLEI_MASK_SUFFIX:-_Nuclei_Mask}" \
    --cells_mask_suffix "${CELLS_MASK_SUFFIX:-_Cells_Mask}" \
    --metric_channels "${METRIC_CHANNELS:-1,2,3}"

. "${SCRIPT_PATH:-$(dirname "$0")}/jobs/biomero_job_helpers.sh"
nl_biomero_verify_outputs

