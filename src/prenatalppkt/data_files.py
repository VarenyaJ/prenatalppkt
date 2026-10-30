"""
Locations of the data files that ship inside the package.
"""

from importlib.resources import files
from pathlib import Path

MAPPINGS_DIR = Path(str(files("prenatalppkt") / "data" / "mappings"))
