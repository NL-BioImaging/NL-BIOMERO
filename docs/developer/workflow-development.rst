Adding Your Workflow to BIOMERO
==================================

This guide is for **image analysts and workflow developers** who want to make their image analysis workflows available through the BIOMERO platform. Whether you're developing CellProfiler pipelines, Python-based analysis scripts, or other computational workflows, BIOMERO provides a standardized framework for packaging and deploying your work.

Overview
--------

BIOMERO enables you to:

* Package your analysis workflows as containerized, FAIR-compliant tools
* Make workflows discoverable and executable through OMERO.web
* Ensure reproducible analysis with proper provenance tracking
* Share workflows with the broader research community
* Run workflows on high-performance computing infrastructure via Slurm

Getting Started
---------------

Core Documentation
~~~~~~~~~~~~~~~~~~

The primary resource for workflow development is the **BIOMERO documentation**:

.. raw:: html

   <div style="background: #e7f3ff; border: 1px solid #b3d9ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
   <h4 style="margin: 0 0 10px 0; color: #0066cc;">📚 Main BIOMERO Workflow Guide</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Comprehensive guide for adding custom workflows to BIOMERO</p>
   <a href="https://nl-bioimaging.github.io/biomero/readme_link.html#how-to-add-your-new-custom-workflow" target="_blank" style="background: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">📖 Read the Guide →</a>
   </div>

Workflow Types & Tutorials
---------------------------

BIOMERO supports various types of workflows. Here are specific tutorials for popular tools:

CellProfiler Workflows
~~~~~~~~~~~~~~~~~~~~~~

.. raw:: html

   <div style="background: #f8f9fa; border: 1px solid #dee2e6; padding: 20px; border-radius: 8px; margin: 20px 0;">
   <h4 style="margin: 0 0 10px 0; color: #495057;">🧬 CellProfiler Integration</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Learn how to package CellProfiler pipelines for BIOMERO deployment</p>
   <a href="https://nl-bioimaging.github.io/biomero/tutorial_link.html#cellprofiler-tutorial" target="_blank" style="background: #6c757d; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">📖 CellProfiler Tutorial →</a>
   </div>

Python Workflows
~~~~~~~~~~~~~~~~

.. raw:: html

   <div style="background: #f8f9fa; border: 1px solid #dee2e6; padding: 20px; border-radius: 8px; margin: 20px 0;">
   <h4 style="margin: 0 0 10px 0; color: #495057;">🐍 Python Script Integration</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Package custom Python scripts as BIOMERO workflows, featuring CellExpansion example (simple mask expansion script similar to watershed)</p>
   <a href="https://nl-bioimaging.github.io/biomero/tutorial_link.html#cellexpansion-tutorial" target="_blank" style="background: #6c757d; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">📖 Python Tutorial →</a>
   </div>

FAIR Workflow Packaging
------------------------

Workshop Materials
~~~~~~~~~~~~~~~~~~

**ELMI 2025 BIOMERO Workshop** provides hands-on guidance for creating workflow containers:

.. raw:: html

   <div style="background: #fff3e0; border: 1px solid #ffcc80; padding: 20px; border-radius: 8px; margin: 20px 0;">
   <h4 style="margin: 0 0 10px 0; color: #e65100;">🎓 ELMI 2025 Workshop: Adding Workflow Containers to BIOMERO</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Complete workshop materials covering the creation of FAIR workflow containers, featuring the modern Stardist workflow example</p>
   <div style="display: flex; gap: 10px; flex-wrap: wrap;">
   <a href="https://doi.org/10.5281/zenodo.15642506" target="_blank" style="background: #ff9800; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">📦 Full Workshop Materials</a>
   <a href="https://zenodo.org/records/15642507/files/250604_ELMI_BIOMERO_workshop_SetupWorkflow.pdf?download=1" target="_blank" style="background: #f57c00; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">📄 Setup Guide PDF</a>
   </div>
   </div>

Real-World Example: Stardist Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The workshop demonstrates the creation of a modern, FAIRly-packaged workflow container:

.. raw:: html

   <div style="background: #e8f5e8; border: 1px solid #c3e6c3; padding: 20px; border-radius: 8px; margin: 20px 0;">
   <h4 style="margin: 0 0 10px 0; color: #2e7d32;">🌟 W_NucleiSegmentation-Stardist5d Example</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Modern Stardist-based nuclei segmentation workflow, demonstrating best practices for FAIR workflow packaging</p>
   <a href="https://github.com/maartenpaul/W_NucleiSegmentation-Stardist5d" target="_blank" style="background: #4caf50; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">🔍 View Repository →</a>
   </div>

Additional Resources
--------------------

BIAFLOWS Integration
~~~~~~~~~~~~~~~~~~~~

For workflows that are part of the BIAFLOWS ecosystem:

.. raw:: html

   <div style="background: #f3e5f5; border: 1px solid #ce93d8; padding: 20px; border-radius: 8px; margin: 20px 0;">
   <h4 style="margin: 0 0 10px 0; color: #7b1fa2;">🔗 BIAFLOWS Documentation</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Comprehensive documentation for BIAFLOWS workflow development and integration</p>
   <a href="http://biaflows-doc.neubias.org/" target="_blank" style="background: #9c27b0; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">📚 BIAFLOWS Docs →</a>
   </div>

Zarr Workflow Types (BIOMERO ≥ 2.4.0)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From BIOMERO v2.4.0 / NL-BIOMERO v1.5.0 onward, workflows can be configured to
receive **Zarr** input instead of the default flat folder of TIFF images. This is
set by a system administrator in the Analyzer Admin UI — it is not part of the
workflow descriptor itself.

Two modes exist:

**Zarr Workflow**
   The workflow receives a single Zarr file exported from OMERO. BIOMERO skips
   the TIFF conversion step and passes the Zarr directly to the SLURM job.

**Zarr Plate Workflow**
   The workflow receives an entire plate packaged as a single Zarr,
   preserving well and acquisition structure. Only plates can be submitted as
   input. These workflows appear under the dedicated **Plate Workflows** tab in
   the analyzer UI.

.. important::
   Standard BIAFLOWS workflows — which read a flat folder of TIFF images — are
   **not** compatible with either Zarr mode. A workflow must be specifically
   written to read Zarr input (or Zarr plate structure) in order to work with
   these options.

For the full explanation of how this interacts with the BIAFLOWS descriptor
format, why auto-detection is not currently possible, and plans for CWL-based
descriptor support, see :ref:`biaflows-descriptor-note` in
:doc:`../sysadmin/omero-biomero-admin`.

Development Workflow
--------------------

Typical workflow development process:

1. **Design Your Workflow**
   
   * Define input/output specifications
   * Identify computational requirements
   * Plan parameter configurations

2. **Container Development**
   
   * Follow the ELMI workshop guide for containerization
   * Implement FAIR principles in your packaging
   * Test locally before deployment

3. **BIOMERO Integration**
   
   * Follow the main BIOMERO workflow guide
   * Ensure compatibility with OMERO data structures
   * Test integration with BIOMERO.analyzer

4. **Deployment & Sharing**
   
   * Deploy to your BIOMERO instance
   * Share with the community through appropriate channels
   * Document usage and cite appropriately

.. note::
   **Coming Soon:** A comprehensive new document detailing workflow development best practices is in development. Watch this space for updates!

Next Steps
----------

* **Start with the tutorials** above that match your workflow type
* **Review the ELMI workshop materials** for hands-on examples
* **Examine the Stardist example** for modern best practices
* **Consult the BIOMERO documentation** for technical details
* **Engage with the community** for support and collaboration

Community Support
-----------------

Get help and connect with the BIOMERO community:

.. raw:: html

   <div style="background: #e7f3ff; border: 1px solid #b3d9ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
   <h4 style="margin: 0 0 10px 0; color: #0066cc;">💬 Community Forum</h4>
   <p style="margin: 0 0 15px 0; font-size: 14px;">Join discussions, ask questions, and share your experiences with the bioimage analysis community</p>
   <div style="display: flex; gap: 10px; flex-wrap: wrap;">
   <a href="https://forum.image.sc/tag/biomero" target="_blank" style="background: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">#biomero</a>
   <a href="https://forum.image.sc/tag/biaflows" target="_blank" style="background: #6f42c1; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold;">#biaflows</a>
   </div>
   </div>

.. tip::
   Consider starting with a simple workflow to understand the process before tackling more complex analysis pipelines. The community is available to help guide you through the development process.