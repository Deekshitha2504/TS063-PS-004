"""Plain data containers shared by the modules."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from .config import COMP_OFF_VALIDITY_DAYS


@dataclass(frozen=True)
class Employee:
    emp_id: str
    name: str
    gender: str
    grade: str
    department: str
    joining_date: date
    manager_id: Optional[str]  # blank in the file -> None
    # ---- payroll fields (employees.csv); defaults keep the leave-only tests simple ----
    location: str = ""
    state: str = ""
    metro: bool = False
    ctc_annual: Decimal = Decimal("0")
    tax_regime: str = "NEW"
    pf_opt_out_excess: bool = False
    declared_80c: Decimal = Decimal("0")
    gross_paid_fy_to_date: Decimal = Decimal("0")
    tds_deducted_fy_to_date: Decimal = Decimal("0")
    bank_account: str = ""
    ifsc: str = ""
    pan: str = ""


@dataclass(frozen=True)
class CompOffCredit:
    emp_id: str
    worked_date: date
    credited_on: date
    days: Decimal

    @property
    def expires_on(self) -> date:
        """Last day this credit can be used (BR-09: credited_on + 60 days)."""
        return self.credited_on + timedelta(days=COMP_OFF_VALIDITY_DAYS)


@dataclass(frozen=True)
class DataIssue:
    """A problem found while reading an input file (we log it and carry on)."""
    source: str
    line_no: int
    kind: str
    message: str
