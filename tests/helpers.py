"""Shared test world for stage 2 tests."""
from datetime import date
from decimal import Decimal as D

from leave_attendance.accrual import AccrualEngine
from leave_attendance.balances import CompOffLedger, LeaveBalances
from leave_attendance.calendar_utils import HolidayCalendar
from leave_attendance.leave_requests import LeaveEngine
from leave_attendance.models import CompOffCredit, Employee

HOLIDAYS = {date(2026, 12, 25): "Christmas", date(2027, 1, 26): "Republic Day"}


def employees():
    j = date(2020, 1, 1)
    return {e.emp_id: e for e in [
        Employee("EMP-001", "Hema", "F", "G5", "HR", j, None),        # HR head
        Employee("EMP-002", "Hari", "M", "G3", "HR", j, "EMP-001"),   # HR approver
        Employee("EMP-005", "Mani", "M", "G4", "Eng", j, "EMP-001"),  # manager
        Employee("EMP-020", "Gita", "F", "G2", "Eng", j, "EMP-005"),  # manager approval only
        Employee("EMP-030", "Ravi", "M", "G3", "Eng", j, "EMP-005"),  # manager + HR
        Employee("EMP-040", "Zoya", "F", "G5", "Eng", j, None),       # HR only
        Employee("EMP-050", "Omar", "M", "G1", "Eng", j, "EMP-005"),
    ]}


def make_world(opening=None, comp_credits=None, start=date(2026, 12, 1)):
    emps = employees()
    base = {}
    for e in emps:
        base[(e, "CL")] = D("0")
        base[(e, "SL")] = D("10")
        base[(e, "EL")] = D("20")
    base.update(opening or {})
    balances = LeaveBalances(base)
    cal = HolidayCalendar(HOLIDAYS)
    accrual = AccrualEngine(emps, balances, start)
    engine = LeaveEngine(emps, cal, balances, CompOffLedger(comp_credits or []), accrual)
    return engine, balances, accrual, cal


_line = [0]


def apply(engine, req_id, emp_id, ltype, frm, to, applied, medical=False):
    _line[0] += 1
    engine.accrual.advance_to(applied)
    return engine.apply(_line[0], req_id, emp_id, ltype, frm, to, applied, "test", medical)
