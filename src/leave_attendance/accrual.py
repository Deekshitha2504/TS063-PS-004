"""Monthly leave accrual and year-end processing.

Rules covered: BR-01 CL, BR-02 SL, BR-03 EL, BR-04 joiner pro-rata, BR-05 year-end.

How time works (important design choice, see decision D-12):
  * The command file is an event log processed top to bottom.
  * Before each command we call advance_to(date). It credits CL/SL for every
    month-start up to that date, so leave applied on 5 Dec already sees December's credit
    (the README says opening balances are 'before December accrual').
  * We never credit a month of the NEXT leave year until YEAR_END has run,
    otherwise January's CL would be credited and then wiped by the year-end lapse.
  * EL is credited quarterly in arrears: Q1 on 1 Apr, Q2 on 1 Jul, Q3 on 1 Oct,
    and Q4 by YEAR_END (README: 'credit Q4 EL (4.5) in arrears').
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Dict, Optional, Set, Tuple

from .balances import LeaveBalances
from .calendar_utils import month_end, month_start
from .config import (CL_MAX, CL_MONTHLY, EL_CARRY_MAX, EL_MONTHLY,
                     JOINER_CUTOFF_DAY, SL_ANNUAL_ACCRUAL_MAX, SL_CARRY_MAX,
                     SL_MONTHLY)
from .models import Employee

ZERO = Decimal("0")


def accrual_eligible(joining_date: date, year: int, month: int,
                     last_working_day: Optional[date] = None) -> bool:
    """Does this employee earn leave for (year, month)?   BR-04

    * joined before the month began               -> yes
    * joined in the month on/before the 15th      -> yes
    * joined in the month on the 16th or later    -> no
    * joined after the month                      -> no
    * left (last working day) before the month    -> no
    """
    start, end = month_start(year, month), month_end(year, month)
    if joining_date > end:
        return False
    if joining_date > start and joining_date.day > JOINER_CUTOFF_DAY:
        return False
    if last_working_day is not None and last_working_day < start:
        return False
    return True


def _capped_add(balance: Decimal, qty: Decimal, cap: Decimal) -> Decimal:
    """Add qty but never push the balance above cap (and never reduce an
    already-higher balance)."""
    if balance >= cap:
        return balance
    return min(balance + qty, cap)


@dataclass
class YearEndResult:
    closed_year: int
    lapsed: Dict[Tuple[str, str], Decimal] = field(default_factory=dict)  # (emp, type) -> days lost


class AccrualEngine:
    def __init__(self, employees: Dict[str, Employee], balances: LeaveBalances,
                 opening_date: date, exit_dates: Optional[Dict[str, date]] = None):
        self.employees = employees
        self.balances = balances
        # called with (year, month) right after that month has been credited
        self.on_month_accrued: Optional[Callable[[int, int], None]] = None
        self.exit_dates: Dict[str, date] = exit_dates if exit_dates is not None else {}
        self.open_year = opening_date.year
        self.clock = opening_date
        # last (year, month) already accrued; opening balances are BEFORE opening month's accrual
        self._last: Tuple[int, int] = (opening_date.year, opening_date.month - 1)
        self._el_quarters_done: Set[Tuple[int, int]] = set()
        # SL accrual already earned this year before opening (for the 12/yr cap)
        self._sl_accrued_ytd: Dict[str, Decimal] = {}
        for emp in employees.values():
            earned_months = sum(
                1 for m in range(1, opening_date.month)
                if accrual_eligible(emp.joining_date, opening_date.year, m, None)
            )
            self._sl_accrued_ytd[emp.emp_id] = SL_MONTHLY * earned_months

    # ---- time -----------------------------------------------------------
    def advance_to(self, d: date) -> None:
        """Move the clock forward and credit every due month-start of the open year."""
        if d > self.clock:
            self.clock = d
        target = (self.clock.year, self.clock.month)
        while True:
            y, m = self._last
            ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
            if ny != self.open_year or (ny, nm) > target:
                break
            self.accrue_month(ny, nm)
            self._last = (ny, nm)
            if self.on_month_accrued is not None:
                self.on_month_accrued(ny, nm)

    def is_month_accrued(self, year: int, month: int) -> bool:
        """True once the month's credits are in the balances (older months always are)."""
        return (year, month) <= self._last

    # ---- monthly credit -------------------------------------------------
    def accrue_month(self, year: int, month: int) -> None:
        for emp in self.employees.values():
            lwd = self.exit_dates.get(emp.emp_id)
            if not accrual_eligible(emp.joining_date, year, month, lwd):
                continue
            # BR-01: CL +1, balance capped at 12
            cl = self.balances.get(emp.emp_id, "CL")
            self.balances.set(emp.emp_id, "CL", _capped_add(cl, CL_MONTHLY, CL_MAX))
            # BR-02: SL +1, but at most 12 accrued per year
            room = max(SL_ANNUAL_ACCRUAL_MAX - self._sl_accrued_ytd[emp.emp_id], ZERO)
            credit = min(SL_MONTHLY, room)
            if credit > 0:
                self.balances.add(emp.emp_id, "SL", credit)
                self._sl_accrued_ytd[emp.emp_id] += credit
        # BR-03: EL for the quarter that just ended, credited on 1 Apr / 1 Jul / 1 Oct
        if month in (4, 7, 10):
            self.credit_el_quarter(year, (month - 1) // 3)

    def credit_el_quarter(self, year: int, quarter: int) -> None:
        """1.5 per eligible month of the quarter. Safe to call twice (only credits once)."""
        if (year, quarter) in self._el_quarters_done:
            return
        self._el_quarters_done.add((year, quarter))
        first_month = 3 * quarter - 2
        for emp in self.employees.values():
            lwd = self.exit_dates.get(emp.emp_id)
            months = sum(
                1 for m in range(first_month, first_month + 3)
                if accrual_eligible(emp.joining_date, year, m, lwd)
            )
            if months:
                self.balances.add(emp.emp_id, "EL", EL_MONTHLY * months)

    # ---- year end -------------------------------------------------------
    def year_end(self, catch_up: bool = True) -> YearEndResult:
        """BR-05: credit Q4 EL, then CL lapses, SL carries <=30, EL carries <=45.

        catch_up=False stops before the new year's credits so the caller can record the
        31 December balances (after carry-forward and lapse, before the 1 January credit);
        it must then call advance_to(clock) itself."""
        closing = self.open_year
        self.credit_el_quarter(closing, 4)
        result = YearEndResult(closed_year=closing)
        for emp in self.employees.values():
            e = emp.emp_id
            cl = self.balances.get(e, "CL")
            if cl:
                result.lapsed[(e, "CL")] = cl
                self.balances.set(e, "CL", ZERO)
            for leave_type, cap in (("SL", SL_CARRY_MAX), ("EL", EL_CARRY_MAX)):
                bal = self.balances.get(e, leave_type)
                if bal > cap:
                    result.lapsed[(e, leave_type)] = bal - cap
                    self.balances.set(e, leave_type, cap)
        # open the new leave year
        self.open_year = closing + 1
        self._last = (self.open_year, 0)
        for key in self._sl_accrued_ytd:
            self._sl_accrued_ytd[key] = ZERO
        if catch_up:
            self.advance_to(self.clock)   # catch up months of the new year already reached
        return result
