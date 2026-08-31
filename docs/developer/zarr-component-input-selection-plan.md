# BIOMERO shallow OME-Zarr result plan

## Decision

BIOMERO will reduce duplicate workflow-result pixels by storing eligible
Zarr-to-Zarr results as RFC-8-shaped shallow collections containing the result
labels and a reference to their source image.

When explicitly enabled, BIOMERO keeps one canonical Zarr representation for a
non-Zarr OMERO source after Image Transfer has already paid the conversion
cost. This is a deliberate one-time storage cost that makes later workflows
faster and provides the stable Zarr source needed by shallow collections.
Native, registered, importer-produced, and returned Zarrs are indexed and
adopted in place instead of copied into another canonical store.

Image Transfer records the exact canonical source and identity sent to the
workflow. Import Results compares the returned image node with that
workflow-scoped snapshot. When they match, BIOMERO may omit the returned copy
of the source pixels and retain the labels. When they differ or cannot be
compared safely, BIOMERO keeps the complete result.

## Non-negotiable boundaries

- This is an importer-enabled, in-place-storage optimization controlled by
  `BIOMERO_SHALLOW_ZARR`.
- `IMPORTER_ENABLED=false` continues to use `SLURM_Get_Results.py` and the
  standard OMERO pixel-upload path unchanged.
- The feature flag defaults to false. Importer-enabled deployments therefore
  keep their prior result behavior unless they explicitly opt in.
- Native or already registered Zarr sources are reused in place. They are
  indexed and identified, not copied into a new canonical location.
- A non-Zarr OMERO source is exported once and promoted into importer-managed
  `.processed` storage only when both feature gates are enabled.
- Unknown, ambiguous, unsupported, or changed pixels are retained. The
  optimization may save less storage but must not lose a workflow result.
- Workflows remain ordinary BILAYERS/FAIR workflows. They do not need to read
  BIOMERO metadata or implement a BIOMERO-only output contract.
- BIOMERO metadata may provide an optional fast-path hint, but the generic
  returned-pixel comparison remains authoritative.
- Original image data is treated as read-only.

## Existing deployment split

`SLURM_Run_Workflow.py` already owns the capability split:

```text
IMPORTER_ENABLED=true   -> SLURM_Import_Results.py
IMPORTER_ENABLED=false  -> SLURM_Get_Results.py
```

All shallow-storage behavior must follow that split.

The independent feature gate is:

```text
effective shallow storage =
    IMPORTER_ENABLED && BIOMERO_SHALLOW_ZARR
```

On an importer-disabled deployment:

- Image Transfer performs its established export and SLURM transfer;
- it must not import `biomero_importer`, resolve importer storage, create
  shallow-storage metadata, or require group mappings;
- Run Workflow does not persist a shallow-comparison input snapshot;
- Get Results downloads and uploads results through the existing non-in-place
  route.

The ability to request an OME-Zarr transfer must not accidentally make
BIOMERO.importer mandatory.

When the importer exists but `BIOMERO_SHALLOW_ZARR=false`, Import
Results continues to provide in-place importing, but canonical promotion,
input snapshots, returned-image comparison, and shallow normalization are
disabled. This is the backward-compatible importer route.

## Importer lifecycle boundary

Shallow-result handling is a native, opt-in importer lifecycle operation. It
is not part of `register.py` and it is not encoded as an
`imports_preprocessing` container. The existing preprocessing table describes
one external converter invocation and must keep doing so unchanged.

An import order may carry a versioned `ImportOptionsEnvelope` in the existing
nullable `imports.import_options` JSON text field. The envelope contains:

- registration options for the eventual OMERO import;
- an ordered tuple of typed lifecycle operations; and
- schema/version discriminators so an importer can validate capability before
  touching data.

The first native operation is `biomero.shallow-zarr`. Its request contains the
exact workflow-scoped `CanonicalInputManifest`, safe failure policy, and
automatic result-view controls. The identity worker count is deployment
configuration owned by the importer service, not a client-controlled field.
Future operation kinds can cover storage relocation, integrity verification,
or deduplication without changing the OMERO registration implementation.

The execution order is:

```text
import order
  -> optional legacy external/container preprocessing
  -> native lifecycle operations (post-conversion, pre-import)
  -> importer-owned registration plan
  -> current register.py / future omero CLI implementation
```

This lets direct Zarr imports and converter-produced Zarrs use the same native
operation. `SLURM_Import_Results.py`, OMERO.biomero, or another uploader can
submit the same typed request through a public BIOMERO.importer order API;
none needs to call the shallow implementation directly.

Compatibility rules are strict:

- missing/empty options and legacy flat schema-1 `ZarrImportOptions` upcast to
  an envelope with no lifecycle operations;
- no operation means the current importer path byte-for-byte in behavior;
- `BIOMERO_SHALLOW_ZARR=false` means BIOMERO scripts do not enqueue the
  operation;
- an importer that does not advertise the operation must not receive such an
  order; the script falls back to the existing full import;
- unsupported operation kinds or invalid payloads fail before mutation with a
  clear order status; and
- the shallow operation itself is fail-safe and idempotent: uncertain
  comparison keeps the full result, while a valid existing shallow manifest is
  reused on retry.

Operation-level status can initially use the existing append-only import
stages and descriptions. If multiple independently retryable operations later
need their own audit trail, add an `imports_operations` table by migration;
the wire request and engine API do not need to change.

## Runtime configuration ownership

The authoritative group-to-storage mapping is:

1. `group-mappings.json`; or
2. the legacy `biomero-config.json["group_mappings"]` fallback.

The dedicated file wins when both contain the same group ID. There is no
`storage_roots` section in `slurm-config.ini` and no second mapping to keep in
sync.

`IMPORT_MOUNT_PATH` is the container mount root. Import Results combines it
with the mapped `folder` when it places workflow results under:

```text
<IMPORT_MOUNT_PATH>/<group folder>/.analyzed/<workflow UUID>/<timestamp>/
```

Image Transfer reads the same mapping only when effective shallow storage is
enabled and it must promote a non-Zarr export under that group's `.processed`
area. It must not read a separate `storage_roots` configuration.

The `biomeroworker` container runs Image Transfer and Import Results. It still
needs shared mappings for result placement and canonical export. The
BIOMERO.importer service independently needs the same read-only mappings and
the same `/data` view to resolve managed references during lifecycle
operations. Do not pass absolute trusted storage paths from web requests.

OMERO's processor does not automatically pass container environment variables
to downloaded script subprocesses. Every required variable must also be in the
explicit allowlist in `biomeroworker/processor.py`. In particular:

- `IMPORTER_ENABLED`;
- `BIOMERO_SHALLOW_ZARR` (forwarded dynamically through
  `biomero.constants.slurm_env`);
- `IMPORT_MOUNT_PATH`;
- `OMERO_BIOMERO_CONFIG_FILE`;
- `OMERO_BIOMERO_GROUP_MAPPINGS_FILE`.

Changing that allowlist requires rebuilding/recreating `biomeroworker`.
`BIOMERO_SHALLOW_ZARR_WORKERS` belongs only to the BIOMERO.importer service;
it defaults to `1` and is not forwarded into OMERO script subprocesses.

## Data identities

Use `iscc-bio`/IMAGEWALK for the pixel identity of an image node. Its useful
property is format-independent identity: the same logical image pixels can
produce the same identity when read from a raw microscopy file, OMERO Pixels,
or OME-Zarr. IMAGEWALK operates on decoded, canonicalized two-dimensional
planes in Z→C→T order and is independent of chunk layout, codecs, metadata,
additional pyramid levels, and separately stored labels. It is therefore the
identity used to answer whether workflow-returned source pixels changed. See
[IEP-0018](https://ieps.iscc.codes/iep-0018/).

Record semantic guards with each identity:

- node path and role (`image` or `label`);
- shape, axes, and dtype;
- coordinate transformations relevant to interpreting the node;
- ISCC, Data-Code, and Instance-Code;
- tool version and IMAGEWALK revision.

Use `iscc-sum`/TREEWALK-ISCC only as an optional store/archive identity for
transfer integrity, fast exact-fileset checks, and operational deduplication.
It changes when a store is rechunked, recompressed, gains labels, or receives
metadata changes, so it is not an image-pixel equality check. Do not create a
BIOMERO-specific checksum implementation.

If BIOMERO later persists a whole-store code, use `<store>/.iscc.json`.
TREEWALK-ISCC always excludes files ending in `.iscc.json`, including in
directory, archive, and object-store traversal, avoiding a circular store sum.
`.isccignore` may additionally exclude operational paths. This whole-store
sidecar is optional and outside the synchronous shallow-eligibility path. See
[IEP-0017](https://ieps.iscc.codes/iep-0017/).

Pixel equality is based on the pixel identity plus semantic guards, not on a
copied directory path. Store identity alone is insufficient because adding
labels or metadata legitimately changes the Zarr tree.

### Portable embedded Image identity (planned interoperability step)

This is the desired direction, not a prerequisite or guaranteed property of
the current schema-1 implementation. Current services persist the same
identity records in managed sidecars and workflow provenance and recompute
returned pixels. Readers must continue to work when no group-level `iscc`
attribute exists.

Whenever BIOMERO calculates or reuses an IMAGEWALK identity for a writable
BIOMERO-produced Zarr, publish a compact ISCC metadata object in the user
attributes of the concrete NGFF Image group:

```json
{
  "iscc": {
    "iscc": "ISCC:..."
  }
}
```

This applies to an ordinary Image root, every HCS field such as `A/1/0`, and
each label Image group for which BIOMERO calculates a label identity. Write it
through the Zarr group-attributes API, not by targeting a metadata filename:

- OME-NGFF 0.4/Zarr v2 serializes it as top-level `iscc` in the Image group's
  `.zattrs`, beside `multiscales`, `omero`, and other group attributes;
- Zarr v3 serializes the same logical attribute as `attributes.iscc` in the
  Image group's `zarr.json`.

Keep it outside the versioned NGFF `ome` namespace. A minimal
`{"iscc": "ISCC:..."}` value follows the lightweight embedding convention;
do not claim that it is a complete IEP-0012 JSON-LD document unless all
required IEP-0012 metadata fields are emitted. See
[IEP-0012](https://ieps.iscc.codes/iep-0012/).

An embedded identity is a portable claim and path-independent hint, not trusted
proof that the current pixels still match it. Generic workflows may copy user
attributes unchanged while modifying pixels. BIOMERO's trusted workflow input
snapshot and a freshly computed returned IMAGEWALK identity remain
authoritative for normalization. Never discard returned pixels solely because
`attrs.iscc` matches the recorded source.

## Shared contracts

Keep the cross-service Pydantic models in `biomero-schema`, separate from the
workflow descriptor schema. The target vocabulary is:

- `PixelIdentity`: identity and guards for one NGFF image or label node;
- `CanonicalZarrSource`: OMERO Image/Plate identity, managed Zarr locator,
  generation, interchange profile, and verified pixel identity;
- `CanonicalPlateSource`: one managed Plate locator plus an independently
  identified `CanonicalPlateImage` for every declared Plate image node;
- `CanonicalInput`: selected object, ordinal, and exact canonical generation
  transferred;
- `CanonicalInputManifest`: ordered inputs bound to workflow and export task;
- `.biomero-input.json`: one serialized `CanonicalInput` written only into a
  temporary transfer Zarr so a copied-and-renamed result can be rebound to its
  selected input;
- `ShallowCollection`: source and label membership plus safe materialization
  metadata.

Previously serialized workflow events must remain readable. Add explicit
upcasting/default behavior for old event payloads and do not rewrite event
history. The transfer marker is a non-authoritative copy of one existing
manifest entry, not a replacement event manifest.

## Export and input snapshot

For an importer-enabled Zarr transfer:

1. Resolve the selected OMERO Images or Plate in stable input order.
2. If a selection is an already registered native or managed Zarr, reuse and
   index that path as its canonical source. Do not duplicate it.
3. Otherwise export an OME-Zarr using the supported Glencoe/OMERO exporter
   profile, verify it against OMERO Pixels, and transactionally promote it once
   into the group's `.processed` area.
4. Calculate or reuse the ISCC-BIO identity for each canonical image node
   actually sent and for each declared label node included in the transfer.
5. Record a `CanonicalInputManifest` in the workflow event store, including the
   selected OMERO object, canonical generation, and transferred identity.
6. For every writable BIOMERO-produced Image or label group, publish its
   IMAGEWALK code as the portable group-level `iscc` user attribute. A native
   read-only Zarr is indexed without mutation; its identity remains available
   through BIOMERO's managed inventory and workflow snapshot.
7. Write `.biomero-input.json` into each writable task-local transfer Zarr. It
   contains that artifact's serialized `CanonicalInput`, never a managed path
   invented by the workflow. Do not modify the canonical source. A generic
   workflow may preserve, remove, or ignore the marker; it never replaces
   return-side verification.
8. Transfer the ordinary, fully usable Zarr to SLURM.
9. Clean up the task-local transfer copy according to existing behavior; retain
   the committed canonical source.

The snapshot describes the exact canonical generation sent to one workflow
run. The canonical locator is managed server metadata, never a task-local path.

Import Results resolves that snapshot directly by workflow UUID. It computes
returned image-node identities and compares them only with the inputs recorded
for that workflow; it does not search a global checksum catalog. A queryable
checksum index may be added later for cross-workflow deduplication, discovery,
or repair, but it is not required for the return path. Whole-store ISCC-SUM is
not an image-equality substitute because adding labels or metadata changes the
store identity while leaving the source image pixels unchanged.

Canonical promotion and identity calculation are an optimization boundary. If
they cannot complete safely, preserve the ordinary export, omit the complete
canonical-input snapshot, and retain the complete returned result rather than
blocking the workflow or guessing a shallow source.

For a Plate, record image-node identities at the known image levels in the
plate hierarchy. Do not guess labels at the plate root. Keep only one compact
`CanonicalPlateIndex` MapAnnotation on the OMERO Plate. Store the potentially
large `CanonicalPlateSource` inventory in managed storage: promoted BIOMERO
canonicals use the internal `.biomero-canonical.json` marker, while native or
otherwise read-only indexed Zarrs use the non-invasive sibling sidecar
`.biomero/<zarr-name>.canonical.json`. Never create one visible OMERO
MapAnnotation per Plate image or label. Readers must continue to accept the
earlier monolithic and split-annotation layouts for backward compatibility and
migration.

## Result normalization

`SLURM_Import_Results.py` copies results into their permanent `.analyzed`
directory, loads the exact workflow input snapshot, and submits one typed
import request. The expensive discovery, identity comparison, normalization,
and result-view planning belong to BIOMERO.importer after it dequeues the
order. Logging out of OMERO.web or timing out the polling script must not stop
those operations.

For every returned Zarr candidate:

1. Load the exact workflow input snapshot through workflow/task provenance.
2. If `.biomero-input.json` survived, validate it as an exact member of the
   authoritative workflow input snapshot. Reject invalid or foreign markers;
   when absent, retain the existing artifact-name and identity fallbacks.
3. Discover returned NGFF image and label nodes, including Plate image-level
   labels.
4. Match returned image nodes to input nodes deterministically by provenance,
   structure, and identity. Never choose an arbitrary candidate.
5. Calculate the returned image-node identity. A copied embedded `attrs.iscc`
   claim is never sufficient to skip this calculation. Any future fast path
   must be independently bound to the exact task input and validated without
   trusting mutable workflow output metadata.
6. If identity and semantic guards match, construct a shallow collection that
   retains labels and references the source OMERO object.
7. If pixels differ, no exact source is available, the mapping is ambiguous, or
   validation fails, keep the complete returned Zarr.
8. Consume the temporary transfer marker before managed registration. Move
   duplicate array directories into a sibling rollback journal, update
   metadata in place, validate the shallow collection, and only then delete the
   journal. Restore every move and metadata file on a pre-commit failure. Do
   not copy the retained label/metadata tree.
9. Build an internal importer registration plan. For an Image result, register
   every viewable label node; multiple masks produce multiple OMERO Images.
   For a Plate result, register one authoritative shallow Plate and do not
   flatten its image-level labels into a Dataset of mask Images.

This optimization removes only copied pixels from the newly returned result.
It never deletes or rewrites the original OMERO object or native Zarr.
Exact recursive byte accounting is a diagnostic option, not part of the
synchronous import path: on mounted Plate storage its directory-stat cost can
dominate the actual normalization. Operational logs report the retained label
count and successful duplicate-array omission without rescanning the tree.

### Return-path performance baseline

The A1/B1 `cisegmentation` result was benchmarked inside the Linux
BIOMERO.importer container against identical disposable copies on the real
`/data` mount. The Plate has 18 image nodes, 18 image-level labels, 1,722 files,
and occupied 146,143,912 bytes before normalization. Its shallow form occupied
10,775,929 bytes: 135,367,983 bytes (92.6%) of copied source pixels were
removed. Copy preparation was excluded because a workflow result already
exists in `.analyzed` when normalization starts.

| Measured component | Copy retained tree | Move journal + size scans | Move journal, production |
| --- | ---: | ---: | ---: |
| NGFF discovery | 1.005 s | 1.042 s | 1.088 s mean |
| Dataset planning | 0.142 s | 0.147 s | 0.154 s mean |
| Retained-tree copy / duplicate-array moves | 81.163 s | 1.235 s | 1.271 s mean |
| Attribute reads | included | 1.186 s | 1.238 s mean |
| Metadata/manifest writes | 0.467 s | 0.317 s | 0.319 s mean |
| Full-tree size before | 77.787 s | 77.004 s | skipped |
| Full-tree size after | 26.221 s | 33.624 s | skipped |
| Delete replaced/pruned tree | 9.458 s | 6.050 s | 6.449 s mean |
| Other/validation | 0.022 s | 2.241 s | 2.211 s mean |
| **Normalization total** | **196.264 s** | **122.844 s** | **12.729 s mean** |

The production result is three runs (12.666, 12.734, and 12.788 seconds).
Moving instead of copying reduced the original measured transaction by 37.4%;
removing the two diagnostic tree scans reduced it by 93.5% overall. Separate
read-only ISCC-BIO verification took 13.583, 12.590, and 11.786 seconds
(12.653 seconds mean): 7.854 seconds for 18 image identities, 3.425 seconds for
18 label identities, 0.705 seconds for discovery, and 0.670 seconds elsewhere.
The complete comparison plus production normalization therefore averages about
25.4 seconds for this fixture.

Returned image nodes are independent identity jobs, as are returned label
nodes. BIOMERO.importer therefore accepts bounded service-side concurrency via
`BIOMERO_SHALLOW_ZARR_WORKERS`. NL-BIOMERO supplies `4` as its deployment
default; the importer library retains a sequential fallback when the variable
is absent. Values greater than one use a bounded thread pool while preserving
discovered node order; every identity phase completes before any result
mutation. Invalid values fall back to the library default. Benchmark 1, 2, 4,
8, 16, and 32 workers against production-like storage before selecting a site
override; CPU count alone is not a suitable default because Zarr chunk and
filesystem-metadata I/O may saturate first.

A preliminary read-only sweep on the same 18-image/18-label result showed the
expected storage-sensitive ceiling. Three runs were collected for 1, 2, and 4
workers; higher counts received one exploratory run:

| Identity workers | Total verification times | Mean / observed |
| ---: | --- | ---: |
| 1 | 16.294, 16.929, 10.350 s | 14.524 s mean |
| 2 | 7.669, 20.565, 7.730 s | 11.988 s mean |
| 4 | 7.609, 12.487, 8.108 s | 9.401 s mean |
| 8 | 12.569 s | 12.569 s observed |
| 16 | 13.857 s | 13.857 s observed |
| 32 | 13.201 s | 13.201 s observed |

Four workers had the best mean on this development mount, but variance was
large and counts above four increased aggregate worker time through I/O
contention. This evidence supports configurability, not a global default
change: deployments remain at one worker until their own storage benchmark
justifies an override.

This is a baseline, not proof of linear scalability to a 1,000-image Plate.
Before broad rollout, benchmark representative large Plates and record image
count, label count, file/chunk count, bytes, mount/backend, identity time, move
time, deletion time, and total wall time. If synchronous unlink becomes the
dominant user-visible cost, commit the manifest after the rollback-safe moves
and queue journal deletion as recoverable background maintenance. Do not adopt
that extra lifecycle until it has crash-recovery and orphan-journal cleanup.

## RFC-8-shaped storage and BIOMERO references

Mirror RFC 8's collection graph and shallow-copy concepts wherever the current
NGFF/tooling profile permits. Preserve native RFC-8 results and rebase their
source references to BIOMERO-managed identities when necessary.

A non-Zarr OMERO source gains a permanent canonical Zarr when the feature is
enabled. The stored shallow result still needs a small BIOMERO source reference
containing at least:

- OMERO source object type and ID;
- expected pixel identity and semantic guards;
- workflow/task provenance;
- managed canonical Zarr locator and generation.

Carry both kinds of source linkage:

- the RFC-8/NGFF relative `source.image` path identifies where the source Image
  lives in one concrete portable materialization; and
- the source Image's IMAGEWALK ISCC in the trusted collection/source record
  identifies which decoded pixel content the result derives from independently
  of storage path.

The source ISCC strengthens, but does not replace, the relative source path.
Do not invent an unversioned relation property inside NGFF's `source` object;
keep BIOMERO's path-independent relation in the versioned shared collection
contract until NGFF or ISCC standardizes such a relation.

This is storage/orchestration metadata, not a BILAYERS requirement. When the
source is later requested for a workflow, BIOMERO materializes a conventional
self-contained transfer Zarr and writes valid paths for that temporary layout.

Do not fabricate a relative source path that resolves only on one container or
after one particular mount arrangement.

### Layered label identity

Input snapshots must eventually describe label components as well as source
image pixels. Calculate ISCC-BIO/IMAGEWALK identities with `role=label` for each
declared label node in the exact transfer artifact. On return, match labels by
image-node membership, logical label path, identity, and semantic guards:

- retain a new label locally;
- retain a changed label as a new component generation;
- replace an unchanged copied label with a managed reference to its prior
  collection component;
- do not infer that similarly named labels are identical.

As a future interoperability step, a writable label group should publish its
own group-level `attrs.iscc` value. This value identifies the label pixels, not
the source Image. The label's source relationship remains in NGFF source
metadata and the trusted shallow-collection graph. Current readers use the
sidecar identity when the embedded value is absent.

Collection references form an acyclic provenance graph. Reconstruction resolves
the canonical source, recursively resolves inherited label references, and then
overlays local labels. A local/newer component wins only at its exact logical
label path. The materialized Zarr is validated to contain each declared label
once. The initial shallow implementation may retain copied labels until these
component identities are implemented; that is functionally correct but not the
final deduplication boundary.

## Materialization for a later workflow

When a user selects a shallow result in OMERO.biomero:

1. Image Transfer reads trusted collection/source metadata from the selected
   OMERO object.
2. It resolves and authorizes the referenced OMERO source object.
3. It copies the indexed native/returned Zarr or cached canonical conversion
   into the temporary transfer layout.
4. It verifies the materialized source against the expected pixel identity.
5. It overlays the selected labels into their proper NGFF label locations and
   writes collection/source paths valid inside the transfer Zarr.
6. It sends a fully functional Zarr to HPC.

Selecting the original image alone does not automatically add every historical
label collection. Selecting a shallow label result requests reconstruction of
that result with its source pixels.

Direct transfer of label-only data may be added later as an explicit workflow
capability. Full materialization is the interoperable default.

An optional future optimization may run the same task-bound image/label
identity comparison on HPC before returning a result and transfer an already
shallow RFC-8-shaped collection. This could reduce both return traffic and
server-side I/O for TB-scale Plates. It is a feasibility item, not the primary
contract: generic FAIR workflows need not know BIOMERO metadata, native shallow
output remains welcome, and BIOMERO's return path remains the backup control
point for conventional full Zarr results.

## OMERO registration and visualization

For an eligible shallow Image result, the source Image is already present in
OMERO and label projections are sufficient until viewers support label layers.
For an eligible shallow Plate result, create one derived OMERO Plate so the
result remains selectable and navigable as a Plate. The complete *logical*
result remains the in-place shallow collection: canonical source pixels plus
its retained and referenced labels.

Every declared returned label of a non-Plate Image is registered automatically
as an ordinary OMERO Image projection while PixelBuffer/iViewer label-layer
support is incomplete. This is determined from the returned Zarr structure,
not from legacy workflow-user options such as `Import_Label_Zarrs` or
`Import_Only_Labels`. These projections provide mask thumbnails, ordinary image
viewing, and input to ROI-conversion scripts. Each carries a validated
`biomero.zarr.shallow` reference. The projections never duplicate top-image
pixel storage.

A shallow Plate is registered from its canonical Plate source. OMERO creates
the normal WellSample child Images, and each child PixelBuffer LSID points to
the corresponding canonical Zarr image node. This displays the original pixels
without storing them again, including when the original OMERO Plate came from a
non-Zarr acquisition: Image Transfer has already promoted a reusable canonical
Zarr before a result can be proven shallow. The derived Plate carries the
shallow collection reference, so a label-aware viewer can overlay every retained
or inherited image-level label and later workflow selection reconstructs the
complete Plate.

An opt-in label-backed Plate preview may additionally register the same Plate
hierarchy with every WellSample child Image pointed at one specifically named,
common label node (for example `labels_nuclei`). This creates OMERO metadata,
not another label-pixel copy. It is off by default. The request must name the
label, or use automatic selection only when exactly one label name is present
on every Plate image. Missing or ambiguous membership fails that optional
preview without weakening the authoritative shallow Plate import. Creating one
preview Plate per arbitrary label and importing thousands of loose label Images
are both outside the default path.

If the returned top-image pixels changed, the result is not shallow: import
that full image/Plate as a distinct primary result and also import its declared
labels automatically.

For Plates, label groups occur at image levels in the Plate hierarchy. The
collection retains exact Plate/well/image membership. The normal Plate view can
therefore use source-backed pixels, while a selected label-backed preview uses
the matching label node for each WellSample.

## Supported interchange profile

BIOMERO supplies the OME-Zarr version/profile produced by its installed
Glencoe `omero-cli-zarr` exporter and accepts the subset supported by
BIOMERO.importer plus Glencoe's OMERO Zarr PixelBuffer. Provider guidance must
name the exact profile configured by the deployed versions; it must not imply
support for every current NGFF proposal.

Workflow providers should return a base image/label structure compatible with
that same profile if they want immediate OMERO registration and thumbnails.
Support will advance as Glencoe and OMERO release compatible exporter,
PixelBuffer, and importer versions.

BIOMERO inputs may contain a group-level `iscc` user attribute on Image and
label groups. Providers may preserve it. If they change the identified pixels
and want the output metadata to remain accurate, they should recompute or
remove it; BIOMERO does not require workflow support for this convention and
will independently verify returned pixels. A copied or stale value never causes
BIOMERO to omit returned arrays.

Native RFC-8 output is an optional optimization. A provider may instead return
a conventional full Zarr with unchanged image pixels and added labels; BIOMERO
will detect and normalize it.

## Component responsibilities

### biomero-schema

- Own versioned Pydantic interchange models only.
- Separate Zarr storage contracts from workflow descriptor models.
- Generate JSON Schema for non-Python consumers.

### biomero

- Persist workflow input snapshots in the event-sourced aggregate.
- Upcast old events and expose empty/default snapshots for old workflows.
- Provide pure comparison/materialization planning helpers.
- Do not implement a second hashing algorithm.

### biomero-scripts

- Image Transfer creates temporary full inputs, identifies them, records the
  workflow snapshot, and materializes selected shallow results.
- Import Results owns result-location resolution and submits a typed,
  workflow-scoped shallow operation when the feature and importer capability
  are enabled. It never hashes or normalizes returned Zarrs itself.
- Get Results remains independent of BIOMERO.importer and in-place storage.
- Run Workflow remains the authoritative importer/Get Results switch.

### BIOMERO.importer

- Expose a public, typed import-order submission/capability API usable by
  biomero-scripts, OMERO.biomero, and other upload clients.
- Parse/upcast the versioned import-options envelope and execute registered
  lifecycle operations after optional converter preprocessing and before
  registration planning.
- Own returned-Zarr discovery, identity work, fail-safe normalization,
  idempotent retry, and automatic result-view planning.
- Parse/validate supported NGFF structures.
- Recognize `.biomero-shallow.json`, resolve and validate its canonical Image or
  Plate source, and attach the collection reference to every derived OMERO
  result object.
- Register a shallow Plate once from its canonical Plate structure and source
  pixels. Optionally register one additional label-backed Plate by routing each
  child Image to the requested image-level label node.
- Automatically register every declared non-Plate label as an ordinary Image
  projection without requiring nested label groups to have a `.zarr` suffix.
- Return every created OMERO object so result provenance can be attached.
- It owns transactional promotion and validation of the permanent
  source-conversion cache for this feature.

### OMERO.biomero

- Edit authoritative group mappings.
- Discover collection membership from server-side metadata.
- Present source/label inventories and mask thumbnails.
- For Plate workflows with a Screen image-result destination, offer an
  off-by-default `Import Plate label preview` control and optional exact label
  name. The backend normalizes this request before Run Workflow applies the
  importer/shallow capability gates.
- Never send trusted absolute storage paths in workflow requests.

### NL-BIOMERO

- Mount the same importer config, group mappings, and in-place storage into the
  services that require them.
- Forward required environment variables through `biomeroworker/processor.py`.
- Keep all new behavior capability-gated by `IMPORTER_ENABLED`.
- Follow the shared feature branch during development, with branch-commit build
  arguments where Docker needs an explicit cache invalidator; document rebuild
  requirements.

## Delivery order

1. Make importer capability and `BIOMERO_SHALLOW_ZARR` gating explicit
   in Image Transfer, Run Workflow, Import Results, dependencies, and tests.
2. Derive canonical roots from shared runtime group mappings and
   `IMPORT_MOUNT_PATH`; remove the duplicate `storage_roots` configuration.
3. Keep shared canonical contracts and add backward-compatible event upcasting.
4. Promote non-Zarr exports once; index native/returned Zarrs in place; record
   exact canonical generations and IMAGEWALK identities in the event store.
   Portable per-Image and per-label `attrs.iscc` claims on writable
   BIOMERO-produced Zarrs remain interoperability work; current deletion
   decisions use the authoritative snapshot and recomputed returned pixels.
5. Add versioned import-operation contracts, legacy option upcasting, a public
   importer order API, and an importer lifecycle operation registry. Preserve
   legacy external preprocessing unchanged.
6. Move result discovery and exact returned-image comparison into the native
   importer `biomero.shallow-zarr` operation, initially in keep mode.
7. Implement importer-owned transactional shallow normalization and automatic
   Image-label projection planning; register Plate results as Plates and omit
   unchanged top-image pass-through objects.
8. Extend input snapshots and shallow collections with per-label identities and
   managed label references so chained workflows reuse unchanged labels.
9. Implement recursive materialization of a selected shallow result for future workflow
   transfer.
10. Add Plate fixtures, per-image canonical identities, shallow normalization,
   source-backed Plate registration, optional common-label Plate registration,
   standalone Image-label reconstruction, and multi-label registration.
11. Expose the optional Plate label-preview import in OMERO.biomero, then add
    full collection inventory and mask-thumbnail presentation.
12. Publish concise workflow-provider guidance and the BILAYERS blog section.

### Integration evidence

Delivery step 6 is proven for image-level results in the development stack.
Three labels from one in-place shallow workflow result were submitted in one
import order and registered as OMERO Images 6151-6153. Each image:

- uses its own label node as PixelBuffer backing and returns a rendered
  thumbnail;
- carries a decodable `biomero.zarr.shallow` MapAnnotation referencing the
  complete shallow collection and its pre-existing source OMERO Image; and
- does not create another OMERO object for the unchanged top-image pixels.

The automatic full-workflow Image route is also proven. Workflow
`ae83dc5e-5273-4f26-a170-563674a915d0` selected five OMERO Images whose decoded
pixels were identical. Image Transfer reused their canonical identities and
wrote one task-local marker per input; the ordered event snapshot let the
importer map all five renamed results to the correct selected objects without
an ambiguous-identity fallback. All five results were classified
`eligible (input-image-unchanged)`, stored shallow, and had their transfer
markers removed. The batch retained 13 local or inherited labels, created 13
viewable label Images, attached five DuckDB files, and created 42 ROIs. Its
estimated full size was 28.463 MiB and stored shallow size was 2.319 MiB, a
91.9% reduction. Importer identity and normalization took approximately ten
seconds with four workers.

Delivery steps 7 and 8 are proven at the image-collection level:

- canonical full-Zarr inputs inventory every existing label node and store its
  ISCC-BIO identity plus managed location in the workflow event snapshot;
- returned labels are independently classified as inherited, new, or changed;
  inherited returned copies are omitted while new/changed label nodes remain
  local and become OMERO result projections;
- selecting any shallow label projection reconstructs a conventional Zarr from
  the canonical image pixels and every local/inherited label component; and
- schema-v1 shallow manifests written before label-component records existed
  are upcast at materialization by hashing their declared physical label paths.

A live smoke test reconstructed OMERO Image 6151 from source Image 1341 into a
temporary 6,848,888-byte Zarr containing both the root image and
`labels/fractal_cellpose_sam_segmentation.zarr`. The temporary artifact was
removed after verification; all managed sources remained read-only.

Delivery step 9 now has unit-level storage and transfer coverage:

- Image Transfer indexes an existing managed Plate Zarr in place, caching an
  ISCC-BIO identity for every declared image node and label node. OMERO stores
  only one compact Plate index. The detailed inventory is an atomic managed
  storage marker beside a read-only indexed Zarr, or inside a BIOMERO-promoted
  canonical Zarr. Events and service boundaries still use one
  `CanonicalPlateSource`. Readers retain support for the earlier monolithic
  and split MapAnnotation shapes, but new writes never scale OMERO annotations
  with the number of Plate images;
- nested Plate nodes without a `.zarr` suffix are presented to ISCC-BIO/BioIO
  through a temporary zero-copy `.ome.zarr` symlink; this works around current
  reader suffix detection while keeping hashing in upstream ISCC-BIO and the
  managed Plate read-only;
- a freshly exported Plate can be transactionally promoted into `.processed`
  through the same canonical store used for Images;
- returned Plates are eligible only when their complete image-node path set and
  every image-node identity match the workflow snapshot;
- normalization removes every duplicate image dataset, preserves Plate/well
  metadata, retains new/changed image-level labels, and references inherited
  labels;
- the logical shallow Plate resolves to its canonical Plate for ordinary
  PixelBuffer registration without restoring copied pixels; and
- an optional label-backed Plate maps one common label name to every WellSample
  child Image without copying the label arrays.

The concrete integration fixtures are
`Project A/cellsA1B1.ome.zarr` (native managed Plate Zarr) and
`Project B/cellssmall/.processed/20220714_TKI_482.ome.zarr` (processed
canonical representation of a raw `.db` acquisition). Both contain 18 image
nodes under `A/1/0..8` and `B/1/0..8`. The planned workflow checks are:

- `bilayers_plate_test`: unchanged, label-free pass-through;
- `simple-zarr-plate-processor` or `cideconvolve` v2.3.3: changed pixels must
  remain a full result; and
- `cisegmentation` v0.5.0: unchanged source pixels plus image-level labels
  should normalize to one source-backed shallow Plate; optionally, its one
  common `labels_nuclei` layer should register as one label-backed Plate.

The first live `cisegmentation` run
`af449699-ea89-4cd0-9bc2-ab0ea015803c` completed against Plate 1552 and produced
18 image-level `labels_nuclei` nodes. It deliberately remained full because the
initial monolithic Plate identity MapAnnotation exceeded PostgreSQL's indexed
map-value limit, so Image Transfer returned no canonical snapshot. A second
run, `2192fb60-9de5-4644-a080-44eda1f3442d`, successfully indexed Plate 1552,
but exposed two defects: it wrote 18 visible image-record MapAnnotations, and
the returned filename differed from the transferred input filename. The latter
caused normalization to retain the complete 140 MB result even though all 18
pixel identities matched. Both defects are corrected: the Plate inventory now
lives in one storage marker with one compact OMERO index, and pixel-identity
matching permits ordinary workflow output renaming. Plate 1552's complete
inventory was migrated to
`cellssmall/.processed/.biomero/20220714_TKI_482.ome.zarr.canonical.json` and
proved to round-trip through the compact index before cleanup. The 18 generated
`biomero.zarr.plate-source.image` annotations were then removed through the
OMERO API. Plate 1552 now retains only compact index annotation 17919, while
the sidecar restores all 18 image identities. A later `cisegmentation` run,
`f186d374-3b9d-439a-9fd6-7798a9b4cb17`, proved the renamed output path: it
committed as a shallow Plate, reduced the result from 146,143,980 to 10,775,997
bytes, and successfully submitted both the authoritative source-backed Plate
and the opt-in label-backed Plate preview to the importer.
The first retry, `9192c966-e316-4e48-a12f-d8c8427ea52b`, stopped before export
because biomero's compatibility module did not re-export the shared
`ShallowPlateReference` model used by Image Transfer. Biomero commit `c9c9018`
adds the missing export and regression assertion; the rebuilt worker now loads
that commit and imports the model from `biomero_schema.zarr` successfully.

The current branches pass their focused canonical, shallow-result, importer,
script, schema, and OMERO.biomero regression suites. Run Workflow and
OMERO.biomero carry the optional Plate-preview choice end to end; it is visible
only for Plate workflows with a Screen destination and remains disabled by
default.

Whole-Plate reselection uses the derived Plate's shallow collection annotation.
Image Transfer resolves the compact `ShallowPlateReference`, reconstructs the
canonical Plate hierarchy with every local or inherited image-level label, and
records the original canonical Plate lineage even though the selected derived
OMERO Plate has a different ID. The reconstructed transfer artifact is always a
conventional full Plate Zarr.
OMERO.biomero collection inventory (delivery step 10) may expose its labels and
preview mode, but must not mutate or ambiguously annotate the original Plate.

## Required tests

- Importer disabled: modules load without `biomero_importer`; Image Transfer
  and `SLURM_Get_Results.py` retain their previous behavior.
- Importer enabled with feature flag false: existing Import Results behavior is
  unchanged and no canonical promotion or shallow comparison occurs.
- Importer enabled but shallow-Zarr dependency unavailable: log a clear warning,
  export/import normally, and do not emit a shallow-input snapshot.
- Processor allowlist: required env vars reach downloaded scripts.
- Runtime mapping edits: Import Results observes the shared mapping file without
  a second `storage_roots` config.
- Native Zarr input: reuse in place and record identity without a persistent
  copy.
- Zarr-v2 identity embedding (future interoperability): writable
  BIOMERO-produced Image, Plate-field, and label groups expose top-level
  `iscc` in `.zattrs`; native read-only Zarrs are never mutated merely to add
  it. Current managed sidecars/event snapshots remain valid when it is absent.
- Zarr-v3 identity embedding: the same group-attributes implementation writes
  `attributes.iscc` in `zarr.json` when that interchange profile becomes
  supported; code does not hard-code either metadata filename.
- IMAGEWALK invariance: rechunking, recompression, added metadata, added scale
  levels, and added labels leave the base Image identity unchanged; changing a
  decoded source pixel changes it.
- Embedded-claim safety: a workflow that copies stale `attrs.iscc` while
  changing pixels is retained as a full result after return-side recomputation.
- Plate identities: every declared field is independently identified and the
  ordered field/path inventory is compared; no synthetic Plate-level pixel
  code substitutes for those Image identities.
- Store identity: adding `<store>/.iscc.json` does not alter a
  TREEWALK-ISCC result, while adding labels or changing store files does; the
  store code is never used as source-pixel equality.
- Raw/non-Zarr input with feature enabled: one `.processed` promotion followed
  by reuse on later workflows.
- Unchanged returned image plus labels: shallow normalization retains labels and
  omits only the duplicate returned image chunks.
- Changed/unknown/ambiguous returned image: full result retained.
- Old event stream: loads successfully with an empty or upcast input snapshot.
- Multiple label nodes on an Image: all receive ordinary Image projections
  referencing the same in-place shallow collection; unchanged top-image pixels
  do not create a duplicate OMERO Image.
- Chained labels: an unchanged inherited label is referenced once, a new or
  changed label is retained as a new component, and reconstruction produces the
  complete expected set without losing source pixels or earlier labels.
- Plate: image-level labels retain correct well/image membership; one derived
  Plate registers against canonical source pixels; loose label Images are not
  created; and the opt-in label-backed Plate succeeds only for an exact common
  label selection.
- Plate metadata scale: a Plate with 1,000 image nodes still creates one compact
  OMERO canonical index; its full identity inventory round-trips through the
  managed storage marker, and legacy split records remain readable.
- Plate performance scale: benchmark at least one representative large Plate;
  no recursive whole-tree byte scan or retained-tree copy occurs in the
  synchronous path, and identity, move, deletion, and total times are reported
  separately.
- Image performance: the five-Image canonical-reuse batch established 91.9%
  storage reduction and approximately ten seconds of importer identity plus
  normalization work. Still measure a first-time canonical export separately,
  and split NGFF discovery, source/label identity, normalization, deletion,
  total return-path time, full/shallow bytes, and file counts per Image.
- Re-materialized shallow result: full source pixels and labels compare with the
  original kept result.
- Unsupported/newer NGFF: conservative retention with an actionable log.

## Acceptance criteria

- No `storage_roots` configuration exists in `slurm-config.ini`.
- At most one verified canonical Zarr generation is retained for a non-Zarr
  source, and later transfers reuse it.
- Group mappings remain runtime-editable and have one authoritative source.
- Importer-disabled BIOMERO continues to run through Get Results without
  importer packages, shared-storage assumptions, or shallow-storage behavior.
- Missing/false `BIOMERO_SHALLOW_ZARR` preserves existing importer
  behavior.
- Eligible unchanged Zarr results occupy label/metadata storage rather than a
  repeated copy of source image pixels.
- Current services share versioned per-Image and per-label IMAGEWALK records;
  later portable embedded ISCC claims must remain non-authoritative for
  returned-pixel deletion.
- OMERO Plate metadata stays bounded: one compact canonical index per
  generation, independent of image and label count.
- Changed results are preserved completely.
- Selecting a shallow result later produces a conventional, fully usable Zarr
  input for the workflow.
