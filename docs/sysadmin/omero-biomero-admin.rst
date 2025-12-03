.. _omero-biomero-plugin-administration:

OMERO.biomero Plugin Administration
===================================

The OMERO.biomero plugin provides two administrative interfaces for managing the Importer (ADI) and Analyzer components. These admin screens are accessible from the OMERO.web interface and provide essential configuration options for system administrators.

.. note::
   For technical details about the Metabase integration and container configuration, 
   see :doc:`../developer/containers/metabase`. For Metabase administrative setup
   and security configuration, see :doc:`metabase-admin`.

Accessing Admin Interfaces
---------------------------

The admin interfaces are available through the OMERO.web plugin after logging in as an administrator:

1. Navigate to the OMERO.biomero plugin in OMERO.web
2. Select the "Admin" tab for Import or Analyze

Importer Admin Configuration
----------------------------

The Importer Admin tab manages settings for BIOMERO.importer (formerly ADI).

Group Folder Mappings
~~~~~~~~~~~~~~~~~~~~~

**Purpose**: Restrict which OMERO groups have access to specific folders that the importer can import from.

**Configuration**:

- Currently supports 1:1 mapping only
- Each OMERO group can be mapped to one subfolder instead of the full mounted disk folder

**Setup Process**:

1. Select the target OMERO group
2. Choose the folder from the available options
3. Save the mapping

.. warning::
   **Folder Selection Limitation**: The folder selector only shows currently loaded subfolders (1st level). 
   
   **Workaround**: To select deeper subfolders:
   
   1. Go to the "Import Images" tab
   2. Navigate and expand the desired subfolder
   3. This loads sub-subfolders into ReactJS memory
   4. Return to Admin tab where they will now be selectable

.. warning::
   **Changes Not Visible Immediately**: Don't refresh (F5) to see changes. Instead:
   
   1. Log out and log in again
   2. Change "Select group" to a different group
   3. The mapping should take effect showing only the mapped subfolder as import options

Configuration File Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Storage**: Changes are written via Django API to a configuration file.

**Environment Variable**: ``OMERO_BIOMERO_CONFIG_FILE``
   - Example: ``/opt/omero/web/OMERO.web/var/biomero-config.json``

**Docker Mount Example**:

.. code-block:: yaml

   volumes:
     - "./web/biomero-config.json:/opt/omero/web/OMERO.web/var/biomero-config.json:rw"

**Important**: Ensure the container user has write access to this file.

**Additional Settings**: The configuration file contains more UI variables than what the Admin tab can modify directly.

Analyzer Admin Configuration
----------------------------

The Analyzer Admin screen is split into two sections: BIOMERO.analyzer settings (left) and OMERO scripts (right).

Overview
~~~~~~~~

**Left Side**: All BIOMERO settings in UI form
**Right Side**: OMERO scripts, organized with admin scripts "Slurm Init" and "Slurm Check Setup" shown by default

**Important Workflow**: Major changes (like adding new workflows) require:

1. Save settings in the left panel
2. Run the "Slurm Init" script from the right panel

Configuration Management
~~~~~~~~~~~~~~~~~~~~~~~~

**File Management**: The Admin interface manages the ``slurm-config.ini`` file automatically.

For container mounting and file sharing setup, see :doc:`slurm-integration`.

Settings Interface Usage
~~~~~~~~~~~~~~~~~~~~~~~~

**Edit Mode**: Click the pencil icon to make fields editable
**Saving**: Click "Save Settings" to write changes to disk via Django API
**Undo**: Use "Undo All Changes" to reset current modifications

Settings Categories
-------------------

SSH Settings
~~~~~~~~~~~~

**SSH Alias Field**: Enter the SSH alias name for your SLURM cluster connection.

.. note::
   The alias must match an entry in your SSH config. For SSH setup and configuration details, see :doc:`slurm-integration`.

SLURM Settings
~~~~~~~~~~~~~~

**Slurm Data Path**: Path where OMERO data will be stored on the cluster

**Slurm Images Path**: Path where workflow container images are stored

**Slurm Script Path**: Path where job scripts are generated and stored

**Slurm Script Repository**: (Optional) Custom GitHub repository for job scripts

.. warning::
   **Script Repository**: Leave empty to use auto-generated scripts (recommended). Only specify for advanced custom script repositories.

Analytics Settings
~~~~~~~~~~~~~~~~~~

.. danger::
   **Advanced Users Only - Do Not Modify**

**Tracking Checkbox**: Controls the BIOMERO eventsourcing system

.. warning::
   Disabling tracking will break progress monitoring and result displays in the web interface.

Converters Settings
~~~~~~~~~~~~~~~~~~~

**For Advanced Users Only**

**Add Converter Button**: Click to add custom data converters

**Name Field**: Use ``X_to_Y`` format (e.g., ``zarr_to_tiff``)

**Docker Image Field**: Specify the container image URL

.. warning::
   Custom converters require additional integration work. Most users should rely on built-in converters.

Models Settings (Workflows)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose**: Add and manage analysis workflows available to users

Adding New Workflows
^^^^^^^^^^^^^^^^^^^^

1. **Click "Add Model"** to create a new workflow entry

2. **Configure Fields**:
   
   - **Name**: Workflow identifier (no spaces)
   - **GitHub Repository**: Versioned URL to workflow code
   - **Slurm Job Script**: Job script path (usually auto-generated)
   - **Additional Slurm Parameters**: Custom SBATCH options for this workflow

3. **Save Settings** to store the configuration

Common SBATCH Parameters
^^^^^^^^^^^^^^^^^^^^^^^^

**Format**: Enter as ``key=value`` pairs (without ``--`` prefix)

**Examples**:

- **GPU allocation**: ``gres=gpu:1g.10gb:1``
- **Partition selection**: ``partition=luna-gpu-short``
- **Memory allocation**: ``mem=15GB``
- **Time limits**: ``time=08:00:00`` (d-hh:mm:ss format)

Editing Existing Workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Edit Model**: Click the pencil icon next to a workflow to modify its settings

**Version Updates**: Change the GitHub Repository URL to update workflow versions

**Parameter Management**: Add, edit, or delete Additional Slurm Parameters

**Reset Changes**: Use "Reset values" button to undo modifications to a specific workflow

**Remove Workflow**: Click "Delete model" to remove a workflow entirely

.. important::
   Always click "Save Settings" after making any modifications.

Required Follow-up Actions
^^^^^^^^^^^^^^^^^^^^^^^^^^

After model changes (except Additional Slurm Parameters):

1. **Save Settings** first
2. **Run "Slurm Init" script** - installs changes on Slurm cluster
3. **Verify with "Slurm Check Setup"** - shows available/pending models

Slurm Check Setup Output
~~~~~~~~~~~~~~~~~~~~~~~~

The "Slurm Check Setup" script provides:

- **Available Models** (with versions)
- **Pending Models** 
- **Available Converters**
- **Available Data**
- **Singularity Log** for download progress monitoring

**Example Output**:

.. code-block:: text

   starting cellpose v1.3.1
   starting stardist v1.3.2
   FATAL: Image file already exists: "cellpose/w_nucleisegmentation-cellpose_v1.3.1.sif" - will not overwrite
   finished cellpose v1.3.1

**Status Indicators**:
- ``FATAL: Image file already exists`` - Good (no redownload needed)
- ``ERROR`` - Problem occurred
- ``starting/finished`` - Normal download process



Interface Troubleshooting
-------------------------

**Changes Not Visible**: Log out and log back in instead of using browser refresh

**Folder Selection Issues**: Navigate to Import Images tab first to load subfolders, then return to Admin tab

**Model Not Available After Adding**: Run the "Slurm Init" script after saving new workflow configurations

For SLURM connection, SSH, and deployment issues, see :doc:`slurm-integration`.

For Metabase-specific troubleshooting (e.g., "Message seems corrupt" errors), 
see :doc:`../developer/containers/metabase`.

Related Documentation
---------------------

* :doc:`slurm-integration` - SLURM cluster deployment, SSH setup, and system architecture
* :doc:`../developer/containers/metabase` - Metabase container configuration and troubleshooting
* :doc:`../developer/containers/omeroweb` - OMERO.web container setup
* :doc:`deployment` - Initial deployment configuration
* :doc:`docker-compose-scenarios` - Container orchestration examples