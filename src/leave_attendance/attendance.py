"""Turn one employee's daily attendance for one month into payable days.

BR-14 / BR-15:  payable days = calendar days - LOP - unauthorised absences,
half-day = 0.5, WFH counts as present.

Days with NO attendance row are days the employee was not on the rolls
(before joining, after last working day), so they are not payable. The README
confirms this: December has 1504 rows = 48 x 31 + 16 (joiner on the 16th).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List

from .calendar_utils import days_in_month, iter_dates, month_end, month_start

ZERO = Decimal("0")
ONE = Decimal("1")
HALF = Decimal("0.5")

# What the leave engine tells us about a date:
PAID = "PAID"   # covered by an approved paid leave (CL/SL/EL/COMP_OFF/MATERNITY)
LOP = "LOP"     # covered by LOP, or an off-day sandwiched inside EL/LOP leave
HALF_LOP = "HALF_LOP"  # balance ran out mid-day: 0.5 paid leave + 0.5 LOP


@dataclass
class MonthlyAttendanceSummary:
    """The 'handshake' object your teammate's payroll code reads."""
    emp_id: str
    month: str                      # "2026-12"
    calendar_days: int
    payable_days: Decimal
    lop_days: Decimal               # LOP leave + sandwiched off-days
    unauthorised_days: Decimal      # 'A' days with no approved leave
    half_day_unpaid: Decimal        # the unworked half of each HD
    not_employed_days: int          # no attendance row (before joining / after exit)
    flags: List[str] = field(default_factory=list)
    payable_by_date: Dict[date, Decimal] = field(default_factory=dict)  # 1, 0.5 or 0 per day

    def check_identity(self) -> bool:
        total = (self.payable_days + self.lop_days + self.unauthorised_days
                 + self.half_day_unpaid + Decimal(self.not_employed_days))
        return total == Decimal(self.calendar_days)


def summarise_month(
    emp_id: str,
    year: int,
    month: int,
    status_by_date: Dict[date, str],
    leave_cover: Dict[date, str],
) -> MonthlyAttendanceSummary:
    """status_by_date: this employee's attendance statuses (P/A/HD/H/WO/WFH).
    leave_cover: date -> PAID or LOP, produced by the leave engine (stage 2)."""
    payable = lop = unauthorised = half_unpaid = ZERO
    not_employed = 0
    flags: List[str] = []

    payable_by_date: Dict[date, Decimal] = {}
    for day in iter_dates(month_start(year, month), month_end(year, month)):
        before = payable
        status = status_by_date.get(day)
        cover = leave_cover.get(day)

        if status is None:
            not_employed += 1
            payable_by_date[day] = ZERO
            continue

        if status in ("P", "WFH"):
            payable += ONE
            if cover is not None:
                flags.append(f"PRESENT_ON_LEAVE_DAY {day}")  # attendance wins
        elif status == "HD":
            payable += HALF
            half_unpaid += HALF
        elif status in ("H", "WO"):
            # An off-day is paid, unless the sandwich rule turned it into LOP.
            if cover == LOP:
                lop += ONE
            elif cover == HALF_LOP:
                payable += HALF
                lop += HALF
            else:
                payable += ONE
        elif status == "A":
            if cover == PAID:
                payable += ONE
            elif cover == LOP:
                lop += ONE
            elif cover == HALF_LOP:
                payable += HALF
                lop += HALF
            else:
                unauthorised += ONE
        payable_by_date[day] = payable - before

    return MonthlyAttendanceSummary(
        emp_id=emp_id,
        month=f"{year:04d}-{month:02d}",
        calendar_days=days_in_month(year, month),
        payable_days=payable,
        lop_days=lop,
        unauthorised_days=unauthorised,
        half_day_unpaid=half_unpaid,
        not_employed_days=not_employed,
        flags=flags,
        payable_by_date=payable_by_date,
    )
