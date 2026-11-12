"""Leave balances (CL/SL/EL) and the comp-off ledger."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List, Tuple

from .models import CompOffCredit

ZERO = Decimal("0")


class LeaveBalances:
    """Simple wallet: (emp_id, leave_type) -> Decimal days."""

    def __init__(self, opening: Dict[Tuple[str, str], Decimal] = None):
        self._bal: Dict[Tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
        for key, value in (opening or {}).items():
            self._bal[key] = value

    def get(self, emp_id: str, leave_type: str) -> Decimal:
        return self._bal[(emp_id, leave_type)]

    def set(self, emp_id: str, leave_type: str, value: Decimal) -> None:
        self._bal[(emp_id, leave_type)] = value

    def add(self, emp_id: str, leave_type: str, qty: Decimal) -> None:
        self._bal[(emp_id, leave_type)] += qty

    def snapshot(self, emp_ids: Iterable[str], leave_types=("CL", "SL", "EL")
                 ) -> Dict[Tuple[str, str], Decimal]:
        return {(e, t): self.get(e, t) for e in emp_ids for t in leave_types}


class CompOffLedger:
    """Comp-off credits expire (BR-09). Oldest-expiring credit is used first."""

    def __init__(self, credits: Iterable[CompOffCredit]):
        self._chunks: List[dict] = [
            {"credit": c, "remaining": c.days}
            for c in sorted(credits, key=lambda c: (c.expires_on, c.credited_on))
        ]

    def available(self, emp_id: str, on_date: date) -> Decimal:
        """Days usable on on_date (a credit is usable up to and including its expiry day)."""
        return sum(
            (ch["remaining"] for ch in self._chunks
             if ch["credit"].emp_id == emp_id and on_date <= ch["credit"].expires_on),
            ZERO,
        )

    def expired_remaining(self, emp_id: str, on_date: date) -> Decimal:
        """Unused days that had already expired by on_date."""
        return sum(
            (ch["remaining"] for ch in self._chunks
             if ch["credit"].emp_id == emp_id and on_date > ch["credit"].expires_on),
            ZERO,
        )

    def consume(self, emp_id: str, qty: Decimal, on_date: date) -> List[Tuple[int, Decimal]]:
        """Take qty days (oldest first). Returns [(chunk_index, taken)] so a
        later cancel can give them back with restore(). Raises if not enough."""
        if self.available(emp_id, on_date) < qty:
            raise ValueError(f"{emp_id}: only {self.available(emp_id, on_date)} comp-off "
                             f"days usable on {on_date}, asked for {qty}")
        taken: List[Tuple[int, Decimal]] = []
        need = qty
        for idx, ch in enumerate(self._chunks):
            if need <= 0:
                break
            if ch["credit"].emp_id != emp_id or on_date > ch["credit"].expires_on:
                continue
            use = min(ch["remaining"], need)
            if use > 0:
                ch["remaining"] -= use
                need -= use
                taken.append((idx, use))
        return taken

    def restore(self, allocations: List[Tuple[int, Decimal]]) -> None:
        for idx, qty in allocations:
            self._chunks[idx]["remaining"] += qty
