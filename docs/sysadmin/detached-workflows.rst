.. _detached-workflows:

Detached BIOMERO Workflows
==========================

.. note::
   **Summary for system administrators:**

   * Enable detached analysis with ``BIOMERO_DETACHED_WORKFLOWS=TRUE``.
   * Detached workflows continue when the submitting OMERO.web session ends.
   * Keep normal OMERO session and script timeouts; they do not need to cover
     the complete Slurm runtime.
   * The setting applies to BIOMERO analysis workflows, not browser uploads.

Overview
--------

BIOMERO analysis may include data transfer, format conversion, Slurm queueing
and execution, and result import. These operations can take considerably longer
than a normal OMERO.web session.

Detached mode hands an accepted analysis request to ``biomeroworker`` for
background execution. Progress and results remain available through BIOMERO
after the submitting browser or OMERO session has ended.

When detached mode is disabled, the workflow runs inline. The OMERO script and
requesting session must then remain available until processing and result
import have completed. Inline deployments may require longer OMERO timeouts for
long-running workflows.

Detached mode covers workflows launched through ``SLURM_Run_Workflow.py`` and
``SLURM_Run_Workflow_Batched.py``. It does not detach an upload that is still
being transferred from a browser.

Configuration
-------------

Set the following value in the NL-BIOMERO ``.env`` file:

.. code-block:: ini

   BIOMERO_DETACHED_WORKFLOWS=TRUE

The supplied Compose files pass this setting to the required services. Set it
to ``FALSE`` only when inline execution is required.

The background worker can be tuned with these optional settings:

.. list-table::
   :header-rows: 1

   * - Variable
     - Default
     - Description
   * - ``BIOMERO_MAX_ACTIVE_WORKFLOWS``
     - ``4``
     - Maximum number of workflows managed concurrently by the worker.
   * - ``BIOMERO_SUPERVISOR_POLL_SECONDS``
     - ``10``
     - Interval between checks for newly submitted workflows.
   * - ``BIOMERO_SUPERVISOR_STARTUP_GRACE_SECONDS``
     - ``60``
     - Delay before a restarted worker resumes unfinished workflows.

Increasing ``BIOMERO_MAX_ACTIVE_WORKFLOWS`` does not increase Slurm capacity.
For example, if two workflows request a GPU and only one GPU is available,
Slurm runs one job while the other remains pending.

Apply a change to the detached-mode setting by recreating the affected
services:

.. code-block:: console

   docker compose up -d --force-recreate biomeroworker omeroweb

Session and timeout settings
----------------------------

Detached workflows are designed to run with ordinary OMERO session settings.
The supplied environment files use the standard timeout values:

.. code-block:: ini

   OMERO_SCRIPTS_TIMEOUT=3600000
   OMERO_SESSIONS_TIMEOUT=600000
   OMERO_WEB_SESSION_COOKIE_AGE=86400

These values correspond to a one-hour OMERO script timeout, a ten-minute OMERO
session idle timeout, and a one-day OMERO.web cookie age. They remain
configurable in ``.env`` according to local security and access policies.

``OMERO_WEB_SESSION_EXPIRE_AT_BROWSER_CLOSE`` controls browser cookie behavior
and may be set independently. Detached analysis does not require this setting
to be disabled.

Normal timeouts must still allow request validation and submission to finish.
They must also be appropriate for individual OMERO-side operations such as data
transfer and result import. They do not need to cover time spent waiting in the
Slurm queue or running the analysis job.

Operational behavior
--------------------

Submitted workflows appear in the BIOMERO workflow overview, where their
progress and final status can be monitored independently of the original web
session.

Workflow state is stored in the BIOMERO tracking database. If
``biomeroworker`` restarts, it resumes unfinished detached workflows and
continues monitoring jobs that have already been submitted to Slurm.

Do not disable detached mode while workflows are queued or running. They remain
recorded but cannot progress until the background worker is available again.

Confirm the active configuration with:

.. code-block:: console

   docker compose exec biomeroworker printenv BIOMERO_DETACHED_WORKFLOWS
   docker compose exec omeroweb printenv BIOMERO_DETACHED_WORKFLOWS

Both services should report the same value.

Troubleshooting
---------------

**A workflow remains queued**
   Confirm that ``biomeroworker`` is running and can access the BIOMERO
   tracking database, OMERO server, shared storage, and Slurm cluster. Review
   the worker logs for connection or permission errors.

**A Slurm job remains pending**
   Inspect the Slurm pending reason. Available partitions, GPUs, memory,
   priorities, and cluster limits determine when a submitted job starts.

**Workflow progress is not updating**
   Confirm that the worker is running and that both the worker and OMERO.web
   connect to the same BIOMERO tracking database.

See also
--------

* :doc:`slurm-integration`
* :doc:`analyzer-importer-admin`
* :doc:`../developer/containers/biomeroworker`
