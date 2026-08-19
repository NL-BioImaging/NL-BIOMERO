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

The `biomeroworker` container runs both Image Transfer and the result scripts.
It therefore still needs the shared mapping files for importer-enabled Import
Results. Mount the same files used by OMERO.biomero read-only in the worker;
do not pass absolute storage paths from the web request.

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

## Data identities

Use `iscc-bio`/IMAGEWALK for the pixel identity of an image node. Its useful
property is format-independent identity: the same logical image pixels can
produce the same identity when read from a raw microscopy file, OMERO Pixels,
or OME-Zarr.

Record semantic guards with each identity:

- node path and role (`image` or `label`);
- shape, axes, and dtype;
- coordinate transformations relevant to interpreting the node;
- ISCC, Data-Code, and Instance-Code;
- tool version and IMAGEWALK revision.

Use `iscc-sum` as an optional store/archive identity for transfer integrity,
fast exact-store checks, and operational deduplication. Do not create a
BIOMERO-specific checksum implementation.

Pixel equality is based on the pixel identity plus semantic guards, not on a
copied directory path. Store identity alone is insufficient because adding
labels or metadata legitimately changes the Zarr tree.

## Shared contracts

Keep the cross-service Pydantic models in `biomero-schema`, separate from the
workflow descriptor schema. The target vocabulary is:

- `PixelIdentity`: identity and guards for one NGFF image or label node;
- `CanonicalZarrSource`: OMERO Image/Plate identity, managed Zarr locator,
  generation, interchange profile, and verified pixel identity;
- `CanonicalInput`: selected object, ordinal, and exact canonical generation
  transferred;
- `CanonicalInputManifest`: ordered inputs bound to workflow and export task;
- `ShallowCollection`: source and label membership plus safe materialization
  metadata.

Previously serialized workflow events must remain readable. Add explicit
upcasting/default behavior for the old event payloads; do not rewrite event
history or add a sidecar manifest on SLURM.

## Export and input snapshot

For an importer-enabled Zarr transfer:

1. Resolve the selected OMERO Images or Plate in stable input order.
2. If a selection is an already registered native or managed Zarr, reuse and
   index that path as its canonical source. Do not duplicate it.
3. Otherwise export an OME-Zarr using the supported Glencoe/OMERO exporter
   profile, verify it against OMERO Pixels, and transactionally promote it once
   into the group's `.processed` area.
4. Calculate or reuse the ISCC-BIO identity for each canonical image node
   actually sent.
5. Record a `CanonicalInputManifest` in the workflow event store, including the
   selected OMERO object, canonical generation, and transferred identity.
6. Optionally place a small BIOMERO hint in the transfer Zarr. A generic
   workflow may preserve, remove, or ignore it.
7. Transfer the ordinary, fully usable Zarr to SLURM.
8. Clean up the task-local transfer copy according to existing behavior; retain
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
plate hierarchy. Do not guess labels at the plate root.

## Result normalization

This processing belongs in `SLURM_Import_Results.py`, after results have been
copied into their permanent `.analyzed` directory and before importer orders
are committed.

For every returned Zarr candidate:

1. Load the exact workflow input snapshot through workflow/task provenance.
2. Discover returned NGFF image and label nodes, including Plate image-level
   labels.
3. Match returned image nodes to input nodes deterministically by provenance,
   structure, and identity. Never choose an arbitrary candidate.
4. Calculate the returned image-node identity unless a valid task-bound hint
   permits a safe fast path.
5. If identity and semantic guards match, construct a shallow collection that
   retains labels and references the source OMERO object.
6. If pixels differ, no exact source is available, the mapping is ambiguous, or
   validation fails, keep the complete returned Zarr.
7. Commit the normalized result transactionally before deleting any redundant
   image chunks from that result.
8. Create importer orders for every viewable label node. Multiple masks produce
   multiple OMERO result objects, matching existing multi-image result
   behavior.

This optimization removes only copied pixels from the newly returned result.
It never deletes or rewrites the original OMERO object or native Zarr.

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

This is storage/orchestration metadata, not a BILAYERS requirement. When the
source is later requested for a workflow, BIOMERO materializes a conventional
self-contained transfer Zarr and writes valid paths for that temporary layout.

Do not fabricate a relative source path that resolves only on one container or
after one particular mount arrangement.

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

## OMERO registration and visualization

The current PixelBuffer/import stack does not render NGFF labels as layers on
their source image. For now:

- register each label image/group as an ordinary OMERO Image projection;
- use the label pixels for its thumbnail and normal viewer representation;
- attach collection membership, source identity, workflow provenance, label
  name, and physical path as server-side metadata;
- allow OMERO.biomero to show a read-only inventory of source and labels;
- leave the future combined Zarr viewer outside this implementation.

For Plates, label groups occur at image levels in the plate hierarchy. Import
the corresponding mask projections and retain their plate/image membership in
the collection metadata.

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
- Import Results owns result-location resolution and shallow normalization.
- Get Results remains independent of BIOMERO.importer and in-place storage.
- Run Workflow remains the authoritative importer/Get Results switch.

### BIOMERO.importer

- Parse/validate supported NGFF structures.
- Register source and label projections without requiring nested label groups
  to have a `.zarr` suffix.
- Return every created OMERO object so result provenance can be attached.
- It owns transactional promotion and validation of the permanent
  source-conversion cache for this feature.

### OMERO.biomero

- Edit authoritative group mappings.
- Discover collection membership from server-side metadata.
- Present source/label inventories and mask thumbnails.
- Never send trusted absolute storage paths in workflow requests.

### NL-BIOMERO

- Mount the same importer config, group mappings, and in-place storage into the
  services that require them.
- Forward required environment variables through `biomeroworker/processor.py`.
- Keep all new behavior capability-gated by `IMPORTER_ENABLED`.
- Pin branch dependencies during feature development and document rebuild
  requirements.

## Delivery order

1. Make importer capability and `BIOMERO_SHALLOW_ZARR` gating explicit
   in Image Transfer, Run Workflow, Import Results, dependencies, and tests.
2. Derive canonical roots from shared runtime group mappings and
   `IMPORT_MOUNT_PATH`; remove the duplicate `storage_roots` configuration.
3. Keep shared canonical contracts and add backward-compatible event upcasting.
4. Promote non-Zarr exports once; index native/returned Zarrs in place; record
   exact canonical generations in the event store.
5. Implement result discovery and exact returned-image comparison in Import
   Results, initially in keep mode with decision logging only.
6. Implement transactional shallow normalization and label projection import.
7. Implement materialization of a selected shallow result for future workflow
   transfer.
8. Add Plate fixtures and multi-label registration.
9. Add OMERO.biomero inventory and mask-thumbnail presentation.
10. Publish concise workflow-provider guidance and the BILAYERS blog section.

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
- Raw/non-Zarr input with feature enabled: one `.processed` promotion followed
  by reuse on later workflows.
- Unchanged returned image plus labels: shallow normalization retains labels and
  omits only the duplicate returned image chunks.
- Changed/unknown/ambiguous returned image: full result retained.
- Old event stream: loads successfully with an empty or upcast input snapshot.
- Multiple label nodes: all become OMERO result objects with collection
  metadata.
- Plate: image-level labels retain correct well/image membership.
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
- Changed results are preserved completely.
- Selecting a shallow result later produces a conventional, fully usable Zarr
  input for the workflow.
