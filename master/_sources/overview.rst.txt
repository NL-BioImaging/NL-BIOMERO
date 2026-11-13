BIOMERO Videos
==============

This page is the canonical collection of NL-BIOMERO videos and their supporting
text. Start with the conceptual introduction if BIOMERO, OMERO, or HPC is new to
you. If you already know OMERO, the shorter architecture clips explain the
technical boundaries and data flows.

Conceptual introduction
-----------------------

.. _video-conceptual-introduction:

BIOMERO explained: a conceptual introduction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** A seven-minute introduction to the FAIR data challenge, OMERO data
management, and the way BIOMERO connects image data to reproducible analysis.

**Duration:** approximately 7 minutes

**For newcomers:** No prior knowledge of OMERO or HPC is required.

.. raw:: html

   <video controls preload="metadata" style="width: 100%; max-width: 800px; height: auto;" aria-label="BIOMERO explained: a conceptual introduction">
     <source src="https://github.com/NL-BioImaging/NL-BIOMERO/releases/download/v1.0.0/BIOMERO_2.mp4" type="video/mp4">
     Your browser does not support the video tag.
   </video>

.. note::
   **Production note:** This conceptual overview was generated with Google
   NotebookLM using NL-BIOMERO's GitHub repositories, documentation, and project
   publications available at the time of production. It was reviewed by the
   project team before publication. The video is intended as an accessible
   introduction; the current documentation remains authoritative for technical
   details and subsequent developments.

**Summary**

Bioimaging produces more data than manual approaches can reliably organize and
reproduce. OMERO centralizes image data, metadata, and access, while BIOMERO 1.0
connects OMERO to containerized analysis on HPC. BIOMERO 2.0 extends that bridge
with guided importing, a unified web interface, automated result return, and
provenance captured throughout the workflow. Together these components make
data and analyses easier to find, access, reproduce, and reuse.

**Read the technical documentation:** :doc:`developer/architecture`

.. _video-technical-architecture-clips:

Technical architecture clips
----------------------------

These short clips focus on one architectural idea at a time. The system-boundary
clip comes first because it provides the orientation needed for the other topics.

.. _video-what-nl-biomero-adds:

What NL-BIOMERO adds to OMERO
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** See where OMERO ends and the importer, analyzer, web interface, and
monitoring services supplied by NL-BIOMERO begin.

**Duration:** 1 minute 26 seconds

.. raw:: html

   <video controls preload="metadata" style="width: 100%; max-width: 800px; height: auto;" aria-label="What NL-BIOMERO adds to OMERO">
     <source src="https://github.com/NL-BioImaging/NL-BIOMERO/releases/download/documentation-videos-v1/BIOMERO_clip_what_NL_BIOMERO_adds_v1.mp4" type="video/mp4">
     Your browser does not support the video tag.
   </video>

**Summary**

OMERO remains the central image-data, metadata, and access-control system.
NL-BIOMERO surrounds it with OMERO.biomero for user-facing import and analysis,
BIOMERO.importer for storage-aware ingestion, BIOMERO.analyzer for HPC execution,
and Metabase for monitoring. BIOMERO.db records import and analysis events and
provides the provenance and live status views used by those services. NL-BIOMERO
connects this surrounding infrastructure rather than replacing OMERO.

**Read the technical documentation:** :doc:`developer/architecture`

.. _video-one-format-flexible-workflows:

One format, flexible workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Understand how a consistent OME-Zarr transfer path can still serve
workflows that consume TIFF, Zarr, or plate-aware Zarr input.

**Duration:** 58 seconds

.. raw:: html

   <video controls preload="metadata" style="width: 100%; max-width: 800px; height: auto;" aria-label="One format, flexible workflows">
     <source src="https://github.com/NL-BioImaging/NL-BIOMERO/releases/download/documentation-videos-v1/BIOMERO_clip_one_format_flexible_workflows_v1.mp4" type="video/mp4">
     Your browser does not support the video tag.
   </video>

**Summary**

Regardless of whether OMERO data originated as CZI, LOF, TIFF, or another
supported format, BIOMERO exports the selected pixels as OME-Zarr. Bilayers
workflows can consume this directly. BIAFLOWS workflows that expect TIFF can
first use an optional Zarr-to-TIFF conversion job on Slurm. Auxiliary attachments
can accompany the image input, while images and file outputs return to OMERO.

**Read the technical documentation:** :ref:`Analysis Pipeline <architecture-analysis-pipeline>`
and :ref:`Zarr and Plate Workflow Types <zarr-workflow-types>`

.. _video-in-place-importing:

In-place importing
~~~~~~~~~~~~~~~~~~

**Purpose:** Learn how NL-BIOMERO registers data from shared storage in OMERO
without making another copy of the original files.

**Duration:** 1 minute 24 seconds

.. raw:: html

   <video controls preload="metadata" style="width: 100%; max-width: 800px; height: auto;" aria-label="In-place importing">
     <source src="https://github.com/NL-BioImaging/NL-BIOMERO/releases/download/documentation-videos-v1/BIOMERO_clip_in_place_importing_v4.mp4" type="video/mp4">
     Your browser does not support the video tag.
   </video>

**Summary**

The selected OMERO group determines which remote-storage folder a user can
browse. A selected file or dataset becomes an asynchronous import order and can
optionally pass through a versioned preprocessing container. OME-Zarr can be
imported directly. The original data remains on shared storage, while the web
uploader provides a side entrance for individual files before starting the same
import route.

**Read the technical documentation:** :ref:`In-Place Import Pipeline <architecture-in-place-import>`
and :doc:`developer/containers/analyzer-importer-integration`

.. _video-provenance-while-working:

Provenance while the work happens
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** See how BIOMERO captures progress and provenance during imports and
analyses rather than trying to reconstruct the history afterward.

**Duration:** 1 minute 26 seconds

.. raw:: html

   <video controls preload="metadata" style="width: 100%; max-width: 800px; height: auto;" aria-label="Provenance while the work happens">
     <source src="https://github.com/NL-BioImaging/NL-BIOMERO/releases/download/documentation-videos-v1/BIOMERO_clip_provenance_while_working_v2.mp4" type="video/mp4">
     Your browser does not support the video tag.
   </video>

**Summary**

OMERO.forms preserves structured metadata and its form version. Import orders
record their source, requester, and preprocessing details, while workflow runs
record inputs, versions, parameters, Slurm identifiers, progress, status, and
results. BIOMERO.db stores these changes as immutable events and derives
query-friendly views for live import and workflow progress, result links, and
later inspection.

**Read the technical documentation:** :ref:`Monitoring and Analytics <architecture-monitoring-analytics>`
and :doc:`developer/containers/metabase`

.. _video-adding-analysis-workflow:

Adding an analysis workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Follow the path from a versioned workflow container and descriptor
to an analysis that users can run from OMERO.biomero.

**Duration:** 1 minute 26 seconds

.. raw:: html

   <video controls preload="metadata" style="width: 100%; max-width: 800px; height: auto;" aria-label="Adding an analysis workflow">
     <source src="https://github.com/NL-BioImaging/NL-BIOMERO/releases/download/documentation-videos-v1/BIOMERO_clip_adding_analysis_workflow_v1.mp4" type="video/mp4">
     Your browser does not support the video tag.
   </video>

**Summary**

A workflow combines a versioned headless container with an explicit interface:
a BIAFLOWS ``descriptor.json`` or Bilayers ``config.yaml``. BIOMERO uses this
metadata to construct the parameter interface and normally generate the Slurm
job. After an administrator registers and initializes the pinned workflow
version, users can run it through OMERO.biomero.

**Read the technical documentation:** :doc:`developer/workflow-development`

.. note::
   **Production and media note:** These technical clips were created with AI
   assistance using original NL-BIOMERO artwork and human-reviewed technical
   content. The animations were rendered programmatically, and the original
   soundtrack was synthesized without third-party audio samples.

.. _video-live-demonstration:

Live demonstration
------------------

NL-BIOMERO in practice
~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** See how users select data, run an analysis workflow, and inspect
results in a working NL-BIOMERO deployment.

**Presenter:** Torec Luik, NL-BioImaging / Amsterdam UMC

**Duration:** 5 minutes 39 seconds

.. raw:: html

   <div style="position: relative; width: 100%; max-width: 800px; aspect-ratio: 16 / 9;">
     <iframe src="https://www.youtube-nocookie.com/embed/gZcbqbHhwTA" title="BIOMERO live demonstration by Torec Luik" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen style="position: absolute; inset: 0; width: 100%; height: 100%; border: 0;"></iframe>
   </div>

.. note::
   **Recorded demonstration (April 2026).** The current interface remains broadly
   similar, but now includes additional functionality such as the web uploader
   and Bilayers workflows. Some dialogs, including the analysis output dialog,
   have also been updated.

`Watch the demonstration on YouTube <https://www.youtube.com/watch?v=gZcbqbHhwTA>`_.

The presentation was recorded for the Euro-BioImaging Image Data Community Days
2026 ToolsExchange session. It is an authentic demonstration of the platform,
not a complete tour of every feature in the current interface.

**Continue with the documentation:** :doc:`user/getting-started`
