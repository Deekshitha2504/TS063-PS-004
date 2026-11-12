"""The leave request lifecycle: apply, approve, reject, cancel, auto-approve.

Rules covered: BR-06 (SL medical), BR-07 (CL/EL clubbing), BR-08 (EL notice),
BR-09 (comp-off expiry), BR-10 (sandwich), BR-11 (excess -> LOP),
BR-12 (approval chain), BR-13 (auto-approval).

Balance handling (decision D-17):
  * Balance is RESERVED when a request is applied, and given back on reject/cancel.
  * Each leave day is charged in the month it falls in, after that month's accrual.
    A day in a month not yet accrued is 'deferred' and charged when the month is
    credited. This is why EL 29 Dec - 4 Jan takes 3 days from the old year and
    4 days from the new year (README, year-end scenario).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Dict, List, Optional, Set, Tuple

from .accrual import AccrualEngine
from .attendance import HALF_LOP, LOP, PAID
from .balances import CompOffLedger, LeaveBalances
from .calendar_utils import HolidayCalendar
from .config import (ACTIVE_STATUSES, AUTO_APPROVE_WORKING_DAYS,
                     COVERING_STATUSES, EL_NOTICE_DAYS, LEAVE_TYPES_WITH_BALANCE,
                     REJECT_OVERLAPPING_REQUESTS, SL_MEDICAL_THRESHOLD_DAYS,
                     VALID_LEAVE_TYPES)
from .leave_rules import counted_days, is_clubbed, required_roles
from .models import Employee

ZERO = Decimal("0")
ONE = Decimal("1")
HALF = Decimal("0.5")


class CommandRejected(Exception):
    """The command itself is not allowed (e.g. approver not in the chain)."""

    def __init__(self, message: str, rule_ids: Optional[List[str]] = None):
        super().__init__(message)
        self.rule_ids = rule_ids or []


@dataclass
class LeaveRequest:
    req_id: str
    emp_id: str
    leave_type: str
    from_date: date
    to_date: date
    applied_on: date
    reason: str
    medical_flag: bool
    line_no: int
    status: str = "PENDING"
    counted_dates: List[date] = field(default_factory=list)
    sandwiched_days: int = 0
    roles_needed: Set[str] = field(default_factory=set)
    approvals: Dict[str, str] = field(default_factory=dict)      # role -> approver
    approved_on: Optional[date] = None
    rule_ids: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    day_cover: Dict[date, str] = field(default_factory=dict)     # date -> PAID/LOP/HALF_LOP
    paid_qty: Decimal = ZERO
    lop_qty: Decimal = ZERO
    deferred_days: List[date] = field(default_factory=list)
    debits: List[Tuple[str, Decimal]] = field(default_factory=list)
    comp_allocations: List[Tuple[int, Decimal]] = field(default_factory=list)

    @property
    def days_counted(self) -> Decimal:
        return Decimal(len(self.counted_dates))

    def add_rule(self, rule_id: str) -> None:
        if rule_id not in self.rule_ids:
            self.rule_ids.append(rule_id)


def _floor_half(x: Decimal) -> Decimal:
    """Round down to a multiple of 0.5 (balances move in half-day steps)."""
    return (x * 2).to_integral_value(rounding=ROUND_FLOOR) / 2


class LeaveEngine:
    def __init__(self, employees: Dict[str, Employee], calendar: HolidayCalendar,
                 balances: LeaveBalances, comp_off: CompOffLedger, accrual: AccrualEngine):
        self.employees = employees
        self.cal = calendar
        self.balances = balances
        self.comp_off = comp_off
        self.accrual = accrual
        self.requests: Dict[str, LeaveRequest] = {}
        self.order: List[str] = []           # req_ids in file order (for the ledger)
        accrual.on_month_accrued = self._charge_deferred_for_month

    # ------------------------------------------------------------------ apply
    def apply(self, line_no: int, req_id: str, emp_id: str, leave_type: str,
              from_date: date, to_date: date, applied_on: date, reason: str,
              medical_flag: bool) -> LeaveRequest:
        if req_id in self.requests:
            raise CommandRejected(f"duplicate request id {req_id}")
        leave_type = leave_type.upper()
        req = LeaveRequest(req_id, emp_id, leave_type, from_date, to_date,
                           applied_on, reason, medical_flag, line_no)
        self.requests[req_id] = req
        self.order.append(req_id)

        reason_failed = self._validate(req)
        if reason_failed:
            rule_id, message = reason_failed
            req.status = "REJECTED"
            req.add_rule(rule_id)
            req.messages.append(message)
            return req

        emp = self.employees[emp_id]
        req.roles_needed = required_roles(emp.grade, bool(emp.manager_id))
        if req.sandwiched_days and leave_type in ("EL", "LOP"):
            req.add_rule("BR-10")
        self._allocate(req, req.counted_dates)
        return req

    def _validate(self, req: LeaveRequest) -> Optional[Tuple[str, str]]:
        """Return (rule_id, message) for the first failed check, else None."""
        emp = self.employees.get(req.emp_id)
        if emp is None:
            return "UNKNOWN_EMPLOYEE", f"{req.emp_id} is not in employees.csv"
        if req.leave_type not in VALID_LEAVE_TYPES:
            return "INVALID_LEAVE_TYPE", f"unknown leave type {req.leave_type}"
        if req.to_date < req.from_date:
            return "INVALID_DATES", "to_date is before from_date"
        if req.from_date < emp.joining_date:
            return "BEFORE_JOINING", "leave starts before the joining date"
        if req.leave_type == "MATERNITY" and emp.gender != "F":
            return "MATERNITY_FEMALE_ONLY", "maternity leave is for female employees only"

        req.counted_dates, req.sandwiched_days = counted_days(
            req.leave_type, req.from_date, req.to_date, self.cal)
        if not req.counted_dates:
            return "NO_LEAVE_DAYS", "the dates fall only on weekly-offs/holidays"

        n = len(req.counted_dates)
        if req.leave_type == "EL" and (req.from_date - req.applied_on).days < EL_NOTICE_DAYS:
            return "BR-08", f"EL needs {EL_NOTICE_DAYS} days' notice"
        if (req.leave_type == "SL" and n > SL_MEDICAL_THRESHOLD_DAYS
                and not req.medical_flag):
            return "BR-06", f"SL of {n} days needs a medical flag"
        if req.leave_type in ("CL", "EL"):
            other_type = "EL" if req.leave_type == "CL" else "CL"
            other_days = self._active_dates(req.emp_id, other_type)
            if is_clubbed(req.counted_dates, other_days, self.cal):
                return "BR-07", "CL cannot be clubbed with EL"
        if REJECT_OVERLAPPING_REQUESTS:
            mine = set(req.counted_dates)
            for other in self.requests.values():
                if (other is not req and other.emp_id == req.emp_id
                        and other.status in ACTIVE_STATUSES
                        and mine & set(other.counted_dates)):
                    return "OVERLAP", f"overlaps request {other.req_id}"
        if req.leave_type == "COMP_OFF":
            usable = self.comp_off.available(req.emp_id, req.from_date)
            if usable == 0 and self.comp_off.expired_remaining(req.emp_id, req.from_date) > 0:
                return "BR-09", "comp-off has expired (60 days after credit)"
        return None

    def _active_dates(self, emp_id: str, leave_type: str) -> Set[date]:
        out: Set[date] = set()
        for r in self.requests.values():
            if r.emp_id == emp_id and r.leave_type == leave_type and r.status in ACTIVE_STATUSES:
                out.update(r.counted_dates)
        return out

    # ------------------------------------------------------------- allocation
    def _allocate(self, req: LeaveRequest, days: List[date]) -> None:
        """Charge days against the right balance now, or defer them."""
        if req.leave_type in LEAVE_TYPES_WITH_BALANCE:
            now: List[date] = []
            for d in days:
                if self.accrual.is_month_accrued(d.year, d.month):
                    now.append(d)
                else:
                    req.deferred_days.append(d)
            if now:
                self._charge_balance(req, now)
        elif req.leave_type == "COMP_OFF":
            self._charge_comp_off(req, days)
        elif req.leave_type == "LOP":
            for d in days:
                req.day_cover[d] = LOP
            req.lop_qty += Decimal(len(days))
        elif req.leave_type == "MATERNITY":
            for d in days:
                req.day_cover[d] = PAID
            req.paid_qty += Decimal(len(days))

    def _charge_balance(self, req: LeaveRequest, days: List[date]) -> None:
        need = Decimal(len(days))
        available = max(self.balances.get(req.emp_id, req.leave_type), ZERO)
        paid = _floor_half(min(available, need))
        if paid > 0:
            self.balances.add(req.emp_id, req.leave_type, -paid)
            req.debits.append((req.leave_type, paid))
        self._assign_cover(req, days, paid)
        req.paid_qty += paid
        lop = need - paid
        if lop > 0:
            req.lop_qty += lop
            req.add_rule("BR-11")
            req.messages.append(f"{lop} day(s) converted to LOP (insufficient {req.leave_type} balance)")

    def _charge_comp_off(self, req: LeaveRequest, days: List[date]) -> None:
        for d in days:
            usable = _floor_half(min(self.comp_off.available(req.emp_id, d), ONE))
            if usable > 0:
                req.comp_allocations.extend(self.comp_off.consume(req.emp_id, usable, d))
            self._assign_cover(req, [d], usable)
            req.paid_qty += usable
            if usable < ONE:
                req.lop_qty += ONE - usable
                req.add_rule("BR-11")
                req.messages.append(f"{ONE - usable} day(s) converted to LOP (insufficient comp-off)")

    @staticmethod
    def _assign_cover(req: LeaveRequest, days: List[date], paid: Decimal) -> None:
        remaining = paid
        for d in days:
            if remaining >= ONE:
                req.day_cover[d] = PAID
                remaining -= ONE
            elif remaining >= HALF:
                req.day_cover[d] = HALF_LOP
                remaining = ZERO
            else:
                req.day_cover[d] = LOP

    def _charge_deferred_for_month(self, year: int, month: int) -> None:
        """Called by the accrual engine once a month's credits are in."""
        for req_id in self.order:
            req = self.requests[req_id]
            if req.status not in ACTIVE_STATUSES or not req.deferred_days:
                continue
            due = [d for d in req.deferred_days if (d.year, d.month) == (year, month)]
            if due:
                req.deferred_days = [d for d in req.deferred_days if d not in due]
                self._charge_balance(req, due)

    def _release(self, req: LeaveRequest) -> None:
        """Give back everything a request had reserved."""
        for leave_type, qty in req.debits:
            self.balances.add(req.emp_id, leave_type, qty)
        self.comp_off.restore(req.comp_allocations)
        req.debits, req.comp_allocations = [], []
        req.day_cover, req.deferred_days = {}, []
        req.paid_qty = req.lop_qty = ZERO

    # -------------------------------------------------------------- approvals
    def _role_of(self, req: LeaveRequest, approver_id: str) -> str:
        emp = self.employees[req.emp_id]
        approver = self.employees.get(approver_id)
        if approver is None:
            raise CommandRejected(f"approver {approver_id} is not an employee", ["BR-12"])
        if approver_id == req.emp_id:
            raise CommandRejected("an employee cannot approve their own leave", ["BR-12"])
        if ("MANAGER" in req.roles_needed and "MANAGER" not in req.approvals
                and approver_id == emp.manager_id):
            return "MANAGER"
        if ("HR" in req.roles_needed and "HR" not in req.approvals
                and approver.department.upper() == "HR"):
            return "HR"
        raise CommandRejected(
            f"{approver_id} is not an outstanding approver for this request "
            f"(needs {sorted(req.roles_needed - set(req.approvals))})", ["BR-12"])

    def _get_pending(self, req_id: str) -> LeaveRequest:
        req = self.requests.get(req_id)
        if req is None:
            raise CommandRejected(f"unknown request {req_id}")
        if req.status != "PENDING":
            raise CommandRejected(f"request {req_id} is {req.status}, not PENDING")
        return req

    def approve(self, req_id: str, approver_id: str, on_date: date) -> LeaveRequest:
        req = self._get_pending(req_id)
        role = self._role_of(req, approver_id)
        req.approvals[role] = approver_id
        if set(req.approvals) >= req.roles_needed:
            req.status = "APPROVED"
            req.approved_on = on_date
            req.add_rule("BR-12")
        return req

    def reject(self, req_id: str, approver_id: str, on_date: date, remark: str) -> LeaveRequest:
        req = self._get_pending(req_id)
        emp = self.employees[req.emp_id]
        approver = self.employees.get(approver_id)
        in_chain = (approver is not None and approver_id != req.emp_id and (
            ("MANAGER" in req.roles_needed and approver_id == emp.manager_id)
            or ("HR" in req.roles_needed and approver.department.upper() == "HR")))
        if not in_chain:
            raise CommandRejected(f"{approver_id} is not in the approval chain", ["BR-12"])
        self._release(req)
        req.status = "REJECTED"
        req.messages.append(f"rejected by {approver_id}: {remark}")
        return req

    def cancel(self, req_id: str, on_date: date) -> LeaveRequest:
        req = self.requests.get(req_id)
        if req is None:
            raise CommandRejected(f"unknown request {req_id}")
        if req.status not in ACTIVE_STATUSES:
            raise CommandRejected(f"request {req_id} is {req.status}; nothing to cancel")
        if on_date >= req.from_date:
            raise CommandRejected("a request can only be cancelled before the leave starts")
        self._release(req)
        req.status = "CANCELLED"
        return req

    # ----------------------------------------------------------- auto-approval
    def sweep_auto_approvals(self, up_to: date, inclusive: bool) -> List[LeaveRequest]:
        """BR-13: a PENDING request is auto-approved 5 working days after it was applied.
        LOP is never auto-approved."""
        done = []
        for req_id in self.order:
            req = self.requests[req_id]
            if req.status != "PENDING" or req.leave_type == "LOP":
                continue
            deadline = self.cal.add_working_days(req.applied_on, AUTO_APPROVE_WORKING_DAYS)
            if deadline < up_to or (inclusive and deadline == up_to):
                req.status = "AUTO_APPROVED"
                req.approved_on = deadline
                req.add_rule("BR-13")
                done.append(req)
        return done

    # ------------------------------------------------------- attendance cover
    def leave_cover(self, emp_id: str, year: int, month: int) -> Dict[date, str]:
        """date -> PAID/LOP/HALF_LOP for approved leave in that month."""
        cover: Dict[date, str] = {}
        for req in self.requests.values():
            if req.emp_id != emp_id or req.status not in COVERING_STATUSES:
                continue
            for d, kind in req.day_cover.items():
                if (d.year, d.month) == (year, month):
                    if d not in cover or kind == PAID:
                        cover[d] = kind
        return cover
