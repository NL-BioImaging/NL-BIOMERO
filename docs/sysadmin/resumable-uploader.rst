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

Enabling the Uploader
~~~~~~~~~~~~~~~~~~~~~

The uploader can be toggled on or off via the **Import -> Admin** tab:

1. Navigate to the **Admin** sub-tab under **Import**.
2. Locate the **General Settings** section.
3. Toggle **Enable Web Uploader**.

Storage Configuration
~~~~~~~~~~~~~~~~~~~~~

The uploader uses a two-stage storage process:

1. **Temporary Storage (Chunks)**: Chunks are stored in a temporary directory while the upload is in progress (Default: ``/tmp/omero_biomero_tus_upload`` inside the container, which is internal and doesn't require mapping).
2. **Final Destination**: Once fully assembled, the file is moved to a permanent/assembled storage directory on the BIOMERO filesystem (Default: ``/data/tus_destination``).

These paths are configured via environment variables:

- ``UPLOADER_CHUNKS_DIR``: Path for temporary chunks.
- ``UPLOADER_DESTINATION_DIR``: Path for assembled files (Default: ``/data/tus_destination``).

.. note::
   If **Upload to group folder** is enabled in Admin settings, the final destination will be overridden by the group-specific mapping (e.g., ``/data/uploads/username/group_folder/``).

Infrastructure Requirements
---------------------------

Nginx Configuration
~~~~~~~~~~~~~~~~~~~

Since the uploader sends file chunks (default 100MB) via HTTP PATCH requests, the web server (Nginx) must be configured to allow large request bodies.

In the containerized deployment, this is controlled by the ``CONFIG_nginx_client_max_body_size`` environment variable for the ``omeroweb`` service.

.. code-block:: yaml

   services:
     omeroweb:
       environment:
         - CONFIG_nginx_client_max_body_size=512m

File System Permissions
~~~~~~~~~~~~~~~~~~~~~~~

To prevent ownership and permission conflicts between different container processes (e.g., ``omero-web`` writing the uploaded files, and ``biomero-importer`` or ``omeroserver`` reading and importing them), the default configuration maps the assembled files directory (``/data/tus_destination``) to a shared Docker named volume named ``tus-destination``.

Since this volume is managed directly by Docker inside the Linux container environment, it bypasses host-level ownership translation issues. 

In Docker Compose, this is set up by mounting the shared volume in all relevant services:

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

If you are uploading directly to group folders (e.g., ``/data/uploads/username/group_folder/``), make sure the host paths have the correct permissions so the containers can read and write:

.. code-block:: bash

   # Example on the host machine
   chown -R 1000:1000 ./web/L-Drive/uploads

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
