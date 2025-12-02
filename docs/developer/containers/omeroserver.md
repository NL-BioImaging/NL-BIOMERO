# OMERO Server Container

The OMERO server container serves as the master node for the entire
platform, handling core OMERO functionality with minimal but important
customizations.

## Overview

Based on the official `openmicroscopy/omero-server` image, this
container acts as the central coordination point for:

- Core OMERO server functionality
- Script execution coordination
- Database management
- Ice grid management for distributed processing

## Key Customizations

### Script Installation

The container automatically installs three sets of scripts during build:

**1. BIOMERO.scripts**  
- Source:
  [NL-BioImaging/biomero-scripts](https://github.com/NL-BioImaging/biomero-scripts)
- Location: `/opt/omero/server/OMERO.server/lib/scripts/biomero/`
- Purpose: Slurm-based image analysis workflows

**2. OMERO.figure Script**  
- Source:
  [ome/omero-figure](https://raw.githubusercontent.com/ome/omero-figure/refs/heads/master/omero_figure/scripts/omero/figure_scripts/Figure_To_Pdf.py)
- Location:
  `/opt/omero/server/OMERO.server/lib/scripts/omero/figure_scripts/`
- Purpose: PDF export functionality for figures

**3. Labels2ROIs Script**  
- Source:
  [Cellular-Imaging-Amsterdam-UMC/label2rois](https://raw.githubusercontent.com/Cellular-Imaging-Amsterdam-UMC/label2rois/main/Labels2Rois.py)
- Location:
  `/opt/omero/server/OMERO.server/lib/scripts/omero/util_scripts/`
- Purpose: Convert BIOMERO label images to OMERO ROIs

### Automated Configuration Restoration

**Configuration Backup/Restore System**  
- Script: `00-restore-config.sh`
- Purpose: Enables stateless container redeployments by automatically
  restoring OMERO configuration from backup
- Location: `/OMERO/backup/omero.config`
- Benefit: No manual configuration needed after container (re)creation

**LDAP Integration Ready**  
- Config: `01-ldap-config.omero`
- Purpose: Pre-configured LDAP settings for enterprise authentication
- Customizable via environment variables. Placeholder for now.

## Dockerfile Key Changes

``` dockerfile
# Install required scripts for analysis workflows
RUN cd /opt/omero/server/OMERO.server/lib/scripts/ && \
    git clone --depth 1 --branch ${BIOMERO_VERSION} \
    https://github.com/NL-BioImaging/biomero-scripts.git biomero

# Configuration restoration on startup
ADD server/00-restore-config.sh* /startup/
ADD server/01-ldap-config.omero /opt/omero/server/config/
```

## Development Guidelines

### Configuration Changes

**Programmatic Configuration**: Always make configuration changes
through scripts or environment variables to maintain stateless
deployments:

``` bash
# Example: Add new configuration via startup script
echo "config set -- omero.my.setting 'value'" >> /opt/omero/server/config/02-my-config.omero
```

**Environment Variables**: Use docker-compose environment variables for
dynamic configuration:

``` yaml
environment:
  CONFIG_omero_db_host: "${POSTGRES_HOST}"
  CONFIG_omero_db_name: "${POSTGRES_DB}"
```

Adding New Scripts \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

To add additional OMERO scripts:

1.  **Via Git Repository** (recommended for script collections):

``` dockerfile
RUN cd /opt/omero/server/OMERO.server/lib/scripts/ && \
    git clone https://github.com/your-org/your-scripts.git
```

2.  **Via Direct Download** (for individual scripts):

``` dockerfile
RUN curl -o /opt/omero/server/OMERO.server/lib/scripts/path/script.py \
    https://raw.githubusercontent.com/your-org/repo/main/script.py
```

### Testing Changes

1.  **Build and test locally**:

``` bash
docker-compose -f docker-compose-dev.yml build omeroserver
docker-compose -f docker-compose-dev.yml up -d omeroserver
```

2.  **Verify script installation**:

``` bash
docker-compose exec omeroserver omero script list
```

3.  **Check configuration**:

``` bash
docker-compose exec omeroserver omero config get
```

## Related Documentation

- `../architecture` - Overall system architecture
- `omeroweb` - Web interface development
- `biomeroworker` - Worker node development
- [OMERO Developer
  Documentation](https://omero.readthedocs.io/en/stable/developers/)
