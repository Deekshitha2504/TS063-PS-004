# Decision log (T063-PS-004)

Every place where the brief or README left room for interpretation, what we chose, why, and where to
change it. **Status:** `Brief` = follows the brief/README directly, `Assumed` = our choice,
`ASK` = please confirm with the trainers on the email thread (the hidden set is compared field by field).

## A. Leave accrual and year-end
| ID | Decision | Why | Where | Status |
|---|---|---|---|---|
| D-01 | SL: 12 is the max accrued per year; 30 is the carry-forward limit (balance can exceed 12 through carry-forward). | "max 12, carries up to 30" cannot both be a balance cap. | `config.py`, `accrual.py` | ASK |
| D-02 | EL for a quarter is credited on the 1st of the following month (Apr, Jul, Oct) and Q4 by `YEAR_END`; 1.5 per eligible month. | "credited quarterly in arrears"; README says Q4 is credited by YEAR_END. | `accrual.credit_el_quarter` | Brief |
| D-12 | Accrual follows the command clock: before each command we credit every month-start reached. A month of the next leave year is not credited until `YEAR_END` has run. | README: opening balances are "before December accrual"; avoids January credit being wiped by the CL lapse. | `accrual.advance_to` | ASK (see D-12a) |
| D-12a | README line 91 says 3 CL days vs "balance 1.0" gives 2 LOP days; we convert 1 because February's CL was already credited on 1 Feb. If accrual should happen inside `RUN_PAYROLL` instead, this changes. | Only one of the two readings can be right. | `accrual.py`, `commands._tick` | ASK |
| D-13 | CL cap (12) applies to the balance; SL cap (12) applies to the amount accrued per year. | See D-01. | `accrual._capped_add` | Assumed |
| D-15 | The "joined on/before the 15th" rule also applies to EL months. | BR-04 is stated generally. | `accrual.accrual_eligible` | Assumed |
| D-16 | `YEAR_END` closes the currently open leave year (not derived from its date). | Robust to the date used on the command. | `accrual.year_end` | Assumed |

## B. Leave requests and approvals
| ID | Decision | Why | Where | Status |
|---|---|---|---|---|
| D-03 | Sandwich rule: only off-days strictly between two counted leave days count, and only for EL and LOP. Off-days at the start/end of the range never count. Only within one request. | BR-10. | `leave_rules.counted_days` | Assumed |
| D-09 | A comp-off credit is usable up to and including `credited_on + 60 days`. | README example: credited 5 Oct, used 11 Dec is expired. | `models.CompOffCredit.expires_on` | Assumed |
| D-17 | Balance is reserved when a request is applied and returned on reject/cancel. Each day is charged in its own month after that month's accrual; days in a not-yet-accrued month are deferred. | Gives the README year-end result: 3 days from the old year, 4 from the new. | `leave_requests._allocate` | Assumed |
| D-18 | Overlapping active requests of the same employee are rejected (`OVERLAP`). | Prevents double charging; not in the brief. Switch: `REJECT_OVERLAPPING_REQUESTS`. | `config.py` | ASK |
| D-19 | If an employee has no manager on file, the manager step is replaced by HR. | CEO has no manager; avoids a request nobody can approve. | `leave_rules.required_roles` | Assumed |
| D-20 | Rejected/cancelled ledger rows keep `days_counted` (days asked for) with `lop_days` 0.0 and no `approved_on`. | Ledger must show every request. | `outputs.write_leave_ledger` | ASK |
| D-21 | Auto-approval date = applied_on + 5 working days (Mon-Fri, no holidays). Ordinary commands sweep deadlines strictly before their date; RUN_PAYROLL / YEAR_END sweep up to and including their date. | "after 5 working days". | `leave_requests.sweep_auto_approvals` | ASK |
| D-25 | Balances move in half-days; a day with only half a day of balance is half paid / half LOP. | EL accrues 1.5. | `leave_requests._charge_balance` | Assumed |
| D-26 | Maternity counts every calendar day, has no balance, is female-only and paid. | Statutory leave includes weekly-offs. | `leave_rules.counted_days` | Assumed |
| D-27 | A request covering only weekly-offs/holidays is rejected (`NO_LEAVE_DAYS`). | Nothing to count. | `leave_requests._validate` | Assumed |
| D-28 | Comp-off whose credits have all expired is rejected (BR-09); a shortfall of valid comp-off converts to LOP. | README example. | `leave_requests._validate` | Assumed |
| D-29 | A PENDING request does not cover an absence: the day is unauthorised until approved/auto-approved. LOP is never auto-approved. | README. | `leave_requests.leave_cover` | Brief |

## C. Attendance and output formats
| ID | Decision | Why | Where | Status |
|---|---|---|---|---|
| D-10 | Payslip `lop_days` = LOP leave + unauthorised absences (half-day remainders excluded). | Brief: payable = calendar - LOP - unauthorised. Switches in `config.py`. | `payroll.run_month` | ASK |
| D-14 | A date with no attendance row means "not on the rolls" (before joining / after exit) and is not payable. | README row counts prove it (1504 = 48x31 + 16). | `attendance.summarise_month` | Brief |
| D-22 | `leave_balances.csv` has CL, SL, EL rows only, one snapshot per payroll run (month end) and one per `YEAR_END`. | README names no COMP_OFF rows. | `commands._snapshot` | ASK |
| D-22a | After `YEAR_END` the snapshot date is the command's date, which can equal the December month-end date. | Date not specified. | `commands._year_end` | ASK |
| D-23 | `command_log` status words: OK / REJECTED / ERROR / NOT_HANDLED; `rule_ids` joined with `;`; `line_no` is the physical line in the file. | README gives columns, not values. | `commands.py` | ASK |
| D-24 | Rule ids on a leave row: BR-10 sandwich used, BR-11 LOP conversion, BR-12 chain completed, BR-13 auto-approved, or the rule that rejected it. | Traceability. | `leave_requests.py` | Assumed |
| D-36 | The payslip of an exit month shows regular salary only. Encashment and recoveries appear only in `fnf_statements.csv`; `other_deductions` is 0.00. | Payslip has no column for encashment. | `payroll.run_month` | ASK |
| D-41 | `bank_advice.csv` and `annual_tax_summary.csv` are extra files (the brief names them; the README does not specify them). | Brief requirements. | `payroll_outputs.py` | Assumed |

## D. Payroll
| ID | Decision | Why | Where | Status |
|---|---|---|---|---|
| D-30 | Basic + HRA + special allowance = monthly CTC (employer PF is on top); `employer_cost` = gross + employer PF. | "Special allowance balances CTC". README: EMP-048 gross exactly Rs 25,000, which fits CTC 3,00,000. **Please check EMP-048's `ctc_annual` in employees.csv.** | `payroll.components` | ASK |
| D-31 | PF base is the earned (pro-rated) basic. `pf_opt_out_excess = true` caps it at the PF wage ceiling; `false` uses full basic. Employer PF equals employee PF. | README column note. | `payroll.provident_fund` | Brief |
| D-32 | Every component is rounded half-up to 2 places; gross is the sum of the rounded components. | Payslips are checked to the paisa. | `payroll.earnings` | Assumed |
| D-33 | TDS projection = FY gross to date + this month's gross + remaining months x full-month standard gross at the CTC in force at month end. Taxable = projected - standard deduction (- 80C, old regime, capped). Rebate and 4% cess applied. No surcharge, marginal relief, HRA exemption or PT deduction. | Brief formula; README gives only these inputs. | `payroll.tds_for_month` | ASK |
| D-34 | In the exit month nothing is projected: all outstanding tax (including tax on EL encashment) is recovered in that month. | Nobody is left to deduct later. | `payroll.tds_for_month` | Assumed |
| D-35 | F&F: salary_to_lwd = that month's gross; notice served = LWD - resignation date; shortfall x (full-month gross / 30); EL encashment = max(balance,0) x monthly basic / 30 at the LWD CTC; EL balance is zeroed; statutory = PF + PT + TDS of the final payslip; net may be negative; release = LWD + 45. | README example (60 days notice, 15 served = 45 short). | `payroll._full_and_final` | ASK (basis for "gross") |
| D-37 | `REGIME_CHANGE` is always rejected (BR-27), including a change to the same regime. | README: must be rejected mid-year. | `payroll._h_regime` | Brief |
| D-38 | A `REVISE_CTC` that arrives after its month's run is stored, but arrears are not computed (stretch goal). | Out of scope. | `payroll._h_revise` | Assumed |
| D-39 | `FNF_RELEASE` is accepted on any date; a warning is printed if it is earlier than the release date. | README is silent on rejection. | `payroll._h_release` | ASK |
| D-40 | PT slab uses the month's earned gross, bounds inclusive; a gap falls to the slab with the highest `gross_from` not above the gross; February uses `february_pt`. | README column notes. | `payroll.professional_tax` | Brief |
| D-42 | `tax_params.csv` keys are found by key-name words (see `params.py`); anything not found uses the FY 2026-27 default and is printed at the start of every run. | We were not told the key names. | `params.py` | Assumed |



