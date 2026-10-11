from datetime import date
from decimal import Decimal

from mxbank.loader import Word, _group_lines
from mxbank.normalize.amounts import is_amount, parse_amount, parse_number
from mxbank.normalize.dates import parse_full_date, parse_short_date
from mxbank.text import clean, norm

SOFT = "­"


def test_soft_hyphen_is_minus():
    assert clean(f"{SOFT}3.20") == "-3.20"
    assert parse_amount(f"{SOFT}1,234.50") == Decimal("-1234.50")
    assert parse_number(f"{SOFT}3.20") == Decimal("-3.20")
    assert norm(f"{SOFT} Menos Retención") == "- MENOS RETENCION"


def test_amounts():
    assert is_amount("99,999.99") and is_amount("$1,520.00") and is_amount("-9,999.99")
    assert not is_amount("999") and not is_amount("9.999") and not is_amount("0012345678")
    assert parse_amount("$1,520.00") == Decimal("1520.00")


def test_dates():
    assert parse_full_date("15/08/2026") == date(2026, 8, 15)
    assert parse_full_date("15/ABR./2026") == date(2026, 4, 15)
    assert parse_full_date("05-09-26") == date(2026, 9, 5)
    assert parse_short_date("16/AGO", date(2026, 8, 15), date(2026, 9, 14)) == date(2026, 8, 16)
    assert parse_short_date("20/04", date(2026, 4, 15), date(2026, 5, 14)) == date(2026, 4, 20)
    assert parse_short_date("04/20", date(2026, 4, 15), date(2026, 5, 14), month_first=True) == date(2026, 4, 20)
    # periodo que cruza el año
    assert parse_short_date("28/DIC", date(2025, 12, 15), date(2026, 1, 14)) == date(2025, 12, 28)
    assert parse_short_date("31/02", None, date(2026, 3, 1)) is None


def test_rows_group_with_tolerance():
    words = [Word("PAGO", 107, 130, 154.0, 10), Word("99.99", 380, 420, 156.2, 8.5), Word("Ref", 106, 120, 166, 9.5)]
    lines = _group_lines(1, words)
    assert [ln.text for ln in lines] == ["PAGO 99.99", "Ref"]
