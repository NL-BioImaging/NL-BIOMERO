# Embedded Data Analysis host

The `analysis_integration` deployment must contain the Data Analysis host as
well as the Analysis package. A stock OMERO.biomero wheel can provide importer
storage and Analyze while omitting the embedded host, which causes the Analysis
middle pane to fall back to standalone navigation.

`biomero-analysis-host.patch` carries the existing host from OMERO.biomero's
`analysis_integration` commit `75adc977a2de5ab86e032bc25713a8185bbc841e` onto the
released `v1.6.1` backend (`fc387a2e941f517e202e0ad49d78871a488b4fd6`). It preserves
the newer Analyze behavior, importer mapping APIs and dependency requirements.
The patch includes the merged frontend source and reproducible Yarn lock.
Compiled JavaScript and wheel binaries are built, not committed in this repo.

The Docker preparation stages apply the patch only to that exact baseline,
run the 43 frontend tests, rebuild the assets, and build an OMERO.biomero wheel
identified as `1.6.1+analysis.host3`. This is an integration build, not an
upstream release. The final image checks its declared version and the complete
host view/template/frontend contract before accepting the build. Analysis itself
is downloaded from its exact GitHub Release and installed from verified wheels.

Set `INTEGRATE_DATA_ANALYSIS=TRUE`. The BIOMERO header then offers Import, Analyze
and Data Analysis; OMERO's redundant Analysis top link is removed. The center
pane carries source/Workspace bindings to the BIOMERO host, which opens the
same-origin Analysis iframe. With integration disabled, standalone behavior is
retained. A missing or partially installed host must fail image validation.

When a released OMERO.biomero version includes the complete host, replace this
backport with that release after verifying source selection, workspace resume,
notebook restoration, storage compatibility and both Import/Analyze screens.
Do not drop the host by installing a stock wheel during an Analysis update.

The workflow and import monitors renew their user-locked, 30-minute Metabase
tokens on opening, every 20 minutes while visible, and when an overdue browser
tab returns to the foreground. A failed renewal keeps the current dashboard
and offers Retry monitor beside the error. Only the dashboard iframe reloads;
OMERO forms and running workflows are unaffected. Metabase may reset dashboard
filters on renewal. The installed image also runs 25 backend regression tests,
including rejection of invalid input IDs and dashboard user-locking tests.
