FROM openmicroscopy/omero-server:5.6.18

ARG BIOMERO_VERSION=2.9.0b1
ARG BIOMERO_IMPORTER_VERSION=1.5.0b2

# Development-only branch wiring. Uncomment the matching ARGs, branch-head
# cache busters, and direct-reference installs together for unpublished work.
# ARG BIOMERO_SCHEMA_BRANCH=main
# ARG BIOMERO_BRANCH=main
# ARG BIOMERO_IMPORTER_BRANCH=main
# ADD "https://api.github.com/repos/NL-BioImaging/biomero-schema/commits/${BIOMERO_SCHEMA_BRANCH}" /latest_commit_biomero_schema
# ADD "https://api.github.com/repos/NL-BioImaging/BIOMERO.importer/commits/${BIOMERO_IMPORTER_BRANCH}" /latest_commit_biomero_importer
# ADD "https://api.github.com/repos/NL-BioImaging/biomero/commits/${BIOMERO_BRANCH}" /latest_commit_biomero
# RUN $VIRTUAL_ENV/bin/python -m pip install \
#     "biomero-schema @ git+https://github.com/NL-BioImaging/biomero-schema.git@${BIOMERO_SCHEMA_BRANCH}" \
#     "biomero-importer[identity] @ git+https://github.com/NL-BioImaging/BIOMERO.importer.git@${BIOMERO_IMPORTER_BRANCH}" \
#     "biomero[full] @ git+https://github.com/NL-BioImaging/biomero.git@${BIOMERO_BRANCH}"

USER root

## Default Python environment
ENV VIRTUAL_ENV=/opt/omero/server/venv3
ENV PATH=/opt/ice-3.6.5-0.3.0/bin:$VIRTUAL_ENV/bin/:$PATH
RUN echo 'skip_if_unavailable=True' >> /etc/dnf/dnf.conf
RUN yum -y install git

## Replace the default configuration files
COPY biomeroworker/ice.config biomeroworker/worker.cfg /opt/omero/server/OMERO.server/etc/templates/

## Install SSH client
RUN yum install -y openssh-clients
COPY biomeroworker/10-mount-ssh.sh /startup/10-mount-ssh.sh
RUN chmod +x /startup/10-mount-ssh.sh

## Install psycopg2 system prerequisites for postgres interaction
RUN yum install -y python3-devel postgresql-devel gcc
# Update PATH manually based on known locations
ENV PATH="/usr/pgsql-12/bin:/usr/pgsql-13/bin:/usr/pgsql-14/bin:/usr/pgsql-15/bin:/usr/pgsql-16/bin:/usr/bin:${PATH}"

## Setup OME ZARR & TIFF modules for data export
RUN yum install -y blosc-devel

# Sadly can't do this in Dockerfile:
# ENV JAVA_HOME=$(readlink -f /usr/bin/java | sed "s:/bin/java::")
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-11.0.23.0.9-3.el9.x86_64
RUN export JAVA_HOME

RUN wget https://github.com/glencoesoftware/bioformats2raw/releases/download/v0.12.0-rc1/bioformats2raw-0.12.0-rc1.zip \
    ; unzip -d /opt bioformats2raw-0.12.0-rc1.zip \
    && rm bioformats2raw-0.12.0-rc1.zip
ENV PATH="$PATH:/opt/bioformats2raw-0.12.0-rc1/bin"

## Add BIOMERO Omero Slurm Client
RUN yum -y install ack

# Install released packages from PyPI. biomero-schema is resolved transitively
# from the compatible constraints declared by BIOMERO and BIOMERO.importer.
RUN test -n "$BIOMERO_VERSION" || (echo "BIOMERO_VERSION build arg is required" >&2; exit 1) \
    && test -n "$BIOMERO_IMPORTER_VERSION" || (echo "BIOMERO_IMPORTER_VERSION build arg is required" >&2; exit 1)
RUN $VIRTUAL_ENV/bin/python -m pip install --upgrade pip \
    && $VIRTUAL_ENV/bin/python -m pip install \
        "biomero-importer[identity]==${BIOMERO_IMPORTER_VERSION}" \
    && $VIRTUAL_ENV/bin/python -m pip install \
        "biomero[full]==${BIOMERO_VERSION}" \
    && $VIRTUAL_ENV/bin/python -m pip install \
        scikit-image==0.25.2 omero-rois==0.4.1 \
        ezomero==3.2.3 dask==2026.1.1 distributed==2026.1.1 \
    && $VIRTUAL_ENV/bin/python -m pip check

## Adjust processor code with BIOMERO Processor
# This version forwards HTTP(S) PROXY environment variables to the subprocesses (scripts)
# See latest OME version @ https://raw.githubusercontent.com/ome/omero-py/master/src/omero/processor.py
# Might need to merge important changes from time to time to keep this version compatible.
COPY biomeroworker/processor.py /opt/omero/server/venv3/lib/python3.11/site-packages/omero/

## OMERO: Replace the default startup scripts
RUN rm /startup/60-database.sh
COPY biomeroworker/99-run.sh /startup/99-run.sh
RUN chmod +x /startup/99-run.sh
USER omero-server
