"""
ViewPoint text file biometry extractor.

Extracts fetal biometry measurements from ViewPoint ultrasound system text exports
and converts them directly to TermBin objects.

ViewPoint Text Format Characteristics:
   - **All fields are optional** - any section may be missing
   - Field presence varies significantly between files
   - Common sections: Fetal Biometry, Dating, General Evaluation
   - Rare sections: Maternal Structures, CHKD Referral, Fetal Echocardiogram
   - Section-based format using "====" dividers
   - Sub-headers within sections (e.g., "Head / Face / Neck Biometry:")

Biometry Line Format:
   [name] [value] [unit] [GA_weeks] [GA_days] [percentile] [method]
   Example: "BPD    63.2    mm    25w 4d    36%    Hadlock"
   Example: "Nuchal Fold    4.5    mm    25w 3d    10%    Standard"

Required Measurements: HC, BPD, AC, Femur (will ERROR if missing)
Optional Measurements: Nuchal Fold, Cerebellum, OFD, Humerus
"""

import logging
from pathlib import Path
from typing import List, Optional

from prenatalppkt.etl.constants import SectionHeader, VIEWPOINT_TEXT_NAME_MAP
from prenatalppkt.etl.term_bin_factory import (
    TermBinFactory,
    validate_required_measurements,
)
from prenatalppkt.gestational_age import GestationalAge
from prenatalppkt.measurements.term_bin import TermBin

logger = logging.getLogger(__name__)


def extract(data: str, factory: TermBinFactory = None) -> List[TermBin]:
    """
    Extract biometry measurements from ViewPoint text and convert to TermBins.

    Args:
        data: ViewPoint text file content as string
        factory: TermBinFactory instance (creates new if None)

    Returns:
        List of TermBin objects

    Raises:
        ValueError: If text format is invalid or required measurements missing
    """
    if factory is None:
        factory = TermBinFactory()

    if not isinstance(data, str):
        raise ValueError(f"Expected string, got {type(data)}")

    lines = data.split("\n")
    biometry_lines = _find_biometry_section(lines)

    if not biometry_lines:
        logger.warning("No 'Fetal Biometry' section found")
        return []

    term_bins = _parse_biometry_lines(biometry_lines, factory)

    # Validate required measurements
    validate_required_measurements(term_bins)

    logger.info(f"Extracted {len(term_bins)} TermBins from ViewPoint text")
    return term_bins


def extract_from_file(filepath: Path, factory: TermBinFactory = None) -> List[TermBin]:
    """
    Extract biometry measurements from ViewPoint text file.

    Args:
        filepath: Path to ViewPoint text file
        factory: TermBinFactory instance (creates new if None)

    Returns:
        List of TermBin objects
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = f.read()

    return extract(data, factory)


def _is_divider(line: str) -> bool:
    """Check if line is section divider (====)."""
    stripped = line.strip()
    return len(stripped) >= 3 and all(c == "=" for c in stripped)


def _find_biometry_section(lines: List[str]) -> List[str]:
    """
    Find lines in Fetal Biometry section using divider-based detection.

    Uses divider approach from legacy ViewpointTextParse:
    - Sections delimited by ==== lines
    - Section header is line BEFORE ====
    - Content is all lines until NEXT ====

    Args:
        lines: All lines from text file

    Returns:
        List of lines in biometry section
    """
    divider_indices = [i for i, line in enumerate(lines) if _is_divider(line)]

    if not divider_indices:
        return []

    # Find Fetal Biometry section
    biometry_start_idx = None
    biometry_end_idx = None

    for i, divider_idx in enumerate(divider_indices):
        if divider_idx > 0:
            header = lines[divider_idx - 1].strip()
            if header == SectionHeader.FETAL_BIOMETRY.value:
                biometry_start_idx = divider_idx + 1
                # End at next divider or EOF
                if i + 1 < len(divider_indices):
                    biometry_end_idx = divider_indices[i + 1] - 1
                else:
                    biometry_end_idx = len(lines)
                break

    if biometry_start_idx is None:
        return []

    # Extract non-empty, non-divider lines
    section_lines = []
    for line in lines[biometry_start_idx:biometry_end_idx]:
        stripped = line.strip()
        if stripped and not _is_divider(stripped):
            section_lines.append(stripped)

    return section_lines


def _parse_biometry_lines(lines: List[str], factory: TermBinFactory) -> List[TermBin]:
    """Parse biometry measurement lines into TermBins."""
    term_bins = []

    for line in lines:
        try:
            term_bin = _parse_biometry_line(line, factory)
            if term_bin:
                term_bins.append(term_bin)
        except Exception as e:  # noqa: PERF203
            logger.warning(f"Failed to parse line '{line}': {e}")

    return term_bins


def _parse_biometry_line(line: str, factory: TermBinFactory) -> Optional[TermBin]:
    """
    Parse single biometry line into TermBin.

    Format: [name] [value] [unit] [GA_weeks] [GA_days] [percentile] [method]

    Sub-headers (e.g., "Head / Face / Neck Biometry:") naturally fail
    parsing and are skipped.

    Args:
        line: Single line from biometry section
        factory: TermBinFactory instance

    Returns:
        TermBin object or None
    """
    parts = line.split()

    # Need at least 6 parts for valid measurement
    if len(parts) < 6:
        return None

    # Try multi-word names first (e.g., "Nuchal Fold")
    name = None
    value_idx = None

    if len(parts) >= 7:
        two_word_name = f"{parts[0]} {parts[1]}"
        if two_word_name in VIEWPOINT_TEXT_NAME_MAP:
            name = VIEWPOINT_TEXT_NAME_MAP[two_word_name].value
            value_idx = 2

    # Fall back to single-word names
    if name is None:
        single_word_name = parts[0]
        if single_word_name in VIEWPOINT_TEXT_NAME_MAP:
            name = VIEWPOINT_TEXT_NAME_MAP[single_word_name].value
            value_idx = 1
        else:
            return None

    try:
        # Parse value and unit
        value = float(parts[value_idx])
        unit = parts[value_idx + 1]
        value_mm = _convert_to_mm(value, unit)

        # Parse gestational age
        ga_weeks_str = parts[value_idx + 2] if len(parts) > value_idx + 2 else None
        ga_days_str = parts[value_idx + 3] if len(parts) > value_idx + 3 else None
        gestational_age = _parse_gestational_age(ga_weeks_str, ga_days_str)

        # Parse percentile
        percentile_str = None
        if len(parts) > value_idx + 4 and "%" in parts[value_idx + 4]:
            percentile_str = parts[value_idx + 4]

        if not percentile_str:
            logger.debug(f"Skipping {name}: no percentile")
            return None

        percentile = _parse_percentile(percentile_str)

        # Extract method
        method = parts[value_idx + 5] if len(parts) > value_idx + 5 else None

        # Create TermBin
        return factory.create_term_bin(
            name=name,
            value_mm=value_mm,
            percentile=percentile,
            gestational_age=gestational_age,
            method=method,
            fetus_number=None,  # ViewPoint text doesn't specify fetus number
        )

    except (ValueError, IndexError) as e:
        logger.debug(f"Failed to parse values from '{line}': {e}")
        return None


def _parse_gestational_age(
    ga_weeks_str: Optional[str], ga_days_str: Optional[str]
) -> Optional[GestationalAge]:
    """Parse gestational age from week/day strings."""
    if not ga_weeks_str or "w" not in ga_weeks_str:
        return None

    text = ga_weeks_str
    if ga_days_str and "d" in ga_days_str:
        text = f"{ga_weeks_str} {ga_days_str}"

    try:
        return GestationalAge.parse(text)
    except ValueError as e:
        logger.warning(f"Ignoring unreadable gestational age '{text}': {e}")
        return None


def _parse_percentile(percentile_str: str) -> float:
    """
    Parse percentile string to float.

    Handles special cases:
    - "<1%" -> 0.5
    - ">99%" -> 99.5
    - "55%" -> 55.0

    Args:
        percentile_str: Percentile as string

    Returns:
        Percentile as float (0-100 scale)
    """
    s = str(percentile_str).strip()

    if s.startswith("<"):
        return 0.5
    elif s.startswith(">"):
        return 99.5

    # Remove % sign
    s = s.rstrip("%")
    return float(s)


def _convert_to_mm(value: float, unit: str) -> float:
    """Convert measurement to millimeters."""
    unit_lower = unit.lower().strip()

    if unit_lower in ["mm", "millimeters", "millimeter"]:
        return value
    elif unit_lower in ["cm", "centimeters", "centimeter"]:
        return value * 10.0
    else:
        raise ValueError(f"Unsupported unit: {unit}")
