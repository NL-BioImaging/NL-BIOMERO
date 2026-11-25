---
name: omero-biomero-expert
description: OMERO/BIOMERO expert runbook for NL-BIOMERO deployments, documentation and release announcements. Use for writing or building NL-BIOMERO docs, preparing release messages, debugging and operating OMERO.server/web, OMERO.biomero, BIOMERO analyzer/importer/converter, Metabase dashboards, Docker Compose, Slurm/HPC, storage permissions, SSH access, logs, and Postgres verification.
---

# OMERO/BIOMERO Expert

Read the shared [NL-BIOMERO engineering rules](../nl-biomero-engineering/SKILL.md)
first; they cover engineering principles, branches and pull requests, agent
guidance and local checkout cleanup for every component repository.

Use this skill for NL-BIOMERO work on dev or prod. Prefer inspection over guesses: identify the active host, read the relevant compose/env/log state, verify data paths and permissions, then run a focused smoke test.

Never print secrets. Mask `.env`, container env, Metabase datasource JSON, passwords, secret keys, JWTs, and tokens in user-facing output.

## Development Branches and Pull Requests

Follow the shared [branch and pull request rules](../nl-biomero-engineering/SKILL.md#development-branches-and-pull-requests).
NL-BIOMERO clones may also reference an OME upstream, so verify the target
repository is `NL-BioImaging/NL-BIOMERO` before opening a PR. Use proportionate
local verification before a release or a change without suitable CI coverage.

## Repository Scope and Example Contract

`NL-BIOMERO` is the runnable local Docker Compose demonstration and the source
used to build the project's Docker Hub images. It is not the repository for an
institution's production HPC deployment; those deployment-specific values live
in separate site repositories.

### Feature flags and demo defaults

Compatibility means keeping supported deployments working. Correct bugs by
default and test existing execution modes; do not preserve faulty behavior
behind a default-off switch merely to call the change backward compatible.

Implement new optional features behind a feature flag. A missing, empty or
explicitly false flag must leave the feature disabled, preserving existing
behavior for deployments upgrading without configuration changes.

NL-BIOMERO is the full-featured demonstration: explicitly enable new features
in its supplied `.env` and `.env.shared` defaults. Keep applicable Compose
wiring in sync, with false fallbacks for feature-enablement flags rather than
implicitly enabling them in containers or library defaults. Documentation must
distinguish the enabled demo configuration from opt-in upgrades elsewhere.
Verify enabled, false, missing and empty flag behavior when adding a feature.

### Deployment flags versus administrator-managed runtime settings

Container feature flags belong in `.env`/`.env.shared` and applicable Compose
environments: they control feature availability and may require recreation or
restart. Do not treat this as permission to put every BIOMERO setting in env.

Runtime and Slurm Init-managed settings belong in the canonical
`web/slurm-config.ini`, so OMERO.biomero administrators can manage them without
editing a deployment. This includes worker/CPU counts, partitions, memory/time
limits and image acquisition settings. The remote shallower helper image is not
a setting: Slurm Init installs the image of the shallower package installed in
the worker. Keep
alternative INI examples aligned where applicable. Do not inject matching env
overrides into web or biomeroworker, including empty values or fallback defaults:
env precedence prevents the admin interface's saved INI values from taking effect.
Library support for an env override is not a reason to enable it in the demo.

Every administrator-editable setting must have a matching Runtime or Slurm Init
indicator in OMERO.biomero and accurate follow-up instructions in these docs.
Verify the consumer rather than inferring timing from the section name. Shared
indicators are sufficient for homogeneous groups; mixed sections show both and
classify each field/subgroup. Runtime applies to new runs or requests after
saving. Slurm Init installs helper images/generated scripts or rebuilds analytics.
For Shallow Zarr, mark remote/local selection and the helper resource limits as
runtime; explain that first remote use requires Slurm Init to have installed the
helper image, and that after an upgrade Slurm Init must run again to install the
new one (until then results stay full). Keep deployment
flags/restarts distinct from these INI-managed settings. Update the sibling web
plugin and this repository's admin docs together when their behavior changes.

Respect component boundaries: the importer has its own settings and does not
read `slurm-config.ini`; do not force importer settings into the Slurm INI or
inject them as overrides into web or biomeroworker. The importer validates
remote shallow results against its own installed shallower package, so no
helper version needs to be aligned by configuration. Do not remove required
validation inputs or weaken validation to simplify configuration.

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

Before preparing a release, the release coordinator checks every component's
third-party dependencies (Python packages, container base images, front-end
packages) for newer versions and security advisories (for example
`pip list --outdated` and `pip-audit` in a fresh environment, and each
repository's open Dependabot alerts:
`gh api "repos/NL-BioImaging/<repo>/dependabot/alerts?state=open"`). Every
component repository has Dependabot alerts enabled; report one that does not. Take patch releases; take minor releases when
their changelog shows no breaking change and the tests pass; file a story on
the board for each major release, because it usually needs code changes. Raise
the pins in the components' own PRs before step 1, and mention notable
upgrades, especially security fixes, in the release notes.

Before publishing any component prerelease for a release, the release
coordinator lists every item on the BIOMERO Roadmap board with that
**Release** value that is not Done, in all repositories (the filtered board
`?filterQuery=release:"X.Y.Z-beta.N"`, or the project GraphQL API). A
component is ready for its prerelease only when no open story for that
release still needs a change in it, including sub-issues and parent stories
tracked in other repositories. Finish such a story first, or move it to
another release with the maintainer's agreement, so each component gets one
prerelease per release instead of small follow-up prereleases. Parent
stories whose PRs only reference them are not closed automatically: close a
parent with a summary of its PRs when all its sub-issues are done, and
reopen the question with the maintainer when an open parent still has work
that no sub-issue covers.

Follow dependency availability, rather than assuming a release announcement
means all artifacts are ready:

1. Publish changed schema contracts first. If needed, publish the shallower
   package/container next, using those published contracts.
2. Update importer dependencies to the required published schema/shallower
   versions, merge through its PR and publish its prerelease. Verify PyPI and
   container availability before consumers depend on it.
3. Update BIOMERO core's importer/schema lower bounds where needed, then merge
   and prerelease core and biomero-scripts together with the same version
   number (for example core `2.9.0b24` with scripts `v2.9.0-beta.24`). Scripts
   must match the released core/importer APIs; verify their release tag is
   available.
4. Update OMERO.biomero to published core/importer dependencies (it comes late
   because it depends on both), merge and prerelease it. Verify its PyPI package contains no feature-branch dependencies.
5. Prepare NL-BIOMERO last, on a `release/X.Y.Z-beta.N` branch with its own
   PR titled `Release X.Y.Z-beta.N` (stable: `release/X.Y.Z`, `Release X.Y.Z`);
   ACC and other readers find it by these names. Open that PR as a draft as
   soon as work on the next prerelease starts:
   its plan (`plans/releases/X.Y.Z-beta.N.md`) keeps a release test checklist,
   and every component PR or review that finds behaviour needing a test in a
   real stack adds it there, with its source PR. Step 6 runs every item
   locally; mark which items the ACC smoke tests cover and ask for the rest to
   be added to ACC. Set the **Release** field on the BIOMERO Roadmap board for
   every issue and PR that goes into the release, in any repository (add PRs
   to the board), and `Later` for deferred stories. The release PR links the
   filtered board (`?filterQuery=release:"X.Y.Z-beta.N"`); before tagging,
   check that list against what is merged, and move released items to Done.
   `master` must always work with the versions pinned in `.env`. Every
   NL-BIOMERO PR targets `master`; one that needs an unreleased component
   version (code, hooks, INIs or docs for a new setting) stays a draft marked
   "On hold" until that version is published and its pin on `master` is
   bumped (a small PR right after each component prerelease). Cut the release
   branch from `master` when the release is prepared; it carries only the
   release work (version, badges, notes, test checklist). Merge `master` into
   it when `master` moves on, never the release branch into `master` except
   through the release PR. In the release PR: advance the clean importer submodule to its
   released commit, pin the prereleased component versions in `.env` and `.env.shared`, restore release
   Dockerfile blocks, and align applicable Compose wiring, INIs and docs.
   Preserve deployment-specific paths/credentials and the enabled demo flags.
   Validate resolved build arguments, shared config mounts and feature settings.
   Keep the documentation front page complete: `docs/index.rst` shows every
   released component with its version badge, repository link and licence,
   and `docs/conf.py` reads each version from `.env`. When the release adds a
   component (or a component whose version is pinned elsewhere, such as a
   Python dependency), add its badge, link, licence and version source in this
   PR, so readers can see which versions were released together.
6. Test that exact setup locally before merging: build and run the stack from
   the release branch with `docker-compose.yml`, the release Dockerfile blocks
   and the `.env` pins (`docker-compose-dev.yml` is for live OMERO.biomero
   frontend development), against NL-BIOMERO-Local-Slurm or NL-BIOMERO-Local-Slurm-GPU, and
   run the release's acceptance cases. Record the plan and outcome in
   `plans/releases/X.Y.Z-beta.N.md` and `plans/releases/X.Y.Z-beta.N-local-acceptance.md`,
   following [the 1.8.0-beta.13 plan](../../../plans/releases/1.8.0-beta.13.md)
   and [its local acceptance report](../../../plans/releases/1.8.0-beta.13-local-acceptance.md).
   Component fixes go back through steps 1-4.
7. On the user's unconditional acceptance of the release PR (see the merge
   rules in the shared engineering skill), squash-merge it into `master`.
8. Publishing the GitHub prerelease, such as `vX.Y.Z-beta.N`, needs its own
   explicit authorization. Mark it as a prerelease. GitHub release tags
   own package versions; do not introduce source-file version bumps. Updating
   deployment references in `.env` is separate from package versioning.
9. The published NL-BIOMERO prerelease builds all stack containers for ACC to
   pull. Verify every required image build/push succeeds before handing the
   pinned image tags to ACC for redeployment. Coordinate its smoke test before a full-Plate test;
   do not automatically start deployment or analysis jobs.
10. ACC reports its findings as commits on the deploy-omero branch it deploys
   from (currently `acc-direct-vfs`, under `plans/acceptance-issues/X.Y.Z-beta.N/`),
   because it cannot create GitHub issues. That branch is ACC's: read it,
   never push to it. Only those reports count as ACC findings; other new
   issues are not picked up as release work. While ACC tests, the coordinator
   polls the branch, checks each claimed cause in the code, files the finding
   in NL-BIOMERO with a sub-issue in the component that owns the fix, and has
   workers fix it. A finding that blocks acceptance (a regression or a bug in
   the release's new work) gets the next beta as **Release**; a pre-existing or
   minor one gets `Later`. The issue body names the beta it was found in. When
   ACC's report is final, fold every blocking fix into one new beta and
   release it through steps 1-9; its release notes and PR are the answer to
   ACC, listing each finding with its issue and outcome. ACC then redeploys
   and retests, and the loop repeats until ACC accepts. Stable X.Y.Z is
   released from the accepted beta. A stable release ships no prerelease
   anywhere: before it, the coordinator releases every prerelease dependency
   (for example BIOMERO.shallower and biomero-schema) as stable from its
   accepted beta, raises the requirement floors of the components that use it
   to that stable version, and checks that installed packages, pins and helper
   images (the shallower image follows the installed shallower version) are all
   stable. Publish in dependency order, each after everything it requires:
   biomero-schema, BIOMERO.shallower, BIOMERO.importer, BIOMERO core (its
   `full` extra requires the importer), biomero-scripts (same version as core),
   OMERO.biomero; then NL-BIOMERO. Open the next beta's release PR as soon as
   the first blocking finding is filed, so ACC can follow it without GitHub
   authentication: the public API
   `https://api.github.com/repos/NL-BioImaging/NL-BIOMERO/pulls?state=all&head=NL-BioImaging:release/X.Y.Z-beta.N`,
   the plan `plans/releases/X.Y.Z-beta.N.md` on that branch, and finally the
   published release and its image tags.
   At every handoff, the coordinator checks that ACC's deployed configuration
   matches the release: image tags and also the container versions pinned in
   configuration files (converter in `biomero-config.json`, workflow versions
   in the Slurm config). The release plan lists these pins, and "unchanged"
   is never assumed.
   Commits on the deployment branches start with a category so the
   coordinator reads only what matters: `[finding]` (a classified finding
   for the coordinator), `[report]` (checkpoint or progress), `[verdict]`
   (final acceptance verdict), `[deploy]` (deployment, proxy or config
   change: the input for the acceptance/production comparison), `[harness]`
   (test tooling), `[backup]` (backup and restore) and `[docs]` (guidance,
   plans). The coordinator polls for `[finding]`, `[report]` and `[verdict]`,
   and reads `[deploy]` for the comparison; the rest is noise to it.

A stable release PR carries a **production plan** instead of an acceptance
plan: `plans/releases/X.Y.Z.md` says what production must do to upgrade from
its running version (images, settings, Slurm Init, migrations, downtime and
its order, backup before the upgrade, rollback, post-upgrade checks). Before
writing it, compare the acceptance and production branches of the private
deployment repository (production deploys from its production branch as
named in that repository's guidance). The first comparison covers the main
deployment files; record the compared commits in the plan and later compare
only the commits since then: list deployment changes (proxy, compose/units,
config) that acceptance has and production lacks, leaving out what belongs
to one side by design (acceptance testing tooling; production backup and
restore). The plan is public, so it names the changes generically; site
details stay in the deployment repository. Also draft the image.sc
announcement as a reply in the NL-BIOMERO thread, in the style of the earlier
announcements there: shorter than the release notes, written to make users
want to upgrade, linking the notes. The maintainer posts it.

Structure the release PR description as in previous release PRs (for example
NL-BIOMERO #66): component
checklist (version, PR and published artifact per component), configuration for
acceptance, ACC acceptance criteria, validation and publication status, local
acceptance report link and published image verification. Draft the release
announcement and component release notes with
[references/release-announcements.md](references/release-announcements.md) and
[references/component-release-notes.md](references/component-release-notes.md).

Use the appropriate version format: PyPI pins use normalized versions such as
`1.5.0b6`, scripts refs use Git tags such as `v2.9.0-beta.9`, and container refs
use the actually published Docker tags such as `1.8.0-beta.6`. Stable container
releases cascade to full-version, major/minor and `latest` tags; prereleases do
not update stable aliases. Pin prerelease images explicitly for ACC, including
the shallower. The helper image tag is derived from the installed shallower
package version (`0.1.0b11` becomes `0.1.0-beta.11`), not configured.

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

### Ownership and detached execution

For processor, workflow or recovery changes, read the shared
[BIOMERO design and ownership guidance](https://github.com/NL-BioImaging/biomero/blob/main/.agents/skills/biomero-dev/SKILL.md#design-reuse-and-responsibility).
Keep the general principles there rather than copying them into this runbook.

`biomeroworker/processor.py` is an OMERO execution adapter and process supervisor.
Its detached workers reuse the workflow pipeline from `biomero-scripts` and
launcher/claim/resume state from `biomero.detached`. Keep worker lifecycle,
concurrency, OMERO sessions and restart discovery here; reuse core's HPC
operations and recovery/reconciliation instead of adding another implementation.
Check existing processor supervision before introducing a new worker/watchdog.
Move reusable domain behavior to core and reusable OMERO behavior to the shared
script pipeline, preserving the core/OMERO dependency boundary.

A processor restart should resume eligible unfinished work using persisted IDs
and progress, not blindly repeat submission/import or reset recovery policy.
Distinguish a transient connection loss, an interrupted process, intentional
cancellation and a terminal workflow attempt. Restart supervision must not
silently resurrect terminal attempts or interpret lost observation as HPC failure.

Detached execution is optional but strongly recommended for long workflows;
preserve the supported inline path and test both modes for shared changes.
A possible detached-only direction for 3.0 is not a current removal decision.

### Script environment forwarding

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

- [references/documentation.md](references/documentation.md): required for documentation work; audience boundaries, concise feature explanations, measurement evidence, navigation and local preview verification.
- [references/release-announcements.md](references/release-announcements.md): release-message style, stable-to-stable scope, component versions, upgrade actions and documentation links. Read before drafting release announcements.
- [references/component-release-notes.md](references/component-release-notes.md): concise component release bodies, shipped PR/issue links and stable/beta scope. Read when coordinating component notes or linking them from a stack announcement.
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

The docs live in `docs/` and use Sphinx, typically from a pre-created venv in `docs/venv`.

Read `references/documentation.md` before writing or reorganizing docs. A request
for user-facing prose does not automatically mean the **User Guide** category.

To build the **current branch only** (no multi-version):

```bash
cd docs
venv/bin/sphinx-build -b html . _build_local   # Windows: .\venv\Scripts\sphinx-build
```

After changing navigation, or when any page shows stale sidebar content, force
all pages to be regenerated with `-E -a -b html . _build_local`. Check the exact
HTML page the user is viewing, not just the homepage. If using another worktree,
state its source branch and output path; do not silently open an older build.

Output is written to `docs/_build_local/`. Open
`docs/_build_local/index.html` in a browser (as a `file://` URL of the absolute
path in your checkout).

Do **not** use `make html` or `sphinx-multiversion` — those build all tagged versions and are slow. The direct `sphinx-build` call above is the correct approach for local preview.

The venv already has all required packages (`Sphinx`, `myst-parser`, `sphinx-rtd-theme`, `sphinxcontrib-mermaid`, `sphinx-multiversion`). No install step is needed.
