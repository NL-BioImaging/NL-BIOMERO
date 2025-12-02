# Deployment Guide

\# NL-BIOMERO Deployment & Upgrade Guide

This document outlines several deployment scenarios for the NL-BIOMERO
platform. Containers are available prebuilt and deployment is possible
on Linux, Windows (via Docker Desktop), or Podman (e.g. RHEL/SELinux).
Kubernetes setups should also be possible with shares between services.

\> Note: The scenarios in this document are examples for inspiration,
not official recommendations or complete solutions. You should adapt
them to your infrastructure, security posture, and operational
requirements.

For detailed docker-compose configurations for each scenario, see
\[Docker Compose Scenarios\](docker-compose-scenarios.md).

---

\## Scenario 0: Development & Demo

- Development-focused deployments with source code access
- Suitable for testing, development, and demonstration purposes
- Builds containers from local source code
- Can include special configurations for easier development workflow

→ See \[Docker Compose Scenarios\](docker-compose-scenarios.md) for
specific configurations and usage details.

---

\## Scenario 1: Fresh Deployment (no existing data)

- Deploy all containers using docker-compose (1 server) or across
  multiple VMs.

- Configuration files define all ports, mounts, and credentials.  
  - You can change mounted Docker volumes to be on-disk mounts.

- No OMERO data required.

- Works on Windows (Docker Desktop), Linux (Docker or Podman).

- For Kubernetes, adjust disk mounts and configs accordingly; some data
  needs to be shared between services.

→ See \[Docker Compose Scenarios\](docker-compose-scenarios.md) for
specific deployment configurations.

---

\## Scenario 2: Fresh Deployment with Existing Data

- Use this if restoring an existing OMERO backup.
- Requires OMERO backup (just follow the standard \<a
  href="https://omero.readthedocs.io/en/stable/sysadmins/server-backup-and-restore.html#backing-up-omero"
  target="\_blank" rel="noopener noreferrer"\>OMERO.server backup and
  restore\</a\>):
  - PostgreSQL dump (<span class="title-ref">pg_dump ...</span>)
  - Config dump (<span class="title-ref">omero config get</span>), store
    in <span class="title-ref">/OMERO/backup</span>
  - <span class="title-ref">/OMERO</span> data backup
- Restore using scripts in \`backup_and_restore/\`:
  - <span class="title-ref">restore/restore_db.sh</span>/\`.ps1\`
  - <span class="title-ref">restore/restore_server.sh</span>/\`.ps1\`
  - The config dump is picked up by
    <span class="title-ref">00-restore-config.sh</span> on server
    startup
- Supports upgrade to newer PostgreSQL too (e.g. dump from 11, restore
  into 16)
- OMERO.server version must match w/ container, \<a
  href="https://omero.readthedocs.io/en/stable/sysadmins/index.html#upgrading"
  target="\_blank" rel="noopener noreferrer"\>upgrade\</a\> locally
  first if it doesn't.

→ See <span class="title-ref">backup_and_restore/README.md</span> for
exact steps of such restore scripts. It also describes the opposite
(backing up containers).

---

\## Scenario 3: Hybrid Deployment with Existing OMERO Server

- Keep your existing OMERO.server + PostgreSQL.
- Deploy (perhaps on a separate VM) only a subset of containers, e.g.:
  - <span class="title-ref">biomero</span>,
    <span class="title-ref">metabase</span>,
    <span class="title-ref">omeroweb</span>,
    <span class="title-ref">biomero-database</span>,
    <span class="title-ref">biomero-importer</span> (BIOMERO.analyzer &
    BIOMERO.importer)
  - <span class="title-ref">biomero</span>,
    <span class="title-ref">metabase</span>,
    <span class="title-ref">omeroweb</span>,
    <span class="title-ref">biomero-database</span> (BIOMERO.analyzer
    only)
  - <span class="title-ref">biomero-importer</span>,
    <span class="title-ref">metabase</span>,
    <span class="title-ref">omeroweb</span>,
    <span class="title-ref">biomero-database</span> (BIOMERO.importer
    only)
- Connect these to the external OMERO server through the env/config
  variables.
  - Specifically, this would require an OMERO.grid connection between
    the 2 VMs. See for example the \<a
    href="https://omero.readthedocs.io/en/stable/sysadmins/server-setup-examples.html#micron-oxford"
    target="\_blank" rel="noopener noreferrer"\>Micron Oxford
    setup\</a\> and \<a
    href="https://omero.readthedocs.io/en/stable/sysadmins/grid.html#nodes-on-multiple-hosts"
    target="\_blank" rel="noopener noreferrer"\>OMERO docs on multiple
    hosts\</a\> for such a split.
- Still requires some minimal config/scripts additions to your OMERO
  server to make the rest work. For now, see the Dockerfile of
  <span class="title-ref">server</span> and its config in the deployment
  configurations.

→ Please contact us directly or on \<a href="https://image.sc"
target="\_blank" rel="noopener noreferrer"\>image.sc\</a\> for help with
such a scenario. We'd love to hear from you and see how we can help
streamline such a deployment.

---

\## Scenario 4: Full Non-Docker Install (Not Recommended)

- Manual install of OMERO + BIOMERO + Metabase on disk (e.g. with
  Ansible).
- Not officially supported — too many OS/env dependencies.
- Harder to upgrade with new versions or reproduce issues.
- But: All Dockerfiles are open source and all install steps can be
  followed if needed.
- Note that Windows is not supported by OMERO itself. And our
  dockerfiles only show installations on Linux too.

→ Use only if containerized deployment is not possible.

---

\## Notes

- All mounts and port mappings are defined in the deployment
  configuration files.
- Environment files control ports, secrets, paths — adjust before
  deploy.
- Podman with SELinux is supported (e.g. on RHEL) with volume labels
  set.
- For restore/upgrade: follow OMERO docs: \<a
  href="https://omero.readthedocs.io/en/stable/sysadmins/server-backup-and-restore.html"
  target="\_blank" rel="noopener
  noreferrer"\>https://omero.readthedocs.io/en/stable/sysadmins/server-backup-and-restore.html\</a\>

---

\## Next Steps

- Want a quick install? → Start with Scenario 1.
- Migrating old data? → Use Scenario 2 and the restore scripts.
- Extending an existing OMERO setup? → Use Scenario 3.
- Avoiding containers? → Proceed with caution (Scenario 4).

Containers reduce complexity — you're not stuck managing dependencies or
OS quirks.

---
