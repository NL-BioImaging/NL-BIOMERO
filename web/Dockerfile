FROM openmicroscopy/omero-web-standalone:5.33.1

ARG OMERO_FORMS_VERSION
ARG OMERO_BIOMERO_VERSION
ARG BIOMERO_ZARR_VIEWER_VERSION
# ARG BIOMERO_SCHEMA_BRANCH=main
# ARG BIOMERO_SHALLOWER_BRANCH=main
# ARG BIOMERO_IMPORTER_BRANCH=main
# ARG BIOMERO_BRANCH=main
# ARG OMERO_BIOMERO_BRANCH=main

USER root

# Install system dependencies needed for psycopg2 and other packages
RUN dnf -y install postgresql-devel gcc make gettext openssl-devel libffi-devel git

# Create L-Drive directory and set permissions
RUN mkdir -p /L-Drive && \
    chown omero-web:omero-web /L-Drive && \
    chmod 755 /L-Drive

# Add volume mount point for L-Drive
VOLUME ["/L-Drive"]

### Pretty Login ###
COPY web/local_omeroweb_edits/pretty_login/login.html /script/
### ###

# OMERO applications (versioned)
RUN /opt/omero/web/venv3/bin/pip install \
        'django-cors-headers==3.7.0' \
        'omero-figure==7.4.1' \
        'omero-iviewer==0.16.0' \
        'omero-fpbioimage==0.4.1' \
        'omero-mapr==0.5.3' \
        'omero-parade==0.2.4' \
        'omero-webtagging-autotag==4.0.0' \
        'omero-webtagging-tagsearch==4.0.0' \
        'whitenoise==6.12.0'


# Update PATH manually based on known locations
ENV PATH="/usr/pgsql-12/bin:/usr/pgsql-14/bin:${PATH}"

### Install OMERO.biomero first ###
### BIOMERO.importer and BIOMERO.analyzer will be installed as a dependency of OMERO.biomero ###

# Development option: uncomment the branch ARGs and ADD/RUN block below, and
# comment the release RUN block. Each branch head is a Docker cache buster.
# ADD "https://api.github.com/repos/NL-BioImaging/biomero-schema/commits/${BIOMERO_SCHEMA_BRANCH}" /latest_commit_biomero_schema
# ADD "https://api.github.com/repos/NL-BioImaging/BIOMERO.shallower/commits/${BIOMERO_SHALLOWER_BRANCH}" /latest_commit_biomero_shallower
# ADD "https://api.github.com/repos/NL-BioImaging/BIOMERO.importer/commits/${BIOMERO_IMPORTER_BRANCH}" /latest_commit_biomero_importer
# ADD "https://api.github.com/repos/NL-BioImaging/biomero/commits/${BIOMERO_BRANCH}" /latest_commit_biomero
# ADD "https://api.github.com/repos/NL-BioImaging/OMERO.biomero/commits/${OMERO_BIOMERO_BRANCH}" /latest_commit_omero_biomero
# RUN /opt/omero/web/venv3/bin/pip install \
#         "biomero-schema @ git+https://github.com/NL-BioImaging/biomero-schema.git@${BIOMERO_SCHEMA_BRANCH}" \
#         "biomero-shallower @ git+https://github.com/NL-BioImaging/BIOMERO.shallower.git@${BIOMERO_SHALLOWER_BRANCH}" \
#         "biomero-importer[identity] @ git+https://github.com/NL-BioImaging/BIOMERO.importer.git@${BIOMERO_IMPORTER_BRANCH}" \
#         "biomero[full] @ git+https://github.com/NL-BioImaging/biomero.git@${BIOMERO_BRANCH}" \
#         "omero-biomero @ git+https://github.com/NL-BioImaging/OMERO.biomero.git@${OMERO_BIOMERO_BRANCH}" \
#     && /opt/omero/web/venv3/bin/omero-biomero-setup

# Release option: install the version selected in OMERO_BIOMERO_VERSION from PyPI.
RUN test -n "$OMERO_BIOMERO_VERSION" || (echo "OMERO_BIOMERO_VERSION build arg is required" >&2; exit 1)
RUN /opt/omero/web/venv3/bin/pip install \
        "omero-biomero==${OMERO_BIOMERO_VERSION}" \
    && /opt/omero/web/venv3/bin/omero-biomero-setup

### Install OMERO.forms ###

# Install OMERO.forms from PyPI
RUN /opt/omero/web/venv3/bin/pip install omero-forms==${OMERO_FORMS_VERSION}

# Install the selected viewer release and its bundled frontend from PyPI, so the
# web image does not need Node.js or a separate viewer checkout.
RUN test -n "$BIOMERO_ZARR_VIEWER_VERSION" || (echo "BIOMERO_ZARR_VIEWER_VERSION build arg is required" >&2; exit 1)
RUN /opt/omero/web/venv3/bin/pip install "biomero-zarr-viewer==${BIOMERO_ZARR_VIEWER_VERSION}"

# Set the working directory
WORKDIR /opt/omero/web/venv3/lib/python3.12/site-packages/omeroweb

# Copy login template and assets directly
COPY web/local_omeroweb_edits/pretty_login/login.html ./webclient/templates/webclient/login.html
ADD web/local_omeroweb_edits/pretty_login/login_page_images ./webclient/static/webclient/image/login_page_images/
ADD web/local_omeroweb_edits/pretty_login/ome.login.css ./webgateway/static/webgateway/css/ome.login.css
COPY web/local_omeroweb_edits/biomero-base-include.html ./webclient/templates/webclient/base/includes/biomero-base-include.html

# Preserve OMERO's script dialog and override only its Chosen list controls.
RUN mv ./webclient/templates/webclient/scripts/script_ui.html ./webclient/templates/webclient/scripts/omero_script_ui.html
COPY web/local_omeroweb_edits/script_ui.html ./webclient/templates/webclient/scripts/script_ui.html

# Configuration file and startup scripts
ADD web/local_omeroweb_edits/01-default-webapps.omero /opt/omero/web/config/
ADD web/44-create_forms_user.py /startup/
ADD web/45-fix-forms-config.sh /startup/
COPY web/55-configure-zarr-viewer.py /startup/
RUN chmod +x /startup/45-fix-forms-config.sh && \
    chmod +x /startup/55-configure-zarr-viewer.py && \
    chmod +x /startup/44-create_forms_user.py && \
    chown -R omero-web:omero-web /opt/omero/web/config && \
    chmod 644 /opt/omero/web/config/01-default-webapps.omero

### Better Buttons ###

# # Improved top menu button clarity
ADD web/local_omeroweb_edits/script-text-play.svg ./webgateway/static/webgateway/img/script-text-play.svg

### ###

USER omero-web
