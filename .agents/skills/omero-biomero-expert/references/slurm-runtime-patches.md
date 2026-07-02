# Slurm Runtime Configuration

This deployment USED to carry a compatibility patch (`patch_biomero_runtime.py`)
for the pinned BIOMERO version. As of the cutover (BIOMERO `v2.6.0`+), all of
that behavior is upstreamed into core BIOMERO and enabled through standard config
options (env vars + `slurm-config.ini`). The patch file and `biomeroworker/patches/`
are gone. See `PATCH_CUTOVER.md` for the full patch-hunk -> config mapping.
Treat the settings below as intentional deployment config, not accidental hacks.

## Accessing Spider SSH

You cannot SSH to Spider directly from the surfbiomero host. The SSH key and `spider` alias are inside the `biomeroworker` container. Always exec in first:

```bash
# On surfbiomero (prod host)
sudo docker exec -it nl-biomero-biomeroworker-1 bash

# Then inside the container:
ssh spider 'squeue -u biomero-sloev'
ssh spider 'sacct -j <JOBID> --format=JobID,JobName,Partition,Reservation,State,ExitCode -X'
ssh spider 'sinfo -s'
```

Or run a one-liner without an interactive shell:

```bash
sudo docker exec nl-biomero-biomeroworker-1 ssh spider 'squeue -u biomero-sloev'
sudo docker exec nl-biomero-biomeroworker-1 ssh spider 'sacct -j <JOBID> --format=JobID,Partition,Reservation,AllocTRES,State -X'
```

The `spider` alias resolves via the SSH config mounted into the biomeroworker container (`worker.cfg` / `10-mount-ssh.sh`).

## Spider Policy

Spider/SURF-specific values are deployment policy, not generic BIOMERO defaults:

```text
SPIDER_USER
SPIDER_PROJECT
spider.surf.nl
/project/<project>/Share/biomero
BIOMERO_GPU_PARTITION   (shared GPU partition default)
BIOMERO_GPU_GRES        (shared GPU --gres default)
BIOMERO_GPU_GPUS        (shared GPU --gpus default; set GRES or GPUS, not both)
BIOMERO_DEFAULT_PARTITION (generic fallback --partition)
```

For Spider, `slurm_conversion_partition` is intentionally blank. The shared GPU
defaults (`BIOMERO_GPU_*`) apply to workflows that request GPU. A workflow
requests GPU either per-run (`use_gpu` from the UI) or by default via a
per-workflow `<name>_use_gpu = true` in `slurm-config.ini`. Per-workflow GPU
resources are set with `<name>_job_partition`, `<name>_job_gres`, or
`<name>_job_gpus` keys in `[MODELS]` and take precedence over the shared env
defaults. The former per-workflow GPU **env** overrides
(`BIOMERO_GPU_*_<WORKFLOW_KEY>`) and the `BIOMERO_FORCE_GPU_WORKFLOWS` /
`BIOMERO_FORCE_GPU_ALL_WORKFLOWS` flags no longer exist; use the `[MODELS]`
keys instead.

## Core Config (formerly the runtime patch)

The behavior previously injected by `patch_biomero_runtime.py` is now core BIOMERO,
enabled by config. Mapping (env vars set in `docker-compose.yml` / `.env.shared`,
ini keys in `web/slurm-config-template.ini`):

- `7z`/`7za` support: core `slurm_zip_cmd` default `$(command -v 7z || command -v 7za)` (no setting needed); override with `BIOMERO_SLURM_ZIP_CMD`.
- `mkdir -p` idempotent unpack dirs: built into core.
- per-job env files for `sbatch`: `BIOMERO_ENV_FILE_SUBMISSION=true`.
- generated scripts source the env file, `set -eo pipefail`, conditional `$GPU_FLAG`, and verify outputs: baked into the released `resources/job_template.sh`.
- conditional `--nv` (GPU_FLAG per job): `BIOMERO_INJECT_GPU_FLAG=true`.
- GPU partition/gres/gpus: shared `BIOMERO_GPU_PARTITION` / `BIOMERO_GPU_GRES` / `BIOMERO_GPU_GPUS`, plus per-workflow `[MODELS]` `<name>_use_gpu` / `<name>_job_*`.
- generic fallback partition: `BIOMERO_DEFAULT_PARTITION`.
- required bind path: core keeps `slurm_data_bind_path` optional; this deployment sets it in `slurm-config.ini` (no hard failure).
- image pulls via Slurm with bounded resources + project Apptainer dirs: `BIOMERO_IMAGE_PULL_VIA_SBATCH=true`, `BIOMERO_PULL_CPUS`, `BIOMERO_PULL_MEM`, and `apptainer_tmpdir` / `apptainer_cachedir` in `[SLURM]`.

## Generated Job Script Normalization

Generated job scripts come straight from BIOMERO's released `resources/job_template.sh`,
which already includes `set -eo pipefail`, optional `$OPTIONAL_ENV` sourcing,
conditional `singularity run $GPU_FLAG`, and an output-verification tail that exits
`2` when `$DATA_PATH/data/out` is missing or empty. No post-processing step or
helper file is injected anymore.

## Slurm Config Rendering

`scripts/render-slurm-config.sh` renders:

```text
web/slurm-config-template.ini -> web/slurm-config.ini
```

It substitutes `SPIDER_USER` and `SPIDER_PROJECT`, then sets `web/slurm-config.ini` mode `0666` because OMERO.biomero writes this bind-mounted file from `omeroweb` as uid 999.

`web/slurm-config-template.ini` and `web/slurm-config.ini` include comments documenting GPU policy: shared GPU defaults come from `BIOMERO_GPU_*` env vars, and per-workflow GPU is opted in with `<name>_use_gpu` / `<name>_job_*` keys in `[MODELS]`.

## Image Pulls and Apptainer

Image initialization should not run parallel background pulls on the login node. With `BIOMERO_IMAGE_PULL_VIA_SBATCH=true`, BIOMERO submits pull jobs via Slurm, uses the `apptainer_tmpdir` / `apptainer_cachedir` project paths from `[SLURM]`, and emits real failures.

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

A workflow runs on GPU when `use_gpu` is effectively true: either passed per-run
from the UI, or defaulted via a per-workflow `<name>_use_gpu = true` in
`slurm-config.ini` `[MODELS]`. When GPU is effective, BIOMERO adds the GPU sbatch
params and (with `BIOMERO_INJECT_GPU_FLAG=true`) sets `GPU_FLAG=--nv`; otherwise
`GPU_FLAG` is empty.

Shared defaults and per-workflow overrides:

```text
# shared defaults (docker-compose / .env.shared); blank = inherit Spider default
BIOMERO_GPU_PARTITION=gpu_a100_mig
BIOMERO_GPU_GRES=gpu:a100_3g.20gb:1
BIOMERO_GPU_GPUS=            # set GRES or GPUS, not both
```

```ini
# per-workflow overrides in slurm-config.ini [MODELS]; take precedence over env
cellpose_use_gpu = true
deconvolve_plate_use_gpu = true
deconvolve_plate_job_partition = gpu_a100_22c
deconvolve_plate_job_gpus = 1
```

Guards: a per-workflow `--partition`/`--gres`/`--gpus` already present in the job
params wins over the shared default, and a GPU partition wins over
`BIOMERO_DEFAULT_PARTITION`. Spider rejects `--gres` and `--gpus` together, so set
only one. The old `BIOMERO_FORCE_GPU_*` flags and per-workflow GPU env overrides
are gone; express the same intent with the `[MODELS]` keys above.

## Output Verification

Workflow result import should fail early if no outputs exist. Look for error text:

```text
ERROR: Workflow output directory does not exist
ERROR: Workflow completed without producing files
```

These are more actionable than a later BIOMERO UI hang at 90%.

## Script Repository Contract

When `slurm_script_repo` is empty, BIOMERO generates scripts locally from the
released `job_template.sh` (which already includes the hardening and verification
logic). If an administrator supplies a custom Git repository, that repository is
used as provided; do not silently mutate custom repository contracts.

## Setup Audit Notes

`setup_docs/slurm_spider_patch_audit.md` and `setup_docs/stack_patch_audit.md` are
historical audits from before the cutover; they describe the now-removed patch.
For the current state and the patch-hunk -> config mapping, use `PATCH_CUTOVER.md`
in the repo root instead.
