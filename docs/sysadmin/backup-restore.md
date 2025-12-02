# Backup and Restore

> [!IMPORTANT]
> The backup and restore scripts and flows included here are examples
> for inspiration. They are not recommendations and should be reviewed,
> tested, and adapted to your environment and policies.

\# NL-BIOMERO Backup & Restore Scripts

**One-command backup and restore for NL-BIOMERO PostgreSQL databases,
OMERO server data/config, and Metabase dashboards.**

\> Important: The scripts and approaches described here are examples for
inspiration, not prescriptive recommendations. Always review, test, and
adapt to your specific environment, security policies, and operational
requirements.

\## Key Features

- **Synchronized backups:** All components use a single timestamp for
  consistency.
- **Flexible targets:** Backup/restore to Docker volumes or local
  folders.
- **Cross-platform:** Bash (Linux/macOS, Docker/Podman) and PowerShell
  (Windows).
- **Zero configuration:** Reads from
  <span class="title-ref">.env</span>, auto-detects containers.
- **Production ready:** Error handling, validation, cleanup.
- **Config hierarchy:** OMERO config can be restored/overridden in
  multiple ways.
- **Metabase/OMERO folder backup:** Can backup OMERO or Metabase
  directly from a host folder (no container needed).

---

\## Quick Start

\### Master Backup (Recommended)

Backs up OMERO DB, BIOMERO DB, OMERO server (data/config), and Metabase
with a single timestamp.

**Linux/macOS:**
`` `bash ./backup_and_restore/backup/backup_master.sh ``\`

**Windows:**
`` `powershell .\backup_and_restore\backup\backup_master.ps1 ``\`

**Creates:** -
<span class="title-ref">omero.{timestamp}.pg_dump</span> -
<span class="title-ref">biomero.{timestamp}.pg_dump</span> -
<span class="title-ref">omero-server.{timestamp}.tar.gz</span> (unless
<span class="title-ref">--skip-server-data</span>) -
<span class="title-ref">metabase.{timestamp}.tar.gz</span>

All files are placed in a timestamped subfolder under
<span class="title-ref">./backup_and_restore/backups/</span>.

---

\### Common Options

- <span class="title-ref">--skip-database</span> / \`-skipDatabase\`:
  Skip both OMERO and BIOMERO DB backup.
- <span class="title-ref">--skip-server</span> / \`-skipServer\`: Skip
  OMERO server backup.
- <span class="title-ref">--skip-metabase</span> / \`-skipMetabase\`:
  Skip Metabase backup.
- <span class="title-ref">--skip-server-data</span> /
  \`-skipServerData\`: Only backup OMERO config (no data tar).
- <span class="title-ref">--skip-server-config</span> /
  \`-skipServerConfig\`: Only backup OMERO data (no config export).
- <span class="title-ref">--output-directory \<dir\></span> /
  \`-outputDirectory \<dir\>\`: Custom backup location.
- <span class="title-ref">--omero-folder \<path\></span> /
  \`-omeroFolder \<path\>\`: Backup OMERO data directly from a host
  folder (no container needed).
- <span class="title-ref">--metabase-folder \<path\></span> /
  \`-metabaseFolder \<path\>\`: Backup Metabase directly from a host
  folder.

---

\### Typical Backup Workflow

`` `bash # 1. Stop user-facing containers (optional for consistency) docker-compose stop omeroweb metabase biomero-importer  # 2. Run master backup ./backup_and_restore/backup/backup_master.sh  # 3. Restart services docker-compose up -d ``\`

---

\### Typical Restore Workflow

`` `bash # 1. Stop all services docker-compose down  # 2. Restore databases ./backup_and_restore/restore/restore_db.sh  # 3. Restore OMERO server data/config ./backup_and_restore/restore/restore_server.sh  # 4. Restore Metabase dashboards ./backup_and_restore/restore/restore_metabase.sh  # 5. Update docker-compose.yml to use restored volumes/folders # 6. Start all services docker-compose up -d ``\`

---

\## Individual Script Usage

\### Database Backup

`` `bash ./backup_and_restore/backup/backup_db.sh ``<span class="title-ref"> -
Backs up OMERO and BIOMERO DBs from containers. - Output:
\`omero.{timestamp}.pg_dump</span>,
<span class="title-ref">biomero.{timestamp}.pg_dump</span>

\### Server Backup

`` `bash ./backup_and_restore/backup/backup_server.sh ``<span class="title-ref"> -
Backs up OMERO server data/config from container or host folder. -
Output: \`omero-server.{timestamp}.tar.gz</span> - Use
<span class="title-ref">--omero-folder \<path\></span> to backup from a
host folder (no container needed).

\### Metabase Backup

`` `bash ./backup_and_restore/backup/backup_metabase.sh ``<span class="title-ref"> -
Backs up Metabase folder (H2 DB, configs, plugins). - Output:
\`metabase.{timestamp}.tar.gz</span> - Use
<span class="title-ref">--metabase-folder \<path\></span> to specify a
custom folder.

---

\## Restore Scripts

- <span class="title-ref">restore/restore_db.sh</span> /
  \`restore/restore_db.ps1\`: Restore OMERO/BIOMERO DBs to containers or
  local folders.
- <span class="title-ref">restore/restore_server.sh</span> /
  \`restore/restore_server.ps1\`: Restore OMERO server data/config to
  volume or folder.
- <span class="title-ref">restore/restore_metabase.sh</span> /
  \`restore/restore_metabase.ps1\`: Restore Metabase dashboards/configs
  to folder.

---

\## OMERO Configuration Hierarchy

1.  **Backup config**:
    <span class="title-ref">/OMERO/backup/omero.config</span> (restored
    automatically)
2.  **Custom config files**:
    <span class="title-ref">/opt/omero/server/config/\*.omero</span>
    (mount in docker-compose)
3.  **Environment variables**:
    <span class="title-ref">CONFIG_omero\_\*</span> (override
    everything)

---

\## Example: Backup OMERO from Host Folder

`` `bash ./backup_and_restore/backup/backup_server.sh --omero-folder "/srv/omero" ``\`

\## Example: Backup Metabase from Host Folder

`` `bash ./backup_and_restore/backup/backup_metabase.sh --metabase-folder "/srv/metabase" ``\`

---

\## Requirements

- **Linux/macOS:** Docker or Podman, Bash 4+
- **Windows:** Docker Desktop, PowerShell 5.1+
- **For backup:** Running NL-BIOMERO containers (unless using folder
  mode)
- **For restore:** Internet access to pull images

---

\## Troubleshooting

- **Container not found:** Check <span class="title-ref">docker
  ps</span> or <span class="title-ref">podman ps</span>
- **Permission denied:** Ensure backup location is writable
- **Small backup file:** Check container names and credentials
- **Restore failed:** Check logs with <span class="title-ref">docker
  logs \<container\></span>
- **Config not loading:** Check
  <span class="title-ref">/OMERO/backup/omero.config</span> exists in
  restored volume/folder

---

\## Help

All scripts support <span class="title-ref">--help</span> or
<span class="title-ref">-help</span> for usage and options.

---

**For more details, see comments in each script or contact the
NL-BIOMERO team.**
