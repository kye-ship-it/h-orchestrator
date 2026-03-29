"""Root conftest: ensure the pipeline package directory is importable."""

import sys
from pathlib import Path

# Add the pipeline directory itself so that `from mapper import ...` works
# when running tests with `python -m pytest` from the pipeline directory.
_pipeline_dir = str(Path(__file__).resolve().parent)
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)
