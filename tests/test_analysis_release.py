"""Exercise the production downloader against a local release-asset HTTP server."""

import hashlib
import importlib.util
import json
import sys
import threading
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "web" / "release"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release = load("analysis_release")
downloader = load("download_analysis_release")


def wheel(directory, package, version):
    name = package.replace("-", "_")
    path = directory / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        info = f"{name}-{version}.dist-info/"
        archive.writestr(info + "METADATA", f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n")
        archive.writestr(info + "WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        if package == "omero-analysis":
            for asset in ("views.py", "templates/omero_analysis/analysis.html", "static/omero_analysis/app.js", "static/omero_analysis/pyodide/pyodide.mjs"):
                archive.writestr("omero_analysis/" + asset, "fixture")
            for asset in ("49-omero-analysis-cleanup.py", "51-omero-analysis-navigation.py", "90-omero-analysis.omero"):
                archive.writestr(f"{name}-{version}.data/data/share/omero-analysis/{asset}", "fixture")
        else:
            archive.writestr("omero_analysis_notebook/context.py", "fixture")
    return path


@pytest.fixture
def server(tmp_path, monkeypatch):
    assets = tmp_path / "releases" / "download" / "v0.15.0"
    assets.mkdir(parents=True)
    wheels = [wheel(assets, "omero-analysis", "0.15.0"), wheel(assets, "omero-analysis-notebook", "0.1.0")]
    manifest = {"schema": release.SCHEMA, "version": "0.15.0", "wheels": [
        {"name": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "size": file.stat().st_size}
        for file in wheels
    ]}
    (assets / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(tmp_path), **kwargs)
        def log_message(self, *_):
            pass
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(downloader, "RELEASES", f"http://127.0.0.1:{http.server_port}/releases/download")
    try:
        yield assets, wheels, manifest
    finally:
        http.shutdown()
        thread.join()
        http.server_close()


def test_exact_release_downloads_verified_wheels_over_http(server, tmp_path):
    _, wheels, manifest = server
    output = tmp_path / "wheelhouse"
    downloader.prepare_release("0.15.0", output)
    assert json.loads((output / "omero-analysis-release-0.15.0.manifest.json").read_text()) == manifest
    for asset in wheels:
        assert (output / asset.name).read_bytes() == asset.read_bytes()


@pytest.mark.parametrize("case", ["missing-release", "missing-wheel", "hash-mismatch", "bad-version", "corrupt-wheel"])
def test_bad_release_cannot_be_installed_or_silently_replaced(server, tmp_path, case):
    assets, wheels, manifest = server
    version = "0.15.0"
    if case == "missing-release":
        version = "0.16.0"
    elif case == "missing-wheel":
        wheels[1].unlink()
    elif case == "hash-mismatch":
        wheels[0].write_bytes(b"changed")
    elif case == "bad-version":
        manifest["version"] = "0.14.0"
        (assets / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    else:
        wheels[0].write_bytes(b"not a zip")
        manifest["wheels"][0].update(sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest(), size=wheels[0].stat().st_size)
        (assets / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "wheelhouse"
    with pytest.raises(ValueError):
        downloader.prepare_release(version, output)
    assert list(output.iterdir()) == []
