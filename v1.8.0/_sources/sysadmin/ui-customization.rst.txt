UI Customization
================

Login Page Branding
-------------------

BIOMERO uses NL-BioImaging branding by default. To customize for your institution:

**Simple logo replacement:**

.. code-block:: yaml

   services:
     omeroweb:
       volumes:
         - "./your-logo.png:/opt/omero/web/venv3/lib/python3.12/site-packages/omeroweb/webclient/static/webclient/image/login_page_images/nl-bioimaging-banner.png:ro"

**Complete branding (text, colors, footer):**

.. code-block:: yaml

   services:
     omeroweb:
       volumes:
         - "./custom-login.html:/opt/omero/web/venv3/lib/python3.12/site-packages/omeroweb/webclient/templates/webclient/login.html:ro"

Create a custom login template with inline CSS styling. See ``web/local_omeroweb_edits/pretty_login/login-amsterdamumc.html`` for a complete example.

After changes, restart the web container:

.. code-block:: bash

   docker-compose down omeroweb && docker-compose up -d omeroweb