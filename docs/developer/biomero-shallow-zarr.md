# Working with shallow OME-Zarr results

```{raw} html
<style>
.wy-nav-content { max-width: 1100px; }
.wy-table-responsive table { width: 100%; table-layout: fixed; }
.wy-table-responsive table td, .wy-table-responsive table th { white-space: normal; }
.wy-table-responsive code { overflow-wrap: anywhere; }
</style>
```

BIOMERO stores a workflow result as **retained data plus references to unchanged
managed pixels**. The result remains a distinct OMERO Image or Plate with its
own provenance. Storage is saved on the shared filesystem, without deleting the
source or suppressing result registration.

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
| `.biomero-shallow.json` | Which image/label nodes exist, which arrays were omitted, and their source storage roots, paths, generations and identities |
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

A **canonical Zarr** is the stable managed pixel source and identity record used
to compare later workflow results. Establishing it runs during input transfer
when shallow storage is enabled and an eligible canonical record is missing.
Yellow steps below mark ISCC-BIO pixel reads.

```{mermaid} ../_diagrams/shallow-canonical.mmd
```

| Starting point | Pixel calculation | What canonical registration changes |
| --- | --- | --- |
| Existing authoritative backing Zarr | ISCC-BIO reads that store directly; per-image/field and label identities | Adds the marker and OMERO source records in place; no new pixel copy |
| Eligible fresh OMERO export | ISCC-BIO compares OMERO pixels with exported pixels | Commits the verified export to stable managed canonical storage and attaches source records |
| Valid canonical already registered | Reuses cached identities for that generation | Records the workflow's input snapshot; no repeated source hash |

Only the matching generation is reused. A temporary format-mismatch export or
TIFF conversion input is not promoted. Failed indexing/promotion leaves the
full workflow input usable without deduplication for that selection. Missing
dependencies of a shallow input must be resolved before it can be reconstructed.
Returned pixels are calculated again at the return-side comparison shown above.

## When verification runs

| Route | Order |
| --- | --- |
| Shallow off | Workflow → full ZIP → transfer → full result registration |
| Shallow on, remote | Workflow → HPC verification/pruning → smaller ZIP → transfer → receipt validation → registration |
| Shallow on, local | Workflow → full ZIP → transfer → importer verification/pruning → registration |

| Responsibility | Implementation |
| --- | --- |
| Pixel traversal and codes | [bio-codes / ISCC-BIO](https://github.com/bio-codes/iscc-bio), through `iscc_bio.api.biocode`; IMAGEWALK reads decoded highest-resolution pixels per image/field or label |
| Equality decision | BIOMERO compares `instanceCode`, role, shape, dtype, axes and coordinate transformations |
| Storage, transactions and references | BIOMERO.shallower; shared contracts from biomero-schema |
| HPC orchestration and OMERO registration | BIOMERO core/scripts and BIOMERO.importer, respectively |

The aggregate ISCC and similarity-oriented Data-Code are recorded but **do not
authorize removal**. A checksum of the complete Zarr file tree is not an
equality key. Returned identities are computed from pixels rather than trusted
from workflow metadata. See the [exact comparison contract](https://nl-bioimaging.github.io/biomero-schema/pixel-identity/).

Highest-resolution equality is the preservation criterion: lower-resolution
pyramids are reused from the source, not independently compared. This preserves
the scientific pixel representation checked by the method, rather than every
byte or pyramid rendering of the returned store.

| Condition | Action |
| --- | --- |
| Shallow storage disabled; ordinary upload; TIFF result | No shallow operation |
| Input/output Zarr profiles differ | Keep full; check format metadata before pixel hashing |
| Eligible collection with matching image identities | Omit duplicate image pyramids; reference matching inherited labels; retain new/changed labels |
| Changed image, unsupported identity, incomplete or ambiguous match | Keep the full collection |
| Invalid receipt, missing referenced source or unresolved transaction | Stop and preserve evidence for recovery; absent pixels cannot be treated as a full result |

Pruning uses same-filesystem moves and a rollback journal before committing the
manifest. Source pixels remain untouched. See [configuration and recovery](../sysadmin/remote-shallower.rst).

## Results: measured benefits and costs

[![Retained Zarr storage and recorded elapsed time for small, medium and large Plates. Large Full excludes its explicit recovery wait; all other recorded phases remain.](../_static/figures/shallow-results.svg)](../_static/figures/shallow-results.svg)

**Full v3 versus remote-shallow v2; lower is better.** Bars show reported means
for 10, 3 and 1 technical repetitions per configuration, respectively. Storage
is the sum of retained compressed Zarr file sizes before cleanup, excluding
existing shared source data and non-Zarr output. GB is decimal. Dispersion was
not supplied with the summary, so error bars cannot be reconstructed.
The configurations differ in source format and input preparation as well as
shallowing; differences cannot be attributed to shallowing alone.

| Plate images | Full Zarr | Shallow Zarr | Avoided result storage | Recorded elapsed time: Full → shallow |
| --- | --- | --- | --- | --- |
| 18 | 0.164 GB | 0.026 GB | **84.5% / 0.139 GB** | 14.0 → 12.9 min |
| 846 | 7.902 GB | 1.289 GB | **83.7% / 6.613 GB** | 175.3 → 190.2 min |
| 2,844 | 26.438 GB | 2.772 GB | **89.5% / 23.667 GB** | 1,166.5* → 625.9† min |

**\* Large Full is adjusted recorded time, not an uninterrupted-run estimate.**
Its reported 4,012.72 min includes 2,846.23 min explicitly recorded as failed
state / awaiting manual recovery. Only that interval is removed in the figure:
4,012.72 − 2,846.23 = **1,166.49 min**. The remaining 454.82 min of analysis
submission/polling/validation and 431.55 min of orchestration gaps are retained
within grey “other work and waiting”; they are not analysis compute. Its
0.12-minute return stage records an interrupted attempt, not a complete
successful return. These boundaries prevent a reliable large-Plate end-to-end
speedup claim. **† Large shallow used repaired source provenance.** Its measured
stages remain useful, with that qualification.

### Where time is spent

| Stage (minutes) | 18 Full / shallow | 846 Full / shallow | 2,844 Full / shallow |
| --- | --- | --- | --- |
| Input preparation, including canonical staging | 0.96 / 0.63 | 30.65 / 35.30 | 96.73 / 180.23 |
| Analysis execution | 3.16 / 2.94 | 62.05 / 69.14 | 152.65 / 153.95 |
| Remote shallower execution | — / 0.23 | — / 14.88 | — / 110.42 |
| Result return, packaging and extraction | 3.34 / 2.84 | 78.13 / 66.02 | Interrupted / 168.83 |

Input preparation sums compatibility/conversion, canonical preparation and other
input preparation/transfer. Canonical preparation includes validation where no
isolated boundary was available. Figure B stacks these stages with remaining
work and waiting; source indexing/staging costs are included in the recorded
workflow time. Scheduler queues remain included, separately from execution in
the data file. Shared storage, cache history and concurrent HPC activity affect
these measurements; technical repetitions do not establish biological power.

At medium scale, return/packaging/extraction fell by **12.11 min**, but the
complete workflow took **14.87 min longer (+8.5%)**. On the large shallow run,
canonical preparation alone took **180.10 min**, remote shallower execution
**110.42 min**, and result return/packaging/extraction **168.83 min**, alongside
**153.95 min** of analysis. Storage savings therefore come with substantial
processing and data-handling costs; they do not imply faster result delivery.
The supplied campaign summary does not isolate network transfer time or
provide CPU allocation/billing figures.

Reproduce the figure: [measurement data](../_figures/data/shallow-plate-comparison.json),
[plotting script](../_figures/shallow_methods.py),
[campaign plotting module](../_figures/shallow_campaign.py),
[instructions](../_figures/README.txt).
The data preserve all six reported totals and phase breakdowns, including the
large Full recovery wait; exclusion is a plotting rule, not a change to evidence.

### Earlier local versus remote comparison

A separate historical 846-image pair used cached source identities and compared
local with remote shallowing, both v2. It retained **1.90 / 1.91 GB**, versus
**8.35 GB** of complete Full output, including measurements and metadata
(**77.3% / 77.1% avoided**). This is a different storage scope from the Zarr-only
campaign above. The return ZIP was **87.6% smaller** remotely; measured HPC
copy plus ZIP validation took **81.0 → 11.1 s**. This combined stage is not
isolated network throughput.

Return-side shallowing/validation took **107.1 → 15.5 min**, while complete
submission-to-DONE time took **318.3 → 303.8 min** under variable storage load.
A separate Full workflow was not timed in that pair, so it does not measure net
shallowing overhead. Fresh indexing took **34.6 min** separately and is excluded
from those cached-input totals. See the [historical measurements](../_figures/data/shallow-846-image.json)
and [local/remote operational comparison](../sysadmin/remote-shallower.rst).

(reconstruct-shallow-zarr-on-disk)=
## Reuse, reconstruction and storage accounting

| Next use | Representation supplied |
| --- | --- |
| Same-format native Zarr workflow | Reconstructed full Zarr, including inherited and new labels |
| Different-format workflow | Normal export of selected OMERO pixels; inherited labels are not reconstructed and canonical matching is disabled for that run |
| TIFF workflow on a mask Image | Selected mask pixels through the existing v2-to-TIFF route |
| External sharing | Explicitly reconstructed, self-contained Zarr |

V2 / OME-Zarr 0.4 and v3 / OME-Zarr 0.5 remain distinct profiles. Existing stores
keep their format; native workflows default to v2 and opt into v3 individually.
A shallow directory is a private BIOMERO representation, not standalone
OME-Zarr or an RFC 8 Collection.

The existing [standalone reconstruction recipe](https://github.com/NL-BioImaging/BIOMERO.shallower#reconstruct-a-full-zarr)
creates a full Image or Plate at a **new destination**, preserving its format
and leaving OMERO registrations unchanged. It needs all referenced stores and
enough free space. This is a materialized copy, not an in-place undo command.

Operation reports support optional `bytesBefore` / `bytesAfter` measurements
(`--benchmark-bytes` for standalone normalization). Normal runs omit these to
avoid extra filesystem scans. Where measured, **avoided result bytes = before
− after**; archive savings and allocated filesystem space require separate
measurements. A retrospective audit cannot report an exact original result size
when that measurement was never recorded.
