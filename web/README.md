# BIOMERO Web Container

This container extends the standard OMERO.web with BIOMERO-specific functionality and UI enhancements.

## Included Components

- **OMERO.biomero** - Unified importer and analyzer interface
- **OMERO.forms** - Custom metadata forms 
- **Enhanced Login Page** - NL-BioImaging branding with institutional customization support
- **UI Improvements** - Better button icons and styling

## Customization

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

For local development, modify the Dockerfile and rebuild:
```bash
docker-compose build --no-cache omeroweb
docker-compose up -d omeroweb
```

---

Thank you for using NL-BIOMERO!
