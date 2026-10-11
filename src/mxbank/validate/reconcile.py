"""Conciliación contable: detecta extracciones incorrectas."""

from __future__ import annotations

from decimal import Decimal

from ..models.raw import RawStatement
from ..models.statement import Validation
from ..normalize.amounts import q

ZERO = Decimal("0")


def validate(raw: RawStatement) -> Validation:
    s = raw.summary
    warnings = list(raw.warnings)
    credits = sum((t.credit or ZERO for t in raw.transactions), ZERO)
    debits = sum((t.debit or ZERO for t in raw.transactions), ZERO)
    counted = [t for t in raw.transactions if t.type not in raw.totals_exclude]
    n_credits = sum(1 for t in counted if t.credit)
    n_debits = sum(1 for t in counted if t.debit)
    counted_credits = sum((t.credit or ZERO for t in counted), ZERO)
    counted_debits = sum((t.debit or ZERO for t in counted), ZERO)

    opening, closing = s.get("opening_balance"), s.get("closing_balance")
    reconciled = expected = difference = None
    if raw.reconciliation is not None:
        expected, reported = raw.reconciliation
        difference = reported - expected
        reconciled = difference == 0
        if not reconciled:
            warnings.append("La suma de movimientos no cuadra con el resumen del periodo.")
    elif opening is not None and closing is not None:
        expected = opening + credits - debits
        difference = closing - expected
        reconciled = difference == 0
        if not reconciled:
            warnings.append("La suma de movimientos no cuadra con los saldos inicial y final.")
    else:
        warnings.append("No se encontraron saldo inicial y/o final para conciliar.")

    # totales que reporta el propio banco
    checks = []
    for total_key, count_key, total, count in (
        ("total_credits", "credits_count", counted_credits, n_credits),
        ("total_debits", "debits_count", counted_debits, n_debits),
    ):
        for source in (s, raw.bank_totals):
            if source.get(total_key) is not None:
                checks.append(source[total_key] == total)
            if source.get(count_key) is not None:
                checks.append(source[count_key] == count)
    bank_totals_match = all(checks) if checks else None
    if bank_totals_match is False:
        warnings.append("Los totales o conteos de movimientos no coinciden con los que reporta el banco.")

    checked = errors = 0
    if raw.balance_mode and opening is not None:
        running = opening
        for t in raw.transactions:
            running += (t.credit or ZERO) - (t.debit or ZERO)
            candidates = [b for b in (t.balance, t.balance_operation) if b is not None]
            if not candidates:
                continue
            checked += 1
            if running not in candidates:
                errors += 1
                running = t.balance if t.balance is not None else candidates[0]
        if errors:
            warnings.append(f"{errors} saldos de movimiento no coinciden con el saldo corrido.")

    return Validation(
        reconciled=reconciled,
        expected_closing_balance=q(expected),
        difference=q(difference),
        running_balance_checked=checked,
        running_balance_errors=errors,
        bank_totals_match=bank_totals_match,
        warnings=warnings,
    )
