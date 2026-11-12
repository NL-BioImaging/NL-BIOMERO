.. _detached-workflow-supervisor:

Detached Workflow Supervisor
============================

Detached workflow execution is split between the BIOMERO workflow scripts and
the custom OMERO ``processor.py`` supplied by NL-BIOMERO. This page describes
the processor-side implementation and its operational constraints. For
enablement and timeout settings, see
:doc:`../sysadmin/detached-workflows`.

Components and responsibilities
-------------------------------

The workflow scripts remain responsible for validating a request and creating
the event-sourced workflow aggregate. With detached mode enabled, a script also
creates a *launcher task* (``WorkflowTracker.add_launcher_task``). Its
parameters contain the validated script inputs, derived pipeline values, and the
``_biomero_detached_launcher`` marker. The script then returns instead of
executing the pipeline itself. The scripts also decide how an interrupted run
resumes; core only provides the mechanisms (marker, claim, cancel request).

The custom ``processor.py`` starts a ``WorkflowSupervisor`` alongside the
normal OMERO script processor. The supervisor:

1. reads unfinished workflows from ``WorkflowProgressView``;
2. identifies detached requests by loading their launcher task
   (``WorkflowTracker.find_launcher_task``);
3. claims the launcher task and starts one ``WorkflowWorker`` thread per
   claimed workflow; and
4. calls the same ``execute_workflow_pipeline(..., resume=True)`` entry point
   that is used for inline execution.

``RecordedInputsClient`` supplies the persisted launcher parameters through
the client interface expected by the workflow scripts. OMERO sub-scripts are
started through ``polling_script_runner`` because the original top-level OMERO
script session no longer exists.

Worker identity and OMERO access
--------------------------------

The background worker opens an OMERO connection with the processor service
account and switches to the submitting workflow's user and group. This keeps
the ownership and permissions of imported results consistent with inline
execution.

The processor service account must therefore be permitted to act as other
users. This is already required by the standard NL-BIOMERO biomeroworker
deployment.

Discovery and concurrency
-------------------------

The supervisor polls for work every
``BIOMERO_SUPERVISOR_POLL_SECONDS`` seconds. It starts at most
``BIOMERO_MAX_ACTIVE_WORKFLOWS`` ordinary workflow workers at once. This is a
processor-side limit; Slurm resource and queue limits still apply separately.

A batched request creates one detached child workflow per batch. The parent
worker only follows its children and therefore does not occupy a concurrency
slot. Counting it would allow parent workers to consume every slot and prevent
their children from starting.

A workflow is created immediately before its launcher task is recorded. To
avoid misclassifying work during that interval, the supervisor continues to
inspect a workflow without a launcher for five minutes. Older workflows
without a launcher are treated as inline or unrelated work and temporarily
cached as ignored. The cache is cleared periodically so a transient read error
does not exclude a workflow until the next container restart.

Claim and recovery semantics
----------------------------

Before it starts a worker, the supervisor claims the launcher task with
``WorkflowTracker.claim_launcher_task``. The claim is an event on the launcher
task that records the supervisor's name and the time. It is a compare-and-set
in the event store: when two supervisors try to claim the same launcher, one
wins and the other does not run the workflow. A claim does not change the task
status, so it is not an analysis phase and does not appear as workflow progress.

A claim is valid for a lease (``LAUNCHER_CLAIM_LEASE_SECONDS``, five minutes).
The supervisor renews the claim of each running workflow every
``CLAIM_RENEW_SECONDS``, and gives the claims up on a clean shutdown. After a
crash or restart the lease runs out and the new supervisor claims the launcher
and resumes the run: with ``resume=True``, completed transfer and conversion
stages are skipped and an existing Slurm job is adopted instead of submitted
again, while a job that FAILED, was CANCELLED or timed out is submitted anew.
A resume that cannot read the task history fails instead of starting over. A
worker that ends without its workflow reaching a final state is run again after
``WORKER_RESTART_DELAY_SECONDS``.

Launchers claimed by a 2.9 beta carry the status ``CLAIMED`` and no owner; they
are free to claim. A worker that stops because it lost its claim, or because
its supervisor released it, raises ``ClaimLost`` (a ``WorkflowInterrupted``):
the pipeline's stage handlers let it pass without failing any task, and a
batched parent also stops before it writes any child or parent state.

When a renewal finds the claim in another supervisor's hands, the supervisor logs
an error and the worker stops at its next check (between pipeline steps, or by
cancelling the running sub-script) without failing the workflow. Run a single detached supervisor
per BIOMERO tracking database anyway: the claim keeps two of them from running
the same workflow, but metadata maintenance requests below are not claimed.

Cancellation
------------

``WorkflowTracker.request_workflow_cancel(workflow_id, reason)`` records that a
workflow must stop. The worker needs no signal: the workflow pipeline checks the
request between its steps and between Slurm polls, cancels the Slurm jobs it
submitted (``SlurmClient.cancel_slurm_jobs``), closes their tasks and marks the
workflow failed with the reason. While an OMERO sub-script (such as the data
export) runs, ``polling_script_runner`` checks every ``CANCEL_CHECK_SECONDS`` and
cancels the sub-script's OMERO process. A batched parent passes the request on
to each unfinished child and fails once they ended. A cancelled workflow
appears as ``FAILED`` in the workflow overview, with the reason as its message.
The BIOMERO script **Cancel BIOMERO Workflow** (``admin/SLURM_Cancel_Workflow.py``)
sends the request for a workflow ID; it is allowed for the workflow's owner and
for administrators and logs who asked. An OMERO.biomero button can call the same
tracker method later.

Startup, shutdown, and failures
-------------------------------

After processor startup, the supervisor waits
``BIOMERO_SUPERVISOR_STARTUP_GRACE_SECONDS`` seconds before recovery. This
allows ``Processor-0`` to register with OMERO.grid before recovered pipelines
start OMERO sub-scripts. A sub-script that receives
``NoProcessorAvailable`` during startup is retried for up to three minutes.

Supervisor and workflow workers are daemon threads. If the processor process
ends, unfinished state remains in the event store; the next supervisor resumes
it after its startup grace period. Pipeline failures are recorded through the
same workflow tracker used by inline execution.

For a batched request, the parent periodically reads the child workflow
projections. It completes when every child reaches a terminal state, and it
adopts already-created children after a restart rather than creating duplicate
batches.

Deployment compatibility
------------------------

The supervisor is an NL-BIOMERO extension to OMERO's ``processor.py``; it is
not provided by the stock OMERO processor. A detached deployment must use the
matching NL-BIOMERO ``biomeroworker`` image and compatible BIOMERO workflow
scripts and library. Updating only the feature flag, or restarting an older
worker image, does not install the supervisor.

The node descriptors must route the OMERO processor role to that container,
for example:

.. code-block:: yaml

   CONFIG_omero_server_nodedescriptors: >-
     master:Blitz-0
     omeroworker-1:Tables-0,Indexer-0,PixelData-0,DropBox,MonitorServer,FileServer,Storm
     biomeroworker:Processor-0

When upgrading the implementation, pull or rebuild and recreate
``biomeroworker``. Because the file replaces the upstream OMERO implementation,
changes to ``ome/omero-py`` must also be reviewed and merged into the custom
copy when the base image is upgraded.

Metadata maintenance
--------------------

Slurm Init queues metadata **apply** requests when detached mode is enabled.
Dry runs remain inline so their field diffs are available in the activity log.
Slurm setup and analytics rebuilding are not detached by this handoff.

``biomero.maintenance.MetadataRefresh`` is a separate aggregate in the
``WorkflowTracker`` event store, not an analysis workflow or launcher task.
It records the requesting administrator and group, selected workflow UUIDs,
view version, worker count and backup options. No original session credentials
are recorded. Its lifecycle is ``QUEUED`` → ``RUNNING`` → ``DONE`` or ``FAILED``;
progress events contain compact counters, not full metadata maps.

The supervisor reads only maintenance notification topics, maintaining a global
notification cursor. One maintenance thread runs at a time, independently of
the analysis concurrency limit. It loads the fixed Slurm Init adapter, creates
an independent session as the requester and rechecks administrator privileges.
Parallel lanes join that owned session using the existing keepalive and cleanup
helpers. The request ID, progress, skips, failures and final counts are logged
to the existing ``biomero.log``.

Slurm Check Setup reads these aggregates directly to show all active requests
and five recent terminal requests, including counters and errors. Its
``Check Slurm`` option can be disabled for a tracking-database-only query.

After interruption, ``QUEUED`` and ``RUNNING`` requests are retried from discovery.
Already refreshed annotations are unchanged on reapplication; this is an
idempotent sweep, not a per-target checkpoint. Recovery uses a new backup
directory rather than overwriting snapshots from an interrupted attempt.
Completed and failed requests are not retried automatically. Target failures
make the request ``FAILED``; safe skips are counted separately. The same
single-supervisor topology restriction applies to maintenance.

Inspect a request independently of analysis views:

.. code-block:: python

   from uuid import UUID
   request = tracker.repository.get(UUID(request_id))
   print(request.status, request.report, request.error)

Diagnostics
-----------

The detached implementation uses these logger names:

* ``biomero.detached.supervisor`` for discovery and worker management;
* ``biomero.detached.<workflow UUID>`` for an individual workflow; and
* ``biomero.detached.script`` for OMERO sub-script execution.

Metadata requests use ``biomero.detached.maintenance.<request UUID>``.

Use the event store and aggregate repository to distinguish durable workflow
state from a projection or metadata problem. In particular, a launcher task with
a ``claimed_by`` owner and a recent ``claimed_at`` is held by that supervisor
(``LauncherClaimed`` events show each renewal); the subsequent pipeline task
events determine the analysis phase and outcome.

See also
--------

* :doc:`containers/biomeroworker`
* :doc:`../sysadmin/detached-workflows`
* `BIOMERO event-sourcing documentation <https://nl-bioimaging.github.io/biomero/eventsourcing.html>`_
