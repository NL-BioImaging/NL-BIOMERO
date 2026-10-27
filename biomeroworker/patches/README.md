# Bundled compatibility sources

`slurm_client.py` derives from NL-BioImaging/biomero 2.9.0b11 and
`result_zarr.py` from NL-BioImaging/biomero-shallower 0.1.0b5.
Both are distributed under Apache-2.0; see LICENSE-APACHE-2.0.txt.
Their original upstream authors retain their copyrights.

Local modifications add quoted recursive Zarr extraction, post-extraction input
validation, and bounded streaming copies that preserve file metadata. The
optional Dockerfile only applies these sources to the matching package versions.

Sources:
https://github.com/NL-BioImaging/biomero/tree/v2.9.0-beta.11
https://pypi.org/project/biomero-shallower/0.1.0b5/
