# NL-BIOMERO Deployment & Upgrade Guide

This document outlines several deployment scenarios for the NL-BIOMERO platform.
Containers are available prebuilt and deployment is possible on Linux, Windows (via Docker Desktop), or Podman (e.g. RHEL/SELinux). Kubernetes setups should also be possible with shares between services.

```{note}
The scenarios in this document are examples for inspiration, not official recommendations or complete solutions. You should adapt them to your infrastructure, security posture, and operational requirements.
```

For detailed docker-compose configurations for each scenario, see {doc}`docker-compose-scenarios`.

---

## Scenario 0: Development & Demo

- Development-focused deployments with source code access
- Suitable for testing, development, and demonstration purposes
- Builds containers from local source code
- Can include special configurations for easier development workflow

→ See {doc}`docker-compose-scenarios` for specific configurations and usage details.

---

## Scenario 1: Fresh Deployment (no existing data)

- Deploy all containers using docker-compose (1 server) or across multiple VMs.
- Configuration files define all ports, mounts, and credentials.
    - You can change mounted Docker volumes to be on-disk mounts.
- No OMERO data required.
- Works on Windows (Docker Desktop), Linux (Docker or Podman).
- For Kubernetes, adjust disk mounts and configs accordingly; some data needs to be shared between services.

→ See {doc}`docker-compose-scenarios` for specific deployment configurations.

---

## Scenario 2: Fresh Deployment with Existing Data

- Use this if restoring an existing OMERO backup.
- Requires OMERO backup (just follow the standard <a href="https://omero.readthedocs.io/en/stable/sysadmins/server-backup-and-restore.html#backing-up-omero" target="_blank" rel="noopener noreferrer">OMERO.server backup and restore</a>):
  - PostgreSQL dump (`pg_dump ...`)
  - Config dump (`omero config get`), store in `/OMERO/backup`
  - `/OMERO` data backup
- Restore using scripts in `backup_and_restore/`:
  - `restore/restore_db.sh`/`.ps1`
  - `restore/restore_server.sh`/`.ps1`
  - The config dump is picked up by `00-restore-config.sh` on server startup
- Supports upgrade to newer PostgreSQL too (e.g. dump from 11, restore into 16)
- OMERO.server version must match w/ container, <a href="https://omero.readthedocs.io/en/stable/sysadmins/index.html#upgrading" target="_blank" rel="noopener noreferrer">upgrade</a> locally first if it doesn't.

→ See `backup_and_restore/README.md` for exact steps of such restore scripts.
It also describes the opposite (backing up containers).

---

## Scenario 3: Hybrid Deployment with Existing OMERO Server

- Keep your existing OMERO.server + PostgreSQL.
- Deploy (perhaps on a separate VM) only a subset of containers, e.g.:
  - `biomero`, `metabase`, `omeroweb`, `biomero-database`, `biomero-importer` (BIOMERO.analyzer & BIOMERO.importer)
  - `biomero`, `metabase`, `omeroweb`, `biomero-database` (BIOMERO.analyzer only)
  - `biomero-importer`, `metabase`, `omeroweb`, `biomero-database`  (BIOMERO.importer only)
- Connect these to the external OMERO server through the env/config variables.
  - Specifically, this would require an OMERO.grid connection between the 2 VMs. See for example the <a href="https://omero.readthedocs.io/en/stable/sysadmins/server-setup-examples.html#micron-oxford" target="_blank" rel="noopener noreferrer">Micron Oxford setup</a> and <a href="https://omero.readthedocs.io/en/stable/sysadmins/grid.html#nodes-on-multiple-hosts" target="_blank" rel="noopener noreferrer">OMERO docs on multiple hosts</a> for such a split.
- Still requires some minimal config/scripts additions to your OMERO server to make the rest work. For now, see the Dockerfile of `server` and its config in the deployment configurations.

→ Please contact us directly or on <a href="https://image.sc" target="_blank" rel="noopener noreferrer">image.sc</a> for help with such a scenario. We'd love to hear from you and see how we can help streamline such a deployment.

---

## Scenario 4: Full Non-Docker Install (Not Recommended)

- Manual install of OMERO + BIOMERO + Metabase on disk (e.g. with Ansible).
- Not officially supported — too many OS/env dependencies.
- Harder to upgrade with new versions or reproduce issues.
- But: All Dockerfiles are open source and all install steps can be followed if needed.
- Note that Windows is not supported by OMERO itself. And our dockerfiles only show installations on Linux too.

→ Use only if containerized deployment is not possible.

---

## Notes

- All mounts and port mappings are defined in the deployment configuration files.
- Environment files control ports, secrets, paths — adjust before deploy.
- Podman with SELinux is supported (e.g. on RHEL) with volume labels set.
- For restore/upgrade: follow OMERO docs: <a href="https://omero.readthedocs.io/en/stable/sysadmins/server-backup-and-restore.html" target="_blank" rel="noopener noreferrer">https://omero.readthedocs.io/en/stable/sysadmins/server-backup-and-restore.html</a>

---

## Upgrading BIOMERO Components

When upgrading the BIOMERO analyzer version (e.g. bumping `BIOMERO_VERSION` in `.env`), the
general process is:

1. **Update the version** in your `.env` or compose file and pull/rebuild containers.
2. **Check new configuration options** — review the release notes and/or 
   [BIOMERO configuration reference](https://nl-bioimaging.github.io/biomero/configuration-reference.html)
   for any newly introduced `slurm-config.ini` keys or environment variables. New options are
   always opt-in with safe defaults, so the stack will still work without them, but you may
   want to enable new features explicitly.
3. **Restart the stack.**
4. **Run Slurm Init** — navigate to **OMERO.biomero → Analyzer → Admin** and run the
   `SLURM_Init_environment` script.

   This step is required after any BIOMERO version upgrade because it regenerates the job
   scripts deployed on your Slurm cluster. New BIOMERO releases may update the job template,
   add new substitution variables, or change how env-file sourcing or GPU flags are injected.
   Skipping it means the cluster is running stale scripts that may be incompatible with the
   new worker behavior.


```{note}
The same **Run Slurm Init** step is required whenever you change SLURM paths, add or remove
workflows, or modify the `slurm-config.ini` — not just on version upgrades.
```

---

## Next Steps

- Want a quick install? → Start with Scenario 1.
- Migrating old data? → Use Scenario 2 and the restore scripts.
- Extending an existing OMERO setup? → Use Scenario 3.
- Avoiding containers? → Proceed with caution (Scenario 4).

Containers reduce complexity — you're not stuck managing dependencies or OS quirks.

---