OME-Zarr Viewer
=======================

The `BIOMERO OME-Zarr Viewer
<https://github.com/NL-BioImaging/BIOMERO.ZarrViewer>`_ opens physical OME-Zarr
stores registered in OMERO. It provides channel controls, Z/T navigation,
segmentation label overlays and HCS Field, Well and Plate views. It is read-only
and does not convert conventional OMERO images into OME-Zarr.

The NL-BIOMERO demo enables it with ``BIOMERO_ZARR_VIEWER_ENABLED=TRUE``.
Existing deployments opt in with that flag and the proxy/storage configuration
below. A missing, empty or false flag leaves the viewer disabled.

.. note::
   **Summary for system administrators:**

   * Use a web image containing the viewer package and enable
     ``BIOMERO_ZARR_VIEWER_ENABLED=TRUE`` on OMERO.web.
   * A compatible Nginx frontend and read-only access to the registered Zarr
     storage are required; the flag alone is not sufficient.
   * In the local demo, access OMERO through port **4080**, including login.
   * Set the flag to ``FALSE`` and recreate OMERO.web to disable the application.
     Nginx remains the browser-facing OMERO.web service.

Demo defaults and existing deployments
----------------------------------------------

The supplied ``.env`` and ``.env.shared`` explicitly enable the viewer with
``BIOMERO_ZARR_VIEWER_ENABLED=TRUE``. The web image includes the viewer package
and its compiled frontend, so Node.js and a separate ZarrViewer checkout are
not required to run it.

Using the new demo environment file enables the demo features; preserve your
existing environment file and site credentials during an opt-in upgrade.

Windows and local HTTP demo
-----------------------------------

The default Compose stack uses ``zarrviewer-nginx`` as its single browser-facing
OMERO.web service. OMERO.web's Gunicorn port is internal, preventing navigation
or dashboard links from bypassing the authorized Zarr data route. Start the
demo with the normal command:

.. code-block:: powershell

   docker compose up -d --build

Open http://localhost:4080 and sign in. The proxy forwards ordinary OMERO.web
requests and serves only authorized OME-Zarr metadata and chunks. All browser
requests, including login, dashboard links and viewer navigation, use this same
endpoint. Gunicorn does not process ``X-Accel-Redirect`` and is therefore not
published directly.

For an existing locally built deployment, opt in by adding these settings to
your environment file, preserving any other selected profiles:

.. code-block:: ini

   BIOMERO_ZARR_VIEWER_ENABLED=TRUE
   BIOMERO_WEB_HOST_PORT=4080

Rebuild/recreate only the frontend services:

.. code-block:: powershell

   docker compose build omeroweb
   docker compose up -d --no-deps omeroweb zarrviewer-nginx
   docker compose exec zarrviewer-nginx nginx -t

The feature flag controls application registration; Nginx remains the normal
OMERO.web frontend when the viewer is disabled. To disable the viewer, set the
flag to ``FALSE`` and recreate ``omeroweb``. Restarting a container does not
load changed Compose environment values.

``BIOMERO_WEB_HOST_PORT`` defaults to 4080 when absent, preserving the public
endpoint used by existing root-Compose deployments. There must be only one
browser-facing endpoint, and it must be the Nginx service.

The manual-process ``docker-compose-dev.yml`` also includes the same flag,
build argument and proxy. Its existing manual web-process startup requirement
still applies.

Prebuilt images and other scenarios
-------------------------------------------

The deployment-scenario Compose files forward the feature flag to OMERO.web
with a false fallback. For prebuilt deployments, select a published NL-BIOMERO
image that contains this integration and explicitly enable the flag.

Scenarios exposing OMERO.web directly also require an Nginx frontend when
opting in. Use ``nginx/zarrviewer.conf`` with a read-only mount of the same
in-place storage at ``/data`` and proxy to ``omeroweb:4080`` on the web network.
Compose bind paths are relative to the first Compose file: scenario files
under ``deployment_scenarios`` need ``../nginx/zarrviewer.conf`` and the
appropriate host storage path. The ``.env.shared`` demo enables application
registration; add the frontend to the Compose project hosting OMERO.web,
rather than the database-only shared infrastructure project.

Ubuntu HTTPS scenario
-----------------------------

``deployment_scenarios/docker-compose-for-ubuntu-with-SSL.yml`` uses its
existing Nginx service. It mounts the same ``../web/L-Drive`` store as OMERO.web,
read-only at ``/data``. The supplied ``nginx/nginx.conf`` includes the internal
storage location and a dedicated viewer route with shared proxy caching
disabled. Configure the hostname and certificates as described in
:doc:`linux-deployment`; a second proxy is unnecessary.

For an existing site, explicitly enable ``BIOMERO_ZARR_VIEWER_ENABLED=TRUE``
and add the equivalent read-only mount and Nginx locations from this branch
to your customized configuration. Preserve your site hostname, certificate
paths, credentials and other routing. Validate Nginx and recreate the web
and proxy services using your scenario Compose command.

Never publish the storage as a normal public Nginx directory, and never use a
shared proxy cache for ``/biomero_zarr_viewer/``. Every data request must pass
through OMERO authorization before Nginx serves the file.

Storage paths and supported data
----------------------------------------

OMERO.web and Nginx must see the same physical store with an identical relative
directory tree. The local proxy always mounts it at ``/data``. OMERO.web uses
``IMPORT_MOUNT_PATH`` (normally ``/data``) as its viewer mount root. The source
root defaults to that path and represents the prefix recorded in OMERO by the
importer. If the recorded prefix differs, set it explicitly, for example:

.. code-block:: ini

   IMPORT_MOUNT_PATH=/data
   BIOMERO_ZARR_VIEWER_SOURCE_ROOT=/archive

With these roots, an OMERO link to ``/archive/alice/example.ome.zarr`` must
resolve to ``/data/alice/example.ome.zarr`` in OMERO.web and Nginx. Retain
``/_biomero_zarr_internal/`` as the internal redirect prefix in both services.
Ensure both container users can read the store. The viewer does not modify it.

The selected Image, Plate, or Well must be readable in the active OMERO group.
Images and Plates must link unambiguously to a physical store through their
Fileset/OriginalFile or BIOMERO import provenance map annotation. A Well
resolves through its first readable WellSample Image and opens in the
multi-field Well overview. The viewer supports OME-Zarr 0.4/Zarr v2 and
OME-Zarr 0.5/Zarr v3, including NGFF labels and HCS metadata. It is independent
of the shallow-Zarr and detached-workflow feature flags.

Well and Plate overview thumbnails show intensity channels. Open an individual
Field to display and control its segmentation label overlays.

Compatibility with shallow results
------------------------------------------

The viewer resolves a ``biomero.zarr.shallow`` index against its
authoritative ``.biomero-shallow.json`` manifest. It reads intensity metadata
and chunks from the canonical source store while exposing retained or inherited
label paths from the shallow result store as one logical, authorized store.
Complete image and plate stores continue to use their existing direct route.

Before publishing an NL-BIOMERO image, use the released viewer component and
repeat the shallow-label verification below.

Verification and troubleshooting
----------------------------------------

1. Sign in through the proxy and select an imported OME-Zarr Image, Plate, or
   Well.
2. Choose **Open With > OME-Zarr Viewer**.
3. Confirm channels, Z/T controls, labels and plate fields match the store.
   For a shallow result, confirm the original intensities and split result
   labels render together.
4. In browser network tools, confirm requests under
   ``/biomero_zarr_viewer/data/images/`` return 200 or 206 with non-empty bodies.
5. Confirm a direct request to ``/_biomero_zarr_internal/`` returns 404.
6. Confirm signed-out requests cannot retrieve capability or store data.

A disabled Open With entry means the current selection is not exactly one
eligible Image, Plate, or Well. A viewer that opens but reports **Failed to fetch** usually indicates
a stale direct-Gunicorn bookmark, mismatched storage roots, missing read
permissions or an absent internal Nginx location.
Inspect ``docker compose logs --tail=100 omeroweb zarrviewer-nginx`` for the
local demo, or the existing ``nginx`` service in the SSL scenario.

See the `viewer documentation
<https://nl-bioimaging.github.io/BIOMERO.ZarrViewer/>`_ for focused links,
bounded PNG/gallery export, 3D limits and optional renderer settings.
