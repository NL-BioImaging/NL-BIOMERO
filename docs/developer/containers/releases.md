# Container Releases

> **Warning:**
> **Container-Only Releases**
>
> This documentation covers **container releases only**. Many NL-BIOMERO containers depend on underlying libraries that have their own separate release cycles and repositories.
>
> **Before releasing containers, ensure all dependent libraries are released first:**
>
> - **BIOMERO Library** - Release new version, then update `BIOMERO_VERSION` in `.env`
> - **OMERO Plugins** (OMERO.biomero, OMERO.forms, etc.) - Release plugin, then update Dockerfile references
> - **OMERO ADI** - Independent releases with own container builds
> - **Other Dependencies** - Update base image versions, library versions, etc.
>
> **Example workflow:**
>
> 1. Release BIOMERO library v2.1.0
> 2. Update NL-BIOMERO `.env` with `BIOMERO_VERSION=v2.1.0`
> 3. Update relevant Dockerfiles (server, web) with new library versions or requirements
> 4. Release NL-BIOMERO containers to build and distribute the updated images

This section covers the release process for NL-BIOMERO containers, including versioning, building, and distribution.

## Release Overview

NL-BIOMERO uses an automated GitHub Actions workflow to build and publish Docker containers to Docker Hub upon each release. The containers are published to the [cellularimagingcf](https://hub.docker.com/u/cellularimagingcf) organization.

## Release Workflow

### Container Build Automation

- **Main Repository (NL-BIOMERO)**
  - **Trigger**: GitHub release creation via the GitHub web interface
  - **Action**: Automated Docker build and push to Docker Hub
  - **Containers Built**: Most NL-BIOMERO containers (omeroserver, omeroweb, biomeroworker, etc.)
  - **Registry**: [Docker Hub - cellularimagingcf](https://hub.docker.com/u/cellularimagingcf)

- **OMERO ADI Submodule**
  - **Repository**: Separate repository (included as submodule)
  - **Versioning**: Independent release cycle
  - **Action**: Has its own GitHub Actions workflow
  - **Coordination**: Update submodule reference in NL-BIOMERO when needed

### Typical Release Process

1. **Update Dependencies**

   Update underlying library versions in relevant files:

   ```bash
   # Example: Update BIOMERO version
   # Edit .env file:
   BIOMERO_VERSION=v2.1.0

   # Example: Update other dependencies in Dockerfiles
   # server/Dockerfile, web/Dockerfile, etc.
   ```

2. **Test Changes**

   Build and test locally before releasing:

   ```bash
   # Build specific container
   docker-compose -f docker-compose-dev.yml build omeroserver

   # Test the full stack
   docker-compose -f docker-compose-dev.yml up -d
   ```

3. **Create GitHub Release**

   - Go to [GitHub Releases page](https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO/releases)
   - Click "Create a new release"
   - Follow versioning guidelines (see below)
   - Write release notes describing changes
   - Mark as pre-release if applicable

4. **Monitor Build Process**

   - GitHub Actions will automatically trigger
   - Monitor the build process in the Actions tab
   - Verify containers are published to Docker Hub

5. **Update Documentation**

   - Update relevant documentation
   - Announce significant releases (see Communication section)

## Versioning Guidelines

### Semantic Versioning

NL-BIOMERO follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

- **MAJOR** (e.g., 1.0.0 → 2.0.0)
  - Breaking changes that are not backward compatible
  - Significant architectural changes
  - API changes that require user intervention

- **MINOR** (e.g., 1.0.0 → 1.1.0)
  - New optional features
  - New functionality that doesn't break existing workflows
  - New container services or plugins

- **PATCH** (e.g., 1.0.0 → 1.0.1)
  - Bug fixes
  - Security updates
  - Required feature updates that maintain compatibility

### Pre-release Versions

For development and testing versions:

- **Alpha Releases**
  - Format: `1.0.0-alpha.1`, `1.0.0-alpha.2`
  - Early development, may have significant issues
  - Internal testing only
  - **Mark as "Pre-release" in GitHub** to prevent becoming "latest"

- **Beta Releases**
  - Format: `1.0.0-beta.1`, `1.0.0-beta.2`
  - Feature-complete but may have bugs
  - Ready for broader testing
  - **Mark as "Pre-release" in GitHub** to prevent becoming "latest"

- **Release Candidates**
  - No, beta is a release candidate

### Release Examples

```text
# Stable releases
v1.0.0    - Initial stable release
v1.1.0    - Added new BIOMERO workflows
v1.1.1    - Fixed import bug
v2.0.0    - Major UI overhaul (breaking changes)

# Pre-releases
v2.0.0-alpha.1  - Early development of v2.0
v2.0.0-beta.1   - Feature-complete v2.0 for testing
```

## Dependency Management

### Library Updates

- **BIOMERO Library**
  1. **BIOMERO releases** new version (separate repository)
  2. **Update** `BIOMERO_VERSION` in `.env` file
  3. **Test** integration with new BIOMERO version
  4. **Release** new NL-BIOMERO version to build updated containers

- **OMERO Plugins**
  1. **Plugin releases** new version (e.g., OMERO.biomero, OMERO.forms)
  2. **Update** version in relevant Dockerfile
  3. **Test** plugin integration
  4. **Release** new NL-BIOMERO version

- **Base Images**
  1. **Monitor** for security updates to base images (OMERO, PostgreSQL, etc.)
  2. **Update** base image versions in Dockerfiles
  3. **Test** compatibility
  4. **Release** updated containers

### Example Dependency Update

```bash
# 1. BIOMERO releases v2.1.0
# 2. Update NL-BIOMERO .env file:
BIOMERO_VERSION=v2.1.0

# 3. Test locally
docker-compose -f docker-compose-dev.yml build
docker-compose -f docker-compose-dev.yml up -d

# 4. Create release v1.2.0 on GitHub
# 5. GitHub Actions builds and publishes containers
```

## OMERO ADI Submodule

### Special Handling

The OMERO ADI component is managed as a Git submodule with independent versioning:

- **Separate Repository**
  - Repository: [OMERO-Automated-Data-Import](https://github.com/Cellular-Imaging-Amsterdam-UMC/OMERO-Automated-Data-Import)
  - Independent versioning and release cycle
  - Own GitHub Actions for container building

- **Submodule Updates**
  1. **OMERO ADI releases** new version independently
  2. **Update submodule** reference in NL-BIOMERO:

   ```bash
   cd biomero-importer
   git fetch origin
   git checkout v1.x.x  # Latest ADI release
   cd ..
   git add biomero-importer
   git commit -m "Update OMERO ADI to v1.x.x"
   ```

  3. **Release** new NL-BIOMERO version if ADI changes affect the platform

- **Coordination**
  - Most releases don't require ADI updates
  - Update ADI submodule only when necessary
  - Test integration when updating submodule reference

## Docker Hub Management

### Container Registry

- **Organization**: [cellularimagingcf](https://hub.docker.com/u/cellularimagingcf)

- **Published Containers**:
  - `cellularimagingcf/omeroserver`
  - `cellularimagingcf/omeroworker`
  - `cellularimagingcf/omeroweb`
  - `cellularimagingcf/biomero`
  - `cellularimagingcf/biomero-importer` (from separate repo)

- **Tagging Strategy**:
  - `latest` - Latest stable release, but preferably use specific version tags
  - `vX.Y.Z` - Specific version tags (e.g., v1.2.3)
  - `vX.Y` - Minor version tags, updated with latest patch (e.g., v1.2)
  - Pre-releases do **not** update `latest` tag

### Repository Management

- **Automated Publishing**
  - GitHub Actions handles all container publishing
  - No manual Docker Hub interactions needed
  - Credentials managed via GitHub Secrets

- **Tag Management**
  - Stable releases automatically tagged as `latest`
  - Pre-releases (alpha, beta, rc) maintain separate tags
  - Version-specific tags are always created

## Communication & Announcements

### Release Communication

**Significant Releases** (major versions, important features):

1. **NVVM Slack** - Internal team communication

   ```text
   📢 NL-BIOMERO v2.0.0 Released!

   Major updates:
   • New React-based UI via OMERO.biomero plugin
   • Enhanced BIOMERO workflow integration
   • Breaking changes: see migration guide

   Release notes: https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO/releases/tag/v2.0.0
   ```

2. **Image.sc Forum** - Community announcements
   - Post in appropriate categories:
     - [Announcements](https://forum.image.sc/c/announcements)
   - Tag with e.g.
     - [BIOMERO](https://forum.image.sc/tag/biomero)
     - [OMERO](https://forum.image.sc/tag/omero)
     - [BIAFLOWS](https://forum.image.sc/tag/biaflows)

**Patch Releases** (bug fixes):
- GitHub release notes sufficient
- Internal notification if critical fixes

### Release Notes Template

```markdown
## What's Changed

### 🚀 New Features
- Added new BIOMERO workflow XYZ
- Enhanced web interface with React components

### 🐛 Bug Fixes
- Fixed import issue with large datasets
- Resolved Metabase dashboard loading

### 📚 Documentation
- Updated deployment guide
- Added developer container documentation

### ⚠️ Breaking Changes
- Configuration format changed (see migration guide)
- Deprecated old API endpoints

### 🔧 Dependencies
- Updated BIOMERO to v2.1.0
- Updated OMERO base images to 5.6.17

**Full Changelog**: https://github.com/.../compare/v1.0.0...v2.0.0
```

## Troubleshooting Releases

### Common Issues

**Build Failures**
- Check GitHub Actions logs
- Verify Dockerfile syntax
- Test local builds before releasing

**Dependency Conflicts**
- Update dependency versions incrementally
- Test each dependency update separately
- Use development environment for testing

**Docker Hub Issues**
- Verify GitHub Secrets are configured
- Check Docker Hub organization permissions
- Monitor Docker Hub service status

### Emergency Releases

For critical security fixes or major bugs:

1. **Create hotfix branch** from latest stable tag
2. **Apply minimal fix** (avoid feature additions)
3. **Test thoroughly** but expedite process
4. **Release as patch version** (increment PATCH number)
5. **Communicate urgency** in release notes and announcements

## Best Practices

### Release Checklist

Before creating a release:

```text
☐ All dependencies updated and tested
☐ Local build and testing completed
☐ Documentation updated for new features
☐ Migration guide written (if breaking changes)
☐ Release notes prepared
☐ Version number follows semantic versioning
☐ Pre-release marked appropriately (if applicable)
```

### Release Quality

- **Test thoroughly** before releasing
- **Use development environment** for pre-release testing
- **Coordinate with team** for major releases
- **Monitor post-release** for issues
- **Be prepared** to create hotfix releases if needed

## Related Documentation

- [Getting Started](../getting-started.md) - Development setup
- [Architecture](../architecture.md) - System architecture
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Hub Documentation](https://docs.docker.com/docker-hub/)
- [Semantic Versioning](https://semver.org/)
