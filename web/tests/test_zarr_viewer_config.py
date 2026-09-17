"""Check feature transitions against OMERO's config command interface."""

import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "zarr_config", Path(__file__).parents[1] / "55-configure-zarr-viewer.py"
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ViewerConfigTests(unittest.TestCase):
    def setUp(self):
        self.other_apps = ["omero_iviewer", "omero_biomero", "omero_forms"]
        self.other_menu = [["omero_iviewer", "omero_iviewer_index", {"label": "iviewer"}]]
        self.state = {
            "omero.web.apps": json.dumps(self.other_apps),
            "omero.web.open_with": json.dumps(self.other_menu),
            "omero.web.viewer.view": "omero_iviewer.views.index",
        }

    def configure(self, env):
        def read(args, **kwargs):
            return self.state.get(args[-1], "")

        def write(args, **kwargs):
            self.state[args[-2]] = args[-1]

        with patch.dict(os.environ, env, clear=True), \
             patch.object(config.subprocess, "check_output", side_effect=read), \
             patch.object(config.subprocess, "run", side_effect=write):
            config.configure()

    def assert_disabled(self):
        self.assertEqual(json.loads(self.state["omero.web.apps"]), self.other_apps)
        self.assertEqual(json.loads(self.state["omero.web.open_with"]), self.other_menu)
        self.assertEqual(self.state["omero.web.viewer.view"], "omero_iviewer.views.index")

    def test_missing_empty_and_false_flags_preserve_existing_configuration(self):
        for env in ({}, {"BIOMERO_ZARR_VIEWER_ENABLED": ""}, {"BIOMERO_ZARR_VIEWER_ENABLED": "FALSE"}):
            with self.subTest(env=env):
                self.configure(env)
                self.assert_disabled()

    def test_enable_is_idempotent_and_disable_removes_existing_registration(self):
        env = {"BIOMERO_ZARR_VIEWER_ENABLED": "TRUE", "IMPORT_MOUNT_PATH": "/data"}
        self.configure(env)
        self.configure(env)
        self.assertEqual(json.loads(self.state["omero.web.apps"]), self.other_apps + [config.APP])
        self.assertEqual(json.loads(self.state["omero.web.open_with"]), self.other_menu + [config.OPEN_WITH])
        self.assertEqual(self.state["omero.web.zarr_viewer.mount_root"], "/data")
        self.assertEqual(self.state["omero.web.zarr_viewer.source_root"], "/data")
        self.configure({"BIOMERO_ZARR_VIEWER_ENABLED": "FALSE"})
        self.assert_disabled()

    def test_distinct_recorded_and_mounted_roots(self):
        self.configure({
            "BIOMERO_ZARR_VIEWER_ENABLED": "true",
            "IMPORT_MOUNT_PATH": "/mounted-data",
            "BIOMERO_ZARR_VIEWER_SOURCE_ROOT": "/archive",
        })
        self.assertEqual(self.state["omero.web.zarr_viewer.source_root"], "/archive")
        self.assertEqual(self.state["omero.web.zarr_viewer.mount_root"], "/mounted-data")


if __name__ == "__main__":
    unittest.main()
