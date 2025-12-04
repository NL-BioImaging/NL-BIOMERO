FROM openmicroscopy/omero-server:5.6.16

COPY ice.config worker.cfg /opt/omero/server/OMERO.server/etc/templates/

USER root

ENV VIRTUAL_ENV=/opt/omero/server/venv3
ENV PATH=/opt/ice-3.6.5-0.3.0/bin:$VIRTUAL_ENV/bin/:$PATH
# Use existing venv and install packages
RUN $VIRTUAL_ENV/bin/python -m pip install scikit-image scipy

# Replace the default startup scripts
RUN rm /startup/60-database.sh
COPY 99-run.sh /startup/99-run.sh
RUN chmod +x /startup/99-run.sh
USER omero-server
