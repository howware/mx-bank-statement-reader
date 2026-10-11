"""Detectores de PII con validación (ver docs/04 §4).

Compartidos por el redactor, el escáner residual, ``mxbank audit`` y la guardia de git.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CLABE_RE = re.compile(r"(?<!\d)(\d{3})[ -]?(\d{3})[ -]?(\d{11})[ -]?(\d)(?!\d)")
PAN_RE = re.compile(r"(?<!\d)(?:\d[ -]?){14,15}\d(?!\d)")
RFC_RE = re.compile(r"\b([A-ZÑ&]{3,4})[ -]?(\d{2})(\d{2})(\d{2})[ -]?([A-Z0-9]{3})\b")
CURP_RE = re.compile(r"\b[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d\b")
# el dominio debe terminar en letras: evita falsos positivos como "paquete@1.2.3"
EMAIL_RE = re.compile(r"\b[\w.+-]+@((?:[\w-]+\.)+[A-Za-z]{2,})\b")
LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{10,}(?!\d)")

ALLOWED_EMAIL_DOMAINS = frozenset({"example.com", "example.org", "anthropic.com"})


@dataclass(frozen=True)
class Hit:
    kind: str
    start: int
    end: int
    value: str


def clabe_ok(digits: str) -> bool:
    weights = (3, 7, 1)
    total = sum(int(d) * weights[i % 3] % 10 for i, d in enumerate(digits[:17]))
    return (10 - total % 10) % 10 == int(digits[17])


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _date_ok(mm: str, dd: str) -> bool:
    return 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31


def find(text: str, long_numbers: bool = False) -> list[Hit]:
    """Todas las coincidencias validadas en ``text``.

    ``long_numbers`` agrega cualquier secuencia de 10+ dígitos (cuentas, teléfonos,
    referencias): útil sobre la salida, demasiado agresivo para la guardia de git.
    """
    hits: list[Hit] = []
    for m in CLABE_RE.finditer(text):
        if clabe_ok("".join(m.groups())):
            hits.append(Hit("CLABE", m.start(), m.end(), m.group(0)))
    for m in PAN_RE.finditer(text):
        if luhn_ok(re.sub(r"\D", "", m.group(0))):
            hits.append(Hit("TARJETA", m.start(), m.end(), m.group(0)))
    for m in RFC_RE.finditer(text):
        if _date_ok(m.group(3), m.group(4)):
            hits.append(Hit("RFC", m.start(), m.end(), m.group(0)))
    for m in CURP_RE.finditer(text):
        hits.append(Hit("CURP", m.start(), m.end(), m.group(0)))
    for m in EMAIL_RE.finditer(text):
        if m.group(1).lower() not in ALLOWED_EMAIL_DOMAINS:
            hits.append(Hit("EMAIL", m.start(), m.end(), m.group(0)))
    if long_numbers:
        for m in LONG_NUMBER_RE.finditer(text):
            hits.append(Hit("NUMERO_LARGO", m.start(), m.end(), m.group(0)))
    return hits
