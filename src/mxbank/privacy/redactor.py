"""Construye el ``Statement`` público a partir del ``RawStatement`` (ver docs/04 §3).

Capas aplicadas aquí:
1. Estructural: el modelo de salida no tiene campos para el encabezado.
2. Diccionario del documento: valores del encabezado, contrapartes y cuentas.
3. Patrones validados (CLABE, tarjeta, RFC, CURP, correo) y números de 4+ dígitos.
La capa 6 (escáner residual) vive en ``residual_scan``.
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from .. import SCHEMA_VERSION, __version__
from ..models.raw import RawStatement, RawTransaction
from ..models.statement import (
    Account,
    Credit,
    Document,
    InstallmentPlan,
    Period,
    Privacy,
    Rates,
    Source,
    Statement,
    Summary,
    Transaction,
    Validation,
)
from ..normalize.amounts import q
from ..text import norm
from . import detectors
from .pseudonym import Pseudonymizer
from .vocab import BANK_NAMES, COMMON_WORDS

PROFILES = ("minimal", "standard", "strict")
_PLAN_MONEY = {"original_amount", "pending_balance", "required_payment"}
_CREDIT_MONEY = {
    "credit_limit", "available_credit", "minimum_payment", "minimum_payment_with_installments",
    "no_interest_payment", "previous_balance", "regular_charges", "installment_charges", "interest_charged",
    "fees_charged", "vat_on_interest_and_fees", "payments_and_credits", "regular_balance",
    "installment_balance", "total_balance",
}
_TOKEN = re.compile(r"[A-Z0-9&]+")
_DIGITS4 = re.compile(r"\S*\d{4,}\S*")
_COMPANY = re.compile(r"\b(S\.?A\.?|SAPI|S\.?C\.?|S DE RL|C\.?V\.?|SOFOM|AC)\b")
_PLACEHOLDER_RUN = re.compile(r"(\[[A-Z_]+\])(?:\s+\1)+")


class Dictionary:
    """Términos PII normalizados del propio documento, buscados como palabra completa."""

    def __init__(self) -> None:
        self.terms: set[str] = set()
        self._rx: re.Pattern | None = None

    def add(self, value: str | None) -> None:
        if not value:
            return
        n = norm(value)
        if len(n) >= 4 and not n.isdigit():
            self.terms.add(n)
        for tok in _TOKEN.findall(n):
            if tok.isdigit():
                # 4 dígitos ya se eliminan en scrub(); aquí serían ruido (años, horas)
                if len(tok) >= 5:
                    self.terms.add(tok)
            elif len(tok) >= 3 and tok not in COMMON_WORDS and tok not in BANK_NAMES:
                self.terms.add(tok)
        self._rx = None

    def _pattern(self) -> re.Pattern | None:
        if self._rx is None and self.terms:
            alts = "|".join(re.escape(t) for t in sorted(self.terms, key=len, reverse=True))
            self._rx = re.compile(rf"(?<![A-Z0-9])(?:{alts})(?![A-Z0-9])")
        return self._rx

    def sub(self, ntext: str, repl: str = "[DATO]") -> tuple[str, int]:
        rx = self._pattern()
        return rx.subn(repl, ntext) if rx else (ntext, 0)

    def find(self, ntext: str) -> bool:
        rx = self._pattern()
        return bool(rx and rx.search(ntext))


class Redactor:
    def __init__(self, raw: RawStatement, profile: str, pseudo: Pseudonymizer, include_concepts: bool):
        if profile not in PROFILES:
            raise ValueError(profile)
        self.raw = raw
        self.profile = profile
        self.pseudo = pseudo
        self.include_concepts = include_concepts and profile != "strict"
        self.removed: Counter[str] = Counter()
        self.masked: Counter[str] = Counter()
        self.pseudonymized: Counter[str] = Counter()
        self.dictionary = Dictionary()
        for kind, value in raw.header.fields:
            self.dictionary.add(value)
            self.removed[kind] += 1
        for tx in raw.transactions:
            for v in (tx.counterparty_name, tx.counterparty_account, tx.tracking_key, *tx.pii):
                self.dictionary.add(v)

    # -- texto libre -------------------------------------------------------
    def scrub(self, text: str | None) -> str | None:
        if not text:
            return None
        n = norm(text)
        for hit in sorted(detectors.find(n), key=lambda h: h.start, reverse=True):
            n = n[: hit.start] + f"[{hit.kind}]" + n[hit.end :]
            self.removed[f"{hit.kind.lower()}_in_text"] += 1
        n, count = self.dictionary.sub(n)
        self.removed["dictionary_hits"] += count
        n, count = _DIGITS4.subn("[NUM]", n)
        self.removed["numbers_in_text"] += count
        n = _PLACEHOLDER_RUN.sub(r"\1", re.sub(r"\s+", " ", n)).strip()
        return n or None

    # -- construcción ------------------------------------------------------
    def _transaction(self, i: int, tx: RawTransaction) -> Transaction:
        description = self.scrub(tx.description) or "[SIN DESCRIPCION]"
        if self.profile == "strict" and tx.type == "other":
            description = "[OTRO]"
        counterparty_ref = None
        if tx.counterparty_name:
            prefix = "EMPRESA" if _COMPANY.search(norm(tx.counterparty_name)) else "PERSONA"
            counterparty_ref = self.pseudo.token(prefix, tx.counterparty_name)
            self.pseudonymized["counterparty"] += 1
        account_ref = None
        if tx.counterparty_account:
            account_ref = self.pseudo.token("CUENTA", tx.counterparty_account)
            self.pseudonymized["counterparty_account"] += 1
        if tx.tracking_key:
            self.removed["tracking_key"] += 1
        if tx.concept and not self.include_concepts:
            self.removed["concept"] += 1
        amount = (tx.credit or Decimal(0)) - (tx.debit or Decimal(0))
        return Transaction(
            index=i,
            date=tx.date,
            posting_date=tx.posting_date,
            value_date=tx.value_date,
            description=description,
            type=tx.type,
            debit=q(tx.debit),
            credit=q(tx.credit),
            amount=q(amount),
            balance=q(tx.balance),
            balance_operation=q(tx.balance_operation),
            counterparty_ref=counterparty_ref,
            counterparty_account_ref=account_ref,
            counterparty_bank=self.scrub(tx.counterparty_bank),
            merchant=self.scrub(tx.merchant),
            concept=self.scrub(tx.concept) if self.include_concepts else None,
            original_currency=tx.original_currency,
            original_amount=q(tx.original_amount),
            exchange_rate=tx.exchange_rate,
            installment_number=tx.installment_number,
            installments_total=tx.installments_total,
            card_type=tx.card_type,
            page=tx.page,
        )

    def _plan(self, plan: dict) -> InstallmentPlan:
        data = {k: (q(v) if k in _PLAN_MONEY else v) for k, v in plan.items()}
        data["description"] = self.scrub(plan.get("description")) or "[SIN DESCRIPCION]"
        return InstallmentPlan(**data)

    def build(self, file_name: str, sha256: str, validation: Validation) -> Statement:
        raw = self.raw
        strict = self.profile == "strict"
        acct = raw.header.account_number
        account = Account(
            account_ref=self.pseudo.token("ACC", acct) if acct else None,
            account_last4=None if strict or not acct else acct[-4:],
            holder_type=raw.holder_type,
        )
        if acct:
            self.pseudonymized["account"] += 1
            self.masked["account_number"] += 1
        transactions = [self._transaction(i, tx) for i, tx in enumerate(raw.transactions)]
        s = raw.summary
        return Statement(
            schema_version=SCHEMA_VERSION,
            source=Source(
                file_name=None if strict else file_name,
                file_sha256=None if strict else sha256,
                pages=raw.pages,
                tool_version=__version__,
            ),
            document=Document(
                bank=raw.bank,
                bank_name=raw.bank_name,
                product=raw.product,
                product_name=raw.product_name,
                layout_version=raw.layout_version,
                detection_confidence=round(raw.confidence, 2),
                currency=raw.currency,
            ),
            account=account,
            period=Period(start=raw.period_start, end=raw.period_end, statement_date=raw.statement_date, days=raw.days),
            summary=Summary(**{k: (q(v) if not isinstance(v, int) else v) for k, v in s.items() if v is not None}),
            rates=Rates(**{k: v for k, v in raw.rates.items() if v is not None}),
            credit=Credit(**{k: (q(v) if k in _CREDIT_MONEY else v) for k, v in raw.credit.items() if v is not None})
            if raw.product == "credit" else None,
            installment_plans=[self._plan(p) for p in raw.installment_plans],
            transactions=transactions,
            validation=validation,
            privacy=Privacy(
                profile=self.profile,
                pseudonym_scope=self.pseudo.scope,
                include_concepts=self.include_concepts,
                removed={k: v for k, v in sorted(self.removed.items()) if v},
                masked=dict(sorted(self.masked.items())),
                pseudonymized=dict(sorted(self.pseudonymized.items())),
                residual_scan="passed",
            ),
        )
