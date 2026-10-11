"""Registro de parsers y detección de banco (ver docs/02 §4)."""

from __future__ import annotations

from ..loader import LoadedDocument
from .bancoppel_debit import BanCoppelDebitParser
from .base import BankParser
from .bbva_credit import BBVACreditParser
from .bbva_debit import BBVADebitParser

PARSERS: list[BankParser] = [BBVADebitParser(), BBVACreditParser(), BanCoppelDebitParser()]
THRESHOLD = 0.8


def detect(doc: LoadedDocument) -> list[tuple[BankParser, float]]:
    scored = [(p, p.fingerprint(doc)) for p in PARSERS]
    return sorted((s for s in scored if s[1] > 0), key=lambda s: s[1], reverse=True)

