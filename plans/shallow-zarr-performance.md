# Faster shallow OME-Zarr: pixel fingerprints and workflow declarations

Status: proposal for implementation before the final 1.8 release. This document
changes no runtime behaviour, dependencies, defaults or deployed services.
The workflow-declaration shortcut is a separately deliverable extension; it
must not hold up the pixel API, pyramid comparison and documentation work.

## Outcome

Keep the storage savings of shallow results while reducing the work between
GPU analysis and researchers receiving their results. Remove the unused raw
store checksum, compare existing small-resolution pixels, and describe exactly
which ISCC-BIO functionality BIOMERO uses. Capture automatic interpretation of
workflow outputs and a separate per-workflow setting to avoid pixel comparison
when original image arrays need not be returned.

Shallowing remains subject to the existing feature enablement. Unsupported or
unmatched results continue through the full-result import route. Preserve all
new labels, measurements and derived images. A derived image may occupy an
ordinary image array: its location does not make it an unchanged original.

## 1. Use the pixels-only ISCC-BIO API

Replace the filesystem provider's high-level `iscc_bio.api.biocode(source)`
call with `iscc_bio.biocode.generate_biocode(planes)`. Feed decoded planes
directly from the selected Zarr array, retaining the upstream canonical pixel
encoding and hashing implementation. No fork is required for this change.

The high-level local-file API produces two different things: a raw-byte
ISCC-SUM over the source file/store, and per-scene pixel codes under `parts`.
BIOMERO currently consumes the latter. The lower-level pixel API avoids the
unused whole-store read. ISCC-SUM itself does not imply either raw files or
decoded pixels; that distinction depends on the supplied byte stream.

- Keep code generation deterministic: separate image/field identities,
  IMAGEWALK Z -> C -> T traversal, row-major YX and big-endian pixel bytes.
- Preserve existing full-resolution Instance-Codes when the same decoded
  pixels are supplied; establish this with regression fixtures.
- Support OME-Zarr v2/0.4 and v3/0.5, including numeric and `sN` dataset paths.
- Read the managed source directly. Do not export another copy just to compare
  it with the authoritative backing Zarr.
- Apply the removal of raw-store hashing to image and label identities.
  Lower-resolution image comparison does not automatically change the label
  deduplication policy.

## 2. Compare the coarsest compatible stored pyramid level

For original image arrays, fingerprint the coarsest compatible stored level,
rather than the full-resolution array. Select through NGFF metadata and array
dimensions, not directory naming or a fixed 256-pixel threshold. Read existing
numerical pixels; do not generate a rendered thumbnail or a new pyramid.

- Process every channel, Z slice and timepoint of the selected level. Define
  compatibility explicitly so level selection does not silently omit C/Z/T
  coverage. Preserve the full-resolution semantic checks as well.
- Source and returned fingerprints must describe comparable resolutions,
  shapes, dtype, axes and coordinate transforms. Different folder names alone
  must not prevent a match. Do not compare each store's independently chosen
  smallest array without checking compatibility.
- A single-level image uses pixels-only full-resolution comparison. If a
  compatible comparison cannot be established, retain the full result. Do not
  add resampling or Zarr-format conversion to this work.
- Preserve the cheap v2/v3 format mismatch shortcut and perform field/layout
  and semantic checks before reading pixels.
- Stop scheduling additional field identities when no candidate canonical
  input can still match. Keep concurrency bounded; account for already running
  work and multiple possible input candidates.

This is an intentional approximation of full-image equality. Equality of
selected-level bytes is exact; using it to infer unchanged full-resolution
pixels is BIOMERO's deduplication policy. Workflows are expected to return
consistent image pyramids. Do not describe the result as a full-resolution
pixel-equality proof or as perceptual ISCC matching.

### Current profile and stale canonical records

Introduce an explicit versioned comparison profile in the shared contracts.
Record the selected resolution's dataset path, shape and transforms alongside
the original image semantics, code lengths and implementation versions.
Dataset paths identify what was read; compatibility must not require identical
path spelling. Treat this profile as BIOMERO-specific, not a new ISCC standard.

Use one current comparison contract/profile. When a cached canonical record
has an old or missing profile, treat the identity as stale and regenerate the
record using the new pixels-only, selected-resolution method. Read the same
authoritative backing Zarr; stale identity metadata is not a reason to export,
copy, convert or reimport it. Cache the refreshed record for subsequent runs.
An already imported Zarr without any canonical identity follows this same
indexing route when its backing-store provenance is available.

Do not maintain parallel full-resolution and pyramid identity caches, preserve
the slow algorithm for legacy records, or interpret a missing profile as a
request for full-resolution verification. Never relabel or compare codes from
different profiles. Full-resolution pixel hashing remains necessary only for
cases such as a single-level image, not to preserve obsolete cache semantics.

`PixelIdentity` was already included in published `biomero-schema 0.2`; the
later `0.3.0b2` is a prerelease. Version the changed contract/profile explicitly
so stale records are recognized rather than silently reinterpreted. The final
NL-BIOMERO 1.8 release has not shipped: preserving every earlier development
identity or shallow-manifest variant is not a requirement for this work.
Handle any incompatible prerelease test fixtures explicitly instead of adding
a permanent legacy comparison path. Invalidating a record must not delete the
physical source or retained label stores.

Do not force v2 sources into v3. Source format reuse and requested export
format continue to follow the existing route: an incompatible canonical format
uses normal export, with full results where shallowing cannot match.

## 3. Document the actual ISCC-BIO support

Use **resolution-specific pixel fingerprint using ISCC-BIO** for the new
comparison. If the internal model remains named `PixelIdentity`, explain its
profile and scope. Document these distinctions in the shared schema and
shallower references, then link the administrator and developer documentation
to the same explanation.

| Component | Intended BIOMERO use |
| --- | --- |
| IMAGEWALK traversal and canonical pixel encoding | Used for planes at the selected resolution |
| ISCC Instance-Code | Equality comparison of those canonical pixel bytes |
| ISCC Data-Code and composite ISCC-SUM | Generated by the pixel API and retained; Data-Code similarity does not authorize removal |
| Raw file/store ISCC-SUM | Not calculated for shallowing |
| Experimental Imagecode, perceptual Image-Code, Mixed-Code and thumbnail rendering | Not used by this comparison |

Proposed methods wording, to publish only after implementation:

> When pixel comparison is required, BIOMERO generates a resolution-specific
> pixel fingerprint for each OME-Zarr image or Plate field using ISCC-BIO.
> It reads the coarsest compatible stored
> pyramid level and processes its planes in IMAGEWALK Z -> C -> T order, with
> row-major, big-endian pixel encoding. BIOMERO compares the resulting ISCC
> Instance-Codes together with image metadata and comparison-profile
> compatibility. Matching fingerprints establish agreement at the selected
> resolution; BIOMERO uses this agreement as its criterion for replacing
> duplicate returned image arrays with references to the canonical source.
> No raw file-tree checksum is calculated.

Record the exact library and comparison-profile versions for reproducibility.
Identify IMAGEWALK IEP-0018 as a draft specification and pyramid selection as
BIOMERO policy. Provide citations for both ISCC-BIO and the BIOMERO version;
avoid implying certification of the entire pipeline against the ISCC standard.

Admin documentation should explain the comparison scope, existing feature
enablement, fallback and operational costs. Developer/methods documentation
should specify the algorithm, contract and recorded provenance. Keep proposed
behaviour out of the current released-feature instructions until it exists.

## 4. Interpret outputs automatically; offer a separate workflow setting

Use the following decision order. These are proposed behaviours, not features
implemented by this planning PR.

| Condition | Result handling |
| --- | --- |
| Shallow storage is disabled | Keep full results; no shallow pruning or deduplication-only fingerprint work |
| Shallow storage is enabled and usable RO-Crate output evidence exists | Interpret it automatically, without an admin toggle or workflow allowlist |
| No usable output evidence, but the workflow's admin setting says original pixels need not be returned | Reuse the known input and skip original-pixel comparison for that workflow |
| No usable evidence or workflow setting | Use the pixels-only, compatible-pyramid equality checks; keep full results when matching cannot succeed |

### Automatic RO-Crate handling

Recognized, consistent RO-Crate output links are sufficient evidence to select
the relevant result handling. This is ordinary upgraded behaviour within
enabled shallow storage: do not introduce a separate opt-in, per-workflow
approval, allowlist or signature requirement for it.

For Joost's label-level output example, resolve the run's input through
BIOMERO's execution record, retain the declared label datasets and other
results, and link them to that known source. Skip comparing the enclosing
copied originals. No extra unchanged-pixels boolean is needed for this
labels-only case. The parent image copy does not need to be proven unchanged
because BIOMERO uses the authoritative input as the image background.

Keep cheap run/input/output binding and structural checks. A pointer to an
entire Zarr root alone does not identify which image arrays are derived
results. Missing or unusable evidence falls through to the workflow setting
or equality checks. Retain additional derived images and sidecars; do not
interpret an incomplete crate as an exhaustive file-deletion list.

### Independent administrator setting, with future Bilayers presets

Add a per-workflow setting whose meaning is: original image pixels need not
be returned for this workflow; use the known input and retain the derived
results. It supplies the shortcut when no usable RO-Crate evidence exists.
Administrators configure it like existing GPU and Zarr workflow settings, not
as a prerequisite for automatic RO-Crate handling. Leaving it unset or false
does not disable usable RO-Crate evidence. Disabling shallow storage is the
way to require full stored results.

A later input-descriptor integration may preset this same setting when
Bilayers explicitly describes the required output behaviour. Follow existing
OMERO.biomero conventions for descriptor-derived values, manual overrides,
explanation/tooltips and Runtime indication. Do not invent an unrelated GPU
parameter interpretation or present a proposed Bilayers field as implemented.
If new preservation vocabulary is needed, document it as an explicit
extension rather than claiming that it is already a Bilayers standard.

### Record the actual decision and support full stored results

Record the handling basis as RO-Crate output interpretation, administrator
workflow setting, descriptor-derived setting when implemented, or pixel
comparison. Include the executed workflow version and source/run binding for
provenance, without requiring a new admin approval for every workflow version.
Do not fabricate an Instance-Code or mark unmeasured pixels as verified.
Source-linked runs must not calculate otherwise unused source identities just
to populate mandatory fields. Keep label handling independent.

The existing shallow-storage enablement controls the whole feature. When it
is off, RO-Crate evidence and the workflow setting cannot cause original image
arrays to be removed. Full returned Zarrs stay self-contained for other tools.
If a labels-only result needs materialization to satisfy full-result storage,
assemble the source and labels using the reconstruction route rather than
silently storing a shallow reference. Document the implemented behaviour for
that case explicitly.

### Release documentation

At each release, document exactly which paths exist: supported RO-Crate output
forms, the actual admin setting, supported descriptor presets and the fallback
comparison method. Include the main shallow-storage off/full-results choice.
Publish future descriptor ideas only as roadmap material, not as available
configuration. Update the methods wording and recorded decision basis to match
the shipped behaviour; distinguish pixel comparison from source-linked output
interpretation or a workflow setting.

### Findings from the supplied output example

The reviewed example contains workflow configuration, actual parameters,
measurement CSV, `ro-crate-metadata.json` and an HTML preview. It does not
contain the image arrays. The JSON declares RO-Crate 1.3, Workflow RO-Crate 1.1
and Process/Workflow Run Crate 0.5 profiles; those declarations were inspected,
not formally validated.

Useful existing information:

- `CreateAction.instrument` points to the workflow configuration;
  `object` identifies a TIFF input and parameter values; `result` identifies
  an OME-Zarr output.
- `FormalParameter`, `PropertyValue` and `exampleOfWork` connect parameter
  definitions to actual values. These can support parameter-aware output
  interpretation without guessing from parameter defaults.
- The configuration identifies a container/tag, citations and a label output
  described as the input image with segmentation in OME-Zarr labels.

Information to resolve when interpreting the original root-level example:

- The scope of the returned results and a binding to BIOMERO's canonical
  source generation and current run. A label-level output can identify the
  derived content without an additional unchanged-pixels assertion.
- Array-level mapping for image/Plate fields and a separate treatment of
  outputs whose image pixels are derived results.
- The workflow/version from BIOMERO's execution record for provenance; no
  additional administrator approval or container attestation is required to
  interpret recognized RO-Crate output evidence.

The TIFF -> Zarr provenance and human-readable output description do not by
themselves assert unchanged numerical pixels. The actual Zarr was absent, so
no pixel or layout conclusion was tested. The CSV is present in the ZIP but is
not listed as a run result/data entity in its graph: retain such files and
improve enumeration rather than treating the crate as an exhaustive deletion
list. Do not infer preservation from segmentation-related parameter names.
Do not publish the original archive or its workstation paths in this PR.

### Joost's revised label-level output metadata

The subsequently supplied full `ro-crate-metadata.json` identifies the actual
produced dataset:

```json
{
  "@id": "1.ome.zarr/labels/empanada_seg_2d/",
  "@type": "Dataset",
  "exampleOfWork": { "@id": "#output" }
}
```

The revised metadata connects all three relevant links to that entity:

- The run's `CreateAction.result` identifies the label dataset.
- The dataset's `exampleOfWork` identifies the workflow's `#output` parameter.
- The crate root's `hasPart` includes the label dataset.

This locates the derived label content and binds the output parameter to its
execution, rather than designating the enclosing Zarr root as the result.
Local structural inspection found valid JSON, 50 uniquely identified entities
and no unresolved local entity references. This was not a full JSON-LD or
RO-Crate profile conformance validation. No accompanying Zarr was supplied;
NGFF image association and pixel layout were not checked.

With shallow storage enabled, BIOMERO should automatically interpret these
usable label output links and avoid comparing the enclosing copied originals.
No administrator approval is required. Resolve the corresponding immutable
input from the BIOMERO run record and preserve additional results and sidecars.
The pointer identifies produced labels rather than asserting parent-pixel
equality; the labels-only route does not need such an assertion.

The run still identifies a TIFF input, so BIOMERO must use its execution record
to resolve the corresponding managed canonical source; the metadata does not
provide that BIOMERO source/generation binding itself. The revised graph also
still omits a measurement CSV entity/result, so it is not a basis for dropping
the sidecar found in the original example archive.

The original supplied config used Bilayers `subtype: [label]`. Presence of a
label/mask subtype helps classify a produced output; its absence does not
establish preservation, nor does its presence establish unchanged sibling image
arrays. Prefer positive output scope and input association over inferring a
shortcut from a missing subtype. These output links supply usable automatic
labels-only evidence without requiring another preservation boolean.

## Evidence and acceptance

Local read-only measurements used ISCC-BIO 0.2.0, five shuffled repetitions and
medians of the four later passes. These are identity-step measurements on
Windows Docker-mounted storage, not cold-cache or whole-workflow HPC timings.
Direct full-resolution Instance-Codes matched the existing API in every case.

| Fixture | Existing high-level API | Pixels-only full resolution | Pixels-only coarsest level |
| --- | ---: | ---: | ---: |
| Real 18-field, two-channel Plate | 35.36 s | 2.52 s | 0.75 s (251 x 251) |
| Leica v2, two channels and three Z slices | 4.16 s | 2.61 s | 0.078 s (32 x 32) |
| Same Leica image, v3 | 7.01 s | 0.49 s | 0.140 s (32 x 32) |

The v3 timings varied materially; neither these numbers nor field count alone
establish a release-wide speedup. Preserve benchmark scripts, package versions
and raw results in the evidence store, then repeat the identity and end-to-end
measurements on representative shared-storage runs.

Required acceptance for the pixel/pyramid work:

- [ ] Full-resolution lower-level hashing reproduces existing Instance-Codes
  across v2/v3, endian cases, axis layouts, channels, stacks and timepoints.
- [ ] No raw-store checksum, unrelated labels or unused pyramid chunks are read
  when computing the selected original-image fingerprint.
- [ ] Coarsest-level selection, nonnumeric paths, cross-store compatibility,
  missing pyramids and single-level images have regression coverage.
- [ ] Old or missing identity profiles trigger regeneration with the current
  method against the existing backing Zarr, then reuse the refreshed cache.
  This does not invoke legacy hashing, fresh export, source copying or reimport.
- [ ] Previously imported v2/v3 Zarrs without identity records remain usable.
  Stale-record handling preserves backing stores; mismatched formats and
  failed comparisons keep the normal full-result import route.
- [ ] New and changed labels, measurements and derived images survive; source
  pixels remain immutable. Invalid/unmatched results retain the full fallback.
- [ ] Local and remote receipt consumers agree on profiles. Cached identities
  are reused, cheap mismatches avoid pixel reads and early rejection is bounded.
- [ ] Documentation and recorded metadata identify the actual algorithm and
  its approximation; repeatable timings separate hashing from total latency.

Additional acceptance for the declaration extension:

- [ ] Usable RO-Crate output evidence automatically selects source-linked
  handling with no workflow admin approval, opt-in or allowlist.
- [ ] The independent admin workflow setting supplies the shortcut when output
  evidence is absent. Unset/false leaves automatic RO-Crate handling available;
  with neither source of evidence, the new equality checks run.
- [ ] Implemented descriptor presets follow existing UI persistence, manual
  override and explanation conventions. Future preset support is not claimed
  in release configuration documentation before it exists.
- [ ] Recognized output evidence, absent/unusable metadata, parameter
  conditions, multiple inputs, mixed outputs and wrong-run bindings are tested.
  The shortcut performs no original-pixel sweep and records its actual basis.
- [ ] With shallow storage disabled, neither metadata nor the workflow setting
  prunes image arrays or runs deduplication-only hashing. Full stored Zarrs are
  self-contained, including materialization where supported and needed.
- [ ] Sidecars and measurement files survive processing and RO-Crate provenance
  remains accurate after pruning; removed image arrays are represented by the
  appropriate managed-source relationship rather than misleading file entries.
- [ ] Label-level `result`/`exampleOfWork` bindings automatically select
  labels-only handling, including source association and mixed derived outputs.
  A missing mask/label subtype never enables the shortcut by itself.

## Implementation ownership and order

1. **biomero-schema:** the versioned current comparison contract/profile and
   stale-record detection; a separate decision basis if the shortcut
   extension is implemented. No parallel legacy identity support is required.
2. **BIOMERO.shallower:** lower-level pixel reader/hash adapter, pyramid
   selection, compatibility checks, bounded early rejection and receipts.
3. **BIOMERO.importer and biomero-scripts/core as required:** source-profile
   caching, transfer snapshot and receipt consumption. Keep the UI policy out
   of core configuration ownership; scripts pass the selected run policy.
4. **OMERO.biomero:** the independent workflow setting, persistence and Runtime
   indication. Descriptor-derived presets use existing override/explanation
   conventions when that later integration is implemented; output RO-Crate
   interpretation itself requires no new admin control.
5. **NL-BIOMERO:** coordinated published dependency pins, matching helper/trust
   settings, integration coverage and user/admin/methods documentation.

Keep component implementation PRs separate from this planning PR. Publish
dependencies in dependency order and test the assembled v2/v3 stack before
the final 1.8 release. This proposal authorizes no merge, prerelease or deploy.
Labels-only output enforcement, avoiding original-data copies, mixed full and
shallow Plate storage, sharding and archive redesign remain follow-up work.

## References

- [ISCC-BIO high-level and pixel APIs](https://bio.iscc.codes/#high-level-entry-point)
- [IMAGEWALK IEP-0018](https://ieps.iscc.codes/iep-0018/)
- [Instance-Code IEP-0009](https://ieps.iscc.codes/iep-0009/)
- [Data-Code IEP-0008](https://ieps.iscc.codes/iep-0008/)
- [Workflow Run Crate 0.5 used by the example](https://w3id.org/ro/wfrun/workflow/0.5)
- [RO-Crate 1.3 data entities](https://www.researchobject.org/ro-crate/specification/1.3/data-entities.html)
