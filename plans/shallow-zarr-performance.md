# Faster shallow OME-Zarr: pixel fingerprints and workflow declarations

Status: proposal for implementation before the final 1.8 release. This document
changes no runtime behaviour, dependencies, defaults or deployed services.
The workflow-declaration shortcut is a separately deliverable extension; it
must not hold up the pixel API, pyramid comparison and documentation work.

## Outcome

Keep the storage savings of shallow results while reducing the work between
GPU analysis and researchers receiving their results. Remove the unused raw
store checksum, compare existing small-resolution pixels, and describe exactly
which ISCC-BIO functionality BIOMERO uses. Capture a route for approved
workflows to declare unchanged originals and avoid pixel comparison altogether.

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

### Profiles, cached sources and backward compatibility

Introduce an explicit versioned comparison profile in the shared contracts.
Record the selected resolution's dataset path, shape and transforms alongside
the original image semantics, code lengths and implementation versions.
Dataset paths identify what was read; compatibility must not require identical
path spelling. Treat this profile as BIOMERO-specific, not a new ISCC standard.

Existing full-resolution records and manifests remain readable with their
original meaning. Never relabel an old full-resolution code as a pyramid code,
compare unlike profiles, or silently reinterpret an existing shallow result.
Cache the required new fingerprint against the same immutable source
generation, without recreating or reimporting the canonical store. Index on
first use where necessary; reuse the cached profile on later runs. Keep old
references valid and preserve the normal full-result fallback.

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

> BIOMERO generates a resolution-specific pixel fingerprint for each OME-Zarr
> image or Plate field using ISCC-BIO. It reads the coarsest compatible stored
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

## 4. Allow approved workflow declarations to skip original-pixel comparison

Add a per-workflow administrator policy, following the existing workflow
settings pattern. An administrator can approve a particular workflow/version
to preserve original image pixels. Alternatively, an approved descriptor or
output declaration can select the shortcut for a particular run and output.
Automatic interpretation must respect the administrator's explicit override.
Missing policy preserves verification; the presence of an RO-Crate alone does
not enable the shortcut. Keep this under existing shallow feature gating.

The declaration must identify the run, the actual workflow version, the input
source/generation and the specific returned image node that preserves it.
Support parameter-dependent behaviour through actual recorded run values.
Distinguish unchanged originals, labels-only overlays and derived images;
`output is Zarr` or `subtype is label` is not enough. Do not assume a generic
`use_gpu`, `output_to_layer` or other parameter name expresses preservation.

Reuse standard workflow/run provenance links and add a small, explicit
BIOMERO preservation profile where needed. Decide its vocabulary in the shared
schema work; no preservation boolean is claimed to be an existing Bilayers or
Workflow Run RO-Crate standard. The approval is a workflow contract, not a
requirement to introduce digital signatures or perform another full checksum.

Retain cheap source binding, format, layout and metadata validation. Skip the
original pixel sweep only where the approved relationship applies. Record
`declared unchanged` separately from full-resolution or pyramid verification;
do not fabricate an Instance-Code or mark unmeasured data as pixel-verified.
Permit source references without calculating an otherwise unused source code
for such runs; this requires an explicit contract path rather than dummy IDs.
Keep label handling independent. Unrelated outputs continue through their
normal comparison or full-import route. Unusable declarations fall back to
verification, then full import if a match cannot be established.

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
  definitions to actual values. These can support a versioned, parameter-aware
  workflow approval rule without guessing from parameter defaults.
- The configuration identifies a container/tag, citations and a label output
  described as the input image with segmentation in OME-Zarr labels.

Information still needed for skipping comparison:

- An explicit machine-readable unchanged-pixels relationship, its scope and
  a binding to BIOMERO's canonical source generation and current run.
- Array-level mapping for image/Plate fields and a separate treatment of
  outputs whose image pixels are derived results.
- A reliable workflow/version identity from BIOMERO's execution record. The
  sample configuration's container tag helps identification but is not an
  immutable container digest or an executed-workflow attestation.

The TIFF -> Zarr provenance and human-readable output description do not by
themselves assert unchanged numerical pixels. The actual Zarr was absent, so
no pixel or layout conclusion was tested. The CSV is present in the ZIP but is
not listed as a run result/data entity in its graph: retain such files and
improve enumeration rather than treating the crate as an exhaustive deletion
list. Do not infer preservation from segmentation-related parameter names.
Do not publish the original archive or its workstation paths in this PR.

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
- [ ] Missing legacy profile fields retain full-resolution semantics. Old
  sources, old shallow manifests, mismatched formats and failed comparisons
  remain importable without forced migration or data loss.
- [ ] New and changed labels, measurements and derived images survive; source
  pixels remain immutable. Invalid/unmatched results retain the full fallback.
- [ ] Local and remote receipt consumers agree on profiles. Cached identities
  are reused, cheap mismatches avoid pixel reads and early rejection is bounded.
- [ ] Documentation and recorded metadata identify the actual algorithm and
  its approximation; repeatable timings separate hashing from total latency.

Additional acceptance for the declaration extension:

- [ ] Admin approval and explicit disable, absent declarations, parameter
  conditions, multiple inputs, mixed outputs and wrong-run bindings are tested.
- [ ] The approved path performs no original-pixel sweep and records its
  declaration basis. Unknown metadata does not silently enable it.
- [ ] Sidecars and measurement files survive processing and RO-Crate provenance
  remains accurate after pruning; removed image arrays are represented by the
  appropriate managed-source relationship rather than misleading file entries.

## Implementation ownership and order

1. **biomero-schema:** comparison profiles and backward-compatible records;
   a separate declaration basis if the trusted extension is implemented.
2. **BIOMERO.shallower:** lower-level pixel reader/hash adapter, pyramid
   selection, compatibility checks, bounded early rejection and receipts.
3. **BIOMERO.importer and biomero-scripts/core as required:** source-profile
   caching, transfer snapshot and receipt consumption. Keep the UI policy out
   of core configuration ownership; scripts pass the selected run policy.
4. **OMERO.biomero:** the proposed administrator-managed workflow policy,
   persistence and Runtime indication, when implementing the extension.
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
