Optional remote Zarr shallowing
==============================

BIOMERO can shallow eligible workflow OME-Zarr output on Slurm before ZIP
creation and transfer. The helper retains new/changed labels and references
verified canonical pixels already available on the OMERO side. The importer
validates the helper receipt and registers the result without repeating pixel
hashing or shallowing. Other workflow files follow the existing import path.

The NL-BIOMERO demo enables shallow Zarr. Other deployments opt in with
``BIOMERO_SHALLOW_ZARR=true``. Remote processing is then the default; set
``BIOMERO_REMOTE_SHALLOW_ZARR=false`` for local importer processing instead.
Without shallow Zarr enabled, the remote setting has no effect.

Lifecycle overview
------------------

Only derived workflow results are shallowed. The managed source remains
unchanged and must remain available. This diagram shows the Zarr workflow path;
non-Zarr results continue through their usual import path.

.. mermaid::

   flowchart TD
       A["Existing managed Zarr"] --> C["Full source Zarr<br/>Retained unchanged"]
       B["Non-Zarr input"] -->|"Create reusable Zarr"| C
       C --> I["Record or reuse source<br/>ISCC-BIO pixel identities"]
       I --> T["Transfer full Zarr to HPC"]
       T --> H["Workflow produces images and labels"]
       H --> Q{"Where is eligibility checked?"}
       Q -->|"Remote"| R["On HPC, before ZIP and transfer"]
       Q -->|"Local"| L["In importer, after full transfer"]
       R --> V{"Pixels match source<br/>and result is eligible?"}
       L --> V
       I -. "Recorded identities" .-> V
       V -->|"Changed or uncertain"| F["Keep full result"]
       V -->|"Verified unchanged"| S["Shallow result<br/>Remove duplicate result arrays<br/>Keep new labels and managed references"]
       F --> O["Register results in OMERO"]
       S --> O
       C -. "PixelBuffer reads source pixels" .-> O
       S -. "Label views read retained labels" .-> O
       S --> M["Reconstruct on demand"]
       C --> M
       M --> Z["Full, self-contained OME-Zarr<br/>Source pixels and result labels"]
       Z -->|"Next Zarr workflow"| T

In remote mode, transfer follows the eligibility decision: eligible results
travel shallow; other results travel in full. New or changed labels are retained;
unchanged inherited labels may also be referenced instead of duplicated.

A shallow result is a BIOMERO-managed representation, not a self-contained
OME-Zarr for generic readers. OMERO's registered pixel paths reference the
managed source or retained labels; OMERO does not invent missing pixels.
Image Transfer reconstructs a full Zarr for subsequent Zarr workflows.
For a standalone copy on disk, see
:ref:`reconstruct-shallow-zarr-on-disk`.

Choosing local or remote shallowing
----------------------------------

.. list-table:: Illustrative storage and processing trade-offs
   :header-rows: 1
   :widths: 20 30 50

   * - Mode
     - Result disk space
     - Time and compute cost
   * - Full results
     - No deduplication savings
     - No shallowing work; full results transferred and stored.
   * - Local shallow Zarr
     - Approximately 90% saved in measured examples
     - Extra importer work: 63 minutes for the 846-image Plate.
   * - Remote shallow Zarr
     - Preserves shallow-storage savings
     - 18-image comparison: 57% less time in measured return stages and 88% fewer transfer bytes; extra HPC CPU job (25 seconds).

Results depend on data, storage and cluster queues; HPC charges may apply.
The full-Plate remote speedup has not yet been measured. See
:doc:`../developer/biomero-shallow-zarr` for the complete timings and limitations.

Requirements and enablement
---------------------------

Install compatible BIOMERO core, scripts, importer, shallower and schema
packages. The Python package installation does not acquire the helper image
on Slurm. Supply a helper image in a registry accessible to the cluster;
a pinned tag or immutable ``@sha256:...`` reference is recommended.

Set these deployment environment values:

.. code-block:: ini

   IMPORTER_ENABLED=true
   BIOMERO_SHALLOW_ZARR=true
   BIOMERO_REMOTE_SHALLOW_ZARR=true
   BIOMERO_REMOTE_SHALLOWER_WORKERS=1
   BIOMERO_REMOTE_SHALLOWER_PARTITION=

Prefer a pinned ``remote_shallower_image`` under ``[SLURM]`` in the worker's
``slurm-config.ini``. The fallback is
``cellularimagingcf/biomero-shallower:latest``; the BIOMERO core sample
``resources/slurm-config.ini`` contains a maintained release selection.
When ``remote_shallower_version`` is unset, core reads the installed image's
OCI tool-version label before submitting a new helper task. An explicit value
must match the version written into receipts, including any normalized
prerelease suffix. Existing tasks retain their recorded version for recovery.

Set ``BIOMERO_REMOTE_SHALLOWER_IMAGE`` and
``BIOMERO_REMOTE_SHALLOWER_VERSION`` on the importer to the same selected
values for receipt validation. These environment variables can also override
the worker's ini settings. For the Compose demonstration, keep the shared
values in the deployment environment aligned across both services.

The worker's processor forwards the new variables through
``biomero.constants.slurm_env``. Compose supplies matching trust settings to the
importer. An empty helper partition inherits the generic configured partition,
then the scheduler default; administrators can choose their CPU partition
explicitly. The helper requests no GPU. It uses its
worker count as CPUs per task and inherits global memory, time, account,
reservation, and QoS settings. Image acquisition uses the established image-pull
resource settings. Run ``SLURM_Init_environment`` before running analyses and
verify image availability with ``SLURM_check_setup``. Runtime shallowing never
downloads images. A missing or invalid image stops result retrieval with a
setup error identifying the required image; initialize and verify it before retrying.

Equivalent ``[SLURM]`` options are ``remote_shallow_zarr``,
``remote_shallower_image``, ``remote_shallower_version``,
``remote_shallower_workers``, and ``remote_shallower_partition``. Environment
values override ini values. Compose explicitly supplies the environment defaults,
so use its environment values to enable this feature in the demonstration stack.

Admin settings
--------------

When shallow Zarr is enabled, OMERO.biomero's admin settings show a Shallow Zarr
section. The demonstration configuration enables remote shallowing; switching it off hides the
helper fields without removing their saved values. When enabled, the section
provides image, tool version, worker count, partition, memory and time settings.
These fields save the worker's Slurm configuration, not the importer's deployment
environment. Keep the importer trust settings aligned and remember that deployment
environment variables override saved configuration. Run Slurm Init after changing
the helper image.

Failure and observability
-------------------------

Unsupported results use full transfer and local importer handling.
A failed shallowing job runs a recovery job: interrupted
stores roll back; completed shallow stores retain their verified receipts.
Retrieval pauses if submission state or rollback cannot be resolved safely.
Results and journals remain available for recovery. ``keep-full`` is the only
failure policy.

Inspect the shallower task in workflow provenance, its Slurm job IDs, the
``.biomero-shallower/<task-id>/canonical.json.<job-id>.log`` files beside the
workflow data, and the ``.biomero-shallow-report.json`` inside shallow stores.
Image-pull status remains under ``<slurm_script_path>/image-pulls``. Helper task
events do not replace the main analysis progress.

After a detached restart BIOMERO adopts submitted jobs or completed reports.
For an unresolved submission intent, reconcile the unique
``biomero-shallower-<task-id>`` job in Slurm accounting and retry retrieval.
Do not remove prune journals; they can contain arrays needed for rollback.
Keep the original image configured until outstanding recovery is complete.

The helper uses the trusted BIOMERO Slurm account, image, event store, and
import-order writers. Canonical managed identifiers are resolved through the
importer's existing authoritative local group mappings. The canonical store is
not mounted into the helper. ZIP remains the archive format.
