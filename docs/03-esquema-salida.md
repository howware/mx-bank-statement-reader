# 03 · Esquema de salida JSON (v1, borrador)

El JSON Schema formal se genera desde los modelos Pydantic (`src/mxbank/models/statement.py`) y se obtiene con `mxbank schema`; **ese es la referencia autoritativa**. Este documento describe la forma y la semántica.

> Schema 1.0 (v0.1.0), además de lo que muestra el ejemplo: `transactions[].balance_operation`, `value_date`, `counterparty_account_ref`, `concept` (solo con `--include-concepts`); `summary.minimum_average_balance`, `fees_vat`; bloque `rates`; `validation.running_balance_checked`, `bank_totals_match`; `privacy.include_concepts`. También `credit` e `installment_plans` (con `start_date` en lugar de `date`) y en movimientos `original_currency`, `original_amount`, `exchange_rate`, `installment_number`, `installments_total`, `card_type`. Pendiente: `fees[]`.

## 1. Principios

- **Allowlist**: solo existen en la salida los campos definidos aquí. Cualquier campo nuevo requiere revisión de privacidad.
- Montos como **string decimal** (`"1234.56"`) para no perder precisión.
- Fechas ISO‑8601 (`YYYY-MM-DD`).
- `null` significa "no presente en el documento"; nunca se rellenan valores inventados.
- Nombres de campos en inglés `snake_case` (convención estable para herramientas); textos de descripción en el idioma original del banco.

## 2. Ejemplo (cuenta de débito)

```json
{
  "schema_version": "1.0",
  "ok": true,
  "source": {
    "file_name": "estado_2026_09.pdf",
    "file_sha256": "9f2c…",
    "pages": 6,
    "tool_version": "0.1.0"
  },
  "document": {
    "bank": "bbva",
    "bank_name": "BBVA México",
    "product": "debit",
    "product_name": "Libretón Básico",
    "layout_version": "2024.1",
    "detection_confidence": 0.97,
    "currency": "MXN"
  },
  "account": {
    "account_ref": "ACC_3b9e",
    "account_last4": "4821",
    "holder_type": "individual"
  },
  "period": {
    "start": "2026-08-15",
    "end": "2026-09-14",
    "statement_date": "2026-09-14",
    "days": 31
  },
  "summary": {
    "opening_balance": "15230.10",
    "total_credits": "32000.00",
    "total_debits": "28754.33",
    "closing_balance": "18475.77",
    "average_balance": "16890.40",
    "credits_count": 4,
    "debits_count": 37,
    "fees_total": "0.00",
    "interest_earned": "0.00",
    "tax_withheld": "0.00"
  },
  "transactions": [
    {
      "index": 0,
      "date": "2026-08-15",
      "posting_date": "2026-08-15",
      "description": "SPEI RECIBIDO BANORTE PERSONA_7f3a CONCEPTO NOMINA",
      "type": "spei_in",
      "debit": null,
      "credit": "16000.00",
      "amount": "16000.00",
      "balance": "31230.10",
      "counterparty_ref": "PERSONA_7f3a",
      "counterparty_bank": "BANORTE",
      "merchant": null,
      "page": 2
    },
    {
      "index": 1,
      "date": "2026-08-16",
      "posting_date": "2026-08-16",
      "description": "OXXO SUC 1234 CD JUAREZ",
      "type": "card_purchase",
      "debit": "85.50",
      "credit": null,
      "amount": "-85.50",
      "balance": "31144.60",
      "counterparty_ref": null,
      "counterparty_bank": null,
      "merchant": "OXXO",
      "page": 2
    }
  ],
  "fees": [],
  "validation": {
    "reconciled": true,
    "expected_closing_balance": "18475.77",
    "difference": "0.00",
    "running_balance_errors": 0,
    "warnings": []
  },
  "privacy": {
    "profile": "standard",
    "pseudonym_scope": "run",
    "removed": {
      "holder_name": 1,
      "address": 1,
      "rfc": 2,
      "clabe": 1,
      "account_number": 3,
      "client_number": 1,
      "fiscal_uuid": 1
    },
    "masked": { "card_number": 0 },
    "pseudonymized": { "counterparty": 6, "tracking_key": 9 },
    "residual_scan": "passed"
  }
}
```

## 3. Bloques adicionales para tarjeta de crédito (`product: "credit"`)

```json
"credit": {
  "credit_limit": "45000.00",
  "available_credit": "12340.00",
  "cut_off_date": "2026-09-10",
  "payment_due_date": "2026-09-30",
  "minimum_payment": "1520.00",
  "no_interest_payment": "21780.55",
  "previous_balance": "18900.00",
  "purchases": "9870.20",
  "payments_and_credits": "-7000.00",
  "interest_charged": "0.00",
  "fees_charged": "0.00",
  "vat_on_interest_and_fees": "0.00",
  "cat_percent": "78.5",
  "annual_interest_rate_percent": "56.0"
},
"installment_plans": [
  {
    "description": "LIVERPOOL MSI",
    "original_amount": "12000.00",
    "monthly_amount": "1000.00",
    "installments_total": 12,
    "installments_paid": 4,
    "remaining_balance": "8000.00",
    "interest_free": true
  }
]
```

## 4. Semántica de campos sensibles

| Campo | Significado | Nota de privacidad |
|---|---|---|
| `account_ref` | Token estable del número de cuenta (HMAC) | Permite a la IA agrupar meses de la misma cuenta sin conocer el número. |
| `account_last4` | Últimos 4 dígitos | Omitido en perfil `strict`. |
| `counterparty_ref` | Token de la contraparte (`PERSONA_xxxx` / `EMPRESA_xxxx`) | Misma contraparte ⇒ mismo token dentro del ámbito (`run` o `key`). |
| `merchant` | Comercio normalizado | Se conserva: es útil y no identifica al titular. |
| `file_sha256` | Hash del PDF | Identifica el archivo, no a la persona. Omitido en `strict`. |
| `file_name` | Nombre base del archivo | Se sanea si contiene PII detectable; omitido en `strict`. |

## 5. Lote / consolidado

- Varios PDFs sin `--consolidate`: un objeto por archivo (`--ndjson`) o un arreglo.
- Con `--consolidate`: `{ "schema_version", "statements": [...], "accounts": [...] }`, ordenado por cuenta y periodo; con `pseudonym_scope` compartido para que los tokens coincidan entre meses.

## 6. Versionado

- `schema_version` sigue SemVer: cambios aditivos ⇒ menor; cambios que rompen ⇒ mayor.
- `mxbank schema --version N` imprime cualquier versión soportada.
