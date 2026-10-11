"""Contrato de parser por banco y utilidades comunes (ver docs/02 §5)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from decimal import Decimal

from ..loader import Line, LoadedDocument, Page, Word
from ..models.raw import RawStatement
from ..normalize.amounts import INT_RE, is_amount, parse_amount, parse_number
from ..text import norm


class BankParser(ABC):
    bank: str
    bank_name: str
    product: str
    layout_version: str

    @abstractmethod
    def fingerprint(self, doc: LoadedDocument) -> float:
        """Confianza 0..1 de que el documento corresponde a este parser."""

    @abstractmethod
    def parse(self, doc: LoadedDocument, confidence: float) -> RawStatement:
        ...

    def describe(self) -> dict[str, str]:
        return {
            "bank": self.bank,
            "bank_name": self.bank_name,
            "product": self.product,
            "layout_version": self.layout_version,
        }


# -- utilidades ---------------------------------------------------------------

def search(lines: list[Line], pattern: str) -> re.Match | None:
    """Primer match de ``pattern`` sobre el texto normalizado de los renglones."""
    rx = re.compile(pattern)
    for line in lines:
        m = rx.search(line.ntext)
        if m:
            return m
    return None


def all_lines(doc: LoadedDocument) -> list[Line]:
    return [line for page in doc.pages for line in page.lines]


def amounts(words: list[Word]) -> list[tuple[Word, Decimal]]:
    out = []
    for w in words:
        if is_amount(w.text):
            value = parse_amount(w.text)
            if value is not None:
                out.append((w, value))
    return out


def numbers(words: list[Word]) -> list[Decimal]:
    return [n for n in (parse_number(w.text) for w in words) if n is not None]


def ints(words: list[Word]) -> list[int]:
    return [int(w.text) for w in words if INT_RE.match(w.text)]


def label_text(words: list[Word]) -> str:
    """Texto normalizado de un renglón sin los números (para identificar la etiqueta)."""
    return norm(" ".join(w.text for w in words if not re.search(r"\d", w.text)))


class Columns:
    """Asigna montos alineados a la derecha a una columna según su borde derecho (x1).

    Una columna empieza donde empieza el texto de su encabezado; un monto pertenece a
    la última columna cuyo encabezado empieza antes de su borde derecho.
    """

    def __init__(self, starts: dict[str, float], margin: float = 5.0):
        self.starts = sorted(starts.items(), key=lambda kv: kv[1])
        self.margin = margin

    def assign(self, word: Word) -> str | None:
        name = None
        for col, x in self.starts:
            if x < word.x1 - self.margin:
                name = col
        return name


def page_lines_after(page: Page, top: float) -> list[Line]:
    return [line for line in page.lines if line.top > top]
