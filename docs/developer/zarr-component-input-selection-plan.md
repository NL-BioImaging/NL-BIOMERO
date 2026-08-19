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
- `CanonicalPlateSource`: one managed Plate locator plus an independently
  identified `CanonicalPlateImage` for every declared Plate image node;
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
8. For an Image result, create importer orders for every viewable label node;
   multiple masks produce multiple OMERO Images. For a Plate result, import one
   authoritative shallow Plate and do not flatten its image-level labels into
   a Dataset of mask Images.

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
   exact canonical generations in the event store.
5. Implement result discovery and exact returned-image comparison in Import
   Results, initially in keep mode with decision logging only.
6. Implement transactional shallow normalization and automatic Image-label
   projection import; register Plate results as Plates and omit unchanged
   top-image pass-through objects.
7. Extend input snapshots and shallow collections with per-label identities and
   managed label references so chained workflows reuse unchanged labels.
8. Implement recursive materialization of a selected shallow result for future workflow
   transfer.
9. Add Plate fixtures, per-image canonical identities, shallow normalization,
   source-backed Plate registration, optional common-label Plate registration,
   standalone Image-label reconstruction, and multi-label registration.
10. Expose the optional Plate label-preview import in OMERO.biomero, then add
    full collection inventory and mask-thumbnail presentation.
11. Publish concise workflow-provider guidance and the BILAYERS blog section.

### Integration evidence

Delivery step 6 is proven for image-level results in the development stack.
Three labels from one in-place shallow workflow result were submitted in one
import order and registered as OMERO Images 6151-6153. Each image:

- uses its own label node as PixelBuffer backing and returns a rendered
  thumbnail;
- carries a decodable `biomero.zarr.shallow` MapAnnotation referencing the
  complete shallow collection and its pre-existing source OMERO Image; and
- does not create another OMERO object for the unchanged top-image pixels.

The remaining step-6 coverage is the automatic full-workflow route, including
multiple labels and live Plate membership registration.

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
the sidecar restores all 18 image identities. The corrected branches are
deployed in the development stack; the remaining live proof is a new
`cisegmentation` run whose renamed output must commit as a shallow Plate.

The current branches pass all 79 script tests and the 34 focused importer
canonical/shallow-result tests. The full importer unit run passes 129 tests and
has one unrelated SQLite fixture failure (`imports` table missing). Run
Workflow and OMERO.biomero carry the optional Plate-preview choice end to end;
it is visible only for Plate workflows with a Screen destination and remains
disabled by default.

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
- OMERO Plate metadata stays bounded: one compact canonical index per
  generation, independent of image and label count.
- Changed results are preserved completely.
- Selecting a shallow result later produces a conventional, fully usable Zarr
  input for the workflow.
