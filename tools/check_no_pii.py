"""Guardia de git: bloquea commits con estados de cuenta o datos personales.

Revisa los archivos en *staged* (o los pasados como argumentos) y falla si:

- Hay PDFs fuera de ``tests/`` o archivos en ``corpus/`` / ``docs/Estados/``.
- El contenido tiene CLABE (dígito verificador válido), número de tarjeta (Luhn),
  RFC, CURP o correos electrónicos.

Los valores ficticios usados en pruebas se declaran en ``.pii-allowlist``.
Nunca imprime el valor encontrado, solo archivo, línea y tipo.

Uso:
    python tools/check_no_pii.py            # archivos en staged
    python tools/check_no_pii.py ARCHIVO... # archivos concretos
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from mxbank.privacy import detectors

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS = ("corpus/", "docs/Estados/")


def find_pii(text: str, allow: set[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        found = [(h.kind, h.value) for h in detectors.find(line)]
        for kind, value in found:
            if value not in allow and re.sub(r"[ -]", "", value) not in allow:
                hits.append((lineno, kind))
    return hits


def _staged() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def _read(path: str, staged: bool) -> bytes:
    if staged:
        return subprocess.run(["git", "show", f":{path}"], cwd=ROOT, capture_output=True, check=True).stdout
    return (ROOT / path).read_bytes()


def main(argv: list[str]) -> int:
    staged = not argv
    paths = _staged() if staged else argv
    allow_file = ROOT / ".pii-allowlist"
    allow = set()
    if allow_file.exists():
        allow = {
            ln.strip() for ln in allow_file.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")
        }

    problems: list[str] = []
    for path in paths:
        norm = path.replace("\\", "/")
        if norm == ".pii-allowlist":
            continue
        if any(norm.startswith(d) for d in FORBIDDEN_DIRS):
            problems.append(f"{norm}: carpeta prohibida (datos reales)")
            continue
        if norm.lower().endswith(".pdf") and not norm.startswith("tests/"):
            problems.append(f"{norm}: PDF fuera de tests/")
            continue
        data = _read(norm, staged)
        if b"\0" in data[:8192]:
            continue  # binario
        text = data.decode("utf-8", errors="replace")
        for lineno, kind in find_pii(text, allow):
            problems.append(f"{norm}:{lineno}: posible {kind}")

    if problems:
        print("check_no_pii: commit bloqueado — posible dato personal:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print("Si es un valor ficticio de prueba, agréguelo a .pii-allowlist.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
