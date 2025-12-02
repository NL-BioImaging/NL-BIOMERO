# SLURM Integration

NL-BIOMERO integrates with High-Performance Computing (HPC) clusters
using SLURM for scalable bioimage analysis workflows.

## Overview

The SLURM integration allows you to:

- Execute computationally intensive workflows on HPC clusters
- Scale analysis across multiple compute nodes
- Leverage specialized hardware (GPUs, high-memory nodes)
- Manage workflow queuing and resource allocation

## Architecture

``` text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OMERO Web     │    │  BIOMERO Worker │    │  SLURM Cluster  │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ User submits│ │───▶│ │ Workflow    │ │───▶│ │ Job Queue   │ │
│ │ workflow    │ │    │ │ Manager     │ │    │ │             │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │        │        │    │        │        │
│ ┌─────────────┐ │    │        ▼        │    │        ▼        │
│ │ Results     │ │◀───│ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Display     │ │    │ │ Progress    │ │◀───│ │ Compute     │ │
│ └─────────────┘ │    │ │ Tracking    │ │    │ │ Nodes       │ │
└─────────────────┘    │ └─────────────┘ │    │ └─────────────┘ │
                       └─────────────────┘    └─────────────────┘
```

## Configuration

SLURM integration is configured through `slurm-config.ini` files located
in:

- **Web interface**: `/NL-BIOMERO/web/slurm-config.ini`
- **Worker service**: `/NL-BIOMERO/biomeroworker/slurm-config.ini`

### Basic Configuration

``` ini
[SSH]
# SLURM cluster connection
host=localslurm

[SLURM]
# Storage paths on SLURM cluster
slurm_data_path=/data/my-scratch/data
slurm_images_path=/data/my-scratch/singularity_images/workflows
slurm_converters_path=/data/my-scratch/singularity_images/converters
slurm_script_path=/data/my-scratch/slurm-scripts
```

### Container Environment Configuration

For environments requiring explicit container path binding:

``` ini
[SLURM]
# Required when containers need explicit path binding
# Sets APPTAINER_BINDPATH environment variable
slurm_data_bind_path=/data/my-scratch/data

# Optional: specify partition for conversion jobs
slurm_conversion_partition=cpu-short
```

> [!NOTE]
> Configure `slurm_data_bind_path` only when your HPC administrator
> requires setting the `APPTAINER_BINDPATH` environment variable.

### Workflow Definitions

Available workflows are defined in the `[MODELS]` section:

``` ini
[MODELS]
# Cellpose segmentation workflow
cellpose=cellpose
cellpose_repo=https://github.com/TorecLuik/W_NucleiSegmentation-Cellpose/tree/v1.4.0
cellpose_job=jobs/cellpose.sh
cellpose_job_mem=4GB

# StarDist segmentation workflow  
stardist=stardist
stardist_repo=https://github.com/Neubias-WG5/W_NucleiSegmentation-Stardist/tree/v1.3.2
stardist_job=jobs/stardist.sh
```

### Analytics and Monitoring

Enable workflow tracking and analytics:

``` ini
[ANALYTICS]
# Enable workflow tracking
track_workflows=True

# Enable specific monitoring features
enable_job_accounting=True
enable_job_progress=True
enable_workflow_analytics=True
```

## Deployment Considerations

### SSH Configuration

Configure SSH access to your SLURM cluster:

``` bash
# In ~/.ssh/config
Host localslurm
    HostName your-slurm-cluster.example.com
    User your-username
    IdentityFile ~/.ssh/id_rsa_slurm
    Port 22
```

### Directory Structure

Ensure required directories exist on the SLURM cluster:

``` bash
# Create directory structure
mkdir -p /data/my-scratch/{data,singularity_images/{workflows,converters},slurm-scripts}
```

### Permissions and Access

- Verify the BIOMERO worker can SSH to the SLURM cluster
- Ensure read/write access to configured directories
- Check SLURM account permissions and quotas

## Troubleshooting

### Common Issues

**Container Access Errors**

If workflows fail with file access errors:

1.  Configure explicit path binding:

    ``` ini
    [SLURM]
    slurm_data_bind_path=/data/my-scratch/data
    ```

2.  Verify directory permissions on the SLURM cluster

3.  Check if Singularity/Apptainer can access the data directory

**SSH Connection Failures**

If the worker cannot connect to SLURM:

1.  Test SSH connection manually from the worker container
2.  Verify SSH key authentication
3.  Check network connectivity and firewall rules

**Job Submission Issues**

If jobs fail to submit:

1.  Verify SLURM account and partition access
2.  Check resource request limits (memory, GPU, etc.)
3.  Review SLURM queue policies and restrictions

**Workflow Execution Failures**

If submitted jobs fail during execution:

1.  Check SLURM job logs for errors
2.  Verify container images are accessible
3.  Ensure input data is properly transferred

### Debug Commands

``` bash
# Test SSH connection
docker exec -it biomeroworker ssh localslurm

# Check SLURM status
docker exec -it biomeroworker ssh localslurm "squeue -u $USER"

# View job details
docker exec -it biomeroworker ssh localslurm "scontrol show job JOBID"

# Check directory permissions
docker exec -it biomeroworker ssh localslurm "ls -la /data/my-scratch/"
```

## Performance Tuning

### Resource Allocation

Optimize resource requests for different workflow types:

``` ini
[MODELS]
# CPU-intensive workflow
cellprofiler_job_mem=32GB
cellprofiler_job_time=02:00:00

# GPU workflow
cellpose_job_gres=gpu:1g.10gb:1
cellpose_job_partition=gpu-partition

# Memory-intensive workflow
stardist_job_mem=64GB
stardist_job_partition=himem
```

### Queue Management

- Use appropriate partitions for different workflow types
- Configure job time limits based on expected runtime
- Consider using job arrays for batch processing

### Monitoring and Analytics

Enable comprehensive monitoring:

``` ini
[ANALYTICS]
track_workflows=True
enable_job_accounting=True
enable_job_progress=True
enable_workflow_analytics=True

# Optional: specify analytics database
sqlalchemy_url=postgresql://user:pass@db:5432/analytics
```

## Security Considerations

- Use SSH key authentication instead of passwords
- Restrict SSH access to specific users and commands
- Configure firewall rules to limit network access
- Regularly rotate SSH keys and credentials
- Monitor access logs for suspicious activity

## Further Reading

- `../developer/containers/biomeroworker` - Worker container details
- `omero-biomero-admin` - Administrative procedures
- [SLURM Documentation](https://slurm.schedmd.com/documentation.html)
- [Singularity User
  Guide](https://docs.sylabs.io/guides/latest/user-guide/)
