#!/usr/bin/env python3
import omero.model
from omero.rtypes import rstring, rbool
from omero.gateway import BlitzGateway
import os
import sys
import time
import logging

# Silence expected warnings
logging.getLogger("omero.gateway").setLevel(logging.ERROR)
logging.getLogger("omero.client").setLevel(logging.ERROR)
logging.getLogger("paramiko").setLevel(logging.ERROR)


def create_forms_user(host, username, password, forms_user, forms_password, max_attempts=50):
    print("Waiting for OMERO server to be ready...")
    for attempt in range(max_attempts):
        try:
            forms_conn = BlitzGateway(forms_user, forms_password, host=host, port=4064)
            if forms_conn.connect():
                print(f"User {forms_user} already exists and can log in")
                return True

            conn = BlitzGateway(username, password, host=host, port=4064)
            if not conn.connect():
                if attempt % 5 == 0:  # Only print every 5th attempt
                    print(
                        f"Server not ready, attempt {attempt + 1}/{max_attempts}")
                time.sleep(5)  # Increased delay between attempts
                continue

            admin_serv = conn.getAdminService()

            # Check if user exists
            try:
                admin_serv.lookupExperimenter(forms_user)
                print(f"User {forms_user} already exists, updating password")
                conn.c.sf.setSecurityPassword(password)
                admin_serv.changeUserPassword(
                    forms_user, rstring(forms_password))
                return True
            except omero.ApiUsageException:
                print(f"User {forms_user} not found, creating...")

            # Create admin user (similar to: omero user add formmaster form master system)
            experimenter = omero.model.ExperimenterI()
            experimenter.omeName = rstring(forms_user)
            experimenter.firstName = rstring(forms_user)
            experimenter.lastName = rstring(forms_user)
            experimenter.email = rstring("")
            experimenter.ldap = rbool(False)

            # Get system group ID and create group list
            security_roles = admin_serv.getSecurityRoles()
            system_gid = security_roles.systemGroupId
            user_gid = security_roles.userGroupId  # Need user group for active users

            system_group = omero.model.ExperimenterGroupI(system_gid, False)
            user_group = omero.model.ExperimenterGroupI(user_gid, False)

            # Create full admin user with system group as default and both groups
            exp_id = admin_serv.createExperimenterWithPassword(
                experimenter,
                rstring(forms_password),
                system_group,  # default group
                [system_group, user_group]  # groups - need both for active user
            )
            print(f"Created admin user {forms_user}")
            return True

        except Exception as e:
            if attempt == max_attempts - 1:
                print(
                    f"Max attempts ({max_attempts}) reached. Last error: {str(e)}")
                return False
        finally:
            if 'forms_conn' in locals():
                forms_conn.close()
            if 'conn' in locals():
                conn.close()

        time.sleep(2)
    return False


if __name__ == "__main__":
    host = os.environ.get("OMEROHOST", "localhost")
    root_pass = os.environ.get("ROOTPASS", "omero")
    forms_user = os.environ.get("FORMS_MASTER_USER")
    forms_pass = os.environ.get("FORMS_MASTER_PASSWORD")

    if not all([forms_user, forms_pass]):
        print("Missing required environment variables")
        sys.exit(1)

    success = create_forms_user(
        host, "root", root_pass, forms_user, forms_pass)
    sys.exit(0 if success else 1)
