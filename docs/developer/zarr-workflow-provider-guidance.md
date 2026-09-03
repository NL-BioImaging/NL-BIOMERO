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
each newly produced or changed label group as a separate viewable result object
until OMERO supports labels natively. Unchanged labels copied from the input
remain part of the logical result but are referenced rather than stored and
imported again.

## Experimental native shallow output

The reliably supported provider contract is the conventional full OME-NGFF
0.4/Zarr v2 result above. BIOMERO performs its own identity comparison and
private shallow normalization after the workflow returns. Providers should not
assume that arbitrary draft RFC 8 Collections can currently be imported.

A provider may coordinate an experimental native shallow output with a BIOMERO
deployment. Such an output should identify the exact RFC 8 revision it follows,
refer to the task-local input rather than guessing managed storage paths, and
keep every concrete image or label node that OMERO must display compatible with
OME-NGFF 0.4/Zarr v2. BIOMERO would then resolve the task-local source through
its recorded workflow snapshot and rebase it to managed storage. This remains a
future interoperability optimization, not a portable or required provider
feature while RFC 8 and the surrounding OMERO support are evolving.
