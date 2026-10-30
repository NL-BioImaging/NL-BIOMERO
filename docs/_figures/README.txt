Shallow-Zarr results figure
==========================

Data:       data/shallow-846-image.json
Processing: shallow_methods.py
Published:  ../_static/figures/shallow-results.svg

With matplotlib installed, regenerate the current figure from the repository root:

    python docs/_figures/shallow_methods.py

Use a new data file without changing the plotting code:

    python docs/_figures/shallow_methods.py --data new-run.json --output comparison.svg --png

Copy the JSON structure for new measurements. Byte fields contain logical byte
counts; timing fields are wall-clock seconds. Runs are plotted in JSON order;
the usual keys are full, local and remote. Omit local when comparing Full with
Remote only. The full reference is required. Add zarr_format (2 or 3) to show
the format on the axis, and an optional label to name another configuration.
Record provenance and comparison limits in title/notes. The current
Full byte/copy baseline comes from the local run's pre-shallow output; it is not
a separate timed Full workflow.
Storage uses the full archive's uncompressed file bytes, including the measurement
database, against all retained result files. Do not substitute the smaller Zarr-only
baseline while retaining measurement/database bytes in the shallow totals.

Use null for an unmeasured value, not zero. Full stored_bytes and
return_copy_validation_s must provide positive measured reference values.
An unmeasured complete run has timing: null. For a measured run, provide analysis_s,
total_s and a shallowing_stages_s map; use an empty map for a measured Full run.
Stage timings must not overlap and their sum must not exceed total_s. Other work
is calculated as the remainder, including transfer, staging and waiting.

The script calculates totals, percentages, headline savings, labels and axis limits
from the data. Once Full timing is supplied, it is plotted and becomes the time
reference; otherwise the first measured mode is used. Missing measurements remain
marked as unmeasured. Negative, non-finite or inconsistent timings are rejected.
Use one comparison file per plate/dataset. If Zarr formats differ, the chart uses
configuration-comparison headings: the difference cannot be attributed solely
to shallowing. Two runs are sufficient; a local-shallow run is optional.

The SVG is committed, so Sphinx does not need matplotlib. When replacing the
published dataset, update the guide's accompanying caption/table/text as well;
those describe the current historical comparison and are not generated.
