# Database Containers

NL-BIOMERO uses PostgreSQL containers for persistent data storage across multiple services.

## Overview

The platform uses separate PostgreSQL instances:

- **OMERO Database**: Core OMERO metadata and user data
- **BIOMERO Database**: Workflow and analysis data
- **Shared Configuration**: Common database management practices

## Key Components

- **Data Persistence**: Volume management for database files
- **Initialization Scripts**: Automated database setup
- **Configuration Management**: Performance and security settings
- **Backup Integration**: Automated backup and restore workflows

## Schema customization

- OMERO: The OMERO schema is managed by the OME project. NL-BIOMERO does not alter it. Only OMERO.forms interacts with OMERO data using supported APIs.
- BIOMERO: Schemas are owned and created via SQLAlchemy by BIOMERO and BIOMERO.importer. Any schema changes or updates must go through SQLAlchemy migrations or model updates.

## Migration

Migrate to a new PostgreSQL version using pg_dump/pg_restore. The backup_and_restore scripts in this repo automate most steps and can also help migrate an existing OMERO DB into NL-BIOMERO.

```bash
# Dump from old Postgres (inside container or via exec)
docker exec -t nl-biomero_database_1 \
  pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" \
  -f /tmp/omero.pg_dump
docker cp nl-biomero_database_1:/tmp/omero.pg_dump ./backup_and_restore/backups/

# Restore into new Postgres (version upgrade)
# See: backup_and_restore/restore/restore_db.sh (Bash) or restore_db.ps1 (PowerShell)
./backup_and_restore/restore/restore_db.sh --dbType omero --postgresVersion 16
```

## Performance tuning

You can pass PostgreSQL settings to the container via the entrypoint command or environment variables. Example (Podman) enabling logging and increasing connections:

```bash
podman run -d --rm --name database \
  --network=omero \
  -e POSTGRES_USER=... \
  -e POSTGRES_DB=... \
  -e POSTGRES_PASSWORD=... \
  -v /mnt/...:/var/lib/postgresql/data \
  -v "$(pwd)/logs/database:/var/lib/postgresql/data/logs:Z" \
  postgres:16 postgres -N 500 \
  -c logging_collector=on \
  -c log_directory='logs' \
  -c log_filename='postgresql-%Y-%m-%d.log' \
  -c log_rotation_age=1d \
  -c log_rotation_size=100MB \
  -c log_statement=all
```

See the PostgreSQL documentation for the full list of tunables.

## Backup automation

Follow the OMERO backup/restore guidance:
https://omero.readthedocs.io/en/stable/sysadmins/server-backup-and-restore.html

This repository provides container-oriented helpers in backup_and_restore:

- Backup: backup/backup_db.sh, backup/backup_server.sh, backup/backup_metabase.sh
- Restore: restore/restore_db.sh, restore/restore_server.sh, restore/restore_metabase.sh

If you mount data to disk directly, the process mirrors the OMERO docs closely.

## Accessing PostgreSQL

You can exec into the database containers and use psql directly.

```bash
# OMERO DB
docker exec -it nl-biomero_database_1 bash
psql -U "$POSTGRES_USER"

# BIOMERO DB
docker exec -it nl-biomero_database-biomero_1 bash
psql -U "$BIOMERO_POSTGRES_USER"
```

Common psql commands:

```psql
-- List tables
\dt

-- Example queries
-- OMERO DB: count jobs
SELECT COUNT(*) FROM job;

-- BIOMERO DB: inspect recent imports (importer orders)
SELECT uuid, stage, group_name, user_name, timestamp
FROM imports
ORDER BY timestamp DESC
LIMIT 10;

-- Retry a failed importer order by setting it back to pending
UPDATE imports
SET stage = 'Import Pending'
WHERE uuid = '00000000-0000-0000-0000-000000000000';
```

## Related Documentation

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [OMERO Database Documentation](https://omero.readthedocs.io/en/stable/sysadmins/unix/server-postgresql.html)
