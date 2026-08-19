# BIOMERO shallow Zarr storage and workflow transfer plan

Status: implementation in progress on `feature/zarr-shallow-storage`

Implemented foundations:

- shared Pydantic contracts in `biomero-schema`, independently versioned from
  workflow descriptors;
- validated `CanonicalInputsRecorded` workflow events in `biomero`, with legacy
  workflow state defaulting to an empty snapshot;
- transactional `.processed` placement, locking, adoption, and commit primitives
  in BIOMERO.importer for derived conversions that do not already exist as a
  stable Zarr;
- namespace-aware canonical lookup and safe root reuse in Image Transfer;
- immutable workflow event snapshots for fully covered indexed inputs, without
  a second Slurm-side provenance file;
- a pinned `iscc-bio` IMAGEWALK adapter, NGFF 0.4/Zarr v2 semantic guard,
  OMERO-versus-Zarr pixel verification, and transactional first-export
  promotion for individual OMERO Images;
- canonical-source MapAnnotation attachment and inclusion of newly promoted
  Images in the exact workflow input snapshot;
- Import Results loading of the event-store snapshot as a lineage fast path;
  absent or legacy snapshots fall back to exact returned-pixel identity matching.

Raw-import identity calculation, in-place importer-produced/legacy Zarr adoption, Plate
promotion, Import Results normalization, projection, and materialization remain
pending. First-export Image promotion currently bootstraps the authoritative
identity from OMERO Pixels and refuses promotion when dimensions, pixel type, or
the ISCC-BIO Instance-Code disagree.

## Decision

BIOMERO will store eligible Zarr workflow results as shallow, RFC-8-shaped
collections instead of retaining a copy of the original intensity data in every
result.

This is a BIOMERO storage optimization, not a BILAYERS extension. BILAYERS, like
BIAFLOWS before it, is an external FAIR workflow interface that BIOMERO
interprets and runs on scalable infrastructure. Generic workflow providers must
not need to understand BIOMERO storage, OMERO registration, or proprietary Zarr
metadata.

BIOMERO owns both cross-system boundaries:

- after OMERO export and before transfer to the workflow;
- after workflow result retrieval and before storage and OMERO registration.

Those boundaries are sufficient to compute identities, add optional hints,
normalize results, rebase RFC-8 references, and reconstruct complete Zarrs for
later workflows.

## Scope

Implement:

- one canonical, read-only source record per OMERO Image or Plate generation;
  several image records may share one physical multi-series Zarr root;
- source identities calculated once and cached by BIOMERO;
- generic full-Zarr result comparison without workflow changes;
- optional BIOMERO result hints for cooperative workflows or adapters;
- ingestion of native RFC-8 shallow results with source rebasing;
- RFC-8-shaped internal shallow collections;
- label-backed OMERO Image and Plate projections;
- reconstruction of a conventional, self-contained OME-Zarr before another
  workflow receives a stored shallow result;
- transactional retention and cleanup.

Do not implement:

- changes to the BILAYERS specification;
- a requirement that FAIR workflows read or write BIOMERO metadata;
- a black or sparse placeholder image;
- an RFC-8-aware OMERO PixelBuffer or viewer;
- automatic merging of every result collection when an original is selected;
- symlink-only or virtual-chunk transfer as the interoperability baseline.

## Current interchange profile

The initial supported round-trip profile is:

```text
OME-NGFF metadata: 0.4
Zarr storage format: v2
```

This is the format currently selected by default in the BIOMERO scripts. The UI
also exposes NGFF 0.5/Zarr v3, but the full path is constrained by more than the
Python parser:

- export uses `omero-cli-zarr 0.8.0` and Glencoe
  `bioformats2raw 0.12.0-rc1`;
- BIOMERO.importer currently uses Zarr Python 3 APIs for metadata registration;
- OMERO serves registered pixels through Glencoe
  `omero-zarr-pixel-buffer 0.6.1`, backed by `jzarr 0.4.2` in this deployment.
- pixel identity uses the public `iscc_bio.api.biocode` API pinned to upstream
  commit `c536d7699b7d25592bfe5c91c947b749344b6914`; no PyPI release currently
  exists, so both the importer and workflow worker install that Git revision
  through the importer's `identity` extra.

Treat 0.4/v2 as the supported provider contract until 0.5/v3 has passed explicit
export, import, PixelBuffer rendering, label, Plate, and reconstruction tests.
Parsing a store in Python is not sufficient evidence that OMERO can render it.
Record the selected interchange profile in task provenance and make it a
deployment capability rather than a permanent hard-coded assumption.

The initial structural subset is the one the exporter and register path already
share: released multiscale Image metadata with named axes, dataset paths, and
scale coordinate transformations; released HCS Plate/well/field paths; label
groups beneath their image nodes; and Glencoe `bioformats2raw.layout = 3` with
`OME/METADATA.ome.xml`. Treat other layouts as capability-gated.

The internal RFC-8-shaped collection manifest is standalone JSON and is not read
by the PixelBuffer. Every retained node registered as an OMERO projection must,
however, use the deployed readable profile. Initial native RFC-8 ingestion is
therefore limited to compatible retained nodes; v3-only nodes are preserved and
reported until a conversion path or newer PixelBuffer is deployed.

## Storage and write policy

- Canonical source Zarrs are immutable and read-only to workflow workers.
- A workflow receives a writable task-local copy or materialization, never the
  canonical source itself.
- Workflows write only beneath their workflow/task output locations.
- `.processed` and `.analyzed` are writable by the BIOMERO storage service, but
  committed objects are treated as immutable. A change creates a new generation
  through a transactional staging-and-rename operation.
- Normalize never edits a canonical source or committed collection in place.

The filesystem does not have to be globally read-only. The invariant is that
workflow workers cannot mutate canonical or previously committed data.

## Canonical source placement and reuse

"Canonical source" is a catalog role in the current contracts, not an instruction
to create a byte-for-byte copy. Prefer "indexed/referenceable Zarr source" in
operator and provider documentation. Use BIOMERO.importer's existing `.processed`
area only as the durable home for Zarr conversions that did not already exist.
Do not introduce a second global source-Zarr tree, and do not place a newly
exported conversion beneath a transient workflow UUID merely because that
workflow triggered its creation. A genuinely derived image remains part of its
committed result collection.

Apply these cases in order:

1. If an OMERO Image or Plate was registered from an existing managed Zarr, that
   Zarr is already canonical. Keep it in place and record its root plus image or
   Plate node path; do not copy it into `.processed`.
2. If BIOMERO.importer preprocessing already converted the source into Zarr under
   the source directory's `.processed` folder, promote that output as the
   canonical Zarr; do not export another one.
3. If only a non-Zarr OMERO Pixels source exists, Image Transfer performs the
   first OME-Zarr export and atomically promotes the completed export into the
   importer-owned `.processed` area. Later workflows reuse it.

Use an OMERO-identity-based name for a newly promoted conversion rather than the
display filename alone, for example:

```text
<source-directory>/.processed/
  Image-<omero-id>.g<source-generation>.ome.zarr/
  Plate-<omero-id>.g<source-generation>.ome.zarr/
```

If the OMERO object has no managed source-directory locator, use the configured
group import root's `.processed` directory. The group storage mapping—not the
workflow UUID—selects the destination.

An existing importer-produced Zarr does not need to be renamed merely to match
this convention. Its source record points at the committed path.

Attach a namespaced canonical-source record to the OMERO Image or Plate containing
the managed root locator, optional nested image path, source generation,
interchange profile, and intensity identity. A root locator alone is insufficient
for a multi-series `bioformats2raw.layout = 3` store because several OMERO Images
may address different nodes within the same Zarr.

This record is the derived-Zarr counterpart of `Imported_from`, not a replacement
for it. For example, an Image imported from `sample.lif` keeps
`Imported_from=sample.lif` and gains a separate `biomero.zarr.source` record that
points to its reusable canonical representation. Attach the record to the
original OMERO Image or Plate, not only to masks produced from it. Each Image
created from a multi-series source has its own record; records may share one
physical Zarr root while using different `nodePath` values.

This extends an existing seam:

- BIOMERO.importer already writes preprocessing results into `.processed`;
- it currently annotates imported objects with `Filepath` and `Imported_from`;
- `_SLURM_Image_Transfer.py` already copies an existing local `.zarr` found in
  either annotation instead of running another export.

Refactor that lookup to use deterministic precedence:

1. namespaced canonical-source record;
2. registered Zarr `ExternalInfo.lsid` when it resolves to authorized managed
   storage;
3. legacy `Imported_from`;
4. legacy `Filepath`;
5. export once and promote into `.processed`.

Do not retain the current dependence on MapAnnotation iteration order. Validate
that the resolved path is beneath an allowed group storage root, exists, is a
supported Zarr, and matches the recorded OMERO object/node before reuse.

### Canonical-source record and task snapshot

The first implementation does not need a new relational catalog table. Store a
namespaced record on the OMERO Image or Plate, for example:

```text
namespace = biomero.zarr.source
schema = 1
storageRoot = group-5-data
relativePath = project/.processed/Image-3207.g1.ome.zarr
nodePath = . | 0 | A/1/0 | ...
sourceObjectType = Image | Plate
sourceObjectId = 3207
sourceGeneration = 1
interchangeProfile = ngff-0.4-zarr-v2
pixelIdentity = <JSON-encoded biomero_schema.zarr.PixelIdentity>
pixelIdentityOrigin = raw | omero-pixels | canonical-bootstrap
canonicalPixelVerified = true
storeIdentity = ISCC:...
```

The embedded `PixelIdentity` contains the ISCC-BIO method and code, tool and
IMAGEWALK versions, node path, role, shape, axes, dtype, and coordinate
transformations. The optional `storeIdentity` is an ISCC-SUM identifier for the
physical tree; its method is intentionally not conflated with pixel identity.

Use a configured storage-root ID plus relative path instead of assuming every
service has the same absolute mount prefix. For an existing registered Zarr,
derive the initial root/node locator from its trusted `ExternalInfo.lsid` and
then persist the normalized record.

Deployments expose those logical IDs in the shared `biomero-config.json`, which
is mounted into the worker and importer. For example:

```json
{
  "storage_roots": {
    "group-3-data": "/data/Project A"
  }
}
```

The absolute value is a container-visible managed root, while only the logical
ID and a validated relative path enter the portable contract. Missing mappings,
paths outside the configured root, unavailable directories, and ambiguous
records are never guessed from display names or annotation iteration order.

Image Transfer resolves this record from the selected OMERO object. The record
indexes a stable Zarr that already exists; it does not require a duplicate
"canonical copy." If resolution falls
back to `ExternalInfo`, `Imported_from`, or `Filepath`, it validates the candidate,
computes the missing identity, and writes the source-catalog record so the next
lookup is direct. A native or previously registered Zarr is adopted in place.
Only a non-Zarr source that must be converted gains a reusable `.processed` Zarr
representation.

Import Results has a different requirement: it must know the exact source
generation used by that workflow, not merely whatever record is current later.
At export, snapshot the resolved source records in a new workflow-scoped event in
the existing event-sourced tracking model, `CanonicalInputsRecorded`, containing
the export task ID, workflow UUID, input ordinal, selected OMERO object, and
source generation. Do not duplicate that snapshot in a task-root `.biomero`
directory or beside permanent results.

`SLURM_Run_Workflow.py` already gives Import Results the workflow UUID and
completed Slurm job ID. Import Results uses those values to load the immutable
input snapshot and match returned inputs by ordinal/transfer ID. The snapshot is
a fast, lineage-rich candidate list, not a prerequisite for deduplication. For
old events, disabled tracking, or incomplete snapshots, Import Results compares
the returned intensity identity with the ISCC-indexed source catalog. Any exact,
semantically compatible match may back a shallow copy. It
must not depend on the export task ID being threaded through the current local
`task_id` variable, which is subsequently reused for conversion and workflow
tasks. The snapshot is used for comparison and RFC-8 source rebasing.

Adding the canonical defaults did not change the serialized
`WorkflowInitiated` event fields, so existing event streams replay through the
current initializer and receive empty defaults; no upcaster is required for this
change. Accessors also default missing aggregate attributes for defensive
compatibility. Introduce a `class_version` upcaster when a persisted event's
schema actually changes, rather than inventing one for derived aggregate state.

`biomero_task_execution` and the other analytics views do not need new columns
for v1. Add a queryable canonical-source table later only if operators need
cross-object inventory, migration, or repair queries that are inefficient via
OMERO annotations. Such a table would be a projection/cache of the OMERO record,
not a second authority.

Use the deterministic object/generation path plus an atomic creation lock only
when a non-Zarr source needs a derived `.processed` representation, so two
simultaneous first exports converge on one committed cache.

### First and repeated export of a non-Zarr original

For an OMERO Image whose original file is a LIF (or another non-Zarr format), the
end-to-end lifecycle is:

1. Image Transfer reads `biomero.zarr.source` from the selected original Image.
   `Imported_from` continues to identify the LIF and is not expected to identify
   the derived Zarr.
2. If the canonical record resolves and validates, Image Transfer snapshots it
   for the workflow and reuses that Zarr.
3. If no record exists, Image Transfer derives the one allowed destination from
   storage-root ID, OMERO object ID, and source generation, then acquires the
   creation lock. It checks that exact destination for a committed canonical
   marker before exporting; it does not scan `.processed` or guess by display
   filename.
4. If the exact destination already contains a valid, committed Zarr for this
   OMERO object/generation, Image Transfer adopts it and repairs the missing
   OMERO record. This covers a prior crash after atomic promotion but before
   annotation, as well as a controlled migration of existing conversions.
5. Otherwise, Image Transfer exports to staging, validates the supported
   interchange profile, and computes the canonical Zarr's ISCC-BIO pixel
   identity. If the original Image already has a raw/OMERO pixel identity, the
   export must match it before promotion. A mismatch is a conversion or scene-
   mapping failure and must not silently establish a new identity. After a match,
   Image Transfer atomically promotes the Zarr into `.processed` and attaches the
   `biomero.zarr.source` record to the original OMERO object.
6. Image Transfer snapshots the exact source record in workflow tracking, then
   copies/materializes a writable task-local Zarr for Slurm. The workflow never
   writes into the indexed source or `.processed` conversion cache.
7. On return, Import Results first compares against the workflow snapshot and
   then falls back to an exact ISCC lookup across indexed stable Zarr sources.
   It does not infer equality from the LIF filename or from the newly created
   mask object.
8. On a later analysis of the same original OMERO Image, step 1 finds the record
   and step 2 reuses the canonical Zarr without invoking the exporter.

The committed marker or sidecar at the deterministic destination contains at
least the OMERO object type/ID, source generation, node path, interchange
profile, and intensity identity. It is the filesystem recovery witness; the OMERO
record remains the normal lookup mechanism.

Result mask Images receive provenance back to the selected original plus their
collection/label locator. They do not become the authority for discovering the
original's canonical conversion. When a mask is selected for a later workflow,
its collection manifest and task provenance lead back to the snapshotted
canonical source; when the original is selected, only its own canonical source is
sent, without merging unrelated masks.

## Result handling: three lanes

### 1. Generic full OME-Zarr result

This is the default and most important lane. A ported ImageJ, CellProfiler,
Fractal, or other Zarr-to-Zarr workflow receives a normal writable OME-Zarr. It
may copy that store, modify it in place, and add labels. It has no BIOMERO
metadata obligations.

On retrieval, BIOMERO uses task provenance to identify the exact canonical input
and compares the returned image/intensity nodes with the cached source identity.

- Matching intensity nodes are duplicate output data and are omitted from the
  durable result.
- Different intensity nodes are real derived images and are retained.
- Unverifiable nodes are retained.
- Labels and other derived nodes are retained and linked to the image node they
  describe.

The common case—an unchanged copied image plus new `labels`—therefore becomes a
shallow collection without any workflow-specific behavior.

### 2. Optional BIOMERO hint

BIOMERO may add an input hint after export because it controls the transfer Zarr.
The hint helps correlate a copied result with its task input, but merely copying
the input hint is not a claim that pixels remained unchanged.

Illustrative input root attribute:

```json
{
  "biomero:transfer": {
    "schema": 1,
    "inputId": "task-input-0",
    "sourceGeneration": 1,
    "intensityIdentity": {
      "method": "iscc-bio/imagewalk",
      "manifest": [
        {"nodePath": ".", "role": "image", "iscc": "ISCC:..."}
      ]
    }
  }
}
```

A BIOMERO-owned adapter or cooperative workflow may actively add a separate
result attribute:

```json
{
  "biomero:result": {
    "schema": 1,
    "inputId": "task-input-0",
    "pixelRelation": "unchanged"
  }
}
```

`biomero:result` is never present in the exported input, so a generic recursive
copy cannot accidentally create it. A valid task-bound `unchanged` hint lets
BIOMERO skip returned-intensity comparison. `changed` or an absent/invalid hint
uses the generic lane.

This hint is optional BIOMERO orchestration metadata. It is not part of
BILAYERS, OME-Zarr, or RFC-8 and must never be required for workflow portability.

### 3. Native RFC-8 shallow result

A workflow may eventually return an RFC-8 collection directly. Its source path
will often point relatively to the task-local input. BIOMERO uses task provenance
to map that source node to the canonical source Zarr and writes the managed
locator into its durable collection representation.

BIOMERO rebases a source only when it maps unambiguously to an input supplied for
that task and has compatible Image or Plate structure. It does not rewrite an
arbitrary external URL or unrelated source. An unresolved collection is retained
and reported rather than silently redirected.

This is a standards-oriented fast path, separate from splitting a returned full
Zarr.

## Source identity

The original image scene's ISCC-BIO identity is the authority for pixel identity;
the canonical Zarr is a verified reusable representation and transfer cache. Do
not make the canonical path or its stored bytes the definition of the original
image.

Compute and store the source identity as early as BIOMERO has decoded access to a
new image:

- When importing a raw LIF, CZI, ND2, OME-TIFF, or similar file, calculate one
  ISCC-BIO identity per scene and associate each scene with the OMERO Image
  created from it.
- When the importer cannot safely read the raw format directly, calculate the
  identity from the resulting OMERO Pixels and record
  `pixelIdentityOrigin=omero-pixels`.
- For an existing native Zarr, its image node is both the original and canonical
  representation; calculate the identity directly from that node.
- For legacy OMERO objects without an identity, bootstrap once from OMERO Pixels
  or a validated canonical Zarr and record which representation was used.

When BIOMERO first creates or registers a canonical source Zarr:

- Calculate its per-image/scene ISCC-BIO identity and compare it with the stored
  original identity.
- Mark `canonicalPixelVerified=true` only when the exact Instance-Code matches
  and the dimensional/NGFF semantic guard is compatible.
- Refuse automatic canonical promotion on mismatch and report the raw scene,
  OMERO Image, and candidate Zarr node involved.
- Cache it against `(server, group, object type, object ID, source generation)`.
- Recompute only for a deliberate new source generation or integrity repair.

Later workflow comparisons first use the original identity and source generation
snapshotted at export. If that event is absent, legacy, disabled, or incomplete,
they use the returned image identity to query all indexed/referenceable Zarr
sources for an exact compatible match. They do not need to reread the LIF or
other raw file. The snapshot also records the verified source generation/path so
Image Transfer can materialize the matching pixels without searching.

The identity is scoped to image intensity arrays and semantic image metadata,
not the whole mutable Zarr directory. Labels, BIOMERO hints, workflow metadata,
and provenance files are excluded. Adding a label must not change the source
image identity.

For Plates, store identities at image/field level and derive well and plate
aggregate identities. This permits one changed field to be retained without
duplicating every unchanged field.

### ISCC-BIO pixel comparison and ISCC-SUM store identity

Use `iscc-bio`/IMAGEWALK as the primary pixel-identity and deduplication engine
rather than implementing BIOMERO's own Zarr-array hashing. IMAGEWALK reads the
decoded highest-resolution pixels in deterministic Z->C->T plane order and
canonical byte order. Its important property here is format and storage
independence: the same pixels can retain one identity across LIF, OMERO Pixels,
OME-TIFF, and OME-Zarr, and across Zarr rechunking or recompression.

Use `iscc-sum --tree` separately for exact stored-object identity, transfer
integrity, citation, and a cheap fast path when canonical and returned Zarr
storage are byte-identical. A whole-Zarr ISCC-SUM changes when labels or metadata
are added, so it must not be the sole source-pixel deduplication decision.

For every canonical source and returned result:

1. Parse the supported NGFF structure and identify each image/field node and each
   label node by its actual path and role.
2. Invoke `iscc-bio` on each node independently. For a label this can be the
   directly addressable `labels/<name>` image group. Never depend on an
   unlabelled result-list position to distinguish source images from labels.
3. Store the node path, role, scene/field locator, dimensions, dtype, axes,
   coordinate transformations, ISCC, Data-Code, Instance-Code, IMAGEWALK
   revision, and pinned tool version in a small identity manifest.
4. Declare source pixels unchanged only when the corresponding image nodes have
   equal exact Instance-Codes and compatible dimensional/NGFF semantics. Labels
   receive their own identities but do not affect the source image code.

Similarity-oriented Data-Codes and per-plane simprints are useful for duplicate
discovery and investigation, but similarity alone must not cause BIOMERO to omit
returned data. If `iscc-bio` is unavailable, fails, or cannot unambiguously map a
layout, retain the returned intensity image.

Pin the `iscc-bio` version and IMAGEWALK revision because the current project is
explicitly pre-1.0. Do not compare identities made by incompatible revisions
until an upstream compatibility statement or BIOMERO migration establishes that
they use the same canonical pixel stream.

#### Upstream-first NGFF work

The present `iscc-bio` implementation is a strong foundation, but BIOMERO needs
several capabilities made explicit before relying on it for automatic pruning:

- a public API that targets a specific NGFF node path and returns that path,
  node role (`image` or `label`), and scene/field locator with every code;
- stable traversal and locators for NGFF Plates, wells, fields, and per-field
  labels;
- tests proving that adding a label does not alter the source image code, while
  every label can be coded separately;
- cross-reader fixtures proving equal codes for the same scene through LIF or
  OME-TIFF, canonical OME-Zarr, and OMERO;
- conformance tests for bioformats2raw multi-series stores, ordinary image-plus-
  labels stores, and Plates; and
- bounded tile/chunk streaming for XY planes that are too large to materialize
  safely as one NumPy array.

Prefer issues and Apache-2.0 contributions to `iscc-bio` for this generally useful
functionality. A temporary BIOMERO adapter may select the exact node and attach
the missing locator metadata, but it must call the upstream IMAGEWALK/ISCC code
and must not fork the canonicalization or hashing algorithm.

IMAGEWALK currently identifies pixel bytes, not the complete scientific meaning
of an NGFF image. Until canonical metadata is part of the specification, BIOMERO
must still compare shape, dtype, axes, and coordinate transformations alongside
the code. This is a small semantic guard, not another checksum scheme.

Hash returned data while it is already being copied from workflow storage where
possible. The immutable source identity is cached, so ordinary comparisons read
only the returned intensity data.

An encoding change, rechunking, recompression, or pyramid regeneration may change
the ISCC-SUM store identity while leaving the ISCC-BIO pixel identity unchanged.
That result can still be normalized shallowly when the semantic guard also
matches. A changed lower-resolution pyramid with unchanged highest-resolution
pixels is treated as a regenerated cache; BIOMERO reconstruction uses the
canonical source pyramid.

## Normalize: returned result to durable collection

`SLURM_Import_Results.py` knows the workflow UUID, task, job, selected inputs,
and result mapping. It selects the result lane and creates a typed normalization
order. BIOMERO.importer performs the filesystem transaction beneath `.processed`
before registering anything in OMERO.

For a generic full result:

1. Resolve the exact canonical source from task provenance.
2. Inspect the returned Image or Plate Zarr and enumerate intensity and label
   nodes using released NGFF metadata, not filename globbing.
3. Calculate returned intensity identities and compare them with the cached
   source identities.
4. Plan omitted duplicate nodes, retained changed/unknown image nodes, retained
   labels, and each label's actual source image node.
5. Write a temporary RFC-8-shaped `biomero.collection.json` plus retained nodes.
6. Create an OMERO projection order for every retained label layer.
7. Validate the candidate and atomically commit it under `.processed`.
8. Register every projection in OMERO and attach collection/source provenance.
9. Mark ingestion committed before applying result retention.

For the optional-hint lane, steps 3–4 use the valid task-bound hint for covered
nodes. For native RFC-8, they validate and rebase the existing graph instead.

On failure, retain/import the full result. Never mutate the returned result in
place while normalization is incomplete.

## Durable representation

Store a small standalone manifest that mirrors RFC-8 Node, Collection, Path,
Reference, Multiscale, and label-source concepts without claiming conformance to
an unfinished standard:

```text
<result-id>.collection/
  biomero.collection.json
  derived/
    cells/                 # retained label multiscale
    nuclei/                # retained label multiscale
    corrected-image/       # only if returned pixels changed
  audit/
    normalization.json
```

The graph references the canonical source directly. A collection never points to
another shallow result as its source. Paths are managed locators; the BIOMERO
source catalog remains authoritative if storage is moved.

For Plates, preserve the released HCS well/field structure needed to locate each
retained label. Do not create black field arrays or infer fields by display name
or traversal order.

## OMERO projections

The current OMERO Zarr PixelBuffer does not need to understand RFC-8.

- Register every image label multiscale as an ordinary OMERO Image whose pixel
  path points directly to that retained label node.
- Register every plate label layer as a separate OMERO Plate projection whose
  WellSample Images point to the corresponding per-field label nodes.
- Multiple masks produce multiple OMERO result objects, matching existing TIFF
  workflow behavior.
- Give all projections the same collection ID and distinct node IDs.
- Designate one real label projection as the collection representative; do not
  create a black anchor image.

OMERO.biomero can later group these projections into one card and show the mask
thumbnail. The standard viewers continue to display the mask pixels they can
already read.

## Materialize: stored collection to workflow input

Materialization belongs in `_SLURM_Image_Transfer.py`, after an OMERO selection
has been resolved and before workflow transfer.

When a user selects a collection projection:

1. Resolve and authorize its collection and canonical source through trusted
   server-side metadata.
2. Create a workflow-scoped temporary Zarr.
3. Copy or safely clone the canonical source as the base.
4. Overlay retained changed image nodes at their declared locations.
5. Insert all labels from that collection under conventional `labels/<name>`
   locations, including the correct HCS field locations for Plates.
6. Rebuild released-version label listings and relative label source metadata.
7. Validate with the reader expected by the workflow.
8. Transfer the conventional, self-contained OME-Zarr and clean up the temporary
   materialization afterward.

Selecting the original Image or Plate transfers only the original. It never
implicitly gathers Cellpose, StarDist, or other result collections.

Physical materialization is the baseline. Reflinks, symlinks, virtual chunks, or
direct shallow transfer remain optional optimizations behind capability checks
and a physical-copy fallback.

## Retention

```text
BIOMERO_ZARR_RESULT_RETENTION=keep|quarantine|prune
```

- `keep`: create the shallow collection but retain the full workflow result.
- `quarantine`: retain the full result for a configured recovery period.
- `prune`: remove only result data represented by a committed collection or
  identified as duplicate source data.

Start in `keep`, exercise reconstruction, then move through `quarantine` before
enabling `prune`. Logs, tables, models, and unrelated workflow outputs are never
part of this cleanup.

## Repository responsibilities

### biomero-schema

- Own the versioned Pydantic wire contracts shared between BIOMERO services:
  canonical Zarr sources, per-node pixel identities, and canonical workflow
  input snapshots.
- Keep these contracts in `biomero_schema.zarr`, separate from workflow
  descriptors in `biomero_schema.models`; their schema versions evolve
  independently.
- Export JSON Schema for non-Python consumers without redefining OME-NGFF or
  RFC-8 metadata.
- Contain validation and serialization only. Storage, OMERO access, event
  sourcing, normalization, and materialization remain service behavior.

### biomero

- Re-export the shared source contracts for compatibility and own source catalog
  behavior, including deterministic legacy-locator resolution.
- Add `CanonicalInputsRecorded` to the event-sourced WorkflowRun aggregate
  without expanding the task analytics table.
- ISCC-BIO node identity manifests and exact-comparison models, plus optional
  ISCC-SUM store identities; no BIOMERO hashing implementation.
- RFC-8-shaped collection, node, path, reference, and rebase models.
- Pure normalization and materialization planning.
- Safe path and managed-locator validation.

### biomero-scripts

- `_SLURM_Image_Transfer.py`: resolve and index existing imported/native Zarrs in
  place with explicit precedence; export and promote once into importer-owned
  `.processed` only for non-Zarr sources; calculate and record source identities;
  optionally add the input hint; persist the task source snapshot in workflow
  events; materialize shallow selections before transfer.
- `SLURM_Import_Results.py`: resolve task lineage; detect generic, hinted, or
  native RFC-8 results; load the exact canonical-input snapshot; create typed
  importer orders; gate retention after commit.
- Keep BILAYERS-facing workflow I/O conventional and independent of BIOMERO
  storage metadata.

### BIOMERO.importer

- Calculate and attach per-scene ISCC-BIO identities while it has access to newly
  ingested raw files, preserving the raw scene-to-OMERO Image mapping; fall back
  explicitly to OMERO Pixels when a raw reader is unavailable.
- Index stable imported/native Zarrs in place. Own committed conversion caches
  beneath source/group `.processed` only when the source was not already Zarr,
  and attach the namespaced root/node/generation/identity record to every
  resulting OMERO Image or Plate.
- Transactionally normalize results under `.processed` before OMERO
  registration.
- Calculate returned identities during retrieval/copy when possible.
- Retain changed/unknown image nodes and all supported labels.
- Register every label-backed Image or Plate projection without requiring a
  `.zarr` suffix on nested groups.
- Return and annotate every created OMERO object before committing ingestion.

### OMERO.biomero

- Discover collection membership from trusted server-side metadata.
- Group multiple label projections without changing submitted OMERO IDs.
- Show read-only source/label inventory and ordinary mask thumbnails.
- Leave materialization to Image Transfer.

### NL-BIOMERO

- Wire source catalog and identical `.processed`/shared-storage mappings across
  importer, OMERO.server, OMERO.web, and script workers.
- Pin and configure `iscc-bio`/IMAGEWALK and `iscc-sum`, plus comparison
  concurrency, temporary capacity, retention, and quarantine.
- Publish the short workflow-provider guidance alongside the BILAYERS migration
  blog; do not present BIOMERO hints as part of BILAYERS or OME-Zarr.

## Delivery order

### Phase 1: contract and fixtures

1. Freeze the source catalog key, ISCC-BIO node-identity manifest, optional
   ISCC-SUM store identity, internal collection manifest, optional hint, OMERO
   annotation keys, and advertised `ngff-0.4-zarr-v2` interchange capability.
2. Create fixtures for an unchanged image plus labels, changed pixels plus
   labels, multiple masks, a raw multi-scene file and its canonical Zarr, a
   non-Zarr canonical export mismatch, native RFC-8, and one Plate.
3. Benchmark pinned ISCC-BIO over representative 5D images and Plates, and
   ISCC-SUM as the exact-store fast path. Measure IO, decompression, memory, and
   comparison while result data is being copied.

### Phase 2: source and reader first

1. Add the canonical root/node/generation annotation and deterministic resolver,
   retaining `Imported_from` and `Filepath` as ordered legacy fallbacks.
2. Add the workflow-scoped `CanonicalInputsRecorded` event, keyed by workflow
   UUID and input ordinal. Keep older event streams valid with empty defaults;
   do not add a Slurm-side recovery manifest.
3. Index and reuse existing registered, native, or importer-produced Zarrs in
   place without copying them.
4. Promote a first non-Zarr export into source/group `.processed` and cache its
   identity; attach the source-catalog record to the selected original OMERO object
   without changing its `Imported_from` value.
5. Implement collection parsing and physical materialization in Image Transfer.
6. Exercise manually created shallow fixtures through an unchanged generic
   Zarr-to-Zarr workflow.

### Phase 3: image normalization in keep mode

1. Pass exact task lineage to importer orders.
2. Implement generic returned-intensity comparison.
3. Write image shallow collections and import every label projection.
4. Add native RFC-8 rebasing.
5. Add the optional hint shortcut only after the generic path works.
6. Keep full results and compare reconstructed transfers with them.

### Phase 4: Analyzer presentation and retention

1. Group projections and show mask thumbnails/inventory.
2. Enable quarantine for selected groups and test recovery.
3. Enable prune only after explicit operator sign-off.

### Phase 5: Plates

1. Add field/well/plate identities and result comparisons.
2. Normalize labels at their declared field locations.
3. Import one label-backed Plate projection per label layer.
4. Reconstruct and run a representative large Plate through another workflow.

## Acceptance criteria

- Default workflow export produces NGFF 0.4/Zarr v2 and records that profile in
  task provenance.
- Every node registered for OMERO display is readable by the deployed
  PixelBuffer; unsupported newer stores are preserved and reported rather than
  normalized into an unusable collection.
- An unmodified FAIR workflow can copy an input Zarr, add labels, and return it;
  BIOMERO stores the labels without another source intensity pyramid.
- A workflow that changes image pixels has that returned image retained.
- Exact source deduplication uses pinned ISCC-BIO/IMAGEWALK Instance-Codes for
  explicitly located image nodes plus the NGFF semantic guard; BIOMERO does not
  implement its own pixel hash.
- Adding, changing, or removing a label does not change the source image's pixel
  identity, and every label image can receive its own node identity.
- Whole-Zarr ISCC-SUM or similar ISCC matches are never used by themselves to
  omit a returned intensity image.
- A missing hint never prevents generic workflow execution or result import.
- A copied input hint alone never skips comparison.
- A valid actively written result hint can skip comparison for covered nodes.
- A native RFC-8 source pointing to the task-local input is safely rebased to the
  canonical managed source.
- Canonical sources cannot be modified by workflow workers.
- An existing managed or importer-produced Zarr is reused without another
  export; a non-Zarr source is exported and promoted into `.processed` only once.
- A new raw-file import records one authoritative ISCC-BIO identity per scene;
  its canonical Zarr is promoted only after producing the same pixel identity.
- A returned workflow image is compared with the immutable original-scene
  identity captured in the workflow snapshot, without rereading the raw file.
- A LIF-backed Image retains `Imported_from=<lif>` while its first Zarr export
  adds `biomero.zarr.source` to that same original Image; selecting it again
  reuses the committed Zarr.
- If atomic promotion succeeds but OMERO annotation fails, the next export adopts
  the valid deterministic destination and repairs the annotation rather than
  exporting again.
- Canonical lookup is independent of MapAnnotation iteration order and records a
  nested node path for multi-series roots.
- Import Results uses the immutable task snapshot rather than re-resolving a
  possibly newer source generation.
- Two simultaneous first exports commit or reuse one canonical Zarr.
- Every mask is visible as its own OMERO result Image or Plate.
- Selecting a result reconstructs a conventional full OME-Zarr with its source
  pixels and labels before transfer.
- Selecting the original does not merge unrelated result collections.
- A failed normalization retains the full result.
- Retention never runs before collection, OMERO import, and provenance commit.
