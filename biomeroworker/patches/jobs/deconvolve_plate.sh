#!/bin/bash
#SBATCH --job-name=deconvolve_plate
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH --mem=64GB
#SBATCH --output=omero-%4j.log
set -eo pipefail

BIOMERO_ENV_FILE="${1:-}"
if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then
    . "$BIOMERO_ENV_FILE"
fi

echo "Running Deconvolve Plate Job w/ $IMAGE_PATH | $SINGULARITY_IMAGE | $DATA_PATH"

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
    --method "${METHOD:-ci_rl}" \
    --iterations "${ITERATIONS:-150}" \
    --convergence "${CONVERGENCE:-auto}" \
    --rel_threshold "${REL_THRESHOLD:-0.005}" \
    --overrule_image_metadata "${OVERRULE_IMAGE_METADATA:-False}" \
    --na "${NA:-1.4}" \
    --emission_wl "${EMISSION_WL:-520}" \
    --pixel_size_xy "${PIXEL_SIZE_XY:-65.0}" \
    --pixel_size_z "${PIXEL_SIZE_Z:-200.0}" \
    --microscope_type "${MICROSCOPE_TYPE:-confocal}" \
    --excitation_wl "${EXCITATION_WL:-488}" \
    --pinhole_airy "${PINHOLE_AIRY:-1.0}" \
    --refractive_index "${REFRACTIVE_INDEX:-oil (1.515)}" \
    --sample_ri "${SAMPLE_RI:-prolong gold (1.47)}" \
    --projection "${PROJECTION:-none}" \
    --output_format "${OUTPUT_FORMAT:-ome-tiff}" \
    --streaming "${STREAMING:-auto}" \
    --tile_limits "${TILE_LIMITS:-1024,64}" \
    --streaming_threshold_gb "${STREAMING_THRESHOLD_GB:-2.0}" \
    --scene "${SCENE:-auto}" \
    --hcs_field "${HCS_FIELD:-auto}" \
    --benchmark "${BENCHMARK:-False}" \
    --bench_crop "${BENCH_CROP:-False}" \
    --compute_metrics "${COMPUTE_METRICS:-False}" \
    --tv_lambda "${TV_LAMBDA:-0.0001}" \
    --damping "${DAMPING:-none}" \
    --two_d_mode "${TWO_D_MODE:-auto}" \
    --sparse_hessian_weight "${SPARSE_HESSIAN_WEIGHT:-0.6}" \
    --sparse_hessian_reg "${SPARSE_HESSIAN_REG:-0.98}" \
    --background "${BACKGROUND:-auto}" \
    --offset "${OFFSET:-auto}" \
    --prefilter_sigma "${PREFILTER_SIGMA:-0.0}" \
    --start "${START:-auto}" \
    --device "${DEVICE:-auto}" \
    --two_d_wf_aggressiveness "${TWO_D_WF_AGGRESSIVENESS:-Balanced}" \
    --two_d_wf_bg_radius_um "${TWO_D_WF_BG_RADIUS_UM:-0.5}" \
    --two_d_wf_bg_scale "${TWO_D_WF_BG_SCALE:-1.0}"

. "${SCRIPT_PATH:-$(dirname "$0")}/jobs/biomero_job_helpers.sh"
nl_biomero_verify_outputs

