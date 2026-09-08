.. _detached-workflows:

Detached BIOMERO Workflows
==========================

Detached mode lets an analysis continue after the OMERO.web request and the
user's browser session have ended. It is intended for workflows whose data
transfer, Slurm execution, result import, or batching can take longer than a
normal web session.

This mode applies to BIOMERO analysis workflows launched through
``SLURM_Run_Workflow.py`` and ``SLURM_Run_Workflow_Batched.py``. It does not
detach a browser upload or every operation in the Import interface.

Inline and detached execution
-----------------------------

In inline mode, the OMERO script drives the complete pipeline. The script and
its requesting OMERO session therefore need to remain available until results
have been imported.

In detached mode:

1. The OMERO script validates the request and creates a tracked workflow.
2. It records the complete request in a launcher task and returns immediately.
3. The ``WorkflowSupervisor`` in ``biomeroworker`` claims the launcher.
4. A background worker reconnects as the requesting user and group and drives
   the same transfer, conversion, Slurm, import, and postprocessing pipeline.
5. Progress and the final result remain available in the BIOMERO workflow
   overview after the user logs in again.

The OMERO.web Activities entry represents the short queueing script. The
BIOMERO workflow overview represents the longer detached execution.

The submission confirmation reflects the effective mode:

* **Detached:** the workflow runs in the background; the user may close the
  tab or log out.
* **Inline:** the user is warned to keep the browser and OMERO session active.

Requirements
------------

Use mutually compatible releases of ``biomero``, ``biomero-scripts``,
``OMERO.biomero``, and NL-BIOMERO. A partial upgrade is not sufficient:

* ``biomero-scripts`` creates the detached launcher task.
* ``biomero`` defines the launcher and resume contract.
* the NL-BIOMERO ``biomeroworker`` processor runs the supervisor.
* ``OMERO.biomero`` reports the execution mode and displays the correct
  session guidance.

The worker and scripts must share the BIOMERO workflow-tracking database. The
worker also needs its normal OMERO service credentials so it can reconnect and
sudo into the requesting user's account and group.

Enable detached mode
--------------------

Set the following in the NL-BIOMERO ``.env`` file:

.. code-block:: text

   BIOMERO_DETACHED_WORKFLOWS=TRUE

The same value must reach both services:

* ``biomeroworker`` uses it to enable the supervisor and forwards it to the
  workflow script subprocess.
* ``omeroweb`` uses it to return the effective execution mode to the web UI.
  It does not run or supervise the workflow.

The shipped Compose files forward the same ``.env`` value to both containers.
For a custom deployment, add it to both services explicitly. A mismatch can
make the UI give incorrect session advice even if the worker itself behaves
correctly.

The remaining settings are optional tuning controls:

.. list-table::
   :header-rows: 1

   * - Variable
     - Default
     - Purpose
   * - ``BIOMERO_MAX_ACTIVE_WORKFLOWS``
     - ``4``
     - Maximum detached child or non-batched workflows driven concurrently.
       A batched parent does not occupy a slot while it waits for its children.
   * - ``BIOMERO_SUPERVISOR_POLL_SECONDS``
     - ``10``
     - Interval between checks for newly queued workflows.
   * - ``BIOMERO_SUPERVISOR_STARTUP_GRACE_SECONDS``
     - ``60``
     - Delay before a newly started processor adopts queued or interrupted
       work.

These three tuning settings are needed only by ``biomeroworker``. Increasing
``BIOMERO_MAX_ACTIVE_WORKFLOWS`` permits more submissions and pipeline work; it
does not create Slurm capacity. For example, two workflows requesting a GPU on
a one-GPU cluster result in one running job and one normally ``PENDING`` job.

After changing only environment values, recreate the affected containers:

.. code-block:: console

   docker compose up -d --force-recreate biomeroworker omeroweb

When enabling the feature as part of a software upgrade, pull or rebuild the
compatible images before recreating them.

Verify that both services received the switch:

.. code-block:: console

   docker compose exec biomeroworker printenv BIOMERO_DETACHED_WORKFLOWS
   docker compose exec omeroweb printenv BIOMERO_DETACHED_WORKFLOWS

Both commands should print ``TRUE`` (case-insensitive boolean forms are also
accepted).

What you no longer need
-----------------------

Detached analysis should be used with ordinary, security-conscious OMERO
session settings. You do **not** need to:

* configure infinite OMERO server sessions;
* set an extremely large OMERO.web cookie age;
* keep ``expire-at-browser-close`` disabled solely for BIOMERO analysis;
* keep a browser tab open or keep the Activities poller running; or
* increase the OMERO script timeout to cover the complete Slurm runtime.

Normal timeouts must still allow the initial validation and queue hand-off to
finish. Other operations, especially an upload that is still transferring data
from the browser, retain their own session and timeout requirements. Detached
mode also does not override a Slurm wall-time limit, importer timeout, storage
failure, or unavailable external service.

The supplied environment files use OMERO's ordinary timeout values rather than
the previous seven-day overrides::

   OMERO_SCRIPTS_TIMEOUT=3600000
   OMERO_SESSIONS_TIMEOUT=600000
   OMERO_WEB_SESSION_COOKIE_AGE=86400

For the detached-workflow session-expiry test, they keep
``OMERO_WEB_SESSION_EXPIRE_AT_BROWSER_CLOSE=false``. Closing the browser then
leaves the web cookie in place while the underlying OMERO session reaches its
10-minute idle timeout. The one-day cookie does not extend that server session.
Deployments that prefer browser-length cookies can set this value to ``true``;
detached workflows do not depend on either choice.

Recovery behavior
-----------------

Launcher claims and workflow progress are persisted in the tracking database.
After a ``biomeroworker`` crash or restart, the supervisor adopts unfinished
detached workflows. The pipeline can reuse a completed transfer or conversion
and resume monitoring an already-submitted Slurm job instead of submitting it
again.

Do not disable the supervisor while detached workflows are still queued. They
remain recorded but cannot progress until a compatible supervisor is running.

Testing session independence
----------------------------

Test this behavior in a non-production environment with a workflow that lasts
longer than the configured web session:

1. Submit the workflow and wait for the detached confirmation.
2. Record its Workflow UUID from **Analyze > Status**.
3. Log out or close the browser tab.
4. Wait beyond the normal web-session lifetime.
5. Log in again and confirm that the same workflow reached ``DONE`` and its
   results were imported.

A purpose-built validation workflow that waits on a compute node and then
writes a small valid result is usually safer and cheaper than deliberately
inflating a production analysis. Test restart recovery separately by restarting
``biomeroworker`` after the Slurm job has been submitted and checking that the
same job is adopted.

Troubleshooting
---------------

**The UI still says not to log out**
   Check the value in both containers and recreate ``omeroweb``. An old
   OMERO.biomero package or generated frontend bundle may also lack the
   mode-aware confirmation.

**The workflow is queued but never starts**
   Confirm that ``biomeroworker`` has detached mode enabled, its supervisor has
   started, and it can access the tracking database and OMERO server. Also
   confirm that all detached-feature components are from compatible releases.

**A Slurm job remains pending**
   Inspect the Slurm pending reason. Detached concurrency controls how many
   workflows BIOMERO can drive, while partitions, GPUs, memory, priorities, and
   limits still control when Slurm starts a job.

See also
--------

* :doc:`slurm-integration`
* :doc:`analyzer-importer-admin`
* :doc:`../developer/containers/biomeroworker`
