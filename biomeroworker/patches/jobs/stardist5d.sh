#!/bin/bash
#SBATCH --job-name=stardist5d
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --mem=8GB
#SBATCH --output=omero-%4j.log
set -eo pipefail

echo "Running StarDist5D Job w/ $IMAGE_PATH | $SINGULARITY_IMAGE | $DATA_PATH | $STARDIST_PROB_T $STARDIST_NMS_T $STARDIST_NORM_PERC_LOW $STARDIST_NORM_PERC_HIGH $NUC_CHANNEL $TIME_SERIES $Z_SLICES $SCALE_FACTOR $TILE_SIZE_X $TILE_SIZE_Y $BLOCK_OVERLAP $AUTO_TILING"

GPU_FLAG=""
case "${USE_GPU:-}" in
  true|True|TRUE|1|yes|Yes|YES|y|Y|on|On|ON) GPU_FLAG="--nv" ;;
esac

singularity run $GPU_FLAG $IMAGE_PATH/$SINGULARITY_IMAGE \
    --infolder $DATA_PATH/data/in \
    --outfolder $DATA_PATH/data/out \
    --gtfolder $DATA_PATH/data/gt \
    --local \
    --stardist_prob_t $STARDIST_PROB_T \
    --stardist_nms_t $STARDIST_NMS_T \
    --stardist_norm_perc_low $STARDIST_NORM_PERC_LOW \
    --stardist_norm_perc_high $STARDIST_NORM_PERC_HIGH \
    --nuc_channel $NUC_CHANNEL \
    --time_series $TIME_SERIES \
    --z_slices $Z_SLICES \
    --scale_factor $SCALE_FACTOR \
    --tile_size_x $TILE_SIZE_X \
    --tile_size_y $TILE_SIZE_Y \
    --block_overlap $BLOCK_OVERLAP \
    --auto_tiling $AUTO_TILING \
    -nmc

. "$(dirname "$0")/biomero_job_helpers.sh"
nl_biomero_verify_outputs
