OME-Zarr Viewer
===============

The `BIOMERO OME-Zarr Viewer
<https://nl-bioimaging.github.io/BIOMERO.ZarrViewer/>`_ lets users open
registered OME-Zarr data directly from OMERO.web. It provides multichannel and
Z/T viewing, segmentation overlays, and Field, Well and Plate navigation. The
viewer is read-only and does not convert conventional OMERO images.

The supplied NL-BIOMERO Docker Compose demo already installs, registers and
proxies the viewer, and enables it in the demo environment. No additional
viewer setup is needed when starting that stack normally. The installation
steps below are for existing production and custom deployments. Those
deployments opt in with ``BIOMERO_ZARR_VIEWER_ENABLED=TRUE``.

.. note::
   **Summary for system administrators:**

   * The NL-BIOMERO Docker Compose demo is ready to use and enables the viewer.
   * Existing production and custom setups need the Python package, OMERO.web
     registration and two Nginx locations for authenticated file delivery.
   * Enable it to add its **Open With** entry for registered OME-Zarr Images,
     Plates and Wells.
   * Nginx needs read-only access to the same OME-Zarr storage as OMERO.web.

Installation
------------

An installation has three parts:

1. Install the viewer package in the OMERO.web Python environment.
2. Register the application, Open With entry and storage settings in OMERO.web.
3. Add the authenticated file-delivery locations to the existing Nginx
   configuration.

Install the package
~~~~~~~~~~~~~~~~~~~

Install a selected release in the same Python environment as OMERO.web:

.. code-block:: bash

   /opt/omero/web/venv3/bin/pip install \
       "biomero-zarr-viewer==<selected-version>"

The package includes the compiled frontend; Node.js is not required on the
server.

Register the plugin
~~~~~~~~~~~~~~~~~~~

NL-BIOMERO runs `web/55-configure-zarr-viewer.py
<https://github.com/NL-BioImaging/NL-BIOMERO/blob/master/web/55-configure-zarr-viewer.py>`_
after the normal OMERO.web configuration. Add that script to the equivalent
startup stage when maintaining a separate OMERO.web installation. Adapt its
``OMERO`` executable path if the virtual environment is elsewhere.

Set:

.. code-block:: ini

   BIOMERO_ZARR_VIEWER_ENABLED=TRUE
   IMPORT_MOUNT_PATH=/data

The script registers the standard OMERO.web application and Open With entry.
Missing, empty and false enablement values leave the viewer disabled.

A deployment that does not need the NL-BIOMERO feature flag may instead apply
the viewer's standard `90-biomero-zarr-viewer.omero configuration
<https://github.com/NL-BioImaging/BIOMERO.ZarrViewer/blob/main/docker/90-biomero-zarr-viewer.omero>`_.
The viewer needs no service account, database or migration.

Add the Nginx locations
~~~~~~~~~~~~~~~~~~~~~~~

Nginx must be able to read the same OME-Zarr directory tree as OMERO.web. Add
these locations inside the existing OMERO.web HTTPS ``server`` block. Adjust
``alias`` and ``proxy_pass`` for the deployment:

.. code-block:: nginx

   # OMERO.web authorizes the request before Nginx serves the file.
   location ^~ /_biomero_zarr_internal/ {
       internal;
       alias /data/;
       autoindex off;
       disable_symlinks on;
       etag on;
       types {
           application/json json zattrs zarray zgroup zmetadata;
       }
       default_type application/octet-stream;
       add_header X-Content-Type-Options nosniff always;
       add_header Cache-Control "private, max-age=300" always;
   }

   location ^~ /biomero_zarr_viewer/ {
       proxy_pass http://omeroweb:4080;
       proxy_http_version 1.1;
       proxy_set_header Host $http_host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto https;
       proxy_cache off;
       proxy_buffering off;
       proxy_read_timeout 600s;
   }

Mount or expose the storage read-only to Nginx at the path used by ``alias``.
The supplied HTTPS Compose scenario does this with:

.. code-block:: yaml

   services:
     nginx:
       volumes:
         - "../web/L-Drive:/data:ro"

When another proxy terminates HTTPS before Nginx, preserve its forwarded
protocol instead of setting it to a fixed value:

.. code-block:: nginx

   proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;

Storage path mapping
--------------------

``IMPORT_MOUNT_PATH`` is the storage root visible to OMERO.web and normally
matches the Nginx ``alias``. If OMERO contains paths with a different recorded
prefix, set that prefix separately:

.. code-block:: ini

   IMPORT_MOUNT_PATH=/data
   BIOMERO_ZARR_VIEWER_SOURCE_ROOT=/archive

An OMERO path such as ``/archive/alice/example.ome.zarr`` then resolves to
``/data/alice/example.ome.zarr``. The relative path below the two roots must be
identical.

Apply and verify
----------------

Recreate OMERO.web after changing its environment or startup configuration,
then validate and reload Nginx. With the supplied HTTPS Compose scenario:

.. code-block:: bash

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     up -d --no-deps --force-recreate omeroweb nginx

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     exec nginx nginx -t

Check the deployment:

1. Confirm the OMERO.web log contains ``OME-Zarr Viewer enabled``.
2. Sign in, select a registered OME-Zarr Image, Plate or Well, and choose
   **Open With > OME-Zarr Viewer**.
3. Confirm viewer data requests return 200 or 206.
4. Confirm a direct request to
   ``https://<omero-host>/_biomero_zarr_internal/test`` returns 404.

If the viewer reports **Failed to fetch** or tile requests return 500, check
the Nginx error log, storage permissions and the relative path below the
OMERO.web and Nginx storage roots.

Set ``BIOMERO_ZARR_VIEWER_ENABLED=FALSE`` and recreate OMERO.web to remove the
viewer registration.

See the `viewer documentation
<https://nl-bioimaging.github.io/BIOMERO.ZarrViewer/>`_ for supported OME-Zarr
layouts and controls. Shallow-result storage and its path records are described
separately in :doc:`remote-shallower` and the `BIOMERO Schema Zarr contracts
<https://nl-bioimaging.github.io/biomero-schema/zarr-contracts/>`_.
