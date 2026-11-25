import json
from pathlib import Path

import pytest

from prenatalppkt.etl.sections.pregnancy_dating import parse_pregnancy_dating


# ---------------------------------------------------------------------
# Observer JSON
# ---------------------------------------------------------------------


class TestPregnancyDatingObserver:
    def test_basic_lmp_and_edd(self):
        data = json.dumps(
            {"exam": {"lmp": "2025-01-15", "edd": "2025-10-22", "dating_method": "LMP"}}
        )

        result = parse_pregnancy_dating(data, "observer_json")

        assert result["lmp"] == "2025-01-15"
        assert result["edd"] == "2025-10-22"
        assert result["ga_by_lmp"] is None
        assert result["source_format"] == "observer_json"

    def test_missing_dates(self):
        data = json.dumps({"exam": {}})
        result = parse_pregnancy_dating(data, "observer_json")
        assert result["lmp"] is None
        assert result["ga_by_lmp"] is None


# ---------------------------------------------------------------------
# ViewPoint Text
# ---------------------------------------------------------------------


class TestPregnancyDatingViewPointText:
    def test_basic_dating_section(self):
        text = """Dating
======
LMP 01/15/2025
EDD by LMP 10/22/2025
Assigned dating based on LMP
"""

        result = parse_pregnancy_dating(text, "viewpoint_text")

        assert result["lmp"] == "2025-01-15"
        assert result["edd"] == "2025-10-22"
        assert result["ga_by_lmp"] is None
        assert "Assigned" in result["dating_method"]

    def test_missing_dating_section(self):
        text = "Fetal Biometry\n============\nHC 175 mm"
        result = parse_pregnancy_dating(text, "viewpoint_text")
        assert result["lmp"] is None
        assert result["edd"] is None


# ---------------------------------------------------------------------
# ViewPoint HL7
# ---------------------------------------------------------------------


class TestPregnancyDatingViewPointHL7:
    def test_basic_hl7_dates(self):
        hl7 = (
            "OBX||DT|EpisodeHistory.LastMenstrualPeriod^LMP|1|20250115\n"
            "OBX||DT|EpisodeHistory.EDDbyLMP^EDD|1|20251022\n"
        )

        result = parse_pregnancy_dating(hl7, "viewpoint_hl7")

        assert result["lmp"] == "2025-01-15"
        assert result["edd"] == "2025-10-22"
        assert result["ga_by_lmp"] is None

    def test_no_dates(self):
        hl7 = "OBX||NM|SomeOtherField|1|123\n"
        result = parse_pregnancy_dating(hl7, "viewpoint_hl7")
        assert result["lmp"] is None
        assert result["ga_by_lmp"] is None


# ---------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------


class TestPregnancyDatingEdgeCases:
    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_pregnancy_dating("data", "bad_format")

    def test_non_string_text(self):
        with pytest.raises(ValueError):
            parse_pregnancy_dating({"bad": "data"}, "viewpoint_text")

    def test_malformed_dates(self):
        text = """Dating
        ======
        LMP not-a-date
        """
        result = parse_pregnancy_dating(text, "viewpoint_text")
        assert result["lmp"] is None
        assert result["ga_by_lmp"] is None


DATA_DIR = Path(__file__).resolve().parents[3] / "tests" / "data"


class TestGaByLmpUsesTheExamDate:
    def test_observer_ga_by_lmp_is_calculated_from_lmp_and_exam_date(self):
        data = json.dumps({"exam": {"lmp": "2025-01-15", "exm_date": "2025-05-02"}})

        result = parse_pregnancy_dating(data, "observer_json")

        assert result["ga_by_lmp"] == {"weeks": 15, "days": 2}
        assert result["assigned_ga"] == {"weeks": 15, "days": 2}

    def test_observer_placeholder_lmp_gives_no_ga(self):
        # Observer writes 0001-01-01 when no LMP was entered.
        data = json.dumps({"exam": {"lmp": "0001-01-01", "exm_date": "2025-07-02"}})

        assert parse_pregnancy_dating(data, "observer_json")["ga_by_lmp"] is None

    def test_apple_sally_has_a_placeholder_lmp_and_no_ga_by_lmp(self):
        data = (DATA_DIR / "Apple_Sally_pretty.json").read_text()

        result = parse_pregnancy_dating(data, "observer_json")

        assert result["lmp"] == "0001-01-01"
        assert result["ga_by_lmp"] is None

    def test_observer_exam_date_before_lmp_gives_no_ga(self):
        data = json.dumps({"exam": {"lmp": "2025-05-02", "exm_date": "2025-01-15"}})

        assert parse_pregnancy_dating(data, "observer_json")["ga_by_lmp"] is None

    def test_observer_lmp_without_exam_date_gives_no_ga(self):
        data = json.dumps({"exam": {"lmp": "2025-01-15"}})

        assert parse_pregnancy_dating(data, "observer_json")["ga_by_lmp"] is None

    def test_hl7_ga_by_lmp_uses_the_obr_exam_date(self):
        hl7 = (
            "OBR|1|V1|1|US^Ultrasound|||20250502140000\n"
            "OBX||DT|EpisodeHistory.LastMenstrualPeriod^LMP|1|20250115\n"
        )

        result = parse_pregnancy_dating(hl7, "viewpoint_hl7")

        assert result["ga_by_lmp"] == {"weeks": 15, "days": 2}

    def test_hl7_fixture_ga_by_lmp(self):
        hl7 = (DATA_DIR / "viewpoint_hl7_test.txt").read_text(encoding="latin-1")

        result = parse_pregnancy_dating(hl7, "viewpoint_hl7")

        # LMP 2025-10-01, OBR-7 exam date 2025-12-30: 90 days = 12w 6d
        assert result["lmp"] == "2025-10-01"
        assert result["ga_by_lmp"] == {"weeks": 12, "days": 6}

    def test_hl7_lmp_without_obr_gives_no_ga(self):
        hl7 = "OBX||DT|EpisodeHistory.LastMenstrualPeriod^LMP|1|20250115\n"

        assert parse_pregnancy_dating(hl7, "viewpoint_hl7")["ga_by_lmp"] is None
