"""Normalización de texto común a parsers y redacción."""

from __future__ import annotations

import re
import unicodedata

_SPACES = re.compile(r"\s+")


def clean(text: str) -> str:
    """Corrige caracteres problemáticos de los PDFs sin cambiar mayúsculas ni acentos."""
    # BanCoppel usa el guion suave (U+00AD) como signo menos
    return _SPACES.sub(" ", text.replace("­", "-")).strip()


def norm(text: str) -> str:
    """Mayúsculas, sin acentos, espacios colapsados. Base de toda comparación."""
    t = unicodedata.normalize("NFKD", clean(text))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.upper()
