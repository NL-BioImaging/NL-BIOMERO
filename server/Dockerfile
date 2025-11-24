FROM openmicroscopy/omero-server:5.6.16

ARG BIOMERO_VERSION

ENV OMERO_DIST /opt/omero/server/OMERO.server

# Upload scripts for omero-server user
# COPY --chown=omero-server:omero-server scripts/slurm/* /opt/omero/server/OMERO.server/lib/scripts/slurm/
USER root
RUN yum -y install git 
USER omero-server

# Configuration files - use shell script for restore
ADD server/00-restore-config.sh* /startup/
ADD server/01-ldap-config.omero /opt/omero/server/config/

# Development versions:
ADD "https://api.github.com/repos/NL-BioImaging/biomero-scripts/commits/biomero_schema" latest_comm
RUN cd $OMERO_DIST/lib/scripts/ && \
    git clone --depth 1 --branch biomero_schema --single-branch https://github.com/NL-BioImaging/biomero-scripts.git biomero

# Clone specific release version
# RUN cd /opt/omero/server/OMERO.server/lib/scripts/ && \
#     git clone --depth 1 --branch ${BIOMERO_VERSION} --single-branch https://github.com/NL-BioImaging/biomero-scripts.git biomero && \
#     rm -f biomero/admin/Example_Minimal_Slurm_Script.py

# Install the Figure-to-PDF script for OMERO.figure plugin
RUN curl -o $OMERO_DIST/lib/scripts/omero/figure_scripts/Figure_To_Pdf.py \
    https://raw.githubusercontent.com/ome/omero-figure/refs/heads/master/omero_figure/scripts/omero/figure_scripts/Figure_To_Pdf.py

# Install Labels2Rois script
RUN curl -o $OMERO_DIST/lib/scripts/omero/util_scripts/Labels2Rois.py \
    https://raw.githubusercontent.com/Cellular-Imaging-Amsterdam-UMC/label2rois/main/Labels2Rois.py

# Overwrite ICE configuration
# COPY ice.config $OMERO_DIST/etc/templates/
# Overwrite startup run
# COPY 99-run.sh /startup/99-run.sh

# entrypoint from omero-server dockerfile: 
# run all /startup/* scripts in alphabetic/numerical order.

RUN wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/com/github/ben-manes/caffeine/caffeine/3.1.8/caffeine-3.1.8.jar
RUN wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/dev/zarr/jzarr/0.4.2/jzarr-0.4.2.jar
RUN wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/org/lasersonlab/s3fs/2.2.3/s3fs-2.2.3.jar
RUN wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-s3/1.12.659/aws-java-sdk-s3-1.12.659.jar
RUN wget --no-hsts -O $OMERO_DIST/lib/server/omero-zarr-pixel-buffer.jar https://artifacts.glencoesoftware.com:443/artifactory/gs-omero-snapshots-local/com/glencoesoftware/omero/omero-zarr-pixel-buffer/0.5.0/omero-zarr-pixel-buffer-0.5.0.jar
