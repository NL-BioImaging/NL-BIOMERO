# Vendored OMERO.web plugins

## BIOMERO OME-Zarr Viewer

`biomero_zarr_viewer-0.1.10-py3-none-any.whl` and its corresponding
`biomero_zarr_viewer-0.1.10-source.tar.gz` source archive were built from
[`NL-BioImaging/BIOMERO.ZarrViewer`](https://github.com/NL-BioImaging/BIOMERO.ZarrViewer)
at commit `68be0b01fa9584e20fd10b98ea2d5ef822ccb4e6`.

SHA-256 checksums:

```text
3eb0dc11a860337ef617a28d721bb658bf6fb21e4b1ca713518e14473c0d752e  biomero_zarr_viewer-0.1.10-py3-none-any.whl
e08f1c28184d2d78b32d17d7bdcbbadfaae0150232e0bda0611bc6570e30b4a2  biomero_zarr_viewer-0.1.10-source.tar.gz
```

The wheel and source archive were produced and checked with:

```bash
python scripts/build_frontend.py --skip-install
python -m build --wheel
python scripts/verify_wheel.py dist/biomero_zarr_viewer-0.1.10-py3-none-any.whl
git archive --format=tar.gz --prefix=BIOMERO.ZarrViewer-0.1.10/ \
  --output=biomero_zarr_viewer-0.1.10-source.tar.gz HEAD
```

When updating the viewer, replace both archives, update the wheel's exact
filename in `web/Dockerfile`, and record the new source commit and checksums
here.
