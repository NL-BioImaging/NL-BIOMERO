"""Shared, dependency-free validation for tagged Analysis release assets.

Also vendored into NL-BIOMERO's web/release/ for Docker build preparation.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from email.parser import BytesParser
from pathlib import Path

SCHEMA = "nl.bioimaging.omero-analysis.release.v1"
PROJECTS = {"omero-analysis", "omero-analysis-notebook"}
MAX_WHEEL_BYTES = 512 * 1024 * 1024


def release_version(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value):
        raise ValueError("Analysis version must be an exact X.Y.Z version without v (no main/latest)")
    return value


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def wheel_identity(path):
    try:
        return _wheel_identity(path)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"Invalid wheel archive: {Path(path).name}: {exc}") from exc


def _wheel_identity(path):
    """Validate the archive and its canonical name against embedded metadata."""
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
            name.startswith(("/", "\\")) or "\\" in name or ".." in name.split("/")
            for name in names
        ):
            raise ValueError(f"Unsafe wheel archive: {path.name}")
        metadata_files = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_files) != 1 or archive.testzip() is not None:
            raise ValueError(f"Corrupt wheel: {path.name}")
        metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        project = str(metadata.get("Name", "")).lower().replace("_", "-")
        version = str(metadata.get("Version", ""))
        release_version(version)
        if project not in PROJECTS:
            raise ValueError(f"Unexpected release package: {project}")
        expected = f"{project.replace('-', '_')}-{version}-py3-none-any.whl"
        info = f"{project.replace('-', '_')}-{version}.dist-info/"
        if path.name != expected or metadata_files[0] != info + "METADATA":
            raise ValueError(f"Wheel filename/metadata mismatch: {path.name}")
        wheel = BytesParser().parsebytes(archive.read(info + "WHEEL"))
        if wheel.get_all("Tag") != ["py3-none-any"] or wheel.get("Root-Is-Purelib") != "true":
            raise ValueError(f"Expected a portable pure-Python wheel: {path.name}")
        required = (
            ("omero_analysis/views.py", "omero_analysis/templates/omero_analysis/analysis.html",
             "omero_analysis/static/omero_analysis/app.js",
             "omero_analysis/static/omero_analysis/pyodide/pyodide.mjs",
             f"omero_analysis-{version}.data/data/share/omero-analysis/49-omero-analysis-cleanup.py",
             f"omero_analysis-{version}.data/data/share/omero-analysis/51-omero-analysis-navigation.py",
             f"omero_analysis-{version}.data/data/share/omero-analysis/90-omero-analysis.omero")
            if project == "omero-analysis" else ("omero_analysis_notebook/context.py",)
        )
        if not all(name in names for name in required):
            raise ValueError(f"Wheel is missing packaged application assets: {path.name}")
    return project, version


def validate_manifest(manifest, version):
    release_version(version)
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or manifest.get("version") != version:
        raise ValueError("Release manifest schema/version does not match the requested version")
    wheels = manifest.get("wheels")
    if not isinstance(wheels, list) or len(wheels) != 2:
        raise ValueError("Release must contain exactly the Analysis and notebook SDK wheels")
    found = set()
    for entry in wheels:
        if not isinstance(entry, dict):
            raise ValueError("Invalid wheel manifest entry")
        name = entry.get("name", "")
        match = re.fullmatch(r"(omero_analysis(?:_notebook)?)-(\d+\.\d+\.\d+)-py3-none-any\.whl", name) if isinstance(name, str) else None
        if not match or match[1] in found:
            raise ValueError("Invalid or duplicate release wheel filename")
        found.add(match[1])
        release_version(match[2])
        if match[1] == "omero_analysis" and match[2] != version:
            raise ValueError("Analysis wheel version differs from the release pin")
        sha = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("Invalid wheel SHA-256")
        if type(size) is not int or not 0 < size <= MAX_WHEEL_BYTES:
            raise ValueError("Invalid wheel size")
    return wheels


def verify_asset(path, entry):
    path = Path(path)
    if path.name != entry["name"] or path.stat().st_size != entry["size"]:
        raise ValueError(f"Release wheel size/name mismatch: {entry['name']}")
    if digest(path) != entry["sha256"]:
        raise ValueError(f"Release wheel SHA-256 mismatch: {path.name}")
    return wheel_identity(path)
