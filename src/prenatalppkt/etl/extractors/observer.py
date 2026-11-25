"""
Observer JSON biometry extractor.

Extracts fetal biometry measurements from Observer ultrasound system JSON exports
and converts them directly to TermBin objects.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from prenatalppkt.etl.constants import OBSERVER_NAME_MAP
from prenatalppkt.etl.scan_type import (
    ScanType,
    T1_LABELS,
    UnsupportedScanTypeError,
    classify_fetus,
)
from prenatalppkt.etl.term_bin_factory import (
    TermBinFactory,
    validate_required_measurements,
)
from prenatalppkt.gestational_age import GestationalAge
from prenatalppkt.measurements.term_bin import TermBin

logger = logging.getLogger(__name__)

# Enable debug logging by default
logging.basicConfig(level=logging.DEBUG)


# Module-level singleton — YAML is parsed once when the module is first imported,
# then reused for every extract() call. Callers can still inject a custom factory
# (e.g. for testing) via the optional factory parameter.
_default_factory = TermBinFactory()


def _validate_structure(data: Any) -> List[Dict[str, Any]]:
    """Raise on top-level structural issues; return the fetuses list."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data)}")
    if "fetuses" not in data:
        raise ValueError("Missing 'fetuses' key in Observer JSON")
    fetuses = data["fetuses"]
    if not fetuses or not isinstance(fetuses, list):
        raise ValueError("'fetuses' must be non-empty list")
    return fetuses


def _validate_fetus_count(fetuses: List[Dict[str, Any]], declared_count: Any) -> None:
    """Warn (do not raise) if exam.fetus_count disagrees with len(fetuses)."""
    actual = len(fetuses)
    if declared_count is not None and declared_count != actual:
        logger.warning(
            "exam.fetus_count=%s but %d fetuses present in array",
            declared_count,
            actual,
        )


def _extract_one_fetus(
    fetus_data: Dict[str, Any], factory: TermBinFactory
) -> List[TermBin]:
    """Extract TermBins from one fetus dict, dispatching on its own scan type.

    Each fetus is classified independently - twin exams mix scan types, so a
    CRL/NT-only fetus yields T1 bins rather than failing the T2/T3 biometry
    requirement.

    A fetus with some but not all of HC/BPD/AC/Femur (a targeted follow-up
    scan re-checking one prior finding, rather than a full anatomy survey)
    still returns whatever measurements are present and mappable - it does
    not raise just because the full set isn't there. Real Observer exports
    include exactly this: a scan re-measuring only BPD/HC to follow up a
    ventriculomegaly finding, or only the limb bones to follow up a
    suspected skeletal dysplasia. Only a fetus with no measurements at all
    still raises.

    Raises:
        UnsupportedScanTypeError: if the fetus has no measurements at all,
            or is classified T1 but no CRL/NT measurement parsed.
    """
    fetus_number = _get_fetus_number(fetus_data)
    scan_type = classify_fetus(fetus_data)
    logger.debug(f"Processing fetus {fetus_number}, scan_type={scan_type.value}")

    if scan_type is ScanType.FIRST_TRIMESTER:
        term_bins = _parse_t1_measurements(fetus_data, fetus_number, factory)
        if not term_bins:
            raise UnsupportedScanTypeError(
                "First-trimester scan classified but no CRL or NT measurement parsed"
            )
        return term_bins

    if not (fetus_data.get("measurements") or []):
        raise UnsupportedScanTypeError("No measurements present for this fetus")

    term_bins = _parse_measurements(fetus_data, fetus_number, factory)
    try:
        validate_required_measurements(term_bins)
    except ValueError as e:
        logger.warning("Fetus %d: %s", fetus_number, e)
    return term_bins


def extract(data: dict, factory: TermBinFactory | None = None) -> list[TermBin]:
    """
    Extract biometry measurements from Observer JSON and convert to TermBins.

    Args:
        data: Parsed Observer JSON dictionary
        factory: TermBinFactory instance (creates new if None)

    Returns:
        List of TermBin objects

    Raises:
        ValueError: If JSON structure is invalid or required measurements missing
    """
    if factory is None:
        factory = _default_factory  # <-- reuse, no reload

    logger.debug("Starting Observer JSON extraction (single-fetus)")
    fetuses = _validate_structure(data)

    if len(fetuses) > 1:
        logger.warning(
            "Observer JSON has %d fetuses; extract() returns only the first. "
            "Use extract_all_fetuses() for multi-fetus support.",
            len(fetuses),
        )

    term_bins = _extract_one_fetus(fetuses[0], factory)
    logger.info(f"Extracted {len(term_bins)} TermBins from Observer JSON")
    return term_bins


def extract_all_fetuses(
    data: dict, factory: TermBinFactory | None = None
) -> Dict[int, List[TermBin]]:
    """
    Extract biometry from every fetus in an Observer JSON.

    Each fetus is classified and extracted independently, so a twin exam whose
    fetuses have different scan types still yields the right bins per fetus
    (a CRL/NT-only twin yields T1 bins, not []). Per-fetus extraction errors
    (e.g. an UNKNOWN fetus with partial biometry) are logged and surface as an
    empty list for that `fetus_number` key, rather than aborting the whole
    extraction. Top-level structural errors still raise.

    Args:
        data: Parsed Observer JSON dictionary
        factory: TermBinFactory instance (uses module singleton if None)

    Returns:
        Dict keyed by `fetus_number`; values are lists of TermBins for that
        fetus (empty list when extraction failed for that fetus).

    Raises:
        ValueError: If the JSON structure itself is malformed (missing
            `fetuses` key, wrong type, empty list).
    """
    if factory is None:
        factory = _default_factory

    logger.debug("Starting Observer JSON extraction (multi-fetus)")
    fetuses = _validate_structure(data)
    _validate_fetus_count(fetuses, data.get("exam", {}).get("fetus_count"))

    result: Dict[int, List[TermBin]] = {}
    for fetus_data in fetuses:
        fetus_number = _get_fetus_number(fetus_data)
        try:
            result[fetus_number] = _extract_one_fetus(fetus_data, factory)
        except ValueError as e:
            logger.warning("Fetus %d skipped: %s", fetus_number, e)
            result[fetus_number] = []

    logger.info(
        "Extracted %d total TermBins across %d fetuses",
        sum(len(tbs) for tbs in result.values()),
        len(result),
    )
    return result


def extract_from_file(filepath: Path, factory: TermBinFactory = None) -> List[TermBin]:
    """
    Extract biometry measurements from Observer JSON file.

    Args:
        filepath: Path to Observer JSON file
        factory: TermBinFactory instance (creates new if None)

    Returns:
        List of TermBin objects
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return extract(data, factory)


def extract_all_fetuses_from_file(
    filepath: Path, factory: TermBinFactory | None = None
) -> Dict[int, List[TermBin]]:
    """Multi-fetus equivalent of `extract_from_file`."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return extract_all_fetuses(data, factory)


def _get_fetus_number(fetus_data: Dict[str, Any]) -> int:
    """Extract fetus number from fetus data."""
    fetus_section = fetus_data.get("fetus", {})
    return fetus_section.get("fetus_number", 1)


def _parse_measurements(
    fetus_data: Dict[str, Any], fetus_number: int, factory: TermBinFactory
) -> List[TermBin]:
    """
    Parse measurements and convert to TermBins.

    Args:
        fetus_data: Single fetus dictionary
        fetus_number: Fetus identifier
        factory: TermBinFactory instance

    Returns:
        List of TermBin objects
    """
    if "measurements" not in fetus_data:
        logger.warning("No 'measurements' key in fetus data")
        return []

    measurements_list = fetus_data["measurements"]
    if not isinstance(measurements_list, list):
        raise ValueError("'measurements' must be a list")

    logger.debug(f"Found {len(measurements_list)} measurements")

    term_bins = []
    for m in measurements_list:
        try:
            term_bin = _parse_single_measurement(m, fetus_number, factory)
            if term_bin:
                term_bins.append(term_bin)
        except Exception as e:  # noqa: PERF203
            logger.warning(
                f"Failed to parse measurement {m.get('label', 'unknown')}: {e}"
            )

    logger.debug(f"Successfully parsed {len(term_bins)} measurements")
    return term_bins


def _percentile_not_calculated(m: Dict[str, Any]) -> bool:
    """
    True when Observer exported a percentile it never actually calculated.

    Observer writes ``calculated_percentile: 0`` together with an empty
    ``percentile_for_display`` when it has no growth chart for a measurement
    (OFD, NT, Nuchal Fold, Cerebellum, Cisterna Magna, Nasal Bone, the lateral
    ventricles, Biorbit and Mean Gest Sac never get one). A genuinely low
    reading always carries display text such as ``"<3%"``, so this exact pair
    is a placeholder, not a 0th-percentile result. Records without a
    ``percentile_for_display`` key are not treated as placeholders.

    TODO(@VarenyaJ): measurements Observer never calculates a percentile for
    can still be judged from the raw value against an absolute cutoff (e.g. NT
    >= 3.5mm). Add that fallback, with clinically sourced cutoffs, instead of
    dropping them entirely.
    """
    return m.get("calculated_percentile") == 0 and m.get("percentile_for_display") == ""


def _parse_single_measurement(
    m: Dict[str, Any], fetus_number: int, factory: TermBinFactory
) -> TermBin:
    """
    Parse single measurement into TermBin.

    Args:
        m: Measurement dictionary
        fetus_number: Fetus identifier
        factory: TermBinFactory instance

    Returns:
        TermBin object or None if not a target measurement
    """
    label = m.get("label")
    if not label:
        return None

    logger.debug(f"Processing measurement: {label}")

    # Check if target measurement
    if label not in OBSERVER_NAME_MAP:
        logger.debug(f"Skipping {label}: not a target measurement")
        return None

    # Normalize label to standard name
    canonical_name = OBSERVER_NAME_MAP[label].value

    # Extract required fields
    value = m.get("value")
    if value is None:
        logger.debug(f"Skipping {label}: no value")
        return None

    # Extract optional fields
    unit = m.get("unit_of_measure", "cm")
    percentile = m.get("calculated_percentile")
    ega = m.get("calculated_ega")

    if percentile is None:
        logger.debug(f"Skipping {label}: percentile is None (missing)")
        return None

    if _percentile_not_calculated(m):
        logger.debug(f"Skipping {label}: Observer did not calculate a percentile")
        return None

    # If percentile is a number, validate it's in valid range
    if isinstance(percentile, (int, float)):
        if percentile < 0:
            logger.warning(
                f"Skipping {label}: invalid percentile {percentile} (negative)"
            )
            return None
        logger.debug(f"{label} has percentile={percentile}% (valid)")

    # Convert units
    value_mm = _convert_to_mm(float(value), unit)

    gestational_age = _parse_ega(ega, label)

    logger.debug(
        f"Creating TermBin for {canonical_name}: "
        f"value={value_mm}mm, percentile={percentile}%, ga={gestational_age}"
    )

    # Create TermBin using PercentileRange.contains()
    return factory.create_term_bin(
        name=canonical_name,
        value_mm=value_mm,
        percentile=float(percentile),
        gestational_age=gestational_age,
        method=None,  # Observer JSON doesn't include method
        fetus_number=fetus_number,
    )


def _parse_t1_measurements(
    fetus_data: Dict[str, Any], fetus_number: int, factory: TermBinFactory
) -> List[TermBin]:
    """Parse first-trimester measurements (CRL, NT) into TermBins.

    T1 scans have no "required" set; either CRL or NT (or both) is sufficient.
    Anything outside T1_LABELS is skipped silently - extractor stays single-purpose.
    """
    measurements_list = fetus_data.get("measurements") or []
    if not isinstance(measurements_list, list):
        raise ValueError("'measurements' must be a list")

    term_bins: List[TermBin] = []
    for m in measurements_list:
        label = m.get("label")
        if label not in T1_LABELS:
            continue

        value = m.get("value")
        if value is None:
            logger.debug(f"Skipping {label}: no value")
            continue

        percentile = m.get("calculated_percentile")
        if percentile is None:
            logger.debug(f"Skipping {label}: no percentile")
            continue
        if _percentile_not_calculated(m):
            logger.debug(f"Skipping {label}: Observer did not calculate a percentile")
            continue
        if isinstance(percentile, (int, float)) and percentile < 0:
            logger.warning(f"Skipping {label}: invalid percentile {percentile}")
            continue

        unit = m.get("unit_of_measure", "mm")
        value_mm = _convert_to_mm(float(value), unit)

        gestational_age = _parse_ega(m.get("calculated_ega"), label)

        canonical_name = OBSERVER_NAME_MAP[label].value
        term_bin = factory.create_term_bin(
            name=canonical_name,
            value_mm=value_mm,
            percentile=float(percentile),
            gestational_age=gestational_age,
            method=None,
            fetus_number=fetus_number,
        )
        if term_bin is not None:
            term_bins.append(term_bin)

    return term_bins


def _parse_ega(ega: Any, label: str) -> GestationalAge | None:
    """
    Read Observer's ``calculated_ega`` (decimal weeks) into a GestationalAge.

    Observer writes ``calculated_ega: 0`` when it did not calculate an age for
    a measurement, the same way it writes ``calculated_percentile: 0`` for a
    percentile it never calculated. 0 therefore means "unknown", not 0w 0d.
    A value that cannot be read, or is outside the plausible range, is logged
    and the measurement keeps no gestational age.
    """
    if ega is None:
        return None
    if ega == 0:
        logger.debug(f"{label}: Observer did not calculate a gestational age")
        return None
    try:
        return GestationalAge.parse(ega)
    except ValueError as e:
        logger.warning(f"Ignoring unreadable gestational age for {label}: {e}")
        return None


def _convert_to_mm(value: float, unit: str) -> float:
    """
    Convert measurement to millimeters.

    Args:
        value: Measurement value
        unit: Unit of measure

    Returns:
        Value in millimeters

    Raises:
        ValueError: If unit not supported
    """
    unit_lower = unit.lower().strip()

    if unit_lower in ["mm", "millimeters", "millimeter"]:
        return value
    elif unit_lower in ["cm", "centimeters", "centimeter"]:
        return value * 10.0
    else:
        raise ValueError(f"Unsupported unit: {unit}")
