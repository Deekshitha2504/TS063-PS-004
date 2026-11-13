"""Behaviour confirmed by the 10 SECONDS reply to our questions (see docs/decision-log.md section E)."""
import csv
from datetime import date
from decimal import Decimal as D

from test_pipeline import build_data, w
from leave_attendance.pipeline import build, write_all


def run(tmp_path, commands, comp_rows=None):
    d = build_data(tmp_path, commands)
    if comp_rows is not None:
        w(d / "comp_off_credits.csv", ["emp_id", "worked_date", "credited_on", "days"], comp_rows)
    runner, engine = build(str(d))
    runner.run_file(str(d / "commands.txt"))
    out = tmp_path / "out"
    write_all(runner, engine, str(out))
    return runner, engine, list(csv.DictReader(open(out / "leave_balances.csv")))


def rows(balances, as_of, emp, leave_type=None):
    return {r["leave_type"]: r["balance"] for r in balances
            if r["as_of_date"] == as_of and r["emp_id"] == emp and (leave_type is None or r["leave_type"] == leave_type)}


# ---- 3. YEAR_END: as_of_date = 31 December, after carry-forward/lapse, before the 1 January credit
def test_year_end_snapshot_is_dated_31_december_even_if_command_is_dated_1_january(tmp_path):
    cmds = ("RUN_PAYROLL|2026-12|2026-12-31\n"
            "YEAR_END|2027-01-01\n"
            "RUN_PAYROLL|2027-01|2027-01-31\n")
    runner, engine, bal = run(tmp_path, cmds)
    dec31 = rows(bal, "2026-12-31", "EMP-020")
    assert dec31["CL"] == "0.0"            # CL lapsed, January's credit NOT yet in
    assert dec31["EL"] == "14.5"           # 10 + Q4 credit 4.5
    assert dec31["SL"] == "9.0"            # 8 + December credit 1
    jan31 = rows(bal, "2027-01-31", "EMP-020")
    assert jan31["CL"] == "1.0"            # January credited after the year closed


def test_only_one_set_of_rows_for_31_december(tmp_path):
    cmds = "RUN_PAYROLL|2026-12|2026-12-31\nYEAR_END|2026-12-31\n"
    runner, engine, bal = run(tmp_path, cmds)
    dec31 = [r for r in bal if r["as_of_date"] == "2026-12-31" and r["emp_id"] == "EMP-020" and r["leave_type"] == "EL"]
    assert len(dec31) == 1 and dec31[0]["balance"] == "14.5"      # post carry-forward, not the month-end figure


# ---- 3. comp-off rows: unexpired balance only
def test_comp_off_rows_show_unexpired_balance_only(tmp_path):
    comp = [("EMP-020", "2026-11-15", "2026-11-20", "1.0"),        # expires 2027-01-19
            ("EMP-001", "2026-08-20", "2026-09-01", "1.0")]        # expired 2026-10-31
    cmds = ("RUN_PAYROLL|2026-12|2026-12-31\nYEAR_END|2026-12-31\nRUN_PAYROLL|2027-01|2027-01-31\n")
    runner, engine, bal = run(tmp_path, cmds, comp)
    assert rows(bal, "2026-12-31", "EMP-020", "COMP_OFF") == {"COMP_OFF": "1.0"}
    assert rows(bal, "2026-12-31", "EMP-001", "COMP_OFF") == {}            # already expired: no row
    assert rows(bal, "2027-01-31", "EMP-020", "COMP_OFF") == {}            # expired on 19 Jan: no row
    assert rows(bal, "2026-12-31", "EMP-005", "COMP_OFF") == {}            # never had any


# ---- 2. lop_days = LOP leave only (incl. excess converted to LOP and sandwich days)
def test_lop_days_counts_converted_lop_and_excludes_unauthorised(tmp_path):
    # EMP-020 has opening CL 2.0 + December credit 1.0 = 3.0, so a 5-day request converts 2 days to LOP.
    cmds = ("LEAVE_APPLY|R1|EMP-020|CL|2026-12-14|2026-12-18|2026-12-02|x|false\n"      # 5 working days
            "LEAVE_APPROVE|R1|EMP-005|2026-12-03\n"
            "RUN_PAYROLL|2026-12|2026-12-31\n")
    d = build_data(tmp_path, cmds)
    # make the 14-18 Dec absences visible in attendance
    rows_ = list(csv.reader(open(d / "attendance_2026_12.csv")))
    for r in rows_[1:]:
        if r[0] == "EMP-020" and r[1] in {"2026-12-14", "2026-12-15", "2026-12-16", "2026-12-17", "2026-12-18"}:
            r[2] = "A"
    w(d / "attendance_2026_12.csv", rows_[0], rows_[1:])
    runner, engine = build(str(d))
    runner.run_file(str(d / "commands.txt"))
    slip = next(p for p in engine.payslips if p.emp_id == "EMP-020" and p.month == "2026-12")
    req = runner.leave.requests["R1"]
    assert req.paid_qty == D("3") and req.lop_qty == D("2")         # balance 2.0 + December credit 1.0
    # Dec 7 and 8 are unauthorised absences in the test data: they cut payable days (31 - 2 LOP - 2 = 27)
    # but are NOT in lop_days, which holds only the 2 days converted to LOP
    assert slip.lop_days == D("2") and slip.payable_days == D("27")


# ---- 4. rejected / cancelled rows keep the requested days, balances unaffected
def test_rejected_and_cancelled_rows_keep_requested_days_and_balances_unaffected(tmp_path):
    cmds = ("LEAVE_APPLY|R1|EMP-020|SL|2026-12-07|2026-12-10|2026-12-02|x|false\n"     # 4 days, no flag: rejected
            "LEAVE_APPLY|R2|EMP-020|CL|2026-12-14|2026-12-15|2026-12-03|x|false\n"
            "LEAVE_CANCEL|R2|2026-12-04\n"
            "RUN_PAYROLL|2026-12|2026-12-31\n")
    runner, engine, bal = run(tmp_path, cmds)
    ledger = {r["req_id"]: r for r in csv.DictReader(open(tmp_path / "out" / "leave_ledger.csv"))}
    assert ledger["R1"]["status"] == "REJECTED" and ledger["R1"]["days_counted"] == "4.0"
    assert ledger["R2"]["status"] == "CANCELLED" and ledger["R2"]["days_counted"] == "2.0"
    assert ledger["R2"]["lop_days"] == "0.0" and ledger["R2"]["approved_on"] == ""
    dec = rows(bal, "2026-12-31", "EMP-020")
    assert dec["CL"] == "3.0" and dec["SL"] == "9.0"       # 2+1 and 8+1: nothing was taken


# ---- 6. exit month: payslip is regular earnings only; recoveries live on the F&F statement
def test_exit_month_payslip_has_no_fnf_items(tmp_path):
    cmds = ("EXIT|EMP-005|2027-01-05|2027-01-20|60|45000.00\n"
            "RUN_PAYROLL|2026-12|2026-12-31\nRUN_PAYROLL|2027-01|2027-01-31\n")
    runner, engine, bal = run(tmp_path, cmds)
    slip = next(p for p in engine.payslips if p.emp_id == "EMP-005" and p.month == "2027-01")
    assert slip.other_deductions == D("0.00")
    st = engine.fnf["EMP-005"]
    assert st.asset_recovery == D("45000.00") and st.notice_recovery > 0
    # gross/30 uses the FULL monthly gross at the exit-date CTC (1,200,000 / 12 = 100,000), not the earned amount
    assert st.notice_recovery == D("150000.00")             # 45 days x 100,000 / 30
    assert slip.gross < D("100000.00")                       # earned amount is lower (20 of 31 days)
