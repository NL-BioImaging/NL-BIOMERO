OME-Zarr Viewer
===============

NL-BIOMERO includes the read-only `BIOMERO OME-Zarr Viewer
<https://github.com/NL-BioImaging/BIOMERO.ZarrViewer>`_ in its OMERO.web
image. It opens physical OME-Zarr stores registered by an in-place BIOMERO
import and supports multichannel images, segmentation labels, Z stacks, and
HCS plates.

Deployment requirements
-----------------------

The viewer uses an Nginx ``X-Accel-Redirect`` after OMERO.web authorizes each
request. Use the SSL deployment scenario:

.. code-block:: bash

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     up -d

That scenario mounts ``web/L-Drive`` at ``/data`` in both services:

* OMERO.web receives its existing read-write mount for BIOMERO operations.
* Nginx receives a read-only mount and exposes it only through the internal
  ``/_biomero_zarr_internal/`` location.

The default direct OMERO.web endpoint does not process
``X-Accel-Redirect``. It can return viewer capabilities, but cannot deliver
OME-Zarr metadata or chunks. Access the viewer through the SSL Nginx endpoint.

Storage paths
-------------

The bundled configuration assumes that BIOMERO records stores below
``/data`` and that OMERO.web mounts the same tree at ``/data``. These defaults
match ``IMPORT_MOUNT_PATH=/data`` and the supplied Compose files.

If the path recorded in OMERO differs from the OMERO.web mount, change only
the source root. For example, when OMERO records
``/archive/project/example.ome.zarr`` while the container sees
``/data/project/example.ome.zarr``:

.. code-block:: bash

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     exec omeroweb \
     omero config set omero.web.zarr_viewer.source_root /archive

The suffix below both roots must remain identical. If Nginx uses another
mount point, update the ``alias`` in ``nginx/nginx.conf`` to that container
path.

Verification
------------

1. Sign in to OMERO.web through the HTTPS Nginx endpoint.
2. Select a BIOMERO-imported OME-Zarr image or plate.
3. Choose **Open With → OME-Zarr Viewer**.
4. Confirm that viewer data requests return HTTP 200 or 206.
5. Request a path below ``/_biomero_zarr_internal/`` directly and confirm
   that Nginx returns 404.

Validate the Nginx configuration with:

.. code-block:: bash

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     exec nginx nginx -t

If the viewer opens but reports **Failed to fetch**, confirm that OMERO.web
and Nginx see the same underlying store tree below their configured roots.

Security model
--------------

The internal Nginx location is not directly browser-accessible. OMERO.web
first checks the signed-in user, active group, selected OMERO object, physical
store, and requested key. It then returns an internal redirect for Nginx to
serve the authorized file. The Nginx storage mount is read-only.
