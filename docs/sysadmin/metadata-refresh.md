# Workflow Metadata Refresh

This maintenance action is opt-in for each run, including in the demo. Open
**Slurm Init (Admin Only)**, enable **Refresh OMERO Metadata**, and leave
**Metadata Dry Run** checked for the first pass. No deployment flag is needed
to request a refresh.

```{note}
**Summary for system administrators:**

- Preview one selected workflow before applying changes.
- Refresh searchable annotations from recorded history; pixels, storage
  references and provenance CSVs remain unchanged.
- With detached execution enabled, apply runs continue in the background;
  dry runs remain synchronous.
- Optional backups support inspection/manual recovery, not automated rollback.
```

**Slurm Init (Admin Only)** can refresh the searchable workflow annotations on
existing OMERO Images and Plates from BIOMERO's recorded workflow history.
Use this to apply the legacy-compatible `v0` metadata view to existing results.
It retains scientific parameters and job details while removing internal
coordination annotations and unused workflow parameters.

Image data, canonical/shallow storage records, CSV attachments and event history
are unchanged. A refresh preserves the historical snapshot; it does not advance
old annotations to the workflow's latest status or invent missing provenance.
New workflow results already use `v0`; refreshing old results is optional.

## Before starting

Use an OMERO administrator account and matching BIOMERO core, scripts and worker
versions. The worker needs access to the original tracking database. Run a
refresh while metadata writers for the selected results are idle.

1. Open **Slurm Init (Admin Only)**. Uncheck **Init Slurm** for metadata-only
   maintenance, without cluster initialization or analytics rebuilding.
2. Enable **Refresh OMERO Metadata** and keep **Metadata Dry Run** checked.
3. Enable **Filter Metadata by Workflow UUIDs** and select one to three workflows
   with **Metadata Workflow UUIDs**. Use `[+]` and `[-]` for multiple selectors.
4. Run the script and review the proposed field changes in the activity log.
5. To apply the changes, uncheck **Metadata Dry Run**. For all existing workflow
   annotations, also uncheck **Filter Metadata by Workflow UUIDs**.

The UUID selector's preselected value is ignored when filtering is disabled.
When filtering is enabled, at least one valid UUID is required. Discovery uses
existing `biomero/workflow` annotations across groups; it does not add workflow
metadata to unannotated objects.

## Options

| Input | Default | Purpose |
| --- | --- | --- |
| Refresh OMERO Metadata | Off | Enable metadata maintenance explicitly. |
| Metadata View Version | `v0` | The only supported view. |
| Metadata Dry Run | On | Preview changes without writing metadata or backups. |
| Filter Metadata by Workflow UUIDs | Off | Limit the refresh to selected workflows. |
| Metadata Workflow UUIDs | Ignored unless filtering | Select one or more workflows. |
| Metadata Workers | `4` | Process independent targets concurrently; allowed range 1–8. |
| Save Metadata Backups | Off | Save original values and links for inspection or manual recovery. |
| Metadata Backup Directory | Empty | Use a unique directory under `/data/biomero-metadata-backups`, or supply a new absolute worker path. |

Ensure the backup location is on durable shared storage when backups are enabled.
Parent directories are created automatically; an explicitly supplied existing
run directory is refused. Protect backups like other workflow provenance.
There is no automated restore operation.

## Progress and results

The activity result gives a short summary of updated, unchanged, skipped and
failed result/workflow pairs. A workflow with several result objects contributes
several pairs to these counts.

Dry runs of up to three selected workflows (or three result/workflow pairs)
show added, removed and changed fields in the activity log behind the info
button. Unchanged fields are omitted and long values abbreviated. An `unlink`
removes the result's link to an obsolete annotation; it does not delete the
annotation globally. Bulk sweeps report progress counts and skip/failure reasons.

With `BIOMERO_DETACHED_WORKFLOWS=true`, apply runs continue in the background.
The activity returns a maintenance request ID, which differs from any selected
workflow UUID. You can close the browser after the handoff. Run **Slurm Check
Setup (Admin Only)** to see active and five recent completed or failed requests,
processed/total counts and outcomes. Uncheck **Check Slurm** for maintenance
status without an HPC connection. Detailed progress is recorded in the worker's
`biomero.log`, identified by the request ID.

Dry runs remain inline. With the flag absent or false, apply runs remain inline
too. Maintenance submits no Slurm jobs and is separate from the analysis
workflow overview. One background sweep runs at a time. An interrupted sweep
is retried after worker restart, rechecking already processed targets without
overwriting earlier backups. Failed sweeps require inspection and a new request.

## Backups and incomplete updates

When enabled, backups contain per-target JSON snapshots of original annotation
values and links, plus a compact `report.json` written on completion. The run
directory is reported in the inline activity result or detached maintenance
outcome and worker log. With backups disabled, no backup or report file is
written; counts and diagnostics remain in the execution logs.

Missing event-store history, ambiguous snapshots and shared annotations are
skipped without changing those views. Unknown namespaces and custom keys are
preserved. Previously reduced CSV references are retained. Recorded shallow
storage provenance remains available; older snapshots without it cannot acquire
it through a refresh.

A failed write can leave a partially updated target because annotation changes
are not a single transaction. Inspect its log, current annotations and any backup
before retrying. Other targets continue processing.

See [detached workflows](detached-workflows.rst) for deployment settings and
[BIOMERO's metadata developer reference](https://nl-bioimaging.github.io/biomero/developer/metadata-views.html)
for view policies and persistence details.
