"""Fechas de estados de cuenta mexicanos a ``datetime.date``."""

from __future__ import annotations

import re
from datetime import date, timedelta

MONTHS = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "SEPT": 9, "SET": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

FULL_RE = re.compile(r"^(\d{1,2})[/-]([A-Za-z]{3,4}\.?|\d{1,2})[/-](\d{2}|\d{4})$")
SHORT_RE = re.compile(r"^(\d{1,2})[/-]([A-Za-z]{3,4}\.?|\d{1,2})$")


def _month(token: str) -> int | None:
    t = token.rstrip(".").upper()
    if t.isdigit():
        m = int(t)
        return m if 1 <= m <= 12 else None
    return MONTHS.get(t)


def parse_full_date(token: str) -> date | None:
    """``05/09/2026``, ``05/SEP/2026``, ``05/ABR./2026``, ``05-09-26``."""
    m = FULL_RE.match(token.strip())
    if not m:
        return None
    month = _month(m.group(2))
    year = int(m.group(3))
    if year < 100:
        year += 2000
    try:
        return date(year, month, int(m.group(1))) if month else None
    except ValueError:
        return None


def parse_short_date(
    token: str, period_start: date | None, period_end: date | None, month_first: bool = False
) -> date | None:
    """``05/SEP`` o ``05/09`` sin año: el año se infiere del periodo del estado de cuenta.

    ``month_first`` para bancos que imprimen ``MM/DD`` (BanCoppel).
    """
    m = SHORT_RE.match(token.strip())
    if not m:
        return None
    day_s, month_s = (m.group(2), m.group(1)) if month_first else (m.group(1), m.group(2))
    month = _month(month_s)
    if not month or not day_s.isdigit():
        return None
    ref = period_end or period_start or date.today()
    try:
        candidate = date(ref.year, month, int(day_s))
    except ValueError:
        return None
    # periodo que cruza diciembre→enero: un movimiento de diciembre es del año anterior
    if candidate > ref + timedelta(days=7):
        try:
            candidate = candidate.replace(year=ref.year - 1)
        except ValueError:
            return None
    return candidate
