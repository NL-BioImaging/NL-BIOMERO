#!/opt/omero/web/venv3/bin/python
"""Register the optional viewer after the normal OMERO configuration is loaded."""

import json
import os
import subprocess


OMERO = "/opt/omero/web/venv3/bin/omero"
APP = "biomero_zarr_viewer"
OPEN_WITH = [
    APP,
    "biomero_zarr_viewer_index",
    {
        "supported_objects": ["image", "plate"],
        "label": "OME-Zarr Viewer",
        "target": "_blank",
        "script_url": "biomero_zarr_viewer/openwith-v2.js",
    },
]


def get_list(key):
    value = subprocess.check_output([OMERO, "config", "get", key], text=True).strip()
    return json.loads(value) if value else []


def set_value(key, value):
    subprocess.run([OMERO, "config", "set", "--", key, value], check=True)


def configure():
    enabled = os.environ.get("BIOMERO_ZARR_VIEWER_ENABLED", "").strip().lower() in {
        "true", "1", "yes", "on"
    }
    # Remove only our registration, preserving every other installed plugin.
    # This also handles disabling the feature with an existing config volume.
    apps = [app for app in get_list("omero.web.apps") if app != APP]
    open_with = [entry for entry in get_list("omero.web.open_with") if entry[0] != APP]
    if enabled:
        apps.append(APP)
        open_with.append(OPEN_WITH)
        root = os.environ.get("IMPORT_MOUNT_PATH") or "/data"
        set_value("omero.web.zarr_viewer.source_root", os.environ.get("BIOMERO_ZARR_VIEWER_SOURCE_ROOT") or root)
        set_value("omero.web.zarr_viewer.mount_root", root)
        set_value("omero.web.zarr_viewer.internal_prefix", "/_biomero_zarr_internal/")
    set_value("omero.web.apps", json.dumps(apps))
    set_value("omero.web.open_with", json.dumps(open_with))
    print("OME-Zarr Viewer enabled" if enabled else "OME-Zarr Viewer disabled")


if __name__ == "__main__":
    configure()
