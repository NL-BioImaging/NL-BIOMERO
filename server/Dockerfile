FROM openmicroscopy/omero-server:5.6.18

ARG BIOMERO_SCRIPTS_VERSION
ARG LABEL2ROIS_VERSION
ARG OMERO_ZARR_PIXEL_BUFFER_VERSION

# Development-only branch wiring for the scheduler-native image-pull proof of
# concept. Restore the versioned clone below after cross-repository testing.
ARG BIOMERO_SCRIPTS_BRANCH=feature/slurm-image-pull-array
ADD "https://api.github.com/repos/NL-BioImaging/biomero-scripts/commits/${BIOMERO_SCRIPTS_BRANCH}" /latest_commit_biomero_scripts

ENV OMERO_DIST=/opt/omero/server/OMERO.server
ENV OMERO_ZARR_PIXEL_BUFFER_REPO=https://artifacts.glencoesoftware.com:443/artifactory/gs-omero-snapshots-local/com/glencoesoftware/omero/omero-zarr-pixel-buffer
ENV OMERO_ZARR_PIXEL_BUFFER_POM=/tmp/omero-zarr-pixel-buffer.pom

# Upload scripts for omero-server user
# COPY --chown=omero-server:omero-server scripts/slurm/* /opt/omero/server/OMERO.server/lib/scripts/slurm/
USER root
RUN echo 'skip_if_unavailable=True' >> /etc/dnf/dnf.conf
RUN yum -y install git
USER omero-server

# Configuration files - use shell script for restore
ADD server/00-restore-config.sh* /startup/
# LDAP configuration - add with correct values
# ADD server/01-ldap-config.omero /opt/omero/server/config/

RUN cd $OMERO_DIST/lib/scripts/ && \
    git clone --depth 1 --branch ${BIOMERO_SCRIPTS_BRANCH} --single-branch https://github.com/NL-BioImaging/biomero-scripts.git biomero && \
    rm -f biomero/admin/Example_Minimal_Slurm_Script.py && \
    rm -f biomero/__workflows/SLURM_CellPose_Segmentation.py

# Do not expose repository tests as runnable OMERO scripts.
RUN rm -rf $OMERO_DIST/lib/scripts/biomero/tests || true

# Install the Figure-to-PDF script for OMERO.figure plugin (versioned)
RUN curl -o $OMERO_DIST/lib/scripts/omero/figure_scripts/Figure_To_Pdf.py \
    https://raw.githubusercontent.com/ome/omero-figure/v7.4.1/omero_figure/scripts/omero/figure_scripts/Figure_To_Pdf.py

# Install Labels2Rois (versioned)
RUN curl -o $OMERO_DIST/lib/scripts/omero/util_scripts/Labels2Rois.py \
    https://raw.githubusercontent.com/Cellular-Imaging-Amsterdam-UMC/label2rois/${LABEL2ROIS_VERSION}/Labels2Rois.py

# Overwrite ICE configuration
# COPY ice.config $OMERO_DIST/etc/templates/
# Overwrite startup run
# COPY 99-run.sh /startup/99-run.sh

# entrypoint from omero-server dockerfile: 
# run all /startup/* scripts in alphabetic/numerical order.

# Install ZARR support dependencies for BIOMERO.importer remote ZARR file rendering.
# The dependency versions are read from the selected omero-zarr-pixel-buffer POM so
# upgrading OMERO_ZARR_PIXEL_BUFFER_VERSION also upgrades the matching runtime jars.
RUN test -n "$OMERO_ZARR_PIXEL_BUFFER_VERSION" || (echo "OMERO_ZARR_PIXEL_BUFFER_VERSION build arg is required" >&2; exit 1)
RUN wget --no-hsts -O $OMERO_ZARR_PIXEL_BUFFER_POM $OMERO_ZARR_PIXEL_BUFFER_REPO/$OMERO_ZARR_PIXEL_BUFFER_VERSION/omero-zarr-pixel-buffer-$OMERO_ZARR_PIXEL_BUFFER_VERSION.pom
RUN version="$(awk '/<artifactId>caffeine<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && curl -fL -o $OMERO_DIST/lib/server/caffeine-$version.jar https://repo.maven.apache.org/maven2/com/github/ben-manes/caffeine/caffeine/$version/caffeine-$version.jar
RUN version="$(awk '/<artifactId>jzarr<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && curl -fL -o $OMERO_DIST/lib/server/jzarr-$version.jar https://repo.maven.apache.org/maven2/dev/zarr/jzarr/$version/jzarr-$version.jar
RUN version="$(awk '/<artifactId>s3fs<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && curl -fL -o $OMERO_DIST/lib/server/s3fs-$version.jar https://repo.maven.apache.org/maven2/org/lasersonlab/s3fs/$version/s3fs-$version.jar
RUN version="$(awk '/<artifactId>aws-java-sdk-s3<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && curl -fL -o $OMERO_DIST/lib/server/aws-java-sdk-core-$version.jar https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk-core/$version/aws-java-sdk-core-$version.jar
RUN version="$(awk '/<artifactId>aws-java-sdk-s3<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && curl -fL -o $OMERO_DIST/lib/server/aws-java-sdk-s3-$version.jar https://repo.maven.apache.org/maven2/com/amazonaws/aws-java-sdk-s3/$version/aws-java-sdk-s3-$version.jar
RUN version="$(awk '/<artifactId>tika-core<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && curl -fL -o $OMERO_DIST/lib/server/tika-core-$version.jar https://repo.maven.apache.org/maven2/org/apache/tika/tika-core/$version/tika-core-$version.jar
RUN wget --no-hsts -O $OMERO_DIST/lib/server/omero-zarr-pixel-buffer.jar $OMERO_ZARR_PIXEL_BUFFER_REPO/$OMERO_ZARR_PIXEL_BUFFER_VERSION/omero-zarr-pixel-buffer-$OMERO_ZARR_PIXEL_BUFFER_VERSION.jar
RUN rm -f $OMERO_ZARR_PIXEL_BUFFER_POM
