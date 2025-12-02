# Getting Started

## First Steps with NL-BIOMERO

### Access the Platform

After deployment, access these interfaces:

- **OMERO.web**: <http://localhost:4080>
  - Login: `root` / `omero` (change default password)
- **Metabase**: <http://localhost:3000>
  - Login: `admin@biomero.com` / `b1omero` (change default password)

### Default Login

Use the default credentials to get started:

- **Username**: `root`
- **Password**: `omero`

> [!WARNING]
> **Security Setup Required**: Change default passwords and configure
> security settings immediately after first deployment.
>
> For OMERO: Change the default password after first login.
>
> For Metabase: Follow the complete security setup procedure in
> `../developer/containers/metabase` which includes changing passwords,
> updating database connections, and regenerating security keys.

### Next Steps

1.  **Import Data** - See `data-import` for uploading images
2.  **Run Analysis** - See `biomero-workflows` for bioimage analysis
3.  **View Results** - Use the web interface to explore results
4.  **Analytics** - Use Metabase for advanced visualization

## Platform Overview

To get started with data:

1.  **Web Import**: Use the Importer tab in OMERO.biomero at
    <http://localhost:4080/omero_biomero/biomero/>
2.  **OMERO.insight**: Download the \<a
    href="https://downloads.openmicroscopy.org/help/pdfs/getting-started-5.pdf"
    target="\_blank" rel="noopener noreferrer"\>desktop client\</a\>
    - Connect to <span class="title-ref">localhost:4063</span>
    - Login as <span class="title-ref">root</span> /
      <span class="title-ref">omero</span>

---

\## 🧬 BIOMERO - BioImage Analysis

Checkout the \<a href="https://nl-bioimaging.github.io/biomero/"
target="\_blank" rel="noopener noreferrer"\>BIOMERO documentation\</a\>
for detailed usage instructions.

\### Quick Workflow Example:

1.  **Initialize Environment**:
    - Run script: <span class="title-ref">biomero</span> \>
      <span class="title-ref">admin</span> \>
      <span class="title-ref">SLURM Init environment...</span>
    - ☕ Grab coffee (10+ min download time for a few workflow
      containers)
2.  **Run Analysis**:
    - Select your image/dataset
    - Run script: <span class="title-ref">biomero</span> \>
      <span class="title-ref">\_\_workflows</span> \>\`SLURM Run
      Workflow...\`
    - Configure import: Change <span class="title-ref">Import into NEW
      Dataset</span> → <span class="title-ref">hello_world</span>
    - Select workflow: e.g., <span class="title-ref">cellpose</span>
    - Set parameters: nucleus channel, GPU settings, etc.

OR

2.  **OMERO.biomero Analyzer UI**:
    - Use the Analyzer tab at
      <http://localhost:4080/omero_biomero/biomero/?tab=biomero>
    - Select your workflow: e.g.,
      <span class="title-ref">Cellpose</span>
    - Add Dataset, select the image(s) you want to segment
    - Fill in the workflow parameters in tab 2, e.g. nuclei channel 3
    - Select desired output target, e.g. Select Dataset
      <span class="title-ref">hello_world</span> again (don't forget to
      press ENTER if you're typing it); and Run!
    - Track your workflow status at the
      <span class="title-ref">Status</span> tab
3.  **View Results**:
    - Refresh OMERO <span class="title-ref">Explore</span> tab (in the
      Data tab; <http://localhost:4080/webclient/>)
    - Find your <span class="title-ref">hello_world</span> dataset with
      generated masks

---
