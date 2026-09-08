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
creates a *launcher task*. Its parameters contain the validated script inputs,
derived pipeline values, and the ``_biomero_detached_launcher`` marker. The
script then returns instead of executing the pipeline itself.

The custom ``processor.py`` starts a ``WorkflowSupervisor`` alongside the
normal OMERO script processor. The supervisor:

1. reads unfinished workflows from ``WorkflowProgressView``;
2. identifies detached requests by loading their launcher task;
3. starts one ``WorkflowWorker`` thread per eligible workflow; and
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

Before executing a workflow, the worker updates the launcher task to
``CLAIMED``. This is internal supervisor bookkeeping. It records that a
processor started handling the request and allows a replacement process to
recognize an interrupted run. It is not an analysis phase and must not be
presented as workflow progress.

``CLAIMED`` is intentionally resumable: after a worker or container restart,
the new supervisor may claim the same launcher again and reconstruct the
pipeline from the event-sourced workflow and task aggregates. With
``resume=True``, completed transfer and conversion stages are skipped and an
existing Slurm job is adopted instead of submitted again.

The in-memory ``active_workers`` map prevents duplicate workers within one
processor process. The claim does **not** currently contain an owner, lease, or
atomic cross-process lock. Consequently, the supported topology is exactly one
active detached supervisor for each BIOMERO tracking database. Do not run
multiple ``biomeroworker`` replicas or assign additional ``Processor-N`` nodes
with detached mode enabled against the same tracking database.

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

Diagnostics
-----------

The detached implementation uses these logger names:

* ``biomero.detached.supervisor`` for discovery and worker management;
* ``biomero.detached.<workflow UUID>`` for an individual workflow; and
* ``biomero.detached.script`` for OMERO sub-script execution.

Use the event store and aggregate repository to distinguish durable workflow
state from a projection or metadata problem. In particular, a launcher task at
``CLAIMED`` means that the supervisor has handled it; the subsequent pipeline
task events determine the analysis phase and outcome.

See also
--------

* :doc:`containers/biomeroworker`
* :doc:`../sysadmin/detached-workflows`
* `BIOMERO event-sourcing documentation <https://nl-bioimaging.github.io/biomero/eventsourcing.html>`_
