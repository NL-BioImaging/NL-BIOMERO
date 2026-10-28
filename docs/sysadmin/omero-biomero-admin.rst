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

.. _group-folder-mappings:

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

.. note::
   **Zarr workflow support** (see :ref:`zarr-workflow-types` below) requires BIOMERO ≥ 2.4.0
   and biomero.scripts ≥ 2.4.0, and depends on the :doc:`analyzer-importer-admin`
   integration being enabled first (``IMPORTER_ENABLED=true``).

The Analyzer Admin screen is split into two sections: BIOMERO.analyzer settings (left) and OMERO scripts (right).

Overview
~~~~~~~~

**Left Side**
   All BIOMERO settings in UI form

**Right Side**
   OMERO scripts, organized with admin scripts "Slurm Init" and "Slurm Check Setup" shown by default

**Important Workflow**: Major changes (like adding new workflows) require:

1. Save settings in the left panel
2. Run the "Slurm Init" script from the right panel

Configuration Management
~~~~~~~~~~~~~~~~~~~~~~~~

**File Management**: The Admin interface manages the ``slurm-config.ini`` file automatically.

For container mounting and file sharing setup, see :doc:`slurm-integration`.

Settings Interface Usage
~~~~~~~~~~~~~~~~~~~~~~~~

**Edit Mode**
   Click the pencil icon to make fields editable

**Saving**
   Click "Save Settings" to write changes to disk via Django API

**Undo**
   Use "Undo All Changes" to reset current modifications

**Documentation**
   The **Administrator manual** link and book icons beside settings open the
   relevant guide in a new tab. Section help remains visible when collapsed.

**Cluster Scripts**
   Click **Slurm Init** or **Slurm Check Setup** in the settings guidance to open
   the same script dialog as the right-hand script cards. Save changed settings
   first, then review the script parameters and run it from that dialog.

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

UI Settings
~~~~~~~~~~~

**Plate Mask Preview**: Allows users to request a separate mask preview Plate
when importing workflow results.

**Dangerous Jobs**: Allows users to create more than ten batch jobs. The
**Max Batch Jobs** setting caps that choice. Set a limit appropriate for your
cluster and OMERO capacity. These options apply after saving without Slurm Init.

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

Workflows Settings
~~~~~~~~~~~~~~~~~~

**Purpose**: Add and manage analysis workflows available to users

.. _adding-new-workflows:

Adding New Workflows
^^^^^^^^^^^^^^^^^^^^

.. tip::
   🎥 **Visual explanation · 1:26:** :ref:`See how a pinned container and
   descriptor become a workflow users can run <video-adding-analysis-workflow>`.

1. **Click "Add Model"** to create a new workflow entry

2. **Configure Fields**:
   
   - **Name**: Workflow identifier (no spaces)
   - **GitHub Repository**: Versioned URL to workflow code
   - **Slurm Job Script**: Job script path (usually auto-generated)
   - **Additional Slurm Parameters**: Custom SBATCH options for this workflow
   - **Plate Workflow (Zarr Only)**: Accept an entire plate as one OME-Zarr
     store. Plate input requires Zarr and appears in the **Plate Workflows** tab.
   - **Also Allow Image Input**: Offer the same plate-capable workflow in the
     image tab as well. Requires plate support from the setting or descriptor.
   - **Zarr Format Required**: Pass OME-Zarr input directly to the workflow,
     skipping TIFF conversion. Also enabled by plate mode or a descriptor's Zarr
     requirement. Requires the :doc:`analyzer-importer-admin` integration.
   - **Zarr v3 input (OME-Zarr 0.5)**: Suboption below **Zarr Format Required**.
     Enable only for a workflow version that supports v3. Otherwise,
     input uses Zarr v2 / OME-Zarr 0.4. Hover a disabled switch for its prerequisite.

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

The icons beside settings show when changes apply. **Runtime** applies to new
runs or requests after saving. **Slurm Init** requires running that script after
saving. Hover an icon for its explanation. Sections containing both kinds show
both icons; individual fields or subgroups identify which applies.

After changing a workflow's repository, container folder or job script:

1. **Save Settings** first
2. **Run "Slurm Init" script** - installs changes on Slurm cluster
3. **Verify with "Slurm Check Setup"** - shows available/pending models

.. note::
   Workflow input modes, the Zarr version, GPU selection and Additional Slurm
   Parameters are runtime settings. They do not require Slurm Init.

In **Shallow Zarr**, the helper image requires Slurm Init. Remote/local selection,
the expected tool version, workers, partition, memory and time limit are runtime
settings. Install the helper before first enabling remote shallowing, and keep
its image and tool version aligned with the importer's trust configuration.
Environment overrides still take precedence over the saved INI values.

Analytics tracking and listener choices apply to new clients at runtime; the
analytics rebuild window applies when Slurm Init rebuilds the views.

.. _zarr-workflow-types:

Zarr and Plate Workflow Types
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These controls require the :doc:`analyzer-importer-admin` integration
(``IMPORTER_ENABLED=true``). They determine the workflow's input format and the
image/plate tabs in which it is offered.

Zarr Input and Version
^^^^^^^^^^^^^^^^^^^^^^

With **Zarr Format Required**, BIOMERO reuses a compatible backing store or
prepares OME-Zarr input and skips TIFF conversion. The indented **Zarr v3 input
(OME-Zarr 0.5)** switch selects v3; off selects v2 / OME-Zarr 0.4. Native Zarr
workflows can select v3 with either Bilayers or BIAFLOWS descriptors. TIFF
conversion always uses v2.

The version switch is disabled until Zarr input is enabled manually or required
by a plate or descriptor, and while the workflow card is locked. Hover or focus
the disabled control for the reason.
Disabling Zarr clears its v3 selection when no plate or descriptor requirement
remains. Both the form and API reject saving v3 without Zarr or plate input.

The existing cube icon turns green for v3 instead of adding another icon. Its
tooltip names the Zarr and OME-Zarr versions. Plate workflows keep their plate
icon, with the same version color and tooltip. These indicators follow current
edits; **Save Settings** applies them to new runs.

Existing stores keep their original format. When necessary, BIOMERO creates a
temporary workflow input with pixels and labels preserved. Results whose format
differs from the canonical source are retained in full. This setting does not
change importer preprocessing output formats.

Plate and Image Input
^^^^^^^^^^^^^^^^^^^^^

**Plate Workflow (Zarr Only)** preserves the well/field hierarchy in one
OME-Zarr input. Results are imported as plates, including available label views.
**Also Allow Image Input** additionally offers that same workflow in the image
tab, using the image dialog for those runs. Enable this only when the workflow
supports both input structures. Standard BIAFLOWS TIFF workflows do not support
plate input.

.. _biaflows-descriptor-note:

Descriptors and Saved Choices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Bilayers descriptors already declare Zarr and plate requirements. Reading a
workflow repository can enable those controls, and descriptor requirements also
apply at runtime. Administrators can additionally enable supported input modes
manually. BIAFLOWS descriptors do not declare these file-type requirements.

Bilayers does not yet declare Zarr v2/v3 capabilities. The version is therefore
an explicit administrator choice: general Zarr support never automatically
selects v3. Rereading a descriptor preserves a valid manual version choice.
Version capability interpretation can use this same descriptor path once the
Bilayers contract defines it.

**Save Settings** persists JSON workflow-name lists in the existing INI ``[UI]``
section: ``plate_workflows``, ``dual_mode_workflows``, ``zarr_workflows`` and
``zarr_v3_workflows``. A missing or empty v3 list selects v2. Renaming or deleting
a workflow updates its saved list membership; **Reset values** restores its
loaded choices. The displayed spelling is Zarr or OME-Zarr; existing INI keys
and internal ``ZARR`` format values remain compatible.

Slurm Check Setup Output
~~~~~~~~~~~~~~~~~~~~~~~~

The "Slurm Check Setup" script provides:

- Exact **READY**, **RUNNING**, and **FAILED** image counts
- Concise per-image failure reasons
- **Available Models** with validated, non-empty versions
- **Available Converters**
- **Available Data**
- The location of per-image array logs and structured status

**Example Output**:

.. code-block:: text

   Image initialization:
     READY: 15
     RUNNING: 0
     FAILED: 1
     Failure details:
       imagej:v2 - manifest unknown (exit 22)

**Status Indicators**:

- ``READY`` - the existing or newly built SIF passed runtime inspection
- ``RUNNING`` - the array task is queued or building
- ``FAILED`` - the task ended with a concise permanent or exhausted-retry reason



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
* :doc:`analyzer-importer-admin` - Analyzer + Importer integration (prerequisite for Zarr workflows)
* :doc:`../developer/containers/metabase` - Metabase container configuration and troubleshooting
* :doc:`../developer/containers/omeroweb` - OMERO.web container setup
* :doc:`deployment` - Initial deployment configuration
* :doc:`docker-compose-scenarios` - Container orchestration examples
