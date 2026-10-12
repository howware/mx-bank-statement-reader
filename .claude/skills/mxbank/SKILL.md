---
name: mxbank
description: Analiza estados de cuenta bancarios mexicanos en PDF (BBVA débito y tarjeta de crédito, BanCoppel débito) sin exponer datos personales, usando la CLI mxbank, que entrega un JSON anonimizado. Úsalo cuando el usuario pida revisar, resumir, graficar o comparar gastos, ingresos, pagos, intereses, meses sin intereses o cargos recurrentes a partir de un estado de cuenta o de un JSON de mxbank.
---

# mxbank: análisis de estados de cuenta sin datos personales

`mxbank` lee el PDF localmente y entrega un JSON sin nombre, domicilio, RFC, tarjeta, CLABE ni datos de terceros. **Trabaja solo con ese JSON.**

## Reglas (no negociables)

1. **Nunca abras, leas, extraigas texto ni subas el PDF original**, ni con herramientas de lectura de archivos ni con librerías de PDF. Solo `mxbank extract`.
2. Revisa el **código de salida** antes de usar el resultado. Con `0`, el JSON es seguro. Con cualquier otro, stdout trae `{"ok": false, "error": {...}}`: explica el error al usuario y no intentes leer el PDF por otra vía.
3. **No intentes identificar** seudónimos (`ACC_…`, `PERSONA_…`, `CUENTA_…`) ni reconstruir datos marcados como `[DATO]` o `[NUM]`.
4. Los **resúmenes y gráficas con datos reales** se muestran en la conversación o se guardan en un archivo local que el usuario elija, dentro de una carpeta ignorada por git. **No los publiques** (páginas compartibles, gists, servicios externos) sin que el usuario lo pida explícitamente.
5. Si `validation.reconciled` no es `true`, avisa que las cifras pueden estar incompletas.

## Invocar la herramienta

```bash
mxbank version                          # ¿está instalada?
mxbank extract estado.pdf               # un estado → un objeto JSON
mxbank extract carpeta/ --ndjson        # varios → un JSON por línea
mxbank detect estado.pdf                # solo banco y producto
mxbank schema                           # JSON Schema completo
mxbank records estado.json --by person:x # registros comunes para una memoria compartida (docs/AGENT.md)
```

Si `mxbank` no está en el PATH: `uv tool install git+https://github.com/howware/mx-bank-statement-reader` (pide permiso antes de instalar), o desde un clon del repo: `uv run --project <ruta-del-repo> mxbank …`.

- **PDF con contraseña** (código 11): pide al usuario que la ponga en una variable de entorno y usa `--password-env NOMBRE`. Nunca la pases como argumento ni la escribas en la conversación.
- **Varios meses o importación**: usa **siempre la misma llave** (`--pseudonym-key-env NOMBRE`) para que la misma cuenta, contraparte, movimiento y plan a meses tengan el mismo alias e id en todas las ejecuciones. Sin llave, la CLI avisa en stderr y los ids no sirven fuera de esa ejecución.
- `--include-concepts` agrega los conceptos de transferencias (redactados); úsalo solo si el usuario lo pide.

| Código | Significado / qué hacer |
|---|---|
| 0 | Éxito |
| 10 | Archivo inexistente o no es PDF |
| 11 | Falta contraseña o es incorrecta |
| 12 | PDF escaneado; aún no hay OCR |
| 20 / 21 | Banco no soportado o detección dudosa (`mxbank banks`) |
| 40 | Posible PII en la salida: **no se emitió nada**. `error.details` dice el campo, nunca el valor. Repórtalo como bug |

## Leer el JSON

- `transactions[].amount`: **negativo = salida de dinero**, positivo = entrada. `debit`/`credit` traen el monto en positivo.
- `document.product`: `debit` (cuenta) o `credit` (tarjeta). Las reglas de análisis cambian según el producto.
- `credit` (tarjetas): `no_interest_payment` (pago para no generar intereses), `minimum_payment`, `payment_due_date`, `credit_limit`, `available_credit`, `interest_charged`, `vat_on_interest_and_fees`, `cat_percent`.
- `installment_plans[]`: compras a meses con `pending_balance` y `installment_number`/`installments_total`.
- `original_currency` / `original_amount` / `exchange_rate`: compras en otra moneda.
- `merchant`: nombre canónico cuando el comercio es conocido; si no, usa `description`.
- `statement_id`, `transactions[].id`, `installment_plans[].id` (schema 1.1): identificadores HMAC estables.
  - **Para no duplicar** al combinar estados que se enciman o reimportados, agrupa o deduplica por `transactions[].id`, nunca por fecha + monto: dos compras idénticas el mismo día tienen ids distintos y ambas son reales.
  - Sigue una compra a meses entre estados con `installment_plans[].id`.
  - Los ids solo son comparables si `privacy.pseudonym_scope == "key"` y se usó la misma llave; con `"run"` no los guardes ni los compares entre ejecuciones.
  - No intentes deducir nada de un id: no contiene datos.

## Cómo calcular bien (lecciones de estados reales)

**Gasto de consumo en tarjeta de crédito** = movimientos `type == "card_purchase"`. No sumes:
- `card_payment`: es el pago que tú haces a la tarjeta, no un gasto.
- `installment_conversion`: "ALTA PARA MESES" y "ABONO FINANC." son un traslado del saldo a meses que se compensa entre sí; no es consumo nuevo.
- `installment`: parcialidades de compras de meses anteriores. Repórtalas aparte.
- `rewards_redemption`: uso de puntos, que es un abono.

Los intereses y su IVA vienen en `credit.interest_charged` y `credit.vat_on_interest_and_fees`, no como movimientos. Las comisiones sí aparecen como movimientos `fee`, de dos tipos:
- **del banco** (p. ej. "CONTRATACION BENEFICIOS"): su suma es `credit.fees_charged`;
- **de terceros** (p. ej. "COMISION EST SERV PUBL", lo que cobra un establecimiento por pagar un servicio): el banco las cuenta dentro de los cargos regulares, como una compra.

**Cuenta de débito.** Los pagos a la tarjeta de crédito (`card_payment`) son transferencias entre tus productos, no consumo: el gasto real está en el estado de la tarjeta. Agrupa así:
- efectivo: `cash_withdrawal`;
- transferencias: `transfer_out` y `spei_out`;
- préstamos: `loan_payment`;
- impuestos: `tax_payment`.

"RETIRO EN CAJERO DE OTRO BANCO (INCLUYE COMISION E IVA)" es un retiro: si el retiro fue en múltiplos de $100, la comisión estimada es `monto % 100`.

**Categorías semánticas** (supermercado, streaming, gasolina…): mxbank no las asigna; clasifícalas tú por `merchant`/`description` y deja una categoría "Otros" para lo que no reconozcas con certeza. No inventes qué es un comercio desconocido.

**Cargos recurrentes**: compara varios meses, cada uno de un estado distinto.
- Un servicio que cobra cerca de la fecha de corte puede aparecer **dos veces en un periodo y ninguna en otro**: cuenta un cargo por mes.
- Montos que varían poco mes a mes en moneda extranjera son el mismo servicio afectado por el tipo de cambio.
- Distingue fijos, por uso (varios cargos chicos al mes) y únicos (renovaciones anuales).

**Verifica tus sumas antes de presentar resultados** (reglas comprobadas con estados reales):
- Tarjeta: Σ `card_purchase` + Σ `fee` − `credit.fees_charged` = `credit.regular_charges`.
- Tarjeta: Σ `installment` = `credit.installment_charges`.
- Débito: Σ de salidas (`amount < 0`) = `summary.total_debits`, y Σ de entradas = `summary.total_credits` (en BanCoppel ese total no incluye los movimientos `interest`).

Si no coincide, revisa tu clasificación; no ajustes cifras para que cuadren.

## Presentar resultados

- Empieza por las cifras clave (entradas, salidas, neto; o compras, intereses, pago para no generar intereses y fecha límite).
- Ofrece el desglose por categoría y señala lo accionable: intereses pagados, comisiones evitables, servicios duplicados, aumentos de precio.
- Si haces una gráfica, usa barras horizontales ordenadas para comparar categorías, con montos visibles, y guárdala como archivo local (regla 4).
- Marca claramente qué es dato y qué es estimación.
