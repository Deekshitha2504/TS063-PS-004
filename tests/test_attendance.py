from datetime import date
from decimal import Decimal as D

from leave_attendance.attendance import HALF_LOP, LOP, PAID, summarise_month


def dec_days(first, last, status):
    return {date(2026, 12, d): status for d in range(first, last + 1)}


def test_all_present_full_month():
    s = summarise_month("E", 2026, 12, dec_days(1, 31, "P"), {})
    assert s.calendar_days == 31
    assert s.payable_days == D("31")
    assert s.check_identity()


def test_joiner_on_16th_has_16_payable_of_31():
    s = summarise_month("E", 2026, 12, dec_days(16, 31, "P"), {})
    assert s.calendar_days == 31 and s.payable_days == D("16")
    assert s.not_employed_days == 15
    assert s.check_identity()


def test_half_day_wfh_and_holiday():
    status = dec_days(1, 31, "P")
    status[date(2026, 12, 3)] = "HD"
    status[date(2026, 12, 4)] = "WFH"
    status[date(2026, 12, 25)] = "H"
    s = summarise_month("E", 2026, 12, status, {})
    assert s.payable_days == D("30.5")
    assert s.half_day_unpaid == D("0.5")
    assert s.check_identity()


def test_absent_is_paid_when_covered_by_approved_leave():
    status = dec_days(1, 31, "P")
    status[date(2026, 12, 7)] = "A"
    s = summarise_month("E", 2026, 12, status, {date(2026, 12, 7): PAID})
    assert s.payable_days == D("31") and s.unauthorised_days == D("0")


def test_absent_without_leave_is_unauthorised():
    status = dec_days(1, 31, "P")
    status[date(2026, 12, 7)] = "A"
    s = summarise_month("E", 2026, 12, status, {})
    assert s.payable_days == D("30") and s.unauthorised_days == D("1")
    assert s.check_identity()


def test_lop_leave_and_sandwiched_weekend_are_unpaid():
    status = dec_days(1, 31, "P")
    status[date(2026, 12, 4)] = "A"      # Fri LOP
    status[date(2026, 12, 5)] = "WO"     # Sat sandwiched
    status[date(2026, 12, 6)] = "WO"     # Sun sandwiched
    status[date(2026, 12, 7)] = "A"      # Mon LOP
    cover = {date(2026, 12, d): LOP for d in (4, 5, 6, 7)}
    s = summarise_month("E", 2026, 12, status, cover)
    assert s.lop_days == D("4") and s.payable_days == D("27")
    assert s.check_identity()


def test_sandwiched_weekend_inside_paid_el_stays_paid():
    status = dec_days(1, 31, "P")
    status[date(2026, 12, 4)] = "A"
    status[date(2026, 12, 5)] = "WO"
    status[date(2026, 12, 7)] = "A"
    cover = {date(2026, 12, 4): PAID, date(2026, 12, 5): PAID, date(2026, 12, 7): PAID}
    s = summarise_month("E", 2026, 12, status, cover)
    assert s.payable_days == D("31") and s.lop_days == D("0")


def test_maternity_absent_days_are_paid():
    status = dec_days(1, 31, "A")
    cover = {d: PAID for d in status}
    s = summarise_month("E", 2026, 12, status, cover)
    assert s.payable_days == D("31")


def test_present_on_holiday_counts_once():
    status = dec_days(1, 31, "P")
    status[date(2026, 12, 25)] = "P"     # worked on a holiday
    s = summarise_month("E", 2026, 12, status, {})
    assert s.payable_days == D("31")     # not 32 - no double pay


def test_half_lop_day_is_half_paid_half_lop():
    status = dec_days(1, 31, "P")
    status[date(2026, 12, 7)] = "A"
    s = summarise_month("E", 2026, 12, status, {date(2026, 12, 7): HALF_LOP})
    assert s.payable_days == D("30.5") and s.lop_days == D("0.5")
    assert s.check_identity()
