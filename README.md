# T063-PS-004: Payroll, Attendance and Leave Engine

Team T063 (section CSD), 10 SECONDS capstone, problem statement PS-004. Python 3.10+.
A command-file driven engine for a 200-employee company: leave accrual and balances, leave requests
with an approval workflow, monthly attendance, gross-to-net payroll with PF / professional tax / TDS,
payslips, bank advice, joiners, exits with full-and-final, salary revisions and year-end.
There is no UI: input files in, CSV files out.

## Run it
    python -m venv .venv
    .venv\Scripts\activate            (Windows)   |   source .venv/bin/activate   (Mac/Linux)
    pip install -r requirements.txt
    # put the sample CSVs and commands.txt in data/
    python scripts/run_all.py --data data --out output
    python -m pytest -q               # 119 tests

`run_all.py` prints how every `tax_params.csv` key was matched, then processes
`commands.txt` top to bottom and writes the output files.

## Output files (output/)
| File | Content |
|---|---|
| payslips.csv | one row per employee per RUN_PAYROLL |
| leave_ledger.csv | every leave request in file order with its outcome |
| leave_balances.csv | CL/SL/EL balances after each month end and YEAR_END |
| fnf_statements.csv | one row per exited employee |
| command_log.csv | one row per command (status, rule ids, message) |
| bank_advice.csv | net pay per employee per month |
| annual_tax_summary.csv | Form-16-style summary of the financial year so far |

## Layout
    src/leave_attendance/
      config.py            every rule number in one place
      models.py            Employee, CompOffCredit, DataIssue
      calendar_utils.py    weekly-offs, holidays, working days
      loaders.py           CSV readers (cleans duplicates / unknown ids)
      attendance.py        daily attendance -> payable days (MonthlyAttendanceSummary)
      balances.py          CL/SL/EL wallet, comp-off ledger
      accrual.py           monthly accrual, joiner rule, EL quarters, YEAR_END
      leave_rules.py       day counting (sandwich), approval roles, CL/EL clubbing
      leave_requests.py    apply / approve / reject / cancel / auto-approve
      commands.py          reads commands.txt and runs it
      params.py            tax_params / it_slabs / pt_slabs
      payroll.py           earnings, PF, PT, TDS, payslips, full-and-final
      payroll_outputs.py   payroll CSV writers
      outputs.py           leave CSV writers
      pipeline.py          wires both halves together
    scripts/               run_all.py, run_leave.py, smoke_check.py, build_design_doc.py
    tests/                 pytest suite
    docs/                  design-document.pdf, decision-log.md, demo-script.md

## Documents
- Design document: `docs/design-document.pdf`
- Decision log: `docs/decision-log.md`

## Business rules
BR-01 ... BR-34 are listed in the design document with the module and tests that cover each one.
