"""Whole engine, tiny data: leave -> attendance -> payroll -> output files."""
import csv
from datetime import date, timedelta
from decimal import Decimal as D

from leave_attendance.pipeline import build, write_all

EMP_HEADER = ["emp_id", "name", "gender", "grade", "department", "joining_date", "location", "state",
              "metro", "ctc_annual", "tax_regime", "pf_opt_out_excess", "declared_80c",
              "gross_paid_fy_to_date", "tds_deducted_fy_to_date", "manager_id", "bank_account", "ifsc", "pan"]
EMPS = [
    ["EMP-001", "Hema", "F", "G5", "HR", "2020-01-01", "Bengaluru", "Karnataka", "true", "1200000", "NEW", "false", "0", "800000", "0", "", "111111111111", "HDFC0000001", "AAAAA1111A"],
    ["EMP-005", "Mani", "M", "G4", "Eng", "2020-01-01", "Bengaluru", "Karnataka", "true", "1200000", "NEW", "true", "0", "800000", "0", "EMP-001", "222222222222", "HDFC0000001", "AAAAA2222A"],
    ["EMP-020", "Gita", "F", "G2", "Eng", "2020-01-01", "Mysuru", "Karnataka", "false", "600000", "OLD", "false", "150000", "400000", "0", "EMP-005", "333333333333", "HDFC0000001", "AAAAA3333A"],
    ["EMP-049", "Joiner", "M", "G1", "Eng", "2026-12-16", "Bengaluru", "Karnataka", "true", "372000", "NEW", "false", "0", "0", "0", "EMP-005", "444444444444", "HDFC0000001", "AAAAA4444A"],
]


def w(path, header, rows):
    with open(path, "w", newline="") as f:
        c = csv.writer(f)
        c.writerow(header)
        c.writerows(rows)


def build_data(tmp_path, commands):
    d = tmp_path / "data"
    d.mkdir()
    w(d / "employees.csv", EMP_HEADER, EMPS)
    w(d / "holidays.csv", ["date", "name"], [("2026-12-25", "Christmas")])
    bal = [(e[0], t, v) for e in EMPS if e[0] != "EMP-049" for t, v in (("CL", "2.0"), ("SL", "8.0"), ("EL", "10.0"))]
    w(d / "leave_balances_opening.csv", ["emp_id", "leave_type", "balance"], bal)
    w(d / "comp_off_credits.csv", ["emp_id", "worked_date", "credited_on", "days"], [])
    w(d / "pt_slabs.csv", ["state", "gross_from", "gross_to", "monthly_pt", "february_pt"],
      [("Karnataka", "0", "25000", "0", "0"), ("Karnataka", "25000.01", "", "200", "300")])
    w(d / "it_slabs.csv", ["regime", "income_from", "income_to", "rate_pct"],
      [("NEW", "0", "400000", "0"), ("NEW", "400000", "800000", "5"), ("NEW", "800000", "1200000", "10"),
       ("NEW", "1200000", "1600000", "15"), ("NEW", "1600000", "", "20"),
       ("OLD", "0", "250000", "0"), ("OLD", "250000", "500000", "5"), ("OLD", "500000", "1000000", "20"),
       ("OLD", "1000000", "", "30")])
    w(d / "tax_params.csv", ["key", "value"], [("pf_rate_pct", "12"), ("pf_wage_cap", "15000"), ("fnf_release_days", "45")])
    for (y, m, n) in ((2026, 12, 31), (2027, 1, 31)):
        rows = []
        for e in EMPS:
            for day in range(1, n + 1):
                dt = date(y, m, day)
                if e[0] == "EMP-049" and dt < date(2026, 12, 16):
                    continue
                if e[0] == "EMP-005" and dt > date(2027, 1, 20):
                    continue
                status = "WO" if dt.weekday() >= 5 else "P"
                if dt == date(2026, 12, 25):
                    status = "H"
                if e[0] == "EMP-020" and dt in (date(2026, 12, 7), date(2026, 12, 8)):
                    status = "A"
                rows.append((e[0], dt.isoformat(), status))
        w(d / f"attendance_{y}_{m:02d}.csv", ["emp_id", "date", "status"], rows)
    (d / "commands.txt").write_text(commands)
    return d


COMMANDS = """# whole-engine test
LEAVE_APPLY|R1|EMP-020|SL|2026-12-07|2026-12-07|2026-12-02|fever|false
LEAVE_APPROVE|R1|EMP-005|2026-12-03
REVISE_CTC|EMP-020|2026-12-10|720000
RUN_PAYROLL|2026-12|2026-12-31
YEAR_END|2026-12-31
EXIT|EMP-005|2027-01-05|2027-01-20|60|45000.00
REGIME_CHANGE|EMP-020|NEW|2027-01-08
REVISE_CTC|EMP-020|2027-01-16|840000
RUN_PAYROLL|2027-01|2027-01-31
FNF_RELEASE|EMP-005|2027-03-10
"""


def run(tmp_path):
    d = build_data(tmp_path, COMMANDS)
    runner, engine = build(str(d))
    runner.run_file(str(d / "commands.txt"))
    out = tmp_path / "out"
    write_all(runner, engine, str(out))
    return runner, engine, out


def read(path):
    return list(csv.DictReader(open(path)))


def test_every_command_is_handled(tmp_path):
    runner, engine, out = run(tmp_path)
    status = {e[0]: e[2] for e in runner.log}
    assert "NOT_HANDLED" not in status.values()
    assert status[10] == "OK" and status[5] == "OK"            # revise, run payroll
    log = {r["line_no"]: r for r in read(out / "command_log.csv")}
    assert log["8"]["status"] == "REJECTED" and "BR-27" in log["8"]["rule_ids"]     # regime change


def test_payslips_file_shape_and_values(tmp_path):
    runner, engine, out = run(tmp_path)
    rows = read(out / "payslips.csv")
    assert list(rows[0].keys()) == ["month", "emp_id", "calendar_days", "payable_days", "lop_days", "basic",
                                    "hra", "special_allowance", "gross", "pf_employee", "professional_tax",
                                    "tds", "other_deductions", "total_deductions", "net_pay", "pf_employer",
                                    "employer_cost"]
    assert [(r["month"], r["emp_id"]) for r in rows] == sorted((r["month"], r["emp_id"]) for r in rows)
    dec = {r["emp_id"]: r for r in rows if r["month"] == "2026-12"}
    assert dec["EMP-049"]["calendar_days"] == "31" and dec["EMP-049"]["payable_days"] == "16.0"
    assert dec["EMP-049"]["gross"] == "16000.00"                  # 372000/12 x 16/31
    assert dec["EMP-001"]["gross"] == "100000.00" and dec["EMP-001"]["professional_tax"] == "200.00"
    assert dec["EMP-001"]["pf_employee"] == "4800.00"             # 12% of basic 40000, not opted out
    assert dec["EMP-005"]["pf_employee"] == "1800.00"             # opted out of the excess
    # EMP-020: approved SL on 7 Dec covers the absence; the 8th is unauthorised, which lowers
    # payable days but is NOT counted in lop_days (trainers: lop_days = LOP leave only)
    assert dec["EMP-020"]["payable_days"] == "30.0" and dec["EMP-020"]["lop_days"] == "0.0"
    for r in rows:
        assert D(r["net_pay"]) == D(r["gross"]) - D(r["total_deductions"])


def test_revision_split_in_january(tmp_path):
    runner, engine, out = run(tmp_path)
    jan = {r["emp_id"]: r for r in read(out / "payslips.csv") if r["month"] == "2027-01"}
    # 60000/month for 15 days then 70000/month for 16 days, over 31 days
    expected = D("60000") * 15 / 31 + D("70000") * 16 / 31
    assert abs(D(jan["EMP-020"]["gross"]) - expected) < D("0.05")


def test_exit_produces_fnf_with_shortfall(tmp_path):
    runner, engine, out = run(tmp_path)
    fnf = read(out / "fnf_statements.csv")
    assert [r["emp_id"] for r in fnf] == ["EMP-005"]
    r = fnf[0]
    assert r["notice_shortfall_days"] == "45" and r["asset_recovery"] == "45000.00"
    assert r["release_date"] == "2027-03-06"                      # 20 Jan + 45 days
    assert D(r["net_payable"]) < 0
    assert "F&F EMP-005" in runner.log[-1][4]
    jan_emp5 = [p for p in read(out / "payslips.csv") if p["emp_id"] == "EMP-005" and p["month"] == "2027-01"]
    assert len(jan_emp5) == 1 and jan_emp5[0]["payable_days"] == "20.0"


def test_bank_advice_and_annual_summary_exist(tmp_path):
    runner, engine, out = run(tmp_path)
    bank = read(out / "bank_advice.csv")
    assert len(bank) == len(read(out / "payslips.csv"))
    assert bank[0]["ifsc"] == "HDFC0000001"
    annual = {r["emp_id"]: r for r in read(out / "annual_tax_summary.csv")}
    assert "EMP-049" in annual and annual["EMP-001"]["gross_before_period"] == "800000.00"


def test_leave_outputs_still_written(tmp_path):
    runner, engine, out = run(tmp_path)
    for name in ("leave_ledger.csv", "leave_balances.csv", "command_log.csv"):
        assert (out / name).exists()
