.. _resumable-uploader-administration:

Resumable Web Uploader
======================

The Resumable Web Uploader is a feature in OMERO.biomero that allows users to upload large image files directly through the browser. It uses the TUS protocol for resumable uploads, ensuring that large transfers can recover from network interruptions.

Overview
--------

The uploader is integrated into the "Import" tab of the OMERO.biomero plugin. When enabled, it provides a drag-and-drop interface powered by `Uppy <https://uppy.io/>`_.

Features:
- **Resumable**: Automatically resumes uploads after network failures or browser restarts.
- **Large File Support**: Supports multi-gigabyte uploads by splitting files into chunks.
- **File Types**: Supports all standard Bio-Formats single-file extensions.
- **Group-Aware**: Automatically routes files to specific storage locations based on the user's active group.
- **Auto-Import**: Once the upload is complete, the system automatically triggers a BIOMERO import task.

.. warning::
   **Unsupported File Types**: The web uploader does not support folder-based file formats (e.g., Leica ``.xlef``) or complex datasets that require maintaining a specific directory structure. These should continue to be imported via the standard BIOMERO in-place importer.

Administrative Configuration
----------------------------

Uploader Settings
~~~~~~~~~~~~~~~~~

The web uploader can be configured via the **Import -> Admin** tab under the **General Settings** section. These options are saved in the JSON configuration file (configured via the ``OMERO_BIOMERO_CONFIG_FILE`` environment variable, defaulting to ``~/.biomero/biomero-config.json``) inside the ``UPLOADER`` object:

1. **Enable Web Uploader**: 
   - **JSON Key**: ``enabled`` (bool, e.g., ``true`` or ``false``)
   - **Description**: Toggles the visibility of the "Upload images" tab in the OMERO.biomero plugin UI for users.

2. **Upload to group folder**: 
   - **JSON Key**: ``upload_to_group_folder`` (bool, e.g., ``true`` or ``false``)
   - **Description**: When enabled, completed uploads are assembled inside the active group's mapped folder under ``uploads/<username>/`` instead of the shared destination.
   - **Fallback**: If no group mapping exists for the group, it falls back to the default uploader destination subdirectory.

3. **Uploader Chunk Size (MB)**: 
   - **JSON Key**: ``chunk_size`` (integer, default: ``100``)
   - **Description**: Specifies the chunk size in MB for resumable uploads sent by the client. Lowering this value can help bypass proxy body limits (e.g., Nginx).

Storage Configuration
~~~~~~~~~~~~~~~~~~~~~

The uploader uses a two-stage storage process:

1. **Temporary Storage (Chunks)**: Chunks are stored in a temporary directory while the upload is in progress (Default: ``/tmp/omero_biomero_tus_upload`` inside the container).
2. **Final Destination**: Once fully assembled, the file is moved to a permanent/assembled storage directory on the BIOMERO filesystem (Default: ``/data/tus_destination``).

These paths are configured via backend environment variables:

- ``UPLOADER_CHUNKS_DIR``: Path for temporary chunks.
- ``UPLOADER_DESTINATION_DIR``: Path for assembled files (Default: ``/data/tus_destination``).

.. note::
   If **Upload to group folder** is enabled, the final destination is overridden by the resolved group directory mapping: ``<group_folder_path>/uploads/<username>/``.

Infrastructure & Permission Requirements
----------------------------------------

Nginx Configuration
~~~~~~~~~~~~~~~~~~~

Since the uploader sends file chunks via HTTP PATCH requests, the web server (Nginx) must be configured to allow request bodies equal to or larger than the configured chunk size.

In the containerized deployment, this is controlled by the ``CONFIG_nginx_client_max_body_size`` environment variable for the ``omeroweb`` service.

.. code-block:: yaml

   services:
     omeroweb:
       environment:
         - CONFIG_nginx_client_max_body_size=512m

Cross-Container Permission Requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To prevent ownership and permission conflicts, the files and folders used in the uploader must be accessible across multiple container processes:

1. **``omeroweb`` container** (runs Django/TUS backend):
   - Needs **write** access to ``UPLOADER_CHUNKS_DIR`` to write incoming file chunks.
   - Needs **write** access to the final target directory to assemble and move the finished file.
2. **``biomero-importer`` container** (runs the import background worker):
   - Needs **read and write** access to the final target directory to read the file, run optional preprocessing containers (which may run under OCI/Podman engines), and create output directories.
3. **``omeroserver`` container** (runs OMERO application server):
   - Needs **read** access to the final target directory to perform the in-place import and link files in the OMERO database.

Deployment Options
~~~~~~~~~~~~~~~~~~

**Option A: Shared Named Volume (Default)**

For standard single-host setups, the default configuration maps the assembled files directory (``/data/tus_destination``) to a shared Docker named volume (``tus-destination``).

Since this volume is managed directly by Docker inside the Linux container environment, it bypasses host-level ownership translation issues.

.. code-block:: yaml

   services:
     omeroweb:
       volumes:
         - tus-destination:/data/tus_destination
     omeroserver:
       volumes:
         - tus-destination:/data/tus_destination
     biomero-importer:
       volumes:
         - tus-destination:/data/tus_destination

   volumes:
     tus-destination:

**Option B: Host Mounts (Group Folder Mode)**

When **Upload to group folder** is enabled, the final destination directories resolve to host-mounted paths (e.g., mapped under the main ``/data/`` volume mount). 

Because the Docker engine mounts host folders directly, local OS permissions apply:
- The `omero-web`, `omero`, and `biomero-importer` processes typically run under UID and GID **1000**.
- Therefore, the host directories mapped for group folders must be owned by or writable by UID/GID **1000:1000**.

.. code-block:: bash

   # Example: Setting permissions on the host directory
   chown -R 1000:1000 /path/to/shared/group/directories

.. _uploader-data-flow:

Uploader Data Flow
------------------

.. tip::
   🎥 **Visual explanation · 1:24:** :ref:`See how uploads enter the same
   asynchronous in-place import route <video-in-place-importing>`.

The life cycle of an upload and its automatic import follows these steps:

1. **Initialize Uppy Client**
   - The user opens the "Upload images" tab in the OMERO.biomero plugin webclient.
   - The React frontend initializes the `Uppy` uploader with the `Tus` plugin, pointing to the `/omero_biomero/upload/` endpoint.
   - The chunk size is passed to the client (converted from `UPLOADER.chunk_size` setting).

2. **Upload Handshake (POST)**
   - The client initiates an upload by sending a `POST` request to `/omero_biomero/upload/` with `Upload-Length` and base64-encoded `Upload-Metadata` (such as filename, active group, and username).
   - `TusUploadView` verifies the user's OMERO session.
   - It generates a unique `resource_id` (UUID), initializes a temporary chunk file, and saves the metadata to `<resource_id>.meta`.
   - Returns a `201 Created` status with the upload resource `Location` header pointing to `/omero_biomero/upload/<resource_id>`.

3. **Streaming Chunks (PATCH)**
   - The client streams file chunks sequentially using `PATCH` requests to `/omero_biomero/upload/<resource_id>` with the current `Upload-Offset`.
   - The server validates the offset, streams the bytes in 1MB buffer steps directly to the chunk file, and updates the metadata offset on disk.

4. **File Assembly & Relocation**
   - Once `new_offset` equals the total file length, the server triggers finalization.
   - The server resolves the destination directory based on the user group mapping setting.
   - The completed file is moved from the chunk directory to the target path. In case of duplicate filenames, a numeric suffix (e.g. `_1`) is appended.
   - Temporary chunks and metadata files are deleted.

5. **Import Queue Trigger (POST)**
   - Upon successful completion, Uppy fires the `upload-success` event.
   - The frontend receives the finalized filename (exposed via the `Upload-Filename` header) and calls `POST /omero_biomero/importer/import_uploaded_file/`.
   - The request contains the `filename`, target `datasetId`, `datasetType` (Dataset or Project), and target `group`/`groupId`.

6. **Order Creation**
   - The backend checks user write access to the target dataset/project.
   - It searches candidate paths for the uploaded file.
   - Once validated, the backend queues a new order in the ingestion database (``imports`` table) via the ``log_ingestion_step`` utility with stage ``STAGE_NEW_ORDER`` ("Import Pending").

7. **Background Import Processing**
   - The ``biomero-importer`` daemon continuously polls the database for new orders in the ``STAGE_NEW_ORDER`` stage.
   - The worker validates the files, executes any associated preprocessing OCI containers (e.g., converting Incucyte datasets using Podman), and performs the final OMERO import to link the files in-place.

Troubleshooting
---------------

Upload Hangs or Resets
~~~~~~~~~~~~~~~~~~~~~~

- **Nginx Limit**: Check if the Nginx ``client_max_body_size`` is smaller than the chunk size (100MB).
- **Disk Space**: Ensure there is enough space in ``UPLOADER_CHUNKS_DIR`` to hold the incomplete uploads.
- **Permissions**: Verify that the ``omero-web`` user can create files in the upload directories.

Import Not Triggered
~~~~~~~~~~~~~~~~~~~~

- Check the Django logs (``var/log/OMEROweb.log``) for errors in the ``import_uploaded_file`` view.
- Ensure the BIOMERO.importer worker is running and can access the assembled files at the provided path.

Related Documentation
---------------------

* :doc:`omero-biomero-admin` - General administration of the plugin
* :doc:`slurm-integration` - Details on the import worker and cluster integration
