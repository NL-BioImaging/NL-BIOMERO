FROM openmicroscopy/omero-server:5.6.17

ARG BIOMERO_VERSION
ARG OMERO_ZARR_PIXEL_BUFFER_VERSION

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
ADD server/01-ldap-config.omero /opt/omero/server/config/

# Clone specific release version
# We don't need the example scripts
RUN cd $OMERO_DIST/lib/scripts/ && \
    git clone --depth 1 --branch ${BIOMERO_VERSION} --single-branch https://github.com/NL-BioImaging/biomero-scripts.git biomero && \
    rm -f biomero/admin/Example_Minimal_Slurm_Script.py && \
    rm -f biomero/__workflows/SLURM_CellPose_Segmentation.py

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

# Install ZARR support dependencies for BIOMERO.importer remote ZARR file rendering.
# The dependency versions are read from the selected omero-zarr-pixel-buffer POM so
# upgrading OMERO_ZARR_PIXEL_BUFFER_VERSION also upgrades the matching runtime jars.
RUN test -n "$OMERO_ZARR_PIXEL_BUFFER_VERSION" || (echo "OMERO_ZARR_PIXEL_BUFFER_VERSION build arg is required" >&2; exit 1)
RUN wget --no-hsts -O $OMERO_ZARR_PIXEL_BUFFER_POM $OMERO_ZARR_PIXEL_BUFFER_REPO/$OMERO_ZARR_PIXEL_BUFFER_VERSION/omero-zarr-pixel-buffer-$OMERO_ZARR_PIXEL_BUFFER_VERSION.pom
RUN version="$(awk '/<artifactId>caffeine<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/com/github/ben-manes/caffeine/caffeine/$version/caffeine-$version.jar
RUN version="$(awk '/<artifactId>jzarr<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/dev/zarr/jzarr/$version/jzarr-$version.jar
RUN version="$(awk '/<artifactId>s3fs<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/org/lasersonlab/s3fs/$version/s3fs-$version.jar
RUN version="$(awk '/<artifactId>aws-java-sdk-s3<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-core/$version/aws-java-sdk-core-$version.jar
RUN version="$(awk '/<artifactId>aws-java-sdk-s3<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-s3/$version/aws-java-sdk-s3-$version.jar
RUN version="$(awk '/<artifactId>tika-core<\/artifactId>/{getline; gsub(/.*<version>|<\/version>.*/, ""); print; exit}' $OMERO_ZARR_PIXEL_BUFFER_POM)" && wget --no-hsts -P $OMERO_DIST/lib/server https://repo1.maven.org/maven2/org/apache/tika/tika-core/$version/tika-core-$version.jar
RUN wget --no-hsts -O $OMERO_DIST/lib/server/omero-zarr-pixel-buffer.jar $OMERO_ZARR_PIXEL_BUFFER_REPO/$OMERO_ZARR_PIXEL_BUFFER_VERSION/omero-zarr-pixel-buffer-$OMERO_ZARR_PIXEL_BUFFER_VERSION.jar
RUN rm -f $OMERO_ZARR_PIXEL_BUFFER_POM
