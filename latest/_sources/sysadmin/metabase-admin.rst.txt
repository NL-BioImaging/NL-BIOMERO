Metabase Administration
======================

This guide covers the administrative setup and configuration of Metabase for NL-BIOMERO deployments. For technical development details, see :doc:`../developer/containers/metabase`.

Overview
--------

Metabase provides analytics and visualization dashboards for OMERO and BIOMERO data. As a system administrator, you need to:

* Configure secure access and authentication
* Set up database connections
* Manage dashboard deployment and embedding
* Handle upgrades and migrations

Initial Security Setup
----------------------

.. danger::
   **Critical Security Configuration Required**
   
   When deploying NL-BIOMERO in any environment, you **must** change the default Metabase admin password immediately. The default credentials are publicly documented in the project repository and should **never** be used in production environments.

After First Deployment
~~~~~~~~~~~~~~~~~~~~~~~

Follow these security setup steps immediately after deployment:

**Step 1: Change Admin Password**

1. Go to your Metabase URL (e.g., ``http://localhost:3000``)
2. Log in with the default credentials: ``admin@biomero.com`` / ``b1omero``
3. Go to Settings → Account settings → Password
4. Change to a secure password and save

**Step 2: Update Database Connection Passwords**

1. Go to Settings → Admin settings → Databases
2. For each database (BIOMERO and OMERO):
   
   - Click on the database name
   - Change the password to match your environment's database passwords
   - Update host/port if different from defaults
   - Click "Save changes"
   - Click "Sync database schema now" and "Re-scan field values now"

**Step 3: Regenerate Embedding Key**

1. Go to Settings → Admin settings → Embedding
2. Click "Manage" on the Static embedding card
3. Click "Regenerate key"
4. Update your ``.env`` file with the new ``METABASE_SECRET_KEY``
5. Restart OMERO.web to pick up the new key

**Step 4: Update Dashboard URL Redirects**

1. Open the sidebar (Ctrl + .), click on "BIOMERO.importer" dashboard
2. Click "Edit dashboard" (pen icon)
3. Hover over the "Upload Status" table and click "Click behavior"
4. Update all "GO TO CUSTOM DESTINATION" URLs to match your environment
5. Repeat for the "BIOMERO Analytics" dashboard

Database Connection Management
------------------------------

Metabase connects to your OMERO and BIOMERO PostgreSQL databases to provide real-time analytics.

Adding Database Connections
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Go to Settings → Admin settings → Databases
2. Click "Add database"
3. Configure connection parameters:
   
   - **Database type**: PostgreSQL
   - **Host**: Your database host (e.g., ``postgres``)
   - **Port**: Database port (typically ``5432``)
   - **Database name**: Target database (``omero`` or ``biomero``)
   - **Username/Password**: Database credentials

Testing Connections
~~~~~~~~~~~~~~~~~~~

After adding databases:

1. Click "Save changes" to test the connection
2. Use "Sync database schema now" to refresh table structure
3. Use "Re-scan field values now" to update filter options
4. Verify tables are visible in the Data Model section

Dashboard Management
--------------------

NL-BIOMERO includes pre-configured dashboards for monitoring and analytics.

Standard Dashboards
~~~~~~~~~~~~~~~~~~~

* **Dashboard #2**: BIOMERO analytics - Workflow progress and results
* **Dashboard #6**: BIOMERO.importer - Import progress and status

Both dashboards are embedded in OMERO.web via the OMERO.biomero plugin.

Embedding Configuration
~~~~~~~~~~~~~~~~~~~~~~~

Dashboards are embedded using Metabase's static embedding feature:

1. **Enable Embedding**: Settings → Admin settings → Embedding → Static embedding
2. **Get Embed URL**: Dashboard → Sharing → Static embedding
3. **Configure Parameters**: Set up user-specific filtering (e.g., by OMERO user ID)
4. **Update Secret Key**: Ensure ``METABASE_SECRET_KEY`` matches between Metabase and OMERO.web

Editing Dashboards
~~~~~~~~~~~~~~~~~~

**Modify Existing Dashboards**:

1. Open dashboard and click "Edit dashboard" (pen icon)
2. Add, remove, or modify cards (graphs/tables)
3. Configure filters and parameter connections
4. Save changes - effects are immediate in embedded views

**Create New Dashboards**:

1. Click "New" → "Dashboard"
2. Add cards using SQL queries or Metabase Questions
3. Configure static embedding if needed for OMERO.web integration
4. Document embed parameters and integration requirements

User Account Management
-----------------------

Admin Account
~~~~~~~~~~~~~

* **Change Password**: Settings → Account settings → Password
* **Security Audit**: Review login history in account settings
* **Password Reset**: See `Metabase documentation <https://www.metabase.com/docs/latest/people-and-groups/managing#resetting-the-admin-password>`_ for admin password recovery

Additional Users
~~~~~~~~~~~~~~~~

For multi-user Metabase deployments:

1. Go to Settings → Admin settings → People
2. Add users with appropriate permissions
3. Configure groups and database access as needed

Backup and Migration
--------------------

Database File Management
~~~~~~~~~~~~~~~~~~~~~~~~

Metabase stores all configuration in an H2 database file:

* **Location**: Configured via ``MB_DB_FILE`` environment variable
* **File Format**: On disk appears as ``metabase.db.mv.db``
* **Contains**: Dashboards, users, database connections, embedding keys

**Backup Strategy**:

.. code-block:: bash

   # Stop Metabase container
   docker-compose stop metabase
   
   # Backup database file
   cp ./metabase/metabase.db.mv.db ./backups/metabase-$(date +%Y%m%d).db.mv.db
   
   # Restart container
   docker-compose start metabase

Upgrading Dashboards
~~~~~~~~~~~~~~~~~~~~

Dashboard upgrades can be challenging in the free version of Metabase:

**Option 1: Replace Database File**

1. **Backup current database**: Save your existing ``metabase.db.mv.db``
2. **Deploy updated database**: Use new database file from NL-BIOMERO releases
3. **Reconfigure environment**: Follow all steps in `Initial Security Setup`_ section
4. **Update integrations**: Restart OMERO.web with new ``METABASE_SECRET_KEY``

**Option 2: Manual Dashboard Updates**

1. **Keep existing database**: Maintain your current configuration
2. **Apply manual changes**: Update dashboards individually based on release notes
3. **Test functionality**: Verify all embedded dashboards work correctly

Environment Configuration
-------------------------

Docker Compose Setup
~~~~~~~~~~~~~~~~~~~~~

Essential environment variables for Metabase container:

.. code-block:: yaml

   services:
     metabase:
       image: metabase/metabase:latest
       environment:
         MB_DB_TYPE: h2
         MB_DB_FILE: /metabase-data/metabase.db
         JAVA_TIMEZONE: UTC
       volumes:
         - "./metabase:/metabase-data:rw"
       ports:
         - "3000:3000"

Integration with OMERO.web
~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure OMERO.web to embed Metabase dashboards:

.. code-block:: bash

   # In .env file
   METABASE_SECRET_KEY=your_generated_embedding_key
   METABASE_URL=http://metabase:3000

Security Considerations
-----------------------

Network Access
~~~~~~~~~~~~~~

* **Restrict public access**: Use reverse proxy or firewall rules
* **Database connections**: Ensure secure database authentication
* **HTTPS deployment**: Use SSL certificates for production deployments

Data Protection
~~~~~~~~~~~~~~~

* **Regular backups**: Automate Metabase database file backups
* **Access logging**: Monitor dashboard access and admin activities
* **Environment separation**: Use different credentials for dev/staging/production

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**"Message seems corrupt or manipulated" in OMERO.web iframe**

This indicates the embedding key mismatch:

1. Check current embedding key: Metabase → Settings → Admin settings → Embedding
2. Update ``METABASE_SECRET_KEY`` in your ``.env`` file
3. Restart OMERO.web container

**Database Connection Failures**

1. Verify database credentials in Metabase admin settings
2. Test network connectivity between containers
3. Check database logs for connection errors
4. Confirm PostgreSQL is accepting connections

**Dashboard Not Loading**

1. Check Metabase logs for errors
2. Verify dashboard permissions and embedding settings
3. Test dashboard access directly in Metabase UI
4. Confirm iframe parameters match dashboard expectations

Performance Issues
~~~~~~~~~~~~~~~~~~

* **Query optimization**: Review slow dashboard queries
* **Database indexing**: Add indexes for frequently queried columns
* **Resource allocation**: Increase container memory/CPU limits
* **Caching**: Configure Metabase query caching appropriately

Related Documentation
---------------------

* :doc:`omero-biomero-admin` - OMERO.biomero plugin administration
* :doc:`deployment` - Initial deployment configuration
* :doc:`../developer/containers/metabase` - Technical development details
* `Metabase Official Documentation <https://www.metabase.com/docs/>`_