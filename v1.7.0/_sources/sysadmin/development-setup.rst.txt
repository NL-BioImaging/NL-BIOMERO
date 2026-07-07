Development & Demo Setup
=========================

.. warning::
   
   This guide is based on a snapshot in time development/WIP version of NL-BIOMERO. User interfaces, features, and configurations shown in the BIOMERO 101 installation guide may have been updated and changed since this documentation was created. This content does not necessarily represent the final product and should be used as a general reference for development and demonstration purposes.

This guide provides detailed instructions for setting up NL-BIOMERO for development and demonstration purposes.

.. note::
   For Linux deployments, see :doc:`linux-deployment`. For detailed technical architecture, see :doc:`../developer/architecture`. For advanced deployment scenarios, see :doc:`deployment`.

Quick Links to Other Guides
----------------------------

.. grid:: 2
   :gutter: 3

   .. grid-item-card:: 🏗️ System Architecture
      :link: ../developer/architecture
      :link-type: doc
      :class-card: sd-border-1
      
      Understand the complete BIOMERO 2.0 architecture with visual diagrams

   .. grid-item-card:: 🐧 Linux Production Setup  
      :link: linux-deployment
      :link-type: doc
      :class-card: sd-border-1
      
      Full Ubuntu/Linux deployment with SSL support

   .. grid-item-card:: 🔧 Advanced Deployment
      :link: deployment  
      :link-type: doc
      :class-card: sd-border-1
      
      Multiple deployment scenarios and configurations

   .. grid-item-card:: 🖥️ HPC Integration
      :link: slurm-integration
      :link-type: doc
      :class-card: sd-border-1
      
      Connect to SLURM clusters for scalable analysis

Windows Development Setup
-------------------------

For quick development setup on Windows with Docker Desktop:

**Prerequisites**
~~~~~~~~~~~~~~~~~

- Docker Desktop
- Git for Windows 
- SSH keypair (@ ~/.ssh/id_rsa)
- PowerShell

**Quick Setup Steps**
~~~~~~~~~~~~~~~~~~~~~

1. **Clone**: ``git clone --recursive https://github.com/NL-BioImaging/NL-BIOMERO.git``
2. **Configure**: Edit ``.env`` file with passwords and settings
3. **Deploy**: ``docker-compose up -d``
4. **Access**: OMERO.web at http://localhost:4080

.. seealso::
   **📖 Complete Setup Instructions**: See the `main README <https://github.com/NL-BioImaging/NL-BIOMERO>`_ for detailed Windows setup steps, including SSH configuration and local SLURM cluster setup for testing.

Container Management
--------------------

Basic container operations:

.. code-block:: bash

   # Start/stop services
   docker-compose up -d
   docker-compose down
   
   # View logs
   docker-compose logs -f
   
   # Rebuild single container
   docker-compose up -d --build --force-recreate <container-name>
   
   # Access container shell
   docker-compose exec <container-name> bash

Key container names: ``omeroserver``, ``omeroweb``, ``biomeroworker``

Configuration Overview  
----------------------

.. tabs::

   .. tab:: 🔑 SSH/HPC Setup
   
      Configure SLURM cluster access via :doc:`slurm-integration`
      
      - SSH keys and aliases
      - SLURM job submission
      - Storage path configuration

   .. tab:: 🎨 UI Customization
   
      Brand the interface via :doc:`ui-customization`
      
      - Login page branding
      - Logo replacement
      - Custom styling

   .. tab:: 🖥️ Admin Interface
   
      Manage settings via :doc:`omero-biomero-admin`
      
      - Workflow configuration  
      - Import/analyzer settings
      - User group management

BIOMERO 101 Installation Guide
-------------------------------

The BIOMERO 101 installation guide provides step-by-step instructions for setting up a development environment suitable for demonstrations and testing.

Key features of this setup:

- Easy development/demo deployment
- Uses Docker Desktop on Windows
- Includes all necessary components for basic functionality
- Suitable for learning and experimentation

For the complete BIOMERO 101 installation guide, see the PDF document in the deployment_scenarios folder: `BIOMERO 101 - installation guide.pdf`

This guide covers:

- Installing Docker Desktop
- Setting up WSL2 (Windows Subsystem for Linux)
- Cloning the repository
- Running the development setup
- Basic usage and testing

The development setup uses simplified configurations that are ideal for:

- First-time users
- Training sessions
- Feature demonstrations
- Local development work

.. raw:: html

   <embed src="../_static/BIOMERO 101 - installation guide.pdf" type="application/pdf" width="100%" height="600px" />
