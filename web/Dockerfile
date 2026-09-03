FROM openmicroscopy/omero-web-standalone:5.31.1

ARG OMERO_FORMS_VERSION
ARG OMERO_BIOMERO_VERSION

# Development-only branch wiring for the scheduler-native image-pull proof of
# concept. Restore the versioned OMERO.biomero install below after testing.
ARG BIOMERO_BRANCH=feature/slurm-image-pull-array
ARG OMERO_BIOMERO_BRANCH=feature/slurm-image-pull-array
ADD "https://api.github.com/repos/NL-BioImaging/biomero/commits/${BIOMERO_BRANCH}" /latest_commit_biomero
ADD "https://api.github.com/repos/NL-BioImaging/OMERO.biomero/commits/${OMERO_BIOMERO_BRANCH}" /latest_commit_omero_biomero

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

# Install the matching BIOMERO core branch first so OMERO.biomero's dependency
# resolution cannot fall back to the released core package.
RUN /opt/omero/web/venv3/bin/pip install \
        "biomero @ git+https://github.com/NL-BioImaging/biomero.git@${BIOMERO_BRANCH}" \
        "omero-biomero @ git+https://github.com/NL-BioImaging/OMERO.biomero.git@${OMERO_BIOMERO_BRANCH}" \
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
COPY web/local_omeroweb_edits/biomero-base-include.html ./webclient/templates/webclient/base/includes/biomero-base-include.html

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
