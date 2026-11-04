"""
measurement_eval.py - Factory for creating measurement evaluators
"""

from pathlib import Path
from typing import Optional, Dict, List
import logging

from prenatalppkt.sonographic_measurement import SonographicMeasurement
from prenatalppkt.data_files import MAPPINGS_DIR
from prenatalppkt.mapping_loader import BiometryMappingLoader

logger = logging.getLogger(__name__)

DEFAULT_MAPPINGS_FILE = MAPPINGS_DIR / "biometry_hpo_mappings.yaml"


class MeasurementEvaluation:
    """
    Factory for creating measurement evaluators.

    Example:
        >>> evaluator = MeasurementEvaluation()
        >>> hc_mapper = evaluator.get_measurement_mapper("head_circumference")
    """

    def __init__(self, mappings_path: Optional[Path] = None) -> None:
        """
        Initialize the factory.

        Args:
            mappings_path: Path to YAML mappings file
        """
        if mappings_path is None:
            mappings_path = DEFAULT_MAPPINGS_FILE

        logger.info("Loading HPO mappings from %s", mappings_path)
        mappings = BiometryMappingLoader.load(mappings_path)

        self._measurements: Dict[str, SonographicMeasurement] = {}

        for measurement_type, bins in mappings.items():
            self._measurements[measurement_type] = SonographicMeasurement(
                measurement_type=measurement_type, term_bins=bins
            )
            logger.info("Initialized mapper for %s", measurement_type)

    def get_measurement_mapper(
        self, measurement_type: str
    ) -> Optional[SonographicMeasurement]:
        """
        Retrieve a measurement mapper by type.

        Args:
            measurement_type: e.g., "head_circumference"

        Returns:
            Configured SonographicMeasurement or None
        """
        return self._measurements.get(measurement_type)

    def get_available_measurements(self) -> List[str]:
        """Return list of available measurement types."""
        return list(self._measurements.keys())
