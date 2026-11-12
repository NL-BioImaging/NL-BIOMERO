# Working with shallow OME-Zarr results

```{raw} html
<style>
.wy-nav-content { max-width: 1100px; }
.wy-table-responsive table { width: 100%; table-layout: fixed; }
.wy-table-responsive table td, .wy-table-responsive table th { white-space: normal; }
.wy-table-responsive code { overflow-wrap: anywhere; }
</style>
```

BIOMERO stores a workflow result as **retained data plus references to its known
managed input**. The result remains a distinct OMERO Image or Plate with its
own provenance. Storage is saved on the shared filesystem, without deleting the
source or suppressing result registration.

## Why BIOMERO shallows results

BIOMERO gives a workflow one input folder and collects its results only from
one output folder: inputs are never read back as outputs. Reusable workflows
such as Bilayers and BIAFLOWS work this way. Fractal tasks normally write into
their input Zarr, so when they are packaged for BIOMERO (for example as
Bilayers workflows) they are pointed at the output folder instead. With
OME-Zarr this means the output usually repeats the input pixels next to what
the workflow produced, such as a new `labels/` group, so that it is valid on
its own. BIOMERO prepares the input, collects the output and stores both, so it
knows where the repeated pixels came from and can avoid storing them twice. For large Plates and repeated runs this saves most
of the result storage; see {ref}`the measurements <shallow-results-measured>`.

- **Only BIOMERO's own copies are shallowed.** Shallowing applies to managed
  storage written by BIOMERO (the importer's and analyzer's processed and
  analyzed data), never to original acquisition data. Workflows are not
  expected to clean up their own output.
- **A shallow result stays usable.** OMERO reads the source pixels through the
  registered path, the viewer reconstructs labels from the result reference,
  and a result can be {ref}`reconstructed <shallow-reconstruct-standalone>` as a
  full Zarr for a new workflow or for export outside BIOMERO.
- **The comparison is a deliberate trade-off.** Comparing full-resolution
  pixels while the user waits for the result more than doubled the analysis
  time in acceptance tests. BIOMERO therefore compares the smallest compatible
  stored pyramid level. This is acceptable because only BIOMERO-produced copies
  are pruned and workflows should not change their input pixels; exact checks
  belong in background work, not in the result path.
- **Workflows can declare what they did.** A run-bound RO-Crate output
  declaration, or the administrator's per-workflow setting, states that the
  outputs are linked to their source, so BIOMERO can skip the pixel comparison
  (see {ref}`Output handling and comparison <shallow-output-handling>`).
- **The format is interim.** It is a BIOMERO-private representation, not
  OME-NGFF RFC-8 (collections); it is expected to change when RFC-8 is
  available.

## On disk: shallow off versus on

**Example: one 2D v2 Image, unchanged intensities, one new `cells` label.**
The directory contents below represent the same analysis result.
**The two comparisons use grey borders for Shallow OFF and purple for Shallow
ON.** Here, fills describe contents: blue pixels, green labels, yellow
reference/provenance metadata.

```{raw} html
:file: ../_includes/shallow-file-trees.html
```

**The blue folders disappear from the result:** full-resolution image
chunks and their pyramid arrays. The original source retains those pixels.
**Green is added by the workflow, not by the shallower:** those label files
remain in both result formats. Two small JSON files are added; `.zattrs` loses
`multiscales` and gains a `biomero` pointer to the shallow manifest.
These edits affect the returned image metadata; the source is unchanged by
shallowing. Other output files, such as CSV measurements, remain.

The file `0.0` is an example pixel chunk; `…` stands for further chunk files.
Blank rows on the right align the retained labels; they are not files.
This is a file-layout example, not a file-count or size scale. `0`, `1`, ... are
example array names; `s0`, `s1`, ... work too. A Plate repeats the image layout
under its well/field paths. V3 uses `zarr.json` in place of the v2 metadata files;
the same keep/omit/reference distinction applies.

## In OMERO: two different references

```{mermaid} ../_diagrams/shallow-references.mmd
```

The importer creates a new result Image or Plate in both cases. With shallow
storage on, it registers the **source pixel path** for primary intensities and
adds a **`biomero.zarr.shallow` MapAnnotation** locating the shallow result and
its references. The viewer and later transfers use that result reference to
find labels and reconstruct the collection.

**PixelBuffer does not need to interpret the shallow manifest:** it reads the
source path already registered by the importer. Label-backed mask Images and
the optional Plate preview similarly register their retained label paths.
{ref}`Preview controls <plate-mask-preview>`.

The two JSON files have separate jobs:

| File | Purpose |
| --- | --- |
| `.biomero-shallow.json` | Image/label nodes, omitted arrays, source storage bindings and decision basis; measured identities when comparison was used |
| `.biomero-shallow-report.json` | Decision, input snapshot and tool provenance; remote receipts bind this report to the expected helper run |

Source indexing is separate: canonical-source annotations
(`biomero.zarr.source` / `biomero.zarr.plate-source`) record the reusable input.
Indexing can also add a `.biomero-canonical.json` marker to the source store;
this is metadata, not another pixel copy.
**Keep the source, retained labels and their references together in retention
and backup policy.** The shallow folder alone is incomplete.

## Workflow input: reuse, reconstruct or export

The workflow receives full input in its requested format. It does not resolve
BIOMERO shallow references itself.

```{mermaid} ../_diagrams/shallow-workflow-input.mmd
```

**Reconstruction** assembles a temporary full Zarr from the source and all
retained/referenced labels. **Export** reads the selected OMERO pixel view; it
does not reconstruct the shallow result's full label collection. A format
mismatch uses export and leaves the original canonical registration unchanged.

### What registering or promoting a canonical Zarr entails

A **canonical Zarr** is the stable managed source bound to a workflow input.
Its locator, generation and image semantics can be recorded without hashing
original pixels. Comparison fingerprints are calculated only when needed;
source-linked handling does not require an otherwise unused fingerprint.
Yellow steps below mark pixel reads.

```{mermaid} ../_diagrams/shallow-canonical.mmd
```

| Starting point | Pixel calculation | What canonical registration changes |
| --- | --- | --- |
| Existing authoritative backing Zarr | Original-image hashing is deferred until comparison needs it; labels retain their separate policy | Records source binding and semantics in place; no new pixel copy |
| Eligible fresh OMERO export | Full-resolution source/export verification remains a separate promotion check | Commits the verified export to stable managed canonical storage and attaches source records |
| Current comparison fingerprint already cached | Reuses that fingerprint for the same source generation and compatible resolution | Records the workflow input snapshot; no repeated source hash |
| Old or missing comparison profile | Local importer reads the same authoritative backing Zarr when comparison is needed | Replaces the cached record with the current profile; no export, copy or reimport |

Only the matching generation is reused. A temporary format-mismatch export or
TIFF conversion input is not promoted. Failed indexing/promotion leaves the
full workflow input usable without deduplication for that selection. Missing
dependencies of a shallow input must be resolved before it can be reconstructed.
Old records are detected as stale, never relabelled as current fingerprints.
There is one current cache rather than parallel legacy and pyramid identities.
The remote helper uses current cached fingerprints; it cannot refresh them from
the authoritative managed store. Missing/stale fingerprints keep the remote
result full so the importer can compare and cache from the actual source.
Post-analysis HPC input copies are not authoritative comparison sources.

(shallow-output-handling)=
## Output handling and comparison

The decision order is:

| Condition | Handling |
| --- | --- |
| Shallow storage disabled | Full results, without deduplication-only hashing or pruning |
| Enabled, usable run-bound RO-Crate label output declaration | Automatically use the known input as image background; no original-pixel comparison or admin approval |
| No usable declaration, workflow setting enabled | Use the same source-linked route under the recorded workflow policy |
| Neither | Compare compatible stored pyramid pixels; unsupported or unmatched results stay full |

The administrator setting is
`[UI] original_pixels_not_required_workflows`; see the
{ref}`admin controls <shallow-zarr-admin>`.
It is independent of automatic RO-Crate handling and input-format selection.
No Bilayers output-preservation preset is inferred.

Supported declarations connect the run's input and label-level `result` with
the output parameter's `exampleOfWork` and the crate's `hasPart`. The execution
record supplies the managed source binding. A root-level Zarr pointer alone
does not identify which image arrays are derived. Cheap format, layout and
semantic guards still apply; missing or ambiguous evidence falls through to
the setting or comparison. The supported result includes the enclosing image
and label datasets; bare labels-only materialization is not implemented.
Additional derived stores and sidecars are retained.

The original RO-Crate is retained. If its graph explicitly inventories an array
or label subtree that shallowing would remove, the artifact stays full rather
than leaving stale file claims or rewriting an arbitrary graph. For supported
label-output declarations, the retained crate describes the produced labels
and the committed shallow manifest records the managed-source relationships.

Each binding records whether it used `ro-crate-output`, `workflow-setting` or
`pixel-comparison`. Source-linked decisions do not invent a pixel fingerprint
or claim that returned original pixels were measured.

| Route | Order |
| --- | --- |
| Shallow off | Workflow → full ZIP → transfer → full result registration |
| Shallow on, remote | Workflow → HPC output handling/comparison → ZIP → transfer → receipt validation or local comparison → registration |
| Shallow on, local | Workflow → full ZIP → transfer → importer output handling/comparison → registration |

| Responsibility | Implementation |
| --- | --- |
| Pixel traversal and codes | [ISCC-BIO](https://github.com/bio-codes/iscc-bio) `generate_biocode(planes)`; decoded numerical planes from a stored level, without the high-level file/store checksum |
| Comparison policy | BIOMERO selects the coarsest compatible stored image level, retains all C/Z/T coverage and checks full-image and selected-level semantics; labels use full resolution |
| Equality decision | Matching current profiles, code lengths, Instance-Codes and semantic guards; dataset path spelling is provenance, not an equality key |
| Storage, transactions and references | BIOMERO.shallower; shared contracts from biomero-schema |
| HPC orchestration and OMERO registration | BIOMERO core/scripts and BIOMERO.importer, respectively |

The pixel API's composite ISCC-SUM and similarity-oriented Data-Code are
recorded but **do not authorize removal**. No raw file-tree checksum or rendered
thumbnail is calculated. Numerical planes follow IMAGEWALK Z → C → T traversal
with upstream canonical pixel encoding. A single-level image uses full
resolution; compatible stored levels require matching dimensions, dtype, axes
and transformations without omitting channels, Z slices or timepoints.

Selected-level byte equality is exact. Inferring unchanged full-resolution
pixels from a smaller pyramid is **BIOMERO's deduplication approximation**,
not a full-resolution equality proof or perceptual ISCC matching. Workflows
must return internally consistent pyramids. The
[shared comparison contract](https://nl-bioimaging.github.io/biomero-schema/pixel-identity/)
defines profile fields, code lengths, reproducibility versions and scientific
scope; it is the canonical algorithm reference.

| Condition | Action |
| --- | --- |
| Shallow storage disabled; ordinary upload; TIFF result | No shallow operation |
| Input/output Zarr profiles differ | Keep full; check format metadata before pixel hashing |
| Eligible collection with a source-linked decision or matching image fingerprints | Omit returned original-image pyramids; reference matching inherited labels; retain new/changed labels |
| Comparison required but fingerprints differ, or source/layout binding is unsupported or ambiguous | Keep the full collection |
| Invalid receipt, missing referenced source or unresolved transaction | Stop and preserve evidence for recovery; absent pixels cannot be treated as a full result |

Pruning uses same-filesystem moves and a rollback journal before committing the
manifest. Source pixels remain untouched. See [configuration and recovery](../sysadmin/remote-shallower.rst).

(reconstruct-shallow-zarr-on-disk)=
(shallow-reconstruct-standalone)=
## Reconstructing a standalone result

The [reconstruction recipe](https://github.com/NL-BioImaging/BIOMERO.shallower#reconstruct-a-full-zarr)
creates a self-contained Image or Plate at a **new destination**, using its
referenced source and retained labels. It preserves v2/v3 format and leaves
OMERO registrations unchanged. Keep all referenced stores available and allow
enough disk space for the full copy.

(shallow-results-measured)=
## Results: measured benefits and costs

These measurements used the earlier full-resolution comparison path. They
describe the recorded storage and execution costs, not the speed of the
selected-resolution comparison or declaration shortcuts above.

[![Retained Zarr storage and recorded elapsed time for small, medium and large Plates. Large Full excludes its explicit recovery wait; all other recorded phases remain.](../_static/figures/shallow-results.svg)](../_static/figures/shallow-results.svg)

**Full v3 versus remote-shallow v2**, with 10, 3 and 1 technical repetitions per
configuration for small, medium and large Plates. Storage excludes the existing
shared source and non-Zarr output; GB is decimal. **A: mean ± SD** (storage
variation is too small to distinguish). **B: mean with 95% Student-t CI and
individual timings**; headings give the unpaired Welch 95% CI for shallow minus
Full. No CI is estimated for n = 1. These intervals assume independent workflow
executions; shared load and cache history limit that assumption. Formats also differ.

Shallow results retain **83.7-89.5% less Zarr data**. At medium scale,
return/packaging/extraction falls by **12.11 min**, but observed mean waiting increases
by **14.87 min (+8.5%)**. At large scale, canonical preparation (**180.1 min**),
shallowing (**110.4 min**) and result return (**168.8 min**) each approach or
exceed analysis execution (**154.0 min**). Both estimated runtime-difference CIs
include zero; these runs do not establish a timing advantage.

**Large Full (*)** removes only the explicit recovery wait:
4,012.72 - 2,846.23 = **1,166.49 min**. Its ZIP retrieval was interrupted;
the green return stage records only **0.12 min**, while grey includes long
polling and orchestration gaps. This adjusted record is not an uninterrupted-run
speedup comparison. **Large shallow (†)** used repaired source provenance.

[Data](../_figures/data/shallow-plate-comparison.json) and
[reproduction instructions](../_figures/README.txt) preserve the full phase
breakdown. An [earlier local/remote comparison](../sysadmin/remote-shallower.rst)
measured **87.6% less return ZIP data** remotely; its combined copy/validation
stage took **81.0 to 11.1 s**. That comparison uses a different storage scope.
