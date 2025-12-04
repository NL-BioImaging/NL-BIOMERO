FROM openmicroscopy/omero-web-standalone:5.30.0

ARG OMERO_FORMS_VERSION
ARG OMERO_BIOMERO_VERSION

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


# Update PATH manually based on known locations
ENV PATH="/usr/pgsql-12/bin:/usr/pgsql-14/bin:${PATH}"

## Setup slurm-config for biomero, for the BIOMERO django API in OMERO.biomero
COPY biomeroworker/slurm-config.ini /etc/slurm-config.ini

### Install OMERO.biomero first ###
### BIOMERO.importer will be installed as a dependency of OMERO.biomero ###

# For development install with a local biomero.omero clone, activate these lines again:
# ADD "https://api.github.com/repos/Cellular-Imaging-Amsterdam-UMC/OMERO.biomero/commits/main" /latest_commit_biomero
# RUN git clone -b main https://github.com/Cellular-Imaging-Amsterdam-UMC/OMERO.biomero.git /opt/omero/web/OMERO.biomero

# Install released OMERO.biomero from PyPI and run setup
RUN /opt/omero/web/venv3/bin/pip install omero-biomero==${OMERO_BIOMERO_VERSION} \
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

