from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Dict, Optional, Union

from prenatalppkt.gestational_age import GestationalAge

logger = logging.getLogger(__name__)

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"]


def parse_pregnancy_dating(data: Union[str, Dict], source_format: str) -> Dict:
    """
    Parse pregnancy dating information from ultrasound reports.

    Supported formats:
        - observer_json
        - viewpoint_text
        - viewpoint_hl7
    """
    if source_format == "observer_json":
        if isinstance(data, str):
            data = json.loads(data)
        result = _parse_observer_pregnancy(data)

    elif source_format == "viewpoint_text":
        if not isinstance(data, str):
            raise ValueError("viewpoint_text data must be a string")
        result = _parse_viewpoint_text_pregnancy(data)

    elif source_format == "viewpoint_hl7":
        if not isinstance(data, str):
            raise ValueError("viewpoint_hl7 data must be a string")
        result = _parse_viewpoint_hl7_pregnancy(data)

    else:
        raise ValueError(f"Unsupported source_format: {source_format}")

    result["source_format"] = source_format
    return result


# ---------------------------------------------------------------------
# Observer JSON
# ---------------------------------------------------------------------


def _parse_observer_pregnancy(json_data: Dict) -> Dict:
    exam = json_data.get("exam", {})

    lmp = exam.get("lmp")
    edd = exam.get("edd") or exam.get("estimated_due_date")
    dating_method = exam.get("dating_method")

    exam_date = _parse_date_string(exam.get("exm_date") or "")
    ga_by_lmp = _calculate_ga_from_lmp(lmp, exam_date) if lmp else None

    return {
        "lmp": lmp,
        "edd": edd,
        "assigned_edd": edd,
        "dating_method": dating_method,
        "ga_by_lmp": ga_by_lmp,
        "ga_by_ultrasound": None,
        "assigned_ga": ga_by_lmp,
        "raw_data": json_data,
    }


# ---------------------------------------------------------------------
# ViewPoint Text
# ---------------------------------------------------------------------


def _parse_viewpoint_text_pregnancy(text: str) -> Dict:
    """
    Extract pregnancy dating from ViewPoint text reports.

    Example:
        Dating
        ======
        LMP 01/15/2025
        EDD by LMP 10/22/2025
        Assigned dating based on LMP
    """
    lmp = None
    edd = None
    dating_method = None

    section = _extract_dating_section(text)

    for line in section.splitlines():
        line = line.strip()

        if line.upper().startswith("LMP"):
            lmp = _parse_date_from_text(line)

        elif "EDD" in line.upper():
            edd = _parse_date_from_text(line)

        elif "ASSIGNED" in line.upper():
            dating_method = line

    # The Dating section carries no exam date, so there is nothing to count
    # the days from and the age by LMP stays unknown.
    ga_by_lmp = None

    return {
        "lmp": lmp,
        "edd": edd,
        "assigned_edd": edd,
        "dating_method": dating_method,
        "ga_by_lmp": ga_by_lmp,
        "ga_by_ultrasound": None,
        "assigned_ga": ga_by_lmp,
        "raw_data": {"text": text},
    }


def _extract_dating_section(text: str) -> str:
    pattern = re.compile(
        r"Dating\s*\n=+\n(?P<body>.*?)(?:\n[A-Z][^\n]*\n=+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group("body") if match else ""


# ---------------------------------------------------------------------
# ViewPoint HL7
# ---------------------------------------------------------------------


def _parse_viewpoint_hl7_pregnancy(hl7: str) -> Dict:
    lmp = None
    edd = None
    exam_date = None

    for line in hl7.splitlines():
        if line.startswith("OBR"):
            # OBR-7 is the observation date/time; the first 8 characters are YYYYMMDD.
            obr_fields = line.split("|")
            if len(obr_fields) > 7:
                exam_date = _parse_date_string(obr_fields[7][:8])
            continue

        if not line.startswith("OBX"):
            continue

        fields = line.split("|")
        if len(fields) < 6:
            continue

        obs_id = fields[3]
        value = fields[5]

        if "LastMenstrualPeriod" in obs_id:
            lmp = _parse_date_string(value)

        elif "EDD" in obs_id:
            edd = _parse_date_string(value)

    ga_by_lmp = _calculate_ga_from_lmp(lmp, exam_date) if lmp else None

    return {
        "lmp": lmp,
        "edd": edd,
        "assigned_edd": edd,
        "dating_method": None,
        "ga_by_lmp": ga_by_lmp,
        "ga_by_ultrasound": None,
        "assigned_ga": ga_by_lmp,
        "raw_data": {"hl7": hl7},
    }


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _parse_date_from_text(text: str) -> Optional[str]:
    for token in re.split(r"\s+", text):
        parsed = _parse_date_string(token)
        if parsed:
            return parsed
    return None


def _parse_date_string(value: str) -> Optional[str]:
    value = value.split("^")[0].strip()

    # Fast reject: must contain digits
    if not any(ch.isdigit() for ch in value):
        return None

    for fmt in DATE_FORMATS:
        parsed = _try_parse_date(value, fmt)
        if parsed:
            return parsed

    return None


def _try_parse_date(value: str, fmt: str) -> Optional[str]:
    try:
        return datetime.strptime(value, fmt).date().isoformat()
    except ValueError:
        return None


def _calculate_ga_from_lmp(
    lmp_iso: str, exam_date_iso: Optional[str]
) -> Optional[Dict]:
    """
    Gestational age by LMP on the exam date, or None when it cannot be known.

    None covers a missing exam date, an exam before the LMP, and an LMP so far
    back that the age is impossible (a placeholder such as 0001-01-01).
    """
    if not exam_date_iso:
        return None
    try:
        ga = GestationalAge.from_lmp(
            date.fromisoformat(lmp_iso), date.fromisoformat(exam_date_iso)
        )
    except ValueError as e:
        logger.debug(f"No gestational age by LMP for LMP {lmp_iso}: {e}")
        return None
    return {"weeks": ga.weeks, "days": ga.days}
