.. _detached-workflows:

Detached BIOMERO Workflows
==========================

.. versionadded:: 1.8.0

   Detached workflow execution is controlled by an opt-in feature flag. The fresh NL-BIOMERO
   demo configuration enables it, but existing and custom deployments continue
   to use inline execution until ``BIOMERO_DETACHED_WORKFLOWS`` is explicitly
   enabled.

.. note::
   **Summary for system administrators:**

   * Enable detached analysis with ``BIOMERO_DETACHED_WORKFLOWS=TRUE``.
   * Detached workflows continue when the submitting OMERO.web session ends.
   * When detached mode is enabled, the user's OMERO session does not need to
     cover the complete Slurm runtime. The OMERO script timeout must still
     accommodate long server-side transfer and import operations.
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

The supplied Compose files pass this feature flag to the required services. If
the flag is absent or ``FALSE``, workflows use inline execution.

.. important::
   Update ``biomeroworker`` to the corresponding NL-BIOMERO release before
   enabling detached workflows.

   Detached mode currently supports one active ``biomeroworker`` per BIOMERO
   tracking database. Multiple worker replicas are not supported.

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

Detached workflows are designed to run with ordinary user-session settings.
The supplied environment files keep user sessions short while allowing
server-side scripts to complete long transfer and import operations:

.. code-block:: ini

   OMERO_SCRIPTS_TIMEOUT=604800000
   OMERO_SESSIONS_TIMEOUT=600000
   OMERO_WEB_SESSION_COOKIE_AGE=86400

These values correspond to a seven-day OMERO script timeout, a ten-minute OMERO
session idle timeout, and a one-day OMERO.web cookie age. The long script
timeout accommodates operations such as importer polling, which may continue
for several hours. It does not extend the submitting user's session. These
values remain configurable in ``.env`` according to local security and access
policies.

.. important::
   The short session timeout is suitable for long workflows only when detached
   mode is enabled. In inline mode, the requesting session and top-level script
   remain involved until result import completes; long workflows may therefore
   require a longer session timeout as well.

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
* :doc:`../developer/detached-workflow-supervisor`
