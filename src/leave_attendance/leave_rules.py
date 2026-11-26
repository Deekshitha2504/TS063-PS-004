"""Pure rule helpers for leave requests (no state, easy to test)."""
from __future__ import annotations

from datetime import date
from typing import List, Set, Tuple

from .calendar_utils import HolidayCalendar, iter_dates
from .config import SANDWICH_LEAVE_TYPES


def counted_days(leave_type: str, start: date, end: date,
                 cal: HolidayCalendar) -> Tuple[List[date], int]:
    """Which dates a request uses up.  Returns (dates, sandwiched_off_day_count).

    * CL, SL, COMP_OFF : working days only. Weekly-offs/holidays never count.
    * EL, LOP (BR-10)  : working days, PLUS weekly-offs/holidays that sit between
                         two leave days (the sandwich rule). Off-days at the very
                         start or end of the range do not count.
    * MATERNITY        : every calendar day (statutory leave includes weekly-offs).
    """
    all_days = list(iter_dates(start, end))
    if leave_type == "MATERNITY":
        return all_days, 0
    working = [d for d in all_days if cal.is_working_day(d)]
    if leave_type in SANDWICH_LEAVE_TYPES and working:
        first, last = working[0], working[-1]
        days = [d for d in all_days if first <= d <= last]
        return days, sum(1 for d in days if not cal.is_working_day(d))
    return working, 0


def required_roles(grade: str, has_manager: bool) -> Set[str]:
    """BR-12 approval chain: G1-G2 manager; G3-G4 manager + HR; G5 HR only.
    If the employee has no manager on file the manager step is replaced by HR (D-19)."""
    if grade in ("G1", "G2"):
        roles = {"MANAGER"}
    elif grade in ("G3", "G4"):
        roles = {"MANAGER", "HR"}
    elif grade == "G5":
        roles = {"HR"}
    else:
        roles = {"MANAGER"}
    if not has_manager and "MANAGER" in roles:
        roles = (roles - {"MANAGER"}) | {"HR"}
    return roles


def is_clubbed(new_days: List[date], other_days: Set[date],
               cal: HolidayCalendar) -> bool:
    """BR-07: is the new request touching (or overlapping) the other leave, ignoring
    weekly-offs/holidays in between?  Used for CL <-> EL."""
    if not new_days:
        return False
    working = [d for d in new_days if cal.is_working_day(d)] or new_days
    first, last = working[0], working[-1]
    if any(d in other_days for d in new_days):
        return True
    return (cal.previous_working_day(first) in other_days
            or cal.next_working_day(last) in other_days)
