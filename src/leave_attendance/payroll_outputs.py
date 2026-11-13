"""CSV writers for payslips.csv, fnf_statements.csv (README columns, in order),
plus bank_advice.csv and annual_tax_summary.csv (from the brief)."""
from __future__ import annotations

import csv
import os
from decimal import Decimal
from typing import Iterable, List, Sequence

from .outputs import fmt_days
from .payroll import FnfStatement, Payslip, money

PAYSLIP_COLUMNS = ["month", "emp_id", "calendar_days", "payable_days", "lop_days", "basic", "hra",
                   "special_allowance", "gross", "pf_employee", "professional_tax", "tds",
                   "other_deductions", "total_deductions", "net_pay", "pf_employer", "employer_cost"]
FNF_COLUMNS = ["emp_id", "last_working_day", "salary_to_lwd", "el_encashment", "notice_shortfall_days",
               "notice_recovery", "asset_recovery", "statutory_deductions", "net_payable", "release_date"]
BANK_COLUMNS = ["month", "emp_id", "name", "bank_account", "ifsc", "net_pay"]
ANNUAL_COLUMNS = ["emp_id", "tax_regime", "gross_before_period", "gross_in_period", "total_gross",
                  "standard_deduction", "deduction_80c", "taxable_income", "tax_on_income_to_date",
                  "tds_before_period", "tds_in_period", "total_tds"]


def m(x) -> str:
    return f"{money(Decimal(x)):.2f}"


def _write(path: str, header: Sequence[str], rows: Iterable[Sequence]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_payslips(path: str, payslips: List[Payslip]) -> None:
    ordered = sorted(payslips, key=lambda p: (p.month, p.emp_id))
    _write(path, PAYSLIP_COLUMNS, [[
        p.month, p.emp_id, p.calendar_days, fmt_days(p.payable_days), fmt_days(p.lop_days),
        m(p.basic), m(p.hra), m(p.special_allowance), m(p.gross), m(p.pf_employee),
        m(p.professional_tax), m(p.tds), m(p.other_deductions), m(p.total_deductions),
        m(p.net_pay), m(p.pf_employer), m(p.employer_cost)] for p in ordered])


def write_fnf(path: str, statements: List[FnfStatement]) -> None:
    _write(path, FNF_COLUMNS, [[
        s.emp_id, s.last_working_day.isoformat(), m(s.salary_to_lwd), m(s.el_encashment),
        s.notice_shortfall_days, m(s.notice_recovery), m(s.asset_recovery),
        m(s.statutory_deductions), m(s.net_payable), s.release_date.isoformat()]
        for s in sorted(statements, key=lambda s: s.emp_id)])


def write_bank_advice(path: str, payslips: List[Payslip], employees) -> None:
    rows = []
    for p in sorted(payslips, key=lambda p: (p.month, p.emp_id)):
        e = employees[p.emp_id]
        rows.append([p.month, p.emp_id, e.name, e.bank_account, e.ifsc, m(p.net_pay)])
    _write(path, BANK_COLUMNS, rows)


def write_annual_summary(path: str, rows: List[dict]) -> None:
    _write(path, ANNUAL_COLUMNS,
           [[r["emp_id"], r["tax_regime"]] + [m(r[c]) for c in ANNUAL_COLUMNS[2:]] for r in rows])
