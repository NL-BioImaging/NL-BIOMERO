# Resolve omero-zarr-pixel-buffer and its full runtime dependency tree with Maven,
# so upgrading OMERO_ZARR_PIXEL_BUFFER_VERSION also upgrades the matching jars.
FROM maven:3.9-eclipse-temurin-11 AS zarr-deps
ARG OMERO_ZARR_PIXEL_BUFFER_VERSION
RUN test -n "$OMERO_ZARR_PIXEL_BUFFER_VERSION" || (echo "OMERO_ZARR_PIXEL_BUFFER_VERSION build arg is required" >&2; exit 1)
COPY server/zarr-pixel-buffer/pom.xml /build/pom.xml
RUN mvn -B -q -f /build/pom.xml dependency:copy-dependencies \
        -Domero.zarr.pixel.buffer.version=$OMERO_ZARR_PIXEL_BUFFER_VERSION \
        -DincludeScope=runtime \
        -Dmdep.stripVersion=true \
        -DoutputDirectory=/deps

FROM openmicroscopy/omero-server:5.6.18

ARG BIOMERO_SCRIPTS_VERSION
ARG LABEL2ROIS_VERSION

# ARG BIOMERO_SCRIPTS_BRANCH=master

ENV OMERO_DIST=/opt/omero/server/OMERO.server

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

# Development option: uncomment the branch ARG and ADD/RUN block below, and
# comment the release RUN block. The branch head invalidates the clone layer.
# ADD "https://api.github.com/repos/NL-BioImaging/biomero-scripts/commits/${BIOMERO_SCRIPTS_BRANCH}" /latest_commit_biomero_scripts
# RUN cd $OMERO_DIST/lib/scripts/ && \
#     git clone --depth 1 --branch ${BIOMERO_SCRIPTS_BRANCH} --single-branch https://github.com/NL-BioImaging/biomero-scripts.git biomero && \
#     rm -f biomero/admin/Example_Minimal_Slurm_Script.py && \
#     rm -f biomero/__workflows/SLURM_CellPose_Segmentation.py

# Release option: install the tag selected by BIOMERO_SCRIPTS_VERSION.
RUN test -n "$BIOMERO_SCRIPTS_VERSION" || (echo "BIOMERO_SCRIPTS_VERSION build arg is required" >&2; exit 1)
RUN cd $OMERO_DIST/lib/scripts/ && \
    git clone --depth 1 --branch ${BIOMERO_SCRIPTS_VERSION} --single-branch https://github.com/NL-BioImaging/biomero-scripts.git biomero && \
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
# Jars resolved in the zarr-deps stage are added to lib/server, skipping any
# library OMERO.server already ships so its own versions stay on the classpath.
COPY --from=zarr-deps --chown=omero-server:omero-server /deps /tmp/zarr-deps
RUN for jar in /tmp/zarr-deps/*.jar; do \
        name="$(basename "$jar" .jar)"; \
        if ls $OMERO_DIST/lib/server/"$name".jar $OMERO_DIST/lib/server/"$name"-[0-9]*.jar >/dev/null 2>&1; then \
            echo "Skipping $name (provided by OMERO.server)"; \
        else \
            cp "$jar" $OMERO_DIST/lib/server/; \
        fi; \
    done && \
    rm -rf /tmp/zarr-deps
