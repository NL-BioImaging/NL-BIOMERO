# BIOMERO shallow OME-Zarr

```{warning}
BIOMERO shallow OME-Zarr is an experimental, internal storage contract. It is
inspired by the shallow-copy use case in OME-NGFF RFC 8, but a
`.biomero-shallow.json` file is **not** an RFC 8 Collection and must not be
advertised as portable OME-NGFF metadata. The current wire contract is schema
1 and is expected to evolve through versioned readers and upcasters.
```

This page documents why BIOMERO stores some workflow results as shallow
OME-Zarr collections, how those collections are reconstructed at workflow
boundaries, and how ISCC-BIO IMAGEWALK identities make the storage decision
safe.

## Status and scope

This page will distinguish three things that are intentionally related but not
interchangeable:

1. the collection and shallow-copy concepts proposed by
   [OME-NGFF RFC 8](https://ngff.openmicroscopy.org/rfc/8/);
2. the private BIOMERO storage and service contract represented by
   `.biomero-shallow.json`; and
3. the portable pixel-content identities produced by
   [ISCC-BIO](https://github.com/bio-codes/iscc-bio).

The feature is opt-in through `BIOMERO_SHALLOW_ZARR`. Disabling it preserves
the conventional full-result import path.

## Why BIOMERO uses shallow results

<!-- Explain duplicated source pixels in Zarr-to-Zarr workflows and the
read-only managed-storage model. -->

## Operational trade-off: storage versus import time

Shallow normalization exchanges importer time and storage I/O for lower
persistent storage use. Enabling the feature is therefore a deployment choice,
not a format requirement. The work runs in BIOMERO.importer, so it can continue
after the initiating OMERO.web session ends, but the result remains in its
importing state until identity verification and normalization finish.

The current production-path benchmark used an 18-field A1/B1 Plate returned by
`cisegmentation`. It contained one label image per field and 1,722 files. The
test ran inside the Linux importer container against the real `/data` mount;
preparing disposable benchmark copies was excluded.

| Measurement | Result |
| --- | ---: |
| Full returned Plate | 146,143,912 bytes |
| Shallow Plate | 10,775,929 bytes |
| Storage removed | 135,367,983 bytes (92.6%) |
| Read-only ISCC-BIO verification | 12.653 s mean |
| Transactional production normalization | 12.729 s mean |
| **Added importer processing** | **about 25.4 s** |

Production normalization moves duplicate array directories into a rollback
journal on the same filesystem and then deletes the journal. It does not copy
the retained label tree and does not recursively scan both trees merely to
report byte totals. Those two changes reduced the original diagnostic
implementation from roughly 196 seconds to 12.7 seconds for normalization.

An existing single-Image example shows the same storage tendency: its shallow
label result occupies 185,072 bytes while its referenced full source Zarr
occupies 6,848,883 bytes, a 97.3% reduction. This is a storage observation only;
no comparable end-to-end timing was recorded for that Image, so it must not be
used as a latency benchmark.

**Pending benchmark:** run one label-producing workflow for both a single Image
and a group of Images. Report first-time canonical export separately from a
repeat run that reuses the canonical Zarr, then split the return path into NGFF
discovery, source/label identity generation, normalization, deletion and total
import time. Record full and shallow bytes and file counts for each case.

### Scaling and parallel identity workers

The Plate benchmark does **not** prove linear scaling. As a deliberately rough
illustration, linear extrapolation of 25.4 seconds for 18 fields would be about
24 minutes for 1,000 equally sized fields. Real results may be faster or much
slower because decoded pixel volume, label count, chunk/file count, filesystem
metadata latency, cache state and concurrent storage traffic all matter. Very
large or badly chunked Plates can therefore still take hours. A representative
large-Plate benchmark is required before enabling the feature broadly at a
site.

Image and label identities can be calculated concurrently. The importer-only
environment variable `BIOMERO_SHALLOW_ZARR_WORKERS` controls a bounded thread
pool and defaults to `1`. It affects identity generation only; discovery,
transactional moves and journal deletion are not parallelized.

A preliminary read-only sweep of the same 18-image/18-label Plate produced:

| Identity workers | Verification time |
| ---: | ---: |
| 1 | 14.524 s mean |
| 2 | 11.988 s mean |
| 4 | 9.401 s mean |
| 8 | 12.569 s observed |
| 16 | 13.857 s observed |
| 32 | 13.201 s observed |

Four workers performed best on this development mount, but run-to-run variance
was large and higher counts became slower through I/O contention. Parallelism
therefore mitigates identity time but does not remove the scaling risk. Keep the
default until the production storage backend has been benchmarked with 1, 2, 4
and, if useful, more workers.

### When to enable it

The feature is most useful when workflows commonly copy large unchanged images
or Plates while adding relatively small labels, and when the same source is
processed repeatedly. It is less attractive for latency-sensitive facilities,
small results, slow metadata-heavy mounts, or workflows that normally change
the source pixels: those workflows still pay the verification cost but are
correctly retained in full and gain no result-storage reduction.

For the NL-BIOMERO Compose deployment the explicit starting configuration is:

```text
BIOMERO_SHALLOW_ZARR=true
BIOMERO_SHALLOW_ZARR_WORKERS=1
```

The feature flag is consumed across the BIOMERO transfer/import boundary. The
worker-count setting belongs to BIOMERO.importer and should be increased only
after a storage-local benchmark.

Monitor at least image/field count, label count, bytes before and after,
identity time, normalization time and total import time. Disable the feature or
reduce worker concurrency if the measured import delay is not justified by the
storage saved.

## Lifecycle: full input, shallow storage, full input again

<!-- Document canonical discovery/promotion, importer-owned return-side
normalization, OMERO registration, and transfer-time reconstruction. -->

## Relationship to OME-NGFF RFC 8

### What BIOMERO emulates

<!-- Collection contains derived data and links to unchanged source images;
source data remain read-only; output can be viewed and processed together. -->

### What is BIOMERO-specific

<!-- Sidecar name/schema, managed storage roots, OMERO IDs/generations,
event-store snapshots, Plate mapping, registration projections. -->

### What is not claimed

<!-- Not an RFC 8 Collection, not a new OME-NGFF version, not a format that a
generic reader is expected to understand. -->

## Pixel identity with ISCC-BIO

### IMAGEWALK is the source-pixel identity

<!-- Decoded level-0 planes, Z-C-T traversal, format-independent comparison,
data/instance/composite codes, semantic guards, pinned generator revision. -->

### TREEWALK is not used for source-pixel equality

<!-- A whole-store code changes with chunks, codecs, metadata, scales, and
labels. Document the possible future storeIdentity integrity role. -->

### Claims, recomputation, and deletion safety

<!-- Embedded attrs.iscc is a portable claim/cache. The authoritative input
snapshot is recorded before execution; BIOMERO recomputes returned pixels. -->

## The `.biomero-shallow.json` schema

<!-- Add a compact annotated Image example and a Plate fragment. Document
ShallowCollection, ShallowImageReference, CanonicalZarrSource,
ZarrLabelComponent, and PixelIdentity. -->

## Images, labels, and Plates

<!-- Explain local versus inherited label components, per-field Plate
identity, source-backed Plate registration, and optional label-backed preview.
-->

## OMERO representation

<!-- Explain compact MapAnnotations as indexes, the storage sidecar as
authority, PixelBuffer limitations, and label Image/Plate projections. -->

## Compatibility profile

BIOMERO currently exchanges OME-NGFF 0.4 on Zarr v2 because the deployed
Glencoe exporter and OMERO Zarr PixelBuffer must both be able to serve the
result. This profile will advance as those dependencies and OMERO support newer
OME-NGFF and Zarr releases.

## Versioning and expected migration

<!-- Document schema versioning/upcasting, RFC 8/NGFF 1.0 migration intent,
ISCC-BIO 0.1 instability, interchange-profile evolution, and preservation of
old managed results. -->

## Failure behavior and operational controls

<!-- Conservative keep-full rules, importer capability gate, worker count,
logging, retry behavior, and importer-disabled Get Results. -->

## Worked example

<!-- Use a redacted/shortened form of the 18-image cisegmentation Plate
manifest from workflow 77d5452c. Explain matching returned/source codes,
canonical-bootstrap, canonicalPixelVerified, and local label components. -->

## Further reading

- [OME-NGFF RFC 8: Collections and Extensibility](https://ngff.openmicroscopy.org/rfc/8/)
- [ISCC-BIO](https://github.com/bio-codes/iscc-bio)
- [IEP-0017: deterministic Treewalk](https://ieps.iscc.codes/iep-0017/)
- [Zarr workflow provider guidance](zarr-workflow-provider-guidance.md)
