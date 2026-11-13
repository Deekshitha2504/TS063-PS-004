"""Payroll engine: CTC -> earnings -> PF / PT / TDS -> payslip, plus full-and-final.

Rules covered: BR-16 basic, BR-17 HRA, BR-18 special allowance, BR-19 pro-rating,
BR-20/21/22 PF, BR-23/24/25 professional tax, BR-26 TDS, BR-27 regime lock,
BR-28 joiners/exits, BR-29 revisions, BR-30..34 full and final.

It plugs into CommandRunner through `handlers()` so the leave side does not
need to know anything about money.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from .attendance import MonthlyAttendanceSummary
from .calendar_utils import month_end
from .config import PAYSLIP_LOP_INCLUDES_HALF_DAY, PAYSLIP_LOP_INCLUDES_UNAUTHORISED
from .leave_requests import CommandRejected
from .models import Employee
from .params import PayrollParams, PTSlab, Slab, slab_tax

ZERO = Decimal("0")
HUNDRED = Decimal("100")
TWELVE = Decimal("12")


def money(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Payslip:
    month: str
    emp_id: str
    calendar_days: int
    payable_days: Decimal
    lop_days: Decimal
    basic: Decimal
    hra: Decimal
    special_allowance: Decimal
    gross: Decimal
    pf_employee: Decimal
    professional_tax: Decimal
    tds: Decimal
    other_deductions: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    pf_employer: Decimal
    employer_cost: Decimal


@dataclass
class FnfStatement:
    emp_id: str
    last_working_day: date
    salary_to_lwd: Decimal
    el_encashment: Decimal
    notice_shortfall_days: int
    notice_recovery: Decimal
    asset_recovery: Decimal
    statutory_deductions: Decimal
    net_payable: Decimal
    release_date: date


@dataclass
class ExitInfo:
    emp_id: str
    resignation_date: date
    last_working_day: date
    notice_required_days: int
    asset_recovery: Decimal


def fy_index(month: int) -> int:
    """April = 1 ... March = 12."""
    return (month - 4) % 12 + 1


class PayrollEngine:
    def __init__(self, employees: Dict[str, Employee], params: PayrollParams,
                 it_slabs: Dict[str, List[Slab]], pt_slabs: Dict[str, List[PTSlab]]):
        self.employees = employees
        self.p = params
        self.it_slabs = it_slabs
        self.pt_slabs = pt_slabs
        self.revisions: Dict[str, List[Tuple[date, Decimal]]] = {}
        self.exits: Dict[str, ExitInfo] = {}
        self.ytd_gross = {e.emp_id: e.gross_paid_fy_to_date for e in employees.values()}
        self.ytd_tds = {e.emp_id: e.tds_deducted_fy_to_date for e in employees.values()}
        self.run_gross = {e: ZERO for e in employees}       # gross paid by OUR runs only
        self.run_tds = {e: ZERO for e in employees}
        self.payslips: List[Payslip] = []
        self.fnf: Dict[str, FnfStatement] = {}
        self.released: Dict[str, date] = {}
        self.processed_months: set = set()
        self.warnings: List[str] = []

    # ------------------------------------------------------------ salary
    def ctc_on(self, emp_id: str, d: date) -> Decimal:
        """BR-29: the CTC in force on a given date (latest revision effective on/before d)."""
        ctc = self.employees[emp_id].ctc_annual
        for effective, new_ctc in sorted(self.revisions.get(emp_id, []), key=lambda r: r[0]):
            if effective <= d:
                ctc = new_ctc
        return ctc

    def components(self, emp: Employee, ctc: Decimal) -> Tuple[Decimal, Decimal, Decimal]:
        """Full-month (basic, hra, special) at a CTC, unrounded.  BR-16/17/18"""
        monthly = ctc / TWELVE
        basic = monthly * self.p.basic_pct / HUNDRED
        hra_pct = self.p.hra_metro_pct if emp.metro else self.p.hra_other_pct
        hra = basic * hra_pct / HUNDRED
        return basic, hra, monthly - basic - hra

    def monthly_gross_standard(self, emp_id: str, d: date) -> Decimal:
        """A full month's gross at the CTC in force on d (no LOP). Used to project future months."""
        return money(self.ctc_on(emp_id, d) / TWELVE)

    def earnings(self, emp: Employee, summary: MonthlyAttendanceSummary
                 ) -> Tuple[Decimal, Decimal, Decimal]:
        """BR-19: each day pays (day's share of the month) at the CTC in force that day,
        so a mid-month revision is pro-rated by days at each CTC."""
        basic = hra = special = ZERO
        cal_days = Decimal(summary.calendar_days)
        for day, weight in summary.payable_by_date.items():
            if weight == 0:
                continue
            b, h, s = self.components(emp, self.ctc_on(emp.emp_id, day))
            basic += b * weight / cal_days
            hra += h * weight / cal_days
            special += s * weight / cal_days
        return money(basic), money(hra), money(special)

    # -------------------------------------------------------- statutory
    def provident_fund(self, emp: Employee, earned_basic: Decimal) -> Tuple[Decimal, Decimal]:
        """BR-20/21/22: 12% of basic; statutory part capped at the PF wage ceiling.
        pf_opt_out_excess = true -> only the capped part; false -> full basic."""
        wage = min(earned_basic, self.p.pf_wage_cap) if emp.pf_opt_out_excess else earned_basic
        amount = money(wage * self.p.pf_rate_pct / HUNDRED)
        return amount, amount            # (employee, employer)

    def professional_tax(self, emp: Employee, gross: Decimal, month: int) -> Decimal:
        """BR-23/24/25: look up the state's slab; February has its own amount."""
        slabs = self.pt_slabs.get(emp.state.strip().lower())
        if not slabs:
            self.warnings.append(f"no PT slab for state {emp.state!r} ({emp.emp_id}); PT taken as 0")
            return ZERO
        chosen = next((s for s in slabs if s.gross_from <= gross
                       and (s.gross_to is None or gross <= s.gross_to)), None)
        if chosen is None:                          # gross fell in a gap between slabs
            lower = [s for s in slabs if s.gross_from <= gross]
            chosen = lower[-1] if lower else slabs[0]
        return chosen.february_pt if month == 2 else chosen.monthly_pt

    def annual_tax(self, emp: Employee, projected_gross: Decimal) -> Decimal:
        regime = emp.tax_regime
        taxable = projected_gross - self.p.std_deduction[regime]
        if regime == "OLD":
            taxable -= min(emp.declared_80c, self.p.sec_80c_limit)
        taxable = max(taxable, ZERO)
        tax = slab_tax(taxable, self.it_slabs[regime])
        if taxable <= self.p.rebate_limit[regime]:
            tax = max(tax - self.p.rebate_max[regime], ZERO)
        return money(tax * (1 + self.p.cess_pct / HUNDRED))

    def tds_for_month(self, emp: Employee, year: int, month: int, gross_this_run: Decimal,
                      final_month: bool) -> Decimal:
        """BR-26: (projected annual tax - TDS already deducted) / remaining months,
        recomputed every month. In an exit month nothing is projected: everything
        still owed is recovered now."""
        remaining = 1 if final_month else 12 - fy_index(month) + 1
        future_months = 0 if final_month else remaining - 1
        future_gross = future_months * self.monthly_gross_standard(emp.emp_id, month_end(year, month))
        projected = self.ytd_gross[emp.emp_id] + gross_this_run + future_gross
        tax = self.annual_tax(emp, projected)
        return money(max(tax - self.ytd_tds[emp.emp_id], ZERO) / remaining)

    # ------------------------------------------------------- monthly run
    def run_month(self, runner, year: int, month: int, run_date: date,
                  summaries: Dict[str, MonthlyAttendanceSummary]) -> Tuple[int, int]:
        label = f"{year:04d}-{month:02d}"
        made = fnf_made = 0
        for emp_id, s in sorted(summaries.items()):
            emp = self.employees[emp_id]
            basic, hra, special = self.earnings(emp, s)
            gross = basic + hra + special
            pf_emp, pf_er = self.provident_fund(emp, basic)
            pt = self.professional_tax(emp, gross, month)

            exit_info = self.exits.get(emp_id)
            final_month = bool(exit_info and (exit_info.last_working_day.year,
                                              exit_info.last_working_day.month) == (year, month))
            encashment = ZERO
            if final_month:
                el_balance = max(runner.balances.get(emp_id, "EL"), ZERO)
                basic_monthly = money(self.components(emp, self.ctc_on(emp_id, exit_info.last_working_day))[0])
                encashment = money(el_balance * basic_monthly / self.p.encash_divisor)
            tds = self.tds_for_month(emp, year, month, gross + encashment, final_month)

            other = ZERO
            total_ded = pf_emp + pt + tds + other
            lop = s.lop_days
            if PAYSLIP_LOP_INCLUDES_UNAUTHORISED:
                lop += s.unauthorised_days
            if PAYSLIP_LOP_INCLUDES_HALF_DAY:
                lop += s.half_day_unpaid
            self.payslips.append(Payslip(
                month=label, emp_id=emp_id, calendar_days=s.calendar_days,
                payable_days=s.payable_days, lop_days=lop, basic=basic, hra=hra,
                special_allowance=special, gross=gross, pf_employee=pf_emp,
                professional_tax=pt, tds=tds, other_deductions=other,
                total_deductions=total_ded, net_pay=gross - total_ded,
                pf_employer=pf_er, employer_cost=gross + pf_er))
            made += 1
            self.ytd_gross[emp_id] += gross + encashment
            self.ytd_tds[emp_id] += tds
            self.run_gross[emp_id] += gross + encashment
            self.run_tds[emp_id] += tds

            if final_month:
                self._full_and_final(runner, emp, exit_info, gross, encashment,
                                     pf_emp + pt + tds)
                fnf_made += 1
        self.processed_months.add((year, month))
        return made, fnf_made

    def _full_and_final(self, runner, emp: Employee, ex: ExitInfo, salary_to_lwd: Decimal,
                        encashment: Decimal, statutory: Decimal) -> None:
        """BR-30..34."""
        served = (ex.last_working_day - ex.resignation_date).days
        shortfall = max(ex.notice_required_days - served, 0)
        gross_basis = self.monthly_gross_standard(emp.emp_id, ex.last_working_day)
        recovery = money(shortfall * gross_basis / self.p.notice_divisor)
        net = salary_to_lwd + encashment - recovery - ex.asset_recovery - statutory
        self.fnf[emp.emp_id] = FnfStatement(
            emp_id=emp.emp_id, last_working_day=ex.last_working_day,
            salary_to_lwd=salary_to_lwd, el_encashment=encashment,
            notice_shortfall_days=shortfall, notice_recovery=recovery,
            asset_recovery=ex.asset_recovery, statutory_deductions=statutory,
            net_payable=money(net),
            release_date=ex.last_working_day + timedelta(days=self.p.fnf_release_days))
        runner.balances.set(emp.emp_id, "EL", ZERO)        # the balance has been paid out

    # ---------------------------------------------------- command handlers
    def handlers(self):
        return {"REVISE_CTC": self._h_revise, "REGIME_CHANGE": self._h_regime,
                "RUN_PAYROLL": self._h_run, "EXIT": self._h_exit,
                "FNF_RELEASE": self._h_release}

    def _need_employee(self, emp_id: str) -> Employee:
        emp = self.employees.get(emp_id)
        if emp is None:
            raise CommandRejected(f"{emp_id} is not an employee")
        return emp

    def _h_revise(self, runner, line_no, a, ctx):
        emp_id, effective, new_ctc = a[0], date.fromisoformat(a[1]), Decimal(a[2])
        self._need_employee(emp_id)
        if new_ctc <= 0:
            raise CommandRejected("new CTC must be positive", ["BR-29"])
        if emp_id in self.exits and effective > self.exits[emp_id].last_working_day:
            raise CommandRejected("revision is after the last working day", ["BR-29"])
        self.revisions.setdefault(emp_id, []).append((effective, new_ctc))
        note = f"CTC {new_ctc} effective {effective}"
        if any((effective.year, effective.month) <= m for m in self.processed_months):
            note += " (month already processed: arrears are not calculated)"
            self.warnings.append(f"{emp_id}: revision effective {effective} arrived after its payroll run")
        return "OK", note, ["BR-29"]

    def _h_regime(self, runner, line_no, a, ctx):
        emp_id, new_regime = a[0], a[1].upper()
        emp = self._need_employee(emp_id)
        raise CommandRejected(
            f"tax regime is fixed for the financial year ({emp.tax_regime} -> {new_regime} refused)",
            ["BR-27"])

    def _h_exit(self, runner, line_no, a, ctx):
        emp_id = a[0]
        self._need_employee(emp_id)
        info = ExitInfo(emp_id, date.fromisoformat(a[1]), date.fromisoformat(a[2]),
                        int(a[3]), money(Decimal(a[4])))
        self.exits[emp_id] = info
        served = (info.last_working_day - info.resignation_date).days
        return "OK", (f"exit registered: LWD {info.last_working_day}, served {served} of "
                      f"{info.notice_required_days} notice days"), ["BR-28", "BR-30"]

    def _h_run(self, runner, line_no, a, ctx):
        made, fnf = self.run_month(runner, ctx["year"], ctx["month"], ctx["run_date"], ctx["summaries"])
        msg = f"{made} payslips generated"
        if fnf:
            msg += f", {fnf} full-and-final statement(s)"
        return "OK", msg, ["BR-16", "BR-19", "BR-20", "BR-23", "BR-26"]

    def _h_release(self, runner, line_no, a, ctx):
        emp_id, on = a[0], date.fromisoformat(a[1])
        self._need_employee(emp_id)
        st = self.fnf.get(emp_id)
        if st is None:
            raise CommandRejected(f"no full-and-final statement for {emp_id}", ["BR-34"])
        self.released[emp_id] = on
        note = (f"F&F {emp_id}: salary {st.salary_to_lwd} + EL {st.el_encashment} - notice "
                f"{st.notice_recovery} - assets {st.asset_recovery} - statutory "
                f"{st.statutory_deductions} = net {st.net_payable}")
        if on < st.release_date:
            note += f" (released before the {st.release_date} release date)"
            self.warnings.append(f"{emp_id}: F&F released {on}, earlier than {st.release_date}")
        return "OK", note, ["BR-34"]

    # --------------------------------------------------------------- annual
    def annual_summary_rows(self) -> List[dict]:
        """Form-16-style summary of the financial year so far (earlier months come from employees.csv)."""
        rows = []
        for emp_id in sorted(self.employees):
            emp = self.employees[emp_id]
            if self.run_gross[emp_id] == 0 and emp.gross_paid_fy_to_date == 0:
                continue
            total_gross = self.ytd_gross[emp_id]
            std = self.p.std_deduction[emp.tax_regime]
            ded_80c = min(emp.declared_80c, self.p.sec_80c_limit) if emp.tax_regime == "OLD" else ZERO
            taxable = max(total_gross - std - ded_80c, ZERO)
            rows.append({
                "emp_id": emp_id, "tax_regime": emp.tax_regime,
                "gross_before_period": emp.gross_paid_fy_to_date,
                "gross_in_period": self.run_gross[emp_id], "total_gross": total_gross,
                "standard_deduction": std, "deduction_80c": ded_80c,
                "taxable_income": taxable, "tax_on_income_to_date": self.annual_tax(emp, total_gross),
                "tds_before_period": emp.tds_deducted_fy_to_date,
                "tds_in_period": self.run_tds[emp_id], "total_tds": self.ytd_tds[emp_id]})
        return rows
