#!/opt/omero/web/venv3/bin/python
"""Apply the opt-in Analysis flag after declarative OMERO config is loaded."""

import json
import os
import subprocess

OMERO = "/opt/omero/web/venv3/bin/omero"
APP = "omero_analysis"
CENTER = ["Analysis", "omero_analysis/center_plugin.js.html", "omero_analysis_panel"]


def get_list(key):
    value = subprocess.check_output([OMERO, "config", "get", key], text=True).strip()
    return json.loads(value) if value else []


def set_list(key, value):
    subprocess.run([OMERO, "config", "set", "--", key, json.dumps(value)], check=True)


def host_installed():
    from omero_analysis.host_capabilities import biomero_analysis_host_installed
    return biomero_analysis_host_installed()


def configure():
    enabled = os.environ.get("INTEGRATE_DATA_ANALYSIS", "").strip().lower() in {
        "true", "1", "yes", "on"
    }
    apps = [app for app in get_list("omero.web.apps") if app != APP]
    centers = [entry for entry in get_list("omero.web.ui.center_plugins")
               if len(entry) < 3 or entry[2] != "omero_analysis_panel"]
    links = [entry for entry in get_list("omero.web.ui.top_links")
             if len(entry) < 2 or entry[1] != "omero_analysis_index"]
    if enabled:
        if not host_installed() or "omero_biomero" not in apps:
            raise RuntimeError("Data Analysis requires a compatible installed OMERO.biomero host")
        if os.environ.get("OMERO_ANALYSIS_DATA_QUERY_WORKER_URL") and not os.environ.get("OMERO_ANALYSIS_DATA_QUERY_WORKER_TOKEN"):
            raise RuntimeError("Set DQW_API_TOKEN before enabling the configured DataQueryWorker")
        apps.append(APP)
        centers.append(CENTER)
    set_list("omero.web.apps", apps)
    set_list("omero.web.ui.center_plugins", centers)
    set_list("omero.web.ui.top_links", links)
    print("Data Analysis enabled" if enabled else "Data Analysis disabled")


if __name__ == "__main__":
    configure()
