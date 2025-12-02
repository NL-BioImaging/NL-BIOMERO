# Architecture Overview

NL-BIOMERO consists of several interconnected components:

## Container Architecture

The platform uses Docker Compose to orchestrate multiple services:

- **omeroserver** - Core OMERO server with BIOMERO.scripts
- **omeroweb** - Web interface with custom plugins
- **biomeroworker** - BIOMERO.analyzer processor
- **metabase** - Analytics and visualization dashboard (BIOMERO.db)
- **database** - PostgreSQL for OMERO data
- **database-biomero** - PostgreSQL for BIOMERO workflows (BIOMERO.db)
- **biomero-importer** - BIOMERO.importer service

## Network Architecture

Services communicate through Docker networks:

- Internal network for database connections
- Exposed ports for web access (4080, 3000)
- OMERO ports for client connections (4063, 4064)

## Storage Architecture

Persistent data is managed through mounted or Docker volumes:

- OMERO data volume for image metadata storage
- Database volumes for persistent data
- Configuration mounts for customization

## Integration Points

- **Slurm Integration** - BIOMERO connects to HPC clusters
- **SSH Configuration** - Secure connections to compute resources
- **Shared Storage** - Common data access across services
