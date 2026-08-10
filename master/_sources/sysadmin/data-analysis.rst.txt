Integrated Data Analysis
========================

NL-BIOMERO installs OMERO.Analysis alongside OMERO.biomero. One setting chooses
where users launch it; it does not conditionally install or disable Analysis.

Configuration
-------------

Set the following in ``.env`` or in the environment used by every maintained
Compose scenario:

.. code-block:: text

   OMERO_ANALYSIS_VERSION=0.11.0
   INTEGRATE_DATA_ANALYSIS=TRUE

The Boolean setting is case-insensitive. ``true``, ``True``, ``TRUE``, ``1``,
``yes``, and ``on`` enable integrated mode. A false value or an absent setting
uses standalone mode.

.. list-table:: Navigation behavior
   :header-rows: 1

   * - Setting
     - OMERO top menu
     - BIOMERO
     - Center panel
   * - ``FALSE`` or absent
     - **Analysis** opens a new tab
     - No Data Analysis button
     - Opens standalone Analysis
   * - ``TRUE``
     - Redundant Analysis top link is removed
     - **Data Analysis** appears beside Import and Analyze
     - Opens the selected source in BIOMERO

Rebuild and restart only the web image after changing the package version or
when updating the integration branches:

.. code-block:: bash

   docker compose build omeroweb
   docker compose up -d omeroweb

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

Then sign in and check exactly one launch path:

* integrated mode: BIOMERO shows **Data Analysis** and the Analysis top link is absent;
* standalone mode: the Analysis top link is present and BIOMERO has no Data Analysis button;
* the center panel carries Dataset, Screen, Plate, Image, multi-selection, and
  saved-Workspace context to the selected launch path;
* Analysis can run a Method, use Pyodide, upload and download attachments, and
  retain the OMERO session and active group inside the embedded frame.

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
