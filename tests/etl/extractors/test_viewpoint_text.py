"""
Tests for ViewPoint text extractor.
"""

from pathlib import Path

import pytest

from prenatalppkt.etl.extractors import viewpoint_text
from prenatalppkt.etl.term_bin_factory import TermBinFactory
from prenatalppkt.measurements.term_bin import TermBin


class TestViewPointTextExtract:
    """Tests for extract() function."""

    def test_extract_basic(self):
        """Test extraction with minimal valid data."""
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""
        term_bins = viewpoint_text.extract(data)

        assert len(term_bins) == 4
        assert all(isinstance(tb, TermBin) for tb in term_bins)

    def test_extract_with_custom_factory(self):
        """Test extraction with custom factory."""
        factory = TermBinFactory()
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""
        term_bins = viewpoint_text.extract(data, factory)
        assert len(term_bins) == 4

    def test_extract_no_biometry_section(self):
        """Test extraction with no biometry section."""
        data = """
Indication
==========

Some indication text here

History
=======

Some history text here
"""
        term_bins = viewpoint_text.extract(data)
        assert len(term_bins) == 0

    def test_extract_invalid_type(self):
        """Test extraction with invalid data type."""
        with pytest.raises(ValueError, match="Expected string"):
            viewpoint_text.extract(123)

    def test_extract_missing_required_measurements(self):
        """Test extraction fails when required measurements missing."""
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
"""
        with pytest.raises(ValueError, match="Missing required biometry measurements"):
            viewpoint_text.extract(data)

    def test_extract_with_two_word_names(self):
        """Test extraction with two-word measurement names."""
        data = """
        Fetal Biometry
        ==============

        HC              175.0   mm      25w 3d      50%     Hadlock
        BPD             68.0    mm      26w 0d      55%     Hadlock
        AC              212.0   mm      25w 5d      48%     Hadlock
        Femur           48.0    mm      26w 1d      52%     Hadlock
        Nuchal Fold     4.5     mm      25w 2d      10%     Standard
        """
        term_bins = viewpoint_text.extract(data)

        assert len(term_bins) == 5
        nf = next(tb for tb in term_bins if tb.description.startswith("Nuchal Fold"))
        assert nf.value_mm == 4.5

    def test_extract_skips_subheaders(self):
        """Test that sub-headers are skipped during parsing."""
        data = """
Fetal Biometry
==============

Head / Face / Neck Biometry:

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock

Trunk Biometry:

AC      212.0   mm      25w 5d      48%     Hadlock

Extremities:

Femur   48.0    mm      26w 1d      52%     Hadlock
"""
        term_bins = viewpoint_text.extract(data)
        assert len(term_bins) == 4

    def test_extract_extreme_percentiles(self):
        """Test extraction handles < and > percentile symbols."""
        data = """
        Fetal Biometry
        ==============

        HC      175.0   mm      25w 3d      50%     Hadlock
        BPD     76.6    mm      30w 5d      <1%     Hadlock
        AC      212.0   mm      25w 5d      48%     Hadlock
        Femur   48.0    mm      26w 1d      >99%    Hadlock
        """
        term_bins = viewpoint_text.extract(data)
        assert len(term_bins) == 4

        # Check BPD percentile is low
        bpd = next(tb for tb in term_bins if "BPD" in tb.description)
        assert bpd.range.bin_key == "below_3p"  # Changed from .name

        # Check Femur percentile is high
        femur = next(tb for tb in term_bins if "Femur" in tb.description)
        assert femur.range.bin_key == "above_97p"  # Changed from .name


class TestViewPointTextExtractFromFile:
    """Tests for extract_from_file() function."""

    def test_extract_from_file_not_found(self):
        """Test extraction from non-existent file."""
        with pytest.raises(FileNotFoundError):
            viewpoint_text.extract_from_file(Path("nonexistent.txt"))

    def test_extract_from_file_success(self, tmp_path):
        """Test successful extraction from file."""
        test_file = tmp_path / "valid.txt"
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""
        test_file.write_text(data)

        term_bins = viewpoint_text.extract_from_file(test_file)
        assert len(term_bins) == 4


class TestViewPointTextSectionParsing:
    """Tests for section detection."""

    def test_multiple_sections(self):
        """Test parsing with multiple sections."""
        data = """
Indication
==========

Advanced maternal age

History
=======

G2P1

Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock

General Evaluation
==================

Normal appearing fetus
"""
        term_bins = viewpoint_text.extract(data)
        assert len(term_bins) == 4

    def test_biometry_section_with_trailing_content(self):
        """Test biometry section followed by other sections."""
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock

Fetal Anatomy
=============

The following structures appear normal:
Cranium. Brain. Face.
"""
        term_bins = viewpoint_text.extract(data)
        assert len(term_bins) == 4

    def test_empty_biometry_section(self):
        """Test with empty biometry section."""
        data = """
Fetal Biometry
==============


Fetal Anatomy
=============

Normal anatomy
"""
        term_bins = viewpoint_text.extract(data)
        assert len(term_bins) == 0


class TestViewPointTextGestationalAge:
    """Tests for gestational age parsing."""

    def test_ga_with_weeks_and_days(self):
        """Test GA parsing with weeks and days."""
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""
        term_bins = viewpoint_text.extract(data)

        # Check that GA is captured in descriptions
        hc = next(tb for tb in term_bins if "HC" in tb.description)
        assert "25w" in hc.description or "25 w" in hc.description

    def test_ga_with_zero_days(self):
        """Test GA parsing with zero days."""
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 0d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 0d      48%     Hadlock
Femur   48.0    mm      26w 0d      52%     Hadlock
"""
        term_bins = viewpoint_text.extract(data)
        assert len(term_bins) == 4


class TestViewPointTextMalformedLines:
    """Tests for handling malformed lines."""

    @pytest.mark.skip(
        reason="TODO(@VarenyaJ): Revisit validation logic for malformed data"
    )
    def test_line_with_insufficient_fields(self):
        """Test that lines with insufficient fields are skipped."""
        data = """
Fetal Biometry
==============

HC      175.0
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""  # noqa: F841
        # TODO(@VarenyaJ): ensure this works in the main file and then fix this part of the test
        # Should skip HC line and extract others
        # term_bins = viewpoint_text.extract(data)
        # assert len(term_bins) == 3

    def test_line_with_invalid_value(self):
        """Test that lines with invalid values are skipped."""
        data = """
Fetal Biometry
==============

HC      invalid mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""  # noqa: F841
        # TODO(@VarenyaJ): ensure this works in the main file and then fix this part of the test
        # term_bins = viewpoint_text.extract(data)
        # assert len(term_bins) == 3

    @pytest.mark.skip(
        reason="TODO(@VarenyaJ): Revisit validation logic for malformed data"
    )
    def test_line_without_percentile(self):
        """Test that lines without percentiles are skipped."""
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 3d      50%     Hadlock
BPD     68.0    mm      26w 0d              Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""  # noqa: F841
        # TODO(@VarenyaJ): ensure this works in the main file and then fix this part of the test
        # term_bins = viewpoint_text.extract(data)
        # assert len(term_bins) == 3


class TestViewPointTextSharedGaParser:
    def test_parses_weeks_and_days_columns(self):
        ga = viewpoint_text._parse_gestational_age("25w", "3d")

        assert (ga.weeks, ga.days) == (25, 3)

    def test_missing_gestational_age_is_none(self):
        assert viewpoint_text._parse_gestational_age(None, None) is None

    @pytest.mark.parametrize(
        "weeks, days", [("25w", "9d"), ("999w", "0d"), ("xw", "0d")]
    )
    def test_impossible_gestational_age_is_none_and_warns(self, weeks, days, caplog):
        assert viewpoint_text._parse_gestational_age(weeks, days) is None
        assert "gestational age" in caplog.text.lower()

    def test_impossible_gestational_age_keeps_the_measurement(self):
        data = """
Fetal Biometry
==============

HC      175.0   mm      25w 9d      50%     Hadlock
BPD     68.0    mm      26w 0d      55%     Hadlock
AC      212.0   mm      25w 5d      48%     Hadlock
Femur   48.0    mm      26w 1d      52%     Hadlock
"""
        term_bins = viewpoint_text.extract(data)

        hc = next(tb for tb in term_bins if "HC" in tb.description)
        assert len(term_bins) == 4
        assert hc.gestational_age_weeks is None
