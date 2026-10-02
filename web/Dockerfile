# Release preparation downloads only the explicitly pinned Analysis release.
# No first-party source build or package-index fallback enters the final image.
FROM openmicroscopy/omero-web-standalone:5.33.1 AS analysis-release
ARG OMERO_ANALYSIS_VERSION
USER root
COPY web/release/ /tmp/analysis-release-tools/
RUN /opt/omero/web/venv3/bin/python /tmp/analysis-release-tools/download_analysis_release.py \
    --version "${OMERO_ANALYSIS_VERSION}" --output /dist/wheelhouse
# Third-party dependencies still use their ordinary upstream sources. OMERO.web
# itself is supplied by the identical pinned base image in both stages.
RUN /opt/omero/web/venv3/bin/python - <<'PY'
import email.parser
import pathlib
import subprocess
import sys
import zipfile
from packaging.requirements import Requirement

wheel = next(pathlib.Path('/dist/wheelhouse').glob('omero_analysis-*.whl'))
with zipfile.ZipFile(wheel) as archive:
    name = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
    metadata = email.parser.BytesParser().parsebytes(archive.read(name))
requirements = []
for raw in metadata.get_all('Requires-Dist', []):
    requirement = Requirement(raw)
    if requirement.name.lower().replace('_', '-') == 'omero-web':
        continue
    if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
        requirements.append(str(requirement))
subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
                '--dest', '/dist/wheelhouse', *requirements], check=True)
PY

# The released 1.6.1 backend has the newer Analyze/storage behavior but lacks
# the Data Analysis host. Build the reviewed integration patch on that exact
# baseline rather than silently replacing it with a stock or older branch build.
FROM node:22 AS biomero-host-frontend
RUN git clone --branch v1.6.1 --depth 1 https://github.com/NL-BioImaging/OMERO.biomero.git /src
WORKDIR /src
COPY web/biomero-analysis-host.patch /tmp/biomero-analysis-host.patch
RUN git apply --check /tmp/biomero-analysis-host.patch && git apply /tmp/biomero-analysis-host.patch
WORKDIR /src/webapp
ENV CI=true
RUN corepack enable && yarn install --frozen-lockfile && \
    yarn test --watchAll=false --runInBand && yarn build

FROM openmicroscopy/omero-web-standalone:5.33.1 AS biomero-host-wheel
USER root
ARG OMERO_BIOMERO_VERSION=1.6.1+analysis.g75adc97
COPY --from=biomero-host-frontend /src/omero_biomero/ /src/omero_biomero/
COPY --from=biomero-host-frontend /src/setup.py /src/pyproject.toml /src/README.md /src/LICENSE /src/
WORKDIR /src
RUN /opt/omero/web/venv3/bin/python -m pip install build setuptools-scm wheel && \
    SETUPTOOLS_SCM_PRETEND_VERSION="${OMERO_BIOMERO_VERSION}" \
    /opt/omero/web/venv3/bin/python -m build --wheel --no-isolation --outdir /dist/biomero-host

FROM openmicroscopy/omero-web-standalone:5.33.1

ARG OMERO_FORMS_VERSION
ARG OMERO_BIOMERO_VERSION
ARG OMERO_BIOMERO_BRANCH=analysis_integration
ARG OMERO_ANALYSIS_VERSION
ARG BIOMERO_WORKFLOW_SKILLS_VERSION
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

# Install the tested integration wheel prepared above. The local version suffix
# identifies the host backport; the public backend baseline remains 1.6.1.
COPY --from=biomero-host-wheel /dist/biomero-host/ /tmp/biomero-host-wheels/
RUN /opt/omero/web/venv3/bin/pip install \
        /tmp/biomero-host-wheels/omero_biomero-*.whl \
    && /opt/omero/web/venv3/bin/omero-biomero-setup

# Install Analysis from checksum-verified, pre-built GitHub Release wheels.
# The SDK wheel is retained in preparation for authors; it is not a web runtime
# dependency. Third-party dependency wheels were resolved in the build stage.
RUN test -n "$OMERO_ANALYSIS_VERSION" || (echo "OMERO_ANALYSIS_VERSION build arg is required" >&2; exit 1) && \
    test -n "$BIOMERO_WORKFLOW_SKILLS_VERSION" || (echo "BIOMERO_WORKFLOW_SKILLS_VERSION build arg is required" >&2; exit 1)
COPY --from=analysis-release /dist/wheelhouse/ /tmp/omero-plugin-wheelhouse/
RUN /opt/omero/web/venv3/bin/pip install \
        --no-index --find-links /tmp/omero-plugin-wheelhouse \
        "/tmp/omero-plugin-wheelhouse/omero_analysis-${OMERO_ANALYSIS_VERSION}-py3-none-any.whl" && \
    /opt/omero/web/venv3/bin/pip install \
        "biomero-workflow-skills==${BIOMERO_WORKFLOW_SKILLS_VERSION}" && \
    test -f /opt/omero/web/venv3/lib/python3.12/site-packages/omero_analysis/static/omero_analysis/pyodide/pyodide.mjs
RUN cp /opt/omero/web/venv3/share/omero-analysis/90-omero-analysis.omero /opt/omero/web/config/ && \
    cp /opt/omero/web/venv3/share/omero-analysis/49-omero-analysis-cleanup.py /startup/ && \
    cp /opt/omero/web/venv3/share/omero-analysis/51-omero-analysis-navigation.py /startup/ && \
    chmod 755 /startup/49-omero-analysis-cleanup.py \
    /startup/51-omero-analysis-navigation.py

RUN /opt/omero/web/venv3/bin/python - <<'PY'
import os
from importlib.metadata import version

expected = {
    "omero-biomero": os.environ.get("OMERO_BIOMERO_VERSION"),
    "omero-analysis": os.environ.get("OMERO_ANALYSIS_VERSION"),
    "biomero-workflow-skills": os.environ.get("BIOMERO_WORKFLOW_SKILLS_VERSION"),
}
for package, wanted in expected.items():
    installed = version(package)
    if installed != wanted:
        raise SystemExit(f"{package}: expected {wanted}, installed {installed}")
from omero_analysis.host_capabilities import biomero_analysis_host_installed
assert biomero_analysis_host_installed(), "The Data Analysis view, template and frontend must all be installed"
PY

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
