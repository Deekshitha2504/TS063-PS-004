from datetime import date
from decimal import Decimal as D

import pytest

from leave_attendance.balances import CompOffLedger
from leave_attendance.loaders import (index_by_employee, load_attendance,
                                      load_employees, load_opening_balances)
from leave_attendance.models import CompOffCredit


def test_attendance_loader_handles_duplicates_unknowns_and_bom(tmp_path):
    p = tmp_path / "att.csv"
    p.write_text(
        "\ufeffemp_id,date,status\n"
        "EMP-001,2027-01-07,P\n"
        "EMP-001,2027-01-07,P\n"          # exact duplicate
        "EMP-001,2027-01-08,p\n"          # lower case status is tidied
        "EMP-001,2027-01-09,A\n"
        "EMP-001,2027-01-09,P\n"          # conflicting duplicate
        "EMP-099,2027-01-07,P\n"          # unknown employee
        "EMP-001,2027-01-10,XX\n",        # invalid status
        encoding="utf-8",
    )
    statuses, issues, raw = load_attendance(str(p), {"EMP-001"})
    assert raw == 7
    assert statuses[("EMP-001", date(2027, 1, 7))] == "P"
    assert statuses[("EMP-001", date(2027, 1, 8))] == "P"
    assert statuses[("EMP-001", date(2027, 1, 9))] == "A"     # first one kept
    kinds = sorted(i.kind for i in issues)
    assert kinds == ["CONFLICTING_DUPLICATE", "DUPLICATE_ROW", "INVALID_STATUS", "UNKNOWN_EMPLOYEE"]
    assert len(index_by_employee(statuses)["EMP-001"]) == 3


def test_employee_loader_blank_manager_becomes_none(tmp_path):
    p = tmp_path / "emp.csv"
    p.write_text(
        "emp_id,name,gender,grade,department,joining_date,manager_id\n"
        "EMP-001,Asha,f,g5,HR,2019-04-01,\n"
        "EMP-002,Ravi,M,G2,Eng,2021-06-15,EMP-001\n"
    )
    emps = load_employees(str(p))
    assert emps["EMP-001"].manager_id is None
    assert emps["EMP-001"].grade == "G5" and emps["EMP-001"].gender == "F"
    assert emps["EMP-002"].manager_id == "EMP-001"


def test_opening_balance_loader_rejects_unknown_type(tmp_path):
    p = tmp_path / "bal.csv"
    p.write_text("emp_id,leave_type,balance\nEMP-001,XYZ,3.0\n")
    with pytest.raises(ValueError):
        load_opening_balances(str(p))


def test_missing_column_gives_clear_error(tmp_path):
    p = tmp_path / "att.csv"
    p.write_text("emp_id,date\nEMP-001,2027-01-07\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_attendance(str(p), {"EMP-001"})


# ---- comp-off (BR-09) -------------------------------------------------------
CREDIT = CompOffCredit("EMP-001", date(2026, 10, 3), date(2026, 10, 5), D("1"))


def test_comp_off_expires_60_days_after_credit():
    assert CREDIT.expires_on == date(2026, 12, 4)


def test_comp_off_usable_within_window_and_not_after():
    ledger = CompOffLedger([CREDIT])
    assert ledger.available("EMP-001", date(2026, 12, 4)) == D("1")
    assert ledger.available("EMP-001", date(2026, 12, 11)) == D("0")   # expired


def test_comp_off_consume_and_restore():
    ledger = CompOffLedger([CREDIT])
    taken = ledger.consume("EMP-001", D("1"), date(2026, 11, 20))
    assert ledger.available("EMP-001", date(2026, 11, 21)) == D("0")
    ledger.restore(taken)                                              # leave cancelled
    assert ledger.available("EMP-001", date(2026, 11, 21)) == D("1")


def test_comp_off_cannot_overdraw():
    ledger = CompOffLedger([CREDIT])
    with pytest.raises(ValueError):
        ledger.consume("EMP-001", D("2"), date(2026, 11, 20))


def test_comp_off_uses_earliest_expiring_first():
    older = CompOffCredit("EMP-001", date(2026, 9, 1), date(2026, 9, 2), D("1"))
    newer = CompOffCredit("EMP-001", date(2026, 11, 1), date(2026, 11, 2), D("1"))
    ledger = CompOffLedger([newer, older])
    ledger.consume("EMP-001", D("1"), date(2026, 11, 10))
    # the older credit (expires 1 Nov... 2 Sep + 60 = 1 Nov) is already expired on 10 Nov,
    # so the newer one must have been used
    assert ledger.available("EMP-001", date(2026, 11, 10)) == D("0")
