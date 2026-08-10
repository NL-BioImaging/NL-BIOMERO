# OMERO.DataQueryWorker operations

Every maintained Compose scenario containing `omeroweb` also deploys the
released OMERO.DataQueryWorker on an internal-only `data-query` network. The
worker has no published port. Only `omeroweb` receives its private URL and
bearer token.

## Secret setup and rotation

Set `DQW_API_TOKEN` to a high-entropy deployment secret before running Docker
Compose. The repository intentionally provides no usable default. Keep the
token in the deployment secret store or local environment, never in version
control.

To rotate it, generate a replacement, update the secret supplied to Compose,
and recreate both `data-query-worker` and `omeroweb`. Requests authenticated
with the old token stop working as soon as the worker is recreated.

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
