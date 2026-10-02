"""Download a pinned GitHub Release into the offline wheelhouse. Never fall back.

All assets are verified before exposing them in the output directory. Existing
different bytes for a version are refused rather than silently replaced.
"""

import argparse
import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from analysis_release import release_version, validate_manifest, verify_asset, digest

RELEASES = "https://github.com/NL-BioImaging/OMERO.Analysis/releases/download"


def download(url, path, limit):
    try:
        with urllib.request.urlopen(url, timeout=120) as response, path.open("wb") as stream:
            total = 0
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > limit:
                    raise ValueError(f"Release asset exceeds declared size: {path.name}")
                stream.write(block)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"GitHub Release asset unavailable (HTTP {exc.code}): {url}; no fallback") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not download GitHub Release asset: {url}: {exc.reason}; no fallback") from exc


def prepare_release(version, output, fetch=download):
    release_version(version)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    base = f"{RELEASES}/v{version}"
    with tempfile.TemporaryDirectory(prefix="analysis-release-", dir=output.parent) as folder:
        staging = Path(folder)
        manifest_path = staging / "manifest.json"
        fetch(f"{base}/manifest.json", manifest_path, 1024 * 1024)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = validate_manifest(manifest, version)
        for entry in entries:
            asset = staging / entry["name"]
            fetch(f"{base}/{entry['name']}", asset, entry["size"])
            verify_asset(asset, entry)
        manifest_name = f"omero-analysis-release-{version}.manifest.json"
        manifest_path.rename(staging / manifest_name)
        for asset in staging.iterdir():
            target = output / asset.name
            if target.exists() and digest(target) != digest(asset):
                raise ValueError(f"Refusing to replace different bytes for {target.name}")
        # An interrupted preparation cannot look like a complete verified release:
        # publish its manifest only after both wheels have reached the wheelhouse.
        for entry in entries:
            asset = staging / entry["name"]
            asset.replace(output / asset.name)
        (staging / manifest_name).replace(output / manifest_name)
    print(f"Prepared verified Analysis {version} and SDK wheels at {output}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=Path("dist/wheelhouse"))
    args = parser.parse_args()
    try:
        prepare_release(args.version, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Analysis release preparation failed: {exc}\n")


if __name__ == "__main__":
    main()
