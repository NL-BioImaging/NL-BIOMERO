# Production Stack Upgrade Approach

This note documents the preferred approach for evaluating newer BIOMERO stack
versions on production. It is intentionally a plan, not an instruction to
upgrade prod immediately.

## Current Situation

Production currently runs the older stable pins from `.env.shared`:

```text
BIOMERO_IMPORTER_VERSION=1.2.1
BIOMERO_VERSION=v2.5.3
OMERO_BIOMERO_VERSION=1.3.2
OMERO_FORMS_VERSION=2.2.0
```

The local/dev `.env` has been refreshed to newer versions:

```text
BIOMERO_IMPORTER_VERSION=1.3.0
BIOMERO_VERSION=v2.7.0
OMERO_BIOMERO_VERSION=1.5.0b7
OMERO_FORMS_VERSION=2.2.0
```

That refresh appears intentional from repository history, but `.env` later
became an ignored local runtime file. `.env.shared` remained on the older
production pins.

Before promoting these versions, verify that every package/tag is installable
from the build source used by the Dockerfiles. In particular, `biomero==v2.7.0`
was not found on PyPI during inspection, while PyPI did list `2.6.0`.

## Guiding Principle

Do not combine two risky changes:

1. Promoting newer BIOMERO/OMERO.biomero versions.
2. Removing or simplifying runtime compatibility patches.

First prove that the existing patch set still builds and works against the
candidate versions. Only then consider retiring individual patch blocks.

## Candidate Upgrade Flow

1. Create a dedicated upgrade branch.
2. Add a tracked candidate env file or documented override, rather than relying
   on a local ignored `.env`.
3. Set candidate versions explicitly.
4. Build the stack in a disposable/dev environment.
5. Let the existing runtime patch scripts run unchanged.
6. Treat any `_replace_required` failure as useful signal that upstream changed
   the patched code path.
7. Run focused smoke tests.
8. Only after successful smoke tests, decide whether to apply the candidate
   versions to `.env.shared` for production.

## Patch Audit Flow

The current patches are documented in:

```text
setup_docs/slurm_spider_patch_audit.md
setup_docs/stack_patch_audit.md
```

For each patch block, classify it as one of:

```text
still required
covered upstream
Spider policy
unknown, needs smoke test
```

Patch removal should be done one behavior at a time. For each removal, rebuild
and run the relevant smoke test before removing another patch.

## Required Smoke Tests

At minimum, test:

```text
CPU-only workflow
MIG GPU workflow, such as Cellpose or StarDist
full-A100 workflow, currently deconvolve_plate
image pull/build initialization
workflow output import back into OMERO
BIOMERO analyzer status/progress display
BIOMERO importer path through /data
OMERO.web login and forms startup
Metabase dashboard embedding
OMERO.insight connectivity on 4063/4064
```

## Patch Behaviors To Verify

The following behaviors should be explicitly verified before removing any
runtime patch:

```text
7z/7za fallback for remote ZIP extraction and result packaging
retry-safe mkdir -p for remote data directories
required slurm_data_bind_path before submitting jobs
per-job env file creation and sourcing by generated Slurm scripts
conditional singularity --nv based on effective USE_GPU
MIG-by-default GPU policy and deconvolve_plate full-A100 override
image pulls/builds submitted through Slurm, not run on the login node
project-local Apptainer temp/cache paths
early failure for missing or empty workflow outputs
```

## Production Promotion Criteria

Promote candidate versions to production only when:

```text
candidate package/tag sources are confirmed
Docker builds are reproducible from a clean checkout
runtime patch script succeeds without ad hoc edits
all required smoke tests pass
prod-specific .env values are reviewed
rollback path is clear
```

The rollback path should include the previous `.env` version pins and enough
image/build cache or rebuild instructions to return to the known-good stack.

## Recommendation

Keep production on the current stable pins until the candidate version set has
passed the flow above. If a newer feature is required urgently, promote the
smallest version set needed for that feature and keep the existing runtime
patches in place during the first production rollout.
