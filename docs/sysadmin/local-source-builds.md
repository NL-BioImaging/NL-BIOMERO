# Local source integration builds

The standard web and worker Dockerfiles continue to install published releases.
These optional Dockerfiles preserve the local integration fixes without requiring
machine-specific paths or image names in a release build.

## Web source build

Use `web/Dockerfile.source-local` with an explicit `BIOMERO_WEB_IMAGE` build
argument. The base must contain OMERO.web, OMERO.biomero, OMERO.Analysis and its
pinned Pyodide runtime in the Python 3.12 virtual environment. Set the named
build contexts `omero_biomero_src`, `analysis_src` and `viewer_src` to the selected
checkouts; `viewer_src` has `/src/biomero_zarr_viewer` as its package path.
The Analysis and Viewer frontends must already be built. The recipe builds the
host frontend and validates the Analysis wheel before installing it.

## Worker compatibility layer

Build `biomeroworker/Dockerfile.local-patches` from the repository root with an
explicit `BIOMERO_WORKER_IMAGE`. It checks for BIOMERO 2.9.0b11 and
biomero-shallower 0.1.0b5 before applying the bundled source replacements:

- Recursive quoted Zarr extraction filters and a nonempty input check before
  submitting workflow jobs. The corresponding core change is reviewed at
  https://github.com/NL-BioImaging/biomero/pull/53.
- A 1 MiB streaming copy buffer for shallow result export on mounted storage,
  preserving file metadata.

Do not reuse these full-module replacements with a different package version.
Remove the layer when the matching upstream fixes are installed.

## Server dataset paths

The server build includes the documented 0.7.1 pixel-buffer source patch in
`server/zarr-pixel-buffer/LOCAL-FIX.txt`. It resolves each resolution through
NGFF `datasets[].path`, including `s0` names. The build fails on a different
pixel-buffer version until the patch has been reviewed. Numeric dataset paths
remain supported.

Local Compose overrides, credentials, storage mounts, sample-data deletions and
one-off job recovery scripts remain outside these source integration recipes.
