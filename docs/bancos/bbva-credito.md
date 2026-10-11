# BBVA México · Tarjeta de crédito — layout observado

Fuente: 4 PDFs reales de meses consecutivos (9–10 páginas), analizados **solo** mediante volcados de `tools/layout_dump.py` (dígitos siempre enmascarados; letras visibles solo en renglones que inician con fecha) revisados por el titular, y diagnósticos que imprimen únicamente booleanos.
Ningún valor real aparece aquí.

## 1. Estructura

| Página | Contenido |
|---|---|
| 1 | Publicidad y pie legal |
| 2 | Encabezado del titular, pago requerido, resumen de cargos y abonos, CAT, saldos y límite |
| 3 | Tarjetas adicionales, programa de puntos, saldo sobre el que se calcularon intereses, distribución del último pago |
| 4–6 | Compras a meses sin intereses (MSI) y movimientos regulares |
| 7–8 | Notas aclaratorias y glosario; detalle del programa de beneficios |
| 9–10 | CFDI |

El layout es **estable en los 4 meses**; solo cambia el número de páginas de movimientos.

Huellas: pie `BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE`, `TU PAGO REQUERIDO ESTE PERIODO`, `PAGO PARA NO GENERAR INTERESES`, `Tarjeta titular:`. La cuenta de débito BBVA no tiene estas tres últimas, así que la detección distingue ambos productos.

## 2. Página 2 · Encabezado (zona de PII)

Bloque izquierdo (x≈20):

| Renglón | Forma | Clase |
|---|---|---|
| Nombre del titular | 3 palabras | eliminar |
| `Calle:`, `Colonia:`, municipio/estado, `CP:` | 4–5 renglones | eliminar |
| `TARJETA <PRODUCTO> BBVA (<TIPO>)` | texto del banco | conservar como `product_name` |
| `Número de tarjeta:` | **16 dígitos completos** | eliminar |
| `Número de cliente:` | 8 dígitos **pegados a la etiqueta** | eliminar |
| `R.F.C:` | 13 caracteres | eliminar |
| `CLABE:` | 18 dígitos | eliminar |
| `Sucursal:` | nombre y número | eliminar |

Bloque derecho: `Periodo: DD-mmm-AAAA al DD-mmm-AAAA` (mes en minúsculas), `Fecha de corte:`, `Número de días en el periodo N días`, `Fecha límite de pago:` (la fecha va **en el renglón de arriba**, con día de la semana), `Pago para no generar intereses:`, `Pago mínimo + compras y cargo diferidos a meses:`, `Pago mínimo:`. Varias etiquetas llevan **notas al pie como dígitos sueltos** en fuente ~5 pt que no son montos.

Páginas 3+ repiten `Número de cuenta: XXXXXX` + 4 dígitos; las secciones de movimientos traen `Tarjeta titular: XXXXXXXXXXXX` + 4 dígitos. El CFDI trae `Crédito` (10 dígitos, número de cuenta estable entre meses), `No. de Cliente`, `Nombre del Receptor`, código postal, folio fiscal, certificados y sellos.

## 3. Resumen y saldos

Izquierda (`RESUMEN DE CARGOS Y ABONOS DEL PERIODO`): `Adeudo del periodo anterior`, `Cargos regulares (no a meses)`, `Cargos compras a meses`, `Monto de intereses`, `Monto de comisiones`, `IVA de intereses y comisiones`, `Pagos y abonos`, `PAGO PARA NO GENERAR INTERESES`.

Derecha: costo anual (intereses y comisiones de 12 meses), `CAT:` y `TASA DE INTERES ANUAL ORDINARIA` con los porcentajes en el **renglón siguiente** (`99.9% Sin IVA`, `99.99%`), `Saldo cargos regulares`, `Saldo cargo a meses`, `Saldo deudor total`, `Límite de crédito`, `Crédito disponible`.

## 4. Meses sin intereses

`COMPRAS Y CARGOS DIFERIDOS A MESES SIN INTERESES` · columnas: fecha de operación, descripción, monto original, saldo pendiente, pago requerido, `N de M`, tasa → `installment_plans[]`.

## 5. Movimientos regulares

`CARGOS,COMPRAS Y ABONOS REGULARES(NO A MESES)` (repetido en cada página) · columnas: fecha de operación (`DD-mmm-AAAA`), fecha de cargo, descripción, signo (`+` cargo / `-` abono) y monto. Termina con `TOTAL CARGOS` / `TOTAL ABONOS` (mayúsculas o minúsculas según el mes).

Renglones adicionales debajo de un movimiento:

- `USD $99.99 TIPO DE CAMBIO $99.99` → `original_currency`, `original_amount`, `exchange_rate`. La moneda puede venir como código numérico ISO 4217 (`978` = EUR) o como `MXP` (código antiguo del peso, comercios extranjeros que cobran en pesos); se normaliza.
- Desglose de un pago: `IVA : $ … Interes: $ … Comisiones:$… Capital:$…` → no se emite.

Descripciones:

| Forma | `type` |
|---|---|
| `<COMERCIO> [<SUCURSAL/CIUDAD>]` | `card_purchase` (cargo) / `refund` (abono) |
| `… ; Tarjeta Digital ***9999` | se elimina el sufijo; `card_type = "digital"` |
| `NN DE MM <descripción>` | `installment` (parcialidad de una compra a meses) |
| `BMOVIL.PAGO TDC` | `card_payment` |
| `USO DE PUNTOS <comercio>` | `rewards_redemption` |
| `ABONO FINANC. COMPRAS NNMSI`, `ALTA PARA MESES S/INTERESES`, `ABONO POR TRASP. A PROMOC.` | `installment_conversion` |
| `CONTRATACION BENEFICIOS NMSI` (comisión del banco: su monto = `Monto de comisiones` del resumen) | `fee` |
| `COMISION EST SERV PUBL`, `COM …` (comisión que cobra un establecimiento, p. ej. por pagar un servicio) | `fee` (el banco la cuenta en **cargos regulares**, no en comisiones) |
| `COMISION …` | `fee` |

Las descripciones de comercio se emiten tal cual (criterio del proyecto: los movimientos son útiles para finanzas personales), pasando por el diccionario del documento: si contienen palabras del nombre o domicilio del titular (p. ej. la colonia en el nombre de una sucursal) se reemplazan por `[DATO]`.

## 6. Reglas contables verificadas (4/4 estados)

1. **Resumen**: adeudo anterior + cargos regulares + cargos a meses + intereses + comisiones + IVA − pagos y abonos = pago para no generar intereses = saldo de cargos regulares.
2. **Movimientos**: adeudo anterior + Σ cargos − Σ abonos + intereses + IVA = saldo de cargos regulares, **excluyendo los cargos `ALTA PARA MESES`** (son informativos: van al saldo a meses; su contraparte en regulares es `ABONO FINANC.`). Las comisiones sí aparecen como movimiento; intereses e IVA solo en el resumen.
3. **Totales**: `TOTAL ABONOS` = Σ abonos = pagos y abonos del resumen; `TOTAL CARGOS` = Σ cargos − comisiones (**BBVA no incluye las comisiones en ese total**).
4. Σ compras + Σ movimientos `fee` − comisiones del banco = cargos regulares del resumen; Σ parcialidades = cargos a meses.
5. Saldo cargos regulares + saldo a meses = saldo deudor total; límite − saldo deudor total = crédito disponible; Σ saldo pendiente de los planes = saldo a meses.

## 7. Pendientes

- No hubo tarjetas adicionales con movimientos; si aparecen, su sección (`Tarjeta adicional:`) puede traer el nombre del adicional → se trata como dato personal.
- No hubo meses con intereses ni disposiciones de efectivo con movimientos.
