"""Salida pública (JSON v1). Allowlist: solo existe lo definido aquí (ver docs/03).

Cualquier campo nuevo requiere revisión de privacidad.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Money = Decimal

TxType = Literal[
    "spei_in", "spei_out", "spei_refund", "transfer_in", "transfer_out", "transfer_internal",
    "card_purchase", "card_payment", "cash_withdrawal", "cash_deposit", "payroll", "loan_payment",
    "fee", "interest", "tax", "tax_payment", "mobile_topup", "refund", "direct_debit",
    "installment", "installment_conversion", "rewards_redemption", "other",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(_Model):
    file_name: str | None = Field(description="Nombre base del archivo (omitido en perfil strict)")
    file_sha256: str | None = Field(description="Hash del PDF (omitido en perfil strict)")
    pages: int
    tool_version: str


class Document(_Model):
    bank: str
    bank_name: str
    product: str
    product_name: str | None = None
    layout_version: str
    detection_confidence: float
    currency: str


class Account(_Model):
    account_ref: str | None = Field(description="Token estable del número de cuenta (HMAC)")
    account_last4: str | None = Field(description="Últimos 4 dígitos (omitido en perfil strict)")
    holder_type: str


class Period(_Model):
    start: date | None = None
    end: date | None = None
    statement_date: date | None = None
    days: int | None = None


class Summary(_Model):
    opening_balance: Money | None = None
    total_credits: Money | None = None
    total_debits: Money | None = None
    closing_balance: Money | None = None
    average_balance: Money | None = None
    minimum_average_balance: Money | None = None
    credits_count: int | None = None
    debits_count: int | None = None
    fees_total: Money | None = None
    fees_vat: Money | None = None
    interest_earned: Money | None = None
    tax_withheld: Money | None = None


class Rates(_Model):
    gross_annual_rate_percent: Decimal | None = None
    gat_nominal_percent: Decimal | None = None
    gat_real_percent: Decimal | None = None


ID_DESCRIPTION = (
    "HMAC-SHA256 con la llave de seudónimos: estable entre ejecuciones solo con --pseudonym-key-env "
    "(pseudonym_scope = key); sin llave, válido solo dentro de una ejecución"
)


class Transaction(_Model):
    id: str = Field(description="Identificador estable del movimiento (TX_<hex>). " + ID_DESCRIPTION)
    index: int
    date: date
    posting_date: date | None = None
    value_date: date | None = None
    description: str
    type: TxType
    debit: Money | None = None
    credit: Money | None = None
    amount: Money = Field(description="Negativo = salida de dinero")
    balance: Money | None = None
    balance_operation: Money | None = None
    counterparty_ref: str | None = Field(default=None, description="Seudónimo de la contraparte")
    counterparty_account_ref: str | None = Field(default=None, description="Seudónimo de la cuenta de la contraparte")
    counterparty_bank: str | None = None
    merchant: str | None = None
    concept: str | None = Field(default=None, description="Concepto libre redactado; solo con --include-concepts")
    original_currency: str | None = Field(default=None, description="Moneda original en compras en el extranjero")
    original_amount: Money | None = None
    exchange_rate: Decimal | None = None
    installment_number: int | None = Field(default=None, description="Parcialidad N de M")
    installments_total: int | None = None
    card_type: str | None = Field(default=None, description="'digital' si se hizo con la tarjeta digital")
    page: int


class Credit(_Model):
    """Datos de la tarjeta de crédito (solo product = credit)."""

    credit_limit: Money | None = None
    available_credit: Money | None = None
    cut_off_date: date | None = None
    payment_due_date: date | None = None
    minimum_payment: Money | None = None
    minimum_payment_with_installments: Money | None = None
    no_interest_payment: Money | None = Field(default=None, description="Pago para no generar intereses")
    previous_balance: Money | None = None
    regular_charges: Money | None = None
    installment_charges: Money | None = None
    interest_charged: Money | None = None
    fees_charged: Money | None = None
    vat_on_interest_and_fees: Money | None = None
    payments_and_credits: Money | None = None
    regular_balance: Money | None = None
    installment_balance: Money | None = None
    total_balance: Money | None = Field(default=None, description="Saldo deudor total")
    cat_percent: Decimal | None = None
    annual_interest_rate_percent: Decimal | None = None


class InstallmentPlan(_Model):
    id: str = Field(description="Identificador estable de la compra a meses, igual en todos los estados donde aparece (PLAN_<hex>). " + ID_DESCRIPTION)
    description: str
    start_date: date | None = Field(default=None, description="Fecha de la operación original")
    original_amount: Money | None = None
    pending_balance: Money | None = None
    required_payment: Money | None = None
    installment_number: int | None = None
    installments_total: int | None = None
    interest_rate_percent: Decimal | None = None


class Validation(_Model):
    reconciled: bool | None = Field(description="saldo inicial + abonos − cargos = saldo final")
    expected_closing_balance: Money | None = None
    difference: Money | None = None
    running_balance_checked: int = 0
    running_balance_errors: int = 0
    bank_totals_match: bool | None = None
    warnings: list[str] = []


class Privacy(_Model):
    profile: str
    pseudonym_scope: str
    include_concepts: bool
    removed: dict[str, int]
    masked: dict[str, int]
    pseudonymized: dict[str, int]
    residual_scan: Literal["passed"]


class Statement(_Model):
    schema_version: str
    ok: Literal[True] = True
    statement_id: str = Field(description="Identificador estable del estado de cuenta: cuenta + producto + periodo (ST_<hex>). " + ID_DESCRIPTION)
    source: Source
    document: Document
    account: Account
    period: Period
    summary: Summary
    rates: Rates
    credit: Credit | None = None
    installment_plans: list[InstallmentPlan] = []
    transactions: list[Transaction]
    validation: Validation
    privacy: Privacy
