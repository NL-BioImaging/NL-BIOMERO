#!/bin/bash
#SBATCH --job-name=cellexpansion_advanced
#SBATCH --cpus-per-task=4
#SBATCH --time=00:15:00
#SBATCH --mem=5GB
#SBATCH --output=omero-%4j.log
set -eo pipefail

BIOMERO_ENV_FILE="${1:-}"
if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then
    . "$BIOMERO_ENV_FILE"
fi

echo "Running CellExpansionAdvanced w/ $IMAGE_PATH | $SINGULARITY_IMAGE | $DATA_PATH | $MAX_PIXELS $DISCARD_CELLS_WITHOUT_CYTOPLASM $NUCLEI_CHANNEL"

GPU_FLAG=""
case "${USE_GPU:-}" in
  true|True|TRUE|1|yes|Yes|YES|y|Y|on|On|ON) GPU_FLAG="--nv" ;;
esac

for mask in "$DATA_PATH"/data/in/*_nucmask*; do
    [ -e "$mask" ] || continue
    normalized="${mask/_nucmask/_nuclei_mask}"
    [ "$normalized" = "$mask" ] && continue
    [ -e "$normalized" ] || ln -s "$(basename "$mask")" "$normalized"
done

singularity run $GPU_FLAG $IMAGE_PATH/$SINGULARITY_IMAGE \
    --infolder $DATA_PATH/data/in \
    --outfolder $DATA_PATH/data/out \
    --gtfolder $DATA_PATH/data/gt \
    --local \
    --max-pixels $MAX_PIXELS \
    --discard-cells-without-cytoplasm $DISCARD_CELLS_WITHOUT_CYTOPLASM \
    --nuclei-channel ${NUCLEI_CHANNEL:-0} \
    -nmc

. "${SCRIPT_PATH:-$(dirname "$0")}/jobs/biomero_job_helpers.sh"
nl_biomero_verify_outputs
