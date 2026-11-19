Bilayers Workflows in BIOMERO
==============================

BIOMERO now supports the `Bilayers <https://bilayers.org>`_ workflow descriptor format
(``config.yaml``) in addition to the original BIAFLOWS ``descriptor.json`` format.
Bilayers was designed to generate user interfaces for containerized algorithms, and its
``config.yaml`` spec maps naturally onto BIOMERO's parameter-driven OMERO script UI.

This page explains what Bilayers adds, how BIOMERO interprets the spec, and what you
need to be aware of when writing a ``config.yaml`` for BIOMERO deployment.

Why Bilayers?
-------------

BIOMERO needs a machine-readable descriptor to understand how to run a workflow and
what to ask the user.  Until now the only supported format was the BIAFLOWS
``descriptor.json``, which describes a single, fixed I/O pattern: one input folder of
TIFF/OME-TIFF images and one output folder of TIFF/OME-TIFF results.  That covers a
lot of segmentation workflows, but it leaves no way to express:

* a workflow that expects OME-Zarr input rather than TIFF,
* a workflow that operates on whole HCS plates,
* a workflow that produces Zarr output.

Because there was no metadata for these cases, BIOMERO simply could not support them.

The Bilayers ``config.yaml`` provides that metadata.  Its dedicated ``inputs`` and
``outputs`` sections let you declare the exact CLI flags your algorithm expects, the
``type`` of data (``image``, ``array``, ``file``, …), and the accepted ``format`` list
(``tiff``, ``omezarr``, …).  BIOMERO reads those declarations and wires up the correct
data paths per workflow automatically.

In short: **use a Bilayers ``config.yaml`` when your workflow needs anything beyond
the standard TIFF ``inputfolder`` / ``outputfolder`` pattern.**  A workflow can describe
its metadata in a ``descriptor.json`` or a ``config.yaml``; BIOMERO will support both options.

.. raw:: html

   <div style="background: #e7f3ff; border: 1px solid #b3d9ff; padding: 15px; border-radius: 6px; margin: 20px 0;">
   <h4 style="margin: 0 0 8px 0; color: #0066cc;">📚 Bilayers config.yaml reference</h4>
   <p style="margin: 0 0 12px 0; font-size: 14px;">Full documentation on every field and type in the Bilayers spec.</p>
   <a href="https://bilayers.org/understanding-config/" target="_blank" style="background: #007bff; color: white; padding: 6px 14px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 13px;">Read the Bilayers docs →</a>
   </div>

How BIOMERO Reads a Bilayers Descriptor
-----------------------------------------

When BIOMERO fetches a workflow's descriptor from GitHub, it runs it through an
internal parser (``BilayersSchemaAdapter``) that converts the ``config.yaml`` into the
**biomero-schema** intermediate format.  This intermediate schema is what the rest of
BIOMERO — the OMERO script UI builder, the Slurm job generator, and the web UI — all
operate on.

The key mappings are:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Bilayers type
     - biomero-schema type
     - Notes
   * - ``image``, ``file``, ``array``
     - ``image`` / ``file`` / ``array``
     - Treated as server-managed (see below). Never shown to the user.
   * - ``integer``
     - ``integer``
     - Maps to ``omero.scripts.Int``.
   * - ``float``
     - ``float``
     - Maps to ``omero.scripts.Float``.
   * - ``checkbox``
     - ``boolean``
     - Maps to ``omero.scripts.Bool``.
   * - ``radio``, ``dropdown``
     - ``string``
     - Options become ``value-choices``; maps to ``omero.scripts.String`` with a dropdown.
   * - ``textbox``
     - ``string``
     - Free-text. If ``output_dir_set: True``, server-managed (see below).

I/O Directory Handling
-----------------------

This is the most important difference from BIAFLOWS.

.. tip::
   🎥 **Visual explanation · 0:58:** :ref:`See how one OME-Zarr transfer path supports flexible workflow interfaces <video-one-format-flexible-workflows>`.

In a BIAFLOWS workflow the job template always passes ``--infolder`` and
``--outfolder`` at fixed positions. The workflow must accept exactly those flags.

In a Bilayers workflow **the workflow decides** which CLI flags point to the input
and output directories. BIOMERO reads those flags directly from the descriptor and
injects the correct Slurm paths at job submission time — the user never sees or
configures them.

**Input directories** — ``inputs`` entries with ``type: image``, ``file``, ``array``,
``measurement``, or ``executable`` that are **not optional** are automatically wired to
``$DATA_PATH/data/in``.  Their ``cli_tag`` becomes the ``INPARAMS`` block in the Slurm
job script.

**Output directories** — ``outputs`` entries with a ``cli_tag`` are automatically wired
to ``$DATA_PATH/data/out``.  Additionally, any ``parameters`` entry with
``output_dir_set: True`` is *also* wired to ``$DATA_PATH/data/out``.

So use ``output_dir_set: True`` when your workflow receives its output path as a regular
parameter (e.g. ``--savedir``) rather than a dedicated output entry. 
However, you can also just git a ``cli_tag`` to an output entry. Both methods work; the choice is yours.

.. code-block:: yaml

   parameters:
     - name: save_dir
       type: textbox
       label: "Save directory"
       output_dir_set: True
       default: "/output_images"
       cli_tag: "--savedir"
       optional: True

BIOMERO will call the workflow with ``--savedir="$DATA_PATH/data/out"`` and will import
results from that path.  The parameter is hidden from the OMERO UI
(``set-by-server: true`` in the intermediate schema) so users cannot accidentally
override it.

**What BIOMERO sends and receives** — when a job runs, BIOMERO exports the
user-selected images from OMERO to ``$DATA_PATH/data/in`` in the format declared by
the descriptor (TIFF, OME-Zarr, Zarr plate, …) and passes that path to every ``inputs``
entry.  Results are collected from ``$DATA_PATH/data/out``, which is the path passed to
every ``outputs`` entry and every ``output_dir_set`` parameter.  All required ``inputs``
entries share the same ``data/in`` directory; all outputs share ``data/out``.

For OME-Zarr workflows, the directory contains a conventional OME-Zarr rather
than a BIOMERO-specific interchange format. See :doc:`zarr-workflow-development`
for the image and label data contract.

.. note::
   Extra files such as model weights or CSV files are not yet supported as inputs.
   For now, workflows that need additional files should either download them at runtime
   or package them inside the container image.  Support for sending non-image files
   from OMERO (e.g. attachments) to the workflow will be added in a future release.

Parameter Choices (radio / dropdown)
--------------------------------------

Radio and dropdown parameters use an ``options`` list of ``label``/``value`` pairs.
BIOMERO extracts the ``value`` list as ``value-choices`` and presents them as a
dropdown in the OMERO script UI.

.. code-block:: yaml

   parameters:
     - name: an_axis
       type: radio
       options:
         - label: 0
           value: 0
         - label: 1
           value: 1
         - label: 2
           value: 2
       default: 0
       cli_tag: "--an_axis"

When labels differ from values (e.g. ``label: "Option Alpha"``, ``value: alpha``),
BIOMERO stores both so the UI can show the human-readable label while passing the
correct value to the CLI.

Minimal Working Example
------------------------

Below is the smallest valid ``config.yaml`` that BIOMERO will accept, with one image
input, one output, and one user-facing parameter:

.. code-block:: yaml

   citations:
     - name: "MyWorkflow"
       license: "BSD 3-Clause"
       description: "Example workflow"

   docker_image:
     org: myorg
     name: w_myworkflow
     platform: "linux/amd64"

   exec_function:
     name: "generate_cli_command"
     cli_command: "python -m myworkflow"

   inputs:
     - name: inputfile
       type: image
       label: "Input image"
       subtype: [grayscale]
       cli_tag: "--input"
       optional: False
       format: [tiff, omezarr]
       mode: beginner

   outputs:
     - name: outputfolder
       type: image
       label: "Output image"
       cli_tag: "--output"
       optional: True
       format: [tiff]
       mode: beginner

   parameters:
     - name: threshold
       type: float
       label: "Threshold"
       description: "Detection threshold (0–1)."
       default: 0.5
       cli_tag: "--threshold"
       optional: True
       mode: beginner

BIOMERO will generate ``--input="$DATA_PATH/data/in" --output="$DATA_PATH/data/out"``
automatically and expose only ``threshold`` to the user in the OMERO UI.

Adding a Bilayers Workflow to Your BIOMERO Instance
-----------------------------------------------------

The process is the same as for BIAFLOWS workflows — register the GitHub repository
URL via the OMERO.biomero admin UI or in ``slurm-config.ini`` under ``[workflows]``:

.. code-block:: ini

   [workflows]
   W_MyWorkflow = https://github.com/myorg/W_MyWorkflow

BIOMERO will auto-detect the ``config.yaml`` (or ``descriptor.yaml`` / ``descriptor.json``),
parse it, and make it available in the script UI without any further
configuration.

See also: :doc:`workflow-development` for the full workflow packaging guide.

.. _workflow-file-url:

Pointing to a Specific Descriptor File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Instead of registering the repository root, you can point directly at a specific
``config.yaml`` or ``descriptor.json`` file inside the repository.  Use the raw
GitHub file URL as the workflow value:

.. code-block:: ini

   [workflows]
   W_MyWorkflow_Bilayers  = https://raw.githubusercontent.com/myorg/W_MyWorkflow/main/config.yaml
   W_MyWorkflow_BIAFLOWS  = https://raw.githubusercontent.com/myorg/W_MyWorkflow/main/descriptor.json

BIOMERO fetches that URL directly, detects the format from the file content, and
registers it as a normal workflow.

**Why is this useful?**

* **One repo, two descriptor formats.** If your workflow can be driven by either a
  Bilayers ``config.yaml`` or a BIAFLOWS ``descriptor.json`` (e.g. you maintain both
  for compatibility), you can register both independently under different workflow
  names.

* **Two UIs for one container.** You can ship two ``config.yaml`` files in the same
  repo — one for single-image analysis and one for HCS plate analysis (using
  ``subtype: plate``) — and register them as distinct workflows.  Users see two
  separate entries in the OMERO script menu, each with its own parameter set, but
  both run the same underlying container image.

  .. code-block:: ini

     [workflows]
     W_MyWorkflow           = https://raw.githubusercontent.com/myorg/W_MyWorkflow/main/config.yaml
     W_MyWorkflow_Plate     = https://raw.githubusercontent.com/myorg/W_MyWorkflow/main/config_plate.yaml

* **Mono-repo layout.** If you maintain multiple workflows in a single repository
  (each in its own subdirectory), you can register them individually:

  .. code-block:: ini

     [workflows]
     W_Segment   = https://raw.githubusercontent.com/myorg/workflows/main/segment/config.yaml
     W_Classify  = https://raw.githubusercontent.com/myorg/workflows/main/classify/config.yaml

.. note::
   When using a file URL, BIOMERO does **not** search the repository for other
   descriptors — it only reads the file you point at.  This is intentional: it lets
   you have both a ``config.yaml`` and a ``descriptor.json`` in the same repo without
   them interfering with each other.

Bilayers Features Not Supported by BIOMERO
--------------------------------------------

The Bilayers spec includes several features that BIOMERO does not currently support or
intentionally handles differently.  Write your ``config.yaml`` with these constraints
in mind.

**Argument ordering** (``cli_order``)

Bilayers allows you to fix positional argument order via ``cli_order``.  BIOMERO does
not use ordering information — all parameters are emitted as named ``--flag=value``
pairs and order is therefore irrelevant.  Do not rely on ``cli_order`` in descriptors
intended for BIOMERO.

**``hidden_args``**

Bilayers ``hidden_args`` allow embedding fixed CLI arguments that are invisible to the
user.  BIOMERO does not parse or apply ``hidden_args``.  The equivalent in BIOMERO is
to declare a parameter with ``set-by-server: true`` in a biomero-schema descriptor, but
this cannot be set from a Bilayers ``config.yaml`` at the moment.  If your workflow
needs a fixed hidden argument, hardcode it in the container's entry-point script
instead.

**``append_value`` on checkboxes**

Bilayers lets you control whether a boolean flag is emitted as ``--flag True`` /
``--flag False`` or as a presence/absence flag via ``append_value``.  BIOMERO always
emits booleans as ``--flag="True"`` or ``--flag="False"``; ``append_value`` is ignored.
Design your workflow's CLI to accept the ``--flag=True`` / ``--flag=False`` form.

**Extra file inputs** (model weights, CSVs, …)

As described in the I/O section above, BIOMERO currently only sends images to
``data/in``.  Non-image files referenced as ``inputs`` entries (model weights, CSV
files, etc.) are not forwarded to the HPC job.  Bundle such files in the container
image or have the workflow download them at runtime.  User-selectable file inputs are
planned for a future release.

**``exec_function`` / ``cli_command``**

Bilayers uses ``exec_function.cli_command`` to specify the command that runs inside the
container (e.g. ``python -m myworkflow``).  BIOMERO does not read or use this field.
The container image is invoked directly via its default entrypoint; the ``cli_command``
should therefore match what the container already executes on startup.  If your
algorithm requires a specific command, bake it into the container's ``ENTRYPOINT`` or
``CMD``.
