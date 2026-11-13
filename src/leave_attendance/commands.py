"""Read commands.txt and run it top to bottom (the file is the event log).

Format:  COMMAND_NAME|arg1|arg2|...      '#' lines and blank lines are ignored.
line_no in the command log is the PHYSICAL line number in the file (the README's
'line 66' style references count comment and blank lines too).

Your part handles: LEAVE_APPLY, LEAVE_APPROVE, LEAVE_REJECT, LEAVE_CANCEL, YEAR_END,
and the leave/attendance half of RUN_PAYROLL and EXIT. Everything payroll-related
is plugged in through `handlers` (see Hooks below), so your teammate's code can be
attached without editing this file.

Hooks: handlers = {"RUN_PAYROLL": fn, "EXIT": fn, "REVISE_CTC": fn, ...}
       fn(runner, line_no, args, context) -> (status, message, rule_ids)
  For RUN_PAYROLL, context = {"year","month","run_date","summaries"} where summaries is
  {emp_id: MonthlyAttendanceSummary}. For EXIT, context = {"emp_id","last_working_day"}.
"""
from __future__ import annotations

import glob
import os
import re
from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

from .accrual import AccrualEngine
from .attendance import MonthlyAttendanceSummary, summarise_month
from .balances import CompOffLedger, LeaveBalances
from .calendar_utils import HolidayCalendar, month_end, parse_month
from .config import COMP_OFF_SNAPSHOT_INCLUDE_ZERO
from .leave_requests import CommandRejected, LeaveEngine
from .loaders import (index_by_employee, load_attendance, load_comp_off_credits,
                      load_employees, load_holidays, load_opening_balances)
from .models import DataIssue
from .outputs import write_command_log, write_leave_balances, write_leave_ledger

Handler = Callable[["CommandRunner", int, List[str], dict], Tuple[str, str, List[str]]]


def _bool(text: str) -> bool:
    return text.strip().lower() in ("true", "1", "yes", "y")


class CommandRunner:
    def __init__(self, data_dir: str, opening_date: date = date(2026, 12, 1),
                 handlers: Optional[Dict[str, Handler]] = None):
        p = lambda name: os.path.join(data_dir, name)   # noqa: E731
        self.employees = load_employees(p("employees.csv"))
        self.calendar = HolidayCalendar(load_holidays(p("holidays.csv")))
        self.balances = LeaveBalances(load_opening_balances(p("leave_balances_opening.csv")))
        comp = self.comp_off = CompOffLedger(load_comp_off_credits(p("comp_off_credits.csv")))
        self.accrual = AccrualEngine(self.employees, self.balances, opening_date)
        self.leave = LeaveEngine(self.employees, self.calendar, self.balances, comp, self.accrual)
        self.handlers = handlers or {}
        self.attendance_paths: Dict[Tuple[int, int], str] = {}
        for path in glob.glob(p("attendance_*.csv")):
            m = re.search(r"attendance_(\d{4})_(\d{2})\.csv$", path)
            if m:
                self.attendance_paths[(int(m.group(1)), int(m.group(2)))] = path
        self.data_issues: List[DataIssue] = []
        self.summaries: Dict[Tuple[int, int], Dict[str, MonthlyAttendanceSummary]] = {}
        self._snapshots_by_date: Dict[date, List[tuple]] = {}
        self.log: List[tuple] = []

    # ------------------------------------------------------------- main loop
    def run_file(self, commands_path: str) -> None:
        with open(commands_path, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        for line_no, raw in enumerate(lines, start=1):
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            parts = [x.strip() for x in text.split("|")]
            name, args = parts[0].upper(), parts[1:]
            try:
                status, message, rules = self._dispatch(line_no, name, args)
            except CommandRejected as exc:
                status, message, rules = "REJECTED", str(exc), exc.rule_ids
            except (ValueError, IndexError, KeyError) as exc:
                status, message, rules = "ERROR", f"{type(exc).__name__}: {exc}", []
            self.log.append((line_no, name, status, rules, message))

    def _dispatch(self, line_no: int, name: str, args: List[str]):
        table = {
            "LEAVE_APPLY": self._leave_apply,
            "LEAVE_APPROVE": self._leave_approve,
            "LEAVE_REJECT": self._leave_reject,
            "LEAVE_CANCEL": self._leave_cancel,
            "YEAR_END": self._year_end,
            "RUN_PAYROLL": self._run_payroll,
            "EXIT": self._exit,
        }
        if name in table:
            return table[name](line_no, args)
        if name in self.handlers:                    # REVISE_CTC, REGIME_CHANGE, FNF_RELEASE ...
            return self.handlers[name](self, line_no, args, {})
        return "NOT_HANDLED", f"{name}: no handler attached (payroll side)", []

    def _tick(self, d: date, inclusive: bool = False) -> None:
        """Move the clock: credit due accruals, then auto-approve overdue requests."""
        self.accrual.advance_to(d)
        self.leave.sweep_auto_approvals(d, inclusive)

    # --------------------------------------------------------- leave commands
    def _leave_apply(self, line_no: int, a: List[str]):
        req_id, emp_id, ltype, f, t, applied, reason, medical = a[:8]
        applied_on = date.fromisoformat(applied)
        self._tick(applied_on)
        req = self.leave.apply(line_no, req_id, emp_id, ltype, date.fromisoformat(f),
                               date.fromisoformat(t), applied_on, reason, _bool(medical))
        if req.status == "REJECTED":
            return "REJECTED", "; ".join(req.messages), list(req.rule_ids)
        note = f"{req.status}, {req.days_counted} day(s) counted"
        if req.lop_qty and req.leave_type not in ("LOP",):
            note += f", {req.lop_qty} converted to LOP"
        return "OK", note, list(req.rule_ids)

    def _leave_approve(self, line_no: int, a: List[str]):
        req_id, approver, on = a[0], a[1], date.fromisoformat(a[2])
        self._tick(on)
        req = self.leave.approve(req_id, approver, on)
        return "OK", f"{req_id} now {req.status}", list(req.rule_ids)

    def _leave_reject(self, line_no: int, a: List[str]):
        req_id, approver, on, remark = a[0], a[1], date.fromisoformat(a[2]), (a[3] if len(a) > 3 else "")
        self._tick(on)
        req = self.leave.reject(req_id, approver, on, remark)
        return "OK", f"{req_id} REJECTED by {approver}", list(req.rule_ids)

    def _leave_cancel(self, line_no: int, a: List[str]):
        req_id, on = a[0], date.fromisoformat(a[1])
        self._tick(on)
        req = self.leave.cancel(req_id, on)
        return "OK", f"{req_id} CANCELLED, balance restored", list(req.rule_ids)

    # ------------------------------------------------------------ year end etc
    def _year_end(self, line_no: int, a: List[str]):
        on = date.fromisoformat(a[0])
        self._tick(on, inclusive=True)
        result = self.accrual.year_end(catch_up=False)
        # Trainers (D-22a): as_of_date is 31 December, after carry-forward and lapse and
        # before the 1 January credit. It replaces the December month-end snapshot.
        self._snapshot(date(result.closed_year, 12, 31))
        self.accrual.advance_to(self.accrual.clock)       # now credit any month already reached
        lapsed = sum(result.lapsed.values())
        return "OK", f"year {result.closed_year} closed; {lapsed} day(s) lapsed", ["BR-05"]

    def _exit(self, line_no: int, a: List[str]):
        emp_id, lwd = a[0], date.fromisoformat(a[2])
        if emp_id not in self.employees:
            raise CommandRejected(f"{emp_id} is not an employee")
        self.accrual.exit_dates[emp_id] = lwd           # stops leave accrual after exit
        if "EXIT" in self.handlers:
            return self.handlers["EXIT"](self, line_no, a, {"emp_id": emp_id, "last_working_day": lwd})
        return "NOT_HANDLED", "last working day registered for leave accrual; F&F is on the payroll side", []

    # ------------------------------------------------------------- payroll run
    def _attendance_for(self, year: int, month: int) -> Dict[str, Dict[date, str]]:
        path = self.attendance_paths.get((year, month))
        if path is None:
            raise CommandRejected(f"no attendance file for {year}-{month:02d}")
        statuses, issues, _ = load_attendance(path, set(self.employees))
        self.data_issues.extend(issues)
        return index_by_employee(statuses)

    def _run_payroll(self, line_no: int, a: List[str]):
        year, month = parse_month(a[0])
        run_date = date.fromisoformat(a[1])
        self._tick(run_date, inclusive=True)
        self.accrual.advance_to(date(year, month, 1))
        by_emp = self._attendance_for(year, month)
        summaries = {
            emp_id: summarise_month(emp_id, year, month, rows,
                                    self.leave.leave_cover(emp_id, year, month))
            for emp_id, rows in sorted(by_emp.items())
        }
        self.summaries[(year, month)] = summaries
        self._snapshot(month_end(year, month))
        if "RUN_PAYROLL" in self.handlers:
            ctx = {"year": year, "month": month, "run_date": run_date, "summaries": summaries}
            return self.handlers["RUN_PAYROLL"](self, line_no, a, ctx)
        return "OK", f"attendance summarised for {len(summaries)} employees (payroll side not attached)", []

    # ---------------------------------------------------------------- outputs
    @property
    def snapshots(self) -> List[tuple]:
        """(as_of_date, emp_id, leave_type, balance) rows in date order."""
        return [row for d in sorted(self._snapshots_by_date) for row in self._snapshots_by_date[d]]

    def _snapshot(self, as_of: date) -> None:
        """Balances as at `as_of`. A later snapshot for the same date replaces the earlier one."""
        rows: List[tuple] = []
        for emp_id in sorted(self.employees):
            if self.employees[emp_id].joining_date > as_of:
                continue
            for leave_type in ("CL", "SL", "EL"):
                rows.append((as_of, emp_id, leave_type, self.balances.get(emp_id, leave_type)))
            comp = self.comp_off.available(emp_id, as_of)        # unexpired balance only
            if comp > 0 or (COMP_OFF_SNAPSHOT_INCLUDE_ZERO and self.comp_off.has_credits(emp_id)):
                rows.append((as_of, emp_id, "COMP_OFF", comp))
        self._snapshots_by_date[as_of] = rows

    def write_outputs(self, out_dir: str) -> None:
        write_leave_ledger(os.path.join(out_dir, "leave_ledger.csv"),
                           [self.leave.requests[r] for r in self.leave.order])
        write_leave_balances(os.path.join(out_dir, "leave_balances.csv"), self.snapshots)
        write_command_log(os.path.join(out_dir, "command_log.csv"), self.log)
