FROM openmicroscopy/omero-server:5.6.16

ARG BIOMERO_VERSION

USER root

## Default Python environment
ENV VIRTUAL_ENV=/opt/omero/server/venv3
ENV PATH=/opt/ice-3.6.5-0.3.0/bin:$VIRTUAL_ENV/bin/:$PATH
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

RUN wget https://github.com/glencoesoftware/bioformats2raw/releases/download/v0.7.0/bioformats2raw-0.7.0.zip \
    ; unzip -d /opt bioformats2raw-0.7.0.zip \
    && rm bioformats2raw-0.7.0.zip
ENV PATH="$PATH:/opt/bioformats2raw-0.7.0/bin"

## Add BIOMERO Omero Slurm Client
RUN yum -y install ack

# Create virtual environment and install ALL packages in it
RUN python3 -m venv $VIRTUAL_ENV \
    && $VIRTUAL_ENV/bin/python -m pip install --upgrade pip \
    && wget https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp39-cp39-manylinux_2_28_x86_64.whl \
    && $VIRTUAL_ENV/bin/python -m pip install zeroc_ice-3.6.5-cp39-cp39-manylinux_2_28_x86_64.whl \
    && rm zeroc_ice-3.6.5-cp39-cp39-manylinux_2_28_x86_64.whl

# Cache buster: fetch latest commit SHA from GitHub API for biomero_schema branch
ADD https://api.github.com/repos/NL-BioImaging/biomero/git/refs/heads/biomero_schema /tmp/biomero_cache_buster
RUN $VIRTUAL_ENV/bin/python -m pip install --no-cache-dir 'git+https://github.com/NL-BioImaging/biomero@biomero_schema#egg=biomero[full]'

## Adjust processor code with AMC Processor
# This version forwards HTTP(S) PROXY environment variables to the subprocesses (scripts)
# See latest OME version @ https://raw.githubusercontent.com/ome/omero-py/master/src/omero/processor.py
# Might need to merge important changes from time to time to keep this version compatible.
COPY biomeroworker/processor.py /opt/omero/server/venv3/lib/python3.9/site-packages/omero/

## Setup slurm-config for biomero
COPY biomeroworker/slurm-config.ini /etc/slurm-config.ini

## OMERO: Replace the default startup scripts
RUN rm /startup/60-database.sh
COPY biomeroworker/99-run.sh /startup/99-run.sh
RUN chmod +x /startup/99-run.sh
USER omero-server
