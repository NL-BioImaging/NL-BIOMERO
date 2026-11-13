Developer Getting Started
=========================

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
-------------------

The development compose file includes:

* Containers that don't exit when web server stops (for easier development)
* Development-specific configurations  
* Special container setup for easier debugging
* Integration with local OMERO.biomero development

.. note::
   **Important**: The `-dev` compose file starts containers but **not** the web server. The web server is controlled by OMERO.biomero's ``./omero-init.sh`` script.

.. note::
   **Frontend Build Required**: Before running ``./omero-init.sh``, you must build the OMERO.biomero frontend assets. On Windows, you may need to install ``corepack`` and ``yarn`` first.

.. note::
   For detailed OMERO.biomero setup (including Node.js/yarn installation) and development workflow, see the `OMERO.biomero Setup and Development Guide <https://github.com/NL-BioImaging/OMERO.biomero?tab=readme-ov-file#setup-and-development-of-the-plugin-frontend>`_.

For general deployment instructions, see the main README:

.. include:: ../../README.md
   :parser: myst_parser.sphinx_