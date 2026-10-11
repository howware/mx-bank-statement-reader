"""CLI ``mxbank``: JSON en stdout, diagnósticos en stderr, sin prompts (ver docs/02 §3)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from . import SCHEMA_VERSION, __version__
from .errors import MxBankError, ResidualPII, UsageError
from .models.statement import Statement
from .parsers import PARSERS
from .pipeline import Options, detect_file, extract_file
from .privacy import detectors
from .privacy.pseudonym import Pseudonymizer
from .privacy.redactor import PROFILES
from .privacy.residual_scan import scan
from .text import norm

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Lee estados de cuenta bancarios mexicanos (PDF) y emite JSON sin datos personales. "
    "Todo se procesa localmente.",
)


def _emit(obj, pretty: bool, out: Path | None = None) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None)
    if out:
        out.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")


def _pdfs(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        files += sorted(p.glob("*.pdf")) if p.is_dir() else [p]
    return files


def _password(env: str | None, use_stdin: bool) -> str | None:
    if use_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    if env:
        value = os.environ.get(env)
        if value is None:
            raise UsageError(f"La variable de entorno {env} no está definida.")
        return value
    return None


def _run(files: list[Path], fn, pretty: bool, ndjson: bool, out: Path | None) -> None:
    results, exit_code = [], 0
    for f in _pdfs(files):
        try:
            results.append(fn(f))
        except MxBankError as exc:
            if not exc.file:
                exc.file = f.name
            results.append(exc.to_dict())
            exit_code = exit_code or exc.exit_code
            print(f"error: {f.name}: {exc.code}", file=sys.stderr)
    if not results:
        _emit(UsageError("No se encontraron archivos PDF.").to_dict(), pretty, out)
        raise typer.Exit(2)
    if ndjson:
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in results)
        (out.write_text(text + "\n", encoding="utf-8") if out else sys.stdout.write(text + "\n"))
    else:
        _emit(results[0] if len(results) == 1 else results, pretty, out)
    raise typer.Exit(exit_code)


@app.command()
def extract(
    files: Annotated[list[Path], typer.Argument(help="PDFs o directorios con PDFs")],
    out: Annotated[Path | None, typer.Option(help="Archivo de salida (default: stdout)")] = None,
    bank: Annotated[str | None, typer.Option(help="Forzar banco (omite detección)")] = None,
    privacy: Annotated[str, typer.Option(help="Perfil: minimal | standard | strict")] = "standard",
    include_concepts: Annotated[bool, typer.Option(help="Incluir conceptos libres (redactados) de transferencias")] = False,
    pseudonym_key_env: Annotated[str | None, typer.Option(help="Variable de entorno con la llave HMAC para seudónimos estables")] = None,
    password_env: Annotated[str | None, typer.Option(help="Variable de entorno con la contraseña del PDF")] = None,
    password_stdin: Annotated[bool, typer.Option(help="Leer la contraseña del PDF de stdin")] = False,
    fail_on_unbalanced: Annotated[bool, typer.Option(help="Salir con código 30 si no cuadra la conciliación")] = False,
    allow_low_confidence: Annotated[bool, typer.Option(help="Permitir detección con confianza baja")] = False,
    pretty: Annotated[bool, typer.Option(help="JSON indentado")] = False,
    ndjson: Annotated[bool, typer.Option(help="Un objeto JSON por línea")] = False,
) -> None:
    """Extrae el estado de cuenta y emite JSON anonimizado (schema v1)."""
    try:
        if privacy not in PROFILES:
            raise UsageError(f"Perfil inválido: {privacy}. Opciones: {', '.join(PROFILES)}.")
        key_env = os.environ.get(pseudonym_key_env) if pseudonym_key_env else None
        if pseudonym_key_env and not key_env:
            raise UsageError(f"La variable de entorno {pseudonym_key_env} no está definida.")
        opts = Options(
            profile=privacy, password=_password(password_env, password_stdin), bank=bank,
            include_concepts=include_concepts, allow_low_confidence=allow_low_confidence,
            fail_on_unbalanced=fail_on_unbalanced,
        )
    except MxBankError as exc:
        _emit(exc.to_dict(), pretty, out)
        raise typer.Exit(exc.exit_code) from None
    # una sola llave por ejecución: los seudónimos coinciden entre los archivos del lote
    pseudo = Pseudonymizer(key_env.encode() if key_env else None)
    if not key_env and (ndjson or len(files) > 1 or any(f.is_dir() for f in files)):
        print(
            "aviso: sin --pseudonym-key-env, statement_id, transactions[].id, installment_plans[].id y los "
            "seudónimos solo son válidos dentro de esta ejecución; para importar o comparar entre ejecuciones "
            "usa siempre la misma llave.",
            file=sys.stderr,
        )
    _run(files, lambda f: extract_file(f, opts, pseudo), pretty or sys.stdout.isatty(), ndjson, out)


@app.command()
def detect(
    files: Annotated[list[Path], typer.Argument(help="PDFs o directorios con PDFs")],
    password_env: Annotated[str | None, typer.Option(help="Variable de entorno con la contraseña del PDF")] = None,
    pretty: Annotated[bool, typer.Option(help="JSON indentado")] = False,
) -> None:
    """Identifica banco, producto y versión de layout sin extraer movimientos."""
    try:
        password = _password(password_env, False)
    except MxBankError as exc:
        _emit(exc.to_dict(), pretty)
        raise typer.Exit(exc.exit_code) from None
    _run(files, lambda f: detect_file(f, password), pretty or sys.stdout.isatty(), False, None)


@app.command()
def audit(
    source: Annotated[str, typer.Argument(help="Archivo JSON/texto a revisar, o - para stdin")],
    pretty: Annotated[bool, typer.Option(help="JSON indentado")] = False,
) -> None:
    """Busca PII residual (CLABE, tarjeta, RFC, CURP, correo, números largos) antes de enviar algo a una IA."""
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    try:
        findings = scan(json.loads(text))
    except json.JSONDecodeError:
        findings = [
            {"line": i, "kind": h.kind}
            for i, line in enumerate(text.splitlines(), start=1)
            for h in detectors.find(norm(line), long_numbers=True)
        ]
    _emit({"ok": not findings, "findings": findings}, pretty or sys.stdout.isatty())
    raise typer.Exit(ResidualPII.exit_code if findings else 0)


@app.command()
def schema(pretty: Annotated[bool, typer.Option(help="JSON indentado")] = True) -> None:
    """Imprime el JSON Schema de la salida de `extract`."""
    _emit(Statement.model_json_schema(mode="serialization"), pretty)


@app.command()
def banks(pretty: Annotated[bool, typer.Option(help="JSON indentado")] = False) -> None:
    """Lista bancos, productos y versiones de layout soportados."""
    _emit({"banks": [p.describe() for p in PARSERS]}, pretty or sys.stdout.isatty())


@app.command()
def version() -> None:
    """Versión de la herramienta y del schema."""
    _emit({"tool_version": __version__, "schema_version": SCHEMA_VERSION}, False)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    app()


if __name__ == "__main__":
    main()
