BIOMERO.analyzer + BIOMERO.importer Integration
================================================

.. note::
   **TL;DR for System Administrators:**

   - Enable with ``IMPORTER_ENABLED=true`` in ``.env`` / in the `biomeroworker` environment
   - Analysis results are written to the shared remote storage (the same drive BIOMERO.importer monitors)
   - `biomeroworker` needs **two extra volume mounts** and **two extra env vars** — see :ref:`required-config`
   - The `biomeroworker` needs **write permission** on group folders in the mounted storage
   - From BIOMERO v2.3.0 / NL-BIOMERO v1.3.0 onward

This guide covers connecting BIOMERO.analyzer's SLURM result import to BIOMERO.importer so that
analysis results land on your managed **remote storage** rather than on OMERO server storage.

For full technical detail see :doc:`../developer/containers/analyzer-importer-integration`.

Overview
--------

Without this integration, results produced by analysis workflows (e.g., segmentation masks) are
transferred back to OMERO via the standard OMERO API and end up on the OMERO server volume.

With this integration enabled:

1. The biomeroworker copies results to the **shared remote storage** in a dedicated
   ``.analyzed/<workflow-uuid>/<timestamp>/`` folder.
2. It creates an **upload order** in the BIOMERO.importer tracking database.
3. BIOMERO.importer picks up the order and performs an **in-place import** — the same pipeline
   used for incoming research data.
4. The biomeroworker polls for completion and adds provenance metadata to the imported images.

This keeps analysis results under the same storage and permission model as raw data, avoids
bloat on OMERO server storage, and provides a consistent in-place import experience.

.. _required-config:

Required configuration changes
--------------------------------

``.env``
~~~~~~~~~

.. code-block:: ini

   IMPORTER_ENABLED=true
   BIOMERO_IMPORTER_VERSION=1.2.1   # ensure this matches the installed library version

``docker-compose.yml`` — biomeroworker service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the following to the ``biomeroworker`` service:

**Build args** (so the Python library is installed in the container):

.. code-block:: yaml

   build:
     args:
       BIOMERO_IMPORTER_VERSION: ${BIOMERO_IMPORTER_VERSION}

**Environment variables**:

.. code-block:: yaml

   environment:
     IMPORTER_ENABLED: ${IMPORTER_ENABLED}
     INGEST_TRACKING_DB_URL: postgresql+psycopg2://${BIOMERO_POSTGRES_USER}:${BIOMERO_POSTGRES_PASSWORD}@database-biomero:5432/${BIOMERO_POSTGRES_DB}

.. note::
   ``INGEST_TRACKING_DB_URL`` must point to the **same** database used by the
   ``biomero-importer`` service so that upload orders are visible to the importer.

**Volume mounts**:

.. code-block:: yaml

   volumes:
     - "./config/biomero-importer:/opt/omero/server/config-importer:ro"
     - "./web/biomero-config.json:/opt/omero/server/biomero-config.json:ro"

* ``config/biomero-importer`` — directory containing ``settings.yml`` for BIOMERO.importer.
  The worker reads ``base_dir`` from this file to determine where to write result files.
* ``web/biomero-config.json`` — used by OMERO.biomero to define per-group folder mappings.
  The worker uses these to resolve the correct destination path for each OMERO group.

Storage and file-system setup
-------------------------------

Shared mount
~~~~~~~~~~~~~

The three containers below must all mount the same storage at the **same container path**:

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - Container
     - Purpose
     - Mount
   * - ``biomeroworker``
     - Writes ``.analyzed/`` directory tree
     - ``./web/L-Drive:/data``
   * - ``biomero-importer``
     - Reads files for in-place import and writes ``.processed/`` directory
     - ``./web/L-Drive:/data``
   * - ``omeroserver``
     - Resolves symlinks after in-place import
     - ``./web/L-Drive:/data``

Result folder structure
~~~~~~~~~~~~~~~~~~~~~~~

Results are placed under the OMERO group's subfolder on the shared drive:

.. code-block:: text

   <group_base_path>/
   └── .analyzed/
       └── <workflow-uuid>/
           └── <YYYYMMDD_HHMMSS>/
               ├── <job_id>_out.zip          # results archive
               ├── <job_id>_out/             # extracted images + CSVs
               │   ├── data/out/
               │   │   └── result.tiff
               │   └── metadata.csv          # workflow provenance
               └── omero-<job_id>.log        # SLURM job log

Group path resolution
~~~~~~~~~~~~~~~~~~~~~

The ``<group_base_path>`` is resolved in order:

1. **Explicit mapping** in ``biomero-config.json``: if the user's OMERO group has a folder
   mapping configured in the OMERO.biomero UI, that folder is used.
2. **Fallback**: ``<base_dir>/<group_name>`` from ``settings.yml``.
   Example: group ``team-a`` with no mapping and ``base_dir=/data`` → ``/data/team-a/``.

The group is the **active OMERO group of the user who launched the analysis workflow**.

Permissions
~~~~~~~~~~~

The biomeroworker process (runs as the ``omero-server`` user and group, uid=1000 gid=994, by default) needs:

* **Write permission** on the group's base path.
* Permission to **create the group subfolder** if it does not exist yet (first workflow run for
  that group when no explicit mapping is configured).

Verify in the container:

.. code-block:: bash

   # Check ownership of the data root
   ls -la /path/to/L-Drive/
   touch /path/to/L-Drive/test_write && echo "Write OK" || echo "Write failed"

   # If needed, grant write access to UID 1000 and GID 994 or map containers to a different user with appropriate permissions.

Non-Docker deployments
-----------------------

If you are not using the NL-BIOMERO Docker Compose stack:

1. Install the ``biomero-importer`` Python library in the worker's virtual environment:

   .. code-block:: bash

       pip install biomero-importer==<version>

.. note::

    You can ignore Python requirement and Zarr version warnings. Those checks apply
    only to preprocessing or custom pipelines, which are not used in this setup.

2. Set environment variables before starting the OMERO processor:

   .. code-block:: bash

       export IMPORTER_ENABLED=true
       export INGEST_TRACKING_DB_URL=postgresql+psycopg2://user:pass@db:5432/biomero

3. Place configuration files at:

   * ``/opt/omero/server/config-importer/settings.yml``
   * ``/opt/omero/server/biomero-config.json``

4. Ensure the biomeroworker process has write access to the group folders in shared storage.
   See `BIOMERO.analyzer SLURM Integration <slurm-integration.html>`_ for the baseline worker
   deployment prerequisites.

Validating the setup
---------------------

After rebuilding and restarting the biomeroworker container, verify the library is available:

.. code-block:: bash

   docker-compose exec biomeroworker \
       /opt/omero/server/venv3/bin/python -c \
       "import biomero_importer; print('biomero-importer OK')"

Run a test analysis workflow. Afterwards check:

* A ``.analyzed/<uuid>/<timestamp>/`` directory appears on the shared drive.
* The upload order appears in the importer tracking database:

  .. code-block:: sql

     SELECT uuid, stage, created_at FROM imports ORDER BY created_at DESC LIMIT 5;

* Both the importer and the analyzer tabs from metabase show successful operations.
* You can find the imported images in OMERO.web using either UUID from the importer or analyzer.
* The imported images have Fileset Info in OMERO with info about `Imported with: --transfer=ln_s` `Imported from:`` and `Paths on server:`.

Troubleshooting
---------------

``biomero-importer`` not found
  Rebuild the biomeroworker image — the library is installed at build time.
  Confirm the ``BIOMERO_IMPORTER_VERSION`` build arg is present in the Compose file.

Upload order created but import never runs
  Confirm the ``INGEST_TRACKING_DB_URL`` on both biomeroworker and biomero-importer services
  point to the **same** PostgreSQL database.

Results still appear on OMERO server storage
  Confirm ``IMPORTER_ENABLED=true`` is set on the **biomeroworker** (not just omeroweb or
  biomero-importer).

``PermissionError`` writing to ``.analyzed``
  The ``omero-server`` user (UID 1000) lacks write access.  See `Permissions`_ above.

OMERO images not created after import succeeds
  The shared storage must be mounted at the **same path** in all three containers.  Check that
  the paths in docker-compose are consistent.

Related documentation
---------------------

* `BIOMERO.analyzer SLURM Integration <slurm-integration.html>`_ — baseline SLURM setup
* :doc:`../developer/containers/analyzer-importer-integration` — technical deep-dive
* :doc:`../developer/containers/biomero-importer` — BIOMERO.importer container reference
* :doc:`../developer/containers/biomeroworker` — biomeroworker container reference
