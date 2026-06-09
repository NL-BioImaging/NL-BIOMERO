---
name: biomero-importer-converter-debug
description: Instructions for debugging, building, running, and verifying the biomero-converter and biomero-importer components.
---

# Instructions for Debugging and Testing BIOMERO Importer & Converter

This document details the workflow for building, deploying, debugging, and verifying changes when working with the `biomero-converter` and `biomero-importer` stack.

---

## 1. Rebuilding and Loading the Converter Image

The `biomero-importer` runs the `biomero-converter` inside it using rootless **Podman**. Since the Podman storage inside the importer container is ephemeral (wiped whenever the importer container is recreated/restarted via Docker Compose), you must reload the converter image into the importer container's Podman store every time the image is rebuilt or the importer container is recreated.

1. **Rebuild the Converter Image** locally on the host:
   ```bash
   docker build -t cellularimagingcf/biomero-converter:latest .
   ```

2. **Load the rebuilt image** into the running importer's internal Podman store:
   ```bash
   docker save cellularimagingcf/biomero-converter:latest | docker exec -i nl-biomero-biomero-importer-1 podman load
   ```

---

## 2. Deploying Importer Code Changes

If you modify files in the `biomero-importer` repository (such as [register.py](file:///wsl.localhost/Ubuntu/home/przemek/NL-BIOMERO/biomero-importer/biomero_importer/utils/register.py)):

1. Because the importer directory is mounted as a volume into the container, code updates are immediately visible, but python/worker processes may have cached modules.
2. **Restart the importer container** to ensure all code changes are active:
   ```bash
   docker compose restart biomero-importer
   ```

---

## 3. Monitoring Logs and Troubleshooting

When an import order is triggered, the system logs its lifecycle. Use these locations to track issues:

- **Main App Logs**:
  Contains logging from the database poller, preprocessing stage selection, and the main OMERO registration stages.
  - Path: `/home/przemek/NL-BIOMERO/logs/biomero-importer/app.logs`
  - Command: `tail -f /home/przemek/NL-BIOMERO/logs/biomero-importer/app.logs`
- **CLI Standard Error Logs**:
  Contains stderr output for individual worker runs. If preprocessing fails, check these files for tracebacks.
  - Path: `/home/przemek/NL-BIOMERO/logs/biomero-importer/cli.<UUID>*.errs`

---

## 4. OMERO Database Verification

To verify that the import behaved correctly at the database level, run SQL queries in the OMERO Postgres container.

### Step 1: Connect to the DB container
```bash
docker exec -it nl-biomero-database-1 psql -U omero -d omero
```

### Step 2: Run Verification Queries

1. **Verify PlateAcquisition (Timepoints Folder) Creation**:
   Check if any redundant `plateacquisition` entries exist for your newly imported Plate ID:
   ```sql
   SELECT id, plate, name FROM plateacquisition WHERE plate = <PLATE_ID>;
   ```
   *Expectation for Incucyte imports*: Returns `(0 rows)`. If rows exist, the double-timepoint folders will display under the screen in the OMERO client.

2. **Locate Image IDs for the Plate**:
   Find the internal OMERO image IDs associated with the wells of your plate:
   ```sql
   SELECT ws.id AS wellsample_id, ws.well, ws.image 
   FROM wellsample ws 
   JOIN well w ON ws.well = w.id 
   WHERE w.plate = <PLATE_ID>;
   ```

3. **Verify Delta T Timestamps (`PlaneInfo` table)**:
   Ensure the individual z/c/t planes have relative delta T values correctly populated (in seconds) instead of defaulting to `0`:
   ```sql
   SELECT id, thez, thec, thet, deltat 
   FROM planeinfo 
   WHERE pixels IN (SELECT id FROM pixels WHERE image = <IMAGE_ID>) 
   ORDER BY thet;
   ```
   *Expectation*: `deltat` values should show proper increments (e.g. `0`, `43200` for 12h, `86400` for 24h) matching the timepoints in the raw data.

---

## 5. OMERO Physical Units Developer Note

When updating registration scripts (`register.py`) that create OMERO database records using physical units model classes (e.g., `TimeI`, `LengthI`):
- Do **not** wrap raw float/int values in gateway helper methods like `rdouble(val)` or `rint(val)` when instantiating physical units. Doing so will raise a Python Type/Gateway error when the transaction is saved via the OMERO update service.
- **Correct**:
  ```python
  from omero.model import TimeI
  from omero.model.enums import UnitsTime
  p_info.deltaT = TimeI(d_t, UnitsTime.SECOND)
  ```
- **Incorrect**:
  ```python
  p_info.deltaT = TimeI(rdouble(d_t), UnitsTime.SECOND)  # Throws type error on save
  ```
