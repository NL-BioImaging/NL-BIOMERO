# Metabase Container

The Metabase container provides analytics and visualization dashboards for OMERO and BIOMERO data.

## Why Metabase?

Metabase provides a powerful analytics solution that integrates seamlessly with our OMERO and BIOMERO infrastructure:

- **Unified Data Visibility**: Direct connections to both OMERO and BIOMERO databases provide comprehensive analytics across our entire data ecosystem
- **Embedded in Workflow**: Dashboards integrate directly into OMERO.web, keeping analytics accessible within users' existing workflows
- **Real-time Insights**: Visual exploration of data and automated import metrics without leaving the platform
- **Customizable Views**: Tailored visualizations specific to BIOMERO that adapt to user context
- **Parameter-driven**: Dashboards dynamically respond to user identity and selections, providing personalized analytics
- **Low-code Development**: Build and modify sophisticated visualizations through both SQL and visual query builders

But mainly: they provide much-needed tracking of BIOMERO workflow progress and import progress.

## Dashboard Development

### Access

- Direct UI: http://localhost:3000 (container port 3000)
- Behind reverse proxy: typically available at `/dashboard`

### Dashboards in use

- `#2` BIOMERO analytics
- `#6` BIOMERO.importer (formerly OMERO Automated Data Importer)

Both are published and embedded in OMERO.web (via OMERO.biomero) using iFrames.

### Embedding in OMERO.web

- Requires a secret key: `Settings > Admin settings > Embedding > Static embedding`
  Regenerate the static embedding key there if needed.
- iFrame embedding supports parameters (e.g., user id) that can prefill dashboard filters. These parameters are provided by the OMERO.biomero app based on the logged-in OMERO user.
- See and test options via `Sharing > Static embedding` on the dashboard.

### Editing dashboards

- Open a dashboard and click `Edit` to add or modify cards (graphs/tables).
- Queries can be written in SQL or built via Metabase “Questions”.
- Cards can:
  - Link to other pages or set on-click behavior
  - Be connected to top-level filters (selectors) so they respond to filter changes (e.g., user/group)
- All changes are reflected immediately in embedded iFrames.

### Adding a new dashboard

1. Create a new dashboard and add your cards (SQL or Questions).
2. Enable static embedding and note the embed URL/parameters.
3. Add a new iFrame integration in the relevant front-end plugin (see OMERO.biomero docs for examples).
4. Align dashboard parameters with what the embedding app sends (e.g., user id).

### Browse attached databases

- In Metabase, you can browse the connected databases (OMERO and BIOMERO Postgres) directly from the UI. This is visible to anyone with access to your Metabase instance.

### Managing database connections

- Go to `Settings > Admin settings > Databases` to:
  - Add/remove databases
  - Change host/port/username/authentication
  - Sync new schemas and re-scan field values
- Dashboards run real-time queries against these connections.

### Initial Security Setup

> **Warning:**
> When deploying NL-BIOMERO in any environment, you must change the default Metabase admin password immediately. The default credentials in NL-BIOMERO are publicly documented in the project repository and should never be used in production environments.

**After first deployment, follow these security setup steps:**

1. **Change admin password**
   - Go to your metabase URL in a browser (e.g. localhost:3000)
   - Log in with the default credentials: `admin@biomero.com` / `b1omero`
   - Go to Settings > Account settings > Password
   - Change to a secure password and save

2. **Update database connection passwords**
   - Go to Settings > Admin settings > Databases
   - For each database (BIOMERO and OMERO):
     - Click on the database name
     - Change the password to match your environment's database passwords
     - Update host/port if different from defaults
     - Click "Save changes"
     - Click "Sync database schema now" and "Re-scan field values now"

3. **Regenerate embedding key**
   - Go to Settings > Admin settings > Embedding
   - Click "Manage" on the Static embedding card
   - Click "Regenerate key"
   - Update your `.env` file with the new `METABASE_SECRET_KEY`
   - Restart OMERO.web to pick up the new key

4. **Update dashboard URL redirects**
   - Open the sidebar (Ctrl + .), click on "BIOMERO.importer" dashboard
   - Click "Edit dashboard" (pen icon)
   - Hover over the "Upload Status" table and click "Click behavior"
   - Update all "GO TO CUSTOM DESTINATION" URLs to match your environment
   - Repeat for the "BIOMERO Analytics" dashboard

### User account and password

- Change password via `Settings > Account settings > Password`.
- You can also review your login history there for security audits.
- Resetting (admin) password, see https://www.metabase.com/docs/latest/people-and-groups/managing#resetting-the-admin-password

### Versioning and migration

- Metabase stores dashboards, questions, settings, and connections in its application database file.
- In this deployment, the file path is configured via `MB_DB_FILE` (e.g., `/metabase-data/metabase.db`). On disk (H2), this may appear as `metabase.db.mv.db` in the mounted volume.
- This file contains sensitive data (secrets, DB URLs, embedding keys, admin users). Options to propagate changes:
  - Manually replicate dashboard changes across environments
  - Distribute the Metabase DB file and then update secrets per environment (DB URLs, embedding keys, admin password)
- Consider committing the DB file to source control only if acceptable for your security model.

### Upgrading Metabase Dashboards

Upgrading metabase dashboards is not straightforward sadly (at least not in the free version). You have 2 ways to go about this:

1. **Replace database with updated dashboards** - Take a new metabase database (`metabase.db.mv.db`) with updated dashboards and manually update all the admin values to match your environment again
2. **Keep existing database** - Keep your metabase database (`metabase.db.mv.db`) and manually apply all the dashboard updates

#### Upgrade Scenario 1: Replace Database

**Step 1: Replace the database file**
- Copy a `metabase.db.mv.db` (e.g. from our latest GitHub release) to your mount location of your metabase container
- Restart the container

**Step 2: Reconfigure environment settings**
- Go to your metabase URL in a browser (e.g. localhost:3000 or whatever you mapped it to with your reverse proxy)
- Log in with the default login credentials (e.g. see the .env in our latest GitHub release), not with your changed credentials
- Follow steps 2-4 from the Initial Security Setup section to update database connections, regenerate the embedding key, and update URL redirects
- Change your admin password: Settings > Account settings > Password

**Step 3: Restart OMERO.web**
- Restart OMERO.web to take the new METABASE_SECRET_KEY into account.

#### Upgrade Scenario 2: Keep Existing Database

- Go to your metabase URL in a browser (e.g. localhost:3000 or whatever you mapped it to with your reverse proxy)
- Log in with your specific credentials
- Make all the changes you need to the 2 dashboards manually: Open the sidebar (Ctrl + .), click on the bookmarked dashboard and do a combination of the following:

**Edit dashboard layout and components:**
- Edit dashboard ("Edit dashboard" button, the pen icon below the Search bar)
  - to move around tables / graphs or to add new ones or remove current ones
  - Or hover over a table to change "Visualization options" like color highlights, or "Click behavior" like URL redirects
  - Or click on the filter buttons (like "Workflow" or "User") to change which values/columns on a table/graph they should filter
- Click Save (at the top) to keep your changes (or Cancel to discard them)

**Edit individual queries and visualizations:**
- Edit an existing table/graph by clicking on its title (e.g. "Biomero Workflow Progress"). This will open the view of just that one query and its result.
  - There is a button "Show editor" underneath the Search bar where you can change the query using Metabase's fancy filters etc. See the Metabase documentation for all the options.
  - Or (if it says "This question is written in SQL.") there is a "OPEN EDITOR" button where you can change the literal SQL query that creates this result for you. When you change something, you can click the play button (Ctrl + enter) to see the result live (or no results if you misformed your SQL). Another important factor in SQL queries in Metabase is the "Variables" which you see at the top (e.g. "User Name") and that are used in the query like "{{user_name}}". You can find more info and change their behavior on the right hand side at the "{x}" button. See also the "HELP" tab there. Also here you can use the "Run query" button to see your changes, very useful.
  - When you're happy, click "Save" and "Replace original question" to immediately have it changed on your dashboard. Or "Save as new question" if so inclined. To add new questions to your dashboard, go to "Edit dashboard" again.

The changes should take effect in Metabase and OMERO.web without any delays or restarts.

## Troubleshooting

### Common Issues and Solutions

**"Message seems corrupt or manipulated" error in OMERO.web iFrame**

If you see the metabase iframe saying "Message seems corrupt or manipulated" in the OMERO.web plugin, it means that the embedding key for Metabase is not correct.

**Solution:**
Change the `METABASE_SECRET_KEY` environment variable for OMERO.web to match the embedding key in Metabase:

1. Go to Metabase: Settings > Admin settings > Embedding
2. Click "Manage" on the Static embedding card
3. Copy the current embedding key
4. Update your `.env` file: `METABASE_SECRET_KEY=<the_copied_key>`
5. Restart OMERO.web to pick up the new key

Alternatively, you can regenerate a new embedding key in Metabase (step 2 above: "Regenerate key") and then update your environment variable accordingly.

## Related Documentation

- [OMERO.biomero Plugin Administration](../../sysadmin/omero-biomero-admin.md) - OMERO.biomero plugin administration guide
- [OMERO Web](omeroweb.md) - Web interface integration
- [Architecture](../architecture.md) - System architecture
- [Metabase Documentation](https://www.metabase.com/docs/)
