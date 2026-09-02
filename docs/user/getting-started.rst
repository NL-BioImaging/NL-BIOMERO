Getting Started
===============

This guide follows the tasks most people perform in OMERO.biomero: adding data,
running a workflow, monitoring progress, and finding results.

Before You Start
----------------

Open OMERO.web at the address provided by your system administrator and select
the **BIOMERO** panel from the top navigation bar. The active OMERO group matters:
it controls which remote-storage folder you can browse and where imported or
analyzed data is placed.

.. warning::
   Do not log out while an import or analysis is running. Closing the browser
   keeps the OMERO session alive until its configured timeout, but logging out
   ends the session immediately and may leave active work unable to finish.

.. tip::
   🎥 **Live demonstration · 5:39:** :ref:`See NL-BIOMERO in practice
   during a real session <video-live-demonstration>`. The current interface has
   since gained the web uploader, Bilayers workflows, and some updated dialogs.

Interface at a Glance
---------------------

The available tabs depend on the features enabled by your administrator.

**Import**
   **Import Images**
      Browse the remote-storage folder mapped to your active OMERO group and
      start an in-place import.

   **Upload Images** *(when enabled)*
      Upload supported individual files from your computer. After the upload
      completes, the files enter the same asynchronous importer route. See the
      :doc:`../sysadmin/resumable-uploader` guide for supported files and
      additional details.

   **Monitor**
      Follow active and completed import orders. Each order has a UUID that can
      be used when locating data or asking an administrator for help.

**Analyze**
   **Image Workflows**
      Run workflows on selected datasets or individual images.

   **Plate Workflows** *(when configured)*
      Run plate-aware workflows that receive a complete plate as Zarr and
      preserve its well and acquisition structure.

   **Status**
      Follow queued, running, completed, and failed workflow runs. Each run has
      a Workflow ID (UUID) that also identifies its returned results.

.. _user-remote-storage-import:

How Do I Add Data Already on Remote Storage?
--------------------------------------------

Use this route for files or folder-based datasets that already reside on shared
storage:

1. Select the OMERO group that should own the imported data.
2. Open **BIOMERO > Import > Import Images**.
3. Browse the folder made available to that group and select the data to import.
4. Choose the requested destination and preprocessing options, if any, then
   start the import.
5. Open **Import > Monitor** to follow the order and record its UUID.

The importer can optionally run a versioned preprocessing container before
registering the result. The original data remains on shared storage; OMERO stores
the metadata and file references needed to access it.

.. _user-web-upload:

How Do I Add Data Directly from the Web?
----------------------------------------

Use the uploader for supported individual files on your computer:

1. Open **BIOMERO > Import > Upload Images**.
2. Select the target project or dataset shown by the interface.
3. Add the files and start the upload. Interrupted uploads can resume.
4. After assembly, OMERO.biomero creates an import order automatically.
5. Follow that order under **Import > Monitor**.

Folder-based formats and datasets whose directory structure must be preserved
should use **Import Images** from remote storage instead. If **Upload Images** is
not visible, the feature has not been enabled for this deployment. See
:doc:`../sysadmin/resumable-uploader` for the full behavior and supported-file
limitations.

.. _user-run-workflow:

How Do I Run a Workflow on My Images?
-------------------------------------

1. Make sure the input images, dataset, or plate are available in OMERO.
2. Open **BIOMERO > Analyze**.
3. Choose **Image Workflows** for images or datasets, or **Plate Workflows** for
   a compatible plate-aware workflow.
4. Select the workflow and its input data.
5. Configure the exposed parameters and output destination, then submit the run.
6. Open **Analyze > Status** and record the Workflow ID.

When processing finishes, BIOMERO returns supported image and file outputs to
OMERO with provenance metadata. Search for the Workflow ID in OMERO.web to find
the returned results.

.. _user-request-workflow:

How Do I Get a New Workflow into BIOMERO?
-----------------------------------------

You cannot install a new workflow from the normal user interface. Ask your
BIOMERO administrator and provide the workflow repository, required version,
expected input type, and intended use. The administrator must review, register,
and initialize the pinned workflow before it becomes available.

Workflow authors can start with :doc:`../developer/workflow-development`.
Administrators should follow :ref:`Adding New Workflows
<adding-new-workflows>`.

.. _user-faq:

Frequently Asked Questions
--------------------------

I cannot find my folder on the remote disk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First confirm that the correct OMERO group is active. Each group can be mapped
to a different remote-storage folder, so switching groups changes what the
browser can show. If the folder is still absent, ask an administrator to check
the :ref:`group-folder mapping <group-folder-mappings>` and storage permissions.

The Upload Images tab is missing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The web uploader is optional and must be enabled by an administrator. Use
**Import Images** if the data is already on shared storage, or ask the
administrator to review the :doc:`../sysadmin/resumable-uploader` setup.

The workflow I need is missing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It may not yet be registered or initialized, or it may appear only under
**Plate Workflows** because of its input type. Give the workflow name and desired
version to your administrator. Administrators can check :ref:`Adding New
Workflows <adding-new-workflows>`.

My import or workflow is not progressing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Keep the OMERO session active, check **Import > Monitor** or **Analyze > Status**,
and copy the order or Workflow UUID. Send that UUID and the approximate start
time to your administrator; those identifiers connect the interface entry to
the BIOMERO database and service logs.

Where are my workflow results?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After a successful run, search OMERO.web for the Workflow ID shown under
**Analyze > Status**. Returned images are imported automatically and carry
metadata linking them to the workflow run. If the run says it completed but no
results appear, give the Workflow ID to your administrator.
