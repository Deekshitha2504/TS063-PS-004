# Study plan: be able to explain and edit this code live (T063-PS-004)

The viva fails you if you cannot modify your own code live, and it includes walking through one payslip
from CTC to net. This plan takes about 25 to 30 hours. Spread it over the days you have, one block per sitting.
Tick each box (`- [x]`) when you can do the thing without looking at the answer.

**Rules of the plan**
1. Always run the code before you read it, and run the tests after every change you make.
2. Read each file with the question "what goes in, what comes out?" Do not try to memorise lines.
3. Say explanations out loud, to your teammate or to the wall. If you cannot say it, you do not know it yet.
4. Use `git` as an undo button: `git restore <file>` throws away an edit you regret.
5. Your teammate does this same plan. In Block 7 you swap and quiz each other.

---

## Block 0: Setup (30 min)
- [ ] Open the project folder in VS Code (the folder that contains `src`, `scripts`, `tests`).
- [ ] Create the virtual environment and install requirements (`python -m venv .venv`, activate, `pip install -r requirements.txt`).
- [ ] Run `python -m pytest -q` and see all tests pass.
- [ ] Copy the sample files into `data/` and run `python scripts/run_all.py --data data --out output`.
- [ ] Open `output/payslips.csv` and `output/leave_ledger.csv` in VS Code and find your own favourite employee's rows.
- [ ] Learn three VS Code skills: search in all files (`Ctrl+Shift+F`), go to definition (`F12`), and run one test by name in the terminal (`python -m pytest -q -k sandwich`).

## Block 1: The Python this project uses (3 h)
Do each item: find it in the code, read it, then write a 5-line experiment in a scratch file.
- [ ] **Dataclasses**: `models.py` (`Employee`, `CompOffCredit`). Make one by hand and print it.
- [ ] **Dates**: `datetime.date`, `timedelta`, `isoformat()`, `fromisoformat()`, `.weekday()` in `calendar_utils.py`. Work out by hand what weekday 2027-01-08 is, then check in Python.
- [ ] **Decimal for money**: `payroll.money()`. Show why `0.1 + 0.2` is wrong as a float and right as `Decimal`.
- [ ] **Dicts and lists**: `Dict[str, Employee]`, `sorted(..., key=...)`, list comprehensions (`payroll.py`, `commands.py`).
- [ ] **CSV**: `csv.DictReader` in `loaders.py`. Why `encoding="utf-8-sig"`? (the Excel BOM)
- [ ] **Classes and `self`**: `AccrualEngine` in `accrual.py`. What is stored in `self`, and which methods change it?
- [ ] **Exceptions**: `raise`, `try/except`, and the custom `CommandRejected` (`leave_requests.py`, `commands.run_file`).
- [ ] **Functions as values**: the `handlers` dictionary in `commands.py` and `payroll.handlers()`, and the `on_month_accrued` callback in `accrual.py`.
- [ ] **pytest basics**: `assert`, `pytest.raises`, `tmp_path` (`tests/test_loaders_and_compoff.py`).
- [ ] You can explain in one sentence each: dataclass, Decimal, dict, exception, callback.

## Block 2: The big picture (1.5 h)
- [ ] Read `README.md` and `docs/design-document.pdf` sections 1 to 3.
- [ ] From memory, draw the data flow: `commands.txt` -> `CommandRunner` -> leave engine / payroll engine -> CSV files.
- [ ] Open `commands.py`, read `run_file` and `_dispatch`. Explain how one line becomes a function call.
- [ ] **Trace one command**: pick `LEAVE_APPLY` for EMP-023 (29 Dec to 4 Jan). Follow it through `_leave_apply` -> `LeaveEngine.apply` -> `_validate` -> `_allocate` -> `_charge_balance`. Write the path on paper.
- [ ] **Trace one payroll run**: `RUN_PAYROLL` -> `_run_payroll` -> `summarise_month` -> `PayrollEngine.run_month` -> `Payslip`.
- [ ] Explain the "handshake" object `MonthlyAttendanceSummary` and why it has `payable_by_date`.
- [ ] Explain why time follows the command file (`advance_to`) in two sentences.

## Block 3: Leave and attendance code, file by file (5 h)
For each file: read it top to bottom, run its test file, then answer the check questions.
- [ ] `config.py`: name every constant and the BR it supports.
- [ ] `calendar_utils.py` (`tests/test_calendar.py`): how does `add_working_days` skip weekends and holidays?
- [ ] `loaders.py` (`tests/test_loaders_and_compoff.py`): list the three data problems it cleans and the `DataIssue` kind for each.
- [ ] `attendance.py` (`tests/test_attendance.py`): for each status P, WFH, HD, H, WO, A, say how many payable days it gives. What changes when leave covers an `A` day? What is the identity check?
- [ ] `balances.py`: how does the comp-off ledger choose which credit to use first?
- [ ] `accrual.py` (`tests/test_accrual.py`): explain `accrual_eligible` for a joiner on the 15th and on the 16th. Explain why EL is credited quarterly in arrears and what `year_end` does to CL, SL and EL.
- [ ] `leave_rules.py` (`tests/test_leave_rules.py`): explain `counted_days` for EL Fri to Mon and for CL Fri to Mon. Explain `required_roles` for G1 to G5.
- [ ] `leave_requests.py` (`tests/test_leave_requests.py`): walk through `_validate` in order. Explain reserve-at-apply, deferred days, `approve`, `reject`, `cancel`, `sweep_auto_approvals`.
- [ ] Explain the year-end scenario (EL 29 Dec to 4 Jan with a balance of 40: 37, then 41.5, then 37.5) using only the code and one sheet of paper.
- [ ] `outputs.py`: why are `rule_ids` joined with `;`?

## Block 4: Payroll code (4 h)
- [ ] `params.py`: how are `tax_params.csv` keys found? Where do defaults live? How does `slab_tax` handle an exclusive lower bound?
- [ ] `payroll.py` `components`: compute basic, HRA and special allowance for CTC 6,00,000 by hand, then check with the code.
- [ ] `earnings`: explain why each day is paid at the CTC in force that day (mid-month revision).
- [ ] `provident_fund`: explain the two cases (`pf_opt_out_excess` true and false).
- [ ] `professional_tax`: explain inclusive bounds and the February column.
- [ ] `annual_tax` and `tds_for_month`: explain projected gross, standard deduction, 80C (old regime only), rebate, cess, remaining months.
- [ ] `run_month` and `_full_and_final`: explain every field of the F&F statement.
- [ ] Command handlers: `_h_regime`, `_h_revise`, `_h_exit`, `_h_release`.
- [ ] Rebuild the worked payslip in `docs/design-document.pdf` section 6 on paper without looking, then compare.
- [ ] `tests/test_payroll.py`: for any five tests, say what rule they protect.

## Block 5: Rules, code and tests (2 h)
- [ ] Open the rule register (`docs/design-document.pdf` section 4, or the Excel sheet). For all 35 rules, say the function that implements it in under 10 seconds.
- [ ] Cover the "Implemented in" column and quiz yourself, then do the same for the "Tests" column.
- [ ] Read `docs/decision-log.md` completely. Pick any five decisions and explain what you chose and why.
- [ ] Know the seven open questions (section E of the decision log) by heart.

## Block 6: Live-edit drills (4 h)
Each drill: make the change, run the tests, **predict which tests fail before you run them**, then fix the tests (or revert with `git restore`).
- [ ] 1. CL cap 12 -> 10 (`config.CL_MAX`). Surprise: no existing test fails. Work out why, then write the test that proves the new cap (opening CL 9, accrue twice, expect 10).
- [ ] 2. Joiner cutoff 15 -> 10 (`config.JOINER_CUTOFF_DAY`). Expect `test_accrual` failures.
- [ ] 3. EL notice 7 -> 10 days (`config.EL_NOTICE_DAYS`).
- [ ] 4. SL medical threshold 3 -> 2 (`config.SL_MEDICAL_THRESHOLD_DAYS`).
- [ ] 5. Auto-approval 5 -> 3 working days (`config.AUTO_APPROVE_WORKING_DAYS`).
- [ ] 6. Comp-off validity 60 -> 30 days (`config.COMP_OFF_VALIDITY_DAYS`).
- [ ] 7. Apply the sandwich rule to CL as well (`config.SANDWICH_LEAVE_TYPES`).
- [ ] 8. Saturday becomes a working day (`config.WEEKLY_OFF_WEEKDAYS = (6,)`).
- [ ] 9. Stop rejecting overlapping requests (`config.REJECT_OVERLAPPING_REQUESTS`).
- [ ] 10. Make payslip `lop_days` include unauthorised absences (`config.PAYSLIP_LOP_INCLUDES_UNAUTHORISED = True`; the trainers confirmed False).
- [ ] 11. PF rate 12% -> 10% (`PayrollParams.pf_rate_pct` in `params.py`; for a real run the matching key in `tax_params.csv` wins).
- [ ] 12. PF wage ceiling 15,000 -> 21,000 (`pf_wage_cap`).
- [ ] 13. Basic 40% -> 50% of CTC (`basic_pct`).
- [ ] 14. EL encashment divisor 30 -> 26 (`encash_divisor`).
- [ ] 15. F&F release 45 -> 30 days (`fnf_release_days`).
- [ ] 16. Change February PT for Karnataka (edit `pt_slabs.csv`, not code) and re-run.
- [ ] 17. Half-day pays 0.5 -> 0.75 (the `HD` branch in `attendance.summarise_month`).
- [ ] 18. Add a column `net_pay_rounded` to `payslips.csv` (`payroll_outputs.PAYSLIP_COLUMNS` and `write_payslips`).
- [ ] 19. Round money down instead of half-up (`payroll.money`). Predict how many tests break, then count.
- [ ] 20. Project TDS using this month's gross instead of the standard monthly gross (`payroll.tds_for_month`).
- [ ] 21. Add a new command `PRINT_BALANCE|EMP-001` that logs that employee's balances (`commands._dispatch`).
- [ ] 22. Add a new rule: CL cannot be applied for more than 3 days at once (`leave_requests._validate`, new rule id, new test).
- [ ] Time yourself: each of drills 1 to 10 should take under 3 minutes, drills 11 to 20 under 6 minutes.

## Block 7: Viva rehearsal (3 h)
- [ ] **Payslip walk-through**: pick any employee from `output/payslips.csv`. Explain every number from CTC to net, naming the BR for each step.
- [ ] **Leave walk-through**: pick any request from `leave_ledger.csv`. Explain its status, `days_counted`, `lop_days` and `rule_ids`.
- [ ] **F&F walk-through**: explain one row of `fnf_statements.csv`.
- [ ] Answer these out loud, then check the code:
  - [ ] Why `Decimal` and not float?
  - [ ] Why are balances reserved at application time?
  - [ ] What stops January's CL from being wiped at year-end?
  - [ ] How does the sandwich rule differ for EL, CL and LOP?
  - [ ] How is a mid-month salary revision pro-rated?
  - [ ] Why is `REGIME_CHANGE` always rejected?
  - [ ] How does TDS change after a revision or an exit?
  - [ ] What happens to a duplicate or unknown-employee attendance row?
  - [ ] What would you change to add a new leave type?
  - [ ] Which decisions are still unconfirmed with the trainers?
  - [ ] What did you not implement (arrears, per-location policies), and how would you start?
- [ ] **Mock viva**: your teammate picks two drills at random. Do them live while they watch.
- [ ] Run the demo once from `docs/demo-script.md` and time it (5 minutes).

## Block 8: Debugging toolkit (1 h)
- [ ] Put a breakpoint in `LeaveEngine._validate` and step through a request with the VS Code debugger (Run and Debug, `launch.json` for `scripts/run_all.py`).
- [ ] Use `print(...)` inside `payroll.run_month` to show the intermediate numbers for one employee, then remove it.
- [ ] Run one test only: `python -m pytest -q tests/test_payroll.py::test_pf_boundary_basic_exactly_15000`.
- [ ] Read a traceback from the bottom up (last line is the error, the line above it is where).
- [ ] Undo a bad edit with `git restore <file>`; see what you changed with `git diff`.

---

## Where to find things in 10 seconds
| Question | File and function |
|---|---|
| Rule numbers (caps, days, cutoffs) | `config.py` |
| Percentages, PF ceiling, slabs | `params.py`, `tax_params.csv`, `it_slabs.csv`, `pt_slabs.csv` |
| Leave accrual, year-end | `accrual.py` (`accrue_month`, `credit_el_quarter`, `year_end`) |
| Is this request valid? | `leave_requests.py` (`_validate`) |
| Which days does a request use? | `leave_rules.py` (`counted_days`) |
| Who must approve? | `leave_rules.py` (`required_roles`) |
| Payable days | `attendance.py` (`summarise_month`) |
| Earnings, PF, PT | `payroll.py` (`earnings`, `provident_fund`, `professional_tax`) |
| TDS | `payroll.py` (`tds_for_month`, `annual_tax`) |
| Full and final | `payroll.py` (`_full_and_final`) |
| What a command does | `commands.py` (`_dispatch`) |
| Output file columns | `outputs.py`, `payroll_outputs.py` |

## Sources
- Python tutorial: https://docs.python.org/3/tutorial/
- Python `dataclasses`: https://docs.python.org/3/library/dataclasses.html
- Python `decimal`: https://docs.python.org/3/library/decimal.html
- Python `datetime`: https://docs.python.org/3/library/datetime.html
- Python `csv`: https://docs.python.org/3/library/csv.html
- pytest getting started: https://docs.pytest.org/en/stable/getting-started.html
- VS Code Python debugging: https://code.visualstudio.com/docs/python/debugging
- Git basics: https://git-scm.com/book/en/v2
