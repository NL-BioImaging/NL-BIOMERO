"""Discover and compare returned NGFF stores without mutating them.

This module is the decision boundary used before shallow-result normalization.
It deliberately performs no deletion, rewriting, or OMERO registration.  A
caller can therefore run it in keep-only mode and safely retain every result
when discovery or identity matching is incomplete.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import Literal
from uuid import UUID, uuid4

from biomero_schema.zarr import (
    CanonicalInput,
    CanonicalInputManifest,
    ManagedZarrNode,
    PixelIdentity,
    SHALLOW_COLLECTION_MANIFEST,
    TRANSFER_INPUT_MARKER,
    ShallowBindings,
    ShallowCollection,
    ShallowImageBinding,
    ShallowImageNode,
    ShallowLabelBinding,
    ShallowLabelNode,
    ShallowManifest,
    ShallowPlateReference,
    ShallowZarrReference,
    ZarrImportOptions,
    ZarrLabelComponent,
)

from .pixel_identity import (
    IsccBioIdentityProvider,
    PixelIdentityError,
    pixel_identities_match,
    read_zarr_v2_semantic_guard,
)



def _copy2_bounded(source, destination):
    """Copy Windows-mounted files in bounded buffers, preserving metadata."""
    with open(source, "rb") as incoming, open(destination, "wb") as outgoing:
        shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
    shutil.copystat(source, destination)
    return destination

@dataclass(frozen=True)
class NgffNode:
    """One explicitly discovered image or label node in a returned store."""

    node_path: str
    role: Literal["image", "label"]
    parent_image_node_path: str | None = None


@dataclass(frozen=True)
class ReturnedZarrDecision:
    """Keep-only result of comparing one returned store with workflow inputs."""

    store_path: Path
    outcome: Literal["eligible", "keep-full", "skip-passthrough"]
    reason: str
    image_identities: tuple[PixelIdentity, ...] = ()
    label_identities: tuple[PixelIdentity, ...] = ()
    label_components: tuple[ZarrLabelComponent, ...] = ()
    label_node_paths: tuple[str, ...] = ()
    matched_inputs: tuple[CanonicalInput, ...] = ()

    @property
    def eligible(self) -> bool:
        return self.outcome == "eligible"

    @property
    def unchanged_passthrough(self) -> bool:
        return self.outcome == "skip-passthrough"


@dataclass(frozen=True)
class NormalizedShallowResult:
    """Committed shallow collection and optional storage measurements."""

    store_path: Path
    manifest: ShallowManifest
    bytes_before: int | None
    bytes_after: int | None


@dataclass(frozen=True)
class ShallowRegistration:
    """Resolved registration view for a shallow result or label projection."""

    collection_root: Path
    registration_path: Path
    reference: ShallowZarrReference | ShallowPlateReference
    kind: Literal["primary", "label", "plate"]
    plate_label_paths: tuple[tuple[str, Path], ...] = ()
    plate_label_name: str | None = None


@dataclass(frozen=True)
class MaterializedShallowResult:
    """A full temporary workflow input reconstructed from managed components."""

    destination: Path
    manifest: ShallowManifest
    labels: tuple[ZarrLabelComponent, ...]


def _safe_node_path(value: str) -> str:
    if not value or "\\" in value:
        raise PixelIdentityError(f"Unsafe NGFF node path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise PixelIdentityError(f"Unsafe NGFF node path: {value!r}")
    return value


def _join_node_path(*parts: str) -> str:
    useful = [part for part in parts if part and part != "."]
    return str(PurePosixPath(*useful)) if useful else "."


def _node_directory(root: Path, node_path: str) -> Path:
    if node_path == ".":
        return root
    return root.joinpath(*PurePosixPath(node_path).parts)


def _read_attrs(node: Path) -> dict:
    path = node / ".zattrs"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PixelIdentityError(f"Cannot read NGFF attributes: {path}") from exc
    if not isinstance(value, dict):
        raise PixelIdentityError(f"Invalid NGFF attributes: {path}")
    return value


def _write_json(path: Path, value: dict) -> None:
    from .transaction import sync_directory
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def _write_bytes(path: Path, value: bytes) -> None:
    """Atomically restore file content used by normalization rollback."""
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    from .transaction import sync_directory
    with temporary.open("wb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def load_managed_storage_roots(
    *,
    import_mount_path: str | Path | None = None,
    config_file: str | Path | None = None,
    group_mappings_file: str | Path | None = None,
) -> dict[str, Path]:
    """Resolve managed roots from the shared runtime group mappings."""
    import_root = Path(
        import_mount_path or os.getenv("IMPORT_MOUNT_PATH", "/data")
    ).resolve()
    if not import_root.is_absolute():
        raise ValueError("IMPORT_MOUNT_PATH must be absolute")

    config_path = Path(config_file or os.getenv(
        "OMERO_BIOMERO_CONFIG_FILE",
        "/auto-importer/config/biomero-config.json",
    ))
    mappings_path = Path(group_mappings_file or os.getenv(
        "OMERO_BIOMERO_GROUP_MAPPINGS_FILE",
        "/auto-importer/config/group-mappings.json",
    ))

    def read_object(path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot load managed storage mapping {path}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Managed storage mapping must be an object: {path}")
        return value

    legacy = read_object(config_path).get("group_mappings", {})
    if not isinstance(legacy, dict):
        raise ValueError("biomero-config.json group_mappings must be an object")
    mappings = dict(legacy)
    mappings.update(read_object(mappings_path))

    roots = {"import-mount-data": import_root}
    for group_id, mapping in mappings.items():
        if not isinstance(mapping, dict):
            raise ValueError(f"Invalid group mapping for {group_id!r}")
        try:
            normalized_id = int(group_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid group ID {group_id!r}") from exc
        folder = mapping.get("folder")
        if not folder or folder in {".", "root"}:
            root = import_root
        else:
            folder_path = Path(str(folder))
            if folder_path.is_absolute() or ".." in folder_path.parts:
                raise ValueError(
                    f"Group {normalized_id} folder must be relative to IMPORT_MOUNT_PATH"
                )
            root = (import_root / folder_path).resolve()
            try:
                root.relative_to(import_root)
            except ValueError as exc:
                raise ValueError(
                    f"Group {normalized_id} folder escapes IMPORT_MOUNT_PATH"
                ) from exc
        roots[f"group-{normalized_id}-data"] = root
    return roots


def resolve_managed_source_path(
    source,
    storage_roots: dict[str, Path],
) -> Path:
    """Resolve a canonical source without allowing its locator to escape."""
    root = storage_roots.get(source.storage_root)
    if root is None:
        raise ValueError(f"Unknown managed storage root {source.storage_root!r}")
    root = Path(root).resolve()
    candidate = (root / Path(source.relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Canonical source escapes storage root {source.storage_root}"
        ) from exc
    if not candidate.is_dir():
        raise ValueError(f"Canonical source is unavailable: {candidate}")
    return candidate


def resolve_shallow_registration(
    zarr_path: str | Path,
    *,
    storage_roots: dict[str, Path] | None = None,
    import_mount_path: str | Path | None = None,
    import_options: ZarrImportOptions | dict | None = None,
) -> ShallowRegistration | None:
    """Resolve a primary shallow result or one of its label projections."""
    path = Path(zarr_path).resolve()
    import_root = Path(
        import_mount_path or os.getenv("IMPORT_MOUNT_PATH", "/data")
    ).resolve()
    try:
        path.relative_to(import_root)
    except ValueError:
        return None

    collection_root = None
    for candidate in (path, *path.parents):
        try:
            candidate.relative_to(import_root)
        except ValueError:
            break
        if (candidate / SHALLOW_COLLECTION_MANIFEST).is_file():
            collection_root = candidate
            break
        if candidate == import_root:
            break
    if collection_root is None:
        return None

    try:
        manifest = ShallowManifest.from_dict(json.loads(
            (collection_root / SHALLOW_COLLECTION_MANIFEST).read_text(
                encoding="utf-8"
            )
        ))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise PixelIdentityError(
            f"Invalid shallow collection manifest: {collection_root}"
        ) from exc

    options = (
        import_options
        if isinstance(import_options, ZarrImportOptions)
        else ZarrImportOptions.from_dict(import_options or {})
    )
    roots = storage_roots or load_managed_storage_roots(
        import_mount_path=import_root
    )
    relative_node = (
        "." if path == collection_root
        else path.relative_to(collection_root).as_posix()
    )
    if relative_node == ".":
        source_types = {
            binding.source.source_object_type
            for binding in manifest.bindings.images
        }
        if source_types == {"Plate"}:
            reference = ShallowPlateReference.from_manifest(
                manifest,
                storage_root="import-mount-data",
                relative_path=collection_root.relative_to(
                    import_root
                ).as_posix(),
            )
            first_source = manifest.bindings.images[0].source
            registration_path = resolve_managed_source_path(
                first_source,
                roots,
            )
            plate_label_paths = []
            if options.plate_pixel_source == "label":
                label_name = options.plate_label_name
                for plate_image in manifest.collection.images:
                    logical_path = _join_node_path(
                        plate_image.node_path,
                        "labels",
                        label_name,
                    )
                    components = [
                        binding.component
                        for binding in manifest.label_bindings_for_image(
                            plate_image.node_id
                        )
                        if binding.component.logical_node_path == logical_path
                    ]
                    if len(components) != 1:
                        raise PixelIdentityError(
                            f"Plate image {plate_image.node_path} does "
                            f"not declare label {label_name!r} exactly once"
                        )
                    component = components[0]
                    if component.source is None:
                        physical_path = _node_directory(
                            collection_root,
                            logical_path,
                        )
                    else:
                        physical_root = resolve_managed_source_path(
                            component.source,
                            roots,
                        )
                        physical_path = _node_directory(
                            physical_root,
                            component.source.node_path,
                        )
                    if not physical_path.is_dir():
                        raise PixelIdentityError(
                            f"Plate label is unavailable: {physical_path}"
                        )
                    plate_label_paths.append((
                        plate_image.node_path,
                        physical_path,
                    ))
            return ShallowRegistration(
                collection_root=collection_root,
                registration_path=registration_path,
                reference=reference,
                kind="plate",
                plate_label_paths=tuple(plate_label_paths),
                plate_label_name=options.plate_label_name,
            )
        if len(manifest.collection.images) != 1 or source_types != {"Image"}:
            raise PixelIdentityError(
                "Primary registration requires one Image or one Plate source"
            )
        image = manifest.collection.images[0]
        kind = "primary"
    else:
        matches = [
            image for image in manifest.collection.images
            if relative_node in {
                label.node_path for label in manifest.collection.labels
                if label.source_image_id == image.node_id
            }
        ]
        if len(matches) != 1:
            raise PixelIdentityError(
                f"Zarr path is not a declared shallow label: {path}"
            )
        image = matches[0]
        kind = "label"

    reference = ShallowZarrReference.from_manifest(
        manifest,
        storage_root="import-mount-data",
        relative_path=collection_root.relative_to(import_root).as_posix(),
        image_node_path=image.node_path,
    )
    if kind == "label":
        registration_path = path
    else:
        source = manifest.image_binding(image.node_id).source
        registration_path = resolve_managed_source_path(source, roots)
        if source.node_path != ".":
            registration_path = _node_directory(
                registration_path,
                source.node_path,
            )
        if not registration_path.is_dir():
            raise PixelIdentityError(
                f"Shallow source image node is unavailable: {registration_path}"
            )
    return ShallowRegistration(
        collection_root=collection_root,
        registration_path=registration_path,
        reference=reference,
        kind=kind,
    )


def materialize_shallow_zarr(
    reference: ShallowZarrReference | ShallowPlateReference,
    destination: str | Path,
    storage_roots: dict[str, Path],
    *,
    replace=os.replace,
) -> MaterializedShallowResult:
    """Build a conventional image or Plate Zarr from a shallow reference.

    The managed source and collections are read-only. The destination is
    assembled as a sibling staging directory and atomically renamed only after
    every declared label has been copied and its stable source recorded.
    """
    if isinstance(reference, ShallowPlateReference):
        return _materialize_shallow_plate_zarr(
            reference,
            destination,
            storage_roots,
            replace=replace,
        )

    destination = Path(destination)
    if destination.exists():
        raise PixelIdentityError(
            f"Shallow materialization destination already exists: {destination}"
        )
    collection_root = resolve_managed_source_path(reference, storage_roots)
    manifest_path = collection_root / SHALLOW_COLLECTION_MANIFEST
    try:
        manifest = ShallowManifest.from_dict(json.loads(
            manifest_path.read_text(encoding="utf-8")
        ))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise PixelIdentityError(
            f"Invalid shallow collection manifest: {manifest_path}"
        ) from exc
    matches = [
        image for image in manifest.collection.images
        if image.node_path == reference.image_node_path
    ]
    if len(matches) != 1:
        raise PixelIdentityError(
            "Shallow reference must identify exactly one collection image"
        )
    image = matches[0]
    image_binding = manifest.image_binding(image.node_id)
    label_bindings = manifest.label_bindings_for_image(image.node_id)
    label_paths = tuple(
        binding.component.logical_node_path for binding in label_bindings
    )
    if (image_binding.source != reference.source
            or set(label_paths) != set(reference.label_node_paths)):
        raise PixelIdentityError(
            "Shallow reference no longer matches its collection manifest"
        )
    canonical_root = resolve_managed_source_path(
        image_binding.source, storage_roots
    )
    canonical_image = _node_directory(
        canonical_root, image_binding.source.node_path
    )
    if not canonical_image.is_dir():
        raise PixelIdentityError(
            f"Shallow source image node is unavailable: {canonical_image}"
        )
    components = tuple(binding.component for binding in label_bindings)

    token = uuid4().hex
    staging = destination.with_name(
        f".{destination.name}.biomero-materialize-{token}"
    )
    source_labels = canonical_image / "labels"

    def ignore(directory, names):
        current = Path(directory)
        ignored = {".biomero-canonical.json"}.intersection(names)
        if current == canonical_image and source_labels.name in names:
            ignored.add(source_labels.name)
        return ignored

    managed_labels = []
    try:
        shutil.copytree(canonical_image, staging, symlinks=True, ignore=ignore, copy_function=_copy2_bounded)
        labels_root = staging / "labels"
        labels_root.mkdir(parents=True, exist_ok=False)
        _write_json(labels_root / ".zgroup", {"zarr_format": 2})
        label_names = []
        for component in components:
            prefix = PurePosixPath(
                _join_node_path(image.node_path, "labels")
            )
            logical = PurePosixPath(component.logical_node_path)
            try:
                label_name = logical.relative_to(prefix).as_posix()
            except ValueError as exc:
                raise PixelIdentityError(
                    "Label paths must be nested below their image labels/"
                ) from exc
            label_names.append(label_name)
            if component.source is None:
                physical_root = collection_root
                physical_node = component.logical_node_path
                managed_source = ManagedZarrNode(
                    storage_root=reference.storage_root,
                    relative_path=reference.relative_path,
                    node_path=component.logical_node_path,
                )
            else:
                physical_root = resolve_managed_source_path(
                    component.source,
                    storage_roots,
                )
                physical_node = component.source.node_path
                managed_source = component.source
            physical_path = _node_directory(physical_root, physical_node)
            if not physical_path.is_dir():
                raise PixelIdentityError(
                    f"Managed shallow label is unavailable: {physical_path}"
                )
            target_node = _join_node_path("labels", label_name)
            target = _node_directory(staging, target_node)
            shutil.copytree(physical_path, target, symlinks=True, copy_function=_copy2_bounded)
            managed_labels.append(ZarrLabelComponent(
                logical_node_path=target_node,
                pixel_identity=component.pixel_identity.model_copy(update={
                    "node_path": target_node,
                }),
                source=managed_source,
            ))
        _write_json(labels_root / ".zattrs", {"labels": label_names})
        discovered_paths = {
            node.node_path for node in discover_ngff_nodes(staging)
            if node.role == "label"
        }
        expected_paths = {
            _join_node_path(
                "labels",
                PurePosixPath(path).relative_to(prefix).as_posix(),
            )
            for path in label_paths
        }
        if discovered_paths != expected_paths:
            raise PixelIdentityError(
                "Materialized label inventory differs from shallow collection"
            )
        replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    return MaterializedShallowResult(
        destination=destination,
        manifest=manifest,
        labels=tuple(managed_labels),
    )


def _materialize_shallow_plate_zarr(
    reference: ShallowPlateReference,
    destination: str | Path,
    storage_roots: dict[str, Path],
    *,
    replace=os.replace,
) -> MaterializedShallowResult:
    """Reconstruct one conventional Plate from its canonical pixels and labels."""
    destination = Path(destination)
    if destination.exists():
        raise PixelIdentityError(
            f"Shallow materialization destination already exists: {destination}"
        )
    collection_root = resolve_managed_source_path(reference, storage_roots)
    manifest_path = collection_root / SHALLOW_COLLECTION_MANIFEST
    try:
        manifest = ShallowManifest.from_dict(json.loads(
            manifest_path.read_text(encoding="utf-8")
        ))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise PixelIdentityError(
            f"Invalid shallow collection manifest: {manifest_path}"
        ) from exc
    try:
        expected_reference = ShallowPlateReference.from_manifest(
            manifest,
            storage_root=reference.storage_root,
            relative_path=reference.relative_path,
        )
    except ValueError as exc:
        raise PixelIdentityError(
            "Shallow Plate collection has inconsistent canonical sources"
        ) from exc
    if expected_reference != reference:
        raise PixelIdentityError(
            "Shallow Plate reference no longer matches its collection manifest"
        )

    first_source = manifest.bindings.images[0].source
    canonical_root = resolve_managed_source_path(first_source, storage_roots)
    canonical_image_directories = {
        _node_directory(
            canonical_root, manifest.image_binding(image.node_id).source.node_path
        )
        for image in manifest.collection.images
    }
    for directory in canonical_image_directories:
        if not directory.is_dir():
            raise PixelIdentityError(
                f"Shallow Plate source image node is unavailable: {directory}"
            )

    token = uuid4().hex
    staging = destination.with_name(
        f".{destination.name}.biomero-materialize-{token}"
    )
    def ignore(directory, names):
        current = Path(directory)
        ignored = {".biomero-canonical.json"}.intersection(names)
        if current in canonical_image_directories and "labels" in names:
            ignored.add("labels")
        return ignored

    managed_labels = []
    expected_label_paths = set()
    try:
        shutil.copytree(canonical_root, staging, symlinks=True, ignore=ignore)
        for image in manifest.collection.images:
            components = tuple(
                binding.component
                for binding in manifest.label_bindings_for_image(image.node_id)
            )

            labels_root = _node_directory(
                staging,
                _join_node_path(image.node_path, "labels"),
            )
            labels_root.mkdir()
            _write_json(labels_root / ".zgroup", {"zarr_format": 2})
            label_names = []
            prefix = PurePosixPath(
                _join_node_path(image.node_path, "labels")
            )
            for component in sorted(
                components, key=lambda item: item.logical_node_path
            ):
                logical = PurePosixPath(component.logical_node_path)
                try:
                    relative = logical.relative_to(prefix)
                except ValueError as exc:
                    raise PixelIdentityError(
                        "Plate label paths must be nested below their image labels/"
                    ) from exc
                if len(relative.parts) != 1:
                    raise PixelIdentityError(
                        "Plate labels must have one name below the image labels/ group"
                    )
                label_names.append(relative.name)
                expected_label_paths.add(component.logical_node_path)
                if component.source is None:
                    physical_root = collection_root
                    physical_node = component.logical_node_path
                    managed_source = ManagedZarrNode(
                        storage_root=reference.storage_root,
                        relative_path=reference.relative_path,
                        node_path=component.logical_node_path,
                    )
                else:
                    physical_root = resolve_managed_source_path(
                        component.source,
                        storage_roots,
                    )
                    physical_node = component.source.node_path
                    managed_source = component.source
                physical_path = _node_directory(physical_root, physical_node)
                if not physical_path.is_dir():
                    raise PixelIdentityError(
                        f"Managed shallow Plate label is unavailable: {physical_path}"
                    )
                target = _node_directory(staging, component.logical_node_path)
                shutil.copytree(physical_path, target, symlinks=True, copy_function=_copy2_bounded)
                managed_labels.append(component.model_copy(update={
                    "source": managed_source,
                }))
            _write_json(labels_root / ".zattrs", {"labels": label_names})

        discovered_label_paths = {
            node.node_path for node in discover_ngff_nodes(staging)
            if node.role == "label"
        }
        if discovered_label_paths != expected_label_paths:
            raise PixelIdentityError(
                "Materialized Plate label inventory differs from shallow collection"
            )
        replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    return MaterializedShallowResult(
        destination=destination,
        manifest=manifest,
        labels=tuple(managed_labels),
    )


def _discover_labels(root: Path, image_node_path: str) -> list[NgffNode]:
    image_node = _node_directory(root, image_node_path)
    labels_group = image_node / "labels"
    if not labels_group.is_dir():
        return []
    labels_attrs = _read_attrs(labels_group)
    labels = labels_attrs.get("labels")
    if not isinstance(labels, list):
        raise PixelIdentityError(
            f"NGFF labels metadata has no labels list: {labels_group}"
        )

    discovered = []
    seen = set()
    for label in labels:
        if not isinstance(label, str):
            raise PixelIdentityError("NGFF label names must be strings")
        label = _safe_node_path(label)
        label_node_path = _join_node_path(image_node_path, "labels", label)
        if label_node_path in seen:
            raise PixelIdentityError(
                f"Duplicate NGFF label node: {label_node_path}"
            )
        label_attrs = _read_attrs(_node_directory(root, label_node_path))
        if "multiscales" not in label_attrs:
            raise PixelIdentityError(
                f"NGFF label node has no multiscales metadata: {label_node_path}"
            )
        discovered.append(NgffNode(
            node_path=label_node_path,
            role="label",
            parent_image_node_path=image_node_path,
        ))
        seen.add(label_node_path)
    return discovered


def discover_ngff_nodes(zarr_root: str | Path) -> tuple[NgffNode, ...]:
    """Discover NGFF 0.4 image-level nodes by declared image/plate metadata."""
    root = Path(zarr_root)
    attrs = _read_attrs(root)
    image_paths: list[str] = []

    if "multiscales" in attrs:
        image_paths.append(".")
    elif "plate" in attrs:
        plate = attrs["plate"]
        wells = plate.get("wells") if isinstance(plate, dict) else None
        if not isinstance(wells, list):
            raise PixelIdentityError("NGFF plate metadata has no wells list")
        for well in wells:
            well_path = well.get("path") if isinstance(well, dict) else None
            if not isinstance(well_path, str):
                raise PixelIdentityError("NGFF plate well path is missing")
            well_path = _safe_node_path(well_path)
            well_attrs = _read_attrs(_node_directory(root, well_path))
            well_metadata = well_attrs.get("well")
            images = (
                well_metadata.get("images")
                if isinstance(well_metadata, dict)
                else None
            )
            if not isinstance(images, list):
                raise PixelIdentityError(
                    f"NGFF well metadata has no images list: {well_path}"
                )
            for image in images:
                image_path = image.get("path") if isinstance(image, dict) else None
                if not isinstance(image_path, str):
                    raise PixelIdentityError(
                        f"NGFF well image path is missing: {well_path}"
                    )
                image_paths.append(_join_node_path(
                    well_path,
                    _safe_node_path(image_path),
                ))
    else:
        raise PixelIdentityError(
            "Returned Zarr root is neither an NGFF image nor an NGFF plate"
        )

    nodes: list[NgffNode] = []
    seen_images = set()
    for image_path in image_paths:
        if image_path in seen_images:
            raise PixelIdentityError(f"Duplicate NGFF image node: {image_path}")
        image_attrs = _read_attrs(_node_directory(root, image_path))
        if "multiscales" not in image_attrs:
            raise PixelIdentityError(
                f"NGFF image node has no multiscales metadata: {image_path}"
            )
        nodes.append(NgffNode(node_path=image_path, role="image"))
        nodes.extend(_discover_labels(root, image_path))
        seen_images.add(image_path)
    return tuple(nodes)


def find_returned_zarr_stores(results_path: str | Path) -> tuple[Path, ...]:
    """Find outermost returned ``*.zarr`` stores and prune their internals."""
    base = Path(results_path)
    stores = []
    for current, dirs, _files in os.walk(base):
        zarr_dirs = sorted(name for name in dirs if name.lower().endswith(".zarr"))
        stores.extend(Path(current) / name for name in zarr_dirs)
        dirs[:] = [name for name in dirs
                   if not name.lower().endswith(".zarr")
                   and ".biomero-prune-" not in name]
    return tuple(stores)


def _identity_for_node(
    root: Path,
    node: NgffNode,
    identity_provider: IsccBioIdentityProvider,
) -> PixelIdentity:
    guard = read_zarr_v2_semantic_guard(root, node.node_path)
    return identity_provider.generate(
        root,
        node_path=node.node_path,
        role=node.role,
        shape=guard.shape,
        dtype=guard.dtype,
        axes=guard.axes,
        coordinate_transformations=guard.coordinate_transformations,
    )


def _identities_for_nodes(
    root: Path,
    nodes: tuple[NgffNode, ...],
    identity_provider: IsccBioIdentityProvider,
    *,
    max_workers: int = 1,
) -> tuple[PixelIdentity, ...]:
    """Generate identities in node order with optional bounded concurrency."""
    if isinstance(max_workers, bool) or not isinstance(max_workers, int):
        raise ValueError("Identity workers must be a positive integer")
    if max_workers < 1:
        raise ValueError("Identity workers must be a positive integer")
    generate = partial(_identity_for_node, root, identity_provider=identity_provider)
    if max_workers == 1 or len(nodes) < 2:
        return tuple(generate(node) for node in nodes)
    with ThreadPoolExecutor(
        max_workers=min(max_workers, len(nodes)),
        thread_name_prefix="biomero-iscc",
    ) as executor:
        # executor.map preserves the discovered node order even when workers
        # finish out of order, keeping manifests and comparisons deterministic.
        return tuple(executor.map(generate, nodes))


def _declared_image_dataset_directories(
    root: Path,
    image_node_path: str,
) -> tuple[Path, ...]:
    image_node = _node_directory(root, image_node_path)
    attrs = _read_attrs(image_node)
    multiscales = attrs.get("multiscales")
    if not isinstance(multiscales, list) or not multiscales:
        raise PixelIdentityError(
            f"NGFF image node has no multiscales metadata: {image_node_path}"
        )
    directories = []
    for multiscale in multiscales:
        datasets = (
            multiscale.get("datasets")
            if isinstance(multiscale, dict)
            else None
        )
        if not isinstance(datasets, list) or not datasets:
            raise PixelIdentityError(
                f"NGFF multiscales has no datasets: {image_node_path}"
            )
        for dataset in datasets:
            dataset_path = (
                dataset.get("path") if isinstance(dataset, dict) else None
            )
            if not isinstance(dataset_path, str):
                raise PixelIdentityError(
                    f"NGFF dataset path is missing: {image_node_path}"
                )
            dataset_path = _safe_node_path(dataset_path)
            directory = _node_directory(
                root,
                _join_node_path(image_node_path, dataset_path),
            )
            try:
                directory.relative_to(root)
            except ValueError as exc:
                raise PixelIdentityError(
                    f"NGFF dataset escapes its store: {dataset_path}"
                ) from exc
            directories.append(directory)
    return tuple(dict.fromkeys(directories))


def _tree_size(root: Path) -> int:
    return sum(
        path.stat().st_size
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def normalize_returned_zarr(
    decision: ReturnedZarrDecision,
    workflow_id: UUID | str,
    *,
    replace=os.replace,
    measure_bytes: bool = False,
    before_commit=None,
) -> NormalizedShallowResult:
    """Transactionally omit verified duplicate arrays from a result store.

    Duplicate image arrays are atomically moved into a sibling rollback
    journal.  Labels and metadata stay in place, avoiding a costly copy of the
    retained side of a large Plate.  The manifest is committed only after all
    moves and metadata updates validate.  Any pre-commit failure restores the
    original attributes and moves every array back.  The canonical source is
    never modified.

    Exact byte measurement is disabled by default because recursively stating
    every file in a Plate can dominate the complete transaction on a mounted
    filesystem.  ``measure_bytes`` is intended for diagnostics and benchmarks,
    not the interactive import path.
    """
    if not decision.eligible or len(decision.matched_inputs) != 1:
        raise PixelIdentityError("Returned Zarr is not eligible for shallowing")
    root = decision.store_path
    if not root.is_dir():
        raise PixelIdentityError(f"Returned Zarr does not exist: {root}")
    nodes = discover_ngff_nodes(root)
    image_nodes = tuple(node for node in nodes if node.role == "image")
    label_nodes = tuple(node for node in nodes if node.role == "label")
    if not image_nodes:
        raise PixelIdentityError(
            "Returned stores require image nodes"
        )
    returned_by_path = {
        identity.node_path: identity
        for identity in decision.image_identities
    }
    if set(returned_by_path) != {node.node_path for node in image_nodes}:
        raise PixelIdentityError(
            "Returned identities no longer describe the discovered image nodes"
        )
    matched_input = decision.matched_inputs[0]
    if matched_input.plate_source is not None:
        input_sources = {
            image.image_node_path: image.source
            for image in matched_input.plate_source.images
        }
        interchange_profile = matched_input.plate_source.interchange_profile
    elif matched_input.source is not None:
        input_sources = {matched_input.source.node_path: matched_input.source}
        interchange_profile = matched_input.source.interchange_profile
    else:
        raise PixelIdentityError("Matched input has no canonical source")
    if set(input_sources) != set(returned_by_path):
        raise PixelIdentityError(
            "Matched input no longer describes every returned image node"
        )

    components_by_image = {node.node_path: [] for node in image_nodes}
    for component in decision.label_components:
        matches = [
            node.node_path for node in image_nodes
            if PurePosixPath(component.logical_node_path).is_relative_to(
                PurePosixPath(_join_node_path(node.node_path, "labels"))
            )
        ]
        if len(matches) != 1:
            raise PixelIdentityError(
                f"Label has no unique parent image: {component.logical_node_path}"
            )
        components_by_image[matches[0]].append(component)

    image_graph_nodes = tuple(
        ShallowImageNode(
            id=f"image-{index}",
            name=image_node.node_path,
            node_path=image_node.node_path,
        )
        for index, image_node in enumerate(image_nodes)
    )
    image_ids = {
        image.node_path: image.node_id for image in image_graph_nodes
    }
    label_records = tuple(
        (f"label-{index}", image_path, component)
        for index, (image_path, component) in enumerate(
            (image_node.node_path, component)
            for image_node in image_nodes
            for component in components_by_image[image_node.node_path]
        )
    )
    manifest = ShallowManifest(
        workflow_id=UUID(str(workflow_id)),
        transfer_artifact=root.name,
        interchange_profile=interchange_profile,
        collection=ShallowCollection(
            name=root.name,
            images=image_graph_nodes,
            labels=tuple(
                ShallowLabelNode(
                    id=label_id,
                    name=component.logical_node_path,
                    node_path=component.logical_node_path,
                    source_image_id=image_ids[image_path],
                )
                for label_id, image_path, component in label_records
            ),
        ),
        bindings=ShallowBindings(
            images=tuple(
                ShallowImageBinding(
                    node_id=image_ids[image_node.node_path],
                    source=input_sources[image_node.node_path],
                    returned_pixel_identity=(
                        returned_by_path[image_node.node_path]
                    ),
                )
                for image_node in image_nodes
            ),
            labels=tuple(
                ShallowLabelBinding(
                    node_id=label_id,
                    component=component,
                )
                for label_id, _image_path, component in label_records
            ),
        ),
    )
    omitted = {
        directory
        for image_node in image_nodes
        for directory in _declared_image_dataset_directories(
            root,
            image_node.node_path,
        )
    }
    inherited_label_paths = {
        component.logical_node_path
        for component in decision.label_components
        if component.source is not None
    }
    omitted.update(
        _node_directory(root, label_path)
        for label_path in inherited_label_paths
    )
    # Moving whole Zarr array directories on one filesystem is metadata-only.
    # Keep only top-level omitted directories so a future nested declaration
    # cannot cause the same subtree to be moved twice.
    minimal_omitted = []
    for directory in sorted(
        omitted,
        key=lambda path: len(path.relative_to(root).parts),
    ):
        if not any(
            directory.is_relative_to(parent)
            for parent in minimal_omitted
        ):
            minimal_omitted.append(directory)

    token = uuid4().hex
    rollback = root.with_name(f".{root.name}.biomero-prune-{token}")
    bytes_before = _tree_size(root) if measure_bytes else None
    manifest_path = root / SHALLOW_COLLECTION_MANIFEST
    if manifest_path.exists():
        raise PixelIdentityError(
            f"Returned store already has {SHALLOW_COLLECTION_MANIFEST}"
        )

    from .transaction import begin, recover, write_json, sync_directory
    moved_directories = []
    original_attrs = {
        _node_directory(root, node.node_path) / ".zattrs":
        (_node_directory(root, node.node_path) / ".zattrs").read_bytes()
        for node in image_nodes
    }
    try:
        rollback.mkdir()
        journal = begin(root, rollback, minimal_omitted, original_attrs)
        sync_directory(root.parent)
        for directory in minimal_omitted:
            if not directory.is_dir():
                raise PixelIdentityError(
                    f"Returned array disappeared before normalization: "
                    f"{directory}"
                )
            target = rollback / directory.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            replace(directory, target)
            moved_directories.append((directory, target))
            sync_directory(directory.parent)
            sync_directory(target.parent)

        for image_node in image_nodes:
            staging_attrs_path = _node_directory(
                root,
                image_node.node_path,
            ) / ".zattrs"
            original_attrs[staging_attrs_path] = staging_attrs_path.read_bytes()
            staging_attrs = _read_attrs(staging_attrs_path.parent)
            staging_attrs.pop("multiscales", None)
            staging_attrs["biomero"] = {
                "format": manifest.format,
                "manifest": SHALLOW_COLLECTION_MANIFEST,
                "workflowId": str(manifest.workflow_id),
            }
            _write_json(staging_attrs_path, staging_attrs)
        _write_json(
            manifest_path,
            manifest.to_dict(),
        )

        validated = ShallowManifest.from_dict(json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        ))
        if validated != manifest:
            raise PixelIdentityError("Shallow manifest changed")
        for label in label_nodes:
            label_dir = _node_directory(root, label.node_path)
            if label.node_path in inherited_label_paths:
                if label_dir.exists():
                    raise PixelIdentityError(
                        f"Staged shallow result retained inherited label "
                        f"{label.node_path}"
                    )
            elif not label_dir.is_dir():
                raise PixelIdentityError(
                    f"Staged shallow result lost label node {label.node_path}"
                )
        for dataset in omitted:
            if dataset.exists():
                raise PixelIdentityError(
                    f"Shallow result retained image dataset {dataset}"
                )
        bytes_after = _tree_size(root) if measure_bytes else None
        if before_commit is not None:
            before_commit(manifest)
        journal["committed"] = True
        write_json(rollback / "journal.json", journal)
    except Exception:
        # Restore metadata before the arrays so readers never see valid
        # multiscales pointing at only a partially restored pyramid.
        recover(root)
        raise

    # Validation is the commit boundary. Cleanup only unlinks verified
    # duplicate pixels, so it must not attempt a rollback after a partial
    # filesystem deletion.
    shutil.rmtree(rollback)
    return NormalizedShallowResult(
        store_path=root,
        manifest=manifest,
        bytes_before=bytes_before,
        bytes_after=bytes_after,
    )


def evaluate_returned_zarr(
    zarr_root: str | Path,
    canonical_inputs: CanonicalInputManifest | None,
    *,
    identity_provider: IsccBioIdentityProvider | None = None,
    identity_workers: int = 1,
) -> ReturnedZarrDecision:
    """Compare one returned image store with its workflow-scoped inputs.

    The function only reports eligibility.  It never changes the returned
    store, which makes failures and unsupported cases unconditionally fail
    open to ``keep-full``.
    """
    if (
        isinstance(identity_workers, bool)
        or not isinstance(identity_workers, int)
        or identity_workers < 1
    ):
        raise ValueError("Identity workers must be a positive integer")
    root = Path(zarr_root)
    if canonical_inputs is None or not canonical_inputs.inputs:
        return ReturnedZarrDecision(
            store_path=root,
            outcome="keep-full",
            reason="no-canonical-input-snapshot",
        )

    marker_path = root / TRANSFER_INPUT_MARKER
    marked_input = None
    if marker_path.is_file():
        try:
            marked_input = CanonicalInput.from_dict(json.loads(
                marker_path.read_text(encoding="utf-8")
            ))
        except (OSError, json.JSONDecodeError, ValueError):
            return ReturnedZarrDecision(
                store_path=root,
                outcome="keep-full",
                reason="invalid-transfer-input-marker",
            )
        if marked_input not in canonical_inputs.inputs:
            return ReturnedZarrDecision(
                store_path=root,
                outcome="keep-full",
                reason="untrusted-transfer-input-marker",
            )

    try:
        nodes = discover_ngff_nodes(root)
    except PixelIdentityError as exc:
        return ReturnedZarrDecision(
            store_path=root,
            outcome="keep-full",
            reason=f"unsupported-ngff: {exc}",
        )

    image_nodes = tuple(node for node in nodes if node.role == "image")
    label_paths = tuple(node.node_path for node in nodes if node.role == "label")
    if not image_nodes:
        return ReturnedZarrDecision(
            store_path=root,
            outcome="keep-full",
            reason="no-image-nodes",
            label_node_paths=label_paths,
        )
    provider = identity_provider or IsccBioIdentityProvider()
    try:
        returned_identities = _identities_for_nodes(
            root,
            image_nodes,
            provider,
            max_workers=identity_workers,
        )
    except PixelIdentityError as exc:
        return ReturnedZarrDecision(
            store_path=root,
            outcome="keep-full",
            reason=f"identity-unavailable: {exc}",
            label_node_paths=label_paths,
        )

    def sources_for(item: CanonicalInput):
        if item.plate_source is not None:
            return {
                image.image_node_path: image.source
                for image in item.plate_source.images
            }
        if item.source is not None:
            return {item.source.node_path: item.source}
        return {}

    returned_by_path = {
        identity.node_path: identity for identity in returned_identities
    }
    unchanged_reason = (
        "input-image-unchanged"
        if len(returned_identities) == 1
        else "input-plate-unchanged"
    )

    def input_matches(item: CanonicalInput) -> bool:
        sources = sources_for(item)
        return set(sources) == set(returned_by_path) and all(
            pixel_identities_match(
                returned_by_path[node_path],
                source.pixel_identity,
            )
            for node_path, source in sources.items()
        )

    if marked_input is not None:
        matches = (marked_input,)
        reason = (
            unchanged_reason
            if input_matches(matches[0])
            else "pixels-changed"
        )
    else:
        artifact_matches = tuple(
            item for item in canonical_inputs.inputs
            if item.transfer_artifact == root.name
        )
        if len(artifact_matches) > 1:
            reason = "ambiguous-transfer-artifact"
            matches = ()
        elif len(artifact_matches) == 1:
            matches = artifact_matches
            reason = (
                unchanged_reason
                if input_matches(matches[0])
                else "pixels-changed"
            )
        else:
            matches = tuple(
                item for item in canonical_inputs.inputs
                if input_matches(item)
            )
            if len(matches) == 1:
                reason = unchanged_reason
            elif len(matches) > 1:
                reason = "ambiguous-input-identity"
                matches = ()
            else:
                reason = "no-input-identity-match"

    unchanged = reason == unchanged_reason
    # Identity controls pixel storage, never whether the returned object is
    # a result. Label-free results can reference canonical pixels as well.
    if not unchanged:
        return ReturnedZarrDecision(
            store_path=root,
            outcome="keep-full",
            reason=reason,
            image_identities=returned_identities,
            label_node_paths=label_paths,
        )

    try:
        label_identities = _identities_for_nodes(
            root,
            tuple(node for node in nodes if node.role == "label"),
            provider,
            max_workers=identity_workers,
        )
    except PixelIdentityError as exc:
        return ReturnedZarrDecision(
            store_path=root,
            outcome="keep-full",
            reason=f"label-identity-unavailable: {exc}",
            image_identities=returned_identities,
            label_node_paths=label_paths,
        )

    if matches[0].plate_source is not None:
        input_labels = {
            label.logical_node_path: label
            for image in matches[0].plate_source.images
            for label in image.labels
        }
    else:
        input_labels = {
            label.logical_node_path: label
            for label in matches[0].labels
        }
    label_components = []
    for identity in label_identities:
        inherited = input_labels.get(identity.node_path)
        source = None
        if inherited is not None and pixel_identities_match(
            identity,
            inherited.pixel_identity,
        ):
            source = inherited.source
        label_components.append(ZarrLabelComponent(
            logical_node_path=identity.node_path,
            pixel_identity=identity,
            source=source,
        ))

    return ReturnedZarrDecision(
        store_path=root,
        outcome="eligible",
        reason=reason,
        image_identities=returned_identities,
        label_identities=label_identities,
        label_components=tuple(label_components),
        label_node_paths=label_paths,
        matched_inputs=matches,
    )


def remove_transfer_input_marker(zarr_root: str | Path) -> bool:
    """Remove the temporary input binding before managed result storage."""
    marker = Path(zarr_root) / TRANSFER_INPUT_MARKER
    try:
        marker.unlink()
    except FileNotFoundError:
        return False
    return True


__all__ = [
    "NgffNode",
    "MaterializedShallowResult",
    "NormalizedShallowResult",
    "ReturnedZarrDecision",
    "ShallowRegistration",
    "discover_ngff_nodes",
    "evaluate_returned_zarr",
    "find_returned_zarr_stores",
    "load_managed_storage_roots",
    "materialize_shallow_zarr",
    "normalize_returned_zarr",
    "remove_transfer_input_marker",
    "resolve_managed_source_path",
    "resolve_shallow_registration",
]
