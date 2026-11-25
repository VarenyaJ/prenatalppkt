"""Tests for GestationalAge, in particular from_weeks()'s conversion
from a decimal-week float into whole weeks + days.

This class had zero dedicated tests before this file. That mattered:
the real Observer extractor calls
``GestationalAge.from_weeks(float(ega))`` directly on every raw
gestational-age value it reads, so a bug here silently affects the
gestational age stamped on every biometry finding in the whole
pipeline.
"""

from datetime import date

import pytest

from prenatalppkt.gestational_age import GestationalAge


def test_from_weeks_docstring_examples():
    ga = GestationalAge.from_weeks(12)
    assert (ga.weeks, ga.days) == (12, 0)

    ga = GestationalAge.from_weeks(12.5)
    assert (ga.weeks, ga.days) == (12, 3)


@pytest.mark.parametrize("weeks", list(range(10, 43)))
@pytest.mark.parametrize("days", list(range(7)))
def test_from_weeks_round_trips_every_week_and_day_combination(weeks, days):
    """Regression test for a real bug: building the decimal-week value
    the same way the real pipeline does (weeks + days/7, e.g. what a
    source system computing gestational age in days and storing it as
    decimal weeks would produce) and converting it back must recover
    the exact same weeks/days - not silently lose a day.

    Before the fix, 99 of these 231 combinations failed: floating-point
    division/subtraction landed the fraction a hair under the intended
    whole number (e.g. 0.9999999999999964 instead of 1.0), and the old
    int()-based truncation rounded that down to 0 instead of up to 1.
    """
    as_decimal_weeks = weeks + days / 7

    result = GestationalAge.from_weeks(as_decimal_weeks)

    assert (result.weeks, result.days) == (weeks, days)


def test_from_weeks_rejects_non_numeric_input():
    with pytest.raises(TypeError):
        GestationalAge.from_weeks("20.5")  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# Construction is validated
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "weeks, days",
    [
        (-3, 0),  # negative weeks
        (20, -1),  # negative days
        (20, 7),  # days are 0-6
        (20, 99),
        (46, 0),  # one past MAX_WEEKS
        (10_000, 0),  # huge weeks
    ],
)
def test_constructor_rejects_impossible_values(weeks, days):
    with pytest.raises(ValueError):
        GestationalAge(weeks=weeks, days=days)


def test_constructor_accepts_range_limits():
    assert GestationalAge(weeks=0, days=0).weeks == 0
    ga = GestationalAge(weeks=GestationalAge.MAX_WEEKS, days=6)
    assert (ga.weeks, ga.days) == (GestationalAge.MAX_WEEKS, 6)


def test_from_weeks_rejects_impossible_values():
    with pytest.raises(ValueError):
        GestationalAge.from_weeks(-3)
    with pytest.raises(ValueError):
        GestationalAge.from_weeks(500.5)


# ---------------------------------------------------------------------
# One shared parser
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("12w 3d", (12, 3)),
        ("12w3d", (12, 3)),
        ("12W 3D", (12, 3)),
        ("12+3", (12, 3)),
        ("12 + 3", (12, 3)),
        ("  27w 0d ", (27, 0)),
        ("12w", (12, 0)),
        ("12", (12, 0)),
        ("12.5", (12, 3)),
    ],
)
def test_parse_accepts_common_formats(text, expected):
    ga = GestationalAge.parse(text)
    assert (ga.weeks, ga.days) == expected


def test_parse_accepts_numbers():
    assert GestationalAge.parse(21.5).days == 3
    assert GestationalAge.parse(21).weeks == 21


@pytest.mark.parametrize(
    "text", ["", "abc", "w3d", "12w 7d", "12w 3d extra", "99w 0d", "-3w"]
)
def test_parse_rejects_bad_text(text):
    with pytest.raises(ValueError):
        GestationalAge.parse(text)


# ---------------------------------------------------------------------
# from_lmp
# ---------------------------------------------------------------------


def test_from_lmp_counts_days_between_lmp_and_exam():
    ga = GestationalAge.from_lmp(date(2025, 1, 15), date(2025, 5, 2))
    # 107 days = 15 weeks and 2 days
    assert (ga.weeks, ga.days) == (15, 2)


def test_from_lmp_rejects_exam_before_lmp():
    with pytest.raises(ValueError):
        GestationalAge.from_lmp(date(2025, 5, 2), date(2025, 1, 15))


def test_from_lmp_rejects_placeholder_lmp():
    # Observer writes 0001-01-01 when no LMP was entered.
    with pytest.raises(ValueError):
        GestationalAge.from_lmp(date(1, 1, 1), date(2025, 7, 2))
