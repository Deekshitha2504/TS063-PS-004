# Decision log (T063-PS-004)

Every place where the brief or README left room for interpretation: what we chose, why, which business
rule (BR) it belongs to, and where to change it. 
**Status:** `Brief` = follows the brief/README directly, `Assumed` = our choice, `CONFIRMED` = confirmed by the
10 SECONDS reply to our clarification email (section E), `ASK` = still to be confirmed (section F).

## A. Leave accrual and year-end
| ID | BR | Decision | Why | Where | Status |
|---|---|---|---|---|---|
| D-01 | BR-02 | SL: 12 is the max accrued per year; 30 is the carry-forward limit (balance can exceed 12 through carry-forward). | "max 12, carries up to 30" cannot both be a balance cap. | `config.py`, `accrual.py` | ASK |
| D-02 | BR-03 | EL for a quarter is credited on the 1st of the following month (Apr, Jul, Oct) and Q4 by `YEAR_END`; 1.5 per eligible month. | "credited quarterly in arrears"; README says Q4 is credited by YEAR_END. | `accrual.credit_el_quarter` | Brief |
| D-12 | BR-01, BR-02 | CL and SL are credited on the 1st of the month, before any leave request dated in that month is processed. Accrual is not part of `RUN_PAYROLL`. A month of the next leave year is not credited until `YEAR_END` has run. | Trainer reply #1. | `accrual.advance_to`, `commands._tick` | CONFIRMED |
| D-12a | BR-01, BR-02, BR-11 | README line 91 says 3 CL days vs "balance 1.0" gives 2 LOP days; our engine converts 1 for EMP-027 because February's CL had already been credited. EMP-027 is not a joiner, so the joiner rule does not explain it. We follow the rule as stated by the trainers. | Trainer reply #1: if the balance still differs after the joiner check, follow the stated rule and record it. | `accrual.py` | CONFIRMED |
| D-13 | BR-01, BR-02 | CL cap (12) applies to the balance; SL cap (12) applies to the amount accrued per year. | See D-01. | `accrual._capped_add` | Assumed |
| D-15 | BR-03, BR-04 | The "joined on/before the 15th" rule also applies to EL months. | BR-04 is stated generally. | `accrual.accrual_eligible` | Assumed |
| D-16 | BR-05 | `YEAR_END` closes the currently open leave year (not derived from its date). | Robust to the date used on the command. | `accrual.year_end` | Assumed |

## B. Leave requests and approvals
| ID | BR | Decision | Why | Where | Status |
|---|---|---|---|---|---|
| D-03 | BR-10 | Sandwich rule: only off-days strictly between two counted leave days count, and only for EL and LOP. Off-days at the start/end of the range never count. Only within one request. | BR-10. | `leave_rules.counted_days` | Assumed |
| D-09 | BR-09 | A comp-off credit is usable up to and including `credited_on + 60 days`. | README example: credited 5 Oct, used 11 Dec is expired. | `models.CompOffCredit.expires_on` | Assumed |
| D-17 | BR-05, BR-11 | Balance is reserved when a request is applied and returned on reject/cancel. Each day is charged in its own month after that month's accrual; days in a not-yet-accrued month are deferred. | Gives the README year-end result: 3 days from the old year, 4 from the new. | `leave_requests._allocate` | Assumed |
| D-18 | BR-35 (new) | A request that overlaps (date range) a PENDING or APPROVED/AUTO_APPROVED request of the same employee is rejected. Rejected or cancelled requests do not block a new one. Rule id `BR-35`. | Trainer reply #5. | `leave_requests._validate`, `config.REJECT_OVERLAPPING_REQUESTS` | CONFIRMED |
| D-19 | BR-12 | If an employee has no manager on file, the manager step is replaced by HR. | CEO has no manager; avoids a request nobody can approve. | `leave_rules.required_roles` | Assumed |
| D-20 | BR-06 to BR-13 | Rejected and cancelled ledger rows show the requested `days_counted`; `status` shows the outcome; `lop_days` is 0.0, no `approved_on`, and balances are unaffected. | Trainer reply #4. | `outputs.write_leave_ledger` | CONFIRMED |
| D-21 | BR-13 | Auto-approval date = applied_on + 5 working days (Mon-Fri, no holidays). Ordinary commands sweep deadlines strictly before their date; RUN_PAYROLL / YEAR_END sweep up to and including their date. | "after 5 working days". | `leave_requests.sweep_auto_approvals` | ASK |
| D-25 | BR-11 | Balances move in half-days; a day with only half a day of balance is half paid / half LOP. | EL accrues 1.5. | `leave_requests._charge_balance` | Assumed |
| D-26 | BR-10 | Maternity counts every calendar day, has no balance, is female-only and paid. | Statutory leave includes weekly-offs. | `leave_rules.counted_days` | Assumed |
| D-27 | BR-10 | A request covering only weekly-offs/holidays is rejected (`NO_LEAVE_DAYS`). | Nothing to count. | `leave_requests._validate` | Assumed |
| D-28 | BR-09, BR-11 | Comp-off whose credits have all expired is rejected (BR-09); a shortfall of valid comp-off converts to LOP. | README example. | `leave_requests._validate` | Assumed |
| D-29 | BR-13, BR-15 | A PENDING request does not cover an absence: the day is unauthorised until approved/auto-approved. LOP is never auto-approved. | README. | `leave_requests.leave_cover` | Brief |

## C. Attendance and output formats
| ID | BR | Decision | Why | Where | Status |
|---|---|---|---|---|---|
| D-10 | BR-10, BR-11, BR-15 | Payslip `lop_days` = LOP leave only, including excess leave auto-converted to LOP and sandwich days. Unauthorised absences reduce `payable_days` separately and are not in `lop_days`. | Trainer reply #2. | `config.PAYSLIP_LOP_INCLUDES_UNAUTHORISED` (False), `payroll.run_month` | CONFIRMED |
| D-14 | BR-15, BR-28 | A date with no attendance row means "not on the rolls" (before joining / after exit) and is not payable. | README row counts prove it (1504 = 48x31 + 16). | `attendance.summarise_month` | Brief |
| D-22 | BR-05, BR-09 | `leave_balances.csv` has CL, SL, EL rows for every employee on the rolls, plus COMP_OFF rows listing the unexpired balance only (an employee with no unexpired comp-off has no COMP_OFF row). One snapshot per payroll run (month end) and one per `YEAR_END`. | Trainer reply #3. | `commands._snapshot`, `config.COMP_OFF_SNAPSHOT_INCLUDE_ZERO` | CONFIRMED |
| D-22a | BR-05 | The `YEAR_END` snapshot is dated 31 December of the closed year, shows balances after carry-forward and lapse and before the 1 January credit, and replaces the December month-end snapshot (one set of rows per date). | Trainer reply #3. | `commands._year_end`, `accrual.year_end(catch_up=False)` | CONFIRMED |
| D-23 | all | `command_log` status words: OK / REJECTED / ERROR / NOT_HANDLED; `rule_ids` joined with `;`; `line_no` is the physical line in the file. | README gives columns, not values. | `commands.py` | ASK |
| D-24 | BR-10 to BR-13, BR-35 | Rule ids on a leave row: BR-10 sandwich used, BR-11 LOP conversion, BR-12 chain completed, BR-13 auto-approved, BR-35 overlap, or the rule that rejected it. | Traceability. | `leave_requests.py` | Assumed |
| D-36 | BR-30 to BR-34 | The payslip of an exit month carries regular earnings up to the last working day only. EL encashment, notice recovery and asset deductions appear only on the F&F statement; `other_deductions` is 0.00. | Trainer reply #6. | `payroll.run_month` | CONFIRMED |
| D-41 | BR-26, BR-20 | `bank_advice.csv` and `annual_tax_summary.csv` are extra files (the brief names them; the README does not specify them). | Brief requirements. | `payroll_outputs.py` | Assumed |

## D. Payroll
| ID | BR | Decision | Why | Where | Status |
|---|---|---|---|---|---|
| D-30 | BR-16, BR-17, BR-18 | Basic + HRA + special allowance = monthly CTC (employer PF is on top); `employer_cost` = gross + employer PF. | "Special allowance balances CTC". README: EMP-048 gross exactly Rs 25,000, which fits CTC 3,00,000. Check EMP-048's `ctc_annual`. | `payroll.components` | ASK |
| D-31 | BR-20, BR-21, BR-22 | PF base is the earned (pro-rated) basic. `pf_opt_out_excess = true` caps it at the PF wage ceiling; `false` uses full basic. Employer PF equals employee PF. | README column note. | `payroll.provident_fund` | Brief |
| D-32 | BR-19 | Every component is rounded half-up to 2 places; gross is the sum of the rounded components. | Payslips are checked to the paisa. | `payroll.earnings` | Assumed |
| D-33 | BR-26 | TDS projection = FY gross to date + this month's gross + remaining months x full-month standard gross at the CTC in force at month end. Taxable = projected - standard deduction (- 80C, old regime, capped). Rebate and 4% cess applied. No surcharge, marginal relief, HRA exemption or PT deduction. | Brief formula; README gives only these inputs. | `payroll.tds_for_month` | ASK |
| D-34 | BR-26, BR-30 | In the exit month nothing is projected: all outstanding tax (including tax on EL encashment) is recovered in that month. | Nobody is left to deduct later. | `payroll.tds_for_month` | ASK |
| D-35 | BR-30 to BR-34 | F&F: `salary_to_lwd` = that month's earned gross; notice served = LWD - resignation date; shortfall x (**full monthly gross at the exit-date CTC** / 30); EL encashment = max(balance,0) x (**full monthly basic at the exit-date CTC** / 30); EL balance is zeroed; statutory = PF + PT + TDS of the final payslip; net may be negative; release = LWD + 45. | Trainer reply #6 (gross/30 and basic/30 use the full monthly figures at the exit-date CTC). | `payroll._full_and_final`, `payroll.run_month` | CONFIRMED |
| D-37 | BR-27 | `REGIME_CHANGE` is always rejected, including a change to the same regime. | README: must be rejected mid-year. | `payroll._h_regime` | Brief |
| D-38 | BR-29 | A `REVISE_CTC` that arrives after its month's run is stored, but arrears are not computed (stretch goal). | Out of scope. | `payroll._h_revise` | Assumed |
| D-39 | BR-34 | `FNF_RELEASE` is accepted on any date; a warning is printed if it is earlier than the release date. | README is silent on rejection. | `payroll._h_release` | ASK |
| D-40 | BR-23, BR-24, BR-25 | PT slab uses the month's earned gross, bounds inclusive; a gap falls to the slab with the highest `gross_from` not above the gross; February uses `february_pt`. | README column notes. | `payroll.professional_tax` | Brief |
| D-42 | BR-16 to BR-26 | `tax_params.csv` keys are found by key-name words (see `params.py`); anything not found uses the FY 2026-27 default and is printed at the start of every run. | We were not told the key names. | `params.py` | Assumed |

## E. Trainer clarifications (reply from 10 SECONDS support, same email thread)
| # | Question | Trainers' answer (summary) | BR | What we changed | Where |
|---|---|---|---|---|---|
| 1 | Accrual timing | CL and SL are credited on the 1st, before any leave request dated in that month is processed. Accrual is not part of RUN_PAYROLL. For README line 91, check the joiner rule first; if the balance still differs, follow the rule as stated and record it. | BR-01, BR-02, BR-04 | Nothing: behaviour already matched. EMP-027 is not a joiner, so the difference at line 91 is recorded as D-12a. | `accrual.advance_to` |
| 2 | `lop_days` | LOP leave only, including excess auto-converted to LOP and sandwich days. Unauthorised absences reduce payable days separately and are not in `lop_days`. | BR-10, BR-11, BR-15 | `PAYSLIP_LOP_INCLUDES_UNAUTHORISED` set to False. | `config.py` |
| 3 | `YEAR_END` snapshot | `as_of_date` is 31 December, balances after carry-forward and lapse, before the 1 January credit. List comp-off rows with the unexpired balance only. | BR-05, BR-09 | Snapshot dated 31 December of the closed year, taken before the new year's credit and replacing the month-end set. COMP_OFF rows added (unexpired balance only). | `commands._year_end`, `commands._snapshot`, `accrual.year_end` |
| 4 | Rejected/cancelled ledger rows | Show the requested `days_counted`; status shows the outcome; balances unaffected. | BR-06 to BR-13 | Nothing: behaviour already matched. | `outputs.write_leave_ledger` |
| 5 | Overlapping requests | Reject any request that overlaps a pending or approved request of the same employee. Rejected or cancelled requests do not block. | BR-35 (new) | Overlap now compares the date range (not only counted days) and reports rule id `BR-35`. | `leave_requests._validate` |
| 6 | Exit month | Payslip has regular earnings to the last working day only. Encashment, notice recovery and asset deductions only on the F&F statement. "Gross/30" and "basic/30" use the full monthly figures at the exit-date CTC. | BR-30 to BR-34 | Nothing: behaviour already matched; a test now locks it in. | `payroll.run_month`, `_full_and_final` |
| 7 | EMP-014 EL balance | EL is credited quarterly in arrears, so the balance before the Q4 credit is 4.5 lower than after. Our 5.5 is the post-credit figure and is consistent with the README's 1.0 (pre-credit). | BR-03 | Nothing. | n/a |

## F. Still open (ASK the trainers if time allows)
1. D-01: is SL "max 12" the yearly accrual (our reading) or a balance cap?
2. D-21: auto-approval date: applied_on + 5 working days, and does a manual approval dated exactly on the deadline count as manual?
3. D-23: the `command_log` status words (we use OK / REJECTED / ERROR / NOT_HANDLED).
4. D-30: is employer PF inside or outside CTC? (Check EMP-048's `ctc_annual`: 3,00,000 supports "outside".)
5. D-33 / D-34: the TDS projection method and exit-month TDS.
6. D-39: should `FNF_RELEASE` before the release date be rejected?
7. README line 91: check the `applied_on` date on that line. If it is in January, tell the trainers, because our days-in-a-later-month are charged after that month's credit (D-17).
