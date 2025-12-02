FROM openmicroscopy/omero-web-standalone:5.29.2

ARG OMERO_FORMS_VERSION
ARG OMERO_BIOMERO_VERSION

USER root

# Update to Python 3.12
RUN dnf -y install epel-release \
     && dnf -y install python3.12 python3.12-pip python3.12-devel \
         postgresql-devel gcc make gettext openssl-devel libffi-devel bzip2-devel zlib-devel xz-devel readline-devel sqlite-devel \
     && alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 312

# Capture existing (3.9) virtualenv package set, then rebuild venv3 with Python 3.12 and reinstall.
# Robust against missing/broken pip in original venv: bootstrap via ensurepip if needed.
RUN set -eux; \
    FREEZE_ORIG=/tmp/venv3-freeze-original.txt; \
    if [ -d /opt/omero/web/venv3 ]; then \
        echo "Found existing venv3; attempting to freeze packages"; \
        if /opt/omero/web/venv3/bin/python -m pip --version >/dev/null 2>&1; then \
            /opt/omero/web/venv3/bin/python -m pip freeze > "$FREEZE_ORIG" || true; \
        else \
            echo "pip missing or broken in old venv; bootstrapping with ensurepip"; \
            /opt/omero/web/venv3/bin/python -m ensurepip --upgrade || true; \
            /opt/omero/web/venv3/bin/python -m pip install --upgrade pip setuptools wheel || true; \
            /opt/omero/web/venv3/bin/python -m pip freeze > "$FREEZE_ORIG" || true; \
        fi; \
    else \
        echo "Original venv3 missing; proceeding without freeze"; \
        touch "$FREEZE_ORIG"; \
    fi; \
    # Filter out meta-tools & Ice/omero-py (fresh install) & editable installs; ignore comments
    grep -E -v '^(pip==|setuptools==|wheel==|zeroc-ice==|omero-py==|#|Editable\s)' "$FREEZE_ORIG" > /tmp/venv3-freeze-filtered.txt || true; \
    rm -rf /opt/omero/web/venv3; \
    python3.12 -m venv /opt/omero/web/venv3; \
    /opt/omero/web/venv3/bin/python -m ensurepip --upgrade; \
    /opt/omero/web/venv3/bin/pip install --upgrade pip setuptools wheel; \
    /opt/omero/web/venv3/bin/pip install \
        https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl \
        omero-py; \
    if [ -s /tmp/venv3-freeze-filtered.txt ]; then \
        echo "Reinstalling previously captured packages"; \
        /opt/omero/web/venv3/bin/pip install -r /tmp/venv3-freeze-filtered.txt || true; \
    else \
        echo "No previous packages to reinstall"; \
    fi;


# Create L-Drive directory and set permissions
RUN mkdir -p /L-Drive && \
    chown omero-web:omero-web /L-Drive && \
    chmod 755 /L-Drive

# Add volume mount point for L-Drive
VOLUME ["/L-Drive"]

### Pretty Login ###
COPY web/local_omeroweb_edits/pretty_login/get_images_for_login_page.py /script/
COPY web/local_omeroweb_edits/pretty_login/login.html /script/
COPY web/local_omeroweb_edits/pretty_login/institution_banner /images/
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

### OMERO ADI will be installed as a dependency of OMERO.biomero ###

### Install OMERO.biomero first ###

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

# Run the script to update the login.html file from pretty_login
RUN /opt/omero/web/venv3/bin/python /script/get_images_for_login_page.py /images/ /script/login.html ./webclient/templates/webclient/login.html

# Login logos image and style page
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

