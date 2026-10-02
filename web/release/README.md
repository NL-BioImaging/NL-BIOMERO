# Analysis release preparation

`analysis_release.py` and `download_analysis_release.py` are vendored unchanged
from `NL-BioImaging/OMERO.Analysis/scripts/`. They intentionally require only
Python's standard library and are run in the Docker release-preparation stage.
Update both copies together; do not add a fallback to PyPI, main, latest, or
source builds. The final web image installs the prepared wheelhouse offline.
