"""Read the sample-data CSVs. Bad rows are logged as DataIssue and skipped,
so one dirty row never crashes a whole payroll month."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

from .config import LEAVE_TYPES_WITH_BALANCE, VALID_ATTENDANCE_STATUSES
from .models import CompOffCredit, DataIssue, Employee


def _read_rows(path: str, required: Iterable[str]) -> Iterator[Tuple[int, Dict[str, str]]]:
    # utf-8-sig quietly removes the invisible BOM that Excel adds to CSV files
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = [c.strip() for c in (reader.fieldnames or [])]
        missing = [c for c in required if c not in columns]
        if missing:
            raise ValueError(f"{path}: missing columns {missing}")
        for line_no, row in enumerate(reader, start=2):  # line 1 is the header
            yield line_no, {
                (k or "").strip(): (v or "").strip() for k, v in row.items()
            }


def _parse_date(text: str) -> date:
    return date.fromisoformat(text)


def _parse_decimal(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {text!r}") from exc


def load_employees(path: str) -> Dict[str, Employee]:
    required = ["emp_id", "name", "gender", "grade", "department",
                "joining_date", "manager_id"]
    employees: Dict[str, Employee] = {}
    for _, row in _read_rows(path, required):
        emp = Employee(
            emp_id=row["emp_id"],
            name=row["name"],
            gender=row["gender"].upper(),
            grade=row["grade"].upper(),
            department=row["department"],
            joining_date=_parse_date(row["joining_date"]),
            manager_id=row["manager_id"] or None,
            location=row.get("location", ""),
            state=row.get("state", ""),
            metro=row.get("metro", "").lower() == "true",
            ctc_annual=_parse_decimal(row.get("ctc_annual") or "0"),
            tax_regime=(row.get("tax_regime") or "NEW").upper(),
            pf_opt_out_excess=row.get("pf_opt_out_excess", "").lower() == "true",
            declared_80c=_parse_decimal(row.get("declared_80c") or "0"),
            gross_paid_fy_to_date=_parse_decimal(row.get("gross_paid_fy_to_date") or "0"),
            tds_deducted_fy_to_date=_parse_decimal(row.get("tds_deducted_fy_to_date") or "0"),
            bank_account=row.get("bank_account", ""),
            ifsc=row.get("ifsc", ""),
            pan=row.get("pan", ""),
        )
        employees[emp.emp_id] = emp
    return employees


def load_holidays(path: str) -> Dict[date, str]:
    return {_parse_date(row["date"]): row["name"]
            for _, row in _read_rows(path, ["date", "name"])}


def load_opening_balances(path: str) -> Dict[Tuple[str, str], Decimal]:
    balances: Dict[Tuple[str, str], Decimal] = {}
    for line_no, row in _read_rows(path, ["emp_id", "leave_type", "balance"]):
        leave_type = row["leave_type"].upper()
        if leave_type not in LEAVE_TYPES_WITH_BALANCE:
            raise ValueError(f"{path} line {line_no}: unexpected leave_type {leave_type!r}")
        balances[(row["emp_id"], leave_type)] = _parse_decimal(row["balance"])
    return balances


def load_comp_off_credits(path: str) -> List[CompOffCredit]:
    return [
        CompOffCredit(
            emp_id=row["emp_id"],
            worked_date=_parse_date(row["worked_date"]),
            credited_on=_parse_date(row["credited_on"]),
            days=_parse_decimal(row["days"]),
        )
        for _, row in _read_rows(path, ["emp_id", "worked_date", "credited_on", "days"])
    ]


def load_attendance(
    path: str, known_emp_ids: Set[str]
) -> Tuple[Dict[Tuple[str, date], str], List[DataIssue], int]:
    """Return (status by (emp_id, date), issues, raw_row_count).

    Cleaning rules (all from the README's planted traps):
      * unknown employee id        -> skip the row, log UNKNOWN_EMPLOYEE
      * invalid status             -> skip the row, log INVALID_STATUS
      * duplicate (emp, date) row  -> count once (keep the first), log DUPLICATE_ROW
        (CONFLICTING_DUPLICATE if the two rows disagree)
    """
    statuses: Dict[Tuple[str, date], str] = {}
    issues: List[DataIssue] = []
    raw_count = 0
    for line_no, row in _read_rows(path, ["emp_id", "date", "status"]):
        raw_count += 1
        emp_id = row["emp_id"]
        status = row["status"].upper()
        day = _parse_date(row["date"])
        if emp_id not in known_emp_ids:
            issues.append(DataIssue(path, line_no, "UNKNOWN_EMPLOYEE",
                                    f"{emp_id} is not in employees.csv; row skipped"))
            continue
        if status not in VALID_ATTENDANCE_STATUSES:
            issues.append(DataIssue(path, line_no, "INVALID_STATUS",
                                    f"{emp_id} {day}: status {status!r} is not valid; row skipped"))
            continue
        key = (emp_id, day)
        if key in statuses:
            kind = "DUPLICATE_ROW" if statuses[key] == status else "CONFLICTING_DUPLICATE"
            issues.append(DataIssue(path, line_no, kind,
                                    f"{emp_id} {day} appears twice (kept {statuses[key]!r})"))
            continue
        statuses[key] = status
    return statuses, issues, raw_count


def index_by_employee(
    statuses: Dict[Tuple[str, date], str]
) -> Dict[str, Dict[date, str]]:
    """{(emp, date): status}  ->  {emp: {date: status}}"""
    out: Dict[str, Dict[date, str]] = {}
    for (emp_id, day), status in statuses.items():
        out.setdefault(emp_id, {})[day] = status
    return out
