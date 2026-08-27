Developer Getting Started
=========================

.. tip::
   🎥 **BIOMERO Videos:** Start with the :ref:`conceptual introduction
   <video-conceptual-introduction>` or explore the :ref:`short technical
   architecture clips <video-technical-architecture-clips>`.

Quick Setup for Development
---------------------------

Clone the repository and set up your development environment:

.. code-block:: bash

   git clone --recurse-submodules https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO.git
   cd NL-BIOMERO

   # Setup environment
   # Edit .env with your configuration if needed

   # Start development containers (web server will NOT be running yet)
   docker-compose -f docker-compose-dev.yml up -d --build

   # Clone OMERO.biomero plugin for development
   cd ..  # Go to parent directory (both repos must be in same parent folder)
   git clone https://github.com/NL-BioImaging/OMERO.biomero.git
   cd OMERO.biomero

   # Build the frontend (required before starting web server)
   cd webapp
   # On Windows:
   corepack yarn install
   corepack yarn build
   # On Linux:
   # yarn install
   # yarn build
   cd ..

   # Start OMERO web server (use WSL on Windows)
   ./omero-init.sh

   # OMERO web is now available at localhost:4080

Development Features
--------------------

The development compose file includes:

* Containers that don't exit when web server stops (for easier development)
* Development-specific configurations
* Special container setup for easier debugging
* Integration with local OMERO.biomero development

.. note::
   **Important**: The ``-dev`` compose file starts containers but **not** the web
   server. The web server is controlled by OMERO.biomero's ``./omero-init.sh``
   script.

.. note::
   **Frontend Build Required**: Before running ``./omero-init.sh``, you must build
   the OMERO.biomero frontend assets. On Windows, you may need to install
   ``corepack`` and ``yarn`` first.

.. note::
   For detailed OMERO.biomero setup (including Node.js/yarn installation) and
   development workflow, see the `OMERO.biomero Setup and Development Guide
   <https://github.com/NL-BioImaging/OMERO.biomero?tab=readme-ov-file#setup-and-development-of-the-plugin-frontend>`_.

Architecture Overview
---------------------

.. figure:: ../BIOMERO2_overview.png
   :alt: NL-BIOMERO architecture overview
   :align: center
   :width: 100%

   BIOMERO 2.0 architecture showing the integration of containerized analysis
   workflows (BIOMERO 1.0), preprocessing workflows (BIOMERO 2.0), and the
   unified OMERO.biomero web interface with OMERO.forms for metadata collection.

See :doc:`architecture` for the component boundaries, import and analysis
pipelines, monitoring, and workflow-development model.

Deployment Documentation
------------------------

* :doc:`../sysadmin/development-setup` for a detailed development environment
* :doc:`../sysadmin/deployment` for production deployment
* :doc:`../sysadmin/linux-deployment` for Linux-specific deployment guidance
* `Repository README <https://github.com/NL-BioImaging/NL-BIOMERO>`_ for the
  project-level introduction and quick-start commands
