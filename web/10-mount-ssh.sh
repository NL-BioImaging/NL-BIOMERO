#!/usr/bin/env bash
set -e

if [[ -d /tmp/.ssh ]]; then
  rm -rf /opt/omero/web/OMERO.web/var/.ssh
  mkdir -p /opt/omero/web/OMERO.web/var/.ssh
  cp -R /tmp/.ssh/. /opt/omero/web/OMERO.web/var/.ssh/
  chmod 700 /opt/omero/web/OMERO.web/var/.ssh
  chmod 600 /opt/omero/web/OMERO.web/var/.ssh/*
  chmod 644 /opt/omero/web/OMERO.web/var/.ssh/*.pub 2>/dev/null || true
  chmod 644 /opt/omero/web/OMERO.web/var/.ssh/known_hosts 2>/dev/null || true
fi
