.. _omero-biomero-plugin-administration:

OMERO.biomero Plugin Administration
===================================

Use **Import → Admin** to manage browser uploads and group folders, and
**Analyze → Admin** to configure workflows and their Slurm resources. This page
follows the plugin's settings sections and explains what to change, when it
takes effect, and which deployment features it requires.

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

General Settings
~~~~~~~~~~~~~~~~

These controls save automatically to the ``UPLOADER`` section of
``biomero-config.json``. They do not use the Analyzer's **Save Settings** button.

.. list-table:: Browser upload controls
   :header-rows: 1
   :widths: 30 70

   * - Control
     - Effect
   * - **Enable Web Uploader**
     - Shows the **Upload images** tab. The demo enables this; the web service
       still needs the uploader's storage and reverse-proxy configuration.
   * - **Upload to group folder**
     - Assembles uploads under ``uploads/<username>`` in the active group's
       mapped folder. Without a mapping, the default uploader destination is used.
   * - **Uploader Chunk Size (MB)**
     - Size of each resumable upload chunk, default 100 MB and minimum 1 MB.
       Keep it within the reverse proxy's request-body limit. This is a transfer
       chunk size, not a maximum image size.

See :doc:`resumable-uploader` for supported formats, destination permissions and
proxy setup. Conversion and preprocessing settings are managed separately from
these upload controls.

.. _group-folder-mappings:

Group Folder Mappings
~~~~~~~~~~~~~~~~~~~~~

**Purpose**: Restrict which OMERO groups have access to specific folders that the importer can import from.

**Configuration**:

- Each OMERO group can be mapped to one subfolder instead of the full mounted disk folder

**Setup Process**:

1. Select the target OMERO group
2. Open the folder picker and expand folders to reach the destination
3. Select the folder, confirm with **Select**, then click **Add mapping**

Use the edit or delete action in **Current Mappings** to change existing entries.
After editing, confirm the replacement with **Add mapping**. Deleting a mapping
saves immediately. The picker shows directories and filters out names
containing a dot, including hidden directories and stores such as ``.zarr``.
Folder mappings do not change filesystem permissions; the relevant services
still need access to the underlying storage.

Configuration File Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uploader settings are saved to the JSON configuration file selected by
``OMERO_BIOMERO_CONFIG_FILE``. Its default is ``~/.biomero/biomero-config.json``.

Group mappings are saved to the dedicated JSON file selected by
``OMERO_BIOMERO_GROUP_MAPPINGS_FILE`` (default
``~/.biomero/group-mappings.json``). The plugin also updates mappings in an
existing legacy ``biomero-config.json``. When reading both files, entries in
the dedicated mappings file take precedence. Share that file with the worker
when using :doc:`analyzer-importer-admin`.

**Docker Mount Example**:

.. code-block:: yaml

   volumes:
     - "./web/biomero-config.json:/opt/omero/web/OMERO.web/var/biomero-config.json:rw"

**Important**: Give the container user write access to the configuration files
and their containing directories so updates can be saved.

**Additional Settings**: The configuration file contains more UI variables than what the Admin tab can modify directly.

Analyzer Admin Configuration
----------------------------

.. note::
   Zarr and Plate workflow controls require the :doc:`analyzer-importer-admin`
   integration (``IMPORTER_ENABLED=true``). Use the matched component versions
   supplied by your NL-BIOMERO release for Zarr v3 and shallow results. Enabling
   an input-format switch does not install the importer or update a workflow's
   supported formats.

The Analyzer Admin screen is split into two sections: BIOMERO.analyzer settings (left) and OMERO scripts (right).

Overview
~~~~~~~~

**Left Side**
   Workflow and cluster settings grouped into expandable sections

**Right Side**
   OMERO scripts, organized with admin scripts "Slurm Init" and "Slurm Check Setup" shown by default

For a new workflow, save its configuration, run **Slurm Init**, then use
**Slurm Check Setup** to verify installation. The icons beside settings distinguish
changes that need initialization from those used directly by new runs:

* **Runtime**: applies to new runs or requests after saving; already running
  jobs keep their launch settings.
* **Slurm Init**: save first, then run the script to create directories, install
  images, regenerate scripts or rebuild analytics as applicable.

Deployment feature flags are configured outside this form and may require
recreating the affected services. They are distinct from both indicators.

Configuration Management
~~~~~~~~~~~~~~~~~~~~~~~~

The Analyzer form manages ``slurm-config.ini``. NL-BIOMERO shares this file
between OMERO.web and the workflow worker. With ``BIOMERO_SLURM_CONFIG_FILE``
set on both services, it is the authoritative file: additions, edits and
deletions in the form apply to that shared configuration.

Without that setting, BIOMERO retains its legacy layered configuration. Removing
a value in the form can reveal a value from another configuration file. The
note above **Save Settings** identifies which mode the deployment uses.

Supported environment overrides take precedence over INI values. A successful
save cannot override a worker's environment, and the web interface cannot show
worker-local overrides. Keep administrator-managed runtime settings in the
shared INI; use deployment configuration for feature flags and service secrets.

For container mounting and file sharing setup, see :doc:`slurm-integration`.

Settings Interface Usage
~~~~~~~~~~~~~~~~~~~~~~~~

**Edit Mode**
   Click the pencil icon to make fields editable

**Saving**
   Click **Save Settings** to write changes to disk. Resolve any validation
   errors first; their counts appear beside collapsed section titles.

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

**SSH Alias Field**: Selects the SSH host alias used to connect to Slurm. It must
resolve in the SSH configuration available to the services that submit jobs.
Run **Slurm Init** after changing the cluster connection.

.. note::
   The alias must match an entry in your SSH config. For SSH setup and configuration details, see :doc:`slurm-integration`.

SLURM Settings
~~~~~~~~~~~~~~

Paths
^^^^^

Use paths accessible to the Slurm account on the entrypoint and the relevant
compute nodes. Absolute paths are clearest; relative paths are resolved against
the remote account's home directory. Changing a path does not migrate existing
data or installed images.

.. list-table:: Storage and container paths
   :header-rows: 1
   :widths: 28 57 15

   * - Control
     - Purpose
     - Applies
   * - **Slurm Data Path**
     - Base directory for transferred inputs and workflow outputs on HPC.
     - Slurm Init
   * - **Slurm Images Path**
     - Workflow container images on HPC.
     - Slurm Init
   * - **Slurm Converters Path**
     - HPC format-conversion container images.
     - Slurm Init
   * - **Slurm Script Path**
     - Generated or custom Slurm job scripts.
     - Slurm Init
   * - **Slurm Data Bind Path**
     - Exposes storage inside workflow/conversion containers through
       ``APPTAINER_BINDPATH``. Leave blank when cluster defaults suffice.
     - Runtime
   * - **Apptainer Tmp Dir** / **Apptainer Cache Dir**
     - Locations for temporary image-build files and the container cache.
       Use when the normal locations lack space. Scheduled image pulls prefer
       node-local ``SLURM_TMPDIR`` when available.
     - Slurm Init

SACCT History Window
^^^^^^^^^^^^^^^^^^^^

Controls how far back Slurm job-history queries look. Set **SACCT Start Time**
to an absolute ``YYYY-MM-DD`` date, or **SACCT Days Ago** to a rolling window.
Days Ago takes precedence when both are set. With neither configured, the
built-in start date is ``2023-01-01``. Changes apply at runtime. This is separate
from the analytics rebuild window below.

Repositories
^^^^^^^^^^^^

Leave **Slurm Script Repository** empty to generate job scripts from workflow
descriptors using BIOMERO's template. Set it only when maintaining a compatible
repository of custom job scripts. Save and run **Slurm Init** after a change.

Processing Settings
^^^^^^^^^^^^^^^^^^^

Job Script Generation
"""""""""""""""""""""

Both switches change generated scripts and require **Slurm Init** after saving:

* **Env-File Submission** passes each job's parameters through a file. Use it
  when cluster SSH policies prevent reliable environment propagation to jobs.
* **Inject GPU Flag** makes GPU access conditional in generated scripts, so a
  workflow supporting both modes can use the same script on CPU and GPU.
  It does not make a GPU-only workflow capable of CPU execution or allocate
  GPUs by itself; resource requests come from the settings below.

Partition and GPU Fallback
""""""""""""""""""""""""""""""""

These are runtime defaults. Leave partition fields blank when the scheduler's
defaults are appropriate.

.. list-table:: Submission defaults
   :header-rows: 1
   :widths: 30 70

   * - Control
     - Effect
   * - **Default Partition**
     - Fallback for workflow and conversion jobs without a more specific
       partition. It takes precedence over a global ``sbatch_partition``.
   * - **Slurm Conversion Partition**
     - Partition for format-conversion jobs; takes precedence over Default Partition.
   * - **GPU Partition**
     - Partition used for GPU workflows unless the workflow sets its own partition.
   * - **GPU GRES** / **GPU GPUS**
     - GPU allocation using the cluster's ``--gres`` or ``--gpus`` convention.
       Choose one. Configuring both is invalid.

The workflow's **GPU Workflow** toggle activates GPU defaults. Per-workflow
SBATCH settings take precedence over matching defaults; check the effective
parameters shown on its card. A partition alone may not request a GPU. For
per-run CPU/GPU switching, the generated script must also use **Inject GPU Flag**.
Explicit GPU requests in Additional Slurm Parameters still apply independently
of the toggle.

Image Pull Settings
"""""""""""""""""""

**Pull Images via sbatch** moves container acquisition from the login node to
scheduled compute tasks. Slurm Init submits a bounded array for missing or
invalid images and reuses valid installed versions. When disabled, it uses the
legacy background shell path. These settings apply when running **Slurm Init**.

* **Pull CPUs**, **Pull Memory**, **Pull Time** and **Pull Partition** set resources
  for image acquisition, independently of analysis resources. Blank values
  inherit matching global SBATCH settings, then scheduler defaults.
* **Pull Concurrency** caps simultaneous image-acquisition tasks to control load
  on shared storage. It does not limit researchers' analysis jobs.

Use **Slurm Check Setup** to inspect readiness and per-image failures. Saving
these settings or refreshing GitHub version information does not install images.

ZIP Command
"""""""""""

**Slurm Zip Command** selects the HPC archive executable at runtime. Blank
auto-detects ``7z`` or ``7za``. Set ``zip`` to use Info-ZIP; the matching ``unzip``
executable must also be available. This controls archive handling, not
compression inside Zarr arrays.

Global Sbatch Parameters
""""""""""""""""""""""""""""""""

Add shared Slurm submission options as a full flag name and value, without
the leading ``--``. They are saved as ``[SLURM] sbatch_<flag>=<value>`` and apply
to new workflow, conversion and scheduled image-acquisition submissions.
Per-workflow overrides and dedicated conversion/image-pull settings take
precedence. Empty values are ignored.

Use the workflow's **Additional Slurm Parameters** for a single workflow.
See :ref:`workflow-sbatch-parameters` and the
`core Slurm configuration reference <https://nl-bioimaging.github.io/biomero/slurm-configuration.html>`_
for flag syntax and detailed precedence.

Shallow Zarr
~~~~~~~~~~~~

Avoids storing another copy of unchanged pixels in eligible workflow results.
Changed pixels and new labels are retained. If a result cannot safely be
shallowed, BIOMERO retains it in full. Referenced source stores must remain
available for viewing and reusing shallow results.

This section appears when ``BIOMERO_SHALLOW_ZARR`` is enabled in the deployment;
it also requires the Analyzer–Importer integration. The demo enables shallow
storage. Other deployments opt in explicitly. The **Remote shallowing** switch
chooses where processing happens; turning it off selects local importer
processing rather than disabling shallow storage.

.. list-table:: Shallow result processing controls
   :header-rows: 1
   :widths: 28 57 15

   * - Control
     - Purpose
     - Applies
   * - **Remote shallowing**
     - Runs the helper on HPC before the return archive is transferred.
       Off processes the full transferred result in the importer.
     - Runtime
   * - **Shallower image**
     - Versioned helper container. Install it before first remote use or after
       changing the image; keep the previous image while its jobs are outstanding.
     - Slurm Init
   * - **Shallower tool version**
     - Expected version in the helper's receipt. Must match the helper image
       and the importer's trust configuration.
     - Runtime
   * - **Shallower workers**
     - Positive worker count; also sets CPUs per task. The helper requests no GPU.
     - Runtime
   * - **Shallower partition**
     - Overrides Default Partition, then global ``sbatch_partition`` and finally
       the scheduler default.
     - Runtime
   * - **Shallower memory** / **Shallower time limit**
     - Helper limits. Blank values inherit matching global SBATCH settings,
       then scheduler defaults.
     - Runtime

The importer has its own validation/trust configuration and does not read this
form's INI file. Coordinate image/tool changes with that service. See
:doc:`remote-shallower` for enablement, compatible components, storage obligations
and measured costs and savings.

UI Settings
~~~~~~~~~~~

.. _plate-mask-preview:

**Plate Mask Preview**: Exposes a per-run option to create an extra OMERO Plate
showing one selected segmentation label in the original well/field layout.
This is useful for browsing masks directly in OMERO's Plate views. The primary
result Plate shows the image intensities; all labels remain available in the
OME-Zarr Viewer, even when this preview option is disabled.

The option is hidden by default. Enabling it allows users to request a preview;
it does not create one for every run. It requires Shallow Zarr and Plate results
imported into a Screen. If several labels are available, users select the label
by name. If no single label can be selected, only the preview is skipped.
Creating the preview adds OMERO objects and import work, while sharing the
existing label pixels. See :doc:`../developer/biomero-shallow-zarr` for details.

**Dangerous Jobs**: Allows users to create more than ten batch jobs. The
**Max Batch Jobs** setting caps that choice (10–1000; default 100). With Dangerous
Jobs disabled, the batching control stays within 2–10 jobs. This caps the user's
batch selection, not total cluster concurrency. Set a limit appropriate for your
cluster and OMERO capacity. These options apply after saving without Slurm Init.

Analytics Settings
~~~~~~~~~~~~~~~~~~

Records workflow events and builds the views used by monitoring, provenance and
dashboards. Keep **Track Workflows** enabled for the normal BIOMERO deployment.
Disabling it stops event recording and disables the listeners below, even when
their individual switches are on. Missing events cannot be reconstructed later.

.. list-table:: Tracking controls
   :header-rows: 1
   :widths: 30 70

   * - Control
     - Purpose
   * - **SQLAlchemy URL**
     - Analytics database connection. A deployment-provided ``SQLALCHEMY_URL``
       takes precedence; keep credentials in protected deployment configuration.
   * - **Enable Job Accounting**
     - Associates Slurm jobs with OMERO users for resource accounting.
   * - **Enable Job Progress**
     - Builds job-progress views used by the Status dashboard.
   * - **Enable Workflow Analytics**
     - Builds workflow timing and performance views for the dashboard.

These settings apply to new clients at runtime. Enabling a listener later can
replay recorded events; it cannot recover events from periods without tracking.

**Rebuild From Date** and **Rebuild From Days Ago** limit event replay when
**Slurm Init** rebuilds analytics views. Days Ago takes precedence when both
are set; leaving both blank gives a full rebuild. A limited rebuild excludes
older jobs from those views. It does not change the SACCT query window.
See :doc:`metabase-admin` for dashboard access and deployment configuration.

Converters Settings
~~~~~~~~~~~~~~~~~~~

**For Advanced Users Only**

These are HPC format converters used by analysis workflows. Importer
preprocessing (for example, converting Leica uploads to OME-Zarr) is configured
separately and is not changed here.

**Add Converter Button**: Click to add custom data converters

**Name Field**: Use ``X_to_Y`` format (e.g., ``zarr_to_tiff``)

**Docker Image Field**: Specify the container image URL

Use a versioned image that implements the required conversion interface. Save
and run **Slurm Init** to acquire it. The legacy Zarr-to-TIFF analysis route
receives v2 / OME-Zarr 0.4 input; native Zarr workflows skip that conversion.

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

1. **Click "Add Workflow"** to create a new workflow entry

2. **Configure Fields**:
   
   - **Model Name**: Unique lowercase workflow identifier; also used as its
     container folder under Slurm Images Path
   - **GitHub Repository**: Versioned URL to workflow code
   - **Slurm Job Script**: Job script path (usually auto-generated)
   - **Additional Slurm Parameters**: Custom SBATCH options for this workflow
   - **GPU Workflow**: Enables the shared GPU defaults for this workflow.
     Check the effective resource requests and any per-workflow overrides.
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

.. _workflow-sbatch-parameters:

Common SBATCH Parameters
^^^^^^^^^^^^^^^^^^^^^^^^

Enter one ``key=value`` pair at a time, without a leading ``--``, then press
Enter or add it using the control. Always use the extended flag name, such as
``cpus-per-task`` rather than ``c``. Values override the matching global defaults
for this workflow and apply to new runs after saving, without Slurm Init.

Choose memory, CPU, time, partition and GPU values supported by your cluster.
The book icon opens the official
`SBATCH options reference <https://slurm.schedmd.com/sbatch.html#SECTION_OPTIONS>`_.
Use either ``gres`` or ``gpus`` for GPU allocation, consistent with the shared
GPU settings. The card displays effective global settings and flags conflicts.

Editing Existing Workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Edit Model**: Click the pencil icon next to a workflow to modify its settings

**Version Updates**: Change the GitHub Repository URL to update workflow versions

The **up to date** count compares configured versions with GitHub releases; it
does not indicate whether their containers are installed on HPC. **Refresh**
rechecks that information, subject to GitHub rate limits. Use **Slurm Check
Setup** for actual installation status.

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

Existing stores keep their original format. The web app passes the selected
version to the workflow script. Compatible stores are reused; a mismatch uses
the normal OMERO export in the requested format and retains full results for
that run. It neither replaces the canonical nor registers a second one.
Matching shallow inputs reconstruct their managed labels; mismatched inputs
export the selected OMERO pixels without reconstructing inherited label layers.
This setting does not change importer preprocessing output formats.

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

**Saved Analyzer Setting Not Taking Effect**: Confirm the setting was saved,
check whether its icon requires Slurm Init, and check for worker environment
overrides or legacy layered configuration. Already running jobs retain their
launch settings.

**Importer Group Mapping Not Visible**: Re-select the active group; if its
folder list remains stale, log out and back in to reload it.

**Folder Missing from the Picker**: Expand its parent to load subfolders. Check
the mounted storage, service permissions and the picker's dot-name filter.

**Model Not Available After Adding**: Run the "Slurm Init" script after saving new workflow configurations

For SLURM connection, SSH, and deployment issues, see :doc:`slurm-integration`.

For Metabase-specific troubleshooting (e.g., "Message seems corrupt" errors), 
see :doc:`../developer/containers/metabase`.

Related Documentation
---------------------

* :doc:`slurm-integration` - SLURM cluster deployment, SSH setup, and system architecture
* :doc:`analyzer-importer-admin` - Analyzer + Importer integration (prerequisite for Zarr workflows)
* :doc:`remote-shallower` - Shallow storage deployment, helper setup and performance
* :doc:`resumable-uploader` - Browser upload storage, formats and reverse-proxy setup
* `BIOMERO configuration reference <https://nl-bioimaging.github.io/biomero/slurm-configuration.html>`_ - INI keys, environment overrides and submission precedence
* :doc:`../developer/containers/metabase` - Metabase container configuration and troubleshooting
* :doc:`../developer/containers/omeroweb` - OMERO.web container setup
* :doc:`deployment` - Initial deployment configuration
* :doc:`docker-compose-scenarios` - Container orchestration examples
