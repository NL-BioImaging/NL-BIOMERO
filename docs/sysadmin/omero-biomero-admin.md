# OMERO.biomero Plugin Administration

The OMERO.biomero plugin provides two administrative interfaces for managing the Importer (ADI) and Analyzer components. These admin screens are accessible from the OMERO.web interface and provide essential configuration options for system administrators.

> **Note:**
> For technical details about the Metabase integration and container configuration, see [Metabase](../developer/containers/metabase.md).

## Accessing Admin Interfaces

The admin interfaces are available through the OMERO.web plugin after logging in as an administrator:

1. Navigate to the OMERO.biomero plugin in OMERO.web
2. Select the "Admin" tab for Import or Analyze

## Importer Admin Configuration

The Importer Admin tab manages settings for BIOMERO.importer (formerly ADI).

### Group Folder Mappings

**Purpose**: Restrict which OMERO groups have access to specific folders that the importer can import from.

**Configuration**:
- Currently supports 1:1 mapping only
- Each OMERO group can be mapped to one subfolder instead of the full mounted disk folder

**Setup Process**:

1. Select the target OMERO group
2. Choose the folder from the available options
3. Save the mapping

> **Warning:**
> **Folder Selection Limitation**: The folder selector only shows currently loaded subfolders (1st level).
>
> **Workaround:**
> 1. Go to the "Import Images" tab
> 2. Navigate and expand the desired subfolder
> 3. This loads sub-subfolders into ReactJS memory
> 4. Return to Admin tab where they will now be selectable

> **Warning:**
> **Changes Not Visible Immediately**: Don't refresh (F5) to see changes. Instead:
> 1. Log out and log in again
> 2. Change "Select group" to a different group
> 3. The mapping should take effect showing only the mapped subfolder as import options

### Configuration File Management

**Storage**: Changes are written via Django API to a configuration file.

**Environment Variable**: `OMERO_BIOMERO_CONFIG_FILE`
- Example: `/opt/omero/web/OMERO.web/var/biomero-config.json`

**Docker Mount Example**:

```yaml
volumes:
  - "./web/biomero-config.json:/opt/omero/web/OMERO.web/var/biomero-config.json:rw"
```

**Important**: Ensure the container user has write access to this file.

**Additional Settings**: The configuration file contains more UI variables than what the Admin tab can modify directly.

## Analyzer Admin Configuration

The Analyzer Admin screen is split into two sections: BIOMERO.analyzer settings (left) and OMERO scripts (right).

### Overview

- **Left Side**: All BIOMERO settings in UI form
- **Right Side**: OMERO scripts, organized with admin scripts "Slurm Init" and "Slurm Check Setup" shown by default

**Important Workflow**: Major changes (like adding new workflows) require:

1. Save settings in the left panel
2. Run the "Slurm Init" script from the right panel

### Configuration File Sharing

**File**: `slurm-config.ini` - shared between OMERO.web and BIOMERO worker

**Recommended Setup**:

```yaml
# OMERO.web service
volumes:
  - "./web/slurm-config.ini:/opt/omero/web/OMERO.web/var/slurm-config.ini:rw"

# BIOMERO worker service
volumes:
  - "./web/slurm-config.ini:/opt/omero/server/slurm-config.ini:rw"
```

This allows OMERO.web to write changes while BIOMERO worker reads the current configuration.

### Settings Interface Usage

- **Edit Mode**: Click the pencil icon to make fields editable
- **Saving**: Click "Save Settings" to write changes to disk via Django API
- **Undo**: Use "Undo All Changes" to reset current modifications

## Settings Categories

### 1. SSH Settings

**SSH Alias**: Configure the alias used by BIOMERO to connect to the Slurm cluster
- Must reflect an existing SSH alias configured in the BIOMERO container
- Used for headless connection to Slurm

### 2. Slurm Settings

- **Slurm Data Path**: Storage location for OMERO I/O data on Slurm cluster
- **Slurm Images Path**: Storage location for container images
- **Slurm Script Path**: Storage location for Slurm job scripts
- **Slurm Script Repository**: (Optional) GitHub repository URL for custom Slurm scripts

> **Warning:**
> **Script Repository**: Either use a repository with scripts for ALL workflows, or let BIOMERO generate scripts automatically (recommended). Only use custom repositories for advanced cases.

### 3. Analytics Settings

> **Danger:**
> **NOT RECOMMENDED FOR MODIFICATION**
>
> **FOR ADVANCED USERS ONLY**

**Tracking**: Controls BIOMERO 2.0 eventsourcing system
- **Warning**: Disabling tracking breaks views/listeners and progress monitoring
- **Dependencies**: Views/listeners create database tables from tracking records
- **Impact**: Progress tables in OMERO.biomero web plugin depend on this system

### 4. Converters Settings

**FOR ADVANCED USERS ONLY**

**Add Custom Converters**:
- **Naming Convention**: `X_to_Y` format (e.g., `zarr_to_tiff`)
- **Docker Image**: Specify container image (e.g., `cellularimagingcf/convert_zarr_to_tiff:1.14.0`)
- **Default Behavior**: BIOMERO generates `zarr_to_tiff` converter automatically

> **Warning:**
> **Manual Integration Required**: Custom converters require additional script modifications:
> 1. Modify Slurm Workflow script to use custom conversion
> 2. Update Run Workflow script for user selection
> 3. Ensure Slurm Remote Conversion script handles custom converter

### 5. Models Settings (Workflows)

**Primary Function**: Manage available workflows in BIOMERO

#### Adding New Workflows

Click "Add Model" and configure:

- **Name**: No spaces (becomes folder name on Slurm)
- **GitHub Repository**: Versioned URL (e.g., `https://github.com/user/repo/tree/v1.0.0`)
- **Slurm Job Script**: Usually `jobs/<name>.sh` (auto-generated default)
- **Additional Slurm Parameters**: SBATCH options specific to this workflow

#### Common SBATCH Parameters

Add as `<key>=<value>` format (without `--` prefix):

```text
# GPU allocation
gres=gpu:1g.10gb:1

# Partition selection
partition=luna-gpu-short

# Memory allocation
mem=15GB

# Time limits (d-hh:mm:ss)
time=08:00:00
```

#### Editing Existing Workflows

- **Edit Model**: Click pencil icon to modify settings
- **Version Updates**: Change GitHub Repository URL version
- **Parameter Management**: Add/edit/delete Additional Slurm Parameters
- **Reset**: "Reset values" button undos changes to specific model
- **Remove**: "Delete model" button removes workflow entirely

**Save Requirement**: Click "Save Settings" after modifications

#### Required Follow-up Actions

After model changes (except Additional Slurm Parameters):

1. **Save Settings** first
2. **Run "Slurm Init" script** - installs changes on Slurm cluster
3. **Verify with "Slurm Check Setup"** - shows available/pending models

### Slurm Check Setup Output

The "Slurm Check Setup" script provides:

- **Available Models** (with versions)
- **Pending Models**
- **Available Converters**
- **Available Data**
- **Singularity Log** for download progress monitoring

**Example Output**:

```text
starting cellpose v1.3.1
starting stardist v1.3.2
FATAL: Image file already exists: "cellpose/w_nucleisegmentation-cellpose_v1.3.1.sif" - will not overwrite
finished cellpose v1.3.1
```

**Status Indicators**:
- `FATAL: Image file already exists` - Good (no redownload needed)
- `ERROR` - Problem occurred
- `starting/finished` - Normal download process

## Security Considerations

- **Configuration Files**: Ensure proper file permissions for mounted configuration files
- **SSH Access**: Verify SSH aliases and key access for Slurm connectivity
- **Database Access**: Confirm BIOMERO worker can access shared configuration files

For initial security setup including Metabase integration, see [Metabase](../developer/containers/metabase.md).

## Troubleshooting

- **Changes Not Visible**: Log out and back in instead of refreshing
- **Slurm Connection Issues**: Verify SSH alias configuration and key access
- **Model Not Available**: Run "Slurm Init" after adding/modifying workflows
- **Permission Errors**: Check file permissions on mounted configuration files

For Metabase-specific troubleshooting (e.g., "Message seems corrupt" errors), see [Metabase](../developer/containers/metabase.md).

## Related Documentation

- [Metabase](../developer/containers/metabase.md) - Metabase container configuration and troubleshooting
- [OMERO Web](../developer/containers/omeroweb.md) - OMERO.web container setup
- [Deployment Guide](deployment.md) - Initial deployment configuration
- [Docker Compose Scenarios](docker-compose-scenarios.md) - Container orchestration examples
