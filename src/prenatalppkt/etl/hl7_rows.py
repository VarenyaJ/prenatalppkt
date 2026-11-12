"""
Typed reader for the OBX rows of a ViewPoint HL7 v2 export.

A ViewPoint discrete export is an HL7 v2 ``ORU^R01`` message: an ``MSH``
header, patient/order segments (``PID``, ``PV1``, ``OBR``, ...) and then one
``OBX`` segment per recorded value - a measurement, one of its companions
(``VP_<X>_Percentile``, ``VP_<X>_GA``, ...), a drop-down answer or a free-text
box. Every reader that needs those values used to split the raw lines on
``|`` and ``^`` by itself. This module does that splitting once, at the
boundary, and hands back one frozen :class:`Hl7Row` per OBX segment.

Parse, don't validate: :func:`read_hl7_rows` either returns rows whose fields
are already split, typed and checked (integer set id, parsed fetus number,
parsed observation time), or raises :class:`Hl7ParseError` naming the line
and the reason. Downstream code can rely on a row's existence instead of
re-checking field counts.

What the reader does not do, on purpose:

- It does not interpret values. ``value`` is OBX-5 exactly as sent, with its
  components kept (``"205^205.0"``, ``"45^45%"``); turning that into a number,
  a percentile or a gestational age belongs to the code that knows what the
  field means.
- It does not decode HL7 escape sequences (``\\T\\``, ``\\F\\``, ...), so the
  text stays byte-for-byte comparable with the export.
- It does not decide which rows matter. Every OBX row is returned, including
  site-specific forms (``U_*`` namespaces); callers filter by
  ``namespace``/``field_id``.

Error messages name the line number, segment and HL7 field position but never
echo field contents: exports carry patient data, and these messages end up in
logs and bug reports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Segment terminators seen in exports: HL7's own carriage return, CRLF from
# Windows tools, and bare line feeds from files edited by hand.
_LINE_BREAK = re.compile(r"\r\n|\r|\n")

# Any segment id: three characters, a capital letter first (``MSH``, ``OBX``,
# ``ZED``, ...).
_SEGMENT_ID = re.compile(r"[A-Z][A-Z0-9]{2}")

# OBX-4 sub-id naming a fetus: ViewPoint writes "Fetus1", "Fetus2", ... on
# every per-fetus row. Exam-level groups reuse OBX-4 for their own counters
# (bare "1", "2", "3" on repeated history entries), so a bare number is not
# read as a fetus.
_FETUS_SUB_ID = re.compile(r"Fetus(\d+)")

# HL7 v2 date/time (DTM/TS): YYYY[MM[DD[HH[MM[SS[.S[S[S[S]]]]]]]]][+/-ZZZZ].
_HL7_TIMESTAMP = re.compile(
    r"(?P<year>\d{4})"
    r"(?:(?P<month>\d{2})"
    r"(?:(?P<day>\d{2})"
    r"(?:(?P<hour>\d{2})"
    r"(?:(?P<minute>\d{2})"
    r"(?:(?P<second>\d{2})"
    r"(?:\.(?P<fraction>\d{1,4}))?"
    r")?)?)?)?)?"
    r"(?P<offset>[+-]\d{4})?"
)

# OBX field positions (HL7 v2.4 numbering) read into a row. Shorter segments
# are padded: HL7 lets a sender drop trailing empty fields.
_OBX_SET_ID = 1
_OBX_VALUE_TYPE = 2
_OBX_IDENTIFIER = 3
_OBX_SUB_ID = 4
_OBX_VALUE = 5
_OBX_UNITS = 6
_OBX_RESULT_STATUS = 11
_OBX_OBSERVED_AT = 14

# MSH-10, the message control id. MSH-1 *is* the field separator, so after
# splitting an MSH line on it, MSH-n sits at index n - 1.
_MSH_CONTROL_ID_INDEX = 9


class Hl7ParseError(ValueError):
    """An HL7 export line that cannot be read as a well-formed segment.

    Subclasses ``ValueError`` so existing callers that already catch
    ``ValueError`` for bad input keep working.

    Attributes:
        line_number: 1-based line of the input where the problem is.
        reason: What is wrong, without the line's contents.
    """

    def __init__(self, line_number: int, reason: str) -> None:
        self.line_number = line_number
        self.reason = reason
        super().__init__(f"HL7 line {line_number}: {reason}")


@dataclass(frozen=True)
class Hl7Encoding:
    """The delimiters a message declares in MSH-1 and MSH-2.

    Almost every sender uses the defaults below, but HL7 lets each message
    choose its own, so rows carry the ones their message declared.
    """

    field: str = "|"
    component: str = "^"
    repetition: str = "~"
    escape: str = "\\"
    subcomponent: str = "&"


@dataclass(frozen=True)
class Hl7Row:
    """One OBX segment of a ViewPoint HL7 export, split and typed.

    Attributes:
        message_index: 1-based position of the row's message in the input (a
            file may hold several ``MSH``-headed messages).
        message_control_id: MSH-10 of that message, ``""`` when absent.
        segment_index: 1-based position of the segment within its message,
            counting every segment (the ``MSH`` header is 1).
        line_number: 1-based line of the input the segment came from, for
            error reports and drift reports that point back to the source.
        set_id: OBX-1, or ``None`` when the sender left it empty.
        value_type: OBX-2 as sent (``"NM"``, ``"ST"``, ``"DT"``, ...).
        observation_id: OBX-3 first component, namespace included
            (``"SkullFetus.HeadCircumference"``). Never empty.
        observation_text: OBX-3 second component (``"HC"``), ``""`` if absent.
        sub_id: OBX-4 as sent (``"Fetus1"``), ``""`` if absent.
        fetus_number: N when ``sub_id`` is ``"Fetus<N>"`` (``"Fetus2"`` -> 2),
            otherwise ``None`` - including the bare counters (``"1"``,
            ``"2"``) exam-level groups put in OBX-4.
        value: OBX-5 exactly as sent, components and escapes kept.
        units: OBX-6 exactly as sent (``"mm&millimeters^mm&millimeters"``).
        result_status: OBX-11 as sent (``"F"`` for final), ``""`` if absent.
        observed_at: OBX-14 parsed; ``None`` when empty. Parts the sender
            left out are filled with the start of the period (a date-only
            value becomes midnight). Timezone-aware only when the sender
            gave an offset.
        encoding: the delimiters of the row's message.
    """

    message_index: int
    message_control_id: str
    segment_index: int
    line_number: int
    set_id: int | None
    value_type: str
    observation_id: str
    observation_text: str
    sub_id: str
    fetus_number: int | None
    value: str
    units: str
    result_status: str
    observed_at: datetime | None
    encoding: Hl7Encoding = Hl7Encoding()

    @property
    def namespace(self) -> str | None:
        """Part of ``observation_id`` before the first ``.``, or ``None``.

        ``"SkullFetus.HeadCircumference"`` -> ``"SkullFetus"``. Keeping the
        namespace is what tells a site form such as
        ``"U_FGRData_F_<hash>.AbdominalCircumference"`` apart from the real
        ``"AbdomenFetus.AbdominalCircumference"``.
        """
        namespace, dot, _ = self.observation_id.partition(".")
        return namespace if dot else None

    @property
    def field_id(self) -> str:
        """Part of ``observation_id`` after the first ``.`` (all of it if none)."""
        _, dot, field_id = self.observation_id.partition(".")
        return field_id if dot else self.observation_id

    @property
    def value_components(self) -> tuple[str, ...]:
        """OBX-5 split on the component separator: ``"45^45%"`` -> ``("45", "45%")``."""
        return tuple(self.value.split(self.encoding.component))

    @property
    def unit_code(self) -> str:
        """First code in OBX-6: ``"mm&millimeters^mm&millimeters"`` -> ``"mm"``."""
        first_component = self.units.split(self.encoding.component)[0]
        return first_component.split(self.encoding.subcomponent)[0]


@dataclass
class _MessageContext:
    """Running state for the message currently being read (mutable on purpose)."""

    index: int
    control_id: str
    encoding: Hl7Encoding
    segment_count: int = 1  # the MSH header itself


def read_hl7_rows(text: str) -> list[Hl7Row]:
    """Read every OBX segment of an HL7 export into an :class:`Hl7Row`.

    Lines may end in ``\\r``, ``\\r\\n`` or ``\\n``. Blank lines are skipped,
    and whitespace around each line is dropped so hand-indented test
    messages read the same as real ones. Segments other than OBX are checked
    for shape (so a stray non-HL7 line is reported, not silently skipped) and
    then passed over.

    Args:
        text: The export's full text, one or more ``MSH``-headed messages.

    Returns:
        One row per OBX segment, in input order. Empty when the input holds
        no OBX segment.

    Raises:
        Hl7ParseError: A non-blank line that is not an HL7 segment, a segment
            before the first ``MSH``, an ``MSH`` with unusable delimiters, or
            an OBX with a non-integer set id, an empty identifier or an
            unreadable observation time.
    """
    rows: list[Hl7Row] = []
    message: _MessageContext | None = None
    for line_number, raw_line in enumerate(_LINE_BREAK.split(text), start=1):
        line = raw_line.strip().lstrip("﻿")
        if not line:
            continue
        if line.startswith("MSH"):
            message = _read_msh(line, line_number, previous=message)
            continue
        if message is None:
            raise Hl7ParseError(line_number, "segment appears before any MSH header")
        _check_segment_shape(line, line_number, message.encoding)
        message.segment_count += 1
        if line.startswith("OBX" + message.encoding.field):
            rows.append(_read_obx(line, line_number, message))
    return rows


def _read_msh(
    line: str, line_number: int, previous: _MessageContext | None
) -> _MessageContext:
    """Start a new message from its MSH line: delimiters and control id."""
    # MSH-1 is the character right after "MSH"; MSH-2 holds, in order, the
    # component, repetition, escape and subcomponent separators (v2.7 adds a
    # fifth, truncation, which is accepted and ignored).
    if len(line) < 4:
        raise Hl7ParseError(line_number, "MSH header has no field separator")
    field_separator = line[3]
    fields = line.split(field_separator)
    declared = fields[1] if len(fields) > 1 else ""
    delimiters = field_separator + declared[:4]
    if (
        len(declared) < 4
        or len(set(delimiters)) != 5
        or any(char.isalnum() for char in delimiters)
    ):
        raise Hl7ParseError(
            line_number,
            "MSH-2 must declare four distinct encoding characters "
            "(component, repetition, escape, subcomponent)",
        )
    encoding = Hl7Encoding(
        field=field_separator,
        component=declared[0],
        repetition=declared[1],
        escape=declared[2],
        subcomponent=declared[3],
    )
    control_id = (
        fields[_MSH_CONTROL_ID_INDEX] if len(fields) > _MSH_CONTROL_ID_INDEX else ""
    )
    index = previous.index + 1 if previous is not None else 1
    return _MessageContext(index=index, control_id=control_id, encoding=encoding)


def _check_segment_shape(line: str, line_number: int, encoding: Hl7Encoding) -> None:
    """Reject a line that is not ``<segment id><field separator>...``."""
    segment_id = line[:3]
    shaped = _SEGMENT_ID.fullmatch(segment_id) and (
        len(line) == 3 or line[3] == encoding.field
    )
    if not shaped:
        raise Hl7ParseError(
            line_number,
            "not an HL7 segment (expected a three-character segment id "
            f"followed by {encoding.field!r})",
        )


def _read_obx(line: str, line_number: int, message: _MessageContext) -> Hl7Row:
    """Turn one OBX line into a row; every check on its fields happens here."""
    fields = line.split(message.encoding.field)
    # Pad so every position read below exists; HL7 senders may drop trailing
    # empty fields, which is not an error.
    fields += [""] * (_OBX_OBSERVED_AT + 1 - len(fields))

    identifier, _, rest = fields[_OBX_IDENTIFIER].partition(message.encoding.component)
    if not identifier:
        raise Hl7ParseError(line_number, "OBX-3 observation identifier is empty")
    observation_text = rest.split(message.encoding.component)[0]

    sub_id = fields[_OBX_SUB_ID]
    fetus_match = _FETUS_SUB_ID.fullmatch(sub_id)

    return Hl7Row(
        message_index=message.index,
        message_control_id=message.control_id,
        segment_index=message.segment_count,
        line_number=line_number,
        set_id=_parse_set_id(fields[_OBX_SET_ID], line_number),
        value_type=fields[_OBX_VALUE_TYPE],
        observation_id=identifier,
        observation_text=observation_text,
        sub_id=sub_id,
        fetus_number=int(fetus_match.group(1)) if fetus_match else None,
        value=fields[_OBX_VALUE],
        units=fields[_OBX_UNITS],
        result_status=fields[_OBX_RESULT_STATUS],
        observed_at=_parse_timestamp(fields[_OBX_OBSERVED_AT], line_number),
        encoding=message.encoding,
    )


def _parse_set_id(raw: str, line_number: int) -> int | None:
    """OBX-1 -> int; empty means the sender did not number the segment."""
    if not raw:
        return None
    if not raw.isdigit():
        raise Hl7ParseError(line_number, "OBX-1 set id is not a whole number")
    return int(raw)


def _parse_timestamp(raw: str, line_number: int) -> datetime | None:
    """OBX-14 HL7 date/time -> datetime; empty -> None."""
    if not raw:
        return None
    match = _HL7_TIMESTAMP.fullmatch(raw)
    if match is None:
        raise Hl7ParseError(line_number, "OBX-14 is not an HL7 date/time")
    parts = match.groupdict()
    fraction = parts["fraction"] or ""
    try:
        return datetime(
            int(parts["year"]),
            int(parts["month"] or 1),
            int(parts["day"] or 1),
            int(parts["hour"] or 0),
            int(parts["minute"] or 0),
            int(parts["second"] or 0),
            # Up to four fractional digits (tenths to ten-thousandths of a
            # second), scaled to microseconds.
            int(fraction.ljust(6, "0")) if fraction else 0,
            tzinfo=_parse_offset(parts["offset"]),
        )
    except ValueError:
        # Shaped like a timestamp but not a real calendar date or time
        # (month 13, hour 25, ...).
        raise Hl7ParseError(
            line_number, "OBX-14 is not a valid calendar date/time"
        ) from None


def _parse_offset(raw: str | None) -> timezone | None:
    """``"+0130"``/``"-0500"`` -> a fixed-offset timezone; absent -> naive."""
    if raw is None:
        return None
    sign = -1 if raw[0] == "-" else 1
    offset = timedelta(hours=int(raw[1:3]), minutes=int(raw[3:5]))
    return timezone(sign * offset)
