# NL-BIOMERO release announcements

## Match the maintainer's feature-release style

Read the actual bodies of the last two or three full feature releases before
drafting. Maintenance patches and terse prereleases are not the style baseline.
Useful examples are [v1.7.0](https://github.com/NL-BioImaging/NL-BIOMERO/releases/tag/v1.7.0),
[v1.6.0](https://github.com/NL-BioImaging/NL-BIOMERO/releases/tag/v1.6.0) and
[v1.5.0](https://github.com/NL-BioImaging/NL-BIOMERO/releases/tag/v1.5.0).
Retrieve newer examples when available; do not infer style from titles alone.

Use the familiar `What's Changed` structure: linked **Subcomponent Updates**,
**Major Features**, practical **Upgrade Notes**, other improvements where useful,
**Documentation**, and **Full Changelog**. Adapt section names and length to the
release. Keep the tone direct and approachable. Explain each addition through
what researchers or administrators can now do, with short supporting bullets.
Use configuration snippets only when they make an upgrade action clearer.

## Establish what is actually shipping

- Compare the proposed release with the previous stable release, not just the
  preceding beta. Cross-check merged code, deployment pins and component notes;
  later prereleases can reverse earlier behavior. Do not promote an already
  stable feature as new or include an unmerged sibling integration.
- List the significant bundled component versions and link their release notes.
  Use the actual Git/Docker tag and normalized Python version where applicable.
  Never invent final component releases by stripping beta suffixes. If final
  versions are not published, identify the draft's current prerelease baseline
  and the version/link substitutions needed before publication.
- Cover the whole release, rather than only the feature discussed most recently.
  Summarize visible fixes and improvements; omit the implementation diary,
  internal deployment names, test UUIDs and intermediate version-only releases.
- Keep benefit claims proportional to evidence. Storage deduplication does not
  establish faster end-to-end processing. Do not turn small-fixture timings into
  full-Plate performance claims or promise universal recovery from outages.

## Make adoption clear

For each substantial optional feature, state its actual enablement: deployment
flag, administrator setting, per-workflow choice or maintenance action. Explain
enabled demo defaults versus existing-deployment opt-in. For upgrades from an
already fully configured stable stack, focus on new actions and link established
prerequisites rather than repeating initial installation.

Call out required coordinated component updates, Slurm Init / Check Setup,
helper-image and importer-trust alignment, proxy/storage requirements, and any
real migration. State format defaults and existing-data compatibility accurately.
Link detailed setup instructions instead of reproducing the full runbook.

Link directly to feature-specific online manuals. Verify their paths against the
release's documentation configuration: `/latest/` follows stable releases and
can still show the old manual while drafting; `/master/` carries prerelease
documentation. Versioned stable URLs become available after the release docs
build. Check publication and link availability before claiming either is ready.

End with the stack comparison from the previous stable release, plus component
comparisons when useful, following the historical feature-release examples.
Drafting or updating this guidance does not authorize publishing a release.
