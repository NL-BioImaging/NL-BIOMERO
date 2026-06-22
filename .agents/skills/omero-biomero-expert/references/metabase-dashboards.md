# Metabase Dashboards

BIOMERO Import and Analyze status pages embed Metabase dashboards. Most blank, spinner, or iframe failures are Metabase configuration or datasource problems, not OMERO.web React problems.

## Expected Dashboard IDs

Known working BIOMERO dashboard IDs:

```text
METABASE_WORKFLOWS_DB_PAGE_DASHBOARD_ID=2  # BIOMERO Analytics, Analyze > Status
METABASE_IMPORTS_DB_PAGE_DASHBOARD_ID=6    # OMERO Automated Data Importer, Import > Monitor
```

Good dashboard state:

```text
ID 2 | BIOMERO Analytics             | ENABLE_EMBEDDING TRUE  | ARCHIVED FALSE
ID 6 | OMERO Automated Data Importer | ENABLE_EMBEDDING TRUE  | ARCHIVED FALSE
```

Bad state observed on prod:

```text
ID 1 | E-commerce insights | ENABLE_EMBEDDING FALSE
```

## Environment Alignment

Verify `omeroweb` and `metabase` agree on URL and secret:

```bash
cd /opt/omero/NL-BIOMERO
sudo docker compose exec -T metabase env | sort | grep -E 'MB_|METABASE' | sed -E 's/(PASSWORD|SECRET|KEY)=.*/\1=***MASKED***/'
sudo docker compose exec -T omeroweb env | sort | grep -E 'METABASE_(IMPORTS|WORKFLOWS|SITE|SECRET)' | sed -E 's/(PASSWORD|SECRET|KEY)=.*/\1=***MASKED***/'
grep -nE 'METABASE_(SITE|IMPORTS|WORKFLOWS|SECRET)' .env | sed -E 's/(SECRET_KEY=).*/\1***MASKED***/'
```

Metabase env should include:

```text
MB_ENABLE_EMBEDDING=true
MB_ENABLE_EMBEDDING_STATIC=true
MB_EMBEDDING_SECRET_KEY=<same value as METABASE_SECRET_KEY>
MB_SITE_URL=https://<host>/metabase
```

If an iframe says `Message seems corrupt or manipulated`, the Metabase embedding key and `METABASE_SECRET_KEY` do not match. Update `.env`, then restart `omeroweb`.

## Inspect H2 Without Stopping Metabase

Copy the locked live H2 file and query the copy:

```bash
cd /opt/omero/NL-BIOMERO
sudo docker compose exec -T metabase sh -lc '
  rm -rf /tmp/mbinspect &&
  mkdir /tmp/mbinspect &&
  cp /metabase-data/metabase.db/metabase.db.mv.db /tmp/mbinspect/metabase.db.mv.db &&
  /opt/java/openjdk/bin/java -cp /app/metabase.jar org.h2.tools.Shell \
    -url "jdbc:h2:/tmp/mbinspect/metabase.db;ACCESS_MODE_DATA=r" \
    -sql "select id, name, enable_embedding, archived from report_dashboard order by id;"
'
```

Datasource inspection:

```bash
sudo docker compose exec -T metabase sh -lc '
  rm -rf /tmp/mbinspect &&
  mkdir /tmp/mbinspect &&
  cp /metabase-data/metabase.db/metabase.db.mv.db /tmp/mbinspect/metabase.db.mv.db &&
  /opt/java/openjdk/bin/java -cp /app/metabase.jar org.h2.tools.Shell \
    -url "jdbc:h2:/tmp/mbinspect/metabase.db;ACCESS_MODE_DATA=r" \
    -list \
    -sql "select id, name, engine, details from metabase_database order by id;"
' | sed -E 's/(password[^,}]*[,:][^,}]*)/password:***MASKED***/Ig'
```

Known datasource IDs:

```text
2 = BIOMERO, postgres, host database-biomero, db biomero, user biomero
4 = OMERO, postgres, host database, db omero, user omero
```

## Error: Embedding Is Not Enabled

The iframe is reaching Metabase, but the signed resource is not embeddable or the configured dashboard ID points to the wrong object.

Fix pattern:

```bash
cd /opt/omero/NL-BIOMERO
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p backups
sudo docker compose stop omeroweb metabase
sudo tar -czf "backups/metabase.pre-dashboard-fix.$TS.tar.gz" metabase
cp .env "backups/env.pre-dashboard-fix.$TS"
# Replace metabase/ with known-good BIOMERO dashboards, preserving numeric ownership.
sudo sed -i 's/^METABASE_IMPORTS_DB_PAGE_DASHBOARD_ID=.*/METABASE_IMPORTS_DB_PAGE_DASHBOARD_ID=6/' .env
sudo sed -i 's/^METABASE_WORKFLOWS_DB_PAGE_DASHBOARD_ID=.*/METABASE_WORKFLOWS_DB_PAGE_DASHBOARD_ID=2/' .env
sudo docker compose up -d metabase omeroweb
```

When copying from dev:

```bash
tar --numeric-owner -czf - metabase | ssh -F .ssh/config biomero-prod '
  cd /opt/omero/NL-BIOMERO &&
  sudo rm -rf metabase &&
  sudo tar --numeric-owner -xzf -
'
```

After cross-host copy, always repair datasource credentials for the target `.env`.

## Dashboard Spinner / Query Failure

A card that spins forever often means the embedded card query failed. Check logs:

```bash
cd /opt/omero/NL-BIOMERO
sudo docker compose logs --since=15m metabase | grep -Ei 'error|exception|failed|timeout|permission|database|query|card|dashboard|FATAL' | tail -200
```

Observed failure:

```text
Error processing query: FATAL: password authentication failed for user "biomero"
:context :embedded-dashboard
:card-name "Biomero Workflow Progress"
:dashboard-id 2
:database 2
```

This means dashboards are present but Metabase datasource credentials came from another environment.

Stop Metabase before editing H2:

```bash
cd /opt/omero/NL-BIOMERO
sudo docker compose stop metabase
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p backups
sudo tar -czf "backups/metabase.pre-datasource-fix.$TS.tar.gz" metabase
set -a
. ./.env
set +a
sudo docker run --rm -v /opt/omero/NL-BIOMERO/metabase:/metabase-data \
  metabase/metabase@sha256:f7b5dc52c21aaa2dca910a450e7e6119a975090ce9fc80726aa0742882ca176c \
  sh -lc "/opt/java/openjdk/bin/java -cp /app/metabase.jar org.h2.tools.Shell \
    -url jdbc:h2:/metabase-data/metabase.db/metabase.db \
    -sql \"update metabase_database set details='{\\\"ssl\\\":false,\\\"password\\\":\\\"$BIOMERO_POSTGRES_PASSWORD\\\",\\\"advanced-options\\\":false,\\\"schema-filters-type\\\":\\\"all\\\",\\\"use-auth-provider\\\":false,\\\"dbname\\\":\\\"$BIOMERO_POSTGRES_DB\\\",\\\"host\\\":\\\"database-biomero\\\",\\\"tunnel-enabled\\\":false,\\\"user\\\":\\\"$BIOMERO_POSTGRES_USER\\\"}' where id=2;
           update metabase_database set details='{\\\"ssl\\\":false,\\\"password\\\":\\\"$POSTGRES_PASSWORD\\\",\\\"advanced-options\\\":false,\\\"schema-filters-type\\\":\\\"all\\\",\\\"use-auth-provider\\\":false,\\\"dbname\\\":\\\"$POSTGRES_DB\\\",\\\"host\\\":\\\"database\\\",\\\"tunnel-enabled\\\":false,\\\"user\\\":\\\"$POSTGRES_USER\\\"}' where id=4;\""
sudo docker compose up -d metabase
```

Validate:

```bash
sudo docker compose logs --since=30s metabase | grep -Ei 'password authentication failed|Error processing query|FATAL' || true
```

Dashboard 2 card mapping observed for Analyze > Status:

```text
dashcard 61 / card 45 = Biomero Workflow Progress
```

## Signed Embed Smoke Test

Generate a short-lived Metabase JWT and query a dashboard card without a browser:

```bash
cd /opt/omero/NL-BIOMERO
SECRET=$(grep ^METABASE_SECRET_KEY= .env | cut -d= -f2-) python3 - <<'PY' > /tmp/mbtoken
import base64, hashlib, hmac, json, os, time
secret = os.environ["SECRET"].encode()
def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
header = b64(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",", ":")).encode())
payload = b64(json.dumps({"resource":{"dashboard":2},"params":{"user":[0]},"exp":int(time.time())+600}, separators=(",", ":")).encode())
msg = header + "." + payload
sig = b64(hmac.new(secret, msg.encode(), hashlib.sha256).digest())
print(msg + "." + sig)
PY
TOKEN=$(cat /tmp/mbtoken)
curl -k -sS -o /tmp/card.out -w '%{http_code} %{content_type} %{size_download}\n' \
  "https://surfbiomero.biomero-data-ch.src.surf-hosted.nl/metabase/api/embed/dashboard/$TOKEN/dashcard/61/card/45"
head -c 300 /tmp/card.out
```

Good analyzer card result: HTTP `202 application/json` with data rows.

For Import > Monitor, generate the token with dashboard `6` and inspect its dashcards:

```sql
select dc.id as dashcard_id, dc.card_id, c.name
from report_dashboardcard dc
join report_card c on c.id=dc.card_id
where dc.dashboard_id=6
order by dc.id;
```

## Runtime Web Patch

`web/patch_biomero_web_runtime.py` patches pinned OMERO.biomero bundle files so Metabase links rendered as `localhost` or `127.0.0.1` stay under the public OMERO origin when embedded behind a reverse proxy. Remove this only when upstream OMERO.biomero handles proxied Metabase dashboard links.
