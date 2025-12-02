# Docker Compose Scenarios

\# NL-BIOMERO Deployment Scenarios and Docker Compose Files

This document outlines the different deployment scenarios for NL-BIOMERO
and maps them to corresponding docker-compose configurations.

\> Note: The docker-compose files and flows described here are examples
for inspiration. They are not official recommendations or complete
fixes; review and adapt them for your environment before production use.

\## Overview

NL-BIOMERO supports multiple deployment scenarios from development to
production. This guide will help you choose the right configuration for
your needs.

\## Important Usage Note

\> **Note:** All Docker Compose configurations in this project can be
run from the root of the git repository by: \> 1. Specifying the compose
file path with <span class="title-ref">-f</span> \> 2. Providing the
appropriate environment file with
<span class="title-ref">--env-file</span> \> 3. Using the
<span class="title-ref">up -d</span> flags to start containers in
detached mode \> \> **Example:** \>
`` `bash > docker compose -f ./deployment_scenarios/docker-compose-importer-only.yml --env-file .env.shared up -d > ``\`

The examples below assume you're in the
<span class="title-ref">deployment_scenarios</span> directory, but you
can run them from the project root with the above pattern. Just double
check the relative paths if you run them from somewhere else, especially
if they have to build the containers instead of pull them from
DockerHub.

---

\## Scenario 0: Development & Demo

\### Scenario 0.1: Local Development Setup **Purpose**: For developers
working on NL-BIOMERO components

**Docker Compose File**:
<span class="title-ref">docker-compose-dev.yml</span>

**Key Features**: - Builds images from local source code - Includes
development-specific settings - Keeps omeroweb running with
<span class="title-ref">tail -f /dev/null</span> to allow direct
development inside the container

**Usage**: `` `bash docker-compose -f docker-compose-dev.yml up -d ``\`

\### Scenario 0.2: Default (Local Build) **Purpose**: Testing with
locally built images

**Docker Compose File**:
<span class="title-ref">docker-compose.yml</span>

**Key Features**: - Builds all components from local source code -
Includes standard configuration - Suitable for testing before releasing
to production

**Usage**: `` `bash docker-compose up -d ``\`

---

\## Scenario 1: Fresh Deployment (no existing data)

\### Scenario 1.1: Standard Production Deployment **Purpose**:
Production deployment with prebuilt images

**Docker Compose File**:
<span class="title-ref">docker-compose-from-dockerhub.yml</span>

**Key Features**: - Uses prebuilt images from Docker Hub - Standard
configuration with production defaults - No existing OMERO data required

**Usage**:
`` `bash docker-compose -f docker-compose-from-dockerhub.yml up -d ``\`

\### Scenario 1.2: Production with SSL (Ubuntu) **Purpose**: Secure
production deployment with SSL

**Docker Compose File**:
<span class="title-ref">docker-compose-for-ubuntu-with-SSL.yml</span>

**Key Features**: - Includes Nginx for SSL termination - Configured for
Ubuntu environments - Provides secure HTTPS access to web interfaces

**Usage**:
`` `bash docker-compose -f docker-compose-for-ubuntu-with-SSL.yml up -d ``\`

---

\## Scenario 2: Fresh Deployment with Existing Data

\### Scenario 2.1: Restore from OMERO Backup **Purpose**: Deploy with
existing OMERO/BIOMERO data

**Docker Compose File**:
<span class="title-ref">docker-compose-with-restored-data.yml</span>

**Key Features**: - Configured to use external volumes for restored
data - Compatible with backup/restore scripts - Maintains data integrity
from previous installations

**Usage**:
`` `bash # 1. Restore data using backup_and_restore scripts ./backup_and_restore/restore/restore_db.sh ./backup_and_restore/restore/restore_server.sh ./backup_and_restore/restore/restore_metabase.sh  # 2. Deploy with restored data volumes docker-compose -f docker-compose-with-restored-data.yml up -d ``\`

---

\## Scenario 3: Hybrid Deployment with Existing OMERO Server

\> **⚠️ Warning:** This scenario is not properly tested and requires
advanced OMERO grid configuration. You will need to establish an
OMERO.grid connection between your existing OMERO server and the
NL-BIOMERO components, including ensuring port 4061 (and potentially
others) of the host OMERO server is accessible. The docker-compose files
provided are starting points and will likely require significant
customization for your specific environment. Feel free to contact the
development team (e.g. on \<a href="https://image.sc"
target="\_blank"\>image.sc\</a\>) for any assistance with this
deployment scenario.

\### Scenario 3.1: BIOMERO Only (External OMERO) **Purpose**: Connect to
existing external OMERO server

**Docker Compose File**:
<span class="title-ref">docker-compose-biomero-only.yml</span>

**Key Features**: - Deploys only BIOMERO components - Configured to
connect to external OMERO server - Minimal footprint when OMERO is
already deployed

**Usage**:
`` `bash # Copy the example environment file for external OMERO configuration cp external-omero.env.example .env  # Edit .env to set external OMERO server details nano .env  # Deploy BIOMERO components docker-compose -f docker-compose-biomero-only.yml up -d ``\`

\### Scenario 3.2: BIOMERO.importer Only (External OMERO) **Purpose**:
Deploy only BIOMERO.importer with existing OMERO

**Docker Compose File**:
<span class="title-ref">docker-compose-importer-only.yml</span>

**Key Features**: - Deploys only BIOMERO.importer component - Configured
to connect to external OMERO server - Focused on automated data import
functionality

**Usage**:
`` `bash # Copy the example environment file for external OMERO configuration cp external-omero.env.example .env  # Edit .env to set external OMERO server details nano .env  # Deploy BIOMERO.importer components docker-compose -f docker-compose-importer-only.yml up -d ``\`

---

\## Additional Configurations

\### Component Selection with Profiles Some docker-compose files support
selective component deployment using profiles:

`` `bash # Deploy only with importer enabled docker-compose --profile importer_enabled up -d  # Deploy without importer docker-compose up -d ``\`

You can build that in to any of the compose files to have the option of
deploying only a subset of containers, without having to maintain
multiple docker-compose files. See \[Docker
docs\](<https://docs.docker.com/compose/how-tos/profiles/>).

\### Toggle UI Modules (OMERO.biomero plugin) In the
<span class="title-ref">.env</span> file you can hide specific UI
modules without removing containers:

`` `bash # BIOMERO.importer web UI IMPORTER_ENABLED=TRUE  # set FALSE to hide importer UI  # BIOMERO.analyzer workflows UI ANALYZER_ENABLED=TRUE  # set FALSE to hide BIOMERO UI ``\`

Setting either variable to <span class="title-ref">FALSE</span> removes
only the corresponding frontend elements in OMERO.web; backend
containers can still run if present.

\### Environment Customization All deployments should be customized by
editing the <span class="title-ref">.env</span> file before deployment:

`` `bash # Edit environment variables nano .env  # Then deploy docker-compose up -d ``\`

Note that all values in the original .env file are public open source
knowledge, so don't deploy those values on your public facing instances.
See the documentation on how to change passwords of the different
services, like Metabase.

---

\## Creating a Custom Deployment

1.  Start with the docker-compose file closest to your needs
2.  Customize volumes, ports, and environment variables
3.  Use docker-compose override files for minor changes

Example override file
(<span class="title-ref">docker-compose.override.yml</span>):
`` `yaml services:   omeroweb:     ports:       - "8080:4080"  # Use different port      omeroserver:     environment:       CONFIG_omero_web_public_enabled: "true"  # Enable additional feature ``\`

---

For more detailed information about each scenario, see the deployment
scenarios in <span class="title-ref">deployment.md</span>.

\## Detailed Deployment Guides

For specific, in-depth deployment instructions, see these
platform-specific guides:

\### Production Deployments - **\[Linux/Ubuntu with
SSL\](README.linux.md)** - Complete guide for production Ubuntu
deployment with SSL certificates, nginx reverse proxy, and security
configurations - Covers
<span class="title-ref">docker-compose-for-ubuntu-with-SSL.yml</span> -
SSL certificate setup with Let's Encrypt - Nginx reverse proxy
configuration - Volume permissions and security considerations

\### Development & Demo Deployments - **\[BIOMERO 101 Installation
Guide\](BIOMERO%20101%20-%20installation%20guide.pdf)** - Step-by-step
beginner's guide for development setup - Perfect for first-time users
and demonstrations - Covers Docker Desktop installation on Windows -
WSL2 setup and configuration - Basic development workflow

These guides provide platform-specific details, troubleshooting tips,
and best practices for their respective deployment scenarios.
