# PS-004 – Payroll, Attendance and Leave Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T063.

## Files

| File | What it holds | Row count |
|---|---|---|
| `employees.csv` | Employee master (50) incl. 2 joiners inside the period | 50 |
| `holidays.csv` | Company holiday calendar for the period | 5 |
| `leave_balances_opening.csv` | Leave balances as at 2026-12-01 (before December accrual) for employees already on rolls | 144 |
| `comp_off_credits.csv` | Comp-off credits earned before the period (expire 60 days after credited_on) | 2 |
| `attendance_2026_12.csv` | Daily attendance import for December 2026 (one row per employee per calendar day) | 1504 |
| `attendance_2027_01.csv` | Daily attendance import for January 2027 (one row per employee per calendar day) | 1529 |
| `attendance_2027_02.csv` | Daily attendance import for February 2027 (one row per employee per calendar day) | 1355 |
| `pt_slabs.csv` | Professional-tax table by state and monthly gross | 14 |
| `it_slabs.csv` | Income-tax slabs FY 2026-27 by regime | 10 |
| `tax_params.csv` | Scalar parameters for TDS, PF and F&F | 15 |
| `commands.txt` | Command file processed top to bottom (count excludes `#` comment lines) | 107 |

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with at most 2 places (no commas, no symbol); percentages as plain numbers (12.5 = 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### `employees.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `emp_id` | string | EMP-nnn | — | — |
| `name` | string | — | — | — |
| `gender` | string | — | M / F | Maternity leave is for F only |
| `grade` | string | — | G1–G5 | Drives the approval chain |
| `department` | string | — | — | HR department holds the HR approvers |
| `joining_date` | date | YYYY-MM-DD | — | Two employees join inside Dec 2026 – Feb 2027 |
| `location` | string | — | — | — |
| `state` | string | — | Karnataka / Maharashtra / Tamil Nadu / Telangana | Professional-tax state |
| `metro` | boolean | — | true / false | HRA 50% of basic if true else 40% |
| `ctc_annual` | decimal | Rs per year | — | Current CTC at 2026-12-01 (before any REVISE_CTC) |
| `tax_regime` | string | — | OLD / NEW | Fixed for the FY; a mid-year change must be rejected |
| `pf_opt_out_excess` | boolean | — | true / false | true = PF only on the statutory Rs 15,000 cap; false = 12% on full basic |
| `declared_80c` | decimal | Rs | — | Chapter VI-A 80C declaration (OLD regime only; 0.00 for NEW) |
| `gross_paid_fy_to_date` | decimal | Rs | — | Gross salary paid Apr–Nov 2026 (0.00 for new joiners) |
| `tds_deducted_fy_to_date` | decimal | Rs | — | TDS already deducted Apr–Nov 2026 |
| `manager_id` | string | EMP-nnn | — | Approving manager; blank only for the CEO. May be blank (deliberately). |
| `bank_account` | string | 12 digits | — | — |
| `ifsc` | string | AAAA0nnnnnn | — | — |
| `pan` | string | AAAAA9999A | — | — |

### `holidays.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `date` | date | YYYY-MM-DD | — | — |
| `name` | string | — | — | — |

### `leave_balances_opening.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `emp_id` | string | EMP-nnn | — | FK employees.csv |
| `leave_type` | string | — | CL / SL / EL | Comp-offs are in comp_off_credits.csv; LOP and MATERNITY have no balance |
| `balance` | decimal | days | — | One decimal; EL Q4 credit (Oct–Dec) is credited in arrears on 2027-01-01 and is NOT yet included |

### `comp_off_credits.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `emp_id` | string | EMP-nnn | — | — |
| `worked_date` | date | — | — | — |
| `credited_on` | date | — | — | Expiry = credited_on + 60 days |
| `days` | decimal | days | — | — |

### `attendance_2026_12.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `emp_id` | string | EMP-nnn | — | FK employees.csv (one deliberately unknown id in February) |
| `date` | date | YYYY-MM-DD | — | — |
| `status` | string | — | P / A / HD / H / WO / WFH | A = not present: paid if covered by an approved leave, else unauthorised absence; HD = half day (0.5 payable) |

### `attendance_2027_01.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `emp_id` | string | EMP-nnn | — | FK employees.csv (one deliberately unknown id in February) |
| `date` | date | YYYY-MM-DD | — | — |
| `status` | string | — | P / A / HD / H / WO / WFH | A = not present: paid if covered by an approved leave, else unauthorised absence; HD = half day (0.5 payable) |

### `attendance_2027_02.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `emp_id` | string | EMP-nnn | — | FK employees.csv (one deliberately unknown id in February) |
| `date` | date | YYYY-MM-DD | — | — |
| `status` | string | — | P / A / HD / H / WO / WFH | A = not present: paid if covered by an approved leave, else unauthorised absence; HD = half day (0.5 payable) |

### `pt_slabs.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `state` | string | — | — | — |
| `gross_from` | decimal | Rs | — | Inclusive |
| `gross_to` | decimal | Rs | — | Inclusive |
| `monthly_pt` | decimal | Rs | — | Mar–Jan |
| `february_pt` | decimal | Rs | — | Amount in February |

### `it_slabs.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `regime` | string | — | OLD / NEW | — |
| `income_from` | decimal | Rs | — | Exclusive lower bound |
| `income_to` | decimal | Rs | — | Inclusive upper bound |
| `rate_pct` | decimal | percent | — | — |

### `tax_params.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `key` | string | — | — | — |
| `value` | string | — | — | Numbers are plain decimals; lists are ;-separated |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order (the file is the event log). Lines starting with `#` are comments and blank lines are ignored.

Leave requests, approvals, revisions, exits and payroll runs are all commands. Dates inside LEAVE_APPLY are inclusive. Attendance files are read when RUN_PAYROLL for that month executes. Working days for the 5-day auto-approval clock are Mon–Fri excluding holidays.csv. Payroll month = calendar month.

| Command | Arguments (in order) | Notes |
|---|---|---|
| `LEAVE_APPLY` | req_id, emp_id, leave_type, from_date, to_date, applied_on, reason, medical_flag | leave_type ∈ CL / SL / EL / LOP / COMP_OFF / MATERNITY; medical_flag true/false |
| `LEAVE_APPROVE` | req_id, approver_id, on_date | One line per approver in the chain; a chain is complete only when every required approver has approved |
| `LEAVE_REJECT` | req_id, approver_id, on_date, remark | — |
| `LEAVE_CANCEL` | req_id, on_date | Employee withdraws before the leave starts; balance restored |
| `REVISE_CTC` | emp_id, effective_date, new_ctc_annual | Pro-rate the month by days at each CTC |
| `EXIT` | emp_id, resignation_date, last_working_day, notice_required_days, asset_recovery_amount | Full-and-final computed in the LWD month's run; released 45 days after LWD by FNF_RELEASE |
| `FNF_RELEASE` | emp_id, on_date | Print the F&F statement |
| `REGIME_CHANGE` | emp_id, new_regime, on_date | Must be rejected mid-year |
| `RUN_PAYROLL` | YYYY-MM, run_date | Monthly run: accrue leave (1st), payslips, bank advice |
| `YEAR_END` | on_date | Leave-year close: CL lapses, SL carry up to 30, EL carry up to 45; credit Q4 EL (4.5) in arrears |

## Planted scenarios

Every edge case from the brief, and where it sits in this pack:

- **Leave spanning month boundary** — `commands.txt` line 66: EL 2027-01-28 to 2027-02-03 — 4 days in January's run, 3 in February's; sandwich weekend 30–31 Jan counts
- **Leave spanning year end with carry-forward** — `commands.txt` line 25: EL 2026-12-29 to 2027-01-04 for EMP-023 whose EL opening balance is 40.0 — YEAR_END (line 50) must carry forward (cap 45 after the Q4 credit) with 3 days already consumed in Dec and 4 pending in Jan
- **Joiner on the 16th** — `employees.csv` EMP-049 joins 2026-12-16 — no CL/SL accrual for December, 16 payable days of 31; compare EMP-050 joining 2027-01-12 (accrues)
- **Exit during notice with negative balance** — `commands.txt` line 61: EMP-014 resigns 2027-01-05 with LWD 2027-01-20 against 60 days notice (45 days shortfall at gross/30), Rs 45,000 asset recovery, EL balance 1.0 and 5 unauthorised absences 12–16 Jan in `attendance_2027_01.csv` — F&F net is negative
- **Revision on the 1st vs mid-month** — `commands.txt` line 48: revision effective 2027-01-01 (whole month at new CTC); line 64: effective 2027-01-16 (15 days old + 16 days new); also line 20: 2026-12-10
- **February PT** — RUN_PAYROLL 2027-02 at line 109: professional tax uses the `february_pt` column (Rs 300 in Karnataka); EMP-048 has monthly gross exactly Rs 25,000 (Karnataka nil band boundary)
- **Regime switch mid-year (must reject)** — `commands.txt` line 62: REGIME_CHANGE for EMP-042 on 2027-01-08 — must be rejected (regime fixed for the FY)
- **Maternity leave overlapping payroll run** — `commands.txt` line 40: MATERNITY 2027-01-20 to 2027-07-20 for EMP-029 — paid leave overlapping the January and February runs (attendance shows A on those days)

Extra traps (not in the brief, but realistic):

- line 5: SL of 4 consecutive days without medical flag → reject; line 77: same with medical flag → allowed
- line 17: CL on 17 Dec immediately after EL 14–16 Dec (line 3) → clubbing not allowed, reject
- line 32: EL applied 4 days before start (needs 7) → reject
- line 46: EL Fri 8 Jan – Mon 11 Jan = 4 EL days (sandwich); line 58: CL Fri–Mon = 2 days (no sandwich for CL)
- line 91: 3 CL days against balance 1.0 → 2 days auto-convert to LOP with a flag
- line 85: EL never approved — auto-approves 5 working days after application; line 97: LOP never approved — must NOT auto-approve (days become unauthorised absence)
- line 81: G3 employee's EL approved by manager only (HR approval missing) — chain incomplete until the 5-working-day auto-approval
- line 67 + line 74: approved CL cancelled before start (balance restored); line 26 + line 28: rejected SL (day stays unauthorised)
- line 22: comp-off used within 60 days of credit; line 7: comp-off credited 2026-10-05 used 2026-12-11 (expired 2026-12-04) → reject
- `employees.csv` EMP-047: CTC 450000 → basic exactly Rs 15,000/month (PF statutory cap boundary)
- `attendance_2027_01.csv`: duplicate row for EMP-001 on 2027-01-07 (count once); EMP-010 marked P on holiday 2027-01-26 (worked on a holiday — do not double-pay); `attendance_2027_02.csv` has a row for unknown EMP-099 (reject the row, continue)
- line 70: clean exit with full notice served (LWD 2027-02-10) and EL encashment; F&F printed at line 112

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

`status` for leave ∈ APPROVED / AUTO_APPROVED / REJECTED / CANCELLED / PENDING; money to 2 decimals; days with one decimal.

Produce these CSV files (header row, same formatting conventions as the inputs, one row per entity in the order stated). Column names must match exactly.

### `payslips.csv`

One row per employee per RUN_PAYROLL (month order, then emp_id).

Columns, in order: `month`, `emp_id`, `calendar_days`, `payable_days`, `lop_days`, `basic`, `hra`, `special_allowance`, `gross`, `pf_employee`, `professional_tax`, `tds`, `other_deductions`, `total_deductions`, `net_pay`, `pf_employer`, `employer_cost`

### `leave_ledger.csv`

Every leave request in file order with its outcome.

Columns, in order: `req_id`, `emp_id`, `leave_type`, `from_date`, `to_date`, `days_counted`, `status`, `lop_days`, `approved_on`, `rule_ids`

### `leave_balances.csv`

Balance per employee per leave type after each month end and after YEAR_END.

Columns, in order: `as_of_date`, `emp_id`, `leave_type`, `balance`

### `fnf_statements.csv`
hi
One row per exited employee.

Columns, in order: `emp_id`, `last_working_day`, `salary_to_lwd`, `el_encashment`, `notice_shortfall_days`, `notice_recovery`, `asset_recovery`, `statutory_deductions`, `net_payable`, `release_date`

### `command_log.csv`

One row per command in file order.

Columns, in order: `line_no`, `command`, `status`, `rule_ids`, `message`
