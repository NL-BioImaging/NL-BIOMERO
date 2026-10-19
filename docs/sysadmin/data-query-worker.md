# OMERO.DataQueryWorker operations

Every maintained Compose scenario containing `omeroweb` offers the released
OMERO.DataQueryWorker under the optional `analysis` profile on an internal-only
`data-query` network. The demo selects this profile alongside the importer through
`COMPOSE_PROFILES=analysis,IMPORTER_ENABLED`. The
worker has no published port. Only `omeroweb` receives its private URL and
bearer token.

Set `OMERO_DATA_QUERY_WORKER_VERSION=0.2.2` in `.env` / `.env.shared`. All
eight deployment files and the worker smoke fixture use that release version.
They pull `cellularimagingcf/omero-data-query-worker` from Docker Hub, like the
other NL-BIOMERO containers. The 0.2.2 image was copied unchanged from the
historical GHCR publication, including both architectures and attestations;
the worker API and cache format are unchanged.
The smoke reads the same `.env` as the deployment. Advance it after running
Analysis's HTTP compatibility matrix and the authenticated cache smoke. Version 0.2.2 retains the 0.2.0 API and cache
format and repairs release/version publication; the failed 0.2.1 publication
must not be used as a deployment target.

## Secret setup and rotation

The tracked `.env` and `.env.shared` provide the public demo token
`nl-biomero-demo-query-worker-change-me`. This lets the demo start with Analysis
enabled, without generating a secret or creating a local Compose override.
The token is shared by OMERO.web and the worker; it is not an external API key.

Before using real data or exposing the demo to other users, replace this public
token with a unique high-entropy secret, alongside replacing the demo passwords
and rotating the Metabase dashboard embedding secret. Generate a replacement
in PowerShell or a POSIX shell:

```console
python -c "import secrets; print(secrets.token_hex(32))"
```

Set `DQW_API_TOKEN` to the generated value in your deployment environment or
deployment environment file. Keep replacement secrets out of version control.
Compose supplies the same value to both services. Recreate them to apply it:

```console
docker compose up -d --no-deps --force-recreate data-query-worker omeroweb
docker compose exec -T zarrviewer-nginx nginx -s reload
```

For other deployment scenarios, use their usual Compose files and environment
options and reload their frontend proxy. Reloading refreshes the proxy's backend
address after OMERO.web is recreated. Requests authenticated with the old token
stop working as soon as the worker is recreated. Repeat these steps to rotate
the token later; disabled Analysis deployments need no worker token.

## Readiness and restarts

The worker readiness endpoint is checked inside the container at
`/health/ready`. Inspect it with:

```console
docker compose ps data-query-worker
docker compose logs data-query-worker
```

The `data-query-cache` volume survives ordinary container recreation and
restart. Source registration and deterministic query results can therefore be
reused after a restart.

## Cache sizing and trust boundary

The default limits are 100 GiB with a seven-day TTL for source data and 10 GiB
with a 24-hour TTL for query results. Override these on the worker service when
needed with `DQW_SOURCE_CACHE_MAX_BYTES`, `DQW_SOURCE_TTL_SECONDS`,
`DQW_RESULT_CACHE_MAX_BYTES`, and `DQW_RESULT_TTL_SECONDS`. The worker evicts
expired and least-recently-used entries automatically.

The cache holds uploaded databases and generated CSV results in plaintext.
Treat the Docker volume as trusted server storage and protect the underlying
host filesystem accordingly. Cache contents are rebuildable and must be
excluded from backup sets; backing them up needlessly copies user data and can
restore stale entries. Use one worker replica per cache volume.
