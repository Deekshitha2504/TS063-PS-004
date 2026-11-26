from datetime import date
from decimal import Decimal as D

import pytest

from leave_attendance.attendance import summarise_month
from leave_attendance.leave_requests import CommandRejected
from leave_attendance.models import Employee
from leave_attendance.params import PayrollParams, PTSlab, TaxParams, slab_tax
from leave_attendance.payroll import PayrollEngine, money

NEW_SLABS = [(D("0"), D("400000"), D("0")), (D("400000"), D("800000"), D("5")),
             (D("800000"), D("1200000"), D("10")), (D("1200000"), D("1600000"), D("15")),
             (D("1600000"), None, D("20"))]
OLD_SLABS = [(D("0"), D("250000"), D("0")), (D("250000"), D("500000"), D("5")),
             (D("500000"), D("1000000"), D("20")), (D("1000000"), None, D("30"))]
PT = {"karnataka": [PTSlab(D("0"), D("25000"), D("0"), D("0")),
                    PTSlab(D("25000.01"), None, D("200"), D("300"))],
      "maharashtra": [PTSlab(D("0"), D("7500"), D("0"), D("0")),
                      PTSlab(D("7500.01"), None, D("175"), D("300"))]}


def emp(emp_id="E1", ctc="600000", metro=True, state="Karnataka", regime="NEW", opt_out=False,
        d80c="0", gross_ytd="0", tds_ytd="0", joining=date(2020, 1, 1)):
    return Employee(emp_id, emp_id, "M", "G2", "Eng", joining, None, state=state, metro=metro,
                    ctc_annual=D(ctc), tax_regime=regime, pf_opt_out_excess=opt_out,
                    declared_80c=D(d80c), gross_paid_fy_to_date=D(gross_ytd),
                    tds_deducted_fy_to_date=D(tds_ytd))


def engine(*emps):
    params = PayrollParams.from_tax_params(TaxParams({}))
    return PayrollEngine({e.emp_id: e for e in emps}, params,
                         {"NEW": NEW_SLABS, "OLD": OLD_SLABS}, PT)


def full_month(e, year, month, status="P", days=None):
    from leave_attendance.calendar_utils import days_in_month
    n = days_in_month(year, month)
    rows = {date(year, month, d): status for d in (days or range(1, n + 1))}
    return summarise_month(e.emp_id, year, month, rows, {})


# ---------------------------------------------------------------- earnings
def test_components_add_up_to_monthly_ctc():
    e = emp(ctc="600000")
    eng = engine(e)
    basic, hra, special = eng.components(e, D("600000"))
    assert basic == D("20000") and hra == D("10000") and special == D("20000")
    assert basic + hra + special == D("50000")


def test_non_metro_hra_is_40_percent():
    e = emp(metro=False)
    basic, hra, _ = engine(e).components(e, D("600000"))
    assert hra == D("8000")


def test_full_month_earnings_equal_monthly_ctc():
    e = emp(ctc="600000")
    eng = engine(e)
    assert eng.earnings(e, full_month(e, 2026, 12)) == (D("20000.00"), D("10000.00"), D("20000.00"))


def test_prorated_by_payable_days_two_lop_days():
    e = emp(ctc="600000")
    eng = engine(e)
    rows = {date(2026, 12, d): "P" for d in range(1, 32)}
    rows[date(2026, 12, 7)] = "A"
    rows[date(2026, 12, 8)] = "A"
    s = summarise_month("E1", 2026, 12, rows, {})
    basic, hra, special = eng.earnings(e, s)
    assert s.payable_days == D("29")
    assert basic == money(D("20000") * 29 / 31)
    assert basic + hra + special == money(D("20000") * 29 / 31) + money(D("10000") * 29 / 31) + money(D("20000") * 29 / 31)


def test_joiner_on_16th_gets_16_of_31_days():
    e = emp(ctc="372000", joining=date(2026, 12, 16))     # 372000/12 = 31000 per month
    eng = engine(e)
    s = full_month(e, 2026, 12, days=range(16, 32))
    basic, hra, special = eng.earnings(e, s)
    assert s.payable_days == D("16") and s.calendar_days == 31
    assert basic + hra + special == D("16000.00")          # 31000 x 16/31


def test_revision_on_the_1st_applies_to_whole_month():
    e = emp(ctc="600000")
    eng = engine(e)
    eng.revisions["E1"] = [(date(2027, 1, 1), D("720000"))]
    b, h, sp = eng.earnings(e, full_month(e, 2027, 1))
    assert b + h + sp == D("60000.00")


def test_mid_month_revision_is_split_by_days():
    e = emp(ctc="372000")                                   # 31000 / month before
    eng = engine(e)
    eng.revisions["E1"] = [(date(2027, 1, 16), D("744000"))]   # 62000 / month from the 16th
    b, h, sp = eng.earnings(e, full_month(e, 2027, 1))
    # 15 days at 31000/31 + 16 days at 62000/31 = 15000 + 32000
    assert b + h + sp == D("47000.00")


def test_revision_in_december_effective_10th():
    e = emp(ctc="372000")
    eng = engine(e)
    eng.revisions["E1"] = [(date(2026, 12, 10), D("744000"))]
    b, h, sp = eng.earnings(e, full_month(e, 2026, 12))
    assert b + h + sp == D("9000.00") + D("44000.00")      # 9 days x 1000 + 22 days x 2000


def test_ctc_on_uses_latest_revision_not_after_date():
    e = emp(ctc="600000")
    eng = engine(e)
    eng.revisions["E1"] = [(date(2027, 1, 16), D("720000")), (date(2026, 12, 10), D("660000"))]
    assert eng.ctc_on("E1", date(2026, 12, 9)) == D("600000")
    assert eng.ctc_on("E1", date(2026, 12, 10)) == D("660000")
    assert eng.ctc_on("E1", date(2027, 1, 16)) == D("720000")


# --------------------------------------------------------------------- PF
def test_pf_full_basic_when_not_opted_out():
    e = emp(ctc="1200000")                                  # basic 40000
    assert engine(e).provident_fund(e, D("40000")) == (D("4800.00"), D("4800.00"))


def test_pf_capped_when_opted_out():
    e = emp(ctc="1200000", opt_out=True)
    assert engine(e).provident_fund(e, D("40000")) == (D("1800.00"), D("1800.00"))


def test_pf_boundary_basic_exactly_15000():
    e = emp(ctc="450000", opt_out=True)
    eng = engine(e)
    basic = eng.components(e, D("450000"))[0]
    assert basic == D("15000") and eng.provident_fund(e, basic)[0] == D("1800.00")


# --------------------------------------------------------------------- PT
def test_pt_karnataka_boundary_25000_is_nil():
    e = emp()
    eng = engine(e)
    assert eng.professional_tax(e, D("25000.00"), 12) == D("0")
    assert eng.professional_tax(e, D("25000.01"), 12) == D("200")


def test_pt_february_uses_february_amount():
    e = emp()
    eng = engine(e)
    assert eng.professional_tax(e, D("30000"), 2) == D("300")
    assert eng.professional_tax(e, D("30000"), 1) == D("200")
    assert eng.professional_tax(e, D("20000"), 2) == D("0")


def test_pt_other_state_and_unknown_state():
    e = emp(state="Maharashtra")
    eng = engine(e)
    assert eng.professional_tax(e, D("20000"), 5) == D("175")
    odd = emp("E2", state="Goa")
    eng2 = engine(odd)
    assert eng2.professional_tax(odd, D("20000"), 5) == D("0") and eng2.warnings


# --------------------------------------------------------------------- TDS
def test_slab_tax_marginal_bounds():
    assert slab_tax(D("400000"), NEW_SLABS) == D("0")
    assert slab_tax(D("400001"), NEW_SLABS) == D("0.05")
    assert slab_tax(D("1000000"), NEW_SLABS) == D("20000") + D("20000")


def test_annual_tax_new_regime_rebate_makes_12_lakh_zero():
    e = emp(regime="NEW")
    eng = engine(e)
    assert eng.annual_tax(e, D("1275000")) == D("0.00")          # 12.75 L - 75k = 12 L
    # 15 L salary -> 14.25 L taxable: 20000 + 40000 + 15% x 2.25 L = 93,750; +4% cess = 97,500
    assert eng.annual_tax(e, D("1500000")) == D("97500.00")


def test_annual_tax_old_regime_uses_80c_and_rebate():
    e = emp(regime="OLD", d80c="150000")
    eng = engine(e)
    # 800000 - 50000 std - 150000 80C = 600000: 12500 + 20000 = 32500 -> x1.04
    assert eng.annual_tax(e, D("800000")) == money(D("32500") * D("1.04"))
    assert eng.annual_tax(e, D("500000")) == D("0.00")           # rebate wipes out tax


def test_80c_is_capped_at_limit():
    e = emp(regime="OLD", d80c="500000")
    assert engine(e).annual_tax(e, D("800000")) == engine(emp(regime="OLD", d80c="150000")).annual_tax(
        emp(regime="OLD", d80c="150000"), D("800000"))


def test_tds_spreads_remaining_tax_over_remaining_months():
    # CTC 24 lakh (2L / month). NEW regime. December: 4 months left (Dec-Mar), Apr-Nov already paid.
    e = emp(ctc="2400000", gross_ytd="1600000", tds_ytd="100000")
    eng = engine(e)
    tds = eng.tds_for_month(e, 2026, 12, D("200000"), final_month=False)
    projected = D("1600000") + D("200000") + 3 * D("200000")
    expected = money((eng.annual_tax(e, projected) - D("100000")) / 4)
    assert tds == expected and tds > 0


def test_tds_never_negative_when_overpaid():
    e = emp(ctc="2400000", gross_ytd="1600000", tds_ytd="900000")
    assert engine(e).tds_for_month(e, 2026, 12, D("200000"), final_month=False) == D("0.00")


def test_tds_recomputed_after_revision():
    e = emp(ctc="2400000", gross_ytd="1600000", tds_ytd="0")
    eng = engine(e)
    before = eng.tds_for_month(e, 2027, 1, D("200000"), False)
    eng.revisions["E1"] = [(date(2027, 1, 1), D("3600000"))]
    after = eng.tds_for_month(e, 2027, 1, D("300000"), False)
    assert after > before


def test_tds_in_final_month_recovers_everything_in_one_go():
    e = emp(ctc="2400000", gross_ytd="1600000", tds_ytd="100000")
    eng = engine(e)
    tds = eng.tds_for_month(e, 2027, 1, D("120000"), final_month=True)
    assert tds == money(eng.annual_tax(e, D("1720000")) - D("100000"))


# ------------------------------------------------------- command handlers
class FakeRunner:
    def __init__(self, el=D("0")):
        from leave_attendance.balances import LeaveBalances
        self.balances = LeaveBalances({("E1", "EL"): el})


def test_regime_change_is_always_rejected():
    eng = engine(emp())
    with pytest.raises(CommandRejected) as exc:
        eng._h_regime(None, 1, ["E1", "OLD", "2027-01-08"], {})
    assert "BR-27" in exc.value.rule_ids


def test_revise_ctc_validations():
    eng = engine(emp())
    assert eng._h_revise(None, 1, ["E1", "2027-01-16", "720000"], {})[0] == "OK"
    with pytest.raises(CommandRejected):
        eng._h_revise(None, 2, ["E1", "2027-01-16", "0"], {})
    with pytest.raises(CommandRejected):
        eng._h_revise(None, 3, ["NOPE", "2027-01-16", "720000"], {})


def test_full_and_final_clean_exit_with_el_encashment():
    e = emp(ctc="600000", gross_ytd="400000")
    eng = engine(e)
    runner = FakeRunner(el=D("6"))
    eng._h_exit(runner, 1, ["E1", "2026-12-01", "2027-02-10", "60", "0"], {})   # 71 days served: no shortfall
    rows = {date(2027, 2, d): "P" for d in range(1, 11)}
    s = summarise_month("E1", 2027, 2, rows, {})
    made, fnf = eng.run_month(runner, 2027, 2, date(2027, 2, 28), {"E1": s})
    st = eng.fnf["E1"]
    assert fnf == 1 and st.notice_shortfall_days == 0 and st.notice_recovery == D("0.00")
    assert st.el_encashment == money(D("6") * D("20000") / 30) == D("4000.00")
    assert st.release_date == date(2027, 3, 27)                     # LWD + 45 days
    slip = eng.payslips[0]
    assert st.salary_to_lwd == slip.gross
    assert st.statutory_deductions == slip.pf_employee + slip.professional_tax + slip.tds
    assert st.net_payable == money(slip.gross + st.el_encashment - st.statutory_deductions)
    assert runner.balances.get("E1", "EL") == D("0")


def test_full_and_final_short_notice_can_go_negative():
    e = emp(ctc="600000")
    eng = engine(e)
    runner = FakeRunner(el=D("1"))
    # resigns 5 Jan, last day 20 Jan: 15 days served of 60 -> 45 days short
    eng._h_exit(runner, 1, ["E1", "2027-01-05", "2027-01-20", "60", "45000.00"], {})
    rows = {date(2027, 1, d): "P" for d in range(1, 21)}
    s = summarise_month("E1", 2027, 1, rows, {})
    eng.run_month(runner, 2027, 1, date(2027, 1, 31), {"E1": s})
    st = eng.fnf["E1"]
    assert st.notice_shortfall_days == 45
    assert st.notice_recovery == money(45 * D("50000") / 30) == D("75000.00")     # gross/30 per day
    assert st.asset_recovery == D("45000.00")
    assert st.net_payable < 0


def test_fnf_release_needs_a_statement_and_warns_if_early():
    e = emp()
    eng = engine(e)
    runner = FakeRunner(el=D("2"))
    with pytest.raises(CommandRejected):
        eng._h_release(runner, 1, ["E1", "2027-03-01"], {})
    eng._h_exit(runner, 1, ["E1", "2026-12-01", "2027-02-10", "60", "0"], {})
    rows = {date(2027, 2, d): "P" for d in range(1, 11)}
    eng.run_month(runner, 2027, 2, date(2027, 2, 28), {"E1": summarise_month("E1", 2027, 2, rows, {})})
    status, message, rules = eng._h_release(runner, 2, ["E1", "2027-03-01"], {})
    assert status == "OK" and "before" in message and eng.warnings


def test_ytd_figures_roll_forward_between_months():
    e = emp(ctc="2400000", gross_ytd="1600000", tds_ytd="0")
    eng = engine(e)
    runner = FakeRunner()
    eng.run_month(runner, 2026, 12, date(2026, 12, 31), {"E1": full_month(e, 2026, 12)})
    first = eng.payslips[0]
    assert eng.ytd_gross["E1"] == D("1600000") + first.gross
    assert eng.ytd_tds["E1"] == first.tds
    eng.run_month(runner, 2027, 1, date(2027, 1, 31), {"E1": full_month(e, 2027, 1)})
    assert eng.payslips[1].tds > 0


def test_payslip_identities():
    e = emp(ctc="600000")
    eng = engine(e)
    eng.run_month(FakeRunner(), 2026, 12, date(2026, 12, 31), {"E1": full_month(e, 2026, 12)})
    p = eng.payslips[0]
    assert p.gross == p.basic + p.hra + p.special_allowance
    assert p.total_deductions == p.pf_employee + p.professional_tax + p.tds + p.other_deductions
    assert p.net_pay == p.gross - p.total_deductions
    assert p.employer_cost == p.gross + p.pf_employer
