"""
The mapping YAMLs ship inside the package, so a normal (non-editable)
install finds them.
"""

from pathlib import Path

import prenatalppkt
from prenatalppkt.etl.measurement_registry import DEFAULT_REGISTRY_PATH
from prenatalppkt.etl.term_bin_factory import DEFAULT_MAPPINGS_PATH
from prenatalppkt.measurement_eval import DEFAULT_MAPPINGS_FILE
from prenatalppkt.phenotypic_export import PhenotypicExporter

PACKAGE_DIR = Path(prenatalppkt.__file__).resolve().parent


def test_default_mapping_paths_are_inside_the_package():
    exporter_path = PhenotypicExporter()._mappings_path
    for path in (
        DEFAULT_REGISTRY_PATH,
        DEFAULT_MAPPINGS_PATH,
        DEFAULT_MAPPINGS_FILE,
        exporter_path,
    ):
        assert path.resolve().is_relative_to(PACKAGE_DIR), path
        assert path.is_file(), path
