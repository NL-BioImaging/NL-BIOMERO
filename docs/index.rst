.. NL-BIOMERO documentation master file

Welcome to NL-BIOMERO's documentation!
======================================

|biomero_badge| |biomero_importer_badge| |omero_biomero_badge| |omero_forms_badge|

**NL-BIOMERO** delivers a complete FAIR-oriented bioimaging infrastructure built on OMERO and BIOMERO 2.0.

.. raw:: html

   <div style="display: flex; gap: 15px; margin: 20px 0; flex-wrap: wrap;">
   
   <div style="flex: 1; min-width: 300px; background: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; border-radius: 5px;">
   <h4 style="margin: 0 0 10px 0; color: #007bff;">🔬 What is BIOMERO 2.0?</h4>
   <p style="margin: 0; font-size: 14px;">An end-to-end platform that transforms OMERO into a provenance-aware system for bioimage data import, analysis, and sharing. <a href="https://arxiv.org/abs/2511.13611" target="_blank">📄 Read our preprint</a></p>
   </div>
   
   <div style="flex: 1; min-width: 300px; background: #f8f9fa; border-left: 4px solid #28a745; padding: 15px; border-radius: 5px;">
   <h4 style="margin: 0 0 10px 0; color: #28a745;">🚀 Why use NL-BIOMERO?</h4>
   <p style="margin: 0; font-size: 14px;">Get a unified environment where raw data flows seamlessly through automated import, preprocessing, analysis workflows, and results—all with complete provenance tracking and FAIR compliance.</p>
   </div>
   
   </div>

🚀 **Get Started Now!**
========================

Choose your path forward:

.. raw:: html

   <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0;">
   
   <div style="background: #e7f3ff; border: 1px solid #b3d9ff; padding: 20px; border-radius: 8px; text-align: center;">
   <h4 style="margin: 0 0 10px 0; color: #0066cc;">🆕 New Installation</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Fresh deployment on your infrastructure</p>
   <a href="sysadmin/deployment.html#scenario-1-fresh-deployment-no-existing-data" target="_blank" style="background: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">Start Here →</a>
   </div>
   
   <div style="background: #fff3e0; border: 1px solid #ffcc80; padding: 20px; border-radius: 8px; text-align: center;">
   <h4 style="margin: 0 0 10px 0; color: #e65100;">🔧 Existing OMERO</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Integrate with current OMERO setup</p>
   <a href="sysadmin/deployment.html#scenario-3-hybrid-deployment-with-existing-omero-server" target="_blank" style="background: #ff9800; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">Integration Guide →</a>
   </div>
   
   <div style="background: #f3e5f5; border: 1px solid #ce93d8; padding: 20px; border-radius: 8px; text-align: center;">
   <h4 style="margin: 0 0 10px 0; color: #7b1fa2;">⚡ Development</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Contribute to BIOMERO ecosystem</p>
   <a href="developer/getting-started.html" target="_blank" style="background: #9c27b0; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">Dev Setup →</a>
   </div>
   
   <div style="background: #f5f5f5; border: 1px solid #bdbdbd; padding: 20px; border-radius: 8px; text-align: center;">
   <h4 style="margin: 0 0 10px 0; color: #424242;">📚 Browse Components</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Explore individual platform components</p>
   <a href="#core-platform-components" style="background: #616161; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">Continue Reading ↓</a>
   </div>
   
   </div>

Core Platform Components
=========================

This documentation serves as your **main gateway** to the BIOMERO 2.0 ecosystem. Each component below links to both external documentation and local integration guides:

.. raw:: html

   <div style="text-align: center; margin: 40px 0 30px 0; position: relative;">
   <div style="position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent 0%, #667eea 20%, #667eea 80%, transparent 100%);"></div>
   <span style="background: white; padding: 0 20px; color: #667eea; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Analysis Framework</span>
   </div>

.. raw:: html

   <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 20px 0;">
   
   <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">⚡ BIOMERO.analyzer</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/r/cellularimagingcf/biomero" target="_blank" style="background: rgba(255,255,255,0.2); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/NL-BioImaging/biomero" target="_blank" style="background: rgba(0,0,0,0.3); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 15px; font-size: 11px;">Apache-2.0</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px; opacity: 0.9;">Remote high-performance computing workflow management for FAIR image analysis</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://nl-bioimaging.github.io/biomero/" target="_blank" style="background: #007bff; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,123,255,0.3);">📚 Documentation</a>
   <a href="https://github.com/NL-BioImaging/biomero?tab=readme-ov-file#readme" target="_blank" style="background: #6c757d; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(108,117,125,0.3);">📖 README</a>
   <a href="sysadmin/slurm-integration.html" target="_blank" style="background: #28a745; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 6px rgba(40,167,69,0.4);">⚙️ Admin Guide</a>
   </div>
   </div>
   
   <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">🛠️ BIOMERO.scripts</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/r/cellularimagingcf/omeroserver" target="_blank" style="background: rgba(255,255,255,0.2); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/NL-BioImaging/biomero-scripts" target="_blank" style="background: rgba(0,0,0,0.3); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 15px; font-size: 11px;">GPL-2.0</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px; opacity: 0.9;">Run BIOMERO.analyzer directly from OMERO.web via these BIOMERO.scripts</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://github.com/NL-BioImaging/biomero-scripts?tab=readme-ov-file#readme" target="_blank" style="background: #6c757d; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(108,117,125,0.3);">📖 README</a>
   </div>
   </div>
   
   </div>

.. raw:: html

   <div style="text-align: center; margin: 40px 0 30px 0; position: relative;">
   <div style="position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent 0%, #4facfe 20%, #4facfe 80%, transparent 100%);"></div>
   <span style="background: white; padding: 0 20px; color: #4facfe; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Data Management</span>
   </div>

.. raw:: html

   <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 20px 0;">
   
   <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">📥 BIOMERO.importer</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/r/cellularimagingcf/biomero-importer" target="_blank" style="background: rgba(255,255,255,0.2); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/NL-BioImaging/BIOMERO.importer" target="_blank" style="background: rgba(0,0,0,0.3); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 15px; font-size: 11px;">Apache-2.0</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px; opacity: 0.9;">User-friendly data import workflows for in-place importing - keep your raw data where it belongs!</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://github.com/NL-BioImaging/BIOMERO.importer?tab=readme-ov-file#readme" target="_blank" style="background: #6c757d; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(108,117,125,0.3);">📖 README</a>
   </div>
   </div>
   
   <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: white; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">📝 OMERO.forms</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/r/cellularimagingcf/omeroweb" target="_blank" style="background: rgba(255,255,255,0.2); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/NL-BioImaging/OMERO.forms" target="_blank" style="background: rgba(0,0,0,0.3); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 15px; font-size: 11px;">AGPL-3.0</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px; opacity: 0.9;">Flexible metadata annotation interfaces</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://github.com/NL-BioImaging/OMERO.forms?tab=readme-ov-file#readme" target="_blank" style="background: #6c757d; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(108,117,125,0.3);">📖 README</a>
   </div>
   </div>
   
   </div>

.. raw:: html

   <div style="text-align: center; margin: 40px 0 30px 0; position: relative;">
   <div style="position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent 0%, #a8edea 20%, #a8edea 80%, transparent 100%);"></div>
   <span style="background: white; padding: 0 20px; color: #4facfe; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">User Interfaces</span>
   </div>

.. raw:: html

   <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 20px 0;">
   
   <div style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">🧩 OMERO.biomero</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/r/cellularimagingcf/omeroweb" target="_blank" style="background: rgba(0,0,0,0.1); color: #333; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/NL-BioImaging/OMERO.biomero" target="_blank" style="background: rgba(0,0,0,0.2); color: #333; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(0,0,0,0.1); padding: 4px 8px; border-radius: 15px; font-size: 11px;">AGPL-3.0</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Modern web interfaces for BIOMERO.importer and BIOMERO.analyzer</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://github.com/NL-BioImaging/OMERO.biomero?tab=readme-ov-file#readme" target="_blank" style="background: #6c757d; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(108,117,125,0.3);">📖 README</a>
   <a href="sysadmin/omero-biomero-admin.html" target="_blank" style="background: #28a745; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 6px rgba(40,167,69,0.4);">⚙️ Admin Guide</a>
   </div>
   </div>
   
   <div style="background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); color: #333; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">📊 Metabase</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/r/metabase/metabase" target="_blank" style="background: rgba(0,0,0,0.1); color: #333; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/metabase/metabase" target="_blank" style="background: rgba(0,0,0,0.2); color: #333; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(0,0,0,0.1); padding: 4px 8px; border-radius: 15px; font-size: 11px;" title="AGPL-3.0 + Embedding License">Dual License</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Analytics and visualization dashboards for live progress tracking</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://www.metabase.com/docs/" target="_blank" style="background: #007bff; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,123,255,0.3);">📚 Documentation</a>
   <a href="https://www.metabase.com/license/" target="_blank" style="background: #ffc107; color: #212529; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(255,193,7,0.3);">📄 Licensing</a>
   <a href="developer/containers/metabase.html" target="_blank" style="background: #28a745; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 6px rgba(40,167,69,0.4);">⚙️ Setup Guide</a>
   </div>
   </div>
   
   </div>

.. raw:: html

   <div style="text-align: center; margin: 40px 0 30px 0; position: relative;">
   <div style="position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent 0%, #d299c2 20%, #d299c2 80%, transparent 100%);"></div>
   <span style="background: white; padding: 0 20px; color: #8b5cf6; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Infrastructure</span>
   </div>

.. raw:: html

   <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 20px 0;">
   
   <div style="background: linear-gradient(135deg, #d299c2 0%, #fef9d7 100%); color: #333; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">🔬 OMERO</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/r/cellularimagingcf/omeroserver" target="_blank" style="background: rgba(0,0,0,0.1); color: #333; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/ome/openmicroscopy" target="_blank" style="background: rgba(0,0,0,0.2); color: #333; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(0,0,0,0.1); padding: 4px 8px; border-radius: 15px; font-size: 11px;">GPL-2.0</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Renowned image data management platform for microscopy data</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://omero.readthedocs.io/" target="_blank" style="background: #007bff; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,123,255,0.3);">📚 Documentation</a>
   <a href="sysadmin/deployment.html" target="_blank" style="background: #28a745; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 6px rgba(40,167,69,0.4);">⚙️ Setup Guide</a>
   </div>
   </div>
   
   <div style="background: linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%); color: white; padding: 25px; border-radius: 12px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
   <h3 style="margin: 0; font-size: 18px;">🐳 Docker</h3>
   <div style="display: flex; gap: 8px; align-items: center;">
   <a href="https://hub.docker.com/u/cellularimagingcf" target="_blank" style="background: rgba(255,255,255,0.2); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🐳 DockerHub</a>
   <a href="https://github.com/moby/moby" target="_blank" style="background: rgba(0,0,0,0.3); color: white; padding: 4px 8px; text-decoration: none; border-radius: 4px; font-size: 11px;">🔍 Repository</a>
   <div style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 15px; font-size: 11px;" title="Apache-2.0 (CE/Engine) + Commercial (Desktop for enterprise)">Mixed License</div>
   </div>
   </div>
   <p style="margin: 0 0 15px 0; font-size: 14px; opacity: 0.9;">Easy deployment and scaling scenarios</p>
   <div style="display: flex; gap: 8px; flex-wrap: wrap;">
   <a href="https://docs.docker.com/compose/" target="_blank" style="background: #007bff; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,123,255,0.3);">📚 Documentation</a>
   <a href="https://docs.docker.com/engine/#licensing" target="_blank" style="background: #ffc107; color: #212529; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(108,117,125,0.3);">📄 Licensing</a>
   <a href="sysadmin/docker-compose-scenarios.html" target="_blank" style="background: #28a745; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 6px rgba(40,167,69,0.4);">⚙️ Setup Guide</a>
   <a href="developer/containers/index.html" target="_blank" style="background: #17a2b8; color: white; padding: 6px 12px; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; box-shadow: 0 2px 4px rgba(23,162,184,0.3);">📋 Our Containers</a>
   </div>
   </div>
   
   </div>

.. note::
   Deployment, migration, and backup procedures shown in this documentation are examples for inspiration. They are not prescriptive recommendations and may not address all environments. Always adapt and validate them for your organization's security, compliance, and operational requirements.

.. include:: _navigation.rst

.. raw:: html

   <div style="margin: 40px 0; padding: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 8px; border-left: 4px solid #667eea; text-align: center; color: #4a5568;">
   <p style="font-size: 14px; margin: 0; opacity: 0.8;">💡 This documentation covers containerized deployment scenarios. For non-containerized installations, refer to the individual component documentation.</p>
   </div>

