# Working with shallow OME-Zarr results

Shallow storage keeps your analysis results without storing another copy of
unchanged source pixels. New segmentation labels and other changed data remain
in the result; unchanged pixels are referenced from their existing managed
location. Your original data is not modified.

This can substantially reduce storage for repeated analyses of the same Images
or Plates. Earlier examples saved around 90% of result disk space, at the cost
of additional verification and processing. Savings depend on what the workflow
changes, not just the number of images.

Your administrator enables the feature and chooses local or remote processing.
There is no extra step when you submit a supported workflow. For configuration
and the short performance comparison, see
[Shallow OME-Zarr Storage](../sysadmin/remote-shallower.rst).

## What is stored?

| Part | Contents |
| --- | --- |
| Managed source | Full image pixels, reused from an existing Zarr or converted into a reusable Zarr when needed |
| Shallow result | New or changed labels, result metadata, and references to unchanged source pixels or inherited labels |
| Reconstructed result | A full, self-contained Zarr assembled when needed for another workflow or external use |

The shallow result's `.biomero-shallow.json` manifest records how these parts
fit together. **Keep its referenced source and label stores available.** A
shallow directory alone is not a backup of the complete result. Ask your
administrator before moving or deleting managed data.

BIOMERO keeps one canonical registration per OMERO Image or Plate. When an
input is already a managed Zarr, it is indexed in place; duplicate OMERO
imports may therefore share that physical source. Otherwise BIOMERO creates
one stable canonical Zarr and reuses it. It does not retain historical copies
of generated canonical stores.

Only derived workflow results are shallowed. Uploading a Zarr does not by
itself trigger deduplication. If returned image pixels have changed, or BIOMERO
cannot safely establish a match, it retains the full result.

## What you see in OMERO

You can browse the registered results as Images or Plates. OMERO's pixel-reading
component, the **PixelBuffer**, reads original intensities from the managed source
and mask pixels from retained label arrays. Missing duplicate arrays are not
replaced with zeros, and viewing does not require another full copy.

- **Image results:** the primary Image shows source intensities and opens all
  result labels in the OME-Zarr Viewer. Separate mask Images remain available
  as lightweight input projections for TIFF-based workflows.
- **Plate results:** the primary Plate shows source intensities. An optional
  label-backed preview shows one selected label in the same well/field layout.
  Other labels remain in the result even when not registered as separate Plates.

These are views of shared data, not independent copies of all its pixels.
A label preview is not the complete set of labels. The Plate preview control is
hidden by default because the OME-Zarr Viewer displays the labels on the primary
Plate. An administrator can expose it with
`allow_plate_label_preview = true` under `[UI]` in `slurm-config.ini`.

## How BIOMERO checks that pixels are unchanged

BIOMERO uses **ISCC-BIO pixel identities** to compare workflow inputs and results.
It records or reuses input identities, then calculates identities from the
returned pixels before removing duplicates.

The IMAGEWALK method examines decoded image pixels rather than relying on a
filename or a checksum of the whole Zarr directory. Recompression or adding a
label can change stored files without changing the original image. BIOMERO
also checks properties such as shape, data type, axes and spatial transforms;
a matching filename or copied identity annotation is not enough.

Images and labels are checked independently. If a follow-up workflow receives
five existing label layers and adds four new ones, unchanged inherited layers
can remain references while the four new layers are stored in the new result.
Reconstruction includes all nine. A changed label is retained rather than
mistaken for the old one.

This is conservative pixel verification, not an adversarial security guarantee.
For the exact comparison fields, see the
[PixelIdentity reference](https://nl-bioimaging.github.io/biomero-schema/pixel-identity/).

## Using results in another workflow

Select the shallow result normally. For a **Zarr-consuming workflow**, BIOMERO
Image Transfer reconstructs a full Zarr containing source pixels and the
result's inherited and new labels before sending it to HPC.

```{mermaid}
flowchart LR
    S["Managed source pixels"] --> R["Reconstruct full Zarr"]
    L["Shallow result<br/>References and retained labels"] --> R
    R --> W["Next Zarr workflow"]
    W --> C{"Returned pixels<br/>verified unchanged?"}
    C -->|Yes, eligible result| N["Store shallow result"]
    C -->|Changed or uncertain| F["Keep full result"]
```

Reconstruction takes time and temporary disk space proportional to the data
being assembled. It restores a usable full representation; it does not undo
or modify the stored shallow result.

There is one important format distinction:

| Selection | What the next workflow receives |
| --- | --- |
| Shallow Image or Plate selected for a Zarr workflow | Full Zarr with source intensities and the result's labels |
| Mask Image selected for a TIFF workflow | The selected mask pixels as TIFF, not the original intensities |

Plates use the Zarr path. Do not assume that selecting a mask Image means
“mask pixels only” when the next workflow expects a full Zarr.

(reconstruct-shallow-zarr-on-disk)=
## Exporting a standalone Zarr

**A shallow result is not a self-contained OME-Zarr for generic readers.**
Its retained arrays are Zarr, but ordinary readers cannot resolve BIOMERO's
managed references to the omitted arrays.

For external analysis or sharing, reconstruct it first. The current reconstruction
produces conventional **OME-NGFF 0.4 / Zarr v2** data with the referenced pixels
and labels copied into the output.

This can be done on disk without submitting another analysis or running an
OMERO script. The
[standalone reconstruction recipe](https://github.com/NL-BioImaging/BIOMERO.shallower#reconstruct-a-full-zarr)
uses the same `materialize_shallow_zarr` Python function as Image Transfer.
It requires access to the managed source/label stores and their storage mappings;
ask your administrator if you do not have filesystem access.

Choose a new destination and allow space for the full result. Original stores
are left unchanged. Creating this standalone copy does not automatically
register another object in OMERO.

BIOMERO's shallow manifest is a private storage representation, inspired by
the shallow-copy use case of OME-NGFF RFC 8; it is not itself a portable
RFC 8 Collection.

## Local, remote and detached processing

Local and remote shallowing aim to produce the same logical result. Local
processing happens after the full output is transferred back. Remote processing
happens on HPC before transfer, saving network traffic and local extraction work
but requiring additional HPC CPU resources.

The relevant comparison is where shallowing work occurs, not how quickly an
unrelated storage mount happened to copy or extract a result. In a matched
846-image Plate comparison, local identity evaluation and normalization took
1 h 47 min 7 s. The remote path used a 14 min 28 s CPU-only helper followed by
1 min 3 s of importer validation, an 85.5% reduction for those stages. The
return archive was 87.6% smaller, while final extracted storage was equivalent.
Queueing and mounted-storage performance still determine how much of that
stage-level gain appears in the complete workflow time.

Neither changes the workflow's scientific parameters. Remote shallowing can
run with or without detached execution. **Only detached execution removes the
workflow's dependency on the submitting session**; shallow storage alone is
not a reason to close the session during an inline workflow.

See the [administrator's guide](../sysadmin/remote-shallower.rst) for processing
choices and [detached workflows](../sysadmin/detached-workflows.rst) for session
behaviour.
