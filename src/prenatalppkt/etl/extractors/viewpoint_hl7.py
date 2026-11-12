"""
ViewPoint HL7 message biometry extractor.

Extracts fetal biometry measurements from ViewPoint HL7 message exports
and converts them directly to TermBin objects. Segment splitting is left to
the shared row reader (`prenatalppkt.etl.hl7_rows`); this module only decides
which rows are biometry and what their values mean.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from prenatalppkt.etl.constants import VIEWPOINT_HL7_NAME_MAP
from prenatalppkt.etl.hl7_rows import Hl7Row, read_hl7_rows
from prenatalppkt.etl.term_bin_factory import TermBinFactory
from prenatalppkt.gestational_age import GestationalAge
from prenatalppkt.measurements.term_bin import TermBin

logger = logging.getLogger(__name__)

# Enable debug logging by default for troubleshooting
logging.basicConfig(level=logging.DEBUG)


def extract(data: str, factory: TermBinFactory = None) -> List[TermBin]:
    """
    Extract biometry measurements from ViewPoint HL7 and convert to TermBins.

    Args:
        data: ViewPoint HL7 message content as string
        factory: TermBinFactory instance (creates new if None)

    Returns:
        List of TermBin objects

    Raises:
        ValueError: If HL7 format is invalid or required measurements missing
        Hl7ParseError: (a ValueError) If a segment is malformed; the message
            names the line.
    """
    if factory is None:
        factory = TermBinFactory()

    if not isinstance(data, str):
        raise ValueError(f"Expected string, got {type(data)}")

    logger.debug("Starting HL7 extraction")

    # Parse OBX segments
    obx_rows = read_hl7_rows(data)
    logger.debug(f"Found {len(obx_rows)} OBX segments")

    if not obx_rows:
        logger.warning("No OBX segments found in HL7 message")
        return []

    # Group measurements by fetus
    measurements_by_fetus = _group_measurements_by_fetus(obx_rows)
    logger.debug(f"Grouped into {len(measurements_by_fetus)} fetus records")
    logger.debug(f"Fetus IDs: {list(measurements_by_fetus.keys())}")

    # Convert to TermBins (process first fetus for now)
    term_bins = []
    if measurements_by_fetus:
        fetus_id = list(measurements_by_fetus.keys())[0]
        measurements = measurements_by_fetus[fetus_id]
        logger.debug(
            f"Processing fetus {fetus_id} with {len(measurements)} measurements"
        )
        logger.debug(f"Measurement names: {list(measurements.keys())}")
        term_bins = _create_term_bins(measurements, factory)

    # TODO(@VarenyaJ): Skip validation for first trimester exams (missing BPD)
    # Current sample is first trimester - validation will fail
    # TODO(@VarenyaJ): Add gestational age check for conditional validation
    # try:
    #    validate_required_measurements(term_bins)
    # except ValueError as e:
    #    logger.warning(f"Validation failed (expected for first trimester): {e}")
    # For now, don't raise - just log

    logger.info(f"Extracted {len(term_bins)} TermBins from ViewPoint HL7")
    return term_bins


def extract_from_file(filepath: Path, factory: TermBinFactory = None) -> List[TermBin]:
    """
    Extract biometry measurements from ViewPoint HL7 file.

    Args:
        filepath: Path to ViewPoint HL7 file
        factory: TermBinFactory instance (creates new if None)

    Returns:
        List of TermBin objects
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = f.read()
    return extract(data, factory)


def _parse_fetus_number(fetus_id: str) -> int:
    """Convert an OBX-5 sub-id like "Fetus2" to its int fetus number."""
    match = re.search(r"(\d+)$", fetus_id)
    return int(match.group(1)) if match else 1


def extract_all_fetuses(
    data: str, factory: TermBinFactory = None
) -> Dict[int, List[TermBin]]:
    """
    Extract biometry from every fetus in a ViewPoint HL7 message.

    Mirrors etl/extractors/observer.py's extract_all_fetuses shape: one
    key per fetus_number, values are that fetus's TermBins.
    `_group_measurements_by_fetus` and `_create_term_bins` are already
    fetus-count-agnostic - `extract()` just discarded every key but the
    first; this loops over all of them instead.

    Args:
        data: ViewPoint HL7 message content as string
        factory: TermBinFactory instance (creates new if None)

    Returns:
        Dict keyed by fetus_number; values are lists of TermBins for that
        fetus (empty list when no measurements matched for that fetus).

    Raises:
        ValueError: If data is not a string.
        Hl7ParseError: (a ValueError) If a segment is malformed.
    """
    if factory is None:
        factory = TermBinFactory()

    if not isinstance(data, str):
        raise ValueError(f"Expected string, got {type(data)}")

    obx_rows = read_hl7_rows(data)
    if not obx_rows:
        logger.warning("No OBX segments found in HL7 message")
        return {}

    measurements_by_fetus = _group_measurements_by_fetus(obx_rows)

    result: Dict[int, List[TermBin]] = {}
    for fetus_number, measurements in measurements_by_fetus.items():
        result[fetus_number] = _create_term_bins(measurements, factory)
    return result


def extract_all_fetuses_from_file(
    filepath: Path, factory: TermBinFactory = None
) -> Dict[int, List[TermBin]]:
    """Multi-fetus equivalent of `extract_from_file`."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = f.read()
    return extract_all_fetuses(data, factory)


def _fetus_key(row: Hl7Row) -> int:
    """
    Fetus number a biometry row belongs to.

    `Hl7Row.fetus_number` covers the "Fetus<N>" sub-ids ViewPoint writes.
    For anything else this keeps the rule biometry grouping always used: the
    trailing digits of OBX-4, or fetus 1 when OBX-4 is empty or has none.
    """
    if row.fetus_number is not None:
        return row.fetus_number
    return _parse_fetus_number(row.sub_id)


def _group_measurements_by_fetus(obx_rows: List[Hl7Row]) -> Dict[int, Dict[str, any]]:
    """
    Group measurement data by fetus.

    Returns:
        Dict mapping fetus_number -> {measurement_name -> {value, unit, percentile, ga, method}}
    """
    measurements = {}

    logger.debug(f"Processing {len(obx_rows)} OBX segments")

    for i, row in enumerate(obx_rows):
        logger.debug(f"[{i}] Processing OBX on line {row.line_number}")

        result = _process_obx_row(row)

        if result:
            fetus_id, measurement_name, field_type, value = result
            logger.debug(
                f"  -> Parsed: fetus={fetus_id}, measurement={measurement_name}, "
                f"field={field_type}, value={value}"
            )
            _store_measurement_field(
                measurements, fetus_id, measurement_name, field_type, value
            )
        else:
            logger.debug("  -> Skipped (not a measurement field)")

    logger.debug(f"Final measurements dict has {len(measurements)} fetus records")
    for fetus_id, fetus_measurements in measurements.items():
        logger.debug(f"  Fetus {fetus_id}: {len(fetus_measurements)} measurements")
        for name, data in fetus_measurements.items():
            logger.debug(f"    - {name}: {data}")

    return measurements


def _process_obx_row(row: Hl7Row) -> Optional[Tuple[int, str, str, any]]:
    """Process single OBX row and extract measurement info."""
    code = row.observation_id
    fetus_id = _fetus_key(row)
    value_field = row.value

    logger.debug(f"  Code: {code}")
    logger.debug(f"  Fetus ID: {fetus_id}")
    logger.debug(f"  Value field: {value_field}")

    measurement_info = _parse_measurement_code(code)
    if not measurement_info:
        logger.debug(f"  Code not recognized as measurement: {code}")
        return None

    measurement_name, field_type = measurement_info
    logger.debug(f"  Recognized: {measurement_name} ({field_type})")

    value = _extract_field_value(field_type, value_field, row.units)
    if value is None:
        logger.debug(f"  Could not extract value from: {value_field}")
        return None

    logger.debug(f"  Extracted value: {value}")
    return (fetus_id, measurement_name, field_type, value)


def _parse_measurement_code(code: str) -> Optional[Tuple[str, str]]:
    """
    Parse measurement code to extract name and field type.

    Args:
        code: OBX code field (e.g., "SkullFetus.HeadCircumference^HC")

    Returns:
        Tuple of (the standardized name, field_type) or None
    """
    # Extract measurement code (before ^), then strip the leading
    # "<Namespace>." segment (e.g. "SkullFetus.") - OBX-3 identifiers are
    # always namespaced, but VIEWPOINT_HL7_NAME_MAP keys are not.
    code_part = code.split("^")[0]
    local_code = code_part.split(".")[-1] if "." in code_part else code_part

    # Determine field type
    if "_Percentile" in local_code:
        field_type = "percentile"
        base_code = local_code.replace("VP_", "").replace("_Percentile", "")
    elif "_GA" in local_code:
        field_type = "ga"
        base_code = local_code.replace("VP_", "").replace("_GA", "")
    elif "_Author" in local_code:
        field_type = "method"  # Changed from "author" to "method"
        base_code = local_code.replace("VP_", "").replace("_Author", "")
    else:
        field_type = "value"
        base_code = local_code

    logger.debug(f"    Parsed code: base={base_code}, type={field_type}")

    # Map to standard name
    if base_code in VIEWPOINT_HL7_NAME_MAP:
        canonical_name = VIEWPOINT_HL7_NAME_MAP[base_code].value
        logger.debug(f"    Mapped to standard name: {canonical_name}")
        return (canonical_name, field_type)

    logger.debug(f"    Base code not in mapping: {base_code}")
    return None


def _extract_field_value(
    field_type: str, value_field: str, units_field: str
) -> Optional[any]:
    """Extract value based on field type."""
    if field_type == "value":
        value = _parse_value(value_field)
        if value is not None:
            return {"value": value, "unit": _parse_unit_field(units_field)}
        return None

    elif field_type == "percentile":
        return _parse_percentile_field(value_field)

    elif field_type == "ga":
        return _parse_ga_field(value_field)

    elif field_type == "method":
        return value_field

    return None


def _store_measurement_field(
    measurements: Dict,
    fetus_id: int,
    measurement_name: str,
    field_type: str,
    value: any,
):
    """Store measurement field in nested dict structure."""
    # Initialize fetus dict if needed
    if fetus_id not in measurements:
        measurements[fetus_id] = {}
        logger.debug(f"  Created new fetus record: {fetus_id}")

    # Initialize measurement dict if needed
    if measurement_name not in measurements[fetus_id]:
        measurements[fetus_id][measurement_name] = {
            "value": None,
            "unit": None,
            "percentile": None,
            "ga": None,
            "method": None,
        }
        logger.debug(f"  Created new measurement: {measurement_name}")

    # Store value
    if field_type == "value" and isinstance(value, dict):
        measurements[fetus_id][measurement_name]["value"] = value.get("value")
        measurements[fetus_id][measurement_name]["unit"] = value.get("unit")
        logger.debug(f"  Stored value={value.get('value')} unit={value.get('unit')}")
    else:
        measurements[fetus_id][measurement_name][field_type] = value
        logger.debug(f"  Stored {field_type}={value}")


def _parse_value(value_field: str) -> Optional[float]:
    """Parse numeric value from HL7 field."""
    if not value_field:
        return None

    # Value might be "56^56.0" format
    value_str = value_field.split("^")[0]

    try:
        return float(value_str)
    except ValueError:
        logger.debug(f"Could not parse value: {value_field}")
        return None


def _parse_unit_field(unit_field: str) -> str:
    """
    Parse the primary unit code from an HL7 coded-value unit field.

    Format: "mm&millimeters^mm&millimeters" (code&text^code&text) - take
    the first caret segment's code, before "&".
    """
    if not unit_field:
        return unit_field
    return unit_field.split("^")[0].split("&")[0]


def _parse_percentile_field(value_field: str) -> Optional[float]:
    """
    Parse percentile from HL7 field.

    Format: "73^73%" or "0^<1%"
    """
    if not value_field:
        return None

    # Extract percentile string (after ^)
    parts = value_field.split("^")
    if len(parts) < 2:
        return None

    percentile_str = parts[1].rstrip("%")

    if percentile_str.startswith("<"):
        return 0.5
    elif percentile_str.startswith(">"):
        return 99.5

    try:
        return float(percentile_str)
    except ValueError:
        logger.debug(f"Could not parse percentile: {value_field}")
        return None


def _parse_ga_field(value_field: str) -> Optional[GestationalAge]:
    """
    Parse gestational age from HL7 field.

    Format: "87^12w 3d" or "85^12w 1d"
    """
    if not value_field:
        return None

    # Extract GA string (after ^)
    parts = value_field.split("^")
    if len(parts) < 2:
        return None

    ga_str = parts[1]  # e.g., "12w 3d"

    # Parse weeks and days
    match = re.match(r"(\d+)w\s*(\d*)d?", ga_str)
    if not match:
        return None

    weeks = int(match.group(1))
    days = int(match.group(2)) if match.group(2) else 0

    return GestationalAge(weeks=weeks, days=days)


def _create_term_bins(
    measurements: Dict[str, Dict], factory: TermBinFactory
) -> List[TermBin]:
    """
    Create TermBins from parsed measurements.

    Args:
        measurements: Dict of {measurement_name -> {value, unit, percentile, ga, method}}
        factory: TermBinFactory instance

    Returns:
        List of TermBin objects
    """
    term_bins = []

    logger.debug(f"Creating TermBins from {len(measurements)} measurements")

    for name, data in measurements.items():
        logger.debug(f"Processing {name}: {data}")

        value = data.get("value")
        percentile = data.get("percentile")

        if value is None:
            logger.debug(f"Skipping {name}: no value")
            continue

        if percentile is None:
            logger.debug(f"Skipping {name}: no percentile")
            continue

        # Convert units
        unit = data.get("unit", "mm")
        value_mm = _convert_to_mm(value, unit)
        logger.debug(f"Converted {value} {unit} -> {value_mm} mm")

        try:
            term_bin = factory.create_term_bin(
                name=name,
                value_mm=value_mm,
                percentile=percentile,
                gestational_age=data.get("ga"),
                method=data.get("method"),
                fetus_number=None,  # Could extract from MSH/PID if needed
            )
            if term_bin:
                term_bins.append(term_bin)
                logger.debug(f"Created TermBin for {name}")
            else:
                logger.debug(f"TermBin creation returned None for {name}")
        except Exception as e:
            logger.warning(f"Failed to create TermBin for {name}: {e}")

    logger.debug(f"Created {len(term_bins)} TermBins total")
    return term_bins


def _convert_to_mm(value: float, unit: str) -> float:
    """Convert measurement to millimeters."""
    unit_lower = unit.lower().strip()

    if unit_lower in ["mm", "millimeters", "millimeter"]:
        return value
    elif unit_lower in ["cm", "centimeters", "centimeter"]:
        return value * 10.0
    else:
        raise ValueError(f"Unsupported unit: {unit}")
