"""Orquestación: PDF → parser → validación → redacción → escaneo residual → dict JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import BankNotRecognized, LowConfidence, ResidualPII, Unbalanced, UsageError
from .loader import LoadedDocument, load_pdf
from .parsers import PARSERS, THRESHOLD, detect
from .parsers.base import BankParser
from .privacy.pseudonym import Pseudonymizer
from .privacy.redactor import Redactor
from .privacy.residual_scan import scan
from .validate.reconcile import validate


@dataclass
class Options:
    profile: str = "standard"
    password: str | None = None
    bank: str | None = None
    include_concepts: bool = False
    allow_low_confidence: bool = False
    fail_on_unbalanced: bool = False


def _choose(doc: LoadedDocument, opts: Options) -> tuple[BankParser, float]:
    if opts.bank:
        # un banco puede tener varios productos: se elige el de mejor huella
        scored = [(p, p.fingerprint(doc)) for p in PARSERS if p.bank == opts.bank]
        if not scored:
            raise UsageError(f"Banco no soportado: {opts.bank}. Vea `mxbank banks`.", doc.file_name)
        return max(scored, key=lambda s: s[1])
    candidates = detect(doc)
    if not candidates:
        raise BankNotRecognized("No se reconoció el banco del estado de cuenta.", doc.file_name)
    parser, score = candidates[0]
    if score < THRESHOLD and not opts.allow_low_confidence:
        raise LowConfidence(
            f"Confianza de detección {score:.2f} por debajo de {THRESHOLD}. Use --bank o --allow-low-confidence.",
            doc.file_name,
        )
    return parser, score


def detect_file(path: Path, password: str | None = None) -> dict:
    doc = load_pdf(path, password)
    candidates = [{**p.describe(), "confidence": score} for p, score in detect(doc)]
    selected = candidates[0] if candidates and candidates[0]["confidence"] >= THRESHOLD else None
    return {"ok": True, "file": doc.file_name, "pages": len(doc.pages), "selected": selected, "candidates": candidates}


def extract_file(path: Path, opts: Options, pseudo: Pseudonymizer | None = None) -> dict:
    doc = load_pdf(path, opts.password)
    parser, score = _choose(doc, opts)
    raw = parser.parse(doc, score)
    validation = validate(raw)
    redactor = Redactor(raw, opts.profile, pseudo or Pseudonymizer(), opts.include_concepts)

    file_name = doc.file_name
    if scan({"file_name": file_name}, redactor.dictionary):
        file_name = None  # el nombre del archivo contiene datos personales
        validation.warnings.append("Se omitió file_name porque parece contener datos personales.")
    data = redactor.build(file_name, doc.sha256, validation).model_dump(mode="json")

    findings = scan(data, redactor.dictionary)
    if findings:
        raise ResidualPII(
            "Se detectó posible información personal en la salida; no se emitió nada.",
            doc.file_name,
            details=findings,
        )
    if opts.fail_on_unbalanced and data["validation"]["reconciled"] is not True:
        raise Unbalanced("La conciliación contable no cuadra.", doc.file_name)
    return data
