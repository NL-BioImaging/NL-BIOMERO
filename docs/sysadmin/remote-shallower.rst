Optional remote Zarr shallowing
==============================

BIOMERO can normalize eligible workflow OME-Zarr output on Slurm before ZIP
creation and transfer. The helper retains new/changed labels and references
verified canonical pixels already available on the OMERO side. The importer
validates the helper receipt and registers the result without repeating pixel
hashing or normalization. Other workflow files follow the existing import path.

The feature is disabled when ``BIOMERO_REMOTE_SHALLOW_ZARR`` is absent or false.
It is an administrator setting, not a workflow parameter. The existing local
shallow importer path remains the default.

Requirements and enablement
---------------------------

Install matching BIOMERO core, scripts, importer, ``biomero-shallower==0.1.0``,
and schema packages containing the version-1 receipt contracts. The initial
schema build is ``0.2.1.dev1``; use the corresponding published release when
available. Supply a versioned helper image in a registry accessible to the
cluster. An immutable ``@sha256:...`` image reference can be used. Configure
the same image and helper package version on the worker and importer.

Set these deployment environment values:

.. code-block:: ini

   IMPORTER_ENABLED=true
   BIOMERO_SHALLOW_ZARR=true
   BIOMERO_REMOTE_SHALLOW_ZARR=true
   BIOMERO_RESULT_NORMALIZER_IMAGE=cellularimagingcf/biomero-shallower:0.1.0
   BIOMERO_RESULT_NORMALIZER_VERSION=0.1.0
   BIOMERO_RESULT_NORMALIZER_WORKERS=1
   BIOMERO_RESULT_NORMALIZER_PARTITION=

The worker's processor forwards the new variables through
``biomero.constants.slurm_env``. Compose supplies matching trust settings to the
importer. An empty partition lets Slurm select its default; administrators can
choose their CPU partition explicitly. The helper requests no GPU. It uses its
worker count as CPUs per task and inherits global memory, time, account,
reservation, and QoS settings. Image acquisition uses the established image-pull
resource settings. Initialize Slurm images before running analyses.

Equivalent ``[SLURM]`` options are ``remote_shallow_zarr``,
``result_normalizer_image``, ``result_normalizer_version``,
``result_normalizer_workers``, and ``result_normalizer_partition``. Environment
values override ini values. Compose explicitly supplies the environment defaults,
so use its environment values to enable this feature in the demonstration stack.

Failure and observability
-------------------------

Unsupported results and image-acquisition failures use full transfer and local
importer handling. A failed normalization job runs a recovery job: interrupted
stores roll back; completed shallow stores retain their verified receipts.
Retrieval pauses if submission state or rollback cannot be resolved safely.
Results and journals remain available for recovery. ``keep-full`` is the only
failure policy.

Inspect the normalizer task in workflow provenance, its Slurm job IDs, the
``.biomero-normalizer/<task-id>/canonical.json.<job-id>.log`` files beside the
workflow data, and the ``.biomero-shallow-report.json`` inside normalized stores.
Image-pull status remains under ``<slurm_script_path>/image-pulls``. Helper task
events do not replace the main analysis progress.

After a detached restart BIOMERO adopts submitted jobs or completed reports.
For an unresolved submission intent, reconcile the unique
``biomero-normalizer-<task-id>`` job in Slurm accounting and retry retrieval.
Do not remove prune journals; they can contain arrays needed for rollback.
Keep the original image configured until outstanding recovery is complete.

The helper uses the trusted BIOMERO Slurm account, image, event store, and
import-order writers. Canonical managed identifiers are resolved through the
importer's existing authoritative local group mappings. The canonical store is
not mounted into the helper. ZIP remains the archive format.
