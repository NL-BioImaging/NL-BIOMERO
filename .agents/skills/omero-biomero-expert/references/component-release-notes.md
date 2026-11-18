# Component release-note convention

This is the single maintained writing guide for NL-BIOMERO component releases.
Component agent instructions link here on `master`; read the current version
when drafting notes. Change the format here instead of copying it into each repo.
Repository-specific build, test and publication procedures remain in their repos.

## Format

Write a short GitHub release body for people using or integrating the component.
Aim for roughly 100-200 words; a small patch can be much shorter. Use one opening
sentence, a few outcome-focused bullets under **What's Changed**, an **Upgrade
Notes** paragraph only when action or compatibility matters, and **Full Changelog**.
Group related PRs in one bullet. Omit empty sections and link detailed documentation
instead of copying setup instructions, test logs or a README into the notes.

Patch and security releases are shorter still: mirror the previous patch release
(for example v1.7.3) line for line. Say what it is and what it is based on, what
changed with one link to the advisory or announcement, that everything else is
unchanged, and the changes/compare line. Keep verification details in the PR.

For BIOMERO core, and any release that pins a new core version, the **Upgrade
Notes** always say whether `init_slurm` must run, and whether stored data
changed: new or changed events, upcasters, or view tables that need a rebuild
by replaying events. A full replay can take a long time on installs with many
old events, so say whether a partial rebuild is enough
(`BIOMERO_ANALYTICS_REBUILD_START_TIME` / `BIOMERO_ANALYTICS_REBUILD_DAYS_AGO`)
or skipping the replay is safe, and whether a downgrade still works afterwards.

## Select the changes

- For a stable release, compare with the previous stable release and summarize
  the whole beta series in its final form. For a successive beta, compare with
  the previous beta in that series; the first beta starts from the prior stable.
  For a first-ever stable release, summarize the initial capabilities and beta
  fixes, label it as the first stable release, and use the repository history
  when there is no earlier stable tag to compare.
- Verify the actual release commit, diff and merged PRs. Link shipped PRs and
  the issues they resolve beside the relevant bullets. A closed PR is not
  necessarily merged; a closed issue is not necessarily fixed by this release.
  Include shipped direct-commit fixes where relevant. Use a short additional
  PR list only if useful changes are not represented by the main bullets.
- Describe an upstream workaround as a workaround; do not imply the upstream
  issue is closed. Use full links for cross-repository PRs, issues and releases.
- Call out changed defaults, breaking behavior and required companion versions
  only when relevant. Verify versions against published artifacts; do not obtain
  a stable version by removing a beta suffix. Do not claim live acceptance from
  unit tests or recovered runs. Keep internal deployment details out of notes.
- End with a link labelled **Full Changelog**, using the actual Git tags in
  `https://github.com/NL-BioImaging/REPOSITORY/compare/PREVIOUS...CURRENT`.
  GitHub-generated notes are useful source material; edit them into this format.

NL-BIOMERO links to these component notes for detail and owns the stack-wide
summary and coordinated upgrade actions. Keep these notes useful independently.
This is writing guidance; existing release procedures and authorization still apply.

## Component emphasis

| Component | Emphasize when changed |
| --- | --- |
| biomero-schema | Contract/validation changes and reader/writer compatibility; distinguish package versions from wire/schema identifiers. Contracts alone do not enable deployment features. |
| BIOMERO.shallower | Shallowing, reconstruction, identity/report compatibility, and matching helper image/receipt versions. Distinguish retained storage savings from transfer or runtime claims. |
| BIOMERO.importer | Import completion, registration, mandatory provenance and identity behavior; required schema/shallower/converter updates and service restart actions. |
| biomero | Library APIs, SSH/Slurm, transfer/recovery limits and changed defaults; link the matching scripts release where needed. |
| biomero-scripts | Workflow/data/admin script behavior and the matching core release. Harness-only PRs on test-suite are validation context, not production changes in the scripts tag. |
| OMERO.biomero | Visible web/admin changes; distinguish settings for new runs from Slurm Init or container restart actions. |
| BIOMERO.ZarrViewer | Viewing/rendering/export and format support; distinguish standalone capabilities from integrations requiring another plugin or provider. |
| biomero-converter | Affected input/output formats, conversion correctness, metadata preservation and dependency compatibility. |
| OMERO.forms | Form design, submission, history and annotation storage; compatibility with existing forms/data and any migration. |

## Stack announcement

Keep [the established NL-BIOMERO feature-release style](release-announcements.md).
Its linked Subcomponent Updates identify the versions actually bundled.
Summarize their combined user benefit and coordinated upgrade actions; link
the component release bodies for individual fixes and PR/issue references.
Do not copy every component changelog into the stack announcement. A component
release may offer capabilities not enabled in this stack; describe only what
NL-BIOMERO actually integrates. Reuse unchanged stable components without
inventing new releases for version-number alignment.
