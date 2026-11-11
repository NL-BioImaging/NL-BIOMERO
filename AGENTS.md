# NL-BIOMERO

Runnable Docker Compose demonstration of the BIOMERO stack (OMERO.server/web,
OMERO.biomero, BIOMERO analyzer/importer/converter, Metabase) and the source for
the project's Docker Hub images. Not a site's production deployment.

## Read first

1. Shared rules for all component repositories:
   [`.agents/skills/nl-biomero-engineering/SKILL.md`](.agents/skills/nl-biomero-engineering/SKILL.md)
2. Independent PR review procedure:
   [`.agents/skills/nl-biomero-review/SKILL.md`](.agents/skills/nl-biomero-review/SKILL.md)
3. Stack, deployment, documentation and release runbook:
   [`.agents/skills/omero-biomero-expert/SKILL.md`](.agents/skills/omero-biomero-expert/SKILL.md)
   and the `references/` it routes to.

## Layout

- `docker-compose*.yml`, `deployment_scenarios/`: stack definitions.
- `.env`, `.env.shared`: demo feature flags and component versions.
- `web/`, `biomeroworker/`: image builds, `slurm-config*.ini`, processor override.
- `biomero-importer/`: git submodule (BIOMERO.importer).
- `docs/`: Sphinx documentation. `plans/`: release plans and acceptance records.
- `scripts/acceptance/`: reusable acceptance runners.

## Build and check

- Docs: `cd docs && sphinx-build -b html . _build_local` (current branch only).
- Stack: `docker compose up -d --build`; see the runbook before rebuilding.
- CI: `.github/workflows/` builds the docs and the Docker images.

## Related repositories

biomero (core), biomero-scripts, BIOMERO.importer, OMERO.biomero,
BIOMERO.shallower, biomero-schema, BIOMERO.ZarrViewer, all under
<https://github.com/NL-BioImaging>. Each has its own `AGENTS.md`.
