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
   * In the local demo, enable the ``ZARR_VIEWER_ENABLED`` Compose profile and
     access OMERO through port **4081**, including login.
   * Set the flag to ``FALSE`` and recreate OMERO.web to disable the application.
     Existing viewers are preserved; see below for optional proxy removal.

Demo defaults and existing deployments
----------------------------------------------

The supplied ``.env`` and ``.env.shared`` explicitly enable the viewer with
``BIOMERO_ZARR_VIEWER_ENABLED=TRUE``. The web image includes the published
``biomero-zarr-viewer==0.5.0`` wheel, including its compiled frontend; Node.js
and a separate ZarrViewer checkout are not required to run it.

Using the new demo environment file enables the demo features; preserve your
existing environment file and site credentials during an opt-in upgrade.

Windows and local HTTP demo
-----------------------------------

The default Compose stack includes an optional ``zarrviewer-nginx`` service.
The supplied ``.env`` selects its ``ZARR_VIEWER_ENABLED`` profile alongside the
existing importer profile. Start the demo with the normal command:

.. code-block:: powershell

   docker compose up -d --build

Open http://localhost:4081 and sign in. The proxy forwards ordinary OMERO.web
requests and serves only authorized OME-Zarr metadata and chunks. Port 4080
remains the direct OMERO.web endpoint; use port 4081 for the viewer because
Gunicorn does not process ``X-Accel-Redirect``. All browser requests, including
login and viewer navigation, must use the same proxy endpoint.

For an existing locally built deployment, opt in by adding these settings to
your environment file, preserving any other selected profiles:

.. code-block:: ini

   BIOMERO_ZARR_VIEWER_ENABLED=TRUE
   BIOMERO_ZARR_VIEWER_VERSION=0.5.0
   BIOMERO_ZARR_VIEWER_PROXY_PORT=4081
   COMPOSE_PROFILES=IMPORTER_ENABLED,ZARR_VIEWER_ENABLED

Rebuild/recreate only the frontend services:

.. code-block:: powershell

   docker compose build omeroweb
   docker compose up -d --no-deps omeroweb zarrviewer-nginx
   docker compose exec zarrviewer-nginx nginx -t

The proxy profile controls whether Compose starts the optional proxy. The
feature flag controls application registration; enabling the flag alone does
not start the proxy. To disable the local demo viewer, set the flag to ``FALSE``,
remove ``ZARR_VIEWER_ENABLED`` from ``COMPOSE_PROFILES``, recreate ``omeroweb``,
and stop/remove only ``zarrviewer-nginx``. Restarting a container does not load
changed Compose environment values.

The manual-process ``docker-compose-dev.yml`` also includes the same flag,
build argument and proxy. Its existing manual web-process startup requirement
still applies.

Prebuilt images and other scenarios
-------------------------------------------

The deployment-scenario Compose files forward the feature flag to OMERO.web
with a false fallback. For prebuilt deployments, select a published NL-BIOMERO
image that contains this integration and explicitly enable the flag. The
beta.6 web image does not contain the viewer; this PR is preparation for beta.7.
Do not select a beta.7 image until its release image build has completed.

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

The selected Image or Plate must be readable in the active OMERO group and
linked unambiguously to a physical store through its Fileset/OriginalFile
or the BIOMERO import provenance map annotation. The viewer supports OME-Zarr
0.4/Zarr v2 and OME-Zarr 0.5/Zarr v3, including NGFF labels and HCS metadata.
It is independent of the shallow-Zarr and detached-workflow feature flags.

Compatibility with shallow results
------------------------------------------

This initial integration pins viewer 0.5.0, which expects a complete physical
NGFF store. BIOMERO shallow results omit duplicate intensity arrays and retain
labels in a separate result store. Such results are not yet directly supported
by this viewer version and can return ``invalid_ome_zarr_metadata``.

The beta.7 compatibility work must validate the ``biomero.zarr.shallow`` index
against its authoritative ``.biomero-shallow.json`` manifest, then display
canonical source intensities with the retained or inherited label layers.
That work is separate from enabling the viewer in the deployment. Before
releasing the complete beta.7 feature, update the package pin to a published
viewer version that supports this split-store contract and verify a real
remote-shallowed result. Complete image and plate stores remain supported.

Verification and troubleshooting
----------------------------------------

1. Sign in through the proxy and select an imported OME-Zarr Image or Plate.
2. Choose **Open With > OME-Zarr Viewer**.
3. Confirm channels, Z/T controls, labels and plate fields match the store.
4. In browser network tools, confirm requests under
   ``/biomero_zarr_viewer/data/images/`` return 200 or 206 with non-empty bodies.
5. Confirm a direct request to ``/_biomero_zarr_internal/`` returns 404.
6. Confirm signed-out requests cannot retrieve capability or store data.

A disabled Open With entry usually means the selected object is unsupported,
unreadable or has an ambiguous store link. A viewer that opens but reports
**Failed to fetch** usually indicates direct access to port 4080, mismatched
storage roots, missing read permissions or an absent internal Nginx location.
Inspect ``docker compose logs --tail=100 omeroweb zarrviewer-nginx`` for the
local demo, or the existing ``nginx`` service in the SSL scenario.

See the `viewer documentation
<https://github.com/NL-BioImaging/BIOMERO.ZarrViewer#readme>`_ for focused links,
bounded PNG/gallery export, 3D limits and optional renderer settings.
