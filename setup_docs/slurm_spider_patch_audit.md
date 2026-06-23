# BIOMERO Slurm Patch Audit

This branch separates generally useful BIOMERO Slurm extensions from Spider-
specific deployment policy.

## Generally useful extensions

- `7z`/`7za` fallback and idempotent remote unpack directories.
- Required `slurm_data_bind_path` validation before submitting container jobs.
- Per-job environment files for `sbatch` scripts, because remote Slurm jobs may
  not inherit SSH session environment variables.
- Normalizing cloned and descriptor-generated job scripts so hard-coded
  `singularity run --nv` becomes conditional on `USE_GPU`.
- Removing hard-coded `#SBATCH --gres` from cloned workflow scripts so GPU
  resources are controlled centrally.
- Adding missing local job scripts for exposed workflows that upstream
  `slurm-scripts` does not ship.
- Running image pulls/builds as foreground Slurm jobs with project-local
  Apptainer cache/temp directories, bounded CPU/memory, and real exit codes.
- Verifying workflow output directories before BIOMERO enters import, so
  container tracebacks or empty outputs fail early instead of hanging at 90%.
- Focused per-workflow CPU/memory/time defaults in `slurm-config.ini`.

## Spider-specific policy

- SSH/rendering variables use `SPIDER_USER` and `SPIDER_PROJECT`.
- Runtime Slurm paths point at `/project/biomero/Share/biomero/...`.
- GPU-native workflows default to `use_gpu=true` through
  `BIOMERO_FORCE_GPU_WORKFLOWS`.
- Effective GPU jobs default to `gpu_a100_mig` with
  `BIOMERO_GPU_GRES=gpu:a100_3g.20gb:1`. Heavy workflows can override this,
  for example `deconvolve_plate` clears inherited GRES with
  `BIOMERO_GPU_GRES_DECONVOLVE_PLATE=none` and requests full A100 with
  `BIOMERO_GPU_PARTITION_DECONVOLVE_PLATE=gpu_a100_22c` plus
  `BIOMERO_GPUS_DECONVOLVE_PLATE=1`.
- `BIOMERO_FORCE_GPU_ALL_WORKFLOWS=true` is an opt-in admin fallback that
  requests the global GPU default for every workflow. Keep it off by default
  because it is wasteful for CPU-only workflows.
- Env GPU policy is authoritative for GPU-effective workflows: stale static
  `--partition`, `--gres`, or `--gpus` values from `slurm-config.ini` are
  stripped and replaced with the configured env policy.
- CPU-only workflows, conversion jobs, and image-pull jobs omit `--partition` so
  Spider routes them to the normal/default partition.
- `slurm_conversion_partition` is blank for Spider.

## Removed cleanup scaffolding

- Removed migration code that rewrote the temporary inline
  `_nl_biomero_verify_outputs` helper and the temporary bad
  `$(dirname "$0")/biomero_job_helpers.sh` source path. Live Spider scripts and
  generated scripts now use the final helper path directly.
- Renamed an internal remote patch variable from a GPU-specific name to a
  generic Slurm script normalization name.

## Still intentionally deployment-specific

- The current runtime patch remains a compatibility shim for the pinned BIOMERO
  version. It should be retired when upstream BIOMERO supports these Slurm
  behaviors directly.
- Apply the BIOMERO Slurm runtime patch in both `biomeroworker` and `omeroweb`.
  The analyzer web process can submit Slurm jobs directly; if only the worker
  image is patched, generated job scripts may exist but submissions can omit the
  per-job env-file argument, causing empty workflow environment variables and
  Apptainer errors such as `/ as sandbox is not authorized`.
- StarDist/Cellpose channel limitations are workflow-container behavior, not
  Slurm integration behavior. The integration now surfaces those failures
  cleanly.
