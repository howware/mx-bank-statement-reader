"""Apertura del PDF y extracción de palabras con coordenadas, agrupadas en renglones.

Todo ocurre en memoria; nada de lo extraído se escribe a disco.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from .errors import FileNotFound, MxBankError, NotAPdf, NoText, PasswordRequired
from .text import clean, norm

# Diferencia vertical máxima (pt) entre palabras consecutivas del mismo renglón.
# BBVA imprime el monto ~2 pt más abajo que la descripción.
ROW_TOLERANCE = 3.0
MAX_BYTES = 50 * 1024 * 1024
MAX_PAGES = 200


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    size: float


@dataclass
class Line:
    page: int
    top: float
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def ntext(self) -> str:
        return norm(self.text)

    def within(self, x_min: float = 0, x_max: float = 10_000) -> list[Word]:
        return [w for w in self.words if x_min <= w.x0 < x_max]

    def text_within(self, x_min: float = 0, x_max: float = 10_000) -> str:
        return " ".join(w.text for w in self.within(x_min, x_max))


@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    def find(self, needle: str) -> Line | None:
        """Primer renglón cuyo texto normalizado contiene ``needle`` (normalizado)."""
        n = norm(needle)
        return next((line for line in self.lines if n in line.ntext), None)


@dataclass
class LoadedDocument:
    file_name: str
    sha256: str
    pages: list[Page]
    producer: str = ""

    @property
    def ntext(self) -> str:
        return norm("\n".join(p.text for p in self.pages))


def _group_lines(page_no: int, words: list[Word]) -> list[Line]:
    lines: list[Line] = []
    last_top = None
    for w in sorted(words, key=lambda w: (w.top, w.x0)):
        if last_top is None or w.top - last_top > ROW_TOLERANCE:
            lines.append(Line(page=page_no, top=w.top, words=[]))
        lines[-1].words.append(w)
        last_top = w.top
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    return lines


def _is_password_error(exc: BaseException) -> bool:
    seen = exc
    while seen is not None:
        if "password" in type(seen).__name__.lower() or "password" in str(seen).lower():
            return True
        seen = seen.__cause__ or seen.__context__
    return False


def load_pdf(path: Path, password: str | None = None) -> LoadedDocument:
    name = path.name
    if not path.is_file():
        raise FileNotFound("No se encontró el archivo.", name)
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise NotAPdf("El archivo excede el tamaño máximo permitido.", name)
    if not data.lstrip()[:5].startswith(b"%PDF"):
        raise NotAPdf("El archivo no es un PDF.", name)

    try:
        pdf = pdfplumber.open(path, password=password or "")
    except Exception as exc:  # pdfplumber envuelve errores de pdfminer
        if _is_password_error(exc):
            raise PasswordRequired(
                "El PDF está protegido. Proporcione la contraseña con --password-env o --password-stdin.", name
            ) from None
        raise NotAPdf("No se pudo abrir el PDF.", name) from None

    pages: list[Page] = []
    with pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise NotAPdf("El PDF excede el número máximo de páginas.", name)
        producer = clean(str((pdf.metadata or {}).get("Producer", "")))
        try:
            for i, p in enumerate(pdf.pages, start=1):
                # BanCoppel dibuja algunos textos dos veces para simular negritas
                p = p.dedupe_chars(tolerance=1)
                raw = p.extract_words(keep_blank_chars=False, use_text_flow=False, extra_attrs=["size"])
                words = [
                    Word(clean(w["text"]), float(w["x0"]), float(w["x1"]), float(w["top"]), float(w["size"]))
                    for w in raw
                    if clean(w["text"])
                ]
                pages.append(Page(i, float(p.width), float(p.height), _group_lines(i, words)))
        except MxBankError:
            raise
        except Exception as exc:
            if _is_password_error(exc):
                raise PasswordRequired("El PDF está protegido o la contraseña es incorrecta.", name) from None
            raise NotAPdf("No se pudo leer el contenido del PDF.", name) from None

    if not any(p.lines for p in pages):
        raise NoText("El PDF no contiene texto; probablemente es un escaneo y requiere OCR.", name)
    return LoadedDocument(name, hashlib.sha256(data).hexdigest(), pages, producer)
