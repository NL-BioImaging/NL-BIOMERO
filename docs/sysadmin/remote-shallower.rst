Shallow OME-Zarr Storage
========================

Shallow storage avoids keeping another copy of unchanged image pixels in
eligible OME-Zarr workflow results. BIOMERO retains new or changed labels and
references verified source pixels already in managed storage. Original source
data remains unchanged.

The matched component releases support OME-Zarr 0.4 / Zarr v2 and OME-Zarr
0.5 / Zarr v3 Images and Plates. Existing managed stores keep their format;
upgrading does not rewrite them. Shallow results reconstruct in their source
format, including retained labels.

The demo's Leica, Incucyte database and Incucyte archive preprocessing routes
all create new stores with ``extra_params.outputformat=omezarr05``. Workflow
inputs default to ``0.4`` / v2. Administrators can enable **Zarr v3 input
(OME-Zarr 0.5)** per Bilayers workflow in Settings; this saves the JSON list
``[UI] zarr_v3_workflows``. BIAFLOWS and TIFF conversion always use v2. Save
Settings applies to new runs without Slurm Init or a container restart.

Matching formats reuse the backing store directly. A mismatch creates temporary
workflow input, including reconstructed labels, without replacing canonical
storage. Returned data in a different format from its canonical source stays
full. The shallower checks format compatibility before pixel hashing. No second
canonical copy is kept for compatibility; conversion and full-result storage
still have a cost.

The NL-BIOMERO demo enables shallow Zarr. Other deployments opt in with
``BIOMERO_SHALLOW_ZARR=true``. Remote processing is then the default; set
``BIOMERO_REMOTE_SHALLOW_ZARR=false`` for local importer processing instead.
Without shallow Zarr enabled, the remote setting has no effect.

Remote processing is recommended when Slurm is available. It produces the same
shallow result as local processing, while removing duplicate data before the
return archive is created and moving the expensive verification and shallowing
work from the importer to a CPU-only Slurm helper.

.. note::
   **Summary for system administrators:**

   * Requires :doc:`analyzer-importer-admin` and ``IMPORTER_ENABLED=true``.
   * Enable with ``BIOMERO_SHALLOW_ZARR=true``; set it to ``false`` to stop
     shallowing new results. Existing shallow results still need their sources.
   * Remote processing is the recommended default. It reduces transfer volume
     and importer work at the cost of a CPU-only HPC helper job.
   * Configure the helper image/resources and run Slurm Init after upgrading.
     This is the normal post-upgrade initialization step and acquires the helper
     image together with the other configured workflow images when importer,
     shallow storage and remote processing are all enabled.
   * Keep source storage available. This feature reduces duplicate result data;
     it does not replace backups or enable detached execution.

Existing feature switches remain independent:

.. list-table:: Feature scope
   :header-rows: 1
   :widths: 35 65

   * - Switch
     - Effect
   * - ``IMPORTER_ENABLED``
     - Selects in-place result import; false uses classic result upload.
   * - ``BIOMERO_SHALLOW_ZARR``
     - Enables canonical indexing and new shallow results. False keeps full
       results; existing shallow inputs can still be reconstructed from their
       sources with the required dependencies installed.
   * - ``BIOMERO_REMOTE_SHALLOW_ZARR``
     - Within enabled shallow storage, selects remote processing (default true)
       or local importer processing (false). It cannot enable shallow storage.
   * - ``BIOMERO_DETACHED_WORKFLOWS``
     - Selects background execution independently of storage and result-import
       recovery. See :doc:`detached-workflows`.
   * - ``BIOMERO_ZARR_VIEWER_ENABLED``
     - Controls the web viewer independently of storage and execution.
       See :doc:`zarrviewer`.

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
-----------------------------------

.. list-table:: Matched 846-image Plate result handling
   :header-rows: 1
   :widths: 34 28 28

   * - Measure
     - Local shallowing
     - Remote shallowing
   * - Shallow processing and validation
     - 1 h 47 min 7 s on the importer
     - 15 min 31 s total: 14 min 28 s on HPC and 1 min 3 s on the importer
   * - Return ZIP
     - 7.36 GB
     - 0.91 GB (87.6% smaller)
   * - ZIP creation and return validation
     - 9 min 32 s
     - 4 min 6 s (57% less)
   * - Additional Slurm helper allocation
     - None
     - 0.482 CPU-hours; 2 CPUs, 2 GiB memory and no GPU
   * - Final extracted result
     - 1.898 GB (75.4% below the full result)
     - 1.913 GB (75.2% below the full result; effectively equal to local)

Matched comparisons verified source pixels and labels with local and remote
shallowing on both 18-image and 846-image Plates. The large-Plate comparison
reduced the shallowing-specific processing and validation time by 85.5%, while
producing equivalent final data. Both modes reduced final storage by about 75%
relative to the 7.73 GB full workflow result. Slurm accounting and billing
policies are site-specific; the allocated CPU-hours in the table provide the
portable input for estimating that cost.

The complete remote workflow finished 14 min 34 s (4.6%) faster, but unrelated
variation on the mounted storage obscured much of the stage-level saving.
End-to-end time remains dependent on storage load and the Slurm queue; the table
therefore compares the work affected directly by remote shallowing. Choose local
processing only when avoiding the additional HPC allocation is more important
than transfer volume and importer time. See
:doc:`../developer/biomero-shallow-zarr` for the data model and reconstruction.

Requirements and enablement
---------------------------

The demonstration stack shares ``web/slurm-config.ini`` between OMERO.biomero
and the workflow worker. ``SLURM_CONFIG_HOST_PATH`` selects this canonical
configuration in the root Compose files; deployment-scenario files mount the
same file. The INIs under ``biomeroworker/`` are alternative examples, not
additional active configurations. Feature flags belong to the deployment
environment; helper image and resource settings belong to the shared INI.

Install compatible BIOMERO core, scripts, importer, shallower and schema
packages. The Python package installation does not acquire the helper image
on Slurm. Supply a helper image in a registry accessible to the cluster;
a pinned tag or immutable ``@sha256:...`` reference is recommended.

Set these deployment environment values:

.. code-block:: ini

   IMPORTER_ENABLED=true
   BIOMERO_SHALLOW_ZARR=true
   BIOMERO_REMOTE_SHALLOW_ZARR=true

Configure helper runtime settings under ``[SLURM]`` in the shared
``web/slurm-config.ini`` or through OMERO.biomero's admin settings. Do not supply
worker runtime overrides in Compose: they take precedence over saved INI values.

Prefer a pinned ``remote_shallower_image`` under ``[SLURM]`` in the worker's
``slurm-config.ini``. The fallback is
``cellularimagingcf/biomero-shallower:latest``; NL-BIOMERO supplies a pinned
release selection in its shared configuration.
When ``remote_shallower_version`` is unset, core reads the installed image's
OCI tool-version label before submitting a new helper task. An explicit value
must exactly match the version written into receipts. Existing tasks retain
their recorded version for recovery.

Set ``BIOMERO_REMOTE_SHALLOWER_IMAGE`` and
``BIOMERO_REMOTE_SHALLOWER_VERSION`` on the importer to the same selected
values for receipt validation. The importer has its own settings and does not
read the Slurm INI. The demonstration supplies these trust values only to the
importer, not to web or the workflow worker. Keep them aligned when changing
the helper image through the admin interface.

The worker loads helper runtime settings from the shared Slurm INI. Compose
supplies matching trust settings to the importer. An empty helper partition inherits the generic configured partition,
then the scheduler default; administrators can choose their CPU partition
explicitly. The helper requests no GPU. It uses its
worker count as CPUs per task and inherits global memory, time, account,
reservation, and QoS settings. Image acquisition uses the established image-pull
resource settings. Run ``SLURM_Init_environment`` before running analyses and
verify image availability with ``SLURM_check_setup``. Runtime shallowing never
downloads images. A missing or invalid image stops result retrieval with a
setup error identifying the required image. BIOMERO also verifies the installed
helper's version and storage-format capabilities before it changes result data;
initialize and verify the selected image before retrying.

After upgrading an installation that already contains older shallow-storage
data, run ``BIOMERO Migrate Shallow Storage (Admin Only)``. Run its dry mode
first, then apply the migration after reviewing the count and estimated space
recovery. The migration updates manifests and OMERO references, consolidates
canonical registrations, and creates recovery files without copying image
pixels.

Equivalent ``[SLURM]`` options are ``remote_shallow_zarr``,
``remote_shallower_image``, ``remote_shallower_version``,
``remote_shallower_workers``, and ``remote_shallower_partition``. Environment
values override ini values when explicitly supplied. The demonstration keeps
runtime settings in the INI and supplies only feature flags to the worker through
the deployment environment.

Admin settings
--------------

When shallow Zarr is enabled, OMERO.biomero's admin settings show a Shallow Zarr
section. The demonstration configuration enables remote shallowing; switching it off hides the
helper fields without removing their saved values. When enabled, the section
provides image, tool version, worker count, partition, memory and time settings.
These fields save the worker's Slurm configuration, not the importer's separate
settings. Keep the importer trust settings aligned. Run Slurm Init after changing
the helper image.

Failure and observability
-------------------------

Result-import recovery is automatic on compatible storage, with no additional
feature flag. Before preparing an import, the scripts check filesystem locking,
atomic replacement and file/directory synchronization using disposable metadata.
Use coordinated scripts and importer releases that contain recovery support.
This does not add SSH reconnection or require SSHFS.

Order recovery protects importer-enabled full Zarr and TIFF results as well
as shallow results, in both inline and detached workflows. It does not enable
any of the switches above. Importer-side shallow transaction recovery requires
an explicitly requested shallow operation and ``BIOMERO_SHALLOW_ZARR=true``;
ordinary import orders do not enter shallow preparation.

Recovery saves one small record per newly
staged workflow-result import plan, reuses order IDs on retry, and restores
interrupted local shallow transactions. It does not scan or migrate old OMERO
images, Plates or Zarrs. An explicitly retried older result without a record
requires review if existing importer orders make resubmission ambiguous.

If the preflight explicitly reports an unsupported lock or durable-write
operation, a fresh attempt uses legacy operations and logs that recovery is
unavailable. This happens before submitting import orders. A busy lock,
permission failure, disk-full error, storage outage or failure after recovery
has begun does not trigger fallback. Existing recovery records and unfinished
prune journals must be resolved using storage supporting recovery.

Failed imports retain their files and cannot report success in either mode.
In the legacy fallback, automatic order reuse is unavailable; review previous
orders before retrying. See the
`importer recovery guide <https://nl-bioimaging.github.io/BIOMERO.importer/shallow-zarr/#interrupted-imports-and-recovery>`_.

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
