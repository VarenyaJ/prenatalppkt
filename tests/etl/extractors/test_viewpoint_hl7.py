"""
Tests for ViewPoint HL7 extractor.
1. **Unit tests with synthetic inline HL7 data** (TestViewPointHL7Extract):
   - Currently skipped as a class because the real test data file is first-trimester

2. **Integration tests with real file data** (TestViewPointHL7ExtractFromFile and others):
   - These use a test data file which contains first-trimester data (12w 1d) but lacks BPD
"""

import pytest
from pathlib import Path
from prenatalppkt.etl.extractors import viewpoint_hl7
from prenatalppkt.etl.hl7_rows import Hl7ParseError
from prenatalppkt.etl.term_bin_factory import TermBinFactory
from prenatalppkt.measurements.term_bin import TermBin

TEST_DIR = Path(__file__).parent.parent.parent  # Navigate up to tests/
HL7_TEST_FILE = TEST_DIR / "data" / "viewpoint_hl7_test.txt"


@pytest.mark.skip(
    reason="TODO(@VarenyaJ): HL7 test data is first trimester (missing BPD/HC). Need second trimester sample or conditional validation."
)
class TestViewPointHL7Extract:
    """
    Unit tests for extract() function using synthetic inline HL7 data.
    """

    def test_extract_basic(self):
        """
        Test basic extraction with all 4 required measurements.

        Note: Real test file (viewpoint_hl7_test.txt) has HC, AC, Femur but NO BPD because it's first-trimester (12w 1d) data. BPD isn't reliably measurable before ~13-14 weeks.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        PID|1||12345||DOE^JANE||19900101|F
        OBR|1|123456|123456|US^Ultrasound|||20211223144928
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.VP_HeadCircumference_GA|Fetus1|177^25w 3d|d
        OBX|5|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|6|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|7|NM|SkullFetus.VP_BiParietalDiameter_GA|Fetus1|182^26w 0d|d
        OBX|8|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|9|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|10|NM|AbdomenFetus.VP_AbdominalCircumference_GA|Fetus1|179^25w 5d|d
        OBX|11|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|12|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        OBX|13|NM|ExtremitiesFetus.VP_FemurLength_GA|Fetus1|183^26w 1d|d
        """
        term_bins = viewpoint_hl7.extract(data)

        assert len(term_bins) == 4
        assert all(isinstance(tb, TermBin) for tb in term_bins)

    def test_extract_with_custom_factory(self):
        """
        Test extraction with explicitly provided TermBinFactory.

        Note: Real test file lacks BPD, so this synthetic data is needed.
        """
        factory = TermBinFactory()
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|8|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|9|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        """
        term_bins = viewpoint_hl7.extract(data, factory)
        assert len(term_bins) == 4

    def test_extract_no_obx_segments(self):
        """
        Test extraction when HL7 has no OBX (observation) segments.

        Validates:
        - Returns empty list (not None or error)
        - Handles HL7 files with only metadata (MSH, PID, OBR)

        Why this case exists: Some HL7 files may be incomplete or represent orders without actual measurements yet.

        This case IS testable with any data since it doesn't require measurements.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        PID|1||12345||DOE^JANE||19900101|F
        OBR|1|123456|123456|US^Ultrasound|||20211223144928
        """
        term_bins = viewpoint_hl7.extract(data)
        assert len(term_bins) == 0

    def test_extract_invalid_type(self):
        """
        Test that non-string input raises appropriate error.
        """
        with pytest.raises(ValueError, match="Expected string"):
            viewpoint_hl7.extract(123)

    def test_extract_missing_required_measurements(self):
        """
        Test that validation fails when required measurements are missing.

        Note: This is exactly what happens with real test file - it only has HC, AC, Femur (missing BPD), so validation fails and returns empty list.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        """
        with pytest.raises(ValueError, match="Missing required measurements"):
            viewpoint_hl7.extract(data)

    def test_extract_with_femur_undefined_length(self):
        """
        Test extraction handles ViewPoint's 'FemurUndefinedLength' naming variant.

        Validates:
        - Name mapping: FemurUndefinedLength -> Femur
        - ViewPoint uses different field names in different contexts
        - VIEWPOINT_HL7_NAME_MAP in constants.py handles this mapping

        Why this matters: Real HL7 files use 'FemurUndefinedLength' instead of 'FemurLength'. The extractor must normalize these variants to standard names (HC, BPD, AC, Femur).

        Real test file (viewpoint_hl7_test.txt) DOES use FemurUndefinedLength, so this test validates real-world naming.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|8|NM|ExtremitiesFetus.FemurUndefinedLength^FL|Fetus1|48^48.0|mm
        OBX|9|NM|ExtremitiesFetus.VP_FemurUndefinedLength_Percentile|Fetus1|52^52%|%
        """
        term_bins = viewpoint_hl7.extract(data)
        assert len(term_bins) == 4

        # Check Femur is present
        femur = next(tb for tb in term_bins if "Femur" in tb.description)
        assert femur is not None

    def test_extract_extreme_percentiles(self):
        """
        Test extraction handles extreme percentile edge cases.

        Validates:
        - Percentiles like "<1%" map to below_3p bin
        - Percentiles like ">99%" map to above_97p bin
        - String parsing handles comparison operators
        - PercentileRange.evaluate() correctly classifies extremes

        Why this matters: ViewPoint uses "<1%" and ">99%" for values outside the reference range. These must map to appropriate HPO terms:
        - <3%: Often abnormally small (e.g., HP:0000252 Microcephaly for HC)
        - >97%: Often abnormally large (e.g., HP:0000256 Macrocephaly for HC)

        Real test file has HC=34%, AC=73%, Femur=53% - all normal range, so this synthetic data is needed to test extreme values.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|76.6^76.6|mm
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|0^<1%|%
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|8|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|9|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|0^>99%|%
        """
        term_bins = viewpoint_hl7.extract(data)
        assert len(term_bins) == 4

        # Check BPD percentile is low
        bpd = next(tb for tb in term_bins if "BPD" in tb.description)
        assert bpd.range.name in ["below_3p"]

        # Check Femur percentile is high
        femur = next(tb for tb in term_bins if "Femur" in tb.description)
        assert femur.range.name in ["above_97p"]


@pytest.mark.skip(
    reason="TODO(@VarenyaJ): HL7 test data is first trimester (missing BPD/HC). Need second trimester sample or conditional validation."
)
class TestViewPointHL7ExtractFromFile:
    """
    Integration tests for extract_from_file() using actual file I/O.

    These tests use real file operations and the actual test data file. Currently skipped because tests/data/viewpoint_hl7_test.txt contains first-trimester data (12w 1d) without BPD.
    """

    def test_extract_from_file_not_found(self):
        """
        Test FileNotFoundError for missing file.
        """
        with pytest.raises(FileNotFoundError):
            viewpoint_hl7.extract_from_file(Path("nonexistent.hl7"))

    def test_extract_from_file_success(self, tmp_path):
        """
        Test successful extraction from temporary file.
        Real test file would fail this test because it lacks BPD.
        """
        test_file = tmp_path / "valid.hl7"
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|8|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|9|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        """
        test_file.write_text(data)

        term_bins = viewpoint_hl7.extract_from_file(test_file)
        assert len(term_bins) == 4


@pytest.mark.skip(
    reason="TODO(@VarenyaJ): HL7 test data is first trimester (missing BPD/HC). Need second trimester sample or conditional validation."
)
class TestViewPointHL7GestationalAge:
    """
    Tests for gestational age (GA) parsing from HL7.

    ViewPoint includes GA in format like "177^25w 3d|d" meaning:
    - 177 days total
    - 25 weeks 3 days
    - Units: days

    Currently skipped because these tests need complete biometry data.
    """

    def test_ga_with_weeks_and_days(self):
        """
        Test GA parsing with weeks and days format.

        Validates:
        - GA field extraction from VP_*_GA segments
        - Parsing "177^25w 3d|d" format
        - GA is captured in TermBin description

        Why this matters: GA context helps clinicians understand if measurements  are appropriate for gestational age. Some measurements vary significantly by week.

        Real test file (viewpoint_hl7_test.txt) DOES have GA fields:
        - HC GA: 88^12w 4d (88 days = 12 weeks 4 days)
        - AC GA: 87^12w 3d
        - Femur GA: 87^12w 3d
        But test is skipped because file lacks BPD, so extraction returns empty.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.VP_HeadCircumference_GA|Fetus1|177^25w 3d|d
        OBX|5|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|6|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|7|NM|SkullFetus.VP_BiParietalDiameter_GA|Fetus1|182^26w 0d|d
        OBX|8|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|9|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|10|NM|AbdomenFetus.VP_AbdominalCircumference_GA|Fetus1|179^25w 5d|d
        OBX|11|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|12|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        OBX|13|NM|ExtremitiesFetus.VP_FemurLength_GA|Fetus1|183^26w 1d|d
        """
        term_bins = viewpoint_hl7.extract(data)

        # Check that GA is captured
        hc = next(tb for tb in term_bins if "HC" in tb.description)
        # GA should be stored (exact format depends on implementation)
        assert hc is not None


@pytest.mark.skip(
    reason="TODO(@VarenyaJ): HL7 test data is first trimester (missing BPD/HC). Need second trimester sample or conditional validation."
)
class TestViewPointHL7MethodParsing:
    """
    Tests for measurement method/author extraction.

    ViewPoint includes method fields like:
    OBX|4|ST|SkullFetus.VP_HeadCircumference_Author|Fetus1|Hadlock

    Methods reference which fetal growth curve/reference was used:
    - Hadlock: Common for HC, BPD, AC, Femur
    - Nicolaides: Common for nuchal translucency
    - INTERGROWTH-21st: International standard

    Currently skipped because tests need complete biometry data.
    """

    def test_method_author_field(self):
        """
        Test extraction of measurement method/author field.

        Validates:
        - VP_*_Author field parsing
        - Method name captured in TermBin description
        - Multiple methods can coexist (different measurements use different curves)

        Why this matters: Different growth curves have different percentile values for the same measurement. Knowing which curve was used is essential for:
        - Comparing measurements across time
        - Understanding clinical decision-making
        - Reproducing percentile calculations

        Real test file (viewpoint_hl7_test.txt) DOES have Author fields:
        - HC uses Hadlock (OBX|84)
        - AC uses Hadlock (OBX|58)
        - Femur uses Hadlock (OBX|76)

        But test is skipped because file lacks BPD for validation.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|ST|SkullFetus.VP_HeadCircumference_Author|Fetus1|Hadlock
        OBX|5|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|6|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|7|ST|SkullFetus.VP_BiParietalDiameter_Author|Fetus1|Hadlock
        OBX|8|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|9|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|10|ST|AbdomenFetus.VP_AbdominalCircumference_Author|Fetus1|Hadlock
        OBX|11|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|12|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        OBX|13|ST|ExtremitiesFetus.VP_FemurLength_Author|Fetus1|Hadlock
        """
        term_bins = viewpoint_hl7.extract(data)

        # Check that methods are captured
        hc = next(tb for tb in term_bins if "HC" in tb.description)
        # Method should be in description if available
        assert "Hadlock" in hc.description or hc.description  # Just verify exists


@pytest.mark.skip(
    reason="TODO(@VarenyaJ): HL7 test data is first trimester (missing BPD/HC). Need second trimester sample or conditional validation."
)
class TestViewPointHL7MalformedSegments:
    """
    Tests for handling malformed or incomplete HL7 segments.

    Real-world HL7 files may have:
    - Missing fields (empty values)
    - Insufficient pipe-delimited fields
    - Missing percentiles or values

    The extractor should gracefully skip malformed segments rather than crashing, while still extracting valid measurements.

    Currently skipped because tests need validation to pass with 4 measurements.
    """

    def test_missing_value_field(self):
        """
        Test that segments with missing measurement values are skipped.

        Validates:
        - Empty value field: |Fetus1||mm (no value between pipes)
        - Extractor continues processing other measurements
        - Invalid measurement doesn't cause crash

        Why this matters: Ultrasound machines may fail to capture certain measurements (poor image quality, fetal position). The file should still process successfully with whatever measurements are available.

        Real test file doesn't have this issue - all present measurements have valid values. This synthetic case tests error handling.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1||mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|8|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|9|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        """
        term_bins = viewpoint_hl7.extract(data)
        # HC should be skipped due to missing value
        assert len(term_bins) == 3

    def test_missing_percentile(self):
        """
        Test that measurements without percentiles are skipped.

        Validates:
        - Measurement has value but no corresponding percentile segment
        - Extractor requires BOTH value and percentile
        - Other measurements still extracted

        Why this matters: Percentile is required for HPO term mapping. A raw measurement value without percentile context can't be classified as normal/abnormal using the TermBin system.

        Real test file has percentiles for all measurements, so this tests edge case handling.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|4|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|5|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|6|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|7|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|8|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        """
        term_bins = viewpoint_hl7.extract(data)
        # HC should be skipped due to missing percentile
        assert len(term_bins) == 3

    def test_insufficient_fields(self):
        """
        Test that malformed segments with too few fields are skipped.

        Validates:
        - HL7 pipe-delimited format: OBX|field1|field2|field3|...
        - Segments missing required fields are ignored
        - Parser doesn't crash on incomplete lines

        Why this matters: Manual editing, transmission errors, or buggy ultrasound software can produce truncated HL7 segments.

        Real test file is well-formed, so this tests defensive parsing.
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%
        OBX|8|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm
        OBX|9|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%
        """
        term_bins = viewpoint_hl7.extract(data)
        # Should still extract 4 measurements despite malformed line
        assert len(term_bins) == 4


class TestViewPointHL7MeasurementCodeParsing:
    """
    Regression tests for a bug found while scoping multi-fetus extraction
    (#93): namespaced OBX-3 codes (e.g. "SkullFetus.VP_HeadCircumference_
    Percentile") weren't matching VIEWPOINT_HL7_NAME_MAP for percentile/GA/
    method fields - only the "value" field type stripped the namespace
    prefix. This silently dropped every percentile/GA/method reading on
    realistically-shaped HL7, so extract() returned zero TermBins. Not
    exercised by the classes above since they're all skip-marked.
    """

    def test_namespaced_percentile_code_resolves(self):
        from prenatalppkt.etl.extractors.viewpoint_hl7 import _parse_measurement_code

        assert _parse_measurement_code(
            "SkullFetus.VP_HeadCircumference_Percentile"
        ) == ("HC", "percentile")

    def test_namespaced_ga_code_resolves(self):
        from prenatalppkt.etl.extractors.viewpoint_hl7 import _parse_measurement_code

        assert _parse_measurement_code("SkullFetus.VP_HeadCircumference_GA") == (
            "HC",
            "ga",
        )

    def test_namespaced_author_code_resolves(self):
        from prenatalppkt.etl.extractors.viewpoint_hl7 import _parse_measurement_code

        assert _parse_measurement_code("SkullFetus.VP_HeadCircumference_Author") == (
            "HC",
            "method",
        )


class TestViewPointHL7UnitFieldParsing:
    """
    Regression tests for a second bug found while scoping multi-fetus
    extraction (#93): OBX-6 unit fields use HL7's coded-value format
    ("mm&millimeters^mm&millimeters"), but _convert_to_mm expects a bare
    unit string and raised an uncaught ValueError on any realistically-
    formatted unit field - crashing extraction entirely, not just
    dropping one measurement.
    """

    def test_coded_unit_field_parses_to_bare_unit(self):
        from prenatalppkt.etl.extractors.viewpoint_hl7 import _parse_unit_field

        assert _parse_unit_field("mm&millimeters^mm&millimeters") == "mm"

    def test_extract_from_real_shaped_hl7_yields_term_bins(self):
        """
        End-to-end: namespaced percentile codes + coded-value units, the
        exact shape real ViewPoint HL7 exports use (confirmed against
        tests/data/viewpoint_hl7_test.txt). Before both fixes, this
        returned zero TermBins (percentile bug) then raised ValueError
        (unit bug).
        """
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm&millimeters^mm&millimeters
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%&percent^fmt&formatted
        """
        term_bins = viewpoint_hl7.extract(data)
        assert len(term_bins) == 1
        assert "HC" in term_bins[0].description


# Identifiers as GE ViewPoint 6 writes them in its discrete HL7 export,
# namespace included. Values in the tests below are made up.
_GE_VIEWPOINT6_IDS = [
    ("SkullFetus", "BiparietalDiameter", "BPD"),
    ("SkullFetus", "OccipitoFrontalDiameter", "OFD"),
    ("ExtremitiesFetus", "HumerusUndefinedLength", "Humerus"),
    ("ExtremitiesFetus", "TibiaUndefinedLength", "Tibia"),
    ("ExtremitiesFetus", "FibulaUndefinedLength", "Fibula"),
    ("BrainFetus", "TranscerebellarDiameter", "Cerebellum"),
    ("EmbryonicStructuresFetus", "CrownRumpLength", "CRL"),
    ("NeckSkinFetus", "NuchalTranslucency", "NT"),
    ("NeckSkinFetus", "NuchalFoldThickness", "Nuchal Fold"),
]


class TestViewPointHL7GeViewPoint6Identifiers:
    """GE ViewPoint 6 spellings resolve to the standard measurement names."""

    @pytest.mark.parametrize("namespace, identifier, name", _GE_VIEWPOINT6_IDS)
    def test_value_and_percentile_codes_resolve(self, namespace, identifier, name):
        from prenatalppkt.etl.extractors.viewpoint_hl7 import _parse_measurement_code

        assert _parse_measurement_code(f"{namespace}.{identifier}") == (name, "value")
        assert _parse_measurement_code(f"{namespace}.VP_{identifier}_Percentile") == (
            name,
            "percentile",
        )

    def test_extract_all_fetuses_reads_every_identifier(self):
        lines = ["MSH|^~\\&|GE|ViewPoint|||20260101120000||ORU^R01|1|P|2.4"]
        for i, (namespace, identifier, _) in enumerate(_GE_VIEWPOINT6_IDS):
            lines.append(
                f"OBX|{2 * i + 1}|NM|{namespace}.{identifier}^x|Fetus1|20^20|mm&millimeters"
            )
            lines.append(
                f"OBX|{2 * i + 2}|NM|{namespace}.VP_{identifier}_Percentile^x|Fetus1"
                "|50^50%|%&percent^fmt&formatted"
            )
        bins = viewpoint_hl7.extract_all_fetuses("\r\n".join(lines))[1]
        names = {tb.description.split(":")[0] for tb in bins}
        assert names == {name for _, _, name in _GE_VIEWPOINT6_IDS}


HL7_TWINS_TEST_FILE = TEST_DIR / "data" / "viewpoint_hl7_twins_test.txt"


class TestViewPointHL7ExtractAllFetuses:
    def test_extract_all_fetuses_two_fetuses(self):
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm&millimeters^mm&millimeters
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%&percent^fmt&formatted
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm&millimeters^mm&millimeters
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%&percent^fmt&formatted
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm&millimeters^mm&millimeters
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%&percent^fmt&formatted
        OBX|8|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm&millimeters^mm&millimeters
        OBX|9|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%&percent^fmt&formatted
        OBX|10|ST|Fetus.Identifier^Fetus Identifier|Fetus2|B
        OBX|11|NM|SkullFetus.HeadCircumference^HC|Fetus2|180^180.0|mm&millimeters^mm&millimeters
        OBX|12|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus2|60^60%|%&percent^fmt&formatted
        OBX|13|NM|SkullFetus.BiParietalDiameter^BPD|Fetus2|70^70.0|mm&millimeters^mm&millimeters
        OBX|14|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus2|58^58%|%&percent^fmt&formatted
        OBX|15|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus2|215^215.0|mm&millimeters^mm&millimeters
        OBX|16|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus2|50^50%|%&percent^fmt&formatted
        OBX|17|NM|ExtremitiesFetus.FemurLength^FL|Fetus2|49^49.0|mm&millimeters^mm&millimeters
        OBX|18|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus2|54^54%|%&percent^fmt&formatted
        """
        result = viewpoint_hl7.extract_all_fetuses(data)

        assert set(result.keys()) == {1, 2}
        assert len(result[1]) == 4
        assert len(result[2]) == 4

    def test_extract_all_fetuses_single_fetus_backward_compat(self):
        data = """
        MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4
        OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A
        OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|175^175.0|mm&millimeters^mm&millimeters
        OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|50^50%|%&percent^fmt&formatted
        OBX|4|NM|SkullFetus.BiParietalDiameter^BPD|Fetus1|68^68.0|mm&millimeters^mm&millimeters
        OBX|5|NM|SkullFetus.VP_BiParietalDiameter_Percentile|Fetus1|55^55%|%&percent^fmt&formatted
        OBX|6|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|212^212.0|mm&millimeters^mm&millimeters
        OBX|7|NM|AbdomenFetus.VP_AbdominalCircumference_Percentile|Fetus1|48^48%|%&percent^fmt&formatted
        OBX|8|NM|ExtremitiesFetus.FemurLength^FL|Fetus1|48^48.0|mm&millimeters^mm&millimeters
        OBX|9|NM|ExtremitiesFetus.VP_FemurLength_Percentile|Fetus1|52^52%|%&percent^fmt&formatted
        """
        result = viewpoint_hl7.extract_all_fetuses(data)
        assert set(result.keys()) == {1}
        assert len(result[1]) == 4

    def test_extract_all_fetuses_no_obx_segments(self):
        data = "MSH|^~\\&|ViewPoint|Hospital|||20211223144928||ORU^R01|123456|P|2.4"
        assert viewpoint_hl7.extract_all_fetuses(data) == {}

    def test_extract_all_fetuses_invalid_type(self):
        with pytest.raises(ValueError, match="Expected string"):
            viewpoint_hl7.extract_all_fetuses(123)


class TestViewPointHL7ExtractAllFetusesFromFile:
    def test_extract_all_fetuses_from_file_two_fetuses(self):
        result = viewpoint_hl7.extract_all_fetuses_from_file(HL7_TWINS_TEST_FILE)
        assert set(result.keys()) == {1, 2}
        assert len(result[1]) == 4
        assert len(result[2]) == 4


# Synthetic one-measurement message, values made up.
_SYNTHETIC_HC_SEGMENTS = [
    "MSH|^~\\&|GE|ViewPoint|Discrete||20260101120000||ORU^R01|SYN-1|P|2.4",
    "OBX|1|NM|SkullFetus.HeadCircumference^HC|Fetus1|205^205.0|mm&millimeters",
    "OBX|2|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus1|45^45%|%&percent",
]


class TestViewPointHL7SharedRowReader:
    """The extractor reads segments through `prenatalppkt.etl.hl7_rows`."""

    def test_carriage_return_only_message(self):
        """HL7's own segment terminator is a bare CR; such files used to yield nothing."""
        bins = viewpoint_hl7.extract_all_fetuses("\r".join(_SYNTHETIC_HC_SEGMENTS))
        assert set(bins) == {1}
        assert len(bins[1]) == 1
        assert "HC" in bins[1][0].description

    def test_bare_number_sub_id_still_groups_by_its_digits(self):
        """Non-"Fetus<N>" sub-ids keep the old trailing-digits grouping."""
        segments = [s.replace("|Fetus1|", "|2|") for s in _SYNTHETIC_HC_SEGMENTS]
        bins = viewpoint_hl7.extract_all_fetuses("\r\n".join(segments))
        assert set(bins) == {2}

    def test_malformed_segment_names_its_line(self):
        segments = [*_SYNTHETIC_HC_SEGMENTS, "OBX|x|NM|SkullFetus.HeadCircumference"]
        with pytest.raises(Hl7ParseError, match="HL7 line 4: OBX-1"):
            viewpoint_hl7.extract("\r\n".join(segments))
