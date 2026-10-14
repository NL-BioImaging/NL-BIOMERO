Integrated Data Analysis
========================

The web image includes the released Analysis package, but Analysis is disabled
unless explicitly enabled. The supplied NL-BIOMERO demo opts in. Upgrading
OMERO.biomero alone does not install or activate Analysis or its worker.

Configuration
-------------

Set the following in ``.env`` or in the environment used by every maintained
Compose scenario:

.. code-block:: text

   OMERO_BIOMERO_VERSION=1.7.0b7
   OMERO_ANALYSIS_VERSION=1.0.0
   OMERO_DATA_QUERY_WORKER_VERSION=0.2.2
   INTEGRATE_DATA_ANALYSIS=TRUE
   COMPOSE_PROFILES=analysis
   DQW_API_TOKEN=<generate-a-high-entropy-secret>

The Boolean setting is case-insensitive. ``true``, ``True``, ``TRUE``, ``1``,
``yes``, and ``on`` enable integrated mode. A false value or an absent setting
disables the Analysis app, center panel and navigation entries. The local
worker starts only with the ``analysis`` Compose profile. Ordinary disabled
deployments need no worker token. Keep any other selected Compose profiles when
adding ``analysis`` to ``COMPOSE_PROFILES``.

The Dockerfile installs OMERO.biomero, Analysis and WorkflowSkills from PyPI
using exact versions. Analysis 1.0.0 is also available as the identical wheel
on GitHub Releases; there is no deployment-specific downloader or SDK installation.
See the `Analysis release guide
<https://github.com/NL-BioImaging/OMERO.Analysis/blob/main/docs/github-releases.md>`_.
Advance the deployment pin only after the requested release assets exist.

Integrated navigation also requires a compatible installed BIOMERO host view,
template and compiled frontend. An enabled deployment with an incompatible
host fails startup with a clear error instead of silently changing the launch path.

.. list-table:: Navigation behavior
   :header-rows: 1

   * - Setting
     - OMERO top menu
     - BIOMERO
     - Center panel
   * - ``FALSE`` or absent
     - No Analysis link
     - No Data Analysis button
     - No Analysis panel
   * - ``TRUE``
     - Redundant Analysis top link is removed
     - **Data Analysis** appears beside Import and Analyze
     - Opens the selected source in BIOMERO

Rebuild and restart only the web image after changing the package version or
when updating the integration branches:

.. code-block:: bash

   docker compose build omeroweb
   docker compose up -d omeroweb data-query-worker

Source selection and saved Workspaces
-------------------------------------

Data Analysis accepts Datasets, Screens, Plates, one Image, multiple Images,
and multiple Plates. Projects are browsing roots. Multiple selection must use
Images or Plates of one type.

The source selector also exposes the user's managed ``+AnalysisWorkspaces``
Project. Selecting one of its managed Datasets resolves the original source and
the synchronized restore snapshot. Resume is allowed only when the Dataset is
in the current user's current-group managed library and the original source is
still readable. Settings, Skills, result images, mixed selections, corrupt
metadata, and unreadable sources show guidance instead of creating an invalid
Workspace.

Changing or reloading a source warns when Analysis reports unsaved editor
changes. **Open in new tab** launches the same source and saved Workspace using
the standalone route.

Verification
------------

After startup, verify the installed packages and registered URLs:

.. code-block:: bash

   docker compose exec omeroweb /opt/omero/web/venv3/bin/python -c \
     "from importlib.metadata import version; print(version('omero-analysis')); print(version('omero-biomero'))"
   docker compose exec omeroweb /opt/omero/web/venv3/bin/python -c \
     "import django; django.setup(); from django.urls import reverse; print(reverse('omero_analysis_index')); print(reverse('biomero'))"

Then sign in and check the selected feature state:

* integrated mode: BIOMERO shows **Data Analysis** and the Analysis top link is absent;
* disabled mode: the Analysis app, top link, center panel and Data Analysis button are absent;
* the center panel carries Dataset, Screen, Plate, Image, multi-selection, and
  saved-Workspace context to the selected launch path;
* Analysis can run a Method, use Pyodide, upload and download attachments, and
  retain the OMERO session and active group inside the embedded frame.

Remote measurements and image review
------------------------------------

Large DuckDB, SQLite and CSV attachments use the private DataQueryWorker
service. Keep its endpoint and token server-side and verify readiness before
running a notebook. After a reload, the Workspace must retain its remote source
binding without downloading the whole database into the browser.

ZarrViewer review exports require the measured result's store UUID to match its
authenticated capabilities. For shallow segmentation results, canonical source
pixels retain the result's separate identity. Large plates require the viewer's
bounded manifest support as well as adequate request-header limits. This demo
uses ``large_client_header_buffers 4 128k`` in Nginx and
``--limit-request-field_size 131072`` in Gunicorn. Any additional reverse proxy
must accept the same signed context. These limits do not alter authentication,
group checks or the internal-only Zarr route.

Run an unchanged-parameter notebook twice and reload its saved Workspace.
Verify that each PNG has its own SVG/CSV companions, with no redundant plot
attachments on the Dataset. Different parameter/input sets remain separate;
superseded results remain recoverable through Workspace Trash.

Troubleshooting
---------------

**Data Analysis is unavailable**
   The OMERO.biomero page reports an actionable error when the
   ``omero-analysis`` distribution is absent or its Django URL is not
   registered. Rebuild the web image and inspect ``docker compose logs
   omeroweb``.

**The frame is refused**
   Use matching releases. OMERO.Analysis must emit ``frame-ancestors 'self'``
   and ``X-Frame-Options: SAMEORIGIN``. Do not proxy Analysis and BIOMERO through
   different origins.

**A saved Workspace cannot resume**
   Confirm the active OMERO group, read access to the original source, and the
   synchronized restore snapshot in the managed Dataset. An unmarked Project
   merely named ``+AnalysisWorkspaces`` is intentionally never adopted.

**Both or neither navigation entries appear**
   Ensure the same ``INTEGRATE_DATA_ANALYSIS`` value reaches the omeroweb
   container, then restart it so the idempotent startup scripts reconcile the
   exact OMERO.Analysis top-link registration.
