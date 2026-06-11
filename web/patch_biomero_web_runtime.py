"""
Compatibility patches for the OMERO.biomero web package pinned by this deployment.

Metabase dashboard links can be rendered as absolute localhost URLs when the
embedded dashboard is viewed through a reverse proxy. The BIOMERO React app
already intercepts same-host iframe links and opens them in the top window; this
patch also rewrites localhost/127.0.0.1 links to the current public origin.

OMERO.biomero 1.3.2 calls `SlurmClient.pull_descriptor_from_github`, but newer
BIOMERO exposes the same behavior as `generic_descriptor_from_github`. Patch the
web API call sites so workflow metadata requests do not fail with HTTP 500.
Newer BIOMERO descriptors also use JSON-schema-like lowercase input types;
normalize those to the legacy labels the OMERO.biomero 1.3.2 UI renders.

Remove this when OMERO.biomero handles proxied Metabase dashboard links and the
BIOMERO descriptor method rename upstream.
"""

from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent / "patches"
OLD = (PATCH_DIR / "metabase_link_old.js").read_text(encoding="utf-8").strip()
NEW = (PATCH_DIR / "metabase_link_new.js").read_text(encoding="utf-8").strip()
BIOMERO_BUNDLE_ROOTS = [
    Path(
        "/opt/omero/web/venv3/lib/python3.12/site-packages/"
        "omero_biomero/static/omero_biomero/assets"
    ),
    Path("/opt/omero/web/OMERO.web/var/static/omero_biomero/assets"),
]
ANALYZER_VIEWS = Path(
    "/opt/omero/web/venv3/lib/python3.12/site-packages/"
    "omero_biomero/analyzer_views.py"
)
NORMALIZE_HELPER = '''


def _nl_biomero_normalize_workflow_metadata(metadata):
    """Translate newer BIOMERO descriptor types for the OMERO.biomero 1.3.2 UI."""
    if not isinstance(metadata, dict):
        return metadata

    type_map = {
        "integer": "Number",
        "float": "Number",
        "number": "Number",
        "boolean": "Boolean",
        "bool": "Boolean",
        "string": "String",
        "str": "String",
    }
    normalized = dict(metadata)
    inputs = []
    for input_param in metadata.get("inputs", []):
        if not isinstance(input_param, dict):
            inputs.append(input_param)
            continue
        item = dict(input_param)
        raw_type = item.get("type")
        if isinstance(raw_type, str):
            item["type"] = type_map.get(raw_type.lower(), raw_type)
        inputs.append(item)
    normalized["inputs"] = inputs
    return normalized
'''


def patch_bundle(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    patched = source.replace(OLD, NEW)
    if patched == source:
        return False
    path.write_text(patched, encoding="utf-8")
    return True


def patch_analyzer_views(path: Path) -> bool:
    if not path.exists():
        raise RuntimeError(f"Could not find OMERO.biomero analyzer views: {path}")
    source = path.read_text(encoding="utf-8")
    patched = source
    if "_nl_biomero_normalize_workflow_metadata" not in patched:
        anchor = "logger = logging.getLogger(__name__)\n"
        if anchor not in patched:
            raise RuntimeError("Could not patch OMERO.biomero metadata normalizer")
        patched = patched.replace(anchor, anchor + NORMALIZE_HELPER, 1)
    patched = patched.replace(
        "sc.pull_descriptor_from_github(workflow_name)",
        "sc.generic_descriptor_from_github(workflow_name)",
    )
    descriptor_call = "            metadata = sc.generic_descriptor_from_github(workflow_name)\n"
    normalized_call = (
        "            metadata = sc.generic_descriptor_from_github(workflow_name)\n"
        "            metadata = _nl_biomero_normalize_workflow_metadata(metadata)\n"
    )
    normalization_line = (
        "            metadata = _nl_biomero_normalize_workflow_metadata(metadata)\n"
    )
    if normalization_line not in patched:
        if descriptor_call not in patched:
            raise RuntimeError("Could not patch OMERO.biomero workflow metadata API")
        patched = patched.replace(descriptor_call, normalized_call)
    if patched == source:
        return False
    path.write_text(patched, encoding="utf-8")
    return True


def main() -> None:
    # The package asset path is present during image build. The staticfiles path
    # can exist after collection, so keep both locations in one explicit list.
    changed = 0
    for root in BIOMERO_BUNDLE_ROOTS:
        if not root.exists():
            continue
        for path in root.glob("main.*.js"):
            changed += patch_bundle(path)
    if changed == 0:
        raise RuntimeError("Could not patch OMERO.biomero web bundle")
    print(f"patched {changed} BIOMERO web bundle file(s)")
    if patch_analyzer_views(ANALYZER_VIEWS):
        print("patched OMERO.biomero workflow metadata API")


if __name__ == "__main__":
    main()
