# BIOMERO Worker Container

The BIOMERO worker container handles distributed image analysis
processing through Slurm integration and serves as the dedicated
OMERO.grid Processor node.

## Overview

Based on the `openmicroscopy/omero-server` image, this container is
configured as a specialized OMERO worker node that exclusively handles
script execution via the **Processor-0** role in OMERO.grid.

**Grid Role Assignment**:

``` yaml
CONFIG_omero_server_nodedescriptors: >-
  master:Blitz-0
  omeroworker-1:Tables-0,Indexer-0,PixelData-0,DropBox,MonitorServer,FileServer,Storm
  biomeroworker-external:Processor-0
```

This ensures all OMERO script execution (**including BIOMERO.scripts**)
is routed to this container, which has the specialized environment
needed for HPC cluster integration.

## Key Features

**HPC Integration**  
- **SSH Access**: Direct SSH connectivity to Slurm clusters
- **Single Account Model**: One SSH key, one Slurm account per
  deployment
- **Secure Mounting**: SSH keys mounted securely via startup scripts,
  not prepackaged

**Workflow Processing**  
- **OMERO Script Execution**: All script processing via Processor-0 role
- **Event Sourcing**: Complete workflow tracking in PostgreSQL database
- **Data Export**: ZARR format export for HPC workflows

**Analysis Pipeline**  
- **Format Conversion**: OMERO → ZARR → TIFF workflow
- **Multi-format Support**: Handles diverse input formats via
  bioformats2raw
- **Workflow Management**: Configurable analysis pipelines

## Container Customizations

SSH Integration \~\~\~\~\~\~\~\~\~\~\~\~\~~

**SSH Client Installation**:

``` dockerfile
RUN yum install -y openssh-clients
COPY biomeroworker/10-mount-ssh.sh /startup/10-mount-ssh.sh
```

**SSH Key Mounting** (`10-mount-ssh.sh`):

- Copies SSH keys from `/tmp/.ssh` to `/opt/omero/server/.ssh`
- Sets proper permissions (700 for directory, 600 for private keys)
- Enables secure HPC cluster access, without baking secrets into the
  container image

**Usage**:

``` yaml
# Mount SSH keys in docker-compose
volumes:
  - "$HOME/.ssh:/tmp/.ssh:ro"
```

Database Integration \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**PostgreSQL Support**:

``` dockerfile
RUN yum install -y python3-devel postgresql-devel gcc
```

**Purpose**:

- **Event Sourcing**: Complete workflow execution tracking
- **Analytics**: Detailed workflow performance data
- **Audit Trail**: Full history of analysis jobs and statuses
- **SLURM Job Accounting**: Tracks resource usage per job and per OMERO
  user

**BIOMERO 2.0 Feature**: Near real-time event logging provides a single
source of truth for all workflow events.

Data Export Pipeline \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**bioformats2raw Installation**:

``` dockerfile
RUN wget https://github.com/glencoesoftware/bioformats2raw/releases/download/v0.7.0/bioformats2raw-0.7.0.zip
```

**ZARR Export Support**:

``` dockerfile
RUN yum install -y blosc-devel
# ... 
RUN $VIRTUAL_ENV/bin/python -m pip install omero-cli-zarr==0.5.5
```

**Export Workflow**:

1.  **OMERO Data** → Export via `omero-cli-zarr`
2.  **ZARR Format** → Universal intermediate format
3.  **TIFF Conversion** → On HPC cluster for analysis tools
4.  **Results Import** → Back to OMERO as new images/annotations

BIOMERO Library Integration
\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Core BIOMERO Installation**:

``` dockerfile
RUN $VIRTUAL_ENV/bin/python -m pip install biomero==${BIOMERO_VERSION}
```

**Supporting Libraries**:

For BIOMERO.scripts. These can have extra dependencies above just
BIOMERO.analyzer python library.

``` dockerfile
RUN $VIRTUAL_ENV/bin/python -m pip install \
    ezomero==1.1.1 \
    tifffile==2020.9.3 \
    omero-metadata==0.12.0
```

**Zero-C ICE Pre-built Wheels**:

``` dockerfile
RUN wget https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp39-cp39-manylinux_2_28_x86_64.whl
```

Custom Processor Implementation
\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Modified processor.py**:

``` dockerfile
COPY biomeroworker/processor.py /opt/omero/server/venv3/lib/python3.9/site-packages/omero/
```

> [!WARNING]
> **Maintenance Alert**: This file overrides the base OMERO processor.py
> and may conflict with future OMERO updates.
>
> **Key Changes**: \* Environment variable forwarding to subprocesses
> (HTTP_PROXY, etc.) \* Enhanced subprocess handling for BIOMERO
> workflows
>
> **Maintenance Required**: Periodically merge important changes from
> upstream OMERO processor.py to maintain compatibility.

**Original Source**: [ome/omero-py
processor.py](https://raw.githubusercontent.com/ome/omero-py/master/src/omero/processor.py)

Configuration Management -----------------------

Slurm Configuration \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Base Configuration** (`slurm-config.ini`):

``` dockerfile
COPY biomeroworker/slurm-config.ini /etc/slurm-config.ini
```

This file contains:

**SSH Settings**:

``` ini
[SSH]
host=localslurm  # SSH alias for cluster connection
```

**Slurm Paths**:

``` ini
[SLURM]
slurm_data_path=/data/my-scratch/data
slurm_images_path=/data/my-scratch/singularity_images/workflows
slurm_script_path=/data/my-scratch/slurm-scripts
```

**Workflow Models**:

- Cellpose segmentation
- StarDist segmentation
- CellProfiler measurements
- Custom analysis workflows

**Configuration Override**:

The web interface can mount a different configuration that overrides
this base file:

``` yaml
# In docker-compose
volumes:
  - "./slurm-config-override.ini:/etc/slurm-config.ini:ro"
```

> [!NOTE]
> **Configuration Hierarchy**:
>
> 1.  **Base file** (in container): Default workflows and settings
> 2.  **Override file** (mounted): Admin customizations via web
>     interface
> 3.  **Limitation**: Override can modify/add but cannot delete base
>     configurations

Analytics Configuration \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**BIOMERO 2.0 Analytics** (from `slurm-config.ini`):

``` ini
[ANALYTICS]
track_workflows=True
enable_job_accounting=True
enable_job_progress=True
enable_workflow_analytics=True
```

**Database Connection**:

``` ini
# Uses environment variable SQLALCHEMY_URL or container's PostgreSQL connection
sqlalchemy_url=postgresql+psycopg2://user:password@localhost:5432/biomero
```

Worker Startup Process ---------------------

Configuration Generation \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

The startup script dynamically generates OMERO configuration:

**Internal Worker** (`99-run.sh`):

``` bash
# For workers in same Docker network
MASTER_ADDR=$(getent hosts $CONFIG_omero_master_host | cut -d\  -f1)
WORKER_ADDR=$(getent hosts $OMERO_WORKER_NAME | cut -d\  -f1)
```

**Worker Configuration**:

``` bash
cat > OMERO.server/etc/$OMERO_WORKER_NAME.cfg << EOF
IceGrid.Node.Endpoints=tcp -h $WORKER_ADDR -p $WORKER_PORT
IceGrid.Node.Name=$OMERO_WORKER_NAME
IceGrid.Node.Data=var/$OMERO_WORKER_NAME
Ice.StdOut=var/log/$OMERO_WORKER_NAME.out
EOF
```

**ICE Configuration**:

``` bash
sed -e "s/@omero.master.host@/$MASTER_ADDR/" \
    OMERO.server/etc/templates/ice.config > \
    OMERO.server/etc/ice.config
```

## Development Guidelines

BIOMERO Script Development
\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Script Location**: BIOMERO.scripts are installed on the **OMERO server
container**, not the worker:

- Scripts live in: `/opt/omero/server/OMERO.server/lib/scripts/biomero/`
- Worker executes scripts via OMERO.grid Processor-0 role
- Script changes require OMERO server container rebuild on release, but
  during development you can just upload them through web for on-the-fly
  testing!

**Workflow Development**:

1.  **Create workflow**: In separate repository (e.g.,
    [W_NucleiSegmentation-Cellpose](https://github.com/TorecLuik/W_NucleiSegmentation-Cellpose))
2.  **Add to config**: Update `slurm-config.ini` with new workflow
3.  **Test locally**: Use development environment
4.  **Deploy**: Release NL-BIOMERO with new workflow support via the
    config. Or just set it via admin in a live environment.

SSH Key Management \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Development Setup**:

``` bash
# Generate SSH key for HPC access
ssh-keygen -t rsa -f ~/.ssh/hpc_key
# Add public key to HPC cluster
# Mount in development docker-compose
```

**Production Deployment**:

- **Single SSH Key**: One key per deployment
- **Single Slurm Account**: One account per deployment
- **Security**: Keys should be rotated regularly
- **Access Control**: Limit SSH key to specific HPC resources

Configuration Testing \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Test Slurm Configuration**:

``` bash
# Access worker container
docker-compose exec biomeroworker bash

# Test SSH connection
ssh localslurm # SSH alias for HPC cluster in config.ini

# Test BIOMERO configuration
python -c "from biomero.slurm_client import SlurmClient; client = SlurmClient.from_config(); print(client.validate())"
```

**Test Analytics Database**:

Check database connection and initialize analytics (Option 1: direct
configuration)

``` python
from biomero import SlurmClient

slurmClient = SlurmClient(track_workflows=True,
                          enable_job_accounting=False,
                          enable_job_progress=True,
                          enable_workflow_analytics=False)
slurmClient.initialize_analytics_system(True)
print('Analytics system initialized')
```

Option 2: From config file

``` python
from biomero import SlurmClient

slurmClient = SlurmClient.from_config()
slurmClient.workflowTracker.notification_log.section_size = 100
```

Inspect workflow notifications

``` python
from pprint import pprint

notifications = slurmClient.workflowTracker.notification_log.select(54, 10)
if notifications:
    print(f'Found {len(notifications)} workflow notifications')
    [pprint(i.__dict__) for i in notifications]
else:
    print('No workflow notifications found')
```

### Eventsourcing

``` python
from biomero import WorkflowTracker

# Process events from the start (use any leader name if desired)
slurmClient.workflowTracker.pull_and_process(
    leader_name=WorkflowTracker.__name__,
    start=1
)
```

NotificationLog

``` python
# Read the first page of notifications
slurmClient.workflowTracker.notification_log.select(start=1, limit=10)
```

Aggregate view

``` python
# Load an aggregate by its UUID
slurmClient.workflowTracker.repository.get('747fc951-15ca-4b56-a19e-418e1db97d14')
```

Troubleshooting --------------

Common Issues \~\~\~\~\~\~\~\~\~\~\~~

**SSH Connection Failures**:

- Check SSH key permissions (600 for private keys)
- Verify SSH key is added to HPC cluster
- Test SSH connection manually from container

**Processor Role Issues**:

- Verify grid role assignment in docker-compose
- Check OMERO.grid node status: `omero admin diagnostics`
- Ensure only one Processor-0 node is active

**BIOMERO Script Failures**:

- Check script installation on OMERO server container
- Verify BIOMERO library version compatibility
- Review workflow configuration in `slurm-config.ini`

**Database Connection Issues**:

- Verify PostgreSQL connection settings
- Check SQLALCHEMY_URL environment variable
- Ensure database schema is initialized

Performance Optimization \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Resource Allocation**:

- **CPU**: Processor-intensive role benefits from multiple cores
- **Memory**: OME-ZARR export requires sufficient memory for large
  datasets
- **Storage**: Temporary data storage for ZARR exports and Slurm imports

**Network Optimization**:

- **External Workers**: Consider network latency to master
- **HPC Access**: Optimize SSH connection pooling
- **Data Transfer**: Monitor ZARR export/import performance

Upgrade Considerations ---------------------

BIOMERO Library Updates \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

**Version Management**:

``` dockerfile
ARG BIOMERO_VERSION
RUN pip install biomero==${BIOMERO_VERSION}
```

**Upgrade Process**:

1.  **Test new BIOMERO version** in development
2.  **Update Dockerfile** with new version
3.  **Rebuild container** with updated dependencies
4.  **Validate workflows** in staging environment

Processor.py Maintenance \~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~\~~

> [!WARNING]
> **Critical Maintenance Task**: The custom `processor.py` requires
> periodic review and merging with upstream changes.

**Maintenance Process**:

1.  **Monitor** [OMERO processor.py
    updates](https://github.com/ome/omero-py/commits/master/src/omero/processor.py)
2.  **Review changes** for compatibility and security fixes
3.  **Merge important updates** while preserving custom environment
    variable handling
4.  **Test thoroughly** before deploying to production

**Current Custom Features**:

- HTTP_PROXY and HTTPS_PROXY forwarding to subprocesses
- Enhanced environment variable support for BIOMERO workflows

## Related Documentation

- `omeroserver` - Server container and script installation
- `../architecture` - Overall system architecture
- `releases` - Container release process
- [BIOMERO Documentation](https://github.com/NL-BioImaging/biomero)
- [OMERO.grid
  Documentation](https://omero.readthedocs.io/en/stable/sysadmins/grid.html)
- [Slurm Documentation](https://slurm.schedmd.com/documentation.html)

## External Resources

- [BIOMERO Scripts
  Repository](https://github.com/NL-BioImaging/biomero-scripts)
- [Example Workflow:
  Cellpose](https://github.com/TorecLuik/W_NucleiSegmentation-Cellpose)
- [bioformats2raw
  Documentation](https://github.com/glencoesoftware/bioformats2raw)
- [OMERO CLI ZARR Plugin](https://github.com/ome/omero-cli-zarr)
