# OMERO Web Container

The OMERO web container provides the web interface with extensive customizations and plugin integrations, specifically designed for development workflows.

## Overview

Based on `openmicroscopy/omero-web-standalone`, this container includes:

- Custom web interface modifications
- Multiple OMERO plugins pre-installed
- Development-friendly configuration
- Integration with external services (Metabase, BIOMERO)

## Development Workflow

### Development Mode

The development docker-compose (`docker-compose-dev.yml`) handles the web container specially:

- **Container stays alive** without starting OMERO.web automatically
- **Manual control** over web service restarts for live development
- **Volume mounts** for real-time code changes

**Why this approach?**
For active plugin development, especially with the OMERO.biomero plugin, you need frequent restarts and live code changes.

### OMERO.biomero Plugin Development

The primary development target is the [OMERO.biomero plugin](https://github.com/Cellular-Imaging-Amsterdam-UMC/OMERO.biomero/tree/main):

1. **Clone the plugin** in an adjacent folder to NL-BIOMERO:

```bash
cd /path/to/workspace/
git clone https://github.com/Cellular-Imaging-Amsterdam-UMC/OMERO.biomero.git
# Your structure should be:
# workspace/
# ├── NL-BIOMERO/
# └── OMERO.biomero/
```

2. **Follow the plugin README** for development setup
3. **Use the development container** for testing

**OMERO.biomero Features:**
- **React.js user interface** for modern web interactions
- **Django API** for service integration
- **Service orchestration** for BIOMERO workflows
- **Version 2.0 developments** with enhanced UI/UX

## Key Installed Plugins

### Core OMERO Plugins

```dockerfile
RUN /opt/omero/web/venv3/bin/pip install \
        omero-figure \           # Figure creation and export
        omero-iviewer \          # Advanced image viewer
        omero-fpbioimage \       # FPBioimage integration
        omero-mapr \             # Metadata annotation and search
        omero-parade \           # Plate analysis and review
        omero-webtagging-autotag \ # Automatic tagging
        omero-webtagging-tagsearch # Tag-based searching
```

### Supporting Libraries

**OMERO.forms Plugin**
- Purpose: Dynamic form creation for data collection
- Special handling: Automated user creation via startup scripts
- Scripts: `44-create_forms_user.py` and `45-fix-forms-config.sh`
- Benefit: No manual setup required for forms functionality

**BIOMERO.importer (formerly OMERO ADI)**
- Source: [OMERO-Automated-Data-Import](https://github.com/Cellular-Imaging-Amsterdam-UMC/OMERO-Automated-Data-Import)
- Purpose: Automated import order creation
- Integration: Used by OMERO.biomero for import workflows

**BIOMERO Library**
- Source: [biomero](https://github.com/NL-BioImaging/biomero)
- Purpose: BIOMERO Django API integration (REST API for BIOMERO via python library)
- Configuration: BIOMERO configuration editable via `/etc/slurm-config.ini` by the User Interface

## Custom Interface Modifications

> **Warning:**
> These direct OMERO.web modifications may be replaced by plugin-based approaches in future versions.

Current modifications include:

**Pretty Login Page**
- Enhanced visual design for login interface
- Script: `get_images_for_login_page.py`
- Assets: Custom CSS and images

**Better Buttons**
- Improved button clarity and UX
- Modified default OMERO.web templates

**Database Pages Integration** *(Deprecated)*
- *Replaced by OMERO.biomero plugin*
- *Legacy features:*
  - Metabase dashboard embedding
  - Custom navigation elements

### Dockerfile Key Sections

**Plugin Installation:**

```dockerfile
# Install OMERO.boost for BIOMERO integration
RUN git clone -b main https://github.com/Cellular-Imaging-Amsterdam-UMC/omero-boost.git /opt/omero/web/omero-boost
RUN /opt/omero/web/venv3/bin/pip install -e /opt/omero/web/omero-boost
```

**Automated OMERO.forms Setup:**

```dockerfile
# Install OMERO.forms and setup automation
RUN /opt/omero/web/venv3/bin/pip install omero-forms==2.1.0
ADD web/44-create_forms_user.py /startup/
ADD web/45-fix-forms-config.sh /startup/
```

**Interface Customizations:**

```dockerfile
# Custom login page and styling
RUN python3.9 /script/get_images_for_login_page.py /images/ /script/login.html ./webclient/templates/webclient/login.html
ADD web/local_omeroweb_edits/pretty_login/login_page_images ./webclient/static/webclient/image/login_page_images/
```

## Development Guidelines

### Starting Development

1. **Use the development compose:**

```bash
docker-compose -f docker-compose-dev.yml up -d
```

2. **The web container will be running but OMERO.web will not be started**

3. **For OMERO.biomero development:**
   - Clone the OMERO.biomero repository adjacent to NL-BIOMERO
   - Follow the plugin's README for development setup
   - Use the plugin's development tools to control OMERO.web

### Making Changes

**For Plugin Development:**
- Work in the respective plugin repository
- Use volume mounts for live code changes; change to versioned pip installs on release.
- Restart OMERO.web as needed for testing

**For Interface Modifications:**
- Prefer plugin-based approaches over direct file modifications
- Test changes in development mode before building production images
- Consider migration path to plugin-based solutions

**For Configuration Changes:**
- Modify `01-default-webapps.omero` for web app configurations
- Use environment variables for dynamic settings
- Test startup script changes in development containers

### Customizing Login Page with Volume Mounts

You can customize the OMERO.web login page without rebuilding the container by mounting custom files over the default ones. This is particularly useful for branding and institutional customization.

**Example: Custom Institution Banner**

Mount your custom banner image to replace the default AmsterdamUMC logo:

```yaml
services:
  omeroweb:
    volumes:
      - "../web/local_omeroweb_edits/pretty_login/login_page_images/bioimaging.png:/opt/omero/web/venv3/lib/python3.9/site-packages/omeroweb/webclient/static/webclient/image/login_page_images/AmsterdamUMC-logo.png:ro"
```

**Example: Custom Footer Images**

To customize the footer section with your own organization logos and links, mount custom image files:

```yaml
services:
  omeroweb:
    volumes:
      # Custom footer logos
      - "../web/local_omeroweb_edits/pretty_login/login_page_images/your-org-logo.png:/opt/omero/web/venv3/lib/python3.9/site-packages/omeroweb/webclient/static/webclient/image/login_page_images/Cellular Imaging.png:ro"
      - "../web/local_omeroweb_edits/pretty_login/login_page_images/your-sponsor-logo.png:/opt/omero/web/venv3/lib/python3.9/site-packages/omeroweb/webclient/static/webclient/image/login_page_images/DBI.png:ro"
```

**Example: Complete Login Page Template**

For more extensive customization, you can mount a completely custom login.html template. The changes are minimal and focus mainly on the footer section:

**Key Changes in login.html:**

**Custom Footer Section** - Replace the default footer with your organization's links:

```html
<div class="footer-content">
    <a href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO" class="footer-section custom-banner" target="_blank" rel="noopener noreferrer">
        <img src="{% static 'webclient/image/login_page_images/Cellular Imaging.png' %}" alt="Cellular Imaging Icon" class="section-icon">
        <p class="section-text">Cellular Imaging, Amsterdam UMC <br> Developing data management and analysis <br> for your research</p>
    </a>
    <a href="https://www.dbi-infra.eu/" class="footer-section uploader-section" target="_blank" rel="noopener noreferrer">
        <img src="{% static 'webclient/image/login_page_images/DBI.png' %}" alt="DBI Icon" class="section-icon" style="height: 60px; width: auto;">
        <p class="section-text">Server kindly supported <br> by Danish BioImaging Infrastructure!</p>
    </a>
</div>
```

**Docker Compose Mount:**

```yaml
services:
  omeroweb:
    volumes:
      # Custom login page template (minimal changes shown above)
      - "../web/local_omeroweb_edits/pretty_login/login.html:/opt/omero/web/venv3/lib/python3.9/site-packages/omeroweb/webclient/templates/webclient/login.html:ro"
      # Supporting images
      - "../web/local_omeroweb_edits/pretty_login/login_page_images/:/opt/omero/web/venv3/lib/python3.9/site-packages/omeroweb/webclient/static/webclient/image/login_page_images/:ro"
```

**Important Notes:**
- All mounted files should be read-only (`:ro`) to prevent accidental modification
- The custom login.html should maintain the same Django template structure
- Footer links in the template can be updated to point to your organization's resources
- Image paths in the login.html must match the mounted file locations
- Changes take effect immediately without container rebuild

### Testing

```bash
# Build with changes
docker-compose -f docker-compose-dev.yml build omeroweb

# Test in development mode
docker-compose -f docker-compose-dev.yml up -d

# Check logs for issues
docker-compose -f docker-compose-dev.yml logs omeroweb
```

## Related Documentation

- [OMERO.biomero Plugin](https://github.com/Cellular-Imaging-Amsterdam-UMC/OMERO.biomero/tree/main) - Primary development target
- [OMERO Server](omeroserver.md) - Server container development
- [Architecture](../architecture.md) - Overall system architecture
- [OMERO.web Developer Documentation](https://omero.readthedocs.io/en/stable/developers/Web/)
