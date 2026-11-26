"""Run a tiny commands.txt through the whole pipeline and check the three output files."""
import csv
import os
from datetime import date, timedelta

from leave_attendance.commands import CommandRunner

EMP_ROWS = [
    ("EMP-001", "Hema", "F", "G5", "HR", "2020-01-01", ""),
    ("EMP-005", "Mani", "M", "G4", "Eng", "2020-01-01", "EMP-001"),
    ("EMP-020", "Gita", "F", "G2", "Eng", "2020-01-01", "EMP-005"),
]


def w(path, header, rows):
    with open(path, "w", newline="") as f:
        c = csv.writer(f)
        c.writerow(header)
        c.writerows(rows)


def build(tmp_path, commands_text):
    d = tmp_path / "data"
    d.mkdir()
    w(d / "employees.csv", ["emp_id", "name", "gender", "grade", "department", "joining_date", "manager_id"], EMP_ROWS)
    w(d / "holidays.csv", ["date", "name"], [("2026-12-25", "Christmas")])
    bal = [(e[0], t, v) for e in EMP_ROWS for t, v in (("CL", "0.0"), ("SL", "10.0"), ("EL", "20.0"))]
    w(d / "leave_balances_opening.csv", ["emp_id", "leave_type", "balance"], bal)
    w(d / "comp_off_credits.csv", ["emp_id", "worked_date", "credited_on", "days"], [])
    rows, day = [], date(2026, 12, 1)
    while day.month == 12:
        for e in EMP_ROWS:
            status = "WO" if day.weekday() >= 5 else "P"
            if day == date(2026, 12, 25):
                status = "H"
            if e[0] == "EMP-020" and day in (date(2026, 12, 7), date(2026, 12, 14)):
                status = "A"
            rows.append((e[0], day.isoformat(), status))
        day += timedelta(days=1)
    w(d / "attendance_2026_12.csv", ["emp_id", "date", "status"], rows)
    (d / "commands.txt").write_text(commands_text)
    return d


COMMANDS = """# sample event log
LEAVE_APPLY|R1|EMP-020|SL|2026-12-07|2026-12-07|2026-12-02|fever|false
LEAVE_APPROVE|R1|EMP-005|2026-12-03

LEAVE_APPLY|R2|EMP-020|SL|2026-12-14|2026-12-17|2026-12-10|flu|false
LEAVE_APPROVE|R1|EMP-005|2026-12-04
REVISE_CTC|EMP-020|2026-12-10|900000
RUN_PAYROLL|2026-12|2026-12-31
"""


def test_runner_end_to_end(tmp_path):
    d = build(tmp_path, COMMANDS)
    runner = CommandRunner(str(d))
    runner.run_file(str(d / "commands.txt"))
    out = tmp_path / "out"
    runner.write_outputs(str(out))

    log = list(csv.DictReader(open(out / "command_log.csv")))
    by_line = {int(r["line_no"]): r for r in log}
    assert sorted(by_line) == [2, 3, 5, 6, 7, 8]                # physical line numbers
    assert by_line[2]["status"] == "OK"
    assert by_line[2]["rule_ids"] == ""                         # BR-12 only appears once approved
    assert by_line[3]["rule_ids"] == "BR-12"
    assert by_line[5]["status"] == "REJECTED" and "BR-06" in by_line[5]["rule_ids"]
    assert by_line[6]["status"] == "REJECTED"                   # R1 is no longer PENDING
    assert by_line[7]["status"] == "NOT_HANDLED"                # payroll side not attached
    assert by_line[8]["status"] == "OK"

    ledger = {r["req_id"]: r for r in csv.DictReader(open(out / "leave_ledger.csv"))}
    assert list(ledger) == ["R1", "R2"]
    assert ledger["R1"]["status"] == "APPROVED" and ledger["R1"]["approved_on"] == "2026-12-03"
    assert ledger["R1"]["days_counted"] == "1.0" and ledger["R1"]["lop_days"] == "0.0"
    assert ledger["R2"]["status"] == "REJECTED" and ledger["R2"]["days_counted"] == "4.0"
    assert ledger["R2"]["approved_on"] == ""

    # December summary: R1 covers 7 Dec, 14 Dec is an unauthorised absence
    s = runner.summaries[(2026, 12)]["EMP-020"]
    assert s.calendar_days == 31 and s.unauthorised_days == 1 and s.payable_days == 30
    assert s.check_identity()

    bal = list(csv.DictReader(open(out / "leave_balances.csv")))
    assert bal[0]["as_of_date"] == "2026-12-31"
    sl = [r for r in bal if r["emp_id"] == "EMP-020" and r["leave_type"] == "SL"][0]
    assert sl["balance"] == "10.0"        # 10 opening + Dec accrual 1 - 1 day taken (R2 released)


def test_payroll_hook_is_called_with_summaries(tmp_path):
    d = build(tmp_path, COMMANDS)
    seen = {}

    def hook(runner, line_no, args, ctx):
        seen.update(ctx)
        return "OK", "payroll ran", ["BR-16"]

    runner = CommandRunner(str(d), handlers={"RUN_PAYROLL": hook})
    runner.run_file(str(d / "commands.txt"))
    assert seen["year"] == 2026 and seen["month"] == 12
    assert set(seen["summaries"]) == {"EMP-001", "EMP-005", "EMP-020"}
    assert runner.log[-1] == (8, "RUN_PAYROLL", "OK", ["BR-16"], "payroll ran")


def test_exit_registers_last_working_day_for_accrual(tmp_path):
    cmds = "EXIT|EMP-020|2026-12-01|2026-12-03|30|0.00\nRUN_PAYROLL|2026-12|2026-12-31\n"
    d = build(tmp_path, cmds)
    runner = CommandRunner(str(d))
    runner.run_file(str(d / "commands.txt"))
    assert runner.accrual.exit_dates["EMP-020"] == date(2026, 12, 3)


def test_bad_lines_are_logged_not_fatal(tmp_path):
    cmds = ("LEAVE_APPLY|R1|EMP-020|CL\n"                                   # too few args
            "NOPE|x\n"                                                       # unknown command
            "LEAVE_CANCEL|R9|2026-12-02\n"                                   # unknown request
            "LEAVE_APPLY|R2|EMP-020|SL|2026-12-07|2026-12-07|2026-12-02|ok|false\n")
    d = build(tmp_path, cmds)
    runner = CommandRunner(str(d))
    runner.run_file(str(d / "commands.txt"))
    statuses = [e[2] for e in runner.log]
    assert statuses == ["ERROR", "NOT_HANDLED", "REJECTED", "OK"]
