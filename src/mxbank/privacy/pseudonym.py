"""Seudónimos estables con HMAC-SHA256 (ver docs/04 §5)."""

from __future__ import annotations

import hashlib
import hmac
import os

from ..text import norm


class Pseudonymizer:
    def __init__(self, key: bytes | None = None):
        self.scope = "key" if key else "run"
        self._key = key or os.urandom(32)
        self._by_token: dict[str, str] = {}
        self._by_value: dict[tuple[str, str], str] = {}

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
