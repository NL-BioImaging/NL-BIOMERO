#!/usr/bin/env bash
set -e

# Using `-v $HOME/.ssh:/opt/omero/server/.ssh:ro` produce permissions error while in the container
# when working from Linux and maybe from Windows.
# To prevent that we offer the strategy to mount the `.ssh` folder with
# `-v $HOME/.ssh:/tmp/.ssh:ro` thus this entrypoint will automatically handle problem.

if [[ -d /tmp/.ssh ]]; then
  # Replace the target directory contents on every startup to avoid nesting
  # /opt/omero/server/.ssh/.ssh on container restarts.
  rm -rf /opt/omero/server/.ssh
  mkdir -p /opt/omero/server/.ssh
  # TODO: error on windows ? this didn't copy 'config'
  cp -R /tmp/.ssh/. /opt/omero/server/.ssh/
  chmod 700 /opt/omero/server/.ssh
  chmod 600 /opt/omero/server/.ssh/*
  chmod 644 /opt/omero/server/.ssh/*.pub
  chmod 644 /opt/omero/server/.ssh/known_hosts
fi

exec "$@"
