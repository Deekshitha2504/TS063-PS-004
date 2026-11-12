from datetime import date

from leave_attendance.calendar_utils import HolidayCalendar
from leave_attendance.leave_rules import counted_days, is_clubbed, required_roles

CAL = HolidayCalendar({date(2027, 1, 26): "Republic Day"})
FRI, MON = date(2027, 1, 8), date(2027, 1, 11)


def test_el_fri_to_mon_counts_four_with_sandwich():
    days, sandwiched = counted_days("EL", FRI, MON, CAL)
    assert len(days) == 4 and sandwiched == 2


def test_cl_and_sl_fri_to_mon_count_two_no_sandwich():
    assert len(counted_days("CL", FRI, MON, CAL)[0]) == 2
    assert len(counted_days("SL", FRI, MON, CAL)[0]) == 2


def test_lop_sandwich_counts_like_el():
    assert len(counted_days("LOP", FRI, MON, CAL)[0]) == 4


def test_leading_and_trailing_weekend_not_counted_for_el():
    days, _ = counted_days("EL", date(2027, 1, 9), date(2027, 1, 12), CAL)  # Sat..Tue
    assert days[0] == date(2027, 1, 11) and len(days) == 2
    days, _ = counted_days("EL", date(2027, 1, 7), date(2027, 1, 10), CAL)  # Thu..Sun
    assert days[-1] == date(2027, 1, 8) and len(days) == 2


def test_holiday_between_leave_days_counts_for_el_not_cl():
    # Mon 25 Jan, Tue 26 Jan (holiday), Wed 27 Jan
    assert len(counted_days("EL", date(2027, 1, 25), date(2027, 1, 27), CAL)[0]) == 3
    assert len(counted_days("CL", date(2027, 1, 25), date(2027, 1, 27), CAL)[0]) == 2


def test_month_boundary_el_counts_seven():
    days, sandwiched = counted_days("EL", date(2027, 1, 28), date(2027, 2, 3), CAL)
    assert len(days) == 7 and sandwiched == 2
    assert sum(1 for d in days if d.month == 1) == 4
    assert sum(1 for d in days if d.month == 2) == 3


def test_maternity_counts_every_calendar_day():
    days, _ = counted_days("MATERNITY", date(2027, 1, 20), date(2027, 7, 20), CAL)
    assert len(days) == 182


def test_only_weekend_selected_gives_zero_days():
    assert counted_days("CL", date(2027, 1, 9), date(2027, 1, 10), CAL)[0] == []


def test_required_roles_by_grade():
    assert required_roles("G1", True) == {"MANAGER"}
    assert required_roles("G2", True) == {"MANAGER"}
    assert required_roles("G3", True) == {"MANAGER", "HR"}
    assert required_roles("G4", True) == {"MANAGER", "HR"}
    assert required_roles("G5", True) == {"HR"}
    assert required_roles("G2", False) == {"HR"}        # no manager on file -> HR
    assert required_roles("G3", False) == {"HR"}


def test_is_clubbed_adjacent_ignoring_weekend():
    el_days = {date(2027, 1, 8)}                          # Friday
    assert is_clubbed([date(2027, 1, 11)], el_days, CAL)  # CL on Monday: clubbed
    assert not is_clubbed([date(2027, 1, 12)], el_days, CAL)
