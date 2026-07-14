#!/bin/bash

set -eu

omero=/opt/omero/server/venv3/bin/omero
cd /opt/omero/server

# Get IPs https://unix.stackexchange.com/a/20793
MASTER_ADDR=$(getent hosts $CONFIG_omero_master_host | cut -d\  -f1)
WORKER_ADDR=$(getent hosts $OMERO_WORKER_NAME | cut -d\  -f1)

echo "Master addr: $MASTER_ADDR Worker addr: $WORKER_ADDR"
sed \
    -e "s/@omero.worker.host@/$WORKER_ADDR/" \
    -e "s/@worker.name@/$OMERO_WORKER_NAME/" \
    OMERO.server/etc/templates/worker.cfg > \
    OMERO.server/etc/$OMERO_WORKER_NAME.cfg
sed \
    -e "s/@omero.master.host@/$MASTER_ADDR/" \
    OMERO.server/etc/templates/ice.config > \
    OMERO.server/etc/ice.config

echo "Starting background poller daemon..."
python3 /opt/omero/server/biomero_poller.py &

echo "Starting node $OMERO_WORKER_NAME"
exec $omero node $OMERO_WORKER_NAME start --foreground
