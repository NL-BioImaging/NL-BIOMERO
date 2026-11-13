---
tocdepth: 1
---

# BIOMERO file reference

Look up a `.biomero*` file you found on disk: what it is, which component
writes and reads it, which schema and version it has, and whether you can
delete or move it. Design and recovery procedures are in
[Working with shallow OME-Zarr results](biomero-shallow-zarr.md) and
[Remote shallower configuration](../sysadmin/remote-shallower.rst).

**Where the files are.** Results returned from HPC are stored under
`<group base>/.analyzed/<workflow-id>/<timestamp>/`. Canonical Zarr stores are
stored under `<source folder>/.processed/`, and the canonical sidecar of an
in-place Zarr under a `.processed` folder as well (see its entry). `.processed`
is the default name of a configurable folder (`PROCESSED_DATA_FOLDER`). On local
group storage BIOMERO writes only into these two folders; do not edit or move
files in them by hand. The exceptions are the files on the HPC cluster, the
temporary export folder of a workflow input, and, for importer versions before
the one described in the [canonical sidecar](#canonical-sidecar) entry, the
sidecar next to the input.

**Reading the entries.** "Delete" answers whether you can remove the file, and
what happens if you do. Every answer assumes that no BIOMERO process is working
on that result. A file ending in `.tmp` next to any of these files is an
interrupted atomic write and can be deleted. Schema links go to the
[biomero-schema](https://nl-bioimaging.github.io/biomero-schema/) documentation
(its [versioning rules](https://nl-bioimaging.github.io/biomero-schema/versioning/)
apply to all models there).

## All files at a glance

| File | Safe to delete? | Details |
| --- | --- | --- |
| `.biomero-canonical.json` | No | [entry](#biomero-canonical-json) |
| `.biomero-finalize-<id>.lock` | Yes, when no import is running | [entry](#biomero-finalize-lock) |
| `.biomero-import-storage.json` | Yes after the import; provenance is then lost | [entry](#biomero-import-storage-json) |
| `.biomero-input.json` | Yes | [entry](#biomero-input-json) |
| `.biomero-recovery-probe-<hex>.json` | Yes | [entry](#biomero-recovery-probe) |
| `.biomero-recovery/`, `<name>.biomero-ready` and other receipts (HPC) | Not while a workflow uses the data | [entry](#biomero-recovery-dir) |
| `.biomero-remote-attempt.json` | Yes | [entry](#biomero-remote-attempt-json) |
| `.biomero-result-import.json` | No | [entry](#biomero-result-import-json) |
| `.biomero-result-import.lock` | Yes, when no import is running | [entry](#biomero-result-import-lock) |
| `.biomero-results-retrieved.json` | Yes | [entry](#biomero-results-retrieved-json) |
| `.biomero-shallow-batch.json` | Yes, after the import | [entry](#biomero-shallow-batch-json) |
| `.biomero-shallow-report.json` | Not before the import | [entry](#biomero-shallow-report-json) |
| `.biomero-shallow.json` | No | [entry](#biomero-shallow-json) |
| `.biomero-shallower/<task-id>/` (HPC) | Not before the task is reconciled | [entry](#biomero-shallower-dir) |
| `biomero` key in `.zattrs` / `zarr.json` | No | [entry](#biomero-pointer) |
| `<name>.canonical.json` (canonical sidecar) | Cache; for a Plate it is the only detailed inventory | [entry](#canonical-sidecar) |
| `.<name>.ome.zarr.biomero-lock` (legacy: `<name>.ome.zarr.lock`) | Yes, when nothing is creating the store | [entry](#ome-zarr-lock) |
| `.<store>.biomero-lock` | Yes, when no process is running | [entry](#biomero-lock) |
| `.<store>.biomero-materialize-<hex>/` | Yes | [entry](#biomero-materialize) |
| `.<store>.biomero-prune-<token>/` | No, unless its `journal.json` says `committed: true` | [entry](#biomero-prune) |
| `.<store>.biomero-schema1-backup/` | Yes, once the migration is validated | [entry](#biomero-schema1-backup) |

## Which files appear

| Result | Files in the store |
| --- | --- |
| Full Zarr, shallow storage off | none of these |
| Full Zarr, shallow storage on | [import-storage record](#biomero-import-storage-json) |
| Shallowed by the importer (local) | [manifest](#biomero-shallow-json), [`biomero` pointer](#biomero-pointer), [import-storage record](#biomero-import-storage-json); no operation report |
| Shallowed on HPC (remote) | manifest, pointer, [operation report](#biomero-shallow-report-json), import-storage record |
| Remote helper kept the full result | operation report, import-storage record |
| Remote helper left a report but no receipt and did not shallow | [remote-attempt record](#biomero-remote-attempt-json) replaces the operation report, then the importer handles the store as in the local rows |
| Local shallowing failed and the importer kept the full result (from the importer version containing BIOMERO.importer#55) | import-storage record (`location: importer`, with the reason) |
| Zarr promoted to a canonical store in `.processed` | [canonical marker](#biomero-canonical-json) inside the store |
| Zarr indexed in place | [canonical sidecar](#canonical-sidecar), outside the Zarr |
| Temporary Zarr exported for a workflow input (shallow storage on, shallow result reconstructed) | [input marker](#biomero-input-json) inside the export |

Beside each store (not inside it) you can also find the
[lock](#biomero-lock) and, after an interruption, a [prune folder](#biomero-prune).

## Contracts between components

These files carry information from one component to another. Their formats are
versioned; see [biomero-schema](https://nl-bioimaging.github.io/biomero-schema/).

(biomero-shallow-json)=
### `.biomero-shallow.json`

- **Appears:** root of a shallow `*.zarr` result store (Image or Plate).
- **What:** the shallow manifest. It is the authoritative record of which image
  arrays were omitted, which managed source holds their pixels, which labels
  are retained or referenced, and the decision basis.
- **Written by:** BIOMERO.shallower code, inside the prune transaction. The
  remote helper runs it on HPC; the importer runs it for local shallowing.
- **Read by:** BIOMERO.importer (reuses it on retry), biomero-scripts (storage
  provenance), BIOMERO.ZarrViewer (size limit 100 MiB), BIOMERO.shallower
  (validation, reconstruction, migration).
- **Schema:** `ShallowManifest`, `format: biomero-shallow-zarr`, `schema: 2`
  ([model](https://nl-bioimaging.github.io/biomero-schema/zarr-contracts/#models)).
- **Delete:** no. The store becomes an incomplete Zarr: viewers and
  reconstruction fail, and the importer no longer recognizes it as shallow.
  Move it only together with the whole store, and keep the source and labels
  it references available.

(biomero-pointer)=
### `biomero` key in `.zattrs` (Zarr v2) or `zarr.json` (Zarr v3)

- **Appears:** in the attribute file of every image node of a shallow store.
  In `.zattrs` it is the top-level key `biomero`; in `zarr.json` it is
  `attributes.ome.biomero`. The same edit removes `multiscales`.
- **What:** the pointer from an image node to the manifest:
  `{"format": "biomero-shallow-zarr", "manifest": ".biomero-shallow.json", "workflowId": "<id>"}`.
- **Written by:** BIOMERO.shallower, in the same transaction as the manifest.
  Schema-1 stores used `"model": "rfc8-shallow-copy"` instead of `format`; the
  migration rewrites it.
- **Read by:** BIOMERO.shallower (checks that each image node links to the
  manifest, migration).
- **Schema:** none of its own; the manifest it points to carries the version.
  Model: `ShallowNodePointer` ([model](https://nl-bioimaging.github.io/biomero-schema/persisted-files/#shallow-node-pointer), from the
  biomero-schema version containing #14).
- **Delete:** do not edit it. Without the pointer the node no longer links to
  its manifest and the shallow store fails validation.

(biomero-shallow-report-json)=
### `.biomero-shallow-report.json`

- **Appears:** root of a returned `*.zarr` store that the remote helper
  processed, whether it shallowed the store or kept it full. The local importer
  path writes no report.
- **What:** the operation report: decision, input snapshot, helper tool and
  image, timings, and the manifest when shallowed.
- **Written by:** the remote helper (BIOMERO.shallower on HPC), before the prune
  commits. It travels back in the result archive.
- **Read by:** BIOMERO.importer (checks it against the trusted receipt),
  BIOMERO.shallower (validation, migration).
- **Schema:** `ShallowOperationReport`, `schema: 2`, `inputContract: 1`,
  `outputContract: 2`
  ([model](https://nl-bioimaging.github.io/biomero-schema/remote-shallower-contracts/)).
- **Delete:** not before the import has finished, because the importer verifies
  the result against it. Afterwards deleting it only loses the helper's
  provenance. If a prune is rolled back, BIOMERO removes it together with the
  manifest.

(biomero-shallow-batch-json)=
### `.biomero-shallow-batch.json`

- **Appears:** on HPC in `<workflow data>/data/out/`; the result archive
  carries it to the root of `<group base>/.analyzed/<workflow-id>/<timestamp>/`.
- **What:** the batch report of one helper run over the results folder. It
  lists the receipts for the stores the helper handled.
- **Written by:** the remote helper.
- **Read by:** BIOMERO core, over SSH on HPC (also to adopt a finished helper
  job after a restart). Core stores its content in the workflow event store.
  Nothing reads the copy in `.analyzed`.
- **Schema:** `ShallowBatchReport`, `schema: 1`
  ([model](https://nl-bioimaging.github.io/biomero-schema/remote-shallower-contracts/)).
  The receipts it holds (`RemoteShallowReceipt`, `schema: 1`) exist only as
  entries of this file and in the import order.
- **Delete:** the copy in `.analyzed`: yes. On HPC: yes once the workflow
  results were imported; deleting it while a detached workflow is still
  running stops BIOMERO from adopting the finished report, so it polls the
  recorded helper job instead.

(biomero-import-storage-json)=
### `.biomero-import-storage.json`

- **Appears:** root of a result Zarr store, whenever the importer prepared the
  store for an import that requested shallow storage (also when the full result
  was kept).
- **What:** how the importer stored the result: shallow or full, locally or on
  HPC, tool version, and either the decision basis or the reason the full
  result was kept. For remote results it also records helper image, task, Slurm
  job and report checksum.
- **Written by:** BIOMERO.importer, overwritten on a retry.
- **Read by:** biomero-scripts, which mirrors it into the workflow event store
  and the storage-provenance view.
- **Schema:** `schema: 1`, keys in snake_case: `schema`, `workflow_id`,
  `storage` (`shallow-zarr` or `full-zarr`), `location` (`remote` or
  `importer`), and then, depending on the kind of record, `tool_version`,
  `decision_basis`, `reason`, `container`, `task_id`, `job_id`,
  `report_sha256`. Model: `ImportStorageRecordUnion`
  ([model](https://nl-bioimaging.github.io/biomero-schema/persisted-files/#import-storage-record), from the biomero-schema version
  containing #14). The outcome "local shallowing failed, full result kept" is
  recorded from the importer version containing BIOMERO.importer#55.
- **Delete:** safe once the result is imported and its provenance is recorded.
  Without it, scripts record the storage location of a shallow result as
  `unknown`, and the evidence of a full result is lost.

(biomero-remote-attempt-json)=
### `.biomero-remote-attempt.json`

- **Appears:** root of a result Zarr store.
- **What:** an operation report that the importer set aside, kept for
  diagnosis. It exists when the remote helper left a report for a store but
  had not shallowed it (and no trusted receipt exists); the importer then
  evaluates the store itself.
- **Written by:** BIOMERO.importer (renames the report). Nothing reads it.
- **Schema:** a `ShallowOperationReport` (`schema: 2`) under another name.
- **Delete:** yes.

(biomero-canonical-json)=
### `.biomero-canonical.json`

- **Appears:** root of a canonical Zarr store,
  `<source folder>/.processed/<Image|Plate>-<id>.ome.zarr/` (`.processed` is
  the default name of a configurable folder). A temporary
  `.biomero-canonical.json.tmp` exists while the store is promoted.
- **What:** the canonical marker: proof that the store was promoted completely,
  and the identity of the source it was made from (locator, generation, pixel
  identity, labels).
- **Written by:** BIOMERO.importer code, called by biomero-scripts (transfer
  and Migrate Shallow Storage), when a store is promoted; it also rewrites the
  file in place when it refreshes cached comparison metadata.
- **Read by:** BIOMERO.importer (adopts an existing store only when the marker
  matches), biomero-scripts (reuse of canonical inputs). Reconstruction skips
  it when it copies a store.
- **Schema:** wrapper `{"markerSchema": 1, "state": "committed", "source": ...}`
  where `source` is a `CanonicalZarrSource` (Image) or `CanonicalPlateSource`
  (Plate), each `schema: 1`
  ([models](https://nl-bioimaging.github.io/biomero-schema/zarr-contracts/#models)).
  The wrapper is modelled as `CanonicalMarker`
  ([model](https://nl-bioimaging.github.io/biomero-schema/persisted-files/#canonical-marker), from the biomero-schema version containing
  #14).
- **Delete:** no. The importer refuses a canonical store that has no committed
  marker (`InvalidCanonicalStore`) and the cached pixel identity is lost.

(canonical-sidecar)=
### `<name>.canonical.json` in `.processed/.biomero` (canonical sidecar)

<!-- Update when BIOMERO.importer#59 is released: add the importer version. -->

- **Appears:** for a user Zarr that BIOMERO indexes in place, from the importer
  version that contains BIOMERO.importer#59:
  `<Zarr parent>/<processed folder>/.biomero/<Zarr name>.canonical.json`, where
  the processed folder is `.processed` by default (if the Zarr already sits
  directly in a processed folder, that folder is used and no second one is
  created). Nothing is written next to the input outside that folder. If the
  folder cannot be written, the importer logs a warning, skips the sidecar and
  the workflow continues; an old sidecar stays in place. Zarrs that BIOMERO created
  keep an internal [`.biomero-canonical.json`](#biomero-canonical-json)
  instead.
- **Earlier betas:** older importer versions wrote the sidecar to
  `<input parent>/.biomero/<name>.canonical.json`, next to the input. The
  importer still reads that file. The next time it writes the sidecar, it
  writes it to the new location and removes only its own old file, and the old
  `.biomero` folder only if it is empty.
- **What:** the same canonical marker as above, for a Zarr that BIOMERO indexed
  in place instead of promoting. For a Plate it holds the detailed per-image
  inventory behind the compact `biomero.zarr.plate-source` annotation in OMERO.
- **Written by:** BIOMERO.importer code, called by biomero-scripts (transfer
  and Migrate Shallow Storage), when it indexes an existing backing Zarr in
  place and when comparison metadata is refreshed.
- **Read by:** BIOMERO.importer and biomero-scripts, which look for the internal
  marker first, then the sidecar, then the old location.
- **Schema:** the same wrapper as the canonical marker (`markerSchema: 1`).
- **Delete:** it holds cached detail, not the only record. For an Image the
  OMERO `biomero.zarr.source` annotation still holds the record. For a Plate
  the sidecar is the only detailed inventory: without it BIOMERO finds no
  canonical record for the Plate (logged as "No BIOMERO canonical Zarr record
  found"), so the Plate is not reused as a canonical input until it is indexed
  again. Back up the `.processed` folders together with the data. The sidecar
  is keyed by the Zarr's location: if you move the Zarr, the sidecar is not
  found.

(biomero-input-json)=
### `.biomero-input.json`

- **Appears:** root of a temporary Zarr that biomero-scripts export into a
  workflow input folder, only when shallow storage is on and a shallow Zarr is
  reconstructed for the input. It travels to HPC and back with the result.
- **What:** the transfer input marker: which canonical input (source and
  generation) the exported Zarr was made from, so a renamed result can be
  matched to its input.
- **Written by:** biomero-scripts, atomically (through a `.tmp` file).
- **Read by:** BIOMERO.shallower (evaluation of the returned store) and
  BIOMERO.importer. The importer deletes it when it consumes it: on local
  evaluation, or when the helper kept the full result.
- **Removed by:** `SLURM_Run_Workflow.py`, from the imported result folder
  (`.analyzed/<workflow>/<timestamp>` only), once the import has succeeded. From
  the biomero-scripts version containing biomero-scripts#97 it therefore no
  longer remains in a store that the helper shallowed on HPC. Before that
  version it can remain there. A result whose import failed keeps it until the
  retry succeeds.
- **Schema:** `CanonicalInput`, `schema: 1`
  ([model](https://nl-bioimaging.github.io/biomero-schema/zarr-contracts/#models)).
  The event store snapshot stays authoritative.
- **Delete:** yes. Deleting it before the import only costs the matching of a
  renamed result to its input.

## Internal state of one component

These files are not exchanged between components. They protect or resume work
of the component that writes them.

### BIOMERO.shallower and BIOMERO.importer: store transactions

(biomero-prune)=
#### `.<store>.biomero-prune-<token>/` (with `journal.json`)

- **Appears:** beside a result store, only after an interrupted prune. It holds
  the arrays moved out of the store, `journal.json` (and `journal.json.tmp`
  during a write).
- **What:** the rollback folder of a prune. `journal.json` is
  `{"schema": 1, "committed": <bool>, "moves": [...], "attrs": {<path>: <base64>}}`:
  the moved array paths and the original bytes of the changed attribute files.
- **Written by:** BIOMERO.shallower. **Read by:** BIOMERO.shallower recovery,
  which the importer and the remote helper's recovery job run before they
  continue.
- **Reading `committed`:** open `journal.json`. `committed: false` means the
  prune was not finished and the folder can hold the only copy of the omitted
  arrays. `committed: true` means the prune completed and the store is valid;
  only the cleanup of duplicate arrays remains.
- **Delete:** no. While `committed` is `false` the folder can hold the only
  copy of the omitted arrays. BIOMERO finishes or undoes the prune itself the
  next time the importer or helper handles the store. Remove a folder by hand
  only when its `journal.json` says `committed: true`: only the cleanup of
  duplicate arrays remains. See
  {ref}`Failure and observability <remote-shallower-failure>`.

(biomero-lock)=
#### `.<store>.biomero-lock`

- **Appears:** beside a result store (on HPC and in `.analyzed`).
- **What:** the lock file of the store; the lock is held by the process, not by
  the file (empty on Linux, released when the process ends). Lock files created
  on HPC are not part of the result archive.
- **Written and read by:** BIOMERO.shallower and BIOMERO.importer.
- **Delete:** yes, when no process is working on the store.

(biomero-materialize)=
#### `.<store>.biomero-materialize-<hex>/`

- **Appears:** beside the destination of a reconstruction of a full Zarr.
- **What:** staging folder, removed when the reconstruction ends.
- **Written and read by:** BIOMERO.shallower.
- **Delete:** yes. It is a leftover of a killed process.

(biomero-schema1-backup)=
#### `.<store>.biomero-schema1-backup/`

- **Appears:** beside a store migrated with the BIOMERO.shallower `migrate-v1`
  command, unless the caller chose another backup path. The **BIOMERO Migrate
  Shallow Storage** script chooses one: it keeps the backup in
  `<Backup Directory>/store-<n>-files`, where the Backup Directory is the
  administrator's input, or by default
  `/data/biomero-shallow-migrations/shallow-storage-<uuid>/` inside the worker
  container. The script also keeps its other snapshots there.
- **What:** a copy of the schema-1 manifest, operation report (if there was
  one) and the changed `.zattrs` files, from before the migration.
- **Written by:** BIOMERO.shallower. Used by an operator only; the migration
  also restores from it when it fails.
- **Delete:** yes once you validated the migrated store. It is the only way
  back to schema 1.

(ome-zarr-lock)=
#### `.<name>.ome.zarr.biomero-lock` and the legacy `<name>.ome.zarr.lock`

<!-- Update when BIOMERO.importer#61 is released: add the importer version. -->

- **Appears:** beside a canonical store in `.processed`, from the importer
  version containing BIOMERO.importer#61: `.processed/.<name>.ome.zarr.biomero-lock`.
  It is created when the store is created.
- **What:** the creation lock, a kernel lock taken through BIOMERO.shallower's
  `locked()`. The operating system releases it when the process ends, also
  after a crash. The empty file stays behind and never blocks a later creation.
- **Written and read by:** BIOMERO.importer code, called by biomero-scripts'
  canonical promotion in the OMERO script worker.
- **Delete:** yes, when nothing is creating that store.
- **Legacy `<name>.ome.zarr.lock`:** older importer versions created this file
  with the process ID as content and removed it when the creation ended. From
  the importer version containing #61 it is no longer written, and a leftover
  file is ignored and can be deleted. With the older versions, a leftover file
  after a crash blocks creating the store (`CanonicalCreationLocked`) until you
  remove it, and you may delete it only when no importer is creating that store.

### biomero-scripts: result retrieval and import

These files sit in the results folder `<group base>/.analyzed/<workflow-id>/<timestamp>/`
(the lock `.biomero-finalize-<id>.lock` in `.analyzed/<workflow-id>/`).

(biomero-results-retrieved-json)=
#### `.biomero-results-retrieved.json`

- **What:** marker that downloading and extracting the results completed
  (`schema: 1`, `status`, `workflowId`, `slurmJobId`, `completedAt`). It lets a
  rerun skip the download.
- **Delete:** yes. A rerun then falls back to checking the retained archive,
  or downloads the results again.

(biomero-result-import-json)=
#### `.biomero-result-import.json`

- **What:** the saved import plan of these results (`schema: 1`, `phase`, the
  request, the import orders, the rename map and the destination). `phase` is
  `preparing` (written first, before any order exists), then `orders-ready` and
  `registered`. A file that still says `preparing` means the earlier attempt
  stopped before its orders were saved; BIOMERO then refuses to continue and
  asks for a review. The file is written only when the storage supports
  recovery (locks and durable writes); otherwise the legacy path runs without
  it.
- **Delete:** no, keep it. It lets a rerun poll the existing orders instead of
  submitting new ones. If the results already have importer orders but no
  record, a rerun is refused ("already have importer orders but no recovery
  record") until an administrator has reviewed the existing registrations.

(biomero-result-import-lock)=
(biomero-finalize-lock)=
(biomero-recovery-probe)=
#### `.biomero-result-import.lock`, `.biomero-finalize-<id>.lock`, `.biomero-recovery-probe-<hex>.json`

- **What:** locks that serialize the import of one workflow's results, and a
  disposable file that probes whether the storage supports durable writes (it
  is deleted at once).
- **Delete:** yes, when no import is running. A lock is held by the running
  process; the file itself is not state.

### BIOMERO core on HPC

(biomero-shallower-dir)=
#### `<workflow data>/.biomero-shallower/<task-id>/`

- **What:** state of one remote-shallowing helper task: `canonical.json` (the
  canonical input manifest, `CanonicalInputManifest` `schema: 1`) with its
  `.lock`, the helper's Slurm output `canonical.json.<slurm-job-id>.log`, and
  the submission receipts `shallow.*` and `recovery.*` (suffixes `.lock`,
  `.digest`, `.intent`, `.job`, `.job.tmp`, `.failed`, `.stdout`, `.stderr`)
  that let BIOMERO resume after a lost connection. BIOMERO removes the
  `recovery.*` receipts after the recovery job.
- **Written and read by:** BIOMERO core.
- **Delete:** not before the task is reconciled; keep it for recovery and
  diagnosis. See
  {ref}`Failure and observability <remote-shallower-failure>`.

(biomero-recovery-dir)=
#### Other receipts next to HPC data

- **What:** `.biomero-recovery/<task-id>.*` (receipts of tracked job
  submissions), and next to result archives and uploaded input archives `<name>.biomero-ready`,
  `<name>.biomero-partial`, `<name>.biomero-lock`, `<name>.biomero-unpacked`,
  plus `<slurm_script_path>.biomero-update.lock`. They make repeated requests
  after a lost connection safe.
- **Written and read by:** BIOMERO core.
- **Delete:** not while a workflow uses that data; leave them to BIOMERO.

## OMERO mirrors

OMERO annotations are an index; the file is the authority.

| Annotation | Mirrors | Schema |
| --- | --- | --- |
| `biomero.zarr.shallow`, `biomero.zarr.shallow-plate` | [manifest](#biomero-shallow-json) | `ShallowZarrReference`, `ShallowPlateReference`: `schema: 2` |
| `biomero.zarr.source` | [canonical marker](#biomero-canonical-json) or [sidecar](#canonical-sidecar), Image | `CanonicalZarrSource`: `schema: 1` |
| `biomero.zarr.plate-source` (with `.image` and `.label` records for older registrations) | canonical marker or sidecar, Plate (compact index; detail in the file) | `CanonicalPlateIndex`: `schema: 2` |
| storage provenance (event store, shown in OMERO) | [import-storage record](#biomero-import-storage-json) | as the record |

## Maintenance

Adding, moving or removing a file that BIOMERO writes updates this page in the
same change.
