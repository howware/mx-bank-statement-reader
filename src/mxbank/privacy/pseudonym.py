"""Seudónimos estables con HMAC-SHA256 (ver docs/04 §5)."""

from __future__ import annotations

import hashlib
import hmac
import os

from ..text import norm

ID_SIZE = 16
# separador que no aparece en texto normalizado ni en números: evita ambigüedad entre campos
_SEP = "\x1f"
_ID_DOMAIN = "mxbank-id/v1"


class Pseudonymizer:
    def __init__(self, key: bytes | None = None):
        self.scope = "key" if key else "run"
        self._key = key or os.urandom(32)
        self._by_token: dict[str, str] = {}
        self._by_value: dict[tuple[str, str], str] = {}
        self._ids: dict[str, str] = {}

    def ident(self, prefix: str, *parts: str) -> str:
        """Identificador estable ``PREFIJO_<16 hex>`` = HMAC-SHA256(llave, dominio | prefijo | partes).

        HMAC y no un hash simple: las partes (cuenta, fecha, monto) son adivinables y un hash sin
        llave se podría revertir por fuerza bruta. Mismas partes + misma llave ⇒ mismo id.
        """
        material = _SEP.join((_ID_DOMAIN, prefix, *parts))
        digest = hmac.new(self._key, material.encode(), hashlib.sha256).hexdigest()
        size = ID_SIZE
        ident = f"{prefix}_{digest[:size]}"
        # el hash crece solo si hay colisión dentro de esta ejecución (acotado al digest completo)
        while ident in self._ids and self._ids[ident] != material and size < len(digest):
            size += 2
            ident = f"{prefix}_{digest[:size]}"
        self._ids[ident] = material
        return ident

    def token(self, prefix: str, value: str) -> str:
        nvalue = norm(value)
        cached = self._by_value.get((prefix, nvalue))
        if cached:
            return cached
        digest = hmac.new(self._key, f"{prefix}:{nvalue}".encode(), hashlib.sha256).hexdigest()
        size = 4
        tok = f"{prefix}_{digest[:size]}"
        # el hash crece solo si hay colisión dentro de esta ejecución
        while tok in self._by_token and self._by_token[tok] != nvalue:
            size += 2
            tok = f"{prefix}_{digest[:size]}"
        self._by_token[tok] = nvalue
        self._by_value[(prefix, nvalue)] = tok
        return tok
