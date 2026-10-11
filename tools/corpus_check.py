"""Corre el pipeline sobre PDFs reales y muestra SOLO métricas (ver docs/02 §9).

No imprime descripciones, nombres ni montos individuales: banco, conteos por tipo,
resultado de la conciliación, campos del resumen que faltan y conteos de redacción.

Uso:
    uv run python tools/corpus_check.py docs/Estados/
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from mxbank.errors import MxBankError
from mxbank.pipeline import Options, extract_file

SUMMARY_FIELDS = ("opening_balance", "closing_balance", "total_credits", "total_debits")
CREDIT_FIELDS = (
    "credit_limit", "available_credit", "cut_off_date", "payment_due_date", "minimum_payment",
    "no_interest_payment", "previous_balance", "regular_balance", "total_balance", "cat_percent",
)


def check(path: Path) -> list[str]:
    try:
        d = extract_file(path, Options())
    except MxBankError as exc:
        out = [f"  ERROR {exc.code}"]
        out += [f"    {f['path']}: {f['kind']}" for f in exc.details or []]
        return out
    v = d["validation"]
    txs = d["transactions"]
    if d["document"]["product"] == "credit":
        missing = [k for k in CREDIT_FIELDS if (d["credit"] or {}).get(k) is None]
    else:
        missing = [k for k in SUMMARY_FIELDS if d["summary"].get(k) is None]
    missing += [k for k in ("start", "end") if d["period"].get(k) is None]
    types = Counter(t["type"] for t in txs)
    no_amount = sum(1 for t in txs if t["debit"] is None and t["credit"] is None)
    return [
        f"  banco={d['document']['bank']} confianza={d['document']['detection_confidence']} paginas={d['source']['pages']}",
        f"  producto={d['document']['product']} movimientos={len(txs)} sin_monto={no_amount} planes_msi={len(d['installment_plans'])}",
        f"  tipos={dict(sorted(types.items()))}",
        f"  conciliado={v['reconciled']} diferencia={v['difference']} totales_banco={v['bank_totals_match']}",
        f"  saldos_revisados={v['running_balance_checked']} saldos_con_error={v['running_balance_errors']}",
        f"  faltan={missing or '-'}",
        f"  avisos={len(v['warnings'])}: {v['warnings'] or '-'}",
        f"  privacidad: removed={d['privacy']['removed']} pseudonymized={d['privacy']['pseudonymized']}",
    ]


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    paths: list[Path] = []
    for a in argv or ["corpus"]:
        p = Path(a)
        paths += sorted(p.glob("*.pdf")) if p.is_dir() else [p]
    for i, p in enumerate(paths, start=1):
        print(f"[{i}] {p.name}")
        print("\n".join(check(p)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
