# Welcome to NL-BIOMERO's documentation!

**NL-BIOMERO** is a containerized deployment of OMERO with BIOMERO for
bioimage analysis workflows, featuring automated data import, workflow
management, and enhanced web interfaces.

This platform provides a complete solution for bioimage data management
and analysis, combining:

- **OMERO** - Image data management platform
- **BIOMERO.analyzer** - High-performance computing integration
- **BIOMERO.importer** - Automated data import workflows
- **BIOMERO.scripts** - HPC workflow execution scripts
- **OMERO.biomero** - Modern web interfaces for data import and analysis
- **OMERO.forms** - Flexible form-based interfaces for metadata
  annotation
- **Metabase** - Analytics and visualization dashboards
- **Docker Compose** - Easy deployment and scaling scenarios

> [!NOTE]
> Deployment, migration, and backup procedures shown in this
> documentation are examples for inspiration. They are not prescriptive
> recommendations and may not address all environments. Always adapt and
> validate them for your organization’s security, compliance, and
> operational requirements.

# Getting Started

Choose your deployment scenario:

- **New Installation**: Start with `sysadmin/deployment` for fresh
  deployments
- **Existing OMERO**: See `sysadmin/hybrid-deployment` for integration
  options
- **Development**: Use `developer/contributing` for local development
  setup

<div class="toctree" caption="System Administration" maxdepth="3">

sysadmin/index

</div>

<div class="toctree" caption="Developer Guide" maxdepth="3">

developer/index

</div>

<div class="toctree" caption="User Guide" maxdepth="3">

user/index

</div>

# Quick Links

- `sysadmin/deployment` - Deployment scenarios and setup
- `sysadmin/backup-restore` - Backup and restore procedures
- `user/getting-started` - First steps with NL-BIOMERO
- `developer/architecture` - Technical architecture overview

> [!NOTE]
> This documentation covers containerized deployment scenarios. For
> non-containerized installations, refer to the individual component
> documentation.

# Indices and tables

- `genindex`
- `modindex`
- `search`
