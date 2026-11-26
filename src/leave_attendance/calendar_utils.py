"""Calendar helpers: weekly-offs, holidays, working days, month maths."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Dict, Iterator, Tuple

from .config import WEEKLY_OFF_WEEKDAYS


class HolidayCalendar:
    def __init__(self, holidays: Dict[date, str]):
        self.holidays = dict(holidays)

    def is_holiday(self, d: date) -> bool:
        return d in self.holidays

    def is_weekly_off(self, d: date) -> bool:
        return d.weekday() in WEEKLY_OFF_WEEKDAYS

    def is_off_day(self, d: date) -> bool:
        """Weekly-off or company holiday (the days the sandwich rule talks about)."""
        return self.is_weekly_off(d) or self.is_holiday(d)

    def is_working_day(self, d: date) -> bool:
        """Mon-Fri excluding holidays (README: used for the 5-day auto-approval clock)."""
        return not self.is_off_day(d)

    def add_working_days(self, start: date, n: int) -> date:
        """The date reached after counting n working days *after* start."""
        d = start
        counted = 0
        while counted < n:
            d += timedelta(days=1)
            if self.is_working_day(d):
                counted += 1
        return d

    def previous_working_day(self, d: date) -> date:
        d -= timedelta(days=1)
        while not self.is_working_day(d):
            d -= timedelta(days=1)
        return d

    def next_working_day(self, d: date) -> date:
        d += timedelta(days=1)
        while not self.is_working_day(d):
            d += timedelta(days=1)
        return d


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def month_end(year: int, month: int) -> date:
    return date(year, month, days_in_month(year, month))


def iter_dates(start: date, end: date) -> Iterator[date]:
    """Every date from start to end, both inclusive."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def parse_month(text: str) -> Tuple[int, int]:
    """'2026-12' -> (2026, 12)"""
    year_text, month_text = text.strip().split("-")
    year, month = int(year_text), int(month_text)
    if not 1 <= month <= 12:
        raise ValueError(f"bad month: {text!r}")
    return year, month
