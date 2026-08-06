FROM openmicroscopy/omero-web-standalone:5.31.1

ARG OMERO_FORMS_VERSION
ARG OMERO_BIOMERO_VERSION
ARG BIOMERO_ZARR_VIEWER_VERSION

USER root

# Install system dependencies needed for psycopg2 and other packages
RUN dnf -y install postgresql-devel gcc make gettext openssl-devel libffi-devel

# Create L-Drive directory and set permissions
RUN mkdir -p /L-Drive && \
    chown omero-web:omero-web /L-Drive && \
    chmod 755 /L-Drive

# Add volume mount point for L-Drive
VOLUME ["/L-Drive"]

### Pretty Login ###
COPY web/local_omeroweb_edits/pretty_login/login.html /script/
### ###

# OMERO applications
RUN /opt/omero/web/venv3/bin/pip install \
        'django-cors-headers' \
        omero-figure \
        omero-iviewer \
        omero-fpbioimage \
        omero-mapr \
        omero-parade \
        omero-webtagging-autotag \
        omero-webtagging-tagsearch \
        whitenoise

# Track the matching OMERO.Analysis integration branch for local rebuilds.
ADD "https://api.github.com/repos/NL-BioImaging/OMERO.Analysis/commits/analysis_integration" /latest_commit_omero_analysis
RUN /opt/omero/web/venv3/bin/pip install git+https://github.com/NL-BioImaging/OMERO.Analysis.git@analysis_integration
ADD "https://raw.githubusercontent.com/NL-BioImaging/OMERO.Analysis/analysis_integration/docker/90-omero-analysis.omero" /opt/omero/web/config/90-omero-analysis.omero
ADD "https://raw.githubusercontent.com/NL-BioImaging/OMERO.Analysis/analysis_integration/docker/49-omero-analysis-cleanup.py" /startup/49-omero-analysis-cleanup.py
ADD "https://raw.githubusercontent.com/NL-BioImaging/OMERO.Analysis/analysis_integration/docker/51-omero-analysis-navigation.py" /startup/51-omero-analysis-navigation.py
RUN chmod +x /startup/49-omero-analysis-cleanup.py \
    /startup/51-omero-analysis-navigation.py

# Install the released BIOMERO OME-Zarr Viewer from PyPI
RUN test -n "$BIOMERO_ZARR_VIEWER_VERSION" || (echo "BIOMERO_ZARR_VIEWER_VERSION build arg is required" >&2; exit 1)
RUN /opt/omero/web/venv3/bin/pip install biomero-zarr-viewer==${BIOMERO_ZARR_VIEWER_VERSION}

# Update PATH manually based on known locations
ENV PATH="/usr/pgsql-12/bin:/usr/pgsql-14/bin:${PATH}"

## Setup slurm-config for biomero, for the BIOMERO django API in OMERO.biomero
COPY biomeroworker/slurm-config.ini /etc/slurm-config.ini

### Install OMERO.biomero first ###
### BIOMERO.importer and BIOMERO.analyzer will be installed as a dependency of OMERO.biomero ###

# Track the analysis integration branch and invalidate the Docker cache when it advances.
ADD "https://api.github.com/repos/NL-BioImaging/OMERO.biomero/commits/analysis_integration" /latest_commit_omero_biomero
RUN /opt/omero/web/venv3/bin/pip install git+https://github.com/NL-BioImaging/OMERO.biomero.git@analysis_integration \
    && /opt/omero/web/venv3/bin/omero-biomero-setup

### Install OMERO.forms ###

# Install OMERO.forms from PyPI
RUN /opt/omero/web/venv3/bin/pip install omero-forms==${OMERO_FORMS_VERSION}

# Set the working directory
WORKDIR /opt/omero/web/venv3/lib/python3.12/site-packages/omeroweb

# Copy login template and assets directly
COPY web/local_omeroweb_edits/pretty_login/login.html ./webclient/templates/webclient/login.html
ADD web/local_omeroweb_edits/pretty_login/login_page_images ./webclient/static/webclient/image/login_page_images/
ADD web/local_omeroweb_edits/pretty_login/ome.login.css ./webgateway/static/webgateway/css/ome.login.css

# Configuration file and startup scripts
ADD web/local_omeroweb_edits/01-default-webapps.omero /opt/omero/web/config/
ADD web/44-create_forms_user.py /startup/
ADD web/45-fix-forms-config.sh /startup/
RUN chmod +x /startup/45-fix-forms-config.sh && \
    chmod +x /startup/44-create_forms_user.py && \
    chown -R omero-web:omero-web /opt/omero/web/config && \
    chmod 644 /opt/omero/web/config/01-default-webapps.omero

### Better Buttons ###

# # Improved top menu button clarity
ADD web/local_omeroweb_edits/script-text-play.svg ./webgateway/static/webgateway/img/script-text-play.svg

### ###

USER omero-web
