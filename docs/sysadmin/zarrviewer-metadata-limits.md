# ZarrViewer metadata size limit

The viewer already provides the OMERO setting
`omero.web.zarr_viewer.max_metadata_bytes`. Raising it is deployment
configuration and does not require a new viewer package, frontend build or
viewer release. The package default is 4 MiB per JSON metadata document.

For a deployment that needs much larger metadata, put this in its `.env`:

```ini
BIOMERO_ZARR_MAX_METADATA_BYTES=1073741824
```

This is 1 GiB per document, 256 times the package default. It covers metadata
documents such as `.zattrs`, `.zmetadata` and `zarr.json`; image pixels continue
to be read in chunks. Raising the ceiling does not preallocate that amount of
RAM, but parsing a large JSON document needs memory proportional to its contents.

The supplied Compose scenarios forward this value to OMERO.web's `CONFIG_`
startup interface and default to 1 GiB. Setting the plain
`BIOMERO_ZARR_MAX_METADATA_BYTES` process variable alone is not sufficient in a
generic OMERO.web container. For older or custom scenarios, append
`deployment_scenarios/docker-compose-zarrviewer-limits.yml` to the existing
Compose file list, preserving its other overlays.

Recreate only `omeroweb` with the existing Compose command and the additional
file, using `up -d --no-deps --no-build omeroweb`. No Slurm or workflow-worker
restart is needed for this viewer setting. Users may need to sign in again.

For an existing installation the equivalent OMERO configuration commands are:

```sh
omero config set omero.web.zarr_viewer.max_metadata_bytes 1073741824
omero config get omero.web.zarr_viewer.max_metadata_bytes
```

Restart OMERO.web after applying the direct configuration. For container
deployments, keep the Compose/environment configuration as the persistent source
so the value is restored when the web container is recreated.

If the chosen Compose service already forwards this variable, no additional
limits overlay is needed. Keep the value in the deployment's own environment
file so settings remain reproducible when the container is replaced.

Changing deployment YAML and documentation can be committed to the deployment
repository independently of the viewer's package release cycle. These local
changes do not publish a package, image, tag or GitHub release.
