from datetime import date

from leave_attendance.calendar_utils import (HolidayCalendar, days_in_month,
                                             iter_dates, parse_month)

CAL = HolidayCalendar({date(2027, 1, 26): "Republic Day"})


def test_weekend_and_holiday_are_off_days():
    assert CAL.is_weekly_off(date(2027, 1, 9))        # Saturday
    assert CAL.is_holiday(date(2027, 1, 26))          # Tuesday holiday
    assert not CAL.is_working_day(date(2027, 1, 26))
    assert CAL.is_working_day(date(2027, 1, 27))


def test_add_working_days_skips_weekend():
    # Fri 8 Jan + 1 working day = Mon 11 Jan
    assert CAL.add_working_days(date(2027, 1, 8), 1) == date(2027, 1, 11)
    # Mon 4 Jan + 5 working days = Mon 11 Jan
    assert CAL.add_working_days(date(2027, 1, 4), 5) == date(2027, 1, 11)


def test_add_working_days_skips_holiday():
    # Fri 22 Jan + 3 working days: Mon 25, (Tue 26 holiday), Wed 27, Thu 28
    assert CAL.add_working_days(date(2027, 1, 22), 3) == date(2027, 1, 28)


def test_previous_and_next_working_day():
    assert CAL.previous_working_day(date(2027, 1, 11)) == date(2027, 1, 8)
    assert CAL.next_working_day(date(2027, 1, 8)) == date(2027, 1, 11)


def test_month_helpers():
    assert days_in_month(2027, 2) == 28
    assert days_in_month(2028, 2) == 29
    assert parse_month("2026-12") == (2026, 12)
    assert len(list(iter_dates(date(2027, 1, 28), date(2027, 2, 3)))) == 7
