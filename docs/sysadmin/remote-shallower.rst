Optional remote Zarr shallowing
==============================

BIOMERO can shallow eligible workflow OME-Zarr output on Slurm before ZIP
creation and transfer. The helper retains new/changed labels and references
verified canonical pixels already available on the OMERO side. The importer
validates the helper receipt and registers the result without repeating pixel
hashing or shallowing. Other workflow files follow the existing import path.

Shallow Zarr remains opt-in through ``BIOMERO_SHALLOW_ZARR=true``. When enabled,
remote shallowing is the default. Administrators can opt out by setting
``BIOMERO_REMOTE_SHALLOW_ZARR=false`` to use local importer shallowing instead,
for example when additional Slurm compute costs outweigh the transfer savings.
This setting does not enable shallow Zarr by itself and is not a workflow parameter.

Choosing local or remote shallowing
----------------------------------

Shallow Zarr trades pixel-verification compute and storage I/O for reduced
persistent disk use. Local and remote shallowing provide the same storage
optimization; the choice determines where the processing takes place.

Remote shallowing adds a CPU job on the HPC cluster, with any associated
compute charges and queue wait. In exchange, duplicate pixels do not need to
be archived, transferred back, or extracted onto importer storage. It is most
useful when transfer bandwidth or importer storage I/O limits result retrieval.
Local shallowing avoids that extra HPC job but transfers the full result and
performs verification and shallowing in the importer.

In an observed 18-image cisegmentation comparison on the Windows/Docker
development deployment, remote shallowing reduced the returned ZIP from
153.0 MB to 17.8 MB (88.4%). Combined identity calculation, shallowing,
archiving, transfer and local extraction fell from 194.4 to 84.4 seconds,
a saving of approximately 110 seconds (57%). The remote helper occupied one
allocated CPU for 25 seconds. These observations are deployment-specific,
not a guaranteed speedup or a measurement of HPC billing costs.

See :doc:`../developer/biomero-shallow-zarr` for the storage model, detailed
stage measurements, and comparison limitations. Keep remote shallowing enabled
when these savings justify the cluster allocation; set
``BIOMERO_REMOTE_SHALLOW_ZARR=false`` when local processing is preferable.

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
   BIOMERO_REMOTE_SHALLOWER_IMAGE=cellularimagingcf/biomero-shallower:0.1.0
   BIOMERO_REMOTE_SHALLOWER_VERSION=0.1.0
   BIOMERO_REMOTE_SHALLOWER_WORKERS=1
   BIOMERO_REMOTE_SHALLOWER_PARTITION=

The worker's processor forwards the new variables through
``biomero.constants.slurm_env``. Compose supplies matching trust settings to the
importer. An empty partition lets Slurm select its default; administrators can
choose their CPU partition explicitly. The helper requests no GPU. It uses its
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
section. Remote shallowing is enabled by default; switching it off hides the
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
