"""
TermBin factory for creating TermBin objects from biometry measurements.

Handles mapping of measurement names to HPO terms and percentile ranges.
"""

import logging
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Set

from prenatalppkt.data_files import MAPPINGS_DIR
from prenatalppkt.etl.measurement_registry import REGISTRY
from prenatalppkt.gestational_age import GestationalAge
from prenatalppkt.mapping_loader import BiometryMappingLoader
from prenatalppkt.measurements.term_bin import TermBin

logger = logging.getLogger(__name__)

# Enable debug logging by default
logging.basicConfig(level=logging.DEBUG)

# Required measurements that MUST be present in biometry data
REQUIRED_MEASUREMENTS: Set[str] = {
    name for name, spec in REGISTRY.items() if spec.role == "required"
}

# Optional measurements (may or may not be present)
OPTIONAL_MEASUREMENTS: Set[str] = {
    name for name, spec in REGISTRY.items() if spec.role == "optional"
}

# Measurements deliberately excluded from _NAME_TO_YAML - not "not mapped
# yet" but "no real mapping is possible", each with its own reason (the
# registry's unmapped_reason). An optional measurement with no YAML mapping
# and no reason is a gap the completeness tests catch. Add a reason only
# after a real hp.json/LOINC search comes up empty, not on a guess.
DELIBERATELY_UNMAPPED_MEASUREMENTS: Set[str] = {
    name for name, spec in REGISTRY.items() if spec.unmapped_reason is not None
}

# Default path to YAML mappings file
DEFAULT_MAPPINGS_PATH = MAPPINGS_DIR / "biometry_hpo_mappings.yaml"

# TODO(@VarenyaJ): Observer exports no calculated percentile for OFD, NT,
# Nuchal Fold, Cerebellum, Cisterna Magna, Nasal Bone, the lateral
# ventricles, Biorbit or Mean Gest Sac, and the Observer extractor skips
# them, so their bins only apply to sources that report a percentile
# (ViewPoint does for some). An absolute-value fallback (e.g.
# nuchal_translucency's 3.5mm note) would let Observer exams use them too.


class TermBinFactory:
    """
    Factory for creating TermBin objects from biometry measurements.

    Maps measurement names to appropriate HPO terms based on percentile ranges.
    """

    # Map ETL short names to YAML keys
    _NAME_TO_YAML: ClassVar[Dict[str, str]] = {
        name: spec.yaml_key
        for name, spec in REGISTRY.items()
        if spec.yaml_key is not None
    }

    def __init__(self, mappings_path: Optional[Path] = None) -> None:
        """
        Initialize factory with YAML mappings.

        Args:
            mappings_path: Path to YAML file. Defaults to bundled config.
        """
        path = mappings_path or DEFAULT_MAPPINGS_PATH
        self._mappings: Dict[str, List[TermBin]] = BiometryMappingLoader.load(path)
        logger.debug("Loaded mappings for: %s", list(self._mappings.keys()))

    def create_term_bin(
        self,
        name: str,
        value_mm: float,
        percentile: float,
        gestational_age: Optional[GestationalAge] = None,
        method: Optional[str] = None,
        fetus_number: Optional[int] = None,
    ) -> Optional[TermBin]:
        """
        Create a TermBin from measurement data.

        Args:
            name: Measurement name (e.g., "HC", "BPD")
            value_mm: Measurement value in millimeters
            percentile: Percentile value (0-100 scale)
            gestational_age: Optional gestational age
            method: Optional measurement method (e.g., "Hadlock")
            fetus_number: Optional fetus identifier

        Returns:
            TermBin object or None if measurement cannot be mapped

        Raises:
            ValueError: If percentile is out of valid range or required measurement lacks HPO mapping
        """
        logger.debug(
            f"Creating TermBin: name={name}, value={value_mm}mm, "
            f"percentile={percentile}%, ga={gestational_age}, method={method}"
        )

        # Validate percentile range
        if percentile < 0 or percentile > 100:
            logger.error(f"Invalid percentile for {name}: {percentile}")
            raise ValueError(f"Percentile must be 0-100, got {percentile}")

        # Map short name to YAML key
        yaml_key = self._NAME_TO_YAML.get(name)

        if not yaml_key:
            if name in OPTIONAL_MEASUREMENTS:
                logger.warning(
                    f"No HPO mapping for optional measurement '{name}' - skipping. "
                    f"TODO(@VarenyaJ): Add HPO terms when available"
                )
                return None
            logger.error(f"No HPO mapping for REQUIRED measurement: {name}")
            raise ValueError(f"Missing HPO mapping for required measurement: {name}")

        # Get bins for this measurement type
        bins = self._mappings.get(yaml_key)
        if not bins:
            logger.error(f"No bins found for {yaml_key}")
            raise ValueError(f"No mapping bins for {yaml_key}")

        # Find matching bin using TermBin.fits()
        matching_bin: Optional[TermBin] = None
        for bin in bins:
            if bin.fits(percentile):
                matching_bin = bin
                break
        if not matching_bin:
            logger.error(f"No bin matches percentile {percentile} for {name}")
            raise ValueError(f"No bin matches percentile {percentile} for {name}")

        logger.debug(f"Selected HPO: {matching_bin.hpo_id} - {matching_bin.hpo_label}")

        # Build description
        description = self._build_description(
            name, value_mm, percentile, gestational_age, method, fetus_number
        )

        ga_weeks_float: Optional[float] = None
        if gestational_age is not None:
            ga_weeks_float = gestational_age.weeks + gestational_age.days / 7

        # Create new TermBin with runtime description
        term_bin = TermBin(
            range=matching_bin.range,
            hpo_id=matching_bin.hpo_id,
            hpo_label=matching_bin.hpo_label,
            normal=matching_bin.normal,
            description=description,
            loinc_code=matching_bin.loinc_code,
            loinc_label=matching_bin.loinc_label,
            value_mm=value_mm,
            gestational_age_weeks=ga_weeks_float,
        )

        logger.debug(
            f"Created TermBin: {matching_bin.hpo_id} - normal={matching_bin.normal}"
        )
        return term_bin

    def _build_description(
        self,
        name: str,
        value_mm: float,
        percentile: float,
        gestational_age: Optional[GestationalAge],
        method: Optional[str],
        fetus_number: Optional[int],
    ) -> str:
        """
        Build human-readable description for TermBin.

        Format: "NAME: value mm (percentile%) at GAw GAd (method) [Fetus N]"
        """
        parts = [f"{name}: {value_mm:.1f} mm ({percentile:.1f}%)"]

        if gestational_age:
            parts.append(f"at {gestational_age.weeks}w{gestational_age.days}d")

        if method:
            parts.append(f"({method})")

        if fetus_number:
            parts.append(f"[Fetus {fetus_number}]")

        return " ".join(parts)


def validate_required_measurements(term_bins: List[TermBin]) -> None:
    """
    Validate that all required measurements are present.

    Args:
        term_bins: List of created TermBins

    Raises:
        ValueError: If any required measurement is missing
    """
    logger.debug(f"Validating {len(term_bins)} TermBins for required measurements")

    present_measurements = set()
    for tb in term_bins:
        # Description format begins with "NAME: ...", e.g., "HC: 250.0 mm ..."
        name = tb.description.split(":")[0].strip()
        present_measurements.add(name)
        logger.debug(f"Found measurement: {name}")

    logger.debug(f"Present: {present_measurements}")
    logger.debug(f"Required: {REQUIRED_MEASUREMENTS}")

    missing = REQUIRED_MEASUREMENTS - present_measurements

    if missing:
        error_msg = (
            f"Missing required biometry measurements: {', '.join(sorted(missing))}. "
            f"Required measurements are: {', '.join(sorted(REQUIRED_MEASUREMENTS))}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("All required measurements present")
