OME-Zarr Viewer
===============

The `BIOMERO OME-Zarr Viewer
<https://nl-bioimaging.github.io/BIOMERO.ZarrViewer/>`_ adds read-only viewing
of registered OME-Zarr Images, Plates and Wells to OMERO.web. It displays
multichannel pixels and segmentation labels, including labels stored in a
shallow result while the intensity pixels remain in their canonical store.

The NL-BIOMERO demo enables the viewer. Existing deployments keep it disabled
after an upgrade until an administrator opts in and configures storage and the
reverse proxy.

.. note::
   **Summary for system administrators:**

   * Install the viewer package and register it as a standard OMERO.web
     application and Open With option.
   * Give OMERO.web and Nginx access to the same OME-Zarr storage tree. Nginx
     needs read-only access.
   * Add a protected Nginx storage location and an uncached viewer route.
   * Enable ``BIOMERO_ZARR_VIEWER_ENABLED=TRUE`` and recreate OMERO.web.
   * Keep Nginx between the browser and OMERO.web. Direct Gunicorn access cannot
     deliver the authorized Zarr files.

How authorized delivery works
-----------------------------

For every metadata or chunk request, OMERO.web checks the signed-in user,
active group, selected object and requested Zarr key. An allowed request
returns an ``X-Accel-Redirect`` header. Nginx receives that response and reads
the approved file from an ``internal`` location. The browser never receives a
filesystem path and cannot request that internal location directly.

Nginx may be the public HTTPS reverse proxy, or an internal gateway behind an
existing load balancer or reverse proxy. In either layout, the Nginx process
receiving the OMERO.web response must be able to read the Zarr storage.

Prerequisites
-------------

Before enabling the viewer, confirm that:

* the OMERO.web image contains ``biomero-zarr-viewer``;
* OME-Zarr data is registered in OMERO by BIOMERO.importer or another
  compatible registration process;
* OMERO.web can read that data below ``IMPORT_MOUNT_PATH``;
* Nginx can read the same relative directory tree; and
* users access OMERO.web through one reverse-proxy origin for login, Open With
  and viewer requests.

The viewer is independent of the shallow-storage and detached-workflow flags.
Those features are needed only when their processing or storage behavior is
wanted.

OMERO.web plugin registration
-----------------------------

The viewer is a standard OMERO.web plugin. It does not need a service account,
database, migration or one-time initialization. Like other OMERO.web plugins,
it must be installed in the web environment and added to ``omero.web.apps``.
Its Open With declaration and storage settings must also be added to the OMERO
configuration.

The viewer repository supplies the standard `90-biomero-zarr-viewer.omero
configuration file
<https://github.com/NL-BioImaging/BIOMERO.ZarrViewer/blob/main/docker/90-biomero-zarr-viewer.omero>`_.
A deployment that always enables the viewer can install that file in
``/opt/omero/web/config/`` alongside its other OMERO.web plugin configuration
files. No NL-BIOMERO startup script is required in that layout.

NL-BIOMERO opt-in registration
------------------------------

The published NL-BIOMERO OMERO.web image includes the Python package and
compiled frontend. It uses the `web/55-configure-zarr-viewer.py startup script
<https://github.com/NL-BioImaging/NL-BIOMERO/blob/master/web/55-configure-zarr-viewer.py>`_.
This is NL-BIOMERO deployment glue for the backward-compatible feature flag;
it is not extra initialization required by the viewer. The script runs after
the normal OMERO.web configuration and:

* registers the Django application and Open With entry when enabled;
* preserves other installed applications and Open With entries;
* configures the recorded source root, mounted storage root and internal Nginx
  prefix; and
* removes only the viewer registration when the feature is disabled.

Add the following flag to the deployment environment:

.. code-block:: ini

   BIOMERO_ZARR_VIEWER_ENABLED=TRUE

Missing, empty and false values leave the viewer disabled. After changing the
flag, recreate OMERO.web; a restart does not load changed Compose environment
values.

Use an existing custom OMERO.web image
--------------------------------------

Administrators who keep their own OMERO.web image must:

1. Install ``biomero-zarr-viewer`` from PyPI in the OMERO.web Python
   environment. Pin the package according to the deployment's release policy.
2. Add the standard viewer ``.omero`` configuration file, or add equivalent
   application, Open With and storage settings through the site's existing
   OMERO configuration management.

For an image based on ``openmicroscopy/omero-web-standalone``, the relevant
Dockerfile additions are:

.. code-block:: dockerfile

   ARG BIOMERO_ZARR_VIEWER_VERSION
   RUN test -n "$BIOMERO_ZARR_VIEWER_VERSION"
   RUN /opt/omero/web/venv3/bin/pip install \
       "biomero-zarr-viewer==${BIOMERO_ZARR_VIEWER_VERSION}"

   COPY 90-biomero-zarr-viewer.omero \
       /opt/omero/web/config/90-biomero-zarr-viewer.omero

The standard file enables the viewer whenever that image is used. A custom
deployment that wants the same opt-in behavior as NL-BIOMERO may instead copy
``55-configure-zarr-viewer.py`` into its startup sequence and pass the feature
flag and storage-root environment values. The supplied script calls
``/opt/omero/web/venv3/bin/omero``; adapt that path if the custom image uses
another virtual environment.

Upgrade the supplied HTTPS deployment
-------------------------------------

The supplied
``deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml`` already
contains the required wiring. Its existing ``nginx`` service mounts the same
store as OMERO.web, includes the protected data location and disables shared
caching for the viewer route.

Preserve the site's environment, credentials, hostname and certificate paths.
Select an NL-BIOMERO image release containing the viewer, enable the flag above
and render the Compose configuration before recreating services:

.. code-block:: bash

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     config --quiet

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     pull omeroweb

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     up -d --no-deps --force-recreate omeroweb nginx

   docker compose \
     --env-file .env \
     --file deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml \
     exec nginx nginx -t

See :doc:`linux-deployment` for the complete Linux/HTTPS deployment procedure.

Configure a customized Nginx deployment
---------------------------------------

If the site maintains custom Compose and Nginx files, add the following pieces
to those files instead of replacing the complete configuration.

Compose services
~~~~~~~~~~~~~~~~

Pass the feature flag and storage roots to OMERO.web. Mount the same host
storage in OMERO.web and Nginx. The example host path is illustrative; use the
site's actual storage location.

.. code-block:: yaml

   services:
     omeroweb:
       image: "cellularimagingcf/omeroweb:${NL_BIOMERO_VERSION}"
       environment:
         BIOMERO_ZARR_VIEWER_ENABLED: ${BIOMERO_ZARR_VIEWER_ENABLED:-false}
         BIOMERO_ZARR_VIEWER_SOURCE_ROOT: ${BIOMERO_ZARR_VIEWER_SOURCE_ROOT:-}
         IMPORT_MOUNT_PATH: /data
       volumes:
         - "/srv/biomero/zarr:/data:ro"
       networks:
         - omero

     nginx:
       image: nginx:alpine
       volumes:
         - "./nginx.conf:/etc/nginx/nginx.conf:ro"
         - "/srv/biomero/zarr:/data:ro"
         - "/etc/letsencrypt:/etc/letsencrypt:ro"
       networks:
         - omero
       ports:
         - "443:443"

Do not publish OMERO.web's Gunicorn port to users. If host access is required
for administration, bind it to loopback and keep the public OMERO hostname
pointed at Nginx.

HTTPS Nginx server
~~~~~~~~~~~~~~~~~~

Add these locations inside the existing HTTPS ``server`` block. Keep the
site's current ``listen``, ``server_name`` and TLS certificate settings. The
``alias`` is a path in the Nginx container or host and must end in ``/``.

.. code-block:: nginx

   # Only an X-Accel-Redirect returned after OMERO authorization can enter.
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

   # Capability checks, metadata, chunks and rendered tiles must reach
   # OMERO.web and must not enter a shared proxy cache.
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

The existing ``location /`` may continue to proxy other OMERO.web traffic. If
it uses ``proxy_cache``, the more specific location above prevents viewer
authorization and image responses from entering that shared cache.

If Nginx runs directly on the host, replace ``http://omeroweb:4080`` with the
site's private OMERO.web upstream and set ``alias`` to the host path of the
same Zarr tree.

Use another public reverse proxy
--------------------------------

Apache, Traefik, HAProxy and cloud load balancers do not process Nginx
``X-Accel-Redirect`` responses. Keep the existing proxy as the public TLS
endpoint and place a small Nginx gateway between it and OMERO.web:

.. code-block:: text

   Browser -> existing HTTPS proxy -> Nginx viewer gateway -> OMERO.web
                                      |
                                      +-> read-only Zarr storage

Route the complete OMERO hostname from the existing proxy to the Nginx gateway,
not directly to OMERO.web. The gateway can start from
``nginx/zarrviewer.conf`` and needs no published host port when both proxies
share a private network. The outer proxy must pass ``Host``,
``X-Forwarded-For`` and ``X-Forwarded-Proto``.

When TLS terminates at the outer proxy, preserve that protocol in the gateway.
Add this ``map`` inside its ``http`` block:

.. code-block:: nginx

   map $http_x_forwarded_proto $biomero_forwarded_proto {
       ""      $scheme;
       default $http_x_forwarded_proto;
   }

Use the mapped value in the gateway's proxy location:

.. code-block:: nginx

   proxy_set_header X-Forwarded-Proto $biomero_forwarded_proto;

The gateway still needs the protected internal location and read-only storage
mount shown above. Never create a public route to
``/_biomero_zarr_internal/``.

Map registered paths to mounted storage
---------------------------------------

``IMPORT_MOUNT_PATH`` is the root from which OMERO.web reads Zarr data.
``BIOMERO_ZARR_VIEWER_SOURCE_ROOT`` is the prefix recorded in OMERO. It
defaults to ``IMPORT_MOUNT_PATH`` and only needs an explicit value when the
prefixes differ.

.. code-block:: ini

   IMPORT_MOUNT_PATH=/data
   BIOMERO_ZARR_VIEWER_SOURCE_ROOT=/archive

With these values, an OMERO registration for
``/archive/alice/example.ome.zarr`` resolves to
``/data/alice/example.ome.zarr`` inside OMERO.web and Nginx. Preserve the
relative tree below that prefix. Complete stores and shallow-result manifests
both depend on this mapping.

The Nginx ``alias`` must point to the same mounted root used by
``IMPORT_MOUNT_PATH``. The Nginx worker and OMERO.web user must be able to read
directories, metadata and chunks. The viewer never writes to the store.

Recreate and verify
-------------------

For a custom Compose deployment, apply the configuration and inspect startup:

.. code-block:: bash

   docker compose config --quiet
   docker compose up -d --no-deps --force-recreate omeroweb nginx
   docker compose exec nginx nginx -t
   docker compose logs --tail=100 omeroweb nginx

The OMERO.web log should contain ``OME-Zarr Viewer enabled``. Then:

1. Open the public HTTPS URL and sign in to OMERO.web.
2. Select a registered OME-Zarr Image, Plate or Well and choose
   **Open With > OME-Zarr Viewer**.
3. Confirm intensity channels and Z/T navigation. For a Plate, open a Well and
   then a Field. For a shallow result, confirm its labels appear over the
   canonical intensity pixels.
4. In browser developer tools, confirm requests below
   ``/biomero_zarr_viewer/data/images/`` return 200 or 206 with non-empty
   response bodies.
5. Request ``https://<omero-host>/_biomero_zarr_internal/test`` directly. It
   must return 404; a successful response means storage is exposed.
6. Sign out and confirm viewer data requests redirect to login or return an
   authorization error.

Troubleshooting and rollback
----------------------------

**The Open With entry is absent**
   Confirm that startup logged ``OME-Zarr Viewer enabled`` and that exactly one
   eligible Image, Plate or Well is selected. Confirm that the object has a
   compatible physical OME-Zarr registration.

**The viewer reports Failed to fetch, or tile requests return 500**
   Confirm that the browser uses Nginx instead of Gunicorn. Compare the
   resolved relative path below ``/data`` in both containers, check read
   permissions and verify that the internal location is in the active Nginx
   ``server`` block.

**Links use HTTP behind an HTTPS load balancer**
   Preserve the outer proxy's ``X-Forwarded-Proto`` value in the Nginx gateway
   as shown above.

**Nginx returns 404 after OMERO.web authorizes the request**
   Check the trailing slash on ``location`` and ``alias``, the storage mount,
   and the source-root mapping. The Nginx error log shows the filesystem path
   it attempted to open.

To disable the viewer, set ``BIOMERO_ZARR_VIEWER_ENABLED=FALSE`` and recreate
OMERO.web. The registration script removes only this application. The Nginx
locations and read-only mount may remain in place.

The `viewer documentation
<https://nl-bioimaging.github.io/BIOMERO.ZarrViewer/>`_ describes supported
OME-Zarr layouts, controls and rendering limits. The `BIOMERO Schema Zarr
contracts <https://nl-bioimaging.github.io/biomero-schema/zarr-contracts/>`_
describe canonical and shallow-store path records.

Local HTTP demo
---------------

For local evaluation, the root ``docker-compose.yml`` includes
``zarrviewer-nginx`` and publishes it at http://localhost:4080. Start it with
``docker compose up -d --build``. This localhost route is only the supplied
demo; production administrators should use one of the HTTPS layouts above.
