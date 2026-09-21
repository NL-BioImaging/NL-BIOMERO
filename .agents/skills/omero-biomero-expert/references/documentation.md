# NL-BIOMERO documentation rules

## Audience determines content and navigation

| Category | Reader | What belongs here |
| --- | --- | --- |
| User Guide | Biologists and researchers operating the UI | Which screen to open, what to select, how to run an analysis and interpret its visible results. Not storage formats or implementation details. |
| System Administration | OMERO administrators/managers deciding what to enable, and IT staff configuring it | Purpose, benefits/costs, prerequisites, feature flags, configuration and operational consequences. Do not assume they want to write code or understand the internals. |
| Developer Guide | Coding image analysts and BIOMERO developers | How the feature works: data representations, identity checks, reconstruction, scientific semantics, APIs and useful code examples. |

"User-facing" means documentation for people using the software rather than
an internal development diary. It does not automatically mean **User Guide**.
Image analysts who work with code belong to the developer audience, even when
they do not develop BIOMERO itself. Concise writing can still be technical.

## Explain a feature once

- Lead with what the feature does and why it is useful. Let measured benefits
  speak for themselves; avoid hype or universal performance promises.
- Use descriptive titles, like "Shallow OME-Zarr Storage" or "Detached BIOMERO
  Workflows", not "Optional ...". Explain enablement in the page, not its title.
- Keep the admin overview short: a small benefits/costs table, configuration,
  and operational limits. Link to the developer explanation for internals.
- Start feature pages with purpose, practical enablement/demo-versus-upgrade
  behaviour, then a short "Summary for system administrators" note before
  detailed setup. Use a version notice only when the introduction version is
  verified. Reflect the actual control: deployment flag, admin setting or
  per-run action; do not invent a flag to make pages look uniform.
  Core setup pages such as Slurm integration can use the same practical note
  without being described as optional features.
- On the developer page, go deeper without repeating the admin overview or
  explaining the same lifecycle in several different forms. Prefer one useful
  Mermaid diagram over repeated prose when relationships are hard to follow.
- Keep prerequisites and compatibility limits explicit. The demo opts into
  features; custom upgrades must follow the applicable flags. Check actual
  gating behaviour: remote shallowing defaults on only within enabled shallow
  storage; it does nothing without the main shallow flag.
- Test plans, pending ACC smoke instructions, implementation history, workflow
  UUID inventories and deployment audits are not product documentation. Keep
  code examples when they help the intended reader perform a supported task.

## Evidence and performance claims

Public docs need a short, contextual summary, not the experimental ledger.
Distinguish stored bytes, transferred archive bytes, elapsed time, consumed CPU,
allocated HPC resources and monetary cost. State material comparison limits;
do not turn smoke timings into controlled speedup claims or extrapolate large
Plate performance linearly from image count alone.

Preserve detailed measurements outside the published docs before removing them.
The current shallow-Zarr archive is
`D:\workspace\.verification\biomero-shallower-release-notes`; private ACC raw
artifacts remain in its own evidence store. Keep original reports and structured
measurements with provenance and unknown fields, rather than inventing values.
Do not publish host-specific/private operational details with a public summary.

## Navigation and preview

Use existing audience categories in `docs/_navigation.rst`. Do not add a separate
top-level toctree in `docs/index.rst` for one optional feature. Folder names do
not determine sidebar grouping. Preserve existing URLs and cross-references
when rewriting a page unless a move is needed and its links are updated.
Order admin navigation from deployment and prerequisites to dependent features,
then optional extensions and maintenance. The core sequence is demo setup, full
deployment, analyzer/Slurm, importer administration, analyzer/importer
integration, and features that depend on that combined path such as shallow
storage. Keep it flat and group maintenance actions such as metadata refresh
with Backup & Restore through page order, not new categories. Keep the admin
index consistent with it. Use consistent title case while preserving official
product names such as BIOMERO.analyzer, BIOMERO.importer, OMERO.biomero and
OME-Zarr.

Use the local Sphinx procedure in `SKILL.md`, not a multiversion build. After
navigation changes, use `-E -a` so previously unchanged pages get the new sidebar.
Verify the user's exact generated page and report the build path. Check warnings
for touched pages and distinguish unrelated warnings from new problems. Opening
an old worktree's HTML or blaming browser cache is not a substitute for checking
the generated HTML itself.
