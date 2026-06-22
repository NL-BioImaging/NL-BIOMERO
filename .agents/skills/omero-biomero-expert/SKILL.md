---
name: omero-biomero-expert
description: OMERO/BIOMERO expert runbook for NL-BIOMERO deployments. Use for debugging and operating OMERO.server/web, OMERO.biomero, BIOMERO analyzer/importer/converter, Metabase dashboards, Docker Compose, Slurm/Spider, storage permissions, prod/dev SSH, runtime patches, logs, and Postgres verification.
---

# OMERO/BIOMERO Expert

Use this skill for NL-BIOMERO work on dev or prod. Prefer inspection over guesses: identify the active host, read the relevant compose/env/log state, verify data paths and permissions, then run a focused smoke test.

Never print secrets. Mask `.env`, container env, Metabase datasource JSON, passwords, secret keys, JWTs, and tokens in user-facing output.

## First Checks

Confirm the host. In this workspace, `biomero-prod` may live in the repo-local SSH config, so use `ssh -F .ssh/config biomero-prod ...` when the default SSH config does not resolve it.

```bash
ssh -F .ssh/config biomero-prod 'hostname; whoami; pwd'
ssh -F .ssh/config biomero-prod 'cd /opt/omero/NL-BIOMERO && sudo docker compose ps'
```

Known paths:

```text
prod stack: /opt/omero/NL-BIOMERO
dev workspace: /home/sloev/local-share/opt/omero/NL-BIOMERO
```

Docker often requires `sudo`. If `docker ps` fails on `/var/run/docker.sock`, retry with `sudo docker ...`.

Core service names:

```text
metabase
nl-biomero-omeroweb-1
nl-biomero-omeroserver-1
nl-biomero-biomeroworker-1
nl-biomero-omeroworker-1-1
nl-biomero-biomero-importer-1
nl-biomero-database-1
nl-biomero-database-biomero-1
```

Quick status:

```bash
cd /opt/omero/NL-BIOMERO
sudo docker compose ps
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo docker compose logs --tail=120 metabase omeroweb biomero-importer
```

## Reference Routing

Read only the relevant reference before acting:

- [references/permissions-and-deployment.md](references/permissions-and-deployment.md): host/container UID/GID issues, project-local SSH, writable bind mounts, `chmod`/ownership workarounds, production vs dev compose, backup/restore guardrails.
- [references/metabase-dashboards.md](references/metabase-dashboards.md): BIOMERO Analyze/Import iframe failures, dashboard IDs, embedding secrets, H2 inspection, datasource credential repair, signed embed smoke tests.
- [references/slurm-runtime-patches.md](references/slurm-runtime-patches.md): Spider/Slurm behavior, runtime BIOMERO patch intent, GPU policy, per-job env files, Apptainer cache/temp, output verification, generated job script normalization.
- [references/importer-analyzer-storage.md](references/importer-analyzer-storage.md): BIOMERO.importer, analyzer-to-importer result flow, `/data` path invariants, `.analyzed`/`.processed`, shared storage, import order polling, importer logs.

## Converter and Importer Code

The `biomero-importer` runs `biomero-converter` with rootless Podman inside the importer container. The importer container's internal Podman store is ephemeral when the container is recreated, so reload rebuilt converter images after rebuilds or importer recreation.

```bash
docker build -t cellularimagingcf/biomero-converter:latest .
docker save cellularimagingcf/biomero-converter:latest | docker exec -i nl-biomero-biomero-importer-1 podman load
```

If importer Python code changes, mounted source may update immediately but worker processes can cache modules. Restart the service:

```bash
docker compose restart biomero-importer
```

## Importer Logs and Test Images

Importer logs:

```text
<stack-root>/logs/biomero-importer/app.logs
<stack-root>/logs/biomero-importer/cli.<UUID>*.errs
```

Sample test images:

```text
biomero-importer/tests/Barbie1.tif
biomero-importer/tests/Barbie2.tif
biomero-importer/tests/Barbie3.tif
```

Common in-container paths:

```text
/auto-importer/tests/Barbie1.tif
/auto-importer/tests/Barbie2.tif
/auto-importer/tests/Barbie3.tif
```

## OMERO Database Verification

Use Postgres for high-confidence import verification:

```bash
docker exec -it nl-biomero-database-1 psql -U omero -d omero
```

Useful checks:

```sql
SELECT id, plate, name FROM plateacquisition WHERE plate = <PLATE_ID>;

SELECT ws.id AS wellsample_id, ws.well, ws.image
FROM wellsample ws
JOIN well w ON ws.well = w.id
WHERE w.plate = <PLATE_ID>;

SELECT id, thez, thec, thet, deltat
FROM planeinfo
WHERE pixels IN (SELECT id FROM pixels WHERE image = <IMAGE_ID>)
ORDER BY thet;
```

For Incucyte imports, redundant `plateacquisition` rows usually indicate the double-timepoint-folder UI problem. `planeinfo.deltat` should contain meaningful increments, not all zero.

## OMERO Physical Units

When updating registration code such as `biomero-importer/biomero_importer/utils/register.py`, do not wrap raw values in gateway helpers when instantiating physical unit model classes.

Correct:

```python
from omero.model import TimeI
from omero.model.enums import UnitsTime
p_info.deltaT = TimeI(d_t, UnitsTime.SECOND)
```

Incorrect:

```python
p_info.deltaT = TimeI(rdouble(d_t), UnitsTime.SECOND)
```
