# Slurm / HPC Runtime Configuration

## NL-BIOMERO Local-Demo Boundary

The checked-in NL-BIOMERO Compose and INI examples target the documented local
Slurm demonstrations, not Spider or any other institutional HPC. Site-specific
deployment values belong in that site's deployment repository.

Validate concrete scheduler examples against both local clusters before
publishing them. The CPU-only cluster currently has two 4-CPU/5120-MB nodes and
uses `test` as its default partition. The GPU-enabled cluster has three
8-CPU/5120-MB nodes, uses `normal` as its default CPU partition, and reserves
`gpu` for its single GPU node.

For image-pull arrays, the shared portable example is:

```ini
slurm_image_pull_via_sbatch=true
image_pull_cpus=1
image_pull_mem=2G
image_pull_time=
image_pull_concurrency=2
image_pull_partition=
```

Leaving time and partition empty intentionally inherits each demo scheduler's
valid defaults. Re-check the two local cluster READMEs and `slurm.conf` files if
their topology changes instead of treating these values as universal HPC advice.

This deployment carried a compatibility patch (`patch_biomero_runtime.py`) for a pinned BIOMERO version. As of `BIOMERO v2.6.0+`, all of that behavior is upstreamed into core BIOMERO and enabled through standard config options (env vars + `slurm-config.ini`). The patch file and `biomeroworker/patches/` are gone.
Treat the settings below as intentional deployment config, not accidental hacks.

## Accessing the HPC Cluster

You cannot SSH to the HPC cluster directly from the prod host. The SSH key and HPC alias are inside the `biomeroworker` container. Always exec in first:

```bash
# On the prod host:
sudo docker exec -it nl-biomero-biomeroworker-1 bash

# Then inside the container — <hpc-alias> is the SSH alias configured via the mounted worker SSH config:
ssh <hpc-alias> 'squeue -u <hpc-username>'
ssh <hpc-alias> 'sacct -j <JOBID> --format=JobID,JobName,Partition,Reservation,State,ExitCode -X'
ssh <hpc-alias> 'sinfo -s'
```

Or as one-liners without an interactive shell:

```bash
sudo docker exec nl-biomero-biomeroworker-1 ssh <hpc-alias> 'squeue -u <hpc-username>'
sudo docker exec nl-biomero-biomeroworker-1 ssh <hpc-alias> 'sacct -j <JOBID> --format=JobID,Partition,Reservation,AllocTRES,State -X'
```

The HPC alias resolves via the SSH config mounted into the biomeroworker container (via `worker.cfg` / `10-mount-ssh.sh`).

> **For this deployment (Spider at SURF):** the alias is `spider` and the username is the value of `SPIDER_USER`.

## HPC Deployment Policy Variables

These values are deployment-specific and must be adapted per HPC cluster. For Spider at SURF they are:

```text
SPIDER_USER        # HPC account username (Spider-specific env var name)
SPIDER_PROJECT     # HPC project name (Spider-specific env var name)
spider.surf.nl     # actual HPC hostname (resolved by the SSH alias)
/project/<SPIDER_PROJECT>/Share/biomero   # shared project storage path
```

For other HPC clusters, adapt the env var names and paths accordingly. The core concepts are:
- an HPC username
- a project/allocation identifier
- a shared storage path visible from both the HPC nodes and the stack

## GPU Policy

Shared GPU defaults and per-workflow overrides:

```text
# Shared defaults (docker-compose / .env.shared); leave blank to inherit cluster default
BIOMERO_GPU_PARTITION=<cluster-gpu-partition>
BIOMERO_GPU_GRES=<gres-spec>      # e.g. gpu:a100_3g.20gb:1  (Spider/SURF example)
BIOMERO_GPU_GPUS=                 # set GRES or GPUS, not both

BIOMERO_DEFAULT_PARTITION=<fallback-partition>
```

> **Spider/SURF example values:**
> ```text
> BIOMERO_GPU_PARTITION=gpu_a100_mig
> BIOMERO_GPU_GRES=gpu:a100_3g.20gb:1
> ```
> These are Spider-specific partition names; other clusters will differ.

Per-workflow GPU overrides in `slurm-config.ini` `[WORKFLOWS]` take precedence over the shared env defaults:

```ini
cellpose_use_gpu = true
deconvolve_plate_use_gpu = true
deconvolve_plate_job_partition = gpu_a100_22c   # Spider-specific example
deconvolve_plate_job_gpus = 1
```

A workflow requests GPU when `use_gpu` is effectively true (per-run from the UI, or via `<name>_use_gpu = true` in `[WORKFLOWS]`). When GPU is active, BIOMERO adds the GPU sbatch params and (with `BIOMERO_INJECT_GPU_FLAG=true`) sets `GPU_FLAG=--nv`; otherwise `GPU_FLAG` is empty.

Guards:
- A per-workflow `--partition`/`--gres`/`--gpus` in `[WORKFLOWS]` wins over the shared default.
- A GPU partition wins over `BIOMERO_DEFAULT_PARTITION`.
- Do not set `--gres` and `--gpus` simultaneously (rejected by some schedulers including Spider).
- The old `BIOMERO_FORCE_GPU_*` flags and per-workflow GPU env overrides are gone; use `[WORKFLOWS]` keys instead.

## Core Config (formerly the runtime patch)

Mapping from old patch behavior to current config (env vars set in `docker-compose.yml` / `.env.shared`; ini keys in `web/slurm-config-template.ini`):

| Former patch behavior | Current config |
|---|---|
| `7z`/`7za` support | `slurm_zip_cmd` default auto-detects; override with `BIOMERO_SLURM_ZIP_CMD` |
| `mkdir -p` idempotent unpack dirs | built into core |
| per-job env files for `sbatch` | `BIOMERO_ENV_FILE_SUBMISSION=true` |
| generated scripts: `set -eo pipefail`, conditional `$GPU_FLAG`, output verify | `resources/job_template.sh` in released BIOMERO |
| conditional `--nv` (GPU_FLAG per job) | `BIOMERO_INJECT_GPU_FLAG=true` |
| GPU partition/gres/gpus | `BIOMERO_GPU_PARTITION` / `BIOMERO_GPU_GRES` / `BIOMERO_GPU_GPUS` + `[WORKFLOWS]` keys |
| generic fallback partition | `BIOMERO_DEFAULT_PARTITION` |
| image pulls via Slurm | `BIOMERO_IMAGE_PULL_VIA_SBATCH=true`; optional `BIOMERO_PULL_CPUS`, `BIOMERO_PULL_MEM`, `BIOMERO_PULL_TIME`, `BIOMERO_PULL_CONCURRENCY`, and `BIOMERO_PULL_PARTITION` overrides |
| Apptainer dirs | `apptainer_tmpdir` / `apptainer_cachedir` in `[SLURM]` |

## Slurm Config Rendering

`scripts/render-slurm-config.sh` renders:

```text
web/slurm-config-template.ini -> web/slurm-config.ini
```

It substitutes HPC credential env vars (e.g. `SPIDER_USER` and `SPIDER_PROJECT` for Spider), then sets `web/slurm-config.ini` mode `0666` because OMERO.biomero writes this bind-mounted file from `omeroweb` as uid 999.

`web/slurm-config-template.ini` includes comments documenting GPU policy.

## Image Pulls and Apptainer

With `BIOMERO_IMAGE_PULL_VIA_SBATCH=true`, BIOMERO submits workflow and converter pulls as a bounded Slurm array, uses `apptainer_tmpdir` / `apptainer_cachedir` from `[SLURM]`, and emits real failures. Dedicated image-pull values override the generic `sbatch_*` values; blank dedicated values inherit the generic values and then the scheduler defaults. Image initialization should not run background pulls on the login node.

Use the latest submission directory to inspect the machine-readable result and the live output of each array task:

```bash
# Run on the Slurm login node. Replace the path with slurm_script_path.
pull_root=/data/my-scratch/slurm-scripts/image-pulls
latest=$(cat "$pull_root/latest")
cat "$latest/submission.meta"
cat "$latest"/status-*.status
tail -f "$latest"/pull-image-*.log
```

A numeric `array_job_id` in `submission.meta` (and `pull-image-<job>_<task>.log`) confirms scheduler submission. `array_job_id` empty/`None`, a `direct-...` status reason, or `pull-image-direct_<task>.log` means sbatch pulling was disabled and the backward-compatible login-node path was used.

In direct mode, `nohup` returning successfully only confirms that the background task was launched; it cannot synchronously return the eventual image-build result. Follow the per-image status record until it reaches `READY` or `FAILED`. A failed direct task still writes its terminal exit code and reason, removes temporary data, and must not publish a destination SIF.

Each status record reports the image kind, name, version, `READY`/`RUNNING`/`FAILED`, exit code, concise reason, and destination. For example, a missing registry tag should become one `FAILED` record with reason `manifest unknown`; it must not create an empty available version or retry as a transient failure. The corresponding task log contains the streamed Apptainer/Singularity diagnostics.

## Generated Job Script Normalization

Generated job scripts come from BIOMERO's released `resources/job_template.sh`, which already includes `set -eo pipefail`, optional `$OPTIONAL_ENV` sourcing, conditional `singularity run $GPU_FLAG`, and an output-verification tail that exits `2` when `$DATA_PATH/data/out` is missing or empty. No post-processing step or helper file is injected.

## Output Verification

Workflow result import should fail early if no outputs exist. Look for:

```text
ERROR: Workflow output directory does not exist
ERROR: Workflow completed without producing files
```

These are more actionable than a later BIOMERO UI hang at 90%.

## Script Repository Contract

When `slurm_script_repo` is empty, BIOMERO generates scripts locally from `job_template.sh`. If an administrator supplies a custom Git repository, that repository is used as provided; do not silently mutate custom repository contracts.
