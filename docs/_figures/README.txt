Shallow-Zarr results figure
==========================

Data:       data/shallow-plate-comparison.json (current Plate-scale campaign)
            data/shallow-846-image.json (historical local/remote pair)
Processing: shallow_methods.py, shallow_campaign.py
Published:  ../_static/figures/shallow-results.svg

With matplotlib installed, regenerate the current figure from the repository root:

    python docs/_figures/shallow_methods.py

Use a new data file without changing the plotting code:

    python docs/_figures/shallow_methods.py --data new-run.json --output comparison.svg --png

Current Plate-scale campaign
---------------------------

The plate-comparison-v1 schema contains a plates list, with full and remote
configurations per Plate. stored_bytes counts retained compressed Zarr files,
excluding shared source and non-Zarr outputs. total_min and stages_min are the
reported mean wall-clock minutes; helper_execution_s retains separately reported
second precision. n records technical repetitions. total_sd_min and optional
stored_sd_bytes supply sample SDs for elapsed time and retained bytes. Error
bars show mean +/- one sample SD for n >= 2; null means unknown, not zero.
Storage SDs are divided by the Full mean to use the same percent scale as the
bars; they do not estimate uncertainty of a ratio. Do not sum stage SDs to obtain
total SD (stages covary). For adjusted elapsed time, supply adjusted_total_sd_min
computed from adjusted per-run times; the original total SD is not reused.
The supplied summary lacks numeric SDs, so current total_sd_min values remain
null. Populate them from the corresponding per-condition summary or raw runs.

The source report's SHA-256 is recorded in provenance; the original is archived
outside the published documentation. Source metadata repair and recovery are
recorded as qualifications on the affected configurations, not hidden.

For the recovered large Full run, excluded_wait_stage identifies only the
explicit failed-state/awaiting-manual-recovery interval. The plot subtracts this
interval, retaining the other reported stages and gaps. The original total and
all stages remain unchanged in JSON. The adjusted bar is labelled and is not
used to calculate a large-Plate speedup. Its partial return stage is not a
successful complete result transfer. Stage sums tolerate reported 0.01-minute
rounding; inconsistent data are rejected. The large shallow measurement records
repaired source metadata. Timings are compared as configurations because Full
uses v3 and Remote uses v2, not as an isolated effect of shallowing.

Storage is relative to each Plate's Full result, with identical scales. Time
panels use minutes and separate scales to keep small-Plate costs visible.
Input preparation sums compatibility, canonical preparation and other input
preparation/transfer; other work/waiting is the remainder of the plotted total.
The script derives labels, storage savings, time differences and stage stacks.

Historical single-pair format
-----------------------------

Regenerate the earlier comparison explicitly:

    python docs/_figures/shallow_methods.py --data docs/_figures/data/shallow-846-image.json --output historical.svg

Copy that JSON structure for another single-pair measurement. Byte fields contain logical byte
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
those describe the selected comparison and are not generated.
