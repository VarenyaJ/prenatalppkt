import math
import re
import typing
from datetime import date

# "12w 3d", "12w3d", "12W", "12+3", "12 + 3". Group 1 is weeks, group 2 the
# days after a plus sign, group 3 the days after a "w".
_WEEKS_AND_DAYS = re.compile(
    r"(\d+)\s*(?:\+\s*(\d+)|w\s*(?:(\d+)\s*d?)?)", re.IGNORECASE
)
_DECIMAL_WEEKS = re.compile(r"\d+(?:\.\d+)?")


class GestationalAge:
    """
    A class representing gestational age, expressed in weeks and days.

    Gestational age, defined as the time elapsed since the first day of the last menstrual period (LMP), is typically used in obstetrics to describe the age of an embryo or fetus.
    It is expressed as the number of completed weeks and additional days since the first day of the last menstrual period (LMP). Example 34w3d

    Attributes
    ----------
    _weeks : int
        The number of completed gestational weeks.
    _days : int
        The number of additional days beyond the completed weeks (0-6).

    Methods
    -------
    from_weeks(weeks: Union[int, float]) -> "GestationalAge"
        Create a GestationalAge instance from a numeric week value, which may be an integer or float.
    parse(value: Union[str, int, float]) -> "GestationalAge"
        Create a GestationalAge instance from text such as "12w 3d", "12w3d", "12+3" or "12.5".
    from_lmp(lmp: date, exam_date: date) -> "GestationalAge"
        Create a GestationalAge instance from the last menstrual period and the exam date.
    weeks -> int
        Return the number of completed weeks.
    days -> int
        Return the number of additional days.
    """

    MIN_WEEKS: typing.ClassVar[int] = 0
    # A post-term pregnancy ends near 42 weeks. 45 leaves room for dating
    # errors while still rejecting a placeholder date or a typo.
    MAX_WEEKS: typing.ClassVar[int] = 45

    _weeks: int
    _days: int

    def __init__(self, weeks: int, days: int) -> None:
        """
        Initialize a GestationalAge instance.

        Parameters
        ----------
        weeks : int
            The number of completed weeks (MIN_WEEKS to MAX_WEEKS).
        days : int
            The number of additional days (0-6).

        Raises
        ------
        ValueError
            If weeks or days are outside the allowed range.
        """
        if not self.MIN_WEEKS <= weeks <= self.MAX_WEEKS:
            raise ValueError(
                f"weeks must be between {self.MIN_WEEKS} and {self.MAX_WEEKS}, got {weeks}"
            )
        if not 0 <= days <= 6:
            raise ValueError(f"days must be between 0 and 6, got {days}")
        self._weeks = weeks
        self._days = days

    @staticmethod
    def from_weeks(weeks: typing.Union[int, float]) -> "GestationalAge":
        """
        Construct a GestationalAge object from a numeric week value.

        If `weeks` is an integer, the result will represent that many whole weeks and 0 days.
        If `weeks` is a float, the fractional part will be converted into days.

        Examples
        --------
        # >>> GestationalAge.from_weeks(12)
        # <GestationalAge: 12 weeks, 0 days>
        # >>> GestationalAge.from_weeks(12.5)
        # <GestationalAge: 12 weeks, 3 days>

        Parameters
        ----------
        weeks : Union[int, float]
            The gestational age in weeks (can be fractional).

        Returns
        -------
        GestationalAge
            A new instance representing the specified gestational age.
        """
        if isinstance(weeks, int):
            return GestationalAge(weeks=weeks, days=0)
        elif isinstance(weeks, float):
            w = math.floor(weeks)
            week_frac = weeks - w
            # Truncate to completed days (not round to nearest - a
            # genuinely partial day, e.g. weeks=12.5, deliberately
            # truncates to 3 days, not 4), but round to 6 decimal places
            # first to absorb floating-point noise: float subtraction/
            # multiplication here can land a hair under the intended
            # whole number (e.g. a value that should give exactly 1 day
            # computes as 0.9999999999999964), which int() alone would
            # truncate down to 0, silently losing a day.
            d = int(round(week_frac * 7, 6))
            if d == 7:  # rounding pushed the fraction up into the next week
                w += 1
                d = 0
            return GestationalAge(weeks=w, days=d)
        raise TypeError("weeks must be int or float")

    @staticmethod
    def parse(value: typing.Union[str, int, float]) -> "GestationalAge":
        """
        Construct a GestationalAge object from text or a number.

        Accepted text: "12w 3d", "12w3d", "12w", "12+3", and decimal weeks such as "12.5".
        A number is read as decimal weeks, like `from_weeks`.

        Raises
        ------
        ValueError
            If the text has none of these formats, or the values are out of range.
        """
        if isinstance(value, (int, float)):
            return GestationalAge.from_weeks(value)
        text = str(value).strip()
        match = _WEEKS_AND_DAYS.fullmatch(text)
        if match:
            weeks, plus_days, d_days = match.group(1), match.group(2), match.group(3)
            days = plus_days or d_days
            return GestationalAge(weeks=int(weeks), days=int(days) if days else 0)
        if _DECIMAL_WEEKS.fullmatch(text):
            return GestationalAge.from_weeks(float(text))
        raise ValueError(f"Could not read a gestational age from {value!r}")

    @staticmethod
    def from_lmp(lmp: date, exam_date: date) -> "GestationalAge":
        """
        Construct a GestationalAge object from the first day of the last menstrual
        period (LMP) and the date of the exam.

        Raises
        ------
        ValueError
            If the exam is before the LMP, or the result is out of range.
        """
        weeks, days = divmod((exam_date - lmp).days, 7)
        return GestationalAge(weeks=weeks, days=days)

    @property
    def weeks(self) -> int:
        """
        Get the number of completed gestational weeks.

        Returns
        -------
        int
            The number of completed weeks.
        """
        return self._weeks

    @property
    def days(self) -> int:
        """
        Get the number of additional gestational days beyond completed weeks.

        Returns
        -------
        int
            The number of days (0-6).
        """
        return self._days

    def __repr__(self) -> str:
        """Return a concise representation like <GestationalAge: 20 weeks, 6 days>."""
        return f"<GestationalAge: {self._weeks} weeks, {self._days} days>"
