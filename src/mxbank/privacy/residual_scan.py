"""Capa 6: escaneo del JSON final antes de emitirlo (fail-closed)."""

from __future__ import annotations

import re
from typing import Any

from ..text import norm
from . import detectors
from .redactor import Dictionary

# Campos que no son texto del documento y pueden contener secuencias largas de dígitos.
SAFE_KEYS = frozenset({"file_sha256"})
# Identificadores HMAC: se eximen solo si el campo se llama así Y el valor tiene el formato exacto.
# 16 hex normalmente; más largo solo si hubo una colisión dentro de la ejecución (Pseudonymizer.ident).
ID_KEYS = frozenset({"id", "statement_id"})
ID_VALUE = re.compile(r"^(TX|ST|PLAN)_[0-9a-f]{16,64}$")
# Valores tipados que el modelo genera (fechas ISO, montos): no contienen texto del documento.
TYPED_VALUE = re.compile(r"^(?:\d{4}-\d{2}-\d{2}|-?\d+\.\d+)$")


def scan(data: Any, dictionary: Dictionary | None = None, path: str = "") -> list[dict[str, str]]:
    """Devuelve ``[{"path", "kind"}]``. Nunca incluye el valor encontrado."""
    findings: list[dict[str, str]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in SAFE_KEYS or (k in ID_KEYS and isinstance(v, str) and ID_VALUE.match(v)):
                continue
            findings += scan(v, dictionary, f"{path}.{k}" if path else k)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            findings += scan(v, dictionary, f"{path}[{i}]")
    elif isinstance(data, str) and not TYPED_VALUE.match(data):
        n = norm(data)
        kinds = {h.kind for h in detectors.find(n, long_numbers=True)}
        if dictionary is not None and dictionary.find(n):
            kinds.add("DICCIONARIO")
        findings += [{"path": path, "kind": k} for k in sorted(kinds)]
    return findings
