# Temporary reader build for https://github.com/glencoesoftware/omero-zarr-pixel-buffer/pull/60
# (NL-BIOMERO #42; removal tracked in #48). Pin the tested commit rather than following the PR branch.
# Once the fix is released, remove this stage, its ARG/LABELs and the marked
# dependency guard/JAR overlay below; keep the Maven release installation.
ARG OMERO_ZARR_PIXEL_BUFFER_REVISION=da3799e0c59fe9e8e2d562fab67a99b6a6e55b4a
FROM gradle:9.4.1-jdk17 AS zarr-reader-build
ARG OMERO_ZARR_PIXEL_BUFFER_REVISION
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libblosc1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build/reader
RUN git init . \
    && git remote add origin https://github.com/glencoesoftware/omero-zarr-pixel-buffer.git \
    && git fetch --depth=1 origin "$OMERO_ZARR_PIXEL_BUFFER_REVISION" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "$OMERO_ZARR_PIXEL_BUFFER_REVISION"
# Java 17 builds Java 11-compatible bytecode; upstream tests need libblosc1.
# Empty publishing properties allow a local build without upstream credentials.
RUN ./gradlew --no-daemon --console=plain --max-workers=2 \
    -PArtifactoryUserName= -PArtifactoryPassword= build

# Release dependency resolution. The pinned PR has the same runtime dependencies
# as 0.7.1; only its reader JAR is substituted below.
FROM maven:3.9-eclipse-temurin-11 AS zarr-deps
ARG OMERO_ZARR_PIXEL_BUFFER_VERSION
RUN test -n "$OMERO_ZARR_PIXEL_BUFFER_VERSION" || (echo "OMERO_ZARR_PIXEL_BUFFER_VERSION build arg is required" >&2; exit 1)
# Temporary PR #60 guard: do not silently mix this patch with another dependency set.
RUN test "$OMERO_ZARR_PIXEL_BUFFER_VERSION" = "0.7.1" || (echo "Pinned reader PR #60 requires OMERO_ZARR_PIXEL_BUFFER_VERSION=0.7.1 for its runtime dependencies" >&2; exit 1)
COPY server/zarr-pixel-buffer/pom.xml /build/pom.xml
RUN mvn -B -q -f /build/pom.xml dependency:copy-dependencies \
        -Domero.zarr.pixel.buffer.version=$OMERO_ZARR_PIXEL_BUFFER_VERSION \
        -DincludeScope=runtime \
        -Dmdep.stripVersion=true \
        -DoutputDirectory=/deps
# Temporary PR #60 overlay: replace the released JAR, keeping its dependencies.
COPY --from=zarr-reader-build /build/reader/build/libs/omero-zarr-pixel-buffer-0.7.2-SNAPSHOT.jar /deps/omero-zarr-pixel-buffer.jar

FROM openmicroscopy/omero-server:5.6.18

ARG BIOMERO_SCRIPTS_VERSION
ARG LABEL2ROIS_VERSION
ARG OMERO_ZARR_PIXEL_BUFFER_REVISION
LABEL nl.biomero.reader.upstream-pr="https://github.com/glencoesoftware/omero-zarr-pixel-buffer/pull/60" \
      nl.biomero.reader.revision="${OMERO_ZARR_PIXEL_BUFFER_REVISION}"

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
# Replace any older reader JAR so exactly one reader implementation is installed.
COPY --from=zarr-deps --chown=omero-server:omero-server /deps /tmp/zarr-deps
RUN set -eu; \
    for jar in /tmp/zarr-deps/*.jar; do \
        name="$(basename "$jar" .jar)"; \
        provided=false; \
        for existing in "$OMERO_DIST/lib/server/$name.jar" "$OMERO_DIST/lib/server/$name"-[0-9]*.jar; do \
            [ -f "$existing" ] || continue; \
            if [ "$name" = "omero-zarr-pixel-buffer" ]; then \
                rm -f "$existing"; \
            else \
                provided=true; \
            fi; \
        done; \
        if [ "$provided" = true ]; then \
            echo "Skipping $name (provided by OMERO.server)"; \
        else \
            cp "$jar" "$OMERO_DIST/lib/server/"; \
        fi; \
    done && \
    rm -rf /tmp/zarr-deps
