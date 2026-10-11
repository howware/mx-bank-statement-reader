"""Montos: siempre ``Decimal``, nunca ``float``."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

AMOUNT_RE = re.compile(r"^[-+]?\$?[-+]?\d{1,3}(?:,\d{3})*\.\d{2}$|^[-+]?\$?[-+]?\d+\.\d{2}$")
NUMBER_RE = re.compile(r"^[-+]?\d+(?:\.\d+)?$")
INT_RE = re.compile(r"^\d+$")
CENT = Decimal("0.01")


def is_amount(token: str) -> bool:
    return bool(AMOUNT_RE.match(token.replace("­", "-")))


def parse_amount(token: str) -> Decimal | None:
    t = token.replace("­", "-").replace("$", "").replace(",", "").strip()
    negative = t.startswith("-") or t.endswith("-")
    t = t.strip("+-")
    try:
        value = Decimal(t)
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_number(token: str) -> Decimal | None:
    t = token.replace("­", "-").replace("%", "").strip()
    if not NUMBER_RE.match(t):
        return None
    return Decimal(t)


def q(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(CENT)
