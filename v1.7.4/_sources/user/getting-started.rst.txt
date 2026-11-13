Getting Started
===============

First Steps with NL-BIOMERO
---------------------------

Access the Platform
~~~~~~~~~~~~~~~~~~~

After deployment, open OMERO.web at the address provided by your system
administrator (sometimes on port **4080**).

.. note::
   Default credentials are set during deployment. Contact your system administrator
   for login details. Administrators must change default passwords immediately after
   first login — see :doc:`../sysadmin/metabase-admin` for the security setup.

.. warning::
   **Do not log out of OMERO while a job is running.**

   Logging out, or closing the browser without the session being kept alive, will
   terminate your active OMERO session. Any running import or analysis jobs that
   were started under that session may fail or become orphaned.

   - **After closing the browser**, a session remains active for the configured
     session timeout period (default: 7 days). Jobs submitted before closing will
     continue to run.
   - **Logging out immediately ends the session**, regardless of running jobs.
     If you need to step away, simply close the browser tab instead of logging out.

   Administrators can adjust the session timeout via ``CONFIG_omero_sessions_timeout``
   in the deployment ``.env`` file.

OMERO.biomero Interface
-----------------------

OMERO.biomero is a plugin inside OMERO.web that provides a unified interface for
importing and analyzing imaging data. After logging in to OMERO.web, open the
`BIOMERO` panel from the top navigation bar.

The interface has the following main areas:

**Import**
   The Import section has subtabs:

   *Import Images*
      Browse your current group's remote shared storage and start an in-place import to bring
      your data into OMERO without duplicating files on disk.

   *Monitor*
      Track the progress of your import orders. An embedded Metabase dashboard shows
      all active and completed imports for your group. Each import order is identified
      by a **UUID** shown in the table — use this UUID to find your imported data back
      in OMERO.web.

**Analyze**
   The Analyze section has subtabs:

   *Run*
      Submit analysis jobs to the HPC cluster. The Run subtab itself has two sub-sections:

      - **Image Workflows** *(default)* — choose a workflow, select datasets or individual images from OMERO
        as input, configure workflow parameters, and submit.
      - **Plate Workflows** *(BIOMERO ≥ 2.4.0)* — plate-aware analysis that sends the
        entire plate as a single Zarr, preserving well and acquisition structure.
        Only plates can be selected as input. Only workflows configured as
        *Zarr Plate Workflows* by your administrator appear here.

   *Status*
      Track your submitted jobs and see their current state (queued, running,
      finished, failed). Each job is identified by a **Workflow ID (UUID)** shown in
      the dashboard. Once a job finishes, search for that UUID in OMERO.web to find
      your result images, which are imported automatically with full provenance
      metadata.


Next Steps
~~~~~~~~~~

1. **Import Data** — Use the **Import → Import Images** tab to bring your microscopy data into OMERO
2. **Run Analysis** — Open **Analyze → Run → Image Workflows** (or **Plate Workflows** for plates), choose a workflow, and submit
3. **Track Progress** — Check **Analyze → Status** to monitor running jobs; note the Workflow UUID for later
4. **View Results** — Search for the Workflow UUID in OMERO.web to find your imported result images
5. **Analytics** — Use **Import → Monitor** or Metabase to explore import and workflow statistics

Platform Overview from the README
-----------------

.. include:: ../../README.md
   :parser: myst_parser.sphinx_
   :start-after: ## 📊 Data Import
   :end-before: ## 🛠️ Container Management