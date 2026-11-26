from datetime import date
from decimal import Decimal as D

from leave_attendance.accrual import AccrualEngine, accrual_eligible
from leave_attendance.balances import LeaveBalances
from leave_attendance.models import Employee


def emp(emp_id, joining):
    return Employee(emp_id, emp_id, "F", "G2", "Eng", joining, "EMP-001")


# ---- BR-04: joiner pro-rata -------------------------------------------------
def test_joiner_on_15th_accrues_16th_does_not():
    assert accrual_eligible(date(2026, 12, 15), 2026, 12)
    assert not accrual_eligible(date(2026, 12, 16), 2026, 12)


def test_joiner_on_1st_accrues():
    assert accrual_eligible(date(2027, 1, 1), 2027, 1)


def test_joiner_accrues_from_next_month_after_16th():
    assert accrual_eligible(date(2026, 12, 16), 2027, 1)


def test_not_yet_joined_and_already_left():
    assert not accrual_eligible(date(2027, 3, 1), 2027, 1)
    assert not accrual_eligible(date(2020, 1, 1), 2027, 2, last_working_day=date(2027, 1, 20))
    assert accrual_eligible(date(2020, 1, 1), 2027, 1, last_working_day=date(2027, 1, 20))


# ---- engine ----------------------------------------------------------------
def make_engine(opening=None):
    employees = {
        "OLD": emp("OLD", date(2020, 1, 1)),
        "J16": emp("J16", date(2026, 12, 16)),   # joiner on the 16th
        "J12": emp("J12", date(2027, 1, 12)),    # joiner in January, before the 15th
    }
    base = {("OLD", "CL"): D("5"), ("OLD", "SL"): D("10"), ("OLD", "EL"): D("40")}
    base.update(opening or {})
    balances = LeaveBalances(base)
    return AccrualEngine(employees, balances, date(2026, 12, 1)), balances


def test_december_accrual_existing_vs_16th_joiner():
    eng, bal = make_engine()
    eng.advance_to(date(2026, 12, 2))
    assert bal.get("OLD", "CL") == D("6")
    assert bal.get("OLD", "SL") == D("11")
    assert bal.get("J16", "CL") == D("0")       # joined on the 16th -> nothing for December
    assert bal.get("J16", "SL") == D("0")


def test_accrual_not_repeated():
    eng, bal = make_engine()
    eng.advance_to(date(2026, 12, 2))
    eng.advance_to(date(2026, 12, 31))
    assert bal.get("OLD", "CL") == D("6")


def test_el_not_credited_monthly_and_q4_credited_at_year_end():
    eng, bal = make_engine()
    eng.advance_to(date(2026, 12, 31))
    assert bal.get("OLD", "EL") == D("40")      # arrears: nothing yet
    eng.year_end()
    assert bal.get("OLD", "EL") == D("44.5")    # 40 + 3 months x 1.5
    assert bal.get("J16", "EL") == D("0")       # joined 16 Dec: no Oct/Nov/Dec months


def test_year_end_caps_and_lapse():
    eng, bal = make_engine({("OLD", "SL"): D("35"), ("OLD", "EL"): D("43")})
    eng.advance_to(date(2026, 12, 31))
    result = eng.year_end()
    assert bal.get("OLD", "CL") == D("0")        # CL lapses
    assert result.lapsed[("OLD", "CL")] == D("6")
    assert bal.get("OLD", "SL") == D("30")       # SL carry cap (35 + Dec credit 1 = 36 -> 30)
    assert result.lapsed[("OLD", "SL")] == D("6")
    assert bal.get("OLD", "EL") == D("45")       # 43 + 4.5 = 47.5 -> 45
    assert result.lapsed[("OLD", "EL")] == D("2.5")


def test_january_not_credited_until_year_end_has_run():
    eng, bal = make_engine()
    eng.advance_to(date(2027, 1, 10))            # a January command arrives first
    assert bal.get("OLD", "CL") == D("6")        # December only; no January credit yet
    eng.year_end()                               # CL lapses to 0, then January is caught up
    assert bal.get("OLD", "CL") == D("1")        # January credit survives the lapse
    assert bal.get("OLD", "SL") == D("11") + D("1")   # 10 + Dec 1 + Jan 1


def test_january_joiner_before_15th_accrues_after_year_end():
    eng, bal = make_engine()
    eng.advance_to(date(2027, 1, 31))
    eng.year_end()
    assert bal.get("J12", "CL") == D("1")
    assert bal.get("J16", "CL") == D("1")        # joined Dec 16, accrues from January


def test_sl_annual_accrual_cap_is_12():
    # Existing employee joined long ago: 11 months accrued before December -> December makes 12.
    eng, bal = make_engine()
    eng.advance_to(date(2026, 12, 31))
    assert eng._sl_accrued_ytd["OLD"] == D("12")
    # A second December-style credit must not exceed the cap
    eng.accrue_month(2026, 12)
    assert bal.get("OLD", "SL") == D("11")


def test_cl_balance_never_exceeds_12():
    eng, bal = make_engine({("OLD", "CL"): D("12")})
    eng.advance_to(date(2026, 12, 2))
    assert bal.get("OLD", "CL") == D("12")


def test_exited_employee_stops_accruing():
    eng, bal = make_engine()
    eng.exit_dates["OLD"] = date(2026, 11, 30)   # left before December
    eng.advance_to(date(2026, 12, 31))
    assert bal.get("OLD", "CL") == D("5")


def test_q4_credit_only_once_if_called_twice():
    eng, bal = make_engine()
    eng.credit_el_quarter(2026, 4)
    eng.year_end()
    assert bal.get("OLD", "EL") == D("44.5")
