# Developer Getting Started

## Quick Setup for Development

Clone the repository and set up your development environment:

``` bash
git clone --recurse-submodules https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO.git
cd NL-BIOMERO

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Start development stack
docker-compose -f docker-compose-dev.yml up -d --build
```

Development Features -------------------

The development compose file includes:

- Live editing for the front-end plugin
- Development-specific configurations
- Special container setup for easier debugging

For detailed setup instructions, see the main README:

\# Containerized OMERO with BIOMERO

NL‑BIOMERO delivers a full containerized stack to run **OMERO** together
with the **BIOMERO 2.0** framework. It provides Docker/Podman
configurations and Compose files to deploy OMERO + BIOMERO subsystems
(importer, analyzer, OMERO.web plugin, databases, and auxiliary
services) — the recommended starting point for a FAIR‑oriented
bioimaging setup.

BIOMERO 2.0 is described in our preprint: \[“BIOMERO 2.0: end-to-end
FAIR infrastructure for bioimaging data import, analysis, and
provenance”\](<https://arxiv.org/abs/2511.13611>). It transforms OMERO
into a provenance‑aware, FAIR (findable, accessible, interoperable,
reusable) platform by combining: - containerized data import and
preprocessing (importer subsystem), - containerized or HPC‑based
analysis workflows (analyzer subsystem), - metadata enrichment,
versioning, and provenance tracking, - integrated workflow monitoring
and dashboards.

Using NL‑BIOMERO yields a unified environment where image data import,
preprocessing, analysis, and provenance tracking are managed end-to-end
— from raw data to processed results — in a reproducible, shareable,
FAIR‑compliant infrastructure.

It uses Docker Compose to setup an OMERO grid on one computer with a
server, web, processor, and a BIOMERO processor, importer and database.
If you want to experiment with a local HPC cluster, an example Docker
Compose setup is hosted \<a
href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO-Local-Slurm"
target="\_blank" rel="noopener noreferrer"\>here\</a\>.

This is an adaptation of OME's \<a
href="https://github.com/ome/docker-example-omero-grid" target="\_blank"
rel="noopener noreferrer"\>OMERO.server grid and OMERO.web
(docker-compose)\</a\> / \<a
href="http://www.openmicroscopy.org/site/support/omero5/sysadmins/grid.html#nodes-on-multiple-hosts"
target="\_blank" rel="noopener noreferrer"\>OMERO.server components on
multiple nodes using OMERO.grid\</a\>.

- OMERO.server listens on ports <span class="title-ref">4063</span> and
  <span class="title-ref">4064</span>
- OMERO.web listens on port <span class="title-ref">4080</span>
  (<http://localhost:4080/>)

\> ⚠️ **Warning:** This setup is mainly intended for demonstration or
development purposes. For professional deployments, refer to the
documented deployment scenarios in our documentation and see the
\[deployment scenarios\](./deployment_scenarios) folder. We **strongly
discourage** running Slurm inside Docker Compose for production; connect
BIOMERO to a real HPC cluster to ensure stability, full feature support,
and performance.

---

\## 🚀 Platform-Specific Deployment

\### Windows (Docker Desktop) Follow the **Quickstart** section below
for Windows deployment with Docker Desktop.

\### Ubuntu/Linux For Ubuntu/Linux deployments (with SSL support), see
our dedicated guide: 📖 **\[Ubuntu/Linux Deployment
Guide\](README.linux.md)**

---

\## Quickstart (Windows)

**Note**: This quickstart is based on Windows Docker Desktop and uses
<span class="title-ref">host.docker.internal</span> to communicate
between local clusters. Linux users should refer to the \[Ubuntu/Linux
guide\](README.linux.md).

\### 0. Prerequisites

- Docker Desktop
- Git for Windows
- a SSH keypair (@ ~/.ssh/id_rsa)
- Powershell

Then do all these steps in Powershell:

\### 1. Clone and Setup Clone this repository locally:

`` `bash git clone --recurse-submodules https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO.git cd NL-BIOMERO ``\`

\### 2. Configure Environment First, customize your environment file
\`.env\`:

`` `bash # Edit .env with your secure passwords and configuration # Edit biomeroworker/slurm-config.ini if you need different BIOMERO settings # Toggle UI components (both default to TRUE): # IMPORTER_ENABLED=TRUE   # Enables the BIOMERO.importer UI module # ANALYZER_ENABLED=TRUE   # Enables the BIOMERO.analyzer UI module # Set either to FALSE to hide that module from OMERO.web without removing containers ``\`

\### 3. Setup Slurm Connection (Optional) For local testing with a
containerized Slurm cluster:

`` `bash # Setup local Slurm cluster cd .. git clone https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO-Local-Slurm cd NL-BIOMERO-Local-Slurm cp ~/.ssh/id_rsa.pub . docker compose -f .\docker-compose-from-dockerhub.yml up -d --build   cd ../NL-BIOMERO ``\`

\### 4. Configure SSH Access Test Slurm connectivity:

`` `bash # from your host machine: ssh -i ~/.ssh/id_rsa -p 2222 -o StrictHostKeyChecking=no slurm@localhost # or from inside your biomeroworker container: ssh -i ~/.ssh/id_rsa -p 2222 -o StrictHostKeyChecking=no slurm@host.docker.internal exit ``\`

If successful, create an SSH alias:

`` `bash cp ssh.config.example ~/.ssh/config ``\`

If not successful, try forcing ownership and permissions (and then try
ssh again):

`` `bash # from your host machine: docker exec -it slurmctld bash -c "chown -R slurm:slurm /home/slurm/.ssh && chmod 700 /home/slurm/.ssh && chmod 600 /home/slurm/.ssh/authorized_keys" ``\`

\### 5. Deploy NL-BIOMERO Launch the full stack:

`` `bash # For development (with local builds) docker-compose build --no-cache # Then run in the background docker-compose up -d  # OR   # For production (using pre-built images) docker-compose --env-file .\.env -f .\deployment_scenarios\docker-compose-from-dockerhub.yml pull # wait ~10 min for download docker-compose --env-file .\.env -f .\deployment_scenarios\docker-compose-from-dockerhub.yml up -d ``\`

Monitor the deployment:

`` `bash docker-compose logs -f  # OR  docker-compose --env-file .\.env -f .\deployment_scenarios\docker-compose-from-dockerhub.yml logs -f ``\`
Exit w/ CTRL + C

Verify the alias works:

`` `bash # go inside your biomeroworker container: docker-compose exec biomeroworker bash # OR docker-compose --env-file .\.env -f .\deployment_scenarios\docker-compose-from-dockerhub.yml exec biomeroworker bash   # from inside your biomeroworker container: ssh localslurm exit exit ``\`

\### 6. Access the Interfaces - **OMERO.web**: <http://localhost:4080> -
**Login**: <span class="title-ref">root</span> /
<span class="title-ref">omero</span> (change default password) -
**Metabase**: <http://localhost:3000> - **Login**:
<span class="title-ref">admin@biomero.com</span> /
<span class="title-ref">b1omero</span> (change default password)

If you disabled modules via
<span class="title-ref">IMPORTER_ENABLED=FALSE</span> or
<span class="title-ref">ANALYZER_ENABLED=FALSE</span>, the corresponding
UI tabs/panels won't appear.

---

\## 📊 Data Import

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

\## 🛠️ Container Management

\### Basic Operations
`` `bash # Stop the cluster docker-compose down  # Remove with volumes (⚠️ deletes data) docker-compose down --volumes  # Rebuild single container docker-compose up -d --build --force-recreate <container-name>  # Access container shell docker-compose exec <container-name> bash ``\`

\### Useful Container Names -
<span class="title-ref">omeroserver</span> - OMERO server -
<span class="title-ref">omeroweb</span> - Web interface -
<span class="title-ref">biomeroworker</span> - BIOMERO processor -
<span class="title-ref">metabase</span> - Analytics dashboard

---

\## 🔧 Configuration

\### Slurm Connection Requirements See \<a
href="https://nl-bioimaging.github.io/biomero/" target="\_blank"
rel="noopener noreferrer"\>BIOMERO documentation\</a\> for comprehensive
setup details.

**Essential Components**: - **SSH Configuration**: Headless SSH to Slurm
server - Server IP/hostname - SSH port (usually
<span class="title-ref">22</span>) - Username and SSH keys - Alias
configuration in <span class="title-ref">~/.ssh/config</span> - **Slurm
Configuration**: Edit
<span class="title-ref">biomeroworker/slurm-config.ini</span> - SSH
alias (e.g., <span class="title-ref">localslurm</span>) - Storage paths:
<span class="title-ref">slurm_data_path</span>,
<span class="title-ref">slurm_images_path</span>,
<span class="title-ref">slurm_script_path</span>

\### Linux Considerations - SSH permissions:
<span class="title-ref">chmod -R 777 ~/.ssh</span> before deployment -
Use <span class="title-ref">postgres:16-alpine</span> for better
compatibility - See \[Ubuntu/Linux guide\](README.linux.md) for detailed
instructions

---

\## 🎨 Frontend Customizations This deployment includes several UI
enhancements:

- **🧩 OMERO.biomero Plugin**: Unified BIOMERO.importer and
  BIOMERO.analyzer tabs
- **📝 OMERO.forms**: Create custom metadata forms for users to fill in
- **🔘 Better Buttons**: Improved some button design and accessibility
- **🎭 Pretty Login**: Minor enhanced login page aesthetics

The previous codename "CANVAS" has been replaced by the official name
OMERO.biomero.

\### Custom Institution Branding Add your institution's logo to the
login page:

1.  Place logo files in:
    <span class="title-ref">web/local_omeroweb_edits/pretty_login/login_page_images/</span>
2.  And just mount the file over the current image, e.g.

`` `yml volumes:       - "./web/slurm-config.ini:/opt/omero/web/OMERO.web/var/slurm-config.ini:rw"       - "./web/local_omeroweb_edits/pretty_login/login_page_images/bioimaging.png:/opt/omero/web/venv3/lib/python3.9/site-packages/omeroweb/webclient/static/webclient/image/login_page_images/AmsterdamUMC-logo.png:ro"       - "./web/L-Drive:/data:rw" ``\`

More details in \[web/README.md\](web/README.md).

---

\## 📚 Additional Resources

- 📖 **\[Ubuntu/Linux Deployment\](README.linux.md)** - Production
  deployment guide
- 🧬 **\<a href="https://nl-bioimaging.github.io/biomero/"
  target="\_blank" rel="noopener noreferrer"\>BIOMERO
  Documentation\</a\>** - Analysis workflows
- 🏗️ **\<a
  href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO-Local-Slurm"
  target="\_blank" rel="noopener noreferrer"\>Local Slurm
  Cluster\</a\>** - Testing environment
- 🔬 **\<a href="https://omero.readthedocs.io/" target="\_blank"
  rel="noopener noreferrer"\>OMERO Documentation\</a\>** - Core platform
  docs

---

\## 🤝 Support

- **Issues**: \<a
  href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO/issues"
  target="\_blank" rel="noopener noreferrer"\>GitHub Issues\</a\>
- **Discussions**: \<a href="https://forum.image.sc/" target="\_blank"
  rel="noopener noreferrer"\>image.sc\</a\> (tag \#biomero)
- **Contact**: cellularimaging /at/ amsterdamumc.nl

Happy imaging! 🔬✨
