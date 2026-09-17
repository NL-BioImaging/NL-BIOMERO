---
name: omero-biomero-expert
description: OMERO/BIOMERO expert runbook for NL-BIOMERO deployments. Use for debugging and operating OMERO.server/web, OMERO.biomero, BIOMERO analyzer/importer/converter, Metabase dashboards, Docker Compose, Slurm/HPC, storage permissions, SSH access, logs, and Postgres verification.
---

# OMERO/BIOMERO Expert

Use this skill for NL-BIOMERO work on dev or prod. Prefer inspection over guesses: identify the active host, read the relevant compose/env/log state, verify data paths and permissions, then run a focused smoke test.

Never print secrets. Mask `.env`, container env, Metabase datasource JSON, passwords, secret keys, JWTs, and tokens in user-facing output.

## Development Branches and Pull Requests

For NL-BIOMERO and its submodules, including `biomero-importer`, use a dedicated
branch and a pull request when publishing changes, including hotfixes. Give the
PR a clear description of the final change and its validation so the user can
review the work and follow its history.

On an existing non-default branch intended for a pull request, make focused,
coherent commits and push them as normal completion of authorized development
work. Do not hold the branch locally merely to run a slow full suite: run cheap,
relevant checks that catch immediate mistakes, inspect the diff, then let the
required GitHub Actions checks be the full-suite gate. If CI fails, inspect it
and push a follow-up fix. Incremental branch commits may stay small because the
pull request will normally be squash-merged.

When the user authorizes integration (for example, "merge it"), merge through
the PR after the relevant checks pass. Prefer squash merging so each PR becomes
one logical commit that can be reverted as a unit, unless the user requests a
different merge strategy. Do not interpret the integration instruction as a
request to push directly to `main` or `master`; use a direct push only when the
user explicitly requests that exception.

Use proportionate local verification before a direct default-branch push,
release, change without suitable CI coverage, or higher-risk operation. This
workflow does not authorize unrelated publication, merging, deployment, or
destructive actions.

## Repository Scope and Example Contract

`NL-BIOMERO` is the runnable local Docker Compose demonstration and the source
used to build the project's Docker Hub images. It is not the repository for an
institution's production HPC deployment; those deployment-specific values live
in separate site repositories.

### Feature flags and demo defaults

Implement new optional features behind a feature flag. A missing, empty or
explicitly false flag must leave the feature disabled, preserving existing
behavior for deployments upgrading without configuration changes.

NL-BIOMERO is the full-featured demonstration: explicitly enable new features
in its supplied `.env` and `.env.shared` defaults. Keep applicable Compose
wiring in sync, with false fallbacks for feature-enablement flags rather than
implicitly enabling them in containers or library defaults. Documentation must
distinguish the enabled demo configuration from opt-in upgrades elsewhere.
Verify enabled, false, missing and empty flag behavior when adding a feature.

All enabled values and concrete examples shipped by this repository must work in
the documented local environments:

- CPU-only: `NL-BioImaging/NL-BIOMERO-Local-Slurm`
- GPU-enabled: `Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO-Local-Slurm-GPU`

Before changing Slurm resource examples, inspect the current README and
`slurm.conf` in both referenced repositories. Never copy a site-specific
partition, reservation, account, time limit, CPU count, or memory request into
NL-BIOMERO's active examples. Prefer leaving partition and time unset when their
scheduler defaults are portable. Current portable image-pull settings are 1 CPU,
2G memory, bounded concurrency 2, and empty time/partition values; revalidate
them if either local cluster topology changes.

Documentation is for users: show only valid, positive examples. Do not preserve
site-specific or invalid values as negative examples explaining what not to use.

### Dockerfile development/release switching

Feature PR branches may install matching unpublished component branches for
local integration testing. Release-ready PRs and the default branch
(`master`/`main`) must install published component versions, not moving branches.
Switch back during release preparation, before merging NL-BIOMERO.

Keep both approaches in the Dockerfiles: comment/uncomment the existing blocks
instead of deleting them. Development mode enables the branch ARGs, GitHub
commit `ADD` cachebusters, Git-based Python installs and branch-based scripts
clones; comment the corresponding release blocks. Release mode comments all
development ARG/ADD/RUN blocks and enables PyPI version installs and script-tag
clones. No active release instruction should reference a development branch.
Keep the server and biomeroworker scripts selections identical.

Do not put temporary branch selectors in Compose or `.env`. Explicitly install
the matching BIOMERO core branch in the web image before OMERO.biomero, or use
a temporary PEP 508 direct dependency in OMERO.biomero's feature `setup.py`
when a generated development version cannot satisfy its release lower bound.
Restore published dependency ranges before publishing any component package.

### Prerelease coordination and ACC handoff

This sequence is a preparation/status runbook, not permission to execute it.
Agents may prepare and push scoped changes to authorized PR branches. Merging,
creating tags or GitHub releases (including prereleases), rebuilding/restarting
the stack and deploying to ACC require explicit user authorization. A request
to check readiness or update release references does not authorize publication.

Follow dependency availability, rather than assuming a release announcement
means all artifacts are ready:

1. Publish changed schema contracts first. If needed, publish the shallower
   package/container next, using those published contracts.
2. Update importer dependencies to the required published schema/shallower
   versions, merge through its PR and publish its prerelease. Verify PyPI and
   container availability before consumers depend on it.
3. Update BIOMERO core's importer/schema lower bounds where needed, then merge
   and prerelease core and biomero-scripts. Scripts must match the released
   core/importer APIs; verify their release tag is available.
4. Update OMERO.biomero to published core/importer dependencies, merge and
   prerelease it. Verify its PyPI package contains no feature-branch dependencies.
5. Prepare NL-BIOMERO last: advance the clean importer submodule to its released
   commit, align component refs in `.env` and `.env.shared`, restore release
   Dockerfile blocks, and align applicable Compose wiring, INIs and docs.
   Preserve deployment-specific paths/credentials and the enabled demo flags.
   Validate resolved build arguments, shared config mounts and feature settings.
6. Once authorized, merge NL-BIOMERO and publish a GitHub semver release such
   as `vX.Y.Z-beta.N`, explicitly marked as a prerelease. GitHub release tags
   own package versions; do not introduce source-file version bumps. Updating
   deployment references in `.env` is separate from package versioning.
7. The published NL-BIOMERO release triggers container builds. Verify every
   required image build/push succeeds before handing the pinned image tags to
   ACC for redeployment. Coordinate its smoke test before a full-Plate test;
   do not automatically start deployment or analysis jobs.

Use the appropriate version format: PyPI pins use normalized versions such as
`1.5.0b6`, scripts refs use Git tags such as `v2.9.0-beta.9`, and container refs
use the actually published Docker tags such as `1.8.0-beta.6`. Stable container
releases cascade to full-version, major/minor and `latest` tags; prereleases do
not update stable aliases. Pin prerelease images explicitly for ACC, including
the shallower. Its receipt/tool version is the normalized package version, not
the Docker tag; keep importer trust settings aligned with that selected image.

## Stack Root

The stack root is the directory containing `docker-compose.yml` and all stack subdirectories (`web/`, `logs/`, `metabase/`, `.ssh/`, etc.). All relative paths in this runbook assume you are working from `<stack-root>`.

On prod this is typically:

```text
/opt/omero/NL-BIOMERO
```

On a dev machine it may be in a home directory; check with:

```bash
sudo find /opt /home -maxdepth 6 -name 'docker-compose.yml' 2>/dev/null | xargs grep -l 'omeroserver' 2>/dev/null
```

## First Checks

Confirm the host. The SSH alias `biomero-prod` is configured in the repo-local `.ssh/config`, so use `ssh -F .ssh/config biomero-prod ...` when it is not in `~/.ssh/config`.

```bash
ssh -F .ssh/config biomero-prod 'hostname; whoami; pwd'
ssh -F .ssh/config biomero-prod 'cd <stack-root> && sudo docker compose ps'
```

Docker often requires `sudo`. If `docker ps` fails on `/var/run/docker.sock`, retry with `sudo docker ...`.

Core service names (NL-BIOMERO defaults):

```text
metabase
nl-biomero-omeroweb-1
nl-biomero-omeroserver-1
nl-biomero-biomeroworker-1
nl-biomero-omeroworker-1-1
nl-biomero-biomero-importer-1
nl-biomero-database-1
nl-biomero-database-biomero-1
```

## OMERO Script Processor Environment

Environment variables configured on the `biomeroworker` Compose service are
not automatically inherited by downloaded OMERO script subprocesses. The
repository overrides OMERO's processor at `biomeroworker/processor.py`; its
`ProcessI.make_env()` method contains the explicit allowlist passed to scripts.

When a BIOMERO script starts reading a new environment variable, update both
the Compose service and this processor allowlist. Variables represented in
`biomero.constants.slurm_env` are forwarded dynamically, while non-BIOMERO
integration variables such as `IMPORTER_ENABLED`, `IMPORT_MOUNT_PATH`, and
`OMERO_BIOMERO_*` must be listed explicitly unless they are deliberately added
to that shared constants class. Rebuild/recreate `biomeroworker` after changing
the processor override; restarting a container built from the old image is not
enough.

Quick status:

```bash
cd <stack-root>
sudo docker compose ps
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo docker compose logs --tail=120 metabase omeroweb biomero-importer
```

## Reference Routing

Read only the relevant reference before acting:

- [references/permissions-and-deployment.md](references/permissions-and-deployment.md): host/container UID/GID issues, project-local SSH, writable bind mounts, `chmod`/ownership workarounds, production vs dev compose, backup/restore guardrails.
- [references/metabase-dashboards.md](references/metabase-dashboards.md): BIOMERO Analyze/Import iframe failures, dashboard IDs, embedding secrets, H2 inspection, datasource credential repair, signed embed smoke tests.
- [references/slurm-runtime-patches.md](references/slurm-runtime-patches.md): HPC/Slurm behavior, BIOMERO config options, GPU policy, per-job env files, Apptainer cache/temp, output verification, generated job script normalization.
- [references/importer-analyzer-storage.md](references/importer-analyzer-storage.md): BIOMERO.importer, analyzer-to-importer result flow, `/data` path invariants, `.analyzed`/`.processed`, shared storage, import order polling, importer logs.

## Converter and Importer Code

The `biomero-importer` runs `biomero-converter` with rootless Podman inside the importer container. The importer container's internal Podman store is ephemeral when the container is recreated, so reload rebuilt converter images after rebuilds or importer recreation.

### Rebuild and reload the converter image

```bash
# On the host, from the biomero-converter source directory:
docker build -t cellularimagingcf/biomero-converter:latest .

# Load the rebuilt image into the running importer's internal Podman store:
docker save cellularimagingcf/biomero-converter:latest | docker exec -i nl-biomero-biomero-importer-1 podman load
```

### Deploy importer code changes

If you modify files in the `biomero-importer` repository, the mounted source updates immediately but worker processes may have cached modules. Restart the service:

```bash
docker compose restart biomero-importer
```

## Importer Logs and Test Images

Logs (relative to stack root):

```text
logs/biomero-importer/app.logs          # database poller, preprocessing, registration stages
logs/biomero-importer/cli.<UUID>*.errs  # stderr per worker run; check for tracebacks
```

Tail the main log:

```bash
tail -f <stack-root>/logs/biomero-importer/app.logs
# or inside the stack root:
tail -f logs/biomero-importer/app.logs
```

Sample test images (in the biomero-importer repo / container):

```text
# Host repo path (relative to stack):
biomero-importer/tests/Barbie1.tif
biomero-importer/tests/Barbie2.tif
biomero-importer/tests/Barbie3.tif

# Inside the container:
/auto-importer/tests/Barbie1.tif
/auto-importer/tests/Barbie2.tif
/auto-importer/tests/Barbie3.tif
```

## OMERO Database Verification

Use Postgres for high-confidence import verification:

```bash
docker exec -it nl-biomero-database-1 psql -U omero -d omero
```

Useful checks:

```sql
-- Check plate acquisition rows (redundant rows = double-timepoint-folder problem for Incucyte)
-- Expectation for Incucyte: (0 rows). Any rows returned = double-timepoint-folder bug.
SELECT id, plate, name FROM plateacquisition WHERE plate = <PLATE_ID>;

-- Locate image IDs for a plate
SELECT ws.id AS wellsample_id, ws.well, ws.image
FROM wellsample ws
JOIN well w ON ws.well = w.id
WHERE w.plate = <PLATE_ID>;

-- Verify delta T timestamps (should show proper increments, not all zero)
-- Expectation: increments matching raw timepoints, e.g. 0 / 43200 (12 h) / 86400 (24 h). All-zero = registration bug.
SELECT id, thez, thec, thet, deltat
FROM planeinfo
WHERE pixels IN (SELECT id FROM pixels WHERE image = <IMAGE_ID>)
ORDER BY thet;
```

For Incucyte imports, redundant `plateacquisition` rows usually indicate the double-timepoint-folder UI problem. `planeinfo.deltat` should contain meaningful increments, not all zero.

## OMERO Physical Units

When updating registration code (e.g. `biomero-importer/biomero_importer/utils/register.py`), do not wrap raw values in gateway helpers when instantiating physical unit model classes.

Correct:

```python
from omero.model import TimeI
from omero.model.enums import UnitsTime
p_info.deltaT = TimeI(d_t, UnitsTime.SECOND)
```

Incorrect:

```python
p_info.deltaT = TimeI(rdouble(d_t), UnitsTime.SECOND)  # raises type error on save
```

## Building the NL-BIOMERO Docs Locally

The docs live in `d:\workspace\NL-BIOMERO\docs\` and use Sphinx with a pre-created venv.

To build the **current branch only** (no multi-version):

```powershell
cd d:\workspace\NL-BIOMERO\docs
.\venv\Scripts\sphinx-build -b html . _build_local
```

Output is written to `_build_local\`. Open in a browser:

```powershell
start d:\workspace\NL-BIOMERO\docs\_build_local\index.html
```

Or open with the browser tool using:

```
file:///d:/workspace/NL-BIOMERO/docs/_build_local/index.html
```

Do **not** use `make html` or `sphinx-multiversion` — those build all tagged versions and are slow. The direct `sphinx-build` call above is the correct approach for local preview.

The venv already has all required packages (`Sphinx`, `myst-parser`, `sphinx-rtd-theme`, `sphinxcontrib-mermaid`, `sphinx-multiversion`). No install step is needed.
