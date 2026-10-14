# Embedded Data Analysis host

The integration image builds OMERO.biomero from the full commit in
`OMERO_BIOMERO_REF`. That commit combines the current upstream backend and its
single-store dependencies with embedded Analysis, cached-image selection fixes,
input validation and authenticated monitor renewal. The former 1.6.1 backport
patch has been removed; the maintained source now lives in OMERO.biomero.

Both `.env` and `.env.shared` identify the same reviewed source. The host's
integration version is `1.7.0b6+analysis.g<short-commit>` and the build checks
that its suffix matches the supplied commit. A moving branch, tag or missing
commit is rejected. This is an integration build, not a published host release.
Once a released host includes these changes, replace the source preparation
stages with that release's wheel after running the same checks.

The preparation stages install the frozen Yarn lock, run frontend tests,
rebuild assets and build a wheel containing the host view, template and frontend.
The final image installs the exact `BIOMERO_VERSION` and
`BIOMERO_IMPORTER_VERSION` alongside that wheel. Package assertions compare
normalized versions so Docker tag `1.5.0-beta.8` matches Python `1.5.0b8`.
The build also runs the host backend suite and Analysis's host-capability check.

Analysis 1.0.0 remains a checksum-verified GitHub Release wheel; WorkflowSkills
0.4.0 and Viewer 0.7.1 remain their existing released packages. All maintained
worker scenarios and the cache smoke use DataQueryWorker 0.2.2 at the same
verified OCI image digest.

Set `INTEGRATE_DATA_ANALYSIS=TRUE` to expose Data Analysis beside Import and
Analyze. Verify source selection, saved-workspace resume and group preservation
in the authenticated deployment. With integration disabled, standalone
navigation must remain available. Unit tests and a successful image build do
not replace those deployment checks.

## Existing deployment considerations

Preserve site credentials, group mappings, data mounts and local workflow
configuration when advancing the checkout. Do not commit runtime databases or
scientific data. The uncommitted local reader override for NL-BIOMERO issue #42
is independent of Analysis: retain it until a tested reader release replaces
its Zstandard and metadata-declared pyramid-path support. This branch does not
claim to resolve the separate result-attachment issue biomero-scripts #37 or
workflow-version descriptor issue OMERO.biomero #32.
