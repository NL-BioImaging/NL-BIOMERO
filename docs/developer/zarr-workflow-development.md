# Developing OME-Zarr workflows

BIOMERO runs Bilayers-compatible FAIR workflows on scalable infrastructure. An
OME-Zarr workflow does not need BIOMERO-specific storage logic or metadata.

## The workflow boundary

BIOMERO gives a Zarr-native workflow a conventional, self-contained OME-Zarr.
If BIOMERO stores the selected result internally in an optimized form, it
restores the image pixels and labels before transfer. The workflow therefore
does not detect or reconstruct BIOMERO's storage representation.

The complete Zarr is the **container** supplied to the workflow. Which data the
workflow analyzes follows its declared purpose:

| Workflow input | Data to read |
| --- | --- |
| Intensity image | The image arrays described by `multiscales` |
| Mask or segmentation image | The requested label image below the corresponding `labels/` group |
| Image and mask | Both the image arrays and the requested label image |
| HCS Plate | The images and, where required, their labels at the Plate image/field level |

A workflow that accepts a mask must identify which label it expects, for
example through a parameter or an unambiguous input convention. It must not
assume that the top-level intensity image is the mask. BIOMERO keeps the labels
together in the Zarr; choosing the label with the correct semantic role remains
part of the workflow interface.

## Returning results

Return an ordinary, valid OME-Zarr in the supported profile. Derived masks
belong in the NGFF `labels/` hierarchy associated with their image. Existing
labels may remain present, so a workflow can use one label to derive another
without flattening the data into unrelated files.

BIOMERO compares returned image and label pixels with the input it supplied. It
may subsequently avoid storing unchanged pixels and labels more than once.
This happens after the workflow boundary and does not change the result format
that workflow authors produce.

## Current compatibility

The BIOMERO/OMERO path supports **OME-NGFF 0.4 on Zarr v2** and
**OME-NGFF 0.5 on Zarr v3**, including sharded v3 arrays. Existing managed
canonical stores retain their original format.
Workflows must support the format of their inputs; accepting OME-Zarr does
not imply support for every NGFF or Zarr version.

Workflow inputs default to `0.4` / v2. Administrators opt individual Bilayers
workflows into `0.5` / v3 using the **Zarr v3 input (OME-Zarr 0.5)** switch or
`[UI] zarr_v3_workflows`. The worker enforces this for both fresh exports and
existing stores. Matching formats are reused directly; mismatches are converted
temporarily with pixels and labels preserved. BIAFLOWS and TIFF conversion always
use v2. Canonical storage remains unchanged, and cross-format results stay full.
The NL-BIOMERO demo explicitly
selects `omezarr05` for new Leica,
Incucyte database and Incucyte archive conversions in `web/biomero-config.json`.
Each route passes the same `extra_params.outputformat` setting; Leica also
passes the selected image UUID. This preprocessing setting is independent of
the per-workflow input compatibility setting.

Workflow authors do **not** need to generate BIOMERO sidecars, ISCC identities,
RFC 8 shallow copies, or BIOMERO provenance metadata. Produce the supported
OME-Zarr structure and declare the appropriate inputs, outputs, formats, and
parameters in the Bilayers descriptor.

See [Bilayers workflows](bilayers-workflows.rst) for descriptor and CLI-path
configuration.
