"""Modelo interno producido por los parsers. CONTIENE PII: nunca se serializa.

Solo vive en memoria entre el parser y el redactor; el redactor construye el
``Statement`` público a partir de él (ver docs/02 §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class HeaderPII:
    """Datos personales del encabezado/CFDI. Alimentan el diccionario del redactor."""

    fields: list[tuple[str, str]] = field(default_factory=list)  # (clase, valor)
    account_number: str | None = None

    def add(self, kind: str, value: str | None) -> None:
        if value and value.strip():
            self.fields.append((kind, value.strip()))


@dataclass
class RawTransaction:
    date: date
    page: int
    first_line: str  # texto del banco tal cual (puede traer datos pegados)
    description: str  # texto canónico del banco, sin claves/números de contraparte
    type: str
    debit: Decimal | None = None
    credit: Decimal | None = None
    balance: Decimal | None = None
    balance_operation: Decimal | None = None
    posting_date: date | None = None
    value_date: date | None = None
    counterparty_name: str | None = None
    counterparty_account: str | None = None
    counterparty_bank: str | None = None
    tracking_key: str | None = None
    merchant: str | None = None
    concept: str | None = None  # texto libre escrito por personas: alto riesgo
    original_currency: str | None = None
    original_amount: Decimal | None = None
    exchange_rate: Decimal | None = None
    installment_number: int | None = None
    installments_total: int | None = None
    card_type: str | None = None
    pii: list[str] = field(default_factory=list)  # otros valores sensibles vistos en el detalle


@dataclass
class RawStatement:
    bank: str
    bank_name: str
    product: str
    product_name: str | None
    layout_version: str
    confidence: float
    pages: int
    currency: str = "MXN"
    holder_type: str = "individual"
    header: HeaderPII = field(default_factory=HeaderPII)
    period_start: date | None = None
    period_end: date | None = None
    statement_date: date | None = None
    days: int | None = None
    summary: dict[str, Decimal | int | None] = field(default_factory=dict)
    rates: dict[str, Decimal | None] = field(default_factory=dict)
    bank_totals: dict[str, Decimal | int | None] = field(default_factory=dict)
    balance_mode: str | None = None  # "per_row" | "per_day"
    # tipos que el banco NO incluye en sus totales de abonos/cargos (p. ej. intereses en BanCoppel)
    totals_exclude: frozenset[str] = frozenset()
    transactions: list[RawTransaction] = field(default_factory=list)
    credit: dict[str, object] = field(default_factory=dict)  # campos de models.statement.Credit
    installment_plans: list[dict[str, object]] = field(default_factory=list)
    # conciliación propia del producto (p. ej. tarjeta de crédito): (esperado, reportado)
    reconciliation: tuple[Decimal, Decimal] | None = None
    warnings: list[str] = field(default_factory=list)
