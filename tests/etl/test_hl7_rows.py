"""
Tests for the typed HL7 OBX row reader (`prenatalppkt.etl.hl7_rows`).

Every message below is synthetic: made-up identifiers, values and
timestamps, shaped like a GE ViewPoint 6 discrete export.
"""

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from prenatalppkt.etl.hl7_rows import (
    DecodedHl7,
    Hl7Encoding,
    Hl7EncodingError,
    Hl7ParseError,
    decode_hl7_bytes,
    read_hl7_rows,
)

TWINS_FIXTURE = Path(__file__).parent.parent / "data" / "viewpoint_hl7_twins_test.txt"

MSH = "MSH|^~\\&|GE|ViewPoint|Discrete||20260101120000||ORU^R01|SYN-1|P|2.4"

# One message: header, two non-OBX segments, then four OBX rows.
SYNTHETIC_MESSAGE = [
    MSH,
    "PID|||SYN0001^^^MRN||Synthetic^Test",
    "OBR|1|SYNVISIT|900",
    "OBX|1|ST|Fetus.Identifier^Fetus Identifier|Fetus1|A|||||||||20260101120000",
    "OBX|2|NM|SkullFetus.HeadCircumference^HC|Fetus1|205^205.0"
    "|mm&millimeters^mm&millimeters|||||F|||20260101120000",
    "OBX|3|NM|SkullFetus.VP_HeadCircumference_Percentile|Fetus2|45^45%"
    "|%&percent^fmt&formatted||||||||20260101120000",
    "OBX|4|ST|ExamStateHistory.State^State|2|done",
]


def _rows(lines, separator="\r\n"):
    return read_hl7_rows(separator.join(lines))


class TestRowFields:
    """Each OBX field lands, split and typed, on the row."""

    def test_one_row_per_obx_segment(self):
        rows = _rows(SYNTHETIC_MESSAGE)
        assert [row.set_id for row in rows] == [1, 2, 3, 4]

    def test_measurement_row(self):
        row = _rows(SYNTHETIC_MESSAGE)[1]
        assert row.value_type == "NM"
        assert row.observation_id == "SkullFetus.HeadCircumference"
        assert row.observation_text == "HC"
        assert row.namespace == "SkullFetus"
        assert row.field_id == "HeadCircumference"
        assert row.sub_id == "Fetus1"
        assert row.fetus_number == 1
        assert row.value == "205^205.0"
        assert row.value_components == ("205", "205.0")
        assert row.units == "mm&millimeters^mm&millimeters"
        assert row.unit_code == "mm"
        assert row.result_status == "F"
        assert row.observed_at == datetime(2026, 1, 1, 12, 0, 0)

    def test_companion_row_without_label(self):
        row = _rows(SYNTHETIC_MESSAGE)[2]
        assert row.field_id == "VP_HeadCircumference_Percentile"
        assert row.observation_text == ""
        assert row.fetus_number == 2
        assert row.value_components == ("45", "45%")
        assert row.unit_code == "%"

    def test_provenance(self):
        rows = _rows(SYNTHETIC_MESSAGE)
        assert [row.line_number for row in rows] == [4, 5, 6, 7]
        # MSH, PID and OBR are segments 1-3 of the message.
        assert [row.segment_index for row in rows] == [4, 5, 6, 7]
        assert {row.message_index for row in rows} == {1}
        assert {row.message_control_id for row in rows} == {"SYN-1"}

    def test_rows_are_frozen(self):
        row = _rows(SYNTHETIC_MESSAGE)[0]
        with pytest.raises(dataclasses.FrozenInstanceError):
            row.value = "changed"


class TestSubIdAndNamespace:
    def test_bare_counter_is_not_a_fetus(self):
        """Exam-level groups number their repeats in OBX-4 ("1", "2", ...)."""
        row = _rows(SYNTHETIC_MESSAGE)[3]
        assert row.sub_id == "2"
        assert row.fetus_number is None

    @pytest.mark.parametrize(
        "sub_id, fetus_number",
        [("Fetus1", 1), ("Fetus3", 3), ("Fetus12", 12), ("", None), ("FetusA", None)],
    )
    def test_fetus_number(self, sub_id, fetus_number):
        rows = _rows([MSH, f"OBX|1|ST|Fetus.Identifier^Fetus Identifier|{sub_id}|A"])
        assert rows[0].fetus_number == fetus_number

    def test_identifier_without_namespace(self):
        rows = _rows([MSH, "OBX|1|ST|Remarks^Remarks||free text"])
        assert rows[0].namespace is None
        assert rows[0].field_id == "Remarks"

    def test_site_form_keeps_its_own_namespace(self):
        """A site form's field no longer looks like the real field of the same name."""
        rows = _rows(
            [
                MSH,
                "OBX|1|NM|AbdomenFetus.AbdominalCircumference^AC|Fetus1|168^168.0|mm",
                "OBX|2|ST|U_SiteForm_F_0000.AbdominalCircumference^AC|Fetus1|168",
            ]
        )
        assert [row.field_id for row in rows] == ["AbdominalCircumference"] * 2
        assert [row.namespace for row in rows] == ["AbdomenFetus", "U_SiteForm_F_0000"]

    def test_namespace_splits_on_first_dot(self):
        rows = _rows([MSH, "OBX|1|ST|Outer.Inner.Leaf^x|Fetus1|v"])
        assert rows[0].namespace == "Outer"
        assert rows[0].field_id == "Inner.Leaf"


class TestLayout:
    """Line endings, blank lines, indentation and multiple messages."""

    @pytest.mark.parametrize("separator", ["\r", "\r\n", "\n"])
    def test_any_line_ending(self, separator):
        rows = _rows(SYNTHETIC_MESSAGE, separator)
        assert [row.observation_id for row in rows] == [
            "Fetus.Identifier",
            "SkullFetus.HeadCircumference",
            "SkullFetus.VP_HeadCircumference_Percentile",
            "ExamStateHistory.State",
        ]

    def test_blank_lines_and_indentation(self):
        text = "\n    " + "\n\n    ".join(SYNTHETIC_MESSAGE) + "\n    "
        rows = read_hl7_rows(text)
        assert len(rows) == 4
        # Blank lines still count toward the line number.
        assert rows[0].line_number == 8

    def test_byte_order_mark(self):
        rows = read_hl7_rows("\ufeff" + "\r".join(SYNTHETIC_MESSAGE))
        assert len(rows) == 4

    def test_no_obx_segments(self):
        assert _rows([MSH, "PID|||SYN0001^^^MRN"]) == []

    def test_empty_input(self):
        assert read_hl7_rows("") == []

    def test_dropped_trailing_fields_read_as_empty(self):
        rows = _rows([MSH, "OBX|1|ST|Fetus.Identifier"])
        assert rows[0].observation_text == ""
        assert rows[0].sub_id == ""
        assert rows[0].value == ""
        assert rows[0].units == ""
        assert rows[0].observed_at is None

    def test_empty_set_id(self):
        assert _rows([MSH, "OBX||ST|Fetus.Identifier^x|Fetus1|A"])[0].set_id is None

    def test_several_messages(self):
        second_msh = MSH.replace("SYN-1", "SYN-2")
        rows = _rows(
            [
                MSH,
                "OBX|1|ST|Fetus.Identifier^x|Fetus1|A",
                second_msh,
                "PID|||SYN0002^^^MRN",
                "OBX|1|ST|Fetus.Identifier^x|Fetus1|A",
            ]
        )
        assert [row.message_index for row in rows] == [1, 2]
        assert [row.message_control_id for row in rows] == ["SYN-1", "SYN-2"]
        assert [row.segment_index for row in rows] == [2, 3]

    def test_message_declared_delimiters(self):
        """Delimiters come from MSH-1/MSH-2, not from a fixed assumption."""
        rows = _rows(
            [
                "MSH#*~\\%#GE#ViewPoint#Discrete##20260101120000##ORU*R01#SYN-3#P#2.4",
                "OBX#1#NM#SkullFetus.HeadCircumference*HC#Fetus1#205*205.0"
                "#mm%millimeters*mm%millimeters",
            ]
        )
        assert rows[0].encoding == Hl7Encoding("#", "*", "~", "\\", "%")
        assert rows[0].observation_text == "HC"
        assert rows[0].value_components == ("205", "205.0")
        assert rows[0].unit_code == "mm"
        assert rows[0].message_control_id == "SYN-3"


class TestObservationTime:
    def _observed_at(self, raw):
        return _rows([MSH, f"OBX|1|ST|Fetus.Identifier^x|Fetus1|A|||||||||{raw}"])[
            0
        ].observed_at

    def test_full_precision(self):
        assert self._observed_at("20260101120530") == datetime(2026, 1, 1, 12, 5, 30)

    def test_date_only_is_midnight(self):
        assert self._observed_at("20260101") == datetime(2026, 1, 1)

    def test_fraction_of_a_second(self):
        assert self._observed_at("20260101120530.25") == datetime(
            2026, 1, 1, 12, 5, 30, 250000
        )

    def test_offset_makes_it_timezone_aware(self):
        assert self._observed_at("202601011205-0500") == datetime(
            2026, 1, 1, 12, 5, tzinfo=timezone(-timedelta(hours=5))
        )


class TestMalformedSegments:
    """Malformed input raises Hl7ParseError naming the line, never its contents."""

    @pytest.mark.parametrize(
        "lines, line_number, reason",
        [
            (["OBX|1|ST|Fetus.Identifier^x|Fetus1|A"], 1, "before any MSH"),
            ([MSH, "this is not a segment"], 2, "not an HL7 segment"),
            ([MSH, "obx|1|ST|Fetus.Identifier^x|Fetus1|A"], 2, "not an HL7 segment"),
            ([MSH, "OBX 1 ST"], 2, "not an HL7 segment"),
            ([MSH, "OBX|one|ST|Fetus.Identifier^x|Fetus1|A"], 2, "OBX-1"),
            ([MSH, "OBX|1|ST||Fetus1|A"], 2, "OBX-3"),
            ([MSH, "OBX|1|ST|^Label only|Fetus1|A"], 2, "OBX-3"),
            ([MSH, "OBX|1|ST|F.I^x|Fetus1|A|||||||||2026-01-01"], 2, "OBX-14"),
            ([MSH, "OBX|1|ST|F.I^x|Fetus1|A|||||||||20261301"], 2, "OBX-14"),
            (["MSH|^~|GE|ViewPoint"], 1, "MSH-2"),
            (["MSH|^^\\&|GE|ViewPoint"], 1, "MSH-2"),
            (["MSH"], 1, "MSH header"),
        ],
    )
    def test_reports_line_and_reason(self, lines, line_number, reason):
        with pytest.raises(Hl7ParseError, match=reason) as caught:
            _rows(lines)
        assert caught.value.line_number == line_number
        assert str(caught.value).startswith(f"HL7 line {line_number}:")

    def test_message_does_not_echo_contents(self):
        with pytest.raises(Hl7ParseError) as caught:
            _rows([MSH, "OBX|SECRET|ST|Fetus.Identifier^x|Fetus1|A"])
        assert "SECRET" not in str(caught.value)

    def test_is_a_value_error(self):
        with pytest.raises(ValueError):
            _rows(["not hl7 at all"])


class TestCommittedFixture:
    def test_twins_fixture(self):
        rows = read_hl7_rows(TWINS_FIXTURE.read_text(encoding="utf-8"))
        assert len(rows) == 34
        assert {row.fetus_number for row in rows} == {1, 2}
        assert {row.value_type for row in rows} == {"NM", "ST"}
        assert all(row.observed_at is not None for row in rows)


def _export_text(charset_field, text_value):
    """Synthetic export: MSH declaring `charset_field` in MSH-18, one ST row.

    Tests encode it with whichever codec they need.
    """
    msh = "MSH|^~\\&|GE|ViewPoint|Discrete||20260101120000||ORU^R01|SYN-1|P|2.4"
    msh += f"|||AL|NE||{charset_field}"
    return f"{msh}\r\nOBX|1|ST|ExamAddData.Comment^Comment||{text_value}\r\n"


class TestDecodeHl7Bytes:
    """UTF-8 first; the MSH-18 charset only when UTF-8 fails."""

    def test_valid_utf8_wins_over_latin9_declaration(self):
        raw = _export_text("8859/15", "caf\u00e9 \u20ac").encode("utf-8")
        decoded = decode_hl7_bytes(raw)
        assert decoded == DecodedHl7(
            text=raw.decode("utf-8"), encoding="utf-8", declared_charset="8859/15"
        )
        assert read_hl7_rows(decoded.text)[0].value == "caf\u00e9 \u20ac"

    def test_invalid_utf8_falls_back_to_declared_latin9(self):
        # 0xE9 alone is not UTF-8; 0xA4 is the euro sign in ISO 8859-15
        # (it would be the generic currency sign in ISO 8859-1).
        raw = _export_text("8859/15", "caf\u00e9 \u20ac").encode("iso8859_15")
        with pytest.raises(UnicodeDecodeError):
            raw.decode("utf-8")
        decoded = decode_hl7_bytes(raw)
        assert decoded.encoding == "iso8859_15"
        assert decoded.declared_charset == "8859/15"
        assert read_hl7_rows(decoded.text)[0].value == "caf\u00e9 \u20ac"

    def test_invalid_utf8_falls_back_to_declared_latin1(self):
        raw = _export_text("8859/1", "caf\u00e9").encode("latin-1")
        decoded = decode_hl7_bytes(raw)
        assert decoded.encoding == "latin-1"
        assert read_hl7_rows(decoded.text)[0].value == "caf\u00e9"

    def test_first_repetition_of_charset_field(self):
        raw = _export_text("8859/15~UNICODE UTF-8", "caf\u00e9").encode("iso8859_15")
        assert decode_hl7_bytes(raw).encoding == "iso8859_15"

    def test_utf8_byte_order_mark(self):
        raw = b"\xef\xbb\xbf" + _export_text("8859/15", "x").encode("utf-8")
        decoded = decode_hl7_bytes(raw)
        assert decoded.encoding == "utf-8"
        assert decoded.declared_charset == "8859/15"
        assert len(read_hl7_rows(decoded.text)) == 1

    def test_unknown_declared_charset_is_named(self):
        raw = _export_text("SYNTHETIC/99", "caf\u00e9").encode("latin-1")
        with pytest.raises(Hl7EncodingError, match="'SYNTHETIC/99'") as caught:
            decode_hl7_bytes(raw)
        assert caught.value.declared_charset == "SYNTHETIC/99"
        assert "caf" not in str(caught.value)

    def test_missing_declaration(self):
        raw = _export_text("", "caf\u00e9").encode("latin-1")
        with pytest.raises(Hl7EncodingError, match="no charset declared"):
            decode_hl7_bytes(raw)

    def test_unknown_declaration_is_fine_when_utf8_decodes(self):
        decoded = decode_hl7_bytes(_export_text("SYNTHETIC/99", "x").encode())
        assert decoded.encoding == "utf-8"
        assert decoded.declared_charset == "SYNTHETIC/99"

    def test_is_a_value_error(self):
        with pytest.raises(ValueError):
            decode_hl7_bytes(b"MSH|^~\\&|GE\r\nOBX|1|ST|A.B||\xff")

    def test_committed_fixture_declares_latin9(self):
        decoded = decode_hl7_bytes(TWINS_FIXTURE.read_bytes())
        assert decoded.encoding == "utf-8"
        assert decoded.declared_charset == "8859/15"
