#!/bin/bash
# Initialize biomero library for development in the biomeroworker container

CONTAINER_NAME="nl-biomero-biomeroworker-1"

# Mark volume-mounted repo as safe for git (needed by setuptools_scm)
COMMAND_GIT="git config --global --add safe.directory /opt/omero/server/biomero"

# Install biomero in editable mode
COMMAND1="/opt/omero/server/venv3/bin/python -m pip install -e /opt/omero/server/biomero[full]"

# Restart the OMERO processor to pick up changes
COMMAND2="kill \$(cat /opt/omero/server/OMERO.server/var/master/biomeroworker.pid 2>/dev/null) 2>/dev/null; sleep 2"

docker exec --user root "$CONTAINER_NAME" sh -c "$COMMAND_GIT"
docker exec --user root "$CONTAINER_NAME" sh -c "$COMMAND1"
echo "biomero installed in editable mode."
echo "Note: restart the biomeroworker container to pick up changes:"
echo "  docker compose -f docker-compose-dev.yml restart biomeroworker"
