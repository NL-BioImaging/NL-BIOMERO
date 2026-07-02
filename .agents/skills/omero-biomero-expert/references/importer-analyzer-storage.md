# Importer and Analyzer Storage

## Shared Storage Invariant

For in-place import and analyzer-to-importer result import, these containers must see the same storage at the same path:

```text
biomeroworker    -> /data
biomero-importer -> /data
omeroserver      -> /data
omeroweb         -> /data   (for UI file selection/config)
```

The compose mount is typically:

```yaml
- "./web/L-Drive:/data"
```

If paths differ between containers, imports can queue correctly but fail with file-not-found, broken symlink, or result import polling failures.

## Analyzer to Importer Flow

When `IMPORTER_ENABLED=true`, analyzer results use `SLURM_Import_Results.py` instead of the classic `SLURM_Get_Results.py` API path.

Result storage layout:

```text
<group_base_path>/
└── .analyzed/
    └── <workflow-uuid>/
        └── <YYYYMMDD_HHMMSS>/
            ├── <job_id>_out.zip
            ├── <job_id>_out/
            │   └── data/out/
            ├── metadata.csv
            └── omero-<job_id>.log
```

The worker creates an upload order in the BIOMERO.importer tracking DB and polls until import succeeds or fails. Imported images then receive workflow metadata annotations.

## Group Base Path Resolution

The group base path is resolved in this order:

1. Explicit mapping in `web/biomero-config.json`
2. Fallback `<base_dir>/<group_name>`, where `base_dir` comes from importer `settings.yml`

The active OMERO group at workflow launch determines where analysis results land.

## Permissions

The `biomeroworker` process must be able to write to the group base path. For first-time groups, it must also be able to create the group-named subfolder under `base_dir`.

The default compose stack runs the worker as the OMERO server user, commonly uid `999`. Host/NAS permissions must allow that UID to create:

```text
/data/<group>/
/data/<group>/.analyzed/
```

The importer user must have read/write access to `/data`, and OMERO.server must also mount `/data` to resolve symlink-based in-place imports.

## Importer Configuration

Important env/config:

```text
INGEST_TRACKING_DB_URL      # must match across web, worker, and importer
IMPORTER_ENABLED=true       # required on biomeroworker, not just web/importer
SQLALCHEMY_URL              # BIOMERO event-sourcing DB
config/biomero-importer/settings.yml
web/biomero-config.json
```

The worker requires these volume mounts:

```yaml
- "./config/biomero-importer:/opt/omero/server/config-importer:ro"
- "./web/biomero-config.json:/opt/omero/server/biomero-config.json:ro"
```

Verify the worker library:

```bash
sudo docker compose exec biomeroworker \
  /opt/omero/server/venv3/bin/python -c "import biomero_importer; print('ok')"
```

Verify DB URLs align (mask passwords in output):

```bash
sudo docker compose exec -T biomeroworker env | grep INGEST_TRACKING_DB_URL
sudo docker compose exec -T biomero-importer env | grep INGEST_TRACKING_DB_URL
sudo docker compose exec -T omeroweb env | grep INGEST_TRACKING_DB_URL
```

## BIOMERO.importer Model

BIOMERO.importer:

- stores orders in the BIOMERO Postgres DB
- imports files in-place from `/data`
- uses `/OMERO` and `/data` shared with OMERO.server
- authenticates to OMERO as root initially, then switches context to the requesting user/group
- writes preprocessing outputs under `.processed`
- marks failed imports failed and does not retry automatically

For preprocessing, BIOMERO.importer runs external containers through Podman-in-Podman. That requires the privilege model documented in `permissions-and-deployment.md`.

## Logs

Logs are relative to the stack root:

```text
logs/biomero-importer/app.logs          # main lifecycle log
logs/biomero-importer/cli.<UUID>*.errs  # per-worker stderr; check for tracebacks
```

Analyzer result logs:

```text
/data/<group>/.analyzed/<workflow-uuid>/<timestamp>/omero-<job_id>.log
```

Useful commands:

```bash
tail -f logs/biomero-importer/app.logs
sudo docker compose logs --tail=200 biomero-importer biomeroworker
```

## Retry Failed Import Order

A failed order can be retried by setting it back to pending in the BIOMERO DB. Confirm schema/stage names in the running DB first.

Example:

```sql
UPDATE imports
SET stage = 'Import Pending'
WHERE uuid = '00000000-0000-0000-0000-000000000000';
```

## Troubleshooting Patterns

**Results end up on OMERO server storage instead of being in-place:**
- `IMPORTER_ENABLED=true` is missing on `biomeroworker`
- `biomero-importer` Python library is missing in worker venv

**Upload order created but never completes:**
- importer container is stopped
- worker/importer/web point at different `INGEST_TRACKING_DB_URL`
- importer logs show OMERO CLI or permission failures

**Files not found:**
- `/data` mount mismatch between worker, importer, and server
- `biomero-config.json` maps group to a non-existent path

**PermissionError writing `.analyzed`:**
- worker UID cannot write the group base path
- first run for a group cannot create `/data/<group>`

**Import polling timeout:**
- default timeout is one hour
- large datasets or slow import settings may need tuning

## Test Assets

Repo test images:

```text
# Host (relative to stack or source checkout):
biomero-importer/tests/Barbie1.tif
biomero-importer/tests/Barbie2.tif
biomero-importer/tests/Barbie3.tif

# Inside the biomero-importer container:
/auto-importer/tests/Barbie1.tif
/auto-importer/tests/Barbie2.tif
/auto-importer/tests/Barbie3.tif
```
