"""Statutory tables and parameters: tax_params.csv, it_slabs.csv, pt_slabs.csv.

tax_params.csv holds scalar parameters under key names we have not been told
(README: 'key,value'). So each parameter is found by looking for a key that
contains certain words (e.g. 'std', 'old'). Every lookup is recorded in
`TaxParams.report`, and anything not found falls back to a documented default
(the FY 2026-27 values). The run script prints the report so you can check it.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Sequence, Tuple

D = Decimal

# (words that must all appear in the key, words that must NOT appear)
TokenSet = Tuple[Tuple[str, ...], Tuple[str, ...]]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


class TaxParams:
    def __init__(self, raw: Dict[str, str]):
        self.raw = dict(raw)
        self._by_norm = {_norm(k): k for k in self.raw}
        self.report: List[Tuple[str, str, str]] = []   # (logical name, key used or DEFAULT, value)

    @classmethod
    def from_csv(cls, path: str) -> "TaxParams":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            raw = {(r.get("key") or "").strip(): (r.get("value") or "").strip() for r in reader}
        return cls({k: v for k, v in raw.items() if k})

    def number(self, name: str, token_sets: Sequence[TokenSet], default: Decimal) -> Decimal:
        for include, exclude in token_sets:
            hits = [orig for n, orig in self._by_norm.items()
                    if all(t in n for t in include) and not any(t in n for t in exclude)]
            for key in sorted(hits, key=len):
                try:
                    value = Decimal(self.raw[key])
                except InvalidOperation:
                    continue
                self.report.append((name, key, str(value)))
                return value
        self.report.append((name, "DEFAULT", str(default)))
        return default


def _ts(*pairs) -> List[TokenSet]:
    """_ts(("std","old"), (("hra","metro"), ("non",))) helper for readability."""
    out: List[TokenSet] = []
    for p in pairs:
        if p and isinstance(p[0], tuple):
            out.append((p[0], p[1]))
        else:
            out.append((tuple(p), ()))
    return out


@dataclass
class PayrollParams:
    pf_rate_pct: Decimal = D("12")
    pf_wage_cap: Decimal = D("15000")
    basic_pct: Decimal = D("40")
    hra_metro_pct: Decimal = D("50")
    hra_other_pct: Decimal = D("40")
    std_deduction: Dict[str, Decimal] = field(default_factory=lambda: {"OLD": D("50000"), "NEW": D("75000")})
    sec_80c_limit: Decimal = D("150000")
    rebate_limit: Dict[str, Decimal] = field(default_factory=lambda: {"OLD": D("500000"), "NEW": D("1200000")})
    rebate_max: Dict[str, Decimal] = field(default_factory=lambda: {"OLD": D("12500"), "NEW": D("60000")})
    cess_pct: Decimal = D("4")
    fnf_release_days: int = 45
    encash_divisor: Decimal = D("30")
    notice_divisor: Decimal = D("30")
    report: List[Tuple[str, str, str]] = field(default_factory=list)

    @classmethod
    def from_tax_params(cls, tp: TaxParams) -> "PayrollParams":
        p = cls()
        p.pf_rate_pct = tp.number("pf_rate_pct", _ts(("pf", "rate"), ("epf", "rate"), ("pf", "pct")), p.pf_rate_pct)
        p.pf_wage_cap = tp.number("pf_wage_cap", _ts(("pf", "cap"), ("pf", "ceiling"), ("pf", "wage")), p.pf_wage_cap)
        p.basic_pct = tp.number("basic_pct", _ts(("basic", "pct"), ("basic", "percent")), p.basic_pct)
        p.hra_metro_pct = tp.number("hra_metro_pct", _ts((("hra", "metro"), ("non", "other"))), p.hra_metro_pct)
        p.hra_other_pct = tp.number("hra_other_pct", _ts(("hra", "non"), ("hra", "other")), p.hra_other_pct)
        for regime in ("OLD", "NEW"):
            r = regime.lower()
            p.std_deduction[regime] = tp.number(f"std_deduction_{r}", _ts(("std", r), ("standard", r)), p.std_deduction[regime])
            p.rebate_limit[regime] = tp.number(
                f"rebate_limit_{r}",
                _ts((("rebate", "limit", r), ()), (("87a", "limit", r), ()), (("rebate", "income", r), ()),
                    (("rebate", "threshold", r), ())), p.rebate_limit[regime])
            p.rebate_max[regime] = tp.number(
                f"rebate_max_{r}",
                _ts((("rebate", "max", r), ()), (("rebate", "amount", r), ()), (("87a", "max", r), ())),
                p.rebate_max[regime])
        p.sec_80c_limit = tp.number("sec_80c_limit", _ts(("80c",)), p.sec_80c_limit)
        p.cess_pct = tp.number("cess_pct", _ts(("cess",)), p.cess_pct)
        p.fnf_release_days = int(tp.number("fnf_release_days", _ts(("release",), ("fnf", "days")), D(p.fnf_release_days)))
        p.encash_divisor = tp.number("encash_divisor", _ts(("encash",), ("el", "div")), p.encash_divisor)
        p.notice_divisor = tp.number("notice_divisor", _ts(("notice", "div"), ("notice", "recover"), ("notice", "basis")), p.notice_divisor)
        p.report = list(tp.report)
        return p


# ------------------------------------------------------------------ slabs
Slab = Tuple[Decimal, Optional[Decimal], Decimal]       # (from exclusive, to inclusive or None, rate %)


def load_it_slabs(path: str) -> Dict[str, List[Slab]]:
    slabs: Dict[str, List[Slab]] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            regime = row["regime"].strip().upper()
            to = row["income_to"].strip()
            slabs.setdefault(regime, []).append(
                (Decimal(row["income_from"].strip()), Decimal(to) if to else None,
                 Decimal(row["rate_pct"].strip())))
    for lst in slabs.values():
        lst.sort(key=lambda s: s[0])
    return slabs


def slab_tax(income: Decimal, slabs: Sequence[Slab]) -> Decimal:
    """Tax on `income` using marginal slabs (lower bound exclusive, upper inclusive)."""
    tax = D("0")
    for lo, hi, rate in slabs:
        if income > lo:
            top = income if hi is None else min(income, hi)
            tax += (top - lo) * rate / D("100")
    return tax


@dataclass(frozen=True)
class PTSlab:
    gross_from: Decimal            # inclusive
    gross_to: Optional[Decimal]    # inclusive; None = no upper limit
    monthly_pt: Decimal
    february_pt: Decimal


def load_pt_slabs(path: str) -> Dict[str, List[PTSlab]]:
    out: Dict[str, List[PTSlab]] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            to = row["gross_to"].strip()
            out.setdefault(row["state"].strip().lower(), []).append(PTSlab(
                Decimal(row["gross_from"].strip()), Decimal(to) if to else None,
                Decimal(row["monthly_pt"].strip()), Decimal(row["february_pt"].strip())))
    for lst in out.values():
        lst.sort(key=lambda s: s.gross_from)
    return out
