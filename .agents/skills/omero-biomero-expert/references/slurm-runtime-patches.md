# Slurm Runtime Patches

This deployment carries compatibility patches for the pinned BIOMERO version and Spider/SURF Slurm behavior. Treat them as intentional runtime shims, not accidental local hacks.

## Spider Policy

Spider/SURF-specific values are deployment policy, not generic BIOMERO defaults:

```text
SPIDER_USER
SPIDER_PROJECT
spider.surf.nl
/project/<project>/Share/biomero
BIOMERO_GPU_PARTITION
BIOMERO_GPUS
BIOMERO_GPU_GRES
BIOMERO_FORCE_GPU_WORKFLOWS
BIOMERO_FORCE_GPU_ALL_WORKFLOWS
```

For Spider, `slurm_conversion_partition` is intentionally blank. CPU-only workflows, conversions, and image-pull jobs should omit `--partition` so Spider routes them to the normal/default partition. Effective GPU jobs request global GPU defaults unless a workflow-specific override is configured.
Per-workflow overrides use the uppercased workflow key with non-alphanumeric characters replaced by underscores, for example `BIOMERO_GPU_PARTITION_CELLPOSE` or `BIOMERO_GPU_GRES_FRACTAL_CELLPOSE_SAM_BIAFLOWS`.
When a workflow is GPU-effective, env GPU policy is authoritative: stale static `--partition`, `--gres`, or `--gpus` values from `slurm-config.ini` are removed and rebuilt from the env policy.

## Runtime Patch File

`biomeroworker/patch_biomero_runtime.py` patches `biomero/slurm_client.py` inside the active container environment without importing BIOMERO during image build.

Reasons the patch exists:

- Support `7z` or `7za` on Slurm systems.
- Use `mkdir -p` so retry directories are idempotent.
- Require `slurm_data_bind_path` before submitting jobs; blank bind path can lead to Apptainer errors like `/ as sandbox is not authorized`.
- Write per-job env files because `sbatch` jobs may not inherit SSH session env.
- Normalize descriptor-generated scripts to source those env files.
- Replace hard-coded `singularity run --nv` with conditional GPU use.
- Add GPU partition/count/GRES only when effective `use_gpu` is true.
- Fail generated jobs when output directories are missing or empty.
- Run image pulls/builds through Slurm, not the login node, with project-local Apptainer temp/cache.
- Bound image pull resources using `BIOMERO_PULL_CPUS` and `BIOMERO_PULL_MEM`.

Remove the patch only when upstream BIOMERO includes equivalent behavior.

## Generated Job Script Normalization

`biomeroworker/patches/generated_job_postprocess.py` injects:

- `set -eo pipefail`
- optional sourcing of `BIOMERO_ENV_FILE`
- conditional `GPU_FLAG="--nv"` based on `USE_GPU`
- `_nl_biomero_verify_outputs`

`biomeroworker/patches/jobs/biomero_job_helpers.sh` defines `nl_biomero_verify_outputs`, which fails if `$DATA_PATH/data/out` does not exist or is empty. This prevents workflows that print tracebacks but exit zero from hanging later during import.

## Slurm Config Rendering

`scripts/render-slurm-config.sh` renders:

```text
web/slurm-config-template.ini -> web/slurm-config.ini
```

It substitutes `SPIDER_USER` and `SPIDER_PROJECT`, then sets `web/slurm-config.ini` mode `0666` because OMERO.biomero writes this bind-mounted file from `omeroweb` as uid 999.

`web/slurm-config-template.ini` and `web/slurm-config.ini` include comments documenting GPU policy: GPU resources are intentionally not static in the workflow definitions; the runtime patch injects them only for effective GPU jobs.

## Image Pulls and Apptainer

Image initialization should not run parallel background pulls on the login node. The patch submits pull jobs via Slurm, creates project-local `.apptainer_tmp` and `.apptainer_cache`, and emits real failures.

If image initialization appears successful but SIFs are missing:

```bash
ssh spider 'find /project/<project>/Share/biomero -name "pull_*-%j.log" -o -name "sing.log"'
```

Check for:

```text
failed <path> <version> exit=<code>
No space left on device
permission denied
```

## GPU Behavior

Effective GPU workflows are controlled by global defaults and optional per-workflow overrides:

```text
BIOMERO_FORCE_GPU_WORKFLOWS=cellpose,stardist,stardist5d,fractal-cellpose-sam-biaflows,deconvolve_plate
BIOMERO_GPU_PARTITION=gpu_a100_mig
BIOMERO_GPU_GRES=gpu:a100_3g.20gb:1
BIOMERO_GPUS=
BIOMERO_GPU_PARTITION_DECONVOLVE_PLATE=gpu_a100_22c
BIOMERO_GPU_GRES_DECONVOLVE_PLATE=none
BIOMERO_GPUS_DECONVOLVE_PLATE=1
BIOMERO_FORCE_GPU_ALL_WORKFLOWS=false
```

If a request explicitly sets device `cpu` or disables `use_gpu`, it should not receive GPU Slurm params. Otherwise GPU-native workflows default to `use_gpu=true`.
When `BIOMERO_GPU_GRES...` is set, it is emitted as `--gres=...` instead of `--gpus=...`. Use `none`, `false`, or `off` on a workflow-specific `BIOMERO_GPU_GRES_<WORKFLOW_KEY>` to clear an inherited global GRES and fall back to that workflow's `BIOMERO_GPUS_<WORKFLOW_KEY>`. This keeps common GPU workflows on MIG while leaving heavier workflows, such as `deconvolve_plate`, on full A100.
Set `BIOMERO_FORCE_GPU_ALL_WORKFLOWS=true` only as an emergency/admin override to request the global GPU default for every workflow. It is useful when a workflow internally detects GPUs but has no `use_gpu` parameter; it is wasteful for CPU-only work and still respects explicit `device=cpu` or `use_gpu=false`.

## Output Verification

Workflow result import should fail early if no outputs exist. Look for error text:

```text
ERROR: Workflow output directory does not exist
ERROR: Workflow completed without producing files
```

These are more actionable than a later BIOMERO UI hang at 90%.

## Script Repository Contract

When `slurm_script_repo` is empty, BIOMERO generates scripts locally and NL-BIOMERO normalizes them. If an administrator supplies a custom Git repository, that repository is used as provided; do not silently mutate custom repository contracts.

## Setup Audit Notes

`setup_docs/slurm_spider_patch_audit.md` distinguishes generally useful Slurm improvements from Spider-specific policy. `setup_docs/stack_patch_audit.md` records patch intent and cleanup candidates. Consult both before removing patches or converting them into upstream PRs.
