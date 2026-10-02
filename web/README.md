# BIOMERO Web Container

This container extends the standard OMERO.web with BIOMERO-specific functionality and UI enhancements.

## Included Components

The `analysis_integration` branch builds and validates the embedded **Data
Analysis** host beside **Import** and **Analyze**. Keep
`INTEGRATE_DATA_ANALYSIS=TRUE`; see [the host build contract](biomero-analysis-host.md)
for the reviewed stable-backend backport and rebuild checks.

- **OMERO.biomero** - Unified importer and analyzer interface
- **OMERO.Analysis** - Browser-local Methods, Pipelines, Notebooks, and Assistant workspace
- **OMERO.forms** - Custom metadata forms 
- **BIOMERO OME-Zarr Viewer** - Optional read-only image, label and plate viewer
- **Enhanced Login Page** - NL-BioImaging branding with institutional customization support
- **UI Improvements** - Better button icons and styling

## Customization

The image includes the BIOMERO OME-Zarr Viewer and its compiled frontend. The
viewer is registered only when
`BIOMERO_ZARR_VIEWER_ENABLED=TRUE`; missing, empty or false values disable it.
Startup preserves other plugins and removes the viewer registration when disabled.
Use the Nginx endpoint to view data. See the
[deployment and upgrade guide](../docs/sysadmin/zarrviewer.rst).

### Login Page Branding

The default NL-BioImaging branding can be customized using Docker volume mounts:

**Simple logo replacement:**
```yaml
- "./your-logo.png:/opt/omero/web/venv3/lib/python3.12/site-packages/omeroweb/webclient/static/webclient/image/login_page_images/nl-bioimaging-banner.png:ro"
```

**Complete branding (footer, colors, text):**
```yaml
- "./custom-login.html:/opt/omero/web/venv3/lib/python3.12/site-packages/omeroweb/webclient/templates/webclient/login.html:ro"
```

See `local_omeroweb_edits/pretty_login/login-amsterdamumc.html` for a complete example with inline CSS.

After changes: `docker-compose down omeroweb && docker-compose up -d omeroweb`

## Development

### Analysis production distribution

Set `OMERO_ANALYSIS_VERSION=X.Y.Z` to an exact tagged OMERO.Analysis GitHub
Release containing both application/SDK wheels and `manifest.json`. Compose
rejects an absent pin. The web Dockerfile prepares `dist/wheelhouse` in an
isolated build stage, downloads only `releases/download/vX.Y.Z/` assets,
and verifies SHA-256, sizes, archive validity and embedded package versions.
The final image installs Analysis using `--no-index --find-links`, and uses
the startup/configuration files packaged in that wheel. Third-party dependencies
are resolved during preparation; running containers do not fetch GitHub assets.

The SDK has an independent version recorded in the manifest. It is retained
in preparation for notebook authors and is not installed on the web server.
Existing BIOMERO components keep their deployment sources. This migration
changes only OMERO.Analysis and its notebook SDK distribution.

There is no branch, `latest`, package-index, or older-version fallback. Missing
releases, missing wheels and wrong hashes stop the build. Existing source-only
releases (including the current v0.14.0 without wheel assets) cannot satisfy this
contract; publish a new release with the updated Analysis workflow before
advancing the deployment pin. Keep the running image until that release exists.

The dependency-free scripts in `web/release/` are vendored from
`OMERO.Analysis/scripts/analysis_release.py` and `download_analysis_release.py`.
Update the copies together and run `tests/test_analysis_release.py` after changes.
For development use an Analysis checkout and its `build-docker-image.ps1` helper;
the production web Docker build must not build Analysis from Git source.

For local development, modify the Dockerfile and rebuild:
```bash
docker-compose build --no-cache omeroweb
docker-compose up -d omeroweb
```

---

Thank you for using NL-BIOMERO!
