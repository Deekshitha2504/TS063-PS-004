"""One call that wires the leave side and the payroll side together."""
from __future__ import annotations

import os
from typing import Tuple

from .commands import CommandRunner
from .params import PayrollParams, TaxParams, load_it_slabs, load_pt_slabs
from .payroll import PayrollEngine
from .payroll_outputs import (write_annual_summary, write_bank_advice, write_fnf,
                              write_payslips)


def build(data_dir: str) -> Tuple[CommandRunner, PayrollEngine]:
    p = lambda name: os.path.join(data_dir, name)   # noqa: E731
    runner = CommandRunner(data_dir)
    params = PayrollParams.from_tax_params(TaxParams.from_csv(p("tax_params.csv")))
    engine = PayrollEngine(runner.employees, params,
                           load_it_slabs(p("it_slabs.csv")), load_pt_slabs(p("pt_slabs.csv")))
    runner.handlers.update(engine.handlers())
    return runner, engine


def write_all(runner: CommandRunner, engine: PayrollEngine, out_dir: str) -> None:
    runner.write_outputs(out_dir)                       # leave_ledger, leave_balances, command_log
    write_payslips(os.path.join(out_dir, "payslips.csv"), engine.payslips)
    write_fnf(os.path.join(out_dir, "fnf_statements.csv"), list(engine.fnf.values()))
    write_bank_advice(os.path.join(out_dir, "bank_advice.csv"), engine.payslips, runner.employees)
    write_annual_summary(os.path.join(out_dir, "annual_tax_summary.csv"), engine.annual_summary_rows())
