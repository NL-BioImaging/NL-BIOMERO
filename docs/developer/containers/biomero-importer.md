# BIOMERO.importer Container

> **Note:**
> **ADI** is the deprecated name for this service. The new canonical name is **BIOMERO.importer**.

The BIOMERO.importer service handles automated data import workflows and order management.

## Overview

BIOMERO.importer provides:

- **Automated Import**: Hands-free data import from configured directories
- **Order Management**: Import job queuing and tracking
- **File Monitoring**: Automated detection of new data files
- **Integration**: Seamless connection with OMERO server and web interface

See the [BIOMERO.importer README](https://github.com/Cellular-Imaging-Amsterdam-UMC/BIOMERO.importer#readme) for detailed setup, configuration, and usage.

## Import Workflow

![BIOMERO.importer automated import workflow](./flow_diagram_ADI_import.png)

High-level flow of the BIOMERO.importer import process, from user request and database orchestration to worker thread execution.

## Import order creation and management

Orders are managed in PostgreSQL. Tables are created by BIOMERO.importer via SQLAlchemy at startup, using the database configured by `INGEST_TRACKING_DB_URL` (env var preferred) or in `settings.yml` (see below).

Ways to create orders:

- OMERO.biomero web plugin: Uses the `biomero_importer` Python library to insert into both the main imports table and the preprocessing table when needed.
- Direct SQL: Insert directly into the database (see the [BIOMERO.importer README](https://github.com/Cellular-Imaging-Amsterdam-UMC/BIOMERO.importer#readme) for schema details).
- Programmatically: Use the `biomero_importer` Python library from any client.

Database access:

- See [Database](database.md) for information on how to access the PostgreSQL database.
- You can also browse tables in Metabase. See [Metabase](metabase.md). Note: Metabase browsing is read-focused; creating new orders is typically done via OMERO.biomero or direct SQL.

## File system monitoring and processing

- The shared file system is mounted into biomero-importer at `/data`. The importer user must have read/write permissions.
- Orders can reference any files/folders under this mount. The OMERO.biomero app can restrict selectable folders per group in its UI; the database itself does not enforce these restrictions.
- When preprocessing is enabled, converted files are written back alongside originals under a `.processed` subfolder within the same directory.
- All imports are in-place. OMERO.server must mount the same storage at the same path for symlink-based imports to work.
- For large/long imports, enable preprocessing: after preprocessing BIOMERO.importer imports from local temporary storage on OMERO.server, then redirects symlinks to the network location afterward. This reduces network risk during in-place import.

## Configuration

- `settings.yml` is read at startup. Prefer environment variables for secrets and URLs.
- Key options:
  - `ingest_tracking_db` (or `INGEST_TRACKING_DB_URL` via env)
  - `log_level`, `log_file_path`
  - `max_workers`
  - OMERO CLI import tuning per worker: `parallel_upload_per_worker`, `parallel_filesets_per_worker`
  - OMERO CLI import skips: `skip_all`, `skip_checksum`, `skip_minmax`, `skip_thumbnails`, `skip_upgrade`
- You can bind-mount a customized `settings.yml` into the container to override defaults.
- Some settings can be tuned for performance depending on your storage and data shape.

## Integration with OMERO server

- The biomero-importer container shares both `/OMERO` and `/data` with OMERO.server. This is required for preprocessing and in-place imports.
- BIOMERO.importer authenticates to OMERO as root initially, then switches context to the requesting user/group to perform the import as that user.

## Custom import pipeline development

- See the [BIOMERO.importer README](https://github.com/Cellular-Imaging-Amsterdam-UMC/BIOMERO.importer#readme) for container interfaces and examples.
- Provide a standalone Docker/Podman-compatible container that follows the IO conventions (inputs/outputs and optional JSON metadata). BIOMERO.importer will run it via podman-in-docker/podman-in-podman.
- Windows note: preprocessing containers should run as root inside the container to avoid file permission issues on mounted volumes. On Linux, userns keep-id can help for non-root, but Windows Docker commonly needs root.
- Files without preprocessing are imported in-place using OMERO CLI/bioformats via ezomero/CLI integration.

## Error handling and retry mechanisms

- Logs: application and import logs are written in the container (default: `/auto-importer/logs`). Each import also has dedicated OMERO CLI logs.
- Failed imports: orders are marked as FAILED and are not retried automatically. You can set them back to PENDING to re-run.

Example to retry a specific order by UUID:

```sql
UPDATE imports
SET stage = 'Import Pending'
WHERE uuid = '00000000-0000-0000-0000-000000000000';
```

## Testing

Quick checks for a running deployment:

Run a small end-to-end test order:

```bash
# BIOMERO.importer upload health check
podman exec -it biomero-importer /bin/bash -c "python tests/t_main.py"
```

Test podman-in-podman:

```bash
# Podman-in-podman test run
podman exec -it biomero-importer /bin/bash -c "podman run docker.io/godlovedc/lolcow"
```

See the [BIOMERO.importer README](https://github.com/Cellular-Imaging-Amsterdam-UMC/BIOMERO.importer#readme) for details on configuring `settings.yml` to point to your demo file and target destination.

## Security and runtime requirements

> **Note:**
> BIOMERO.importer runs podman-in-podman (or podman-in-docker). The container currently requires `--privileged` and access to `/dev/fuse` for running preprocessing containers as the importer user. Some reports suggest alternatives may be possible on specific platforms, but our attempts without privileged have not been reliable yet. A potential future improvement is to switch the podman engine that runs BIOMERO.importer to a different model so the inner podman can run without privileged.

## Related Documentation

- [OMERO Server](omeroserver.md) - Server integration
- [OMERO Web](omeroweb.md) - Web interface integration
- [Metabase](metabase.md) - Analytics and DB browsing
- [BIOMERO.importer Repository](https://github.com/Cellular-Imaging-Amsterdam-UMC/BIOMERO.importer)
