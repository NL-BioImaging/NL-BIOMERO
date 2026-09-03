# Experimental BIOMERO shallow OME-Zarr storage

```{warning}
This is an experimental, private BIOMERO storage contract. It is inspired by
the shallow-copy use case in OME-NGFF RFC 8, but
`.biomero-shallow.json` is **not** an RFC 8 Collection and is not a portable
OME-NGFF standard. The current wire schema is version 1 and will evolve through
versioned readers and upcasters.
```

Standards status at a glance:

- RFC 8 is a proposal, not a released OME-NGFF Collections specification;
- BIOMERO emulates its composition idea with a private managed sidecar rather
  than claiming standards compliance;
- the current workflow interchange profile is OME-NGFF 0.4 on Zarr v2, not the
  newest draft NGFF/Zarr feature set, because the Glencoe exporter and OMERO
  Zarr PixelBuffer must both be able to serve the result; and
- generic readers are only expected to read a BIOMERO result after it has been
  reconstructed into a conventional full Zarr.

BIOMERO can store a label-producing Zarr workflow result without keeping a
second copy of the unchanged input pixels. The retained result contains its
labels, the structural metadata needed to describe them, and managed references
to a full source Zarr. When that result is selected for a Zarr-consuming
workflow, BIOMERO reconstructs an ordinary, self-contained OME-Zarr before
transfer.

The feature deliberately applies only to **derived workflow results**. It never
removes or rewrites the user's original raw data or the managed full source.
When BIOMERO cannot establish that returned pixels are unchanged, it keeps the
returned Zarr in full. A workflow result can also be regenerated from its
original input and parameters, so the optimization has a smaller risk boundary
than deduplicating primary data.

## Why shallow results exist

A typical segmentation workflow receives a full OME-Zarr, copies its image
arrays to the output, and adds one or more NGFF labels. Persisting every such
output duplicates the largest part of the data. This becomes costly for Plates:
several segmentation and analysis runs can otherwise create several copies of
the same hundreds of gigabytes or terabytes of intensity data.

The shallow result is a managed composition:

```text
full managed source pixels ───────────────┐
                                          ├─ reconstruct ─> full workflow input
derived result metadata + local labels ───┘
```

This is primarily a **storage optimization**, not an interchange format.
Zarr-consuming workflows normally receive the reconstructed full Zarr so that
generic tools can use intensity pixels, physical metadata, inherited labels,
and new labels without understanding BIOMERO. A TIFF-consuming workflow is the
intentional exception: its temporary Zarr conversion material represents the
exact OMERO Image pixels the user selected, such as one registered mask Image,
rather than the complete shallow collection.

## Which Zarr is which?

There can be several Zarr directories during one workflow, but they have
different owners and lifetimes. They must not all be interpreted as the same
scientific object.

| Artifact | Typical location | What it contains | Who consumes it |
| --- | --- | --- | --- |
| Managed source or canonical Zarr | Original managed location or `.processed` | Complete image pixels and NGFF structure; it may already contain labels | BIOMERO as the read-only pixel source |
| Temporary transfer Zarr | Workflow-specific transfer directory | A complete, ordinary Zarr assembled for this workflow | A Zarr-native workflow on HPC |
| Full returned Zarr | Temporary result, then `.analyzed` | Whatever the workflow produced, often copied input pixels plus labels | BIOMERO.importer before normalization |
| Stored shallow result | `.analyzed` | Result metadata, locally new or changed labels, and managed references to unchanged pixels and inherited labels | BIOMERO, OMERO registration, and later reconstruction |
| OMERO label Image | OMERO metadata plus PixelBuffer path | A view of one label node, not another copy of the whole collection | iViewer, thumbnails, ROI conversion, and user selection |
| Reconstructed follow-up input | Temporary transfer directory | Source pixels plus all inherited and local labels, materialized as one conventional Zarr | The next Zarr-native workflow |

The stored shallow directory is therefore often **not byte-for-byte the Zarr
that the workflow received**. It is the compact, authoritative result in
BIOMERO-managed storage. At the workflow boundary BIOMERO turns it back into a
normal Zarr.

```{mermaid}
flowchart LR
    A[OMERO selection] --> B{Workflow input format}
    B -->|Zarr-native| C[Full temporary Zarr]
    B -->|TIFF / BIAFLOWS| D[Disposable Zarr from selected PixelBuffer]
    D --> E[TIFF input]
    C --> F[Workflow]
    E --> F
    F --> G{Returned a Zarr?}
    G -->|no| H[Legacy result import]
    G -->|yes| I[Verify image and label identities]
    I -->|image pixels changed or uncertain| J[Keep full returned Zarr]
    I -->|image pixels unchanged| K[Store shallow result]
    K --> L[Keep new or changed labels locally]
    K --> M[Reference unchanged pixels and inherited labels]
    L --> N[Create new OMERO label views]
    M --> O[Reconstruct when selected for another Zarr workflow]
    L --> O
```

### What the workflow actually receives

| User selection and workflow | Data delivered to the workflow |
| --- | --- |
| Ordinary Image selected for a Zarr-native workflow | A complete Zarr copied from an existing managed Zarr or reusable canonical conversion |
| Shallow label result selected for a Zarr-native workflow | A newly materialized full Zarr containing the original intensity pixels, every inherited label, and every label stored by the selected result |
| Ordinary or label Image selected for a TIFF/BIAFLOWS workflow | TIFF converted from the selected OMERO PixelBuffer; for a label Image this means mask pixels, not reconstructed intensity pixels |
| Plate selected for a workflow | A complete Plate Zarr; Plates remain Zarr-only and are never flattened into the TIFF exception |
| Zarr uploaded directly through BIOMERO.importer | The submitted Zarr is imported normally; no workflow input snapshot exists, so BIOMERO does not automatically shallow it |

"Complete" describes the transport artifact, not which array is the semantic
input to an analysis. A segmentation workflow normally reads the image arrays
and writes a label below the corresponding `labels/` group. A label-driven
workflow, such as cell expansion, reads the requested existing label from that
group and writes its derived label back into the Zarr. It may additionally read
the intensity image when its algorithm needs intensity information. The
workflow contract or parameters must identify the intended label name; BIOMERO
preserves all labels during reconstruction rather than guessing that the
top-level image is the desired mask.

The temporary Zarr used before a TIFF conversion is an implementation detail
of the older transfer path. The TIFF workflow never receives that Zarr. It is
also excluded from canonical promotion and return-side Zarr matching.

### Labels across workflow generations

BIOMERO identifies label pixels independently from image pixels. A follow-up
workflow may receive five existing label layers and add four more. On return:

- the five unchanged inherited labels remain members of the logical result but
  become references to their existing managed locations;
- the four new labels remain physically stored in the new shallow result;
- only the four new labels become new OMERO mask Images by default; and
- the next reconstruction contains all nine labels exactly once.

This is label deduplication as well as image-pixel deduplication. Labels are
not forgotten merely because their chunks are not copied into every result.
If a workflow changes an existing label at the same logical path, its ISCC-BIO
identity changes and BIOMERO stores that changed label as a new component.

## Lifecycle

1. Image Transfer resolves or creates a full managed Zarr for every selected
   OMERO Image or Plate. A non-Zarr original may therefore acquire a reusable
   canonical representation in `.processed`; an already managed Zarr can be
   used directly without making another canonical copy.
2. BIOMERO calculates per-image and per-label pixel identities and stores the
   authoritative ordered input snapshot in its workflow event store.
3. Each task-local input copy receives `.biomero-input.json`. This small marker
   identifies the selected input even when several inputs contain identical
   pixels or a workflow renames its result. It is not a workflow-provider
   contract and is removed from the stored result.
4. The workflow runs against a normal, full OME-Zarr. Image-driven workflows
   read its image arrays; label-driven workflows read the appropriate
   `labels/` member. It may ignore and simply copy BIOMERO metadata.
5. On return, BIOMERO.importer recomputes the decoded pixel identities. If the
   image pixels match the corresponding source and useful labels are present,
   it transactionally removes the duplicated image arrays and writes
   `.biomero-shallow.json`. Changed or uncertain results stay full.
6. OMERO registers viewable projections of the result while the authoritative
   shallow collection remains in managed `.analyzed` storage.
7. Selecting a shallow result for a later Zarr workflow causes Image Transfer
   to materialize a temporary full Zarr containing the source pixels, inherited
   labels, and locally retained labels. For a workflow that will convert its
   inputs to TIFF, Image Transfer instead uses the established OMERO CLI Zarr
   export route for the selected OMERO Image. The registered PixelBuffer then
   remains the authority, so selecting a label Image exports that label rather
   than reconstructing and accidentally converting the original image. This
   conversion artifact is not promoted as a canonical source and carries no
   returned-Zarr matching contract. Temporary inputs are removed after
   transfer.

Return-side identity work and normalization belong to BIOMERO.importer. They
are not tied to the lifetime of the OMERO.web request that submitted the
workflow. The OMERO script currently waits for the import status, but an ended
web session does not terminate importer-owned processing.

## Relationship to OME-NGFF RFC 8

[RFC 8](https://ngff.openmicroscopy.org/rfc/8/) proposes Collections and, as a
motivating use case, shallow copies of images with segmentations. BIOMERO mirrors
the following design ideas:

- unchanged image data can remain in a separately managed source;
- a derived collection can retain labels and refer back to that source;
- collection members can be composed into a complete view at a system
  boundary; and
- a Plate can refer to source images per field rather than inventing one
  Plate-wide pixel checksum.

BIOMERO currently adds private machinery that RFC 8 does not define: OMERO
object IDs and generations, logical storage roots, relative managed paths,
workflow and transfer identifiers, an event-store input snapshot, ISCC-BIO
pixel identities, and registration projections for the current OMERO
PixelBuffer.

Consequently, a BIOMERO shallow result must not be presented as a standardized
RFC 8 Collection. Generic OME-Zarr readers are not expected to follow its
managed references. Once a compatible Collections model is released and
supported by the surrounding OMERO stack, the private schema can be migrated or
adapted behind its versioned reader.

### NGFF label `source`

A retained label still has the standard NGFF 0.4 relationship:

```json
{
  "image-label": {
    "source": {"image": "../../"},
    "version": "0.4"
  }
}
```

That relative path describes the label's logical image inside the reconstructed
Zarr. While the result is shallow, the local image arrays may be absent, so the
BIOMERO sidecar is the authority for locating the externally managed pixels.
Reconstruction makes the ordinary relative NGFF relationship valid again. We
do not overload `image-label.source.image` with a deployment-specific absolute
filesystem or object-store path.

## The BIOMERO storage contract

The Pydantic models in
[`biomero-schema`](https://nl-bioimaging.github.io/biomero-schema/) are the
shared contract between BIOMERO, BIOMERO.importer, and the OMERO scripts.
Services must use those models instead of independently constructing JSON. The
principal markers are:

| Marker | Lifetime and purpose |
| --- | --- |
| `.biomero-canonical.json` | Identifies a committed reusable full source representation. |
| `.biomero-input.json` | Task-local input hint, validated against the workflow event snapshot and removed on return. |
| `.biomero-shallow.json` | Authoritative manifest for a stored derived result whose image arrays were omitted. |

An abbreviated Image result looks like this:

```json
{
  "schema": 1,
  "model": "rfc8-shallow-copy",
  "workflowId": "<workflow-id>",
  "transferArtifact": "segmentation-result.ome.zarr",
  "interchangeProfile": "ngff-0.4-zarr-v2",
  "images": [{
    "imageNodePath": ".",
    "source": {
      "storageRoot": "group-0-data",
      "relativePath": ".processed/canonical-image.ome.zarr",
      "sourceObjectType": "Image",
      "sourceObjectId": 42,
      "sourceGeneration": 1,
      "nodePath": ".",
      "pixelIdentity": {"method": "iscc-bio/imagewalk", "role": "image"}
    },
    "returnedPixelIdentity": {
      "method": "iscc-bio/imagewalk",
      "role": "image"
    },
    "labelNodePaths": ["labels/labels_nuclei"],
    "labelComponents": [{
      "logicalNodePath": "labels/labels_nuclei",
      "source": null,
      "pixelIdentity": {"method": "iscc-bio/imagewalk", "role": "label"}
    }]
  }]
}
```

The actual identity objects also contain the ISCC codes, shape, dtype, axes,
coordinate transformations, tool version, and IMAGEWALK revision. A Plate has
one `images` entry for every retained field such as `A/1/0`; each entry points
to that field in the managed source Plate.

`source: null` on a label component means the label is stored locally in this
result. A managed source on a label component means it is inherited from an
earlier shallow result. This distinction lets chains such as nuclei
segmentation → cell expansion → measurement reconstruct all prior and new
labels without repeatedly storing their pixels.

The Zarr root also carries a small `biomero` pointer to the manifest, but the
sidecar is authoritative. A shallow root is not a synthetic black image: its
duplicated multiscale image arrays are absent. This avoids storing even a fake
pixel pyramid and prevents readers from mistaking zeros for scientific data.

## Pixel identity with ISCC-BIO

The BIOMERO Schema documentation provides the normative, field-by-field
[`PixelIdentity` reference](https://nl-bioimaging.github.io/biomero-schema/pixel-identity/),
including the exact equality predicate and a complete JSON example. This page
focuses on how that contract participates in shallow storage.

BIOMERO uses the experimental
[ISCC-BIO](https://github.com/bio-codes/iscc-bio) IMAGEWALK implementation.
IMAGEWALK traverses decoded level-0 bioimage planes deterministically and is
designed to identify the logical pixels independently of their container,
chunking, compression, extra pyramid levels, labels, and ordinary metadata
changes. In principle this also lets BIOMERO recognize the same pixels in a raw
format and in its canonical OME-Zarr representation.

For every image or label node BIOMERO records:

- the combined ISCC value, Data-Code, and Instance-Code;
- `shape`, `dtype`, axes, and coordinate transformations;
- the node role (`image` or `label`) and logical node path; and
- the ISCC-BIO version and IMAGEWALK implementation revision.

The current exact equality predicate compares the **Instance-Code** together
with the role, shape, dtype, axes, and coordinate transformations. Node paths
and aggregate/Data-Codes are not used to disambiguate otherwise identical
selected images. The task-local marker and ordered event snapshot provide that
mapping.

An embedded code is a claim, not proof that a workflow preserved the pixels.
BIOMERO therefore records the input identity before execution and recomputes
the returned pixels before removing anything. Copying a stale metadata field
does not make changed pixels eligible. This is not intended as adversarial
cryptographic attestation; it is a conservative decision about whether to keep
more or less of a reproducible derived result.

### Why TREEWALK is not the equality check

An ISCC-SUM TREEWALK over an entire Zarr answers whether the stored fileset is
bit-identical. It changes when chunks are recompressed or rechunked, metadata or
scales change, or labels are added—the exact changes a Zarr workflow may make
without modifying the original image pixels. It is therefore the wrong signal
for shallow eligibility.

TREEWALK remains interesting for future whole-store integrity,
deduplication, version tracking, or citation. Its convention excludes a
`.iscc.json` sidecar and supports `.isccignore`, avoiding a circular whole-store
identifier. The schema already leaves room for a separate `storeIdentity`, but
BIOMERO does not currently require one.

### Embedded `attrs.iscc`

The intended portable direction is to publish an IMAGEWALK identity in the
user attributes of each Image group—for Zarr v3, `attributes.iscc` as a sibling
of the versioned `attributes.ome` namespace. That makes a derived Zarr carry a
path-independent identity for its source. Current BIOMERO matching does **not**
assume this attribute exists: identities are held in the managed markers and
event provenance, and returned pixels are recomputed. Embedding and consuming
the group attribute consistently is remaining interoperability work and may
change with ISCC-BIO and NGFF guidance.

## Eligibility and failure behavior

The normalizer is intentionally conservative:

| Returned result | Storage outcome |
| --- | --- |
| Source pixels match and at least one local or inherited label exists | Store shallow collection. |
| Source pixels changed | Keep full returned Zarr. |
| Identity, source, field mapping, or schema is missing/ambiguous | Keep full returned Zarr. |
| Label-free pass-through duplicates only the input | Do not create a useless derived shallow result. |
| Feature flag disabled | Preserve the legacy full-result import path. |
| Importer integration disabled | Preserve the independent Get Results path. |

Normalization uses a same-filesystem rollback journal. Duplicate array
directories are moved into the journal first, the sidecar and remaining
metadata are committed, and only then is the journal deleted. A failure before
commit restores the result. The full managed source is read-only throughout.

## Images, Plates, and OMERO representation

For an Image result, BIOMERO can register retained label nodes as separate
viewable OMERO Images. This makes masks available to today's PixelBuffer and
iViewer and permits optional conversion to ROIs. The authoritative shallow
collection stays in `.analyzed`; the OMERO objects carry compact managed
references and provenance rather than a copy of the entire manifest.

For a chained result, the importer projects locally new or changed labels by
default. Unchanged inherited labels remain in the shallow manifest and are
included in later reconstruction, but do not create duplicate OMERO mask
Images. An explicit re-projection option may be added later for users who need
another OMERO view of an inherited mask.

For a Plate, labels live below each Plate image/field in NGFF. Importing every
label from a large Plate as unrelated Images would lose the useful Plate
organization and could create thousands of OMERO objects. BIOMERO therefore
keeps one authoritative derived Plate representation. It can register:

- a source-backed Plate whose ordinary pixels come from the original managed
  Zarr; and
- optionally, a label-backed Plate preview when one requested label name is
  present consistently across the fields.

The preview is a convenience for current OMERO viewing, not another authority.
Native label overlays and complete RFC 8 traversal depend on future OMERO and
viewer support. Per-field identities and mappings remain in the storage
sidecar; OMERO gets one compact Plate-level reference instead of hundreds or
thousands of repeated key-value annotations.

## Compatibility profile

BIOMERO currently exchanges **OME-NGFF 0.4 on Zarr v2**. This is determined by
the deployed Glencoe exporter/importer tooling and the OMERO Zarr PixelBuffer
that must serve registered pixels; accepting a newer, valid NGFF version in one
component would not help if the rest of the OMERO path could not read it.

Workflows do not need to know about BIOMERO's shallow-storage representation.
They receive a complete Zarr—including its labels—and should consume its image
or label members according to their own declared analysis contract. They return
an ordinary, valid OME-Zarr in the supported profile. BIOMERO inspects and
optimizes that result only after the workflow has finished. BIOMERO will advance
the profile as Glencoe and OMERO releases add compatible support. The private
shallow reader remains versioned so older managed results can be reconstructed
during such a transition.

## Operational trade-off: storage versus import time

Shallow normalization trades importer CPU and storage I/O for lower persistent
storage use. It is opt-in because a deployment with small results or a slow,
metadata-heavy filesystem may value latency more than the saved capacity.

The current production-path Plate benchmark used an 18-field Plate returned by
a Zarr-to-Zarr segmentation workflow, with one new label per field and 1,722
files. It ran inside the Linux importer container against the real `/data`
mount; preparing disposable benchmark copies was excluded.

| Measurement | Result |
| --- | ---: |
| Full returned Plate | 146,143,912 bytes |
| Stored shallow Plate | 10,775,929 bytes |
| Storage removed | 135,367,983 bytes (92.6%) |
| Read-only ISCC-BIO verification | 12.653 s mean |
| Transactional normalization | 12.729 s mean |
| **Added importer processing** | **about 25.4 s** |

The first diagnostic implementation took roughly 196 seconds to normalize the
same Plate. Same-filesystem moves, avoiding a copy of the retained label tree,
and avoiding recursive before/after byte scans reduced normalization to 12.7
seconds.

The following observations put the Plate benchmark alongside the live Image
paths tested so far. ``Estimated full`` means the size of the pixels and label
components if they were materialized together; production deliberately skips
an exact recursive pre-normalization size scan because that scan can cost more
than normalization itself.

| Scenario | Logical content | Full or estimated full | Stored shallow | Storage avoided | Return-path shallow processing | Outbound reconstruction |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 18-field Plate benchmark | 18 fields, one new label per field | 146,143,912 bytes | 10,775,929 bytes | 135,367,983 bytes (92.6%) | 25.4 s mean | not measured |
| Five-Image live batch | five Images with new and inherited labels | 28.463 MiB estimated | 2.319 MiB | 26.144 MiB (91.9%) | about 10 s total | not measured |
| Multi-generation Image chain | one Image, five inherited labels and four new labels | 8,956,291 bytes estimated | 990,300 bytes | 7,965,991 bytes (88.9%) | 19.7 s observed | 7.6 s observed |
| Earlier individual Image | one Image result | 6,848,883 bytes | 185,072 bytes | 6,663,811 bytes (97.3%) | not measured | not measured |

The multi-generation observation started from one shallow Image referencing
canonical intensity pixels and five inherited label layers. A Zarr-to-Zarr
segmentation reconstructed that complete collection and appended four new
labels. Reconstruction took 7.6 seconds. On return, the importer spent 18.3
seconds evaluating image and label identities with four workers and 1.4
seconds transactionally retaining only the four new layers. The five inherited
label directories were absent from the new physical store but remained present
as managed components in `.biomero-shallow.json`. Only the four new labels were
registered as new OMERO Images. The estimated 8,956,291-byte full footprint is
the sum of the referenced canonical pixels and all nine logical label
components, not a recursive pre-normalization tree scan. This is one warm-system
observation rather than a statistically stable benchmark.

A later live run processed five Image results with both new and inherited
labels. Their estimated full size was 28.463 MiB and their stored shallow size
was 2.319 MiB: 26.144 MiB, or **91.9%**, was avoided. Importer identity and
normalization work took approximately 10 seconds in total with four workers.
One earlier individual Image example occupied 185,072 bytes shallow versus a
6,848,883-byte full source Zarr, a 97.3% size difference; that individual
observation did not include a comparable end-to-end timing.

### Parallel identity workers and scaling

`BIOMERO_SHALLOW_ZARR_WORKERS` controls a bounded importer thread pool for
per-image and per-label identity generation. It defaults to `4` in the
NL-BIOMERO deployment. Discovery, transactional moves, and journal deletion are
not parallelized.

A preliminary read-only sweep of the 18-image/18-label Plate produced:

| Workers | Verification time |
| ---: | ---: |
| 1 | 14.524 s mean |
| 2 | 11.988 s mean |
| 4 | 9.401 s mean |
| 8 | 12.569 s observed |
| 16 | 13.857 s observed |
| 32 | 13.201 s observed |

Four workers performed best on this development mount. Higher counts increased
I/O contention, and variance was material. Sites should benchmark their own
storage with 1, 2, and 4 workers before increasing the value.

The 18-field result does not establish linear scaling. A deliberately crude
linear extrapolation of 25.4 seconds would be about 24 minutes for 1,000 equally
sized fields. Actual time depends on decoded pixel volume, label and file
counts, chunking, cache state, filesystem metadata latency, and concurrent I/O;
a very large or badly chunked Plate could still take hours. A representative
large-Plate benchmark remains necessary before broad production enablement.

## Enabling and observing the feature

The NL-BIOMERO Compose deployment uses:

```text
IMPORTER_ENABLED=true
BIOMERO_SHALLOW_ZARR=true
BIOMERO_SHALLOW_ZARR_WORKERS=4
```

`BIOMERO_SHALLOW_ZARR` defaults off, preserving the old export/import behavior.
The worker flag crosses the OMERO processor environment allow-list; the worker
count belongs to the importer service. Shallow processing also requires the
BIOMERO.importer `identity` extra, which supplies ISCC-BIO. The shipped
NL-BIOMERO importer image installs that extra. A custom importer installation
must use `pip install "biomero-importer[identity]"`; when it is absent, the
importer reports the missing capability and rejects only shallow lifecycle
orders while ordinary imports continue. Monitor image/field count, label count,
bytes before and after, identity time, normalization time, and total import
time. Disable the feature if its measured latency is not justified by the
storage saved.

Useful logs distinguish:

- calculation versus reuse of canonical source identities;
- the selected source and transfer marker;
- `eligible (input-image-unchanged)` versus a conservative keep-full reason;
- identity generation and normalization durations; and
- stored full versus shallow outcomes.

## Validation status

The feature branch has verified the following live paths:

- full canonical creation and later reuse during Image Transfer;
- ordered event provenance and task-local markers, including five selected
  Images with identical pixels and renamed outputs;
- five Image results normalized to 91.9% smaller shallow collections while
  retaining multiple and inherited labels;
- label-Image registration, non-image attachments, and ROI creation for those
  Image results;
- an 18-field Plate normalized to 92.6% smaller storage, with one compact
  derived Plate reference and optional label-backed preview;
- a complete chained Zarr workflow: five inherited labels were reconstructed,
  four appended labels were retained, unchanged inherited label chunks were
  referenced rather than copied, and only the four new labels became OMERO
  Images;
- focused reconstruction of a shallow Image into a temporary full Zarr;
- a live and unit-covered TIFF-bound exception, where a selected shallow label
  Image is exported from its registered OMERO PixelBuffer instead of being
  reconstructed with the original pixels; and
- compatibility readers/tests for older event streams and absent optional
  shallow settings.

The following remain release gates or scale validation:

- a live changed-pixel Image and changed-pixel Plate must remain full;
- a full canonical Zarr that already contains labels must be repeated live
  after the canonical-input inventory regression fix; unit coverage verifies
  that an empty preliminary inventory now triggers label discovery;
- feature-off behavior and importer-disabled Get Results need live controls;
- unsupported/newer NGFF input must fail or fall back clearly; and
- a representative large high-content Plate needs storage-local timing and
  capacity measurements.

## Expected evolution

The present contract fixes `schema: 1`, `model: "rfc8-shallow-copy"`, and the
`ngff-0.4-zarr-v2` interchange profile. Recorded identities also pin the
ISCC-BIO version and IMAGEWALK revision because ISCC-BIO is itself early-stage.

Likely future changes include migration toward a released NGFF Collections
model, newer Zarr/NGFF profiles as OMERO PixelBuffer support advances,
standardized embedded Image identities, object-store-aware references, and
asynchronous or differently scheduled processing for very large Plates. Those
changes should be introduced through new schema/profile versions and upcasters,
not by silently changing the meaning of existing managed results.

## Further reading

- [BIOMERO Schema: Zarr contracts](https://nl-bioimaging.github.io/biomero-schema/zarr-contracts/)
- [BIOMERO Schema: Pixel identity](https://nl-bioimaging.github.io/biomero-schema/pixel-identity/)
- [OME-NGFF RFC 8: Collections and Extensibility](https://ngff.openmicroscopy.org/rfc/8/)
- [ISCC-BIO and IMAGEWALK](https://github.com/bio-codes/iscc-bio)
- [IEP-0017: TREEWALK](https://ieps.iscc.codes/iep-0017/)
- [IEP-0018: IMAGEWALK](https://ieps.iscc.codes/iep-0018/)
