# BIOMERO Web Container

This container extends the standard OMERO.web with BIOMERO-specific functionality and UI enhancements.

## Included Components

The `analysis_integration` branch installs and validates the embedded **Data
Analysis** host beside **Import** and **Analyze**. Keep
`INTEGRATE_DATA_ANALYSIS=TRUE` in the demo; other deployments remain disabled
until explicitly enabled. See the [administrator guide](../docs/sysadmin/data-analysis.rst).

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

The web Dockerfile uses ordinary `pip install` commands for released components.
OMERO.biomero 1.7.0b7, Analysis 1.0.0 and WorkflowSkills 0.4.0 come from PyPI.
Analysis's identical wheel is also available on its GitHub Release for users
who prefer that distribution channel. This deployment uses
`OMERO_ANALYSIS_VERSION` with the normal PyPI installation; there is no
custom downloader, manifest parser, source build, SDK installation or fallback.
ZarrViewer keeps its existing single PyPI installation.

The packaged Analysis defaults are loaded with normal OMERO configuration.
`54-configure-data-analysis.py` then applies the runtime opt-in flag, like the
existing viewer startup script. A missing/false flag removes only Analysis's
app and UI registrations, including stale registrations on upgrades. It never
deletes workspaces, notebooks or results. Enable the demo's `analysis` Compose
profile and set `DQW_API_TOKEN` to use the local worker.

Component release validation belongs in the component repositories. This
repository tests its startup/configuration behavior and the resulting web image.

For local development, modify the Dockerfile and rebuild:
```bash
docker-compose build --no-cache omeroweb
docker-compose up -d omeroweb
```

---

Thank you for using NL-BIOMERO!
