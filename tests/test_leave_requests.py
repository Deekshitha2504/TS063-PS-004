from datetime import date
from decimal import Decimal as D

import pytest

from helpers import apply, make_world
from leave_attendance.attendance import HALF_LOP, LOP, PAID
from leave_attendance.leave_requests import CommandRejected
from leave_attendance.models import CompOffCredit


# ------------------------------------------------------------------ validity
def test_sl_four_days_without_medical_flag_rejected_with_flag_allowed():
    eng, bal, acc, cal = make_world()
    r = apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 10), date(2026, 12, 4))
    assert r.status == "REJECTED" and "BR-06" in r.rule_ids
    r2 = apply(eng, "R2", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 10), date(2026, 12, 4), medical=True)
    assert r2.status == "PENDING"


def test_sl_three_days_needs_no_flag():
    eng, *_ = make_world()
    r = apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 9), date(2026, 12, 4))
    assert r.status == "PENDING"


def test_el_needs_seven_days_notice():
    eng, *_ = make_world()
    short = apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 14), date(2026, 12, 14), date(2026, 12, 10))
    assert short.status == "REJECTED" and "BR-08" in short.rule_ids
    ok = apply(eng, "R2", "EMP-020", "EL", date(2026, 12, 17), date(2026, 12, 17), date(2026, 12, 10))
    assert ok.status == "PENDING"


def test_cl_right_after_el_is_clubbing_and_rejected():
    eng, *_ = make_world()
    el = apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 14), date(2026, 12, 16), date(2026, 12, 2))
    assert el.status == "PENDING"
    cl = apply(eng, "R2", "EMP-020", "CL", date(2026, 12, 17), date(2026, 12, 17), date(2026, 12, 3))
    assert cl.status == "REJECTED" and "BR-07" in cl.rule_ids


def test_cl_with_a_gap_after_el_is_fine():
    eng, *_ = make_world(opening={("EMP-020", "CL"): D("3")})
    apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 14), date(2026, 12, 16), date(2026, 12, 2))
    cl = apply(eng, "R2", "EMP-020", "CL", date(2026, 12, 21), date(2026, 12, 21), date(2026, 12, 3))
    assert cl.status == "PENDING"


def test_el_right_after_cl_is_also_clubbing():
    eng, *_ = make_world(opening={("EMP-020", "CL"): D("3")})
    apply(eng, "R1", "EMP-020", "CL", date(2026, 12, 14), date(2026, 12, 14), date(2026, 12, 1))
    el = apply(eng, "R2", "EMP-020", "EL", date(2026, 12, 15), date(2026, 12, 16), date(2026, 12, 2))
    assert el.status == "REJECTED" and "BR-07" in el.rule_ids


def test_cancelled_el_no_longer_blocks_cl():
    eng, *_ = make_world(opening={("EMP-020", "CL"): D("3")})
    apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 14), date(2026, 12, 16), date(2026, 12, 2))
    eng.cancel("R1", date(2026, 12, 3))
    cl = apply(eng, "R2", "EMP-020", "CL", date(2026, 12, 17), date(2026, 12, 17), date(2026, 12, 4))
    assert cl.status == "PENDING"


def test_maternity_only_for_female():
    eng, *_ = make_world()
    man = apply(eng, "R1", "EMP-050", "MATERNITY", date(2027, 1, 20), date(2027, 7, 20), date(2026, 12, 15))
    assert man.status == "REJECTED"
    woman = apply(eng, "R2", "EMP-020", "MATERNITY", date(2027, 1, 20), date(2027, 7, 20), date(2026, 12, 15))
    assert woman.status == "PENDING" and woman.days_counted == D("182")


def test_overlapping_request_rejected():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 8), date(2026, 12, 2))
    r = apply(eng, "R2", "EMP-020", "CL", date(2026, 12, 8), date(2026, 12, 8), date(2026, 12, 3))
    assert r.status == "REJECTED" and "BR-35" in r.rule_ids


def test_rejected_request_keeps_days_but_reserves_no_balance():
    eng, bal, acc, _ = make_world()
    acc.advance_to(date(2026, 12, 4))            # let December's accrual happen first
    before = bal.get("EMP-020", "SL")
    r = apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 10), date(2026, 12, 4))
    assert r.days_counted == D("4") and bal.get("EMP-020", "SL") == before


# --------------------------------------------------------------- comp-off
CREDIT = CompOffCredit("EMP-020", date(2026, 10, 3), date(2026, 10, 5), D("1"))


def test_expired_comp_off_is_rejected():
    eng, *_ = make_world(comp_credits=[CREDIT])
    r = apply(eng, "R1", "EMP-020", "COMP_OFF", date(2026, 12, 11), date(2026, 12, 11), date(2026, 12, 7))
    assert r.status == "REJECTED" and "BR-09" in r.rule_ids


def test_comp_off_within_window_is_paid():
    eng, *_ = make_world(comp_credits=[CREDIT])
    r = apply(eng, "R1", "EMP-020", "COMP_OFF", date(2026, 12, 3), date(2026, 12, 3), date(2026, 12, 2))
    assert r.status == "PENDING" and r.paid_qty == D("1") and r.lop_qty == D("0")


# ------------------------------------------------------- LOP conversion BR-11
def test_excess_days_convert_to_lop():
    eng, bal, *_ = make_world()   # CL opening 0, +1 December accrual = 1
    r = apply(eng, "R1", "EMP-020", "CL", date(2026, 12, 14), date(2026, 12, 16), date(2026, 12, 2))
    assert r.days_counted == D("3") and r.paid_qty == D("1") and r.lop_qty == D("2")
    assert "BR-11" in r.rule_ids
    assert bal.get("EMP-020", "CL") == D("0")
    assert [r.day_cover[d] for d in sorted(r.day_cover)] == [PAID, LOP, LOP]


def test_half_day_balance_gives_half_lop():
    eng, bal, *_ = make_world(opening={("EMP-020", "EL"): D("1.5")})
    r = apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 14), date(2026, 12, 15), date(2026, 12, 2))
    assert r.paid_qty == D("1.5") and r.lop_qty == D("0.5")
    assert r.day_cover[date(2026, 12, 15)] == HALF_LOP


def test_lop_request_is_all_lop():
    eng, *_ = make_world()
    r = apply(eng, "R1", "EMP-020", "LOP", date(2026, 12, 14), date(2026, 12, 15), date(2026, 12, 2))
    assert r.lop_qty == D("2")


# ------------------------------------------------------------- approvals
def approve_ok(eng, req_id, who, on=date(2026, 12, 3)):
    return eng.approve(req_id, who, on)


def test_g2_needs_manager_only():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    r = approve_ok(eng, "R1", "EMP-005")
    assert r.status == "APPROVED" and r.approved_on == date(2026, 12, 3)


def test_g3_needs_manager_and_hr():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-030", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    assert approve_ok(eng, "R1", "EMP-005").status == "PENDING"      # manager only: not enough
    assert approve_ok(eng, "R1", "EMP-002").status == "APPROVED"     # then HR


def test_g5_needs_hr_only():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-040", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    with pytest.raises(CommandRejected):
        approve_ok(eng, "R1", "EMP-005")                             # a manager is not enough for G5
    assert approve_ok(eng, "R1", "EMP-002").status == "APPROVED"


def test_wrong_person_cannot_approve_or_self_approve():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    with pytest.raises(CommandRejected):
        approve_ok(eng, "R1", "EMP-050")
    with pytest.raises(CommandRejected):
        approve_ok(eng, "R1", "EMP-020")


def test_cannot_approve_twice():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    approve_ok(eng, "R1", "EMP-005")
    with pytest.raises(CommandRejected):
        approve_ok(eng, "R1", "EMP-005")


def test_reject_restores_balance_and_cancel_restores_balance():
    eng, bal, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 8), date(2026, 12, 2))
    assert bal.get("EMP-020", "SL") == D("9")          # 10 + Dec accrual 1 - 2
    eng.reject("R1", "EMP-005", date(2026, 12, 3), "busy")
    assert bal.get("EMP-020", "SL") == D("11") and eng.requests["R1"].status == "REJECTED"
    apply(eng, "R2", "EMP-020", "SL", date(2026, 12, 9), date(2026, 12, 9), date(2026, 12, 4))
    eng.approve("R2", "EMP-005", date(2026, 12, 5))
    eng.cancel("R2", date(2026, 12, 6))
    assert bal.get("EMP-020", "SL") == D("11") and eng.requests["R2"].status == "CANCELLED"


def test_cannot_cancel_once_leave_has_started():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    with pytest.raises(CommandRejected):
        eng.cancel("R1", date(2026, 12, 7))


# ---------------------------------------------------------- auto-approval
def test_auto_approval_after_five_working_days():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-030", "SL", date(2026, 12, 21), date(2026, 12, 21), date(2026, 12, 7))  # Mon
    approve_ok(eng, "R1", "EMP-005", date(2026, 12, 8))           # HR approval is missing
    eng.sweep_auto_approvals(date(2026, 12, 11), inclusive=True)   # only 4 working days gone
    assert eng.requests["R1"].status == "PENDING"
    eng.sweep_auto_approvals(date(2026, 12, 14), inclusive=True)   # Mon 14 Dec = 5 working days
    r = eng.requests["R1"]
    assert r.status == "AUTO_APPROVED" and r.approved_on == date(2026, 12, 14) and "BR-13" in r.rule_ids


def test_auto_approval_boundary_inclusive_flag():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 21), date(2026, 12, 21), date(2026, 12, 7))
    eng.sweep_auto_approvals(date(2026, 12, 14), inclusive=False)
    assert eng.requests["R1"].status == "PENDING"


def test_auto_approval_counts_holiday_as_non_working():
    eng, *_ = make_world()
    # applied Mon 21 Dec: working days = 22, 23, 24, (25 holiday), 28, 29 -> deadline Tue 29 Dec
    apply(eng, "R1", "EMP-020", "SL", date(2027, 1, 4), date(2027, 1, 4), date(2026, 12, 21))
    eng.sweep_auto_approvals(date(2026, 12, 28), inclusive=True)
    assert eng.requests["R1"].status == "PENDING"
    eng.sweep_auto_approvals(date(2026, 12, 29), inclusive=True)
    assert eng.requests["R1"].status == "AUTO_APPROVED"


def test_lop_is_never_auto_approved():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "LOP", date(2026, 12, 21), date(2026, 12, 21), date(2026, 12, 7))
    eng.sweep_auto_approvals(date(2027, 3, 1), inclusive=True)
    assert eng.requests["R1"].status == "PENDING"


def test_pending_leave_does_not_cover_attendance_but_approved_does():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    assert eng.leave_cover("EMP-020", 2026, 12) == {}
    eng.approve("R1", "EMP-005", date(2026, 12, 3))
    assert eng.leave_cover("EMP-020", 2026, 12) == {date(2026, 12, 7): PAID}


# ----------------------------------------------- year-end spanning (README)
def test_el_spanning_year_end_charges_each_year_separately():
    eng, bal, acc, cal = make_world(opening={("EMP-020", "EL"): D("40")})
    r = apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 29), date(2027, 1, 4), date(2026, 12, 10))
    assert r.days_counted == D("7")
    assert bal.get("EMP-020", "EL") == D("37")           # only the 3 December days so far
    assert len(r.deferred_days) == 4                      # 4 January days wait for January
    eng.approve("R1", "EMP-005", date(2026, 12, 11))

    acc.advance_to(date(2026, 12, 31))
    acc.year_end()
    assert bal.get("EMP-020", "EL") == D("41.5")         # 37 + Q4 credit 4.5, under the cap of 45
    acc.advance_to(date(2027, 1, 5))                      # January accrues; deferred days charged
    assert bal.get("EMP-020", "EL") == D("37.5")
    assert r.deferred_days == [] and r.lop_qty == D("0") and r.paid_qty == D("7")
    jan_cover = eng.leave_cover("EMP-020", 2027, 1)
    assert len(jan_cover) == 4 and set(jan_cover.values()) == {PAID}
    assert len(eng.leave_cover("EMP-020", 2026, 12)) == 3


def test_year_end_cap_applies_before_january_days_are_charged():
    # 44 + (-3 Dec days) = 41 + 4.5 = 45.5 -> capped at 45 -> then 4 January days -> 41
    eng, bal, acc, cal = make_world(opening={("EMP-020", "EL"): D("44")})
    apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 29), date(2027, 1, 4), date(2026, 12, 10))
    acc.advance_to(date(2026, 12, 31))
    result = acc.year_end()
    assert bal.get("EMP-020", "EL") == D("45")
    assert result.lapsed[("EMP-020", "EL")] == D("0.5")
    acc.advance_to(date(2027, 1, 5))
    assert bal.get("EMP-020", "EL") == D("41")


def test_cancel_before_january_removes_deferred_days():
    eng, bal, acc, cal = make_world(opening={("EMP-020", "EL"): D("40")})
    r = apply(eng, "R1", "EMP-020", "EL", date(2026, 12, 29), date(2027, 1, 4), date(2026, 12, 10))
    eng.cancel("R1", date(2026, 12, 15))
    assert bal.get("EMP-020", "EL") == D("40") and r.deferred_days == []
    acc.advance_to(date(2026, 12, 31)); acc.year_end(); acc.advance_to(date(2027, 1, 5))
    assert bal.get("EMP-020", "EL") == D("44.5")


def test_leave_spanning_month_boundary_is_split_by_month_in_cover():
    eng, bal, acc, cal = make_world()
    acc.advance_to(date(2027, 1, 2)); acc.year_end()
    r = apply(eng, "R1", "EMP-020", "EL", date(2027, 1, 28), date(2027, 2, 3), date(2027, 1, 12))
    eng.approve("R1", "EMP-005", date(2027, 1, 13))
    acc.advance_to(date(2027, 2, 3))
    assert len(eng.leave_cover("EMP-020", 2027, 1)) == 4     # 28, 29, 30, 31 Jan (weekend sandwiched)
    assert len(eng.leave_cover("EMP-020", 2027, 2)) == 3     # 1, 2, 3 Feb


# ------------------------------------------------ BR-35 overlap (trainers)
def test_overlap_checks_the_date_range_not_just_counted_days():
    eng, *_ = make_world(opening={("EMP-020", "CL"): D("3")})
    # SL Thu 3 Dec - Mon 7 Dec counts Thu, Fri, Mon; Saturday 5 Dec is inside the range
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 3), date(2026, 12, 7), date(2026, 12, 2), medical=True)
    r = apply(eng, "R2", "EMP-020", "EL", date(2026, 12, 5), date(2026, 12, 12), date(2026, 11, 20))
    assert r.status == "REJECTED" and "BR-35" in r.rule_ids


def test_overlap_blocked_by_pending_and_approved_but_not_by_rejected_or_cancelled():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 8), date(2026, 12, 2))      # PENDING
    assert apply(eng, "R2", "EMP-020", "SL", date(2026, 12, 8), date(2026, 12, 8), date(2026, 12, 2)).status == "REJECTED"
    eng.approve("R1", "EMP-005", date(2026, 12, 3))                                                    # APPROVED
    assert apply(eng, "R3", "EMP-020", "SL", date(2026, 12, 8), date(2026, 12, 8), date(2026, 12, 4)).status == "REJECTED"
    eng.cancel("R1", date(2026, 12, 4))                                                                # CANCELLED
    assert apply(eng, "R4", "EMP-020", "SL", date(2026, 12, 8), date(2026, 12, 8), date(2026, 12, 4)).status == "PENDING"
    eng.reject("R4", "EMP-005", date(2026, 12, 5), "no")                                               # REJECTED
    assert apply(eng, "R5", "EMP-020", "SL", date(2026, 12, 8), date(2026, 12, 8), date(2026, 12, 5)).status == "PENDING"


def test_overlap_is_per_employee():
    eng, *_ = make_world()
    apply(eng, "R1", "EMP-020", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2))
    assert apply(eng, "R2", "EMP-050", "SL", date(2026, 12, 7), date(2026, 12, 7), date(2026, 12, 2)).status == "PENDING"
