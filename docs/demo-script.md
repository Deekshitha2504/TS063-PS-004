# 5-minute demo video script (T063-PS-004)

**Total 5:00. Record the VS Code window with the terminal visible. Both team members speak.**

| Time | Who | Show | Say |
|---|---|---|---|
| 0:00-0:25 | Both | README on GitHub | Team T063, PS-004. A command-file driven payroll, attendance and leave engine in Python. No UI: files in, CSV files out. |
| 0:25-1:00 | Leave person | Folder tree in VS Code | Two halves. Leave/attendance: accrual, requests, approvals, payable days. Payroll: earnings, PF, PT, TDS, payslip, full-and-final. They meet at `MonthlyAttendanceSummary`. |
| 1:00-1:40 | Both | Terminal: `python scripts/run_all.py --data data --out output` | One command runs `commands.txt` top to bottom. Show the summary: commands processed, payslips, F&F statements, data issues caught (duplicate row, unknown employee). |
| 1:40-2:30 | Leave person | `output/leave_ledger.csv` | Walk three rows: sandwich (EL Fri-Mon = 4 days), CL not sandwiched (2 days), SL 4 days without medical flag rejected (BR-06). Show the excess-to-LOP row. |
| 2:30-3:00 | Leave person | `output/leave_balances.csv` + the 29 Dec-4 Jan EL | Leave spanning year end: 3 days from 2026, 4 from 2027, carry-forward cap applied in between. |
| 3:00-4:00 | Payroll person | `output/payslips.csv`, one employee | One payslip from CTC to net: CTC/12, basic 40%, HRA 50%/40%, special allowance, pro-rating by payable days, PF 12% with the 15,000 cap, PT (Feb Rs 300), TDS formula. |
| 4:00-4:30 | Payroll person | `fnf_statements.csv` | Exit with short notice: shortfall days, recovery at gross/30, EL encashment at basic/30, assets, net can be negative; release date = LWD + 45. Show REGIME_CHANGE rejected in `command_log.csv`. |
| 4:30-5:00 | Both | `python -m pytest -q` | 119 tests pass. Decision log lists every assumption. Thank you. |

Tips: rehearse once; keep the font large; do not read code line by line; if a number is asked in the viva, be able to trace it to a rule id.
