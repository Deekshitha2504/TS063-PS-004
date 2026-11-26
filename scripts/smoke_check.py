"""Run this on the REAL sample data to confirm everything loads.

    python scripts/smoke_check.py --data data

Expected counts from the README: 50 employees, 5 holidays, 144 opening-balance
rows, 2 comp-off credits, attendance raw rows 1504 / 1529 / 1355.
"""
import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from leave_attendance.accrual import AccrualEngine                      # noqa: E402
from leave_attendance.attendance import summarise_month                 # noqa: E402
from leave_attendance.balances import CompOffLedger, LeaveBalances      # noqa: E402
from leave_attendance.loaders import (index_by_employee, load_attendance,  # noqa: E402
                                      load_comp_off_credits, load_employees,
                                      load_holidays, load_opening_balances)

ATTENDANCE_FILES = [("attendance_2026_12.csv", 2026, 12, 1504),
                    ("attendance_2027_01.csv", 2027, 1, 1529),
                    ("attendance_2027_02.csv", 2027, 2, 1355)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data", help="folder holding the sample CSVs")
    args = ap.parse_args()
    p = lambda name: os.path.join(args.data, name)   # noqa: E731

    employees = load_employees(p("employees.csv"))
    holidays = load_holidays(p("holidays.csv"))
    opening = load_opening_balances(p("leave_balances_opening.csv"))
    comp = load_comp_off_credits(p("comp_off_credits.csv"))
    print(f"employees        : {len(employees)}   (README: 50)")
    print(f"holidays         : {len(holidays)}   (README: 5)")
    print(f"opening balances : {len(opening)}   (README: 144)")
    print(f"comp-off credits : {len(comp)}   (README: 2)")
    for c in comp:
        print(f"   {c.emp_id} credited {c.credited_on} -> expires {c.expires_on}")

    all_status = {}
    for fname, year, month, expected in ATTENDANCE_FILES:
        statuses, issues, raw = load_attendance(p(fname), set(employees))
        all_status[(year, month)] = statuses
        print(f"\n{fname}: raw rows {raw} (README: {expected}), kept {len(statuses)}")
        for i in issues:
            print(f"   ISSUE line {i.line_no}: {i.kind} - {i.message}")

    # Dry run: December accrual, then year end, with no leave requests applied yet
    balances = LeaveBalances(opening)
    engine = AccrualEngine(employees, balances, date(2026, 12, 1))
    engine.advance_to(date(2026, 12, 31))
    result = engine.year_end()
    print("\nAfter December accrual + YEAR_END (no leave requests applied yet):")
    for emp_id in ("EMP-023", "EMP-049"):
        if emp_id in employees:
            print(f"   {emp_id}: CL {balances.get(emp_id, 'CL')}  "
                  f"SL {balances.get(emp_id, 'SL')}  EL {balances.get(emp_id, 'EL')}")
    print(f"   {len(result.lapsed)} lapsed entries at year end")

    # Dry run: December attendance with NO leave coverage
    dec = index_by_employee(all_status[(2026, 12)])
    print("\nDecember attendance (no leave coverage applied yet):")
    for emp_id in ("EMP-049", "EMP-001"):
        if emp_id in dec:
            s = summarise_month(emp_id, 2026, 12, dec[emp_id], {})
            print(f"   {emp_id}: calendar {s.calendar_days}, payable {s.payable_days}, "
                  f"unauthorised {s.unauthorised_days}, not employed {s.not_employed_days}, "
                  f"identity ok = {s.check_identity()}")


if __name__ == "__main__":
    main()
