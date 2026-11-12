"""Builds docs/design-document.pdf (reportlab). Edit the text below and re-run:

    python scripts/build_design_doc.py
The worked payslip is computed by the real engine, so its numbers cannot drift from the code.
"""
import os
import sys
from datetime import date
from decimal import Decimal as D

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reportlab.lib import colors                                        # noqa: E402
from reportlab.lib.pagesizes import A4                                  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet    # noqa: E402
from reportlab.lib.units import mm                                      # noqa: E402
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table, TableStyle)

from leave_attendance.attendance import summarise_month                 # noqa: E402
from leave_attendance.models import Employee                            # noqa: E402
from leave_attendance.params import PayrollParams, TaxParams, slab_tax  # noqa: E402
from leave_attendance.payroll import PayrollEngine, money               # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "design-document.pdf")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceBefore=10, spaceAfter=6, keepWithNext=1)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("B", parent=ss["BodyText"], fontSize=9.5, leading=13)
CELL = ParagraphStyle("C", parent=BODY, fontSize=8, leading=10)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
MONO = ParagraphStyle("M", parent=BODY, fontName="Courier", fontSize=8.5, leading=11)


def P(t, s=BODY):
    return Paragraph(t, s)


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), CELLB if (header and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")))
    t.setStyle(TableStyle(style))
    return t


# ------------------------------------------------ worked payslip, from the real engine
NEW = [(D(0), D(400000), D(0)), (D(400000), D(800000), D(5)), (D(800000), D(1200000), D(10)),
       (D(1200000), D(1600000), D(15)), (D(1600000), D(2000000), D(20)),
       (D(2000000), D(2400000), D(25)), (D(2400000), None, D(30))]
emp = Employee("EMP-DEMO", "Demo", "F", "G4", "Eng", date(2020, 1, 1), None, state="Karnataka", metro=True,
               ctc_annual=D("2400000"), tax_regime="NEW", pf_opt_out_excess=False,
               gross_paid_fy_to_date=D("1600000"), tds_deducted_fy_to_date=D("195000"))
eng = PayrollEngine({emp.emp_id: emp}, PayrollParams.from_tax_params(TaxParams({})), {"NEW": NEW, "OLD": NEW},
                    {"karnataka": []})
rows = {date(2026, 12, d): "P" for d in range(1, 32)}
rows[date(2026, 12, 14)] = "A"                       # one unauthorised absence
summ = summarise_month(emp.emp_id, 2026, 12, rows, {})
basic, hra, special = eng.earnings(emp, summ)
gross = basic + hra + special
pf, _ = eng.provident_fund(emp, basic)
pt = D("200")
tds = eng.tds_for_month(emp, 2026, 12, gross, False)
proj = D("1600000") + gross + 3 * eng.monthly_gross_standard(emp.emp_id, date(2026, 12, 31))
taxable = proj - D("75000")
annual = eng.annual_tax(emp, proj)
net = gross - pf - pt - tds

# ------------------------------------------------ rule table: id, rule, module, tests
BR = [
 ("BR-01", "CL 1/month on the 1st, max 12, lapses at year-end", "accrual.accrue_month / year_end", "test_accrual"),
 ("BR-02", "SL 1/month, max 12 accrued, carry-forward up to 30", "accrual.accrue_month / year_end", "test_accrual"),
 ("BR-03", "EL 1.5/month credited quarterly in arrears, carry up to 45", "accrual.credit_el_quarter / year_end", "test_accrual"),
 ("BR-04", "Joiner accrues for the joining month only if joined on/before the 15th", "accrual.accrual_eligible", "test_accrual"),
 ("BR-05", "Year-end carry-forward / lapse", "accrual.year_end", "test_accrual, test_leave_requests"),
 ("BR-06", "SL over 3 consecutive days needs a medical flag", "leave_requests._validate", "test_leave_requests"),
 ("BR-07", "CL cannot be clubbed with EL", "leave_rules.is_clubbed", "test_leave_rules, test_leave_requests"),
 ("BR-08", "EL needs 7 days' notice", "leave_requests._validate", "test_leave_requests"),
 ("BR-09", "Comp-off expires in 60 days", "models.CompOffCredit, balances.CompOffLedger", "test_loaders_and_compoff"),
 ("BR-10", "Sandwich rule for EL and LOP, not CL/SL", "leave_rules.counted_days", "test_leave_rules"),
 ("BR-11", "Insufficient balance converts to LOP with a flag", "leave_requests._charge_balance", "test_leave_requests"),
 ("BR-12", "Approval chain by grade (G1-2 manager; G3-4 manager+HR; G5 HR)", "leave_rules.required_roles, leave_requests.approve", "test_leave_requests"),
 ("BR-13", "Auto-approve after 5 working days, except LOP", "leave_requests.sweep_auto_approvals", "test_leave_requests"),
 ("BR-14", "Attendance statuses P/A/HD/H/WO/WFH imported", "loaders.load_attendance", "test_loaders_and_compoff"),
 ("BR-15", "Payable days = calendar - LOP - unauthorised; HD 0.5; WFH present", "attendance.summarise_month", "test_attendance"),
 ("BR-16", "Basic = 40% of CTC", "payroll.components", "test_payroll"),
 ("BR-17", "HRA 50% of basic metro / 40% other", "payroll.components", "test_payroll"),
 ("BR-18", "Special allowance balances CTC", "payroll.components", "test_payroll"),
 ("BR-19", "Earnings pro-rated by payable / calendar days", "payroll.earnings", "test_payroll"),
 ("BR-20", "PF 12% of basic, employee and employer", "payroll.provident_fund", "test_payroll"),
 ("BR-21", "Statutory PF basic capped at Rs 15,000", "payroll.provident_fund", "test_payroll"),
 ("BR-22", "Opt-out of PF on the excess allowed", "payroll.provident_fund", "test_payroll"),
 ("BR-23", "Karnataka PT: nil up to 25,000, 200 above", "payroll.professional_tax", "test_payroll"),
 ("BR-24", "February PT Rs 300", "payroll.professional_tax", "test_payroll"),
 ("BR-25", "Other states' PT from the table", "payroll.professional_tax", "test_payroll"),
 ("BR-26", "TDS = (projected tax - TDS paid) / remaining months, monthly", "payroll.tds_for_month", "test_payroll"),
 ("BR-27", "Regime switch mid-year rejected", "payroll._h_regime", "test_payroll, test_pipeline"),
 ("BR-28", "Mid-month joiners and exits proportional", "attendance, payroll.earnings", "test_payroll, test_pipeline"),
 ("BR-29", "Revision effective any date (split by days)", "payroll.ctc_on / earnings", "test_payroll"),
 ("BR-30", "F&F: pay to last working day", "payroll._full_and_final", "test_payroll"),
 ("BR-31", "EL encashment at basic/30", "payroll.run_month", "test_payroll"),
 ("BR-32", "Notice shortfall recovery at gross/30", "payroll._full_and_final", "test_payroll"),
 ("BR-33", "Asset deductions", "payroll._full_and_final", "test_payroll"),
 ("BR-34", "F&F release 45 days after LWD", "payroll._full_and_final, _h_release", "test_payroll"),
]
EDGE = [
 ("Leave spanning a month boundary", "Days are counted once; the daily cover map splits them by month, so January's run sees 4 days and February's 3.", "test_leave_rules, test_leave_requests"),
 ("Leave spanning year end with carry-forward", "Days in a month not yet accrued are deferred. Old-year days are charged first, YEAR_END credits Q4 EL and applies the cap, then new-year days are charged.", "test_leave_requests (year-end tests)"),
 ("Joiner on the 16th", "accrual_eligible gives nothing for December; attendance rows start on the 16th, so payable = 16 of 31 calendar days.", "test_accrual, test_payroll, test_pipeline"),
 ("Exit during notice with negative balance", "Balance never goes below zero (excess becomes LOP). Notice shortfall and asset recovery can make the F&F net negative.", "test_payroll"),
 ("Revision on the 1st vs mid-month", "ctc_on() is evaluated per day, so a revision on the 1st changes the whole month and a mid-month revision splits it.", "test_payroll"),
 ("February PT", "Slab lookup returns february_pt in month 2 (Rs 300 in Karnataka).", "test_payroll"),
 ("Regime switch mid-year", "REGIME_CHANGE always raises CommandRejected (BR-27); the command log shows REJECTED.", "test_payroll, test_pipeline"),
 ("Maternity overlapping a payroll run", "Maternity is a paid leave covering every calendar day; absent days under it are payable, so the run pays in full.", "test_attendance, test_leave_requests"),
]

story = []
story += [P("T063-PS-004: Payroll, Attendance and Leave Engine", ss["Title"]),
          P("Design document. Team T063, section CSD. 10 SECONDS capstone, PS-004 (Python 3.10+)."), Spacer(1, 6)]

story += [P("1. Problem and approach", H1),
          P("The company needs a monthly payroll for 200 employees driven by text files: an employee master, "
            "daily attendance, a holiday calendar, statutory tables and a command file that records every "
            "event (leave applications, approvals, revisions, exits, payroll runs, year-end). There is no UI. "
            "The program reads the files, replays the command file strictly in order, and writes CSV outputs "
            "(payslips, leave ledger, balances, full-and-final statements, command log)."),
          P("We split the system into two halves that meet at one object. The leave and attendance half decides "
            "how many days each employee is paid for. The payroll half turns those days and the CTC into money. "
            "Every business rule is numbered BR-01 to BR-34 and each is implemented in one function and covered "
            "by named tests (section 4).")]

story += [P("2. Architecture", H1),
          table([["Module", "Responsibility"],
                 ["config.py", "Every rule number (12, 30, 45, 15th, 60 days, 5 working days) in one place."],
                 ["loaders.py, models.py", "Read the CSVs; clean duplicate rows, unknown employees, invalid statuses and log each as a data issue."],
                 ["calendar_utils.py", "Weekly-offs, holidays, working days, add N working days."],
                 ["accrual.py", "Monthly CL/SL credit, joiner rule, EL by quarter, year-end carry-forward and lapse."],
                 ["leave_rules.py, leave_requests.py", "Day counting (sandwich), validity rules, approval chain, auto-approval, balance charging."],
                 ["attendance.py", "Daily statuses plus leave cover become payable days (MonthlyAttendanceSummary)."],
                 ["payroll.py", "Earnings, PF, PT, TDS, payslip, full-and-final, revisions."],
                 ["commands.py, pipeline.py", "Parse and replay commands.txt; connect the two halves; write all outputs."]],
                [48, 122]),
          Spacer(1, 6),
          P("Data flow: commands.txt is read line by line. Leave commands update the leave engine. "
            "RUN_PAYROLL loads that month's attendance, asks the leave engine which days are covered by approved "
            "leave, builds a MonthlyAttendanceSummary per employee, and hands the summaries to the payroll engine. "
            "EXIT, REVISE_CTC, REGIME_CHANGE and FNF_RELEASE go to the payroll engine through a handler table."),
          P("The handshake object is MonthlyAttendanceSummary: calendar_days, payable_days, lop_days, "
            "unauthorised_days, half_day_unpaid, not_employed_days and payable_by_date (the payable amount of each "
            "calendar day, which lets payroll split a month at a salary revision).")]

story += [P("3. Key design decisions", H1),
          P("<b>Time follows the command file.</b> Before each command the accrual clock moves to that command's "
            "date and credits every month-start reached. A month of the next leave year is not credited until YEAR_END "
            "has run, otherwise January's CL would be credited and then wiped by the year-end lapse."),
          P("<b>Balances are reserved at application time.</b> A request takes its days from the balance when applied "
            "and gives them back on reject or cancel. If the balance is short, the excess days become LOP with a flag. "
            "Days that fall in a month not yet accrued are deferred and charged when that month is credited."),
          P("<b>Sandwich rule.</b> For EL and LOP, weekly-offs and holidays between the first and last working leave "
            "day count as leave. CL, SL and comp-off count working days only. Maternity counts every calendar day."),
          P("<b>Money is Decimal.</b> Floats would break component-by-component matching. Each earning component is "
            "rounded half-up to the paisa and gross is the sum of the rounded components."),
          P("<b>Rules in one place, assumptions in one log.</b> Every interpretation is recorded in docs/decision-log.md "
            "with a pointer to the code and a status (Brief, Assumed or ASK the trainers).")]

story += [PageBreak(), P("4. Business rule register", H1),
          table([["ID", "Rule", "Implemented in", "Tests"]] + [list(r) for r in BR], [14, 78, 48, 30])]

story += [P("5. Edge cases", H1),
          table([["Edge case", "How it is handled", "Tests"]] + [list(r) for r in EDGE], [42, 94, 34])]

story += [PageBreak(), P("6. Worked payslip: CTC to net", H1),
          P("Employee: G4, metro (Bengaluru), Karnataka, new regime, CTC Rs 24,00,000, PF on full basic. December 2026 "
            "(31 days), one unauthorised absence on 14 December. Rs 16,00,000 gross and Rs 1,95,000 TDS were already "
            "paid in April to November. The slabs are the FY 2026-27 new-regime slabs; in a real run they come from it_slabs.csv."),
          table([["Step", "Calculation", "Result (Rs)"],
                 ["Monthly CTC", "2,400,000 / 12", "200,000.00"],
                 ["Basic (40%)", "200,000 x 40%", "80,000.00"],
                 ["HRA (metro 50% of basic)", "80,000 x 50%", "40,000.00"],
                 ["Special allowance", "200,000 - 80,000 - 40,000", "80,000.00"],
                 ["Payable days", "31 calendar days - 1 unauthorised", f"{summ.payable_days}"],
                 ["Pro-rating", "each component x 30/31", f"basic {basic}, HRA {hra}, special {special}"],
                 ["Gross", "sum of the three", f"{gross}"],
                 ["PF employee (12% of basic)", f"12% x {basic}", f"{pf}"],
                 ["Professional tax", "Karnataka, gross above 25,000", f"{pt}"],
                 ["Projected annual gross", f"1,600,000 + {gross} + 3 x 200,000", f"{money(proj)}"],
                 ["Taxable income", "projected - 75,000 standard deduction", f"{money(taxable)}"],
                 ["Annual tax", "slabs + 4% cess (no rebate: above 12 lakh)", f"{annual}"],
                 ["TDS this month", f"({annual} - 195,000) / 4 remaining months", f"{tds}"],
                 ["Total deductions", "PF + PT + TDS", f"{pf + pt + tds}"],
                 ["<b>Net pay</b>", "gross - deductions", f"<b>{net}</b>"],
                 ["Employer cost", f"gross + employer PF {pf}", f"{gross + pf}"]],
                [52, 78, 40]),
          Spacer(1, 6),
          P(f"Slab check on taxable income {money(taxable)}: 4-8 lakh at 5% = 20,000; 8-12 lakh at 10% = 40,000; "
            f"12-16 lakh at 15% = 60,000; 16-20 lakh at 20% = 80,000; the remaining {money(taxable - D(2000000))} "
            f"above 20 lakh at 25% = {money((taxable - D(2000000)) * D('0.25'))}; total {money(slab_tax(taxable, NEW))}; "
            f"with 4% cess {annual}.")]

story += [P("7. Validation and data cleaning", H1),
          P("Attendance rows are checked against the employee master and the allowed statuses. A duplicate "
            "(employee, date) row is counted once; a row for an unknown employee is skipped; each is logged as a data "
            "issue and printed at the end of the run. A missing column in an input file stops the run with a clear "
            "message. Every leave request is validated in a fixed order and the first failure sets REJECTED with its rule id. "
            "Every command is logged with a status; one bad line never stops the run. "
            "MonthlyAttendanceSummary carries a built-in identity check: payable + LOP + unauthorised + half-day "
            "remainder + not-employed days always equals the calendar days.")]

story += [P("8. Testing", H1),
          P("119 pytest tests across eight files: calendar, accrual and year-end, attendance and payable days, "
            "loaders and comp-off, leave rules, the leave request lifecycle, payroll arithmetic, and whole-engine runs "
            "that start from CSV files and check the output files. The year-end test reproduces the README scenario "
            "(EL 29 Dec to 4 Jan with a balance of 40: 37, then 41.5 after the Q4 credit, then 37.5). The TDS "
            "calculation was cross-checked against published FY 2026-27 figures (Rs 15 lakh salary, about Rs 97,500 "
            "including cess).")]

story += [P("9. Assumptions, limits and future work", H1),
          P("The full list of interpretations is in docs/decision-log.md; the main open questions are accrual timing "
            "(inside or before RUN_PAYROLL), whether payslip lop_days includes unauthorised absences, and the "
            "basis of gross/30 in full-and-final. TDS ignores surcharge, marginal relief, HRA exemption and professional-tax "
            "deduction. Arrears for late salary revisions and per-location leave policies from JSON (the stretch goals) "
            "are not implemented; a late revision is stored and a warning is printed.")]

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                  bottomMargin=16 * mm, title="T063-PS-004 Design Document", author="Team T063").build(story)
print("wrote", os.path.abspath(OUT))
