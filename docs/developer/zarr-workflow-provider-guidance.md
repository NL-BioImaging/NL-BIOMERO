# Zarr workflow provider guidance

BIOMERO runs BILAYERS-compatible FAIR workflows on scalable infrastructure. A
Zarr workflow does not need BIOMERO-specific logic or metadata.

## Input and output

For now, BIOMERO supplies a writable **OME-NGFF 0.4/Zarr v2** input. It may be an
Image or Plate and may already contain label groups. A deployment may advertise
newer support later, but providers should not require NGFF 0.5, Zarr v3, or
v3-only codecs yet. This boundary is set by the deployed Glencoe OMERO Zarr
PixelBuffer, which must be able to serve returned pixels inside OMERO. BIOMERO
will advance the supported interchange version as Glencoe and OMERO release and
BIOMERO validates support for newer NGFF and Zarr versions.

The portable default is to return an OME-NGFF 0.4/Zarr v2 result:

- Put segmentation results in released `labels/<name>` groups, using meaningful
  names such as `cells`, `nuclei`, or `foci` and correct label `source` metadata.
  For a Plate, put labels beneath the image/field they describe.
- If image pixels changed, return the changed image as real output.
- If the input pixels were only copied while labels were added, no special
  declaration is needed. BIOMERO detects unchanged pixels and avoids storing the
  duplicate source image when safe.
- Do not depend on the task-local absolute input path; it changes between runs
  and systems.

Keeping the concrete image and label nodes in this profile allows BIOMERO to
register them with the currently deployed OMERO Zarr PixelBuffer. BIOMERO imports
each label group as a separate viewable result object until OMERO supports labels
natively.

## Optional native shallow result

An RFC-8-aware workflow may instead return a shallow Collection containing its
derived image or label nodes and a source reference to the task-local input.
BIOMERO resolves that task-local reference through the recorded workflow input
and rebases it to its managed canonical source. The workflow must not guess
BIOMERO filesystem or object-storage locations.

RFC-8 support is an optional optimization, not a requirement. While the proposal
is still evolving, state the RFC revision used and keep each concrete image or
label node that BIOMERO must display compatible with OME-NGFF 0.4/Zarr v2. This
lets BIOMERO import a referenced label node directly even when the collection
envelope itself is not understood by the current OMERO PixelBuffer.
