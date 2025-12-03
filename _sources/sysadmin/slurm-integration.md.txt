# BIOMERO.analyzer SLURM Integration for NL-BIOMERO

This guide covers deploying **BIOMERO.analyzer** with SLURM cluster integration within your NL-BIOMERO infrastructure. For detailed workflow configuration and usage, see the [BIOMERO.analyzer SLURM documentation](https://nl-bioimaging.github.io/biomero/readme_link.html#using-the-gpu-on-slurm).

```{note}
**TL;DR for System Administrators:**
- BIOMERO.analyzer can offload compute-intensive workflows to SLURM clusters via SSH
- Requires one-way SSH access from `biomeroworker` container to your SLURM cluster
- Uses existing SSH keys mounted into the container (see deployment examples)
- Main config files: `web/slurm-config.ini` and `biomeroworker/slurm-config.ini`
- SLURM environment is auto-configured via OMERO admin script `SLURM_Init_environment.py`
- Links to [full BIOMERO.analyzer documentation](https://nl-bioimaging.github.io/biomero/) for workflow details
```

## Overview

BIOMERO.analyzer integrates with High-Performance Computing (HPC) clusters using SLURM to execute computationally intensive bioimage analysis workflows. This integration allows you to:

- **Offload heavy computation** from your NL-BIOMERO containers to dedicated HPC resources
- **Scale analysis** across multiple compute nodes with GPUs and high-memory systems
- **Queue and manage** long-running workflows without blocking the web interface
- **Leverage institutional HPC** infrastructure for bioimage analysis workflows

All communication is **one-way** from NL-BIOMERO to SLURM cluster via SSH/SCP.

## Architecture

```{mermaid}
---
config:
  themeVariables:
    fontSize: 20px
    curve: linear
---
flowchart LR
    subgraph " "
        direction TB
        subgraph omero_web["OMERO Web"]
            direction TB
            submit_workflow("User submits workflow")
            results_display("Results Display")
        end

        subgraph biomero_worker["BIOMERO Worker"]
            direction TB
            workflow_manager("Workflow Manager")
            progress_tracking("Progress Tracking")
        end

        subgraph slurm_cluster["SLURM Cluster"]
            direction TB
            job_queue("Job Queue")
            compute_nodes("Compute Nodes")
        end
    end

    submit_workflow --> workflow_manager
    progress_tracking --> results_display
    
    workflow_manager --> progress_tracking
    workflow_manager --> job_queue

    job_queue --> compute_nodes
    compute_nodes --> progress_tracking
```

## SSH Key Management for Container Deployment

### Development/Docker Compose Setup

For development environments, SSH keys are mounted from your host system:

```yaml
# In docker-compose.yml
services:
  biomeroworker:
    volumes:
      # Mount your existing SSH setup
      - $HOME/.ssh:/tmp/.ssh:ro
      # Startup script handles SSH key positioning
    build:
      context: ./biomeroworker
```

The container's `10-mount-ssh.sh` entrypoint script automatically copies and sets proper permissions:

```bash
# Automatically handled by container startup
cp -R /tmp/.ssh /opt/omero/server/.ssh
chmod 700 /opt/omero/server/.ssh
chmod 600 /opt/omero/server/.ssh/*
```

```{note}
**Linux SSH Keys:** Mounted SSH files need open permissions for container startup. The startup script automatically secures them internally. See below for a more secure approach.
```

### Production/Podman Deployment with Secrets

For production deployments, use container secrets for better security:

```bash
# Create podman secrets (from deployment examples)
podman secret create ssh-config ~/.ssh/config
podman secret create ssh-key ~/.ssh/id_rsa
podman secret create ssh-pubkey ~/.ssh/id_rsa.pub
podman secret create ssh-known_hosts ~/.ssh/known_hosts

# Mount secrets in container
podman run -d --name biomeroworker \
  --secret ssh-config,target=/tmp/.ssh/config \
  --secret ssh-key,target=/tmp/.ssh/id_rsa \
  --secret ssh-pubkey,target=/tmp/.ssh/id_rsa.pub \
  --secret ssh-known_hosts,target=/tmp/.ssh/known_hosts \
  cellularimagingcf/biomero:my-version
```

```{note}
**Security Note:** All SSH access uses a single service account on SLURM cluster shared by all OMERO users. Individual user authentication happens through OMERO, not SLURM accounts.
```

## Configuration Files

SLURM configuration uses shared `slurm-config.ini` files managed through the **OMERO.biomero Admin interface**.

### Container File Sharing Setup

**Critical Requirement:** Mount the same `slurm-config.ini` file into both containers:

```yaml
# Mount same config file to both containers
volumes:
  # Web container - Admin interface reads/writes configuration
  - "./web/slurm-config.ini:/opt/omero/web/OMERO.web/var/slurm-config.ini:rw"
  # Worker container - Reads configuration for job execution  
  - "./web/slurm-config.ini:/opt/omero/server/slurm-config.ini:rw"
```

This allows the web interface to write configuration changes that the worker container can immediately read.

### Configuration Content Structure

**Sample `slurm-config.ini` with key sections:**

```ini
[SSH]
# SSH alias (must match your ~/.ssh/config)
host=localslurm

[SLURM]
# Cluster paths - managed via Admin interface
slurm_data_path=/data/my-scratch/data
slurm_images_path=/data/my-scratch/singularity_images/workflows
slurm_converters_path=/data/my-scratch/singularity_images/converters
slurm_script_path=/data/my-scratch/slurm-scripts

# HPC-specific settings (consult your HPC admin)
slurm_data_bind_path=/data/my-scratch/data  # Only if required by HPC admin
slurm_conversion_partition=cpu-short       # For preprocessing jobs

# Workflow and model settings - managed via Admin interface
# [MODELS] and [CONVERTERS] sections auto-generated by web interface
```

```{note}
**Managed via Web Interface:** Use the **OMERO.biomero plugin → Analyze → Admin** screen to configure all SLURM-related settings. Manual INI editing is possible but the web interface is recommended.

For a complete walkthrough of the Admin interface, see {ref}`OMERO.biomero Plugin Administration <omero-biomero-plugin-administration>`.
```

```{note}
**Important:** The `host` parameter is an SSH alias, not a hostname. Configure the actual connection details in your SSH config file.
```

### SSH Configuration

Configure your SSH connection in `~/.ssh/config`:

```bash
# For development with local Slurm cluster
Host localslurm
    HostName host.docker.internal
    User slurm
    Port 2222
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no

# For production HPC cluster
Host production-slurm
    HostName your-slurm-cluster.example.com
    User biomero-service
    Port 22
    IdentityFile ~/.ssh/id_rsa
```

## SLURM Environment Setup

### Web-Based Configuration (Recommended)

**Use the OMERO.biomero Admin Interface** for all SLURM configuration. For a detailed UI guide, see {ref}`OMERO.biomero Plugin Administration <omero-biomero-plugin-administration>`.

**Quick Setup Steps:**
1. **Access OMERO.web** as administrator
2. **OMERO.biomero** → **Admin** tab → **Analyzer** section
3. **Configure settings** (SSH, SLURM paths, workflows, job parameters)
4. **Save Settings** - automatically updates shared `slurm-config.ini`
5. **Run SLURM Init** script - deploys configuration to cluster

```{note}
**No Server Access Required:** All configuration is done through the web interface, which manages the shared `slurm-config.ini` file between containers.

For detailed interface usage, workflow management, and troubleshooting, see {ref}`OMERO.biomero Plugin Administration <omero-biomero-plugin-administration>`.
```

### Manual SLURM Cluster Setup

After configuring via Admin interface, initialize the SLURM environment:

**Run Scripts** → **Admin** → **SLURM Init environment**

This script:
- Creates directory structure on SLURM cluster
- Downloads workflow containers (Singularity images)
- Sets up job scripts and templates
- Configures analytics and monitoring

```{important}
**Always Run After Changes:** SLURM_Init must be executed whenever you add workflows, modify containers, or change cluster paths via the Admin interface.
```

## Security Considerations

### File Permissions

**Configuration Files**: Ensure the container user has proper read/write access to mounted configuration files:

```bash
# Set proper ownership for mounted config files
chown 1000:1000 ./web/slurm-config.ini ./web/biomero-config.json
chmod 644 ./web/slurm-config.ini ./web/biomero-config.json
```

### SSH Access Security

**SSH Key Management**: Use dedicated service account keys with restricted permissions on SLURM cluster.

**Network Access**: Configure firewall rules to allow only necessary SSH traffic from NL-BIOMERO to SLURM cluster.

### Database Access

**Worker Configuration**: Confirm BIOMERO worker container can access shared configuration files and has proper database connectivity.

For Metabase-specific security setup, see {doc}`../developer/containers/metabase`.

### Manual Verification

Test the SSH connection from your deployment:

```bash
# Test connection from biomeroworker container
docker exec biomeroworker ssh localslurm "sinfo"

# OR for production deployment
podman exec biomeroworker ssh production-slurm "squeue"
```

## Network Security

### Required Network Access

- **SSH Port (22)**: One-way from NL-BIOMERO to SLURM cluster
- **No inbound connections**: SLURM cluster doesn't initiate connections to NL-BIOMERO
- **SCP/SFTP**: For data transfer (uses same SSH connection)

### Firewall Configuration

```bash
# Allow SSH from NL-BIOMERO deployment to SLURM cluster
# Example iptables rule on SLURM cluster:
iptables -A INPUT -p tcp --dport 22 -s YOUR_NL_BIOMERO_IP -j ACCEPT
```

## Service Account Architecture

### Single Service Account

- **One SLURM account** for all NL-BIOMERO workflows
- **User authentication** handled by OMERO, not SLURM
- **Resource sharing** across all OMERO users
- **Centralized billing** on single SLURM account

### Account Requirements

Your SLURM service account needs:
- SSH access to submit jobs (`sbatch`, `squeue`, `scancel`)
- Read/write access to configured storage paths
- Appropriate SLURM resource allocations (CPU, GPU, memory)

## Deployment-Specific Examples

### Local Development (docker-compose)

```bash
# Clone and setup as per main README
git clone --recursive https://github.com/NL-BioImaging/NL-BIOMERO.git
cd NL-BIOMERO

# Setup local Slurm cluster for testing
git clone https://github.com/NL-BioImaging/NL-BIOMERO-Local-Slurm
cd NL-BIOMERO-Local-Slurm
cp ~/.ssh/id_rsa.pub .
docker-compose -f docker-compose-from-dockerhub.yml up -d --build

# Back to NL-BIOMERO
cd ../NL-BIOMERO
cp ssh.config.example ~/.ssh/config
docker-compose up -d
```

### Production (Podman with Secrets)

We suggest to use Podman on RHEL SELinux for complete production setup with secret management and daemon service restarting. 
Alternatively, take our Docker Compose setups as a starting point and use these as inspiration for your production environment. 

## Troubleshooting

### SSH Connection Issues

```bash
# Test SSH from container
docker exec -it biomeroworker ssh -v localslurm "echo 'SSH working'"

# Check SSH key permissions in container
docker exec biomeroworker ls -la ~/.ssh/
```

### SLURM Job Issues

```bash
# Check SLURM cluster status
docker exec biomeroworker ssh localslurm "sinfo"

# View recent jobs
docker exec biomeroworker ssh localslurm "squeue -u $USER"

# Check job details
docker exec biomeroworker ssh localslurm "scontrol show job JOBID"
```

### Configuration Validation

```bash
# Verify slurm-config.ini is properly mounted
docker exec biomeroworker cat /opt/omero/server/slurm-config.ini

# Test SLURM environment initialization
# Run SLURM Init script from OMERO.web admin interface
```

## Further Reading

- {ref}`OMERO.biomero Plugin Administration <omero-biomero-plugin-administration>` – Complete OMERO.biomero Admin interface guide (SLURM configuration, workflows, troubleshooting)
- [BIOMERO.analyzer SLURM Documentation](https://nl-bioimaging.github.io/biomero/readme_link.html#using-the-gpu-on-slurm) – Workflow usage and GPU support  
- [NL-BIOMERO Main README](https://github.com/NL-BioImaging/NL-BIOMERO/blob/master/README.md) – Complete deployment guide
- {doc}`linux-deployment` – Linux-specific deployment instructions
- [Local SLURM Setup](https://github.com/NL-BioImaging/NL-BIOMERO-Local-Slurm) – Development cluster setup
- {doc}`../developer/containers/biomeroworker` – BIOMERO worker container details
