"""Volcado de layout ENMASCARADO de un PDF de estado de cuenta.

Sirve para estudiar la estructura de un banco (posiciones, columnas, secciones,
formatos de fecha/monto) sin exponer datos personales:

- Todos los dígitos se convierten en ``9`` (``1,234.56`` -> ``9,999.99``).
- Toda palabra que no esté en el vocabulario bancario permitido se reemplaza
  por su forma (``Juan`` -> ``Xxxx``).
- Solo se imprimen metadatos técnicos (Producer/Creator) y también enmascarados.

Opciones de revelado (las letras se muestran, los dígitos SIEMPRE se enmascaran):
- ``--reveal-tx-first-line``: primera línea de descripción de cada movimiento
  (renglón que inicia con fecha ``99/MES`` o ``99/99``; si solo trae fechas, el siguiente).
- ``--reveal-pages 6,7``: páginas completas (p. ej. un glosario).

Uso:
    python tools/layout_dump.py <pdf> --out <archivo.txt> [--password-env VAR]
        [--reveal-tx-first-line] [--reveal-pages N[,N...]]

La salida debe revisarla una persona antes de compartirla.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

import pdfplumber

from mxbank.privacy.vocab import COMMON_WORDS

# Vocabulario permitido: términos bancarios genéricos (compartido con el redactor).
VOCAB = COMMON_WORDS

EDGE_PUNCT = ".,:;()[]{}$%*-/\"'¿?¡!#+=<>|"


def _norm(token: str) -> str:
    t = unicodedata.normalize("NFKD", token)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.upper().strip(EDGE_PUNCT)


# fecha de movimiento al inicio del renglón: 05/AGO, 05/09, 05-sep-2026, 05/09/2026
TX_DATE = re.compile(r"^\d{1,2}[/-](?:[A-Za-z]{3}\.?|\d{2})(?:[/-]\d{2,4})?$")


def mask_token(token: str, reveal: bool = False) -> str:
    """Enmascara un token. Con ``reveal`` conserva letras pero nunca dígitos."""
    if reveal:
        return "".join("9" if ch.isdigit() else ch for ch in token)
    # fechas/compuestos como 10-SEP-2026 o 05/ENE: enmascarar cada segmento
    for sep in ("-", "/"):
        if sep in token.strip(sep):
            return sep.join(mask_token(part) if part else part for part in token.split(sep))
    core = _norm(token)
    if core and not any(ch.isdigit() for ch in core) and (core in VOCAB or core.rstrip(".") in VOCAB):
        return token
    out = []
    for ch in token:
        if ch.isdigit():
            out.append("9")
        elif ch.isalpha():
            out.append("X" if ch.isupper() else "x")
        else:
            out.append(ch)
    return "".join(out)


def mask_text(text: str) -> str:
    return " ".join(mask_token(t) for t in text.split())


def dump(
    pdf_path: Path,
    password: str | None,
    reveal_tx_first_line: bool = False,
    reveal_pages: frozenset[int] = frozenset(),
) -> list[str]:
    lines: list[str] = []
    with pdfplumber.open(pdf_path, password=password or "") as pdf:
        meta = pdf.metadata or {}
        lines.append(f"# pages: {len(pdf.pages)}")
        for key in ("Producer", "Creator"):
            if key in meta:
                lines.append(f"# {key}: {mask_text(str(meta[key]))}")
        for pno, page in enumerate(pdf.pages, start=1):
            lines.append("")
            lines.append(
                f"=== page {pno} ({page.width:.0f}x{page.height:.0f}) "
                f"rects={len(page.rects)} lines={len(page.lines)} images={len(page.images)} ==="
            )
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False, extra_attrs=["size"])
            rows: dict[int, list[dict]] = {}
            for w in words:
                rows.setdefault(round(w["top"] / 2) * 2, []).append(w)
            reveal_next = False
            for top in sorted(rows):
                ws = sorted(rows[top], key=lambda w: w["x0"])
                size = max(w["size"] for w in ws)
                reveal = pno in reveal_pages or reveal_next
                reveal_next = False
                if reveal_tx_first_line and TX_DATE.match(ws[0]["text"]):
                    reveal = True
                    # renglón solo con fechas: la descripción viene en el siguiente
                    reveal_next = all(TX_DATE.match(w["text"]) for w in ws)
                cells = "  ".join(f"{w['x0']:.0f}:{mask_token(w['text'], reveal)}" for w in ws)
                lines.append(f"{top:5d} s{size:4.1f} | {cells}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="archivo de salida (no se imprime a stdout)")
    ap.add_argument("--password-env", help="variable de entorno con la contraseña del PDF")
    ap.add_argument("--reveal-tx-first-line", action="store_true", help="mostrar letras de la 1a línea de cada movimiento")
    ap.add_argument("--reveal-pages", default="", help="páginas a mostrar con letras, p. ej. 6,7")
    args = ap.parse_args(argv)

    password = os.environ.get(args.password_env) if args.password_env else None
    reveal_pages = frozenset(int(p) for p in args.reveal_pages.split(",") if p.strip())
    try:
        lines = dump(args.pdf, password, args.reveal_tx_first_line, reveal_pages)
    except Exception as exc:  # no imprimir contenido del PDF en errores
        print(f"error: {type(exc).__name__}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ok: {len(lines)} líneas escritas en {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
