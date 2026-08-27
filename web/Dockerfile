FROM python:3.12-slim AS omero-forms-builder

ARG OMERO_FORMS_VERSION

# OMERO.forms 2.3.0 is released on GitHub but not yet published on PyPI.
# Build its frontend and pure-Python wheel from the matching release tag.
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /var/lib/apt/lists/*
RUN test -n "$OMERO_FORMS_VERSION" || (echo "OMERO_FORMS_VERSION build arg is required" >&2; exit 1)
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OMERO_FORMS="$OMERO_FORMS_VERSION" \
    python -m pip wheel --no-deps --wheel-dir /tmp/omero-forms-wheels \
    "https://github.com/NL-BioImaging/OMERO.forms/archive/refs/tags/v${OMERO_FORMS_VERSION}.tar.gz"

FROM openmicroscopy/omero-web-standalone:5.31.1

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

# To track a branch instead of a release, uncomment the cache-bust line and use the git install:
# ADD "https://api.github.com/repos/NL-BioImaging/OMERO.biomero/commits/surf" /latest_commit_omero_biomero
# RUN /opt/omero/web/venv3/bin/pip install git+https://github.com/NL-BioImaging/OMERO.biomero.git@surf \
#     && /opt/omero/web/venv3/bin/omero-biomero-setup

# Install released OMERO.biomero from PyPI
RUN test -n "$OMERO_BIOMERO_VERSION" || (echo "OMERO_BIOMERO_VERSION build arg is required" >&2; exit 1)
RUN /opt/omero/web/venv3/bin/pip install omero-biomero==${OMERO_BIOMERO_VERSION} \
    && /opt/omero/web/venv3/bin/omero-biomero-setup

### Install OMERO.forms ###

# Install the release wheel built above without retaining Node build tooling.
COPY --from=omero-forms-builder /tmp/omero-forms-wheels /tmp/omero-forms-wheels
RUN /opt/omero/web/venv3/bin/pip install /tmp/omero-forms-wheels/*.whl && \
    rm -rf /tmp/omero-forms-wheels

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
