"""CSV writers for the three outputs on the leave/attendance side.
Formats follow the README: dates YYYY-MM-DD, days with one decimal,
booleans true/false, rule_ids separated by ';'."""
from __future__ import annotations

import csv
import os
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, List, Sequence

LEDGER_COLUMNS = ["req_id", "emp_id", "leave_type", "from_date", "to_date",
                  "days_counted", "status", "lop_days", "approved_on", "rule_ids"]
BALANCE_COLUMNS = ["as_of_date", "emp_id", "leave_type", "balance"]
COMMAND_LOG_COLUMNS = ["line_no", "command", "status", "rule_ids", "message"]


def fmt_days(x: Decimal) -> str:
    return str(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _write(path: str, header: Sequence[str], rows: Iterable[Sequence]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_leave_ledger(path: str, requests: List) -> None:
    rows = []
    for r in requests:
        rows.append([
            r.req_id, r.emp_id, r.leave_type, r.from_date.isoformat(), r.to_date.isoformat(),
            fmt_days(r.days_counted), r.status, fmt_days(r.lop_qty),
            r.approved_on.isoformat() if r.approved_on else "",
            ";".join(r.rule_ids),
        ])
    _write(path, LEDGER_COLUMNS, rows)


def write_leave_balances(path: str, snapshots: List[tuple]) -> None:
    """snapshots: (as_of_date, emp_id, leave_type, balance)"""
    _write(path, BALANCE_COLUMNS,
           [[d.isoformat(), e, t, fmt_days(b)] for d, e, t, b in snapshots])


def write_command_log(path: str, entries: List[tuple]) -> None:
    """entries: (line_no, command, status, rule_ids list, message)"""
    _write(path, COMMAND_LOG_COLUMNS,
           [[n, c, s, ";".join(rules), m] for n, c, s, rules, m in entries])
