# 03 · Esquema de salida JSON (schema 1.1)

El JSON Schema formal se genera desde los modelos Pydantic (`src/mxbank/models/statement.py`) y se obtiene con `mxbank schema`; **ese es la referencia autoritativa**. Este documento describe la forma y la semántica.

> Schema 1.0 (v0.1.0), además de lo que muestra el ejemplo: `transactions[].balance_operation`, `value_date`, `counterparty_account_ref`, `concept` (solo con `--include-concepts`); `summary.minimum_average_balance`, `fees_vat`; bloque `rates`; `validation.running_balance_checked`, `bank_totals_match`; `privacy.include_concepts`. También `credit` e `installment_plans` (con `start_date` en lugar de `date`) y en movimientos `original_currency`, `original_amount`, `exchange_rate`, `installment_number`, `installments_total`, `card_type`. Pendiente: `fees[]`.

> **Schema 1.1** (cambio aditivo): `statement_id` en la raíz, `transactions[].id` e `installment_plans[].id`. Ver §7.

## 1. Principios

- **Allowlist**: solo existen en la salida los campos definidos aquí. Cualquier campo nuevo requiere revisión de privacidad.
- Montos como **string decimal** (`"1234.56"`) para no perder precisión.
- Fechas ISO‑8601 (`YYYY-MM-DD`).
- `null` significa "no presente en el documento"; nunca se rellenan valores inventados.
- Nombres de campos en inglés `snake_case` (convención estable para herramientas); textos de descripción en el idioma original del banco.

## 2. Ejemplo (cuenta de débito)

```json
{
  "schema_version": "1.1",
  "ok": true,
  "statement_id": "ST_5c0e9a41d27b8f36",
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
      "id": "TX_8d41f0b27c9e3a65",
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
      "id": "TX_f20c6b9e41a7d385",
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
    "id": "PLAN_3e7a90c5b1f4d268",
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
| `statement_id`, `transactions[].id`, `installment_plans[].id` | Identificadores estables (HMAC), §7 | No contienen ni dejan derivar la cuenta, montos ni descripciones sin la llave. |
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

## 7. Identificadores estables (schema 1.1)

Sirven para que un importador (p. ej. una base de datos personal de solo agregado) pueda **reimportar** un estado o importar **estados que se enciman** sin duplicar nada: basta con insertar solo los `id` que aún no tiene.

| Campo | Formato | Entradas del HMAC | Igual cuando… |
|---|---|---|---|
| `statement_id` (raíz) | `ST_<16 hex>` | banco, producto, número de cuenta, inicio y fin del periodo | es el mismo estado de cuenta (mismo periodo de la misma cuenta), aunque sea otro PDF o se descargue de nuevo |
| `transactions[].id` | `TX_<16 hex>` | banco, producto, número de cuenta, `date`, `amount`, descripción **cruda** del banco normalizada (`text.norm`), ordinal de ocurrencia | es el mismo movimiento, aunque aparezca en dos estados que se enciman o en otra posición/página |
| `installment_plans[].id` | `PLAN_<16 hex>` | banco, producto, número de cuenta, descripción cruda normalizada, `start_date`, `original_amount`, ordinal de ocurrencia | es la misma compra a meses, en todos los estados donde aparezca (cambian la parcialidad y el saldo, el id no) |

Reglas:

- **Estables solo con llave**: con `--pseudonym-key-env` (`privacy.pseudonym_scope: "key"`) y siempre la misma llave, los ids son iguales entre ejecuciones, PDFs y perfiles. **Sin llave** (`"run"`) la llave es aleatoria y los ids solo valen dentro de esa ejecución; la CLI lo advierte en stderr al procesar varios archivos o usar `--ndjson`.
- **No dependen** de `--privacy`, `--include-concepts`, `index`, `page`, el orden de extracción, `type`, `merchant` ni del texto redactado: se calculan con los datos crudos antes de redactar.
- **Duplicados legítimos** (dos compras idénticas el mismo día): el ordinal de ocurrencia (0, 1, …) entre movimientos con la misma fecha, monto y descripción **dentro del mismo estado** los distingue. Si un estado que se encima trae solo una de dos compras idénticas, se le asigna el ordinal 0.
- **Sin periodo** (el parser no lo encontró), `statement_id` se calcula con el hash del PDF: solo es estable para ese archivo exacto.
- **Sin número de cuenta**, los ids no distinguen entre cuentas distintas; la salida lo avisa en `validation.warnings`.
- Formato: 16 hex (64 bits). Si dos ids chocaran dentro de una ejecución con datos distintos, el hash se alarga de 2 en 2.
- El HMAC usa un separador de dominio versionado (`mxbank-id/v1`): si algún día cambian las entradas, cambiará el prefijo de dominio y se documentará como cambio de esquema.
