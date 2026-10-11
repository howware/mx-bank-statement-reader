# BanCoppel · Cuenta de débito digital — layout observado

Fuente: 1 PDF real (6 páginas), analizado **solo** mediante volcados de `tools/layout_dump.py` (enmascarado y con la primera línea de cada movimiento visible; dígitos siempre enmascarados), revisados por el titular.
Todos los ejemplos usan la forma enmascarada (`9` = dígito, `X/x` = letra). Ningún valor real aparece aquí.

## 1. Datos técnicos

| Elemento | Valor |
|---|---|
| Tamaño de página | 612 × 792 pt (carta) |
| Texto | Embebido; sin contraseña |
| Páginas | 6: 1–3 movimientos, 4 resumen e intereses, 5 avisos legales, 6 CFDI |
| Fuente | Tamaño 10 en casi todo; 6–7 en el CFDI |
| **Texto duplicado** | El pie publicitario aparece con cada palabra **dos veces en la misma posición** (texto dibujado doble para simular negritas) → usar `page.dedupe_chars()` de pdfplumber antes de extraer |
| **Signo menos** | Se usa `U+00AD` (guion suave, `­`) en lugar de `-` en el resumen, la GAT y el UUID → el normalizador debe tratar `U+00AD` como menos/guion |

## 2. Huellas para detección

- Esquina superior derecha de cada página: `Hoja n de m`.
- Página 1: `ESTADO DE CUENTA` / `CUENTA <PRODUCTO> DIGITAL`.
- Títulos: `Detalle de Movimientos`, `Resumen de la Cuenta`, `Movimientos en proceso de aclaración del periodo anterior`.
- Texto legal y CFDI: `BanCoppel, S. A., Institución de Banca Múltiple` (emisor del CFDI con RFC institucional de 12 caracteres, dato público).
- Pie publicitario sobre la tarjeta de débito BanCoppel en todas las páginas.

## 3. Página 1 · Encabezado (zona de PII)

Bloque izquierdo (x≈31, y≈96–146): **nombre del titular** (renglón de fuente 8) y **domicilio** (3–4 renglones, termina en `<CIUDAD> <ESTADO> C.P.99999`).

| Etiqueta | Forma del valor | Clase |
|---|---|---|
| `Sucursal:` | `9999 , <domicilio de sucursal>, Tel.` | eliminar |
| `<Ejecutivo>:` | nombre de persona (3 palabras) | eliminar (**dato de tercero**) |
| `No. de cliente:` | 9 dígitos | eliminar |
| `Número de Cuenta:` | 11 dígitos | enmascarar / token |
| `CLABE:` | 18 dígitos **sin espacios** | eliminar |
| `Domicilio Fiscal:` | código postal (5 dígitos) | eliminar |
| `Régimen Fiscal:`, otros campos fiscales | 2–3 dígitos | eliminar |
| GAT Nominal / GAT Real | `9.99 %` (la real puede ser negativa con `U+00AD`) | conservar |
| `Intereses …`, `Comisiones …` | `$9.99` | conservar |

## 4. Detalle de movimientos (páginas 1–3)

Encabezado del bloque, repetido en cada página: `Período: 99/MES./9999 AL 99/MES./9999 Moneda Nacional $` (mes abreviado **con punto**, p. ej. `ABR.`).

| Columna | x encabezado | Valores |
|---|---|---|
| Fecha | 40 | `99/99` = **MM/DD** (mes primero, sin año; confirmado: los 18 movimientos solo caen en el periodo leídos como MM/DD) |
| Descripción | 178 (valores desde x≈80) | multilínea |
| Retiros | 356 | alineado a la derecha, termina ≈ x 420 |
| Depósitos | 431 | alineado a la derecha, termina ≈ x 500 |
| Saldo | 524 | ≈ x 533, **en todos los movimientos** (saldo corrido) |

Reglas observadas:

1. **Inicio de movimiento** = renglón con fecha `99/99` en x≈41.
2. Montos en el **mismo renglón** que la primera línea de descripción.
3. Las líneas de detalle usan **etiquetas fijas** `ETIQUETA: valor` → extracción por etiqueta, mucho más confiable que en BBVA.
4. Un movimiento puede quedar **partido entre páginas**: sus líneas de detalle continúan después del encabezado repetido de la página siguiente.
5. Como hay saldo en cada renglón, se puede validar movimiento por movimiento (`saldo_anterior ± monto = saldo`).

### Tipos de descripción vistos

| Primera línea | `type` propuesto | Detalle (etiquetas) | PII |
|---|---|---|---|
| `PAGO DE INTERESES` | `interest` | — | No |
| `ABONO SPEI [<clave de rastreo>]` (la clave a veces no viene) | `spei_in` | `BANCO EMISOR:`, `FECHA TRANSFERENCIA:`, `CLABE:` (18 díg.), `ORDENANTE:`, `REF:`, `CONCEPTO:` | **Sí**: nombre y CLABE del ordenante, concepto libre, clave de rastreo |
| `CARGO SPEI <clave de rastreo>` | `spei_out` | `BANCO RECEPTOR:`, `FECHA TRANSFERENCIA:`, `CLABE:` (**16 dígitos = número de tarjeta**), `BENEFICIARIO:` + `(Dato no verificado por esta Institución)`, `REF:`, `CONCEPTO:` | **Sí**: nombre del beneficiario, tarjeta, concepto libre |
| `TRASPASO EN CUENTA 99999999999 <concepto>` | `transfer_out` | continuación del concepto | Número de cuenta destino (11 díg.), **concepto libre en la misma primera línea** |
| `RECARGA DE TIEMPO AIRE A TRAVÉS DE APP` | `mobile_topup` | operador (2 palabras) | No |
| `TRAS. ENTRE CTAS. 99999999999` | `transfer_internal` (abono) | concepto libre (`Xxxx #99 Mes '99`) | Número de cuenta, concepto |

Notas:

- La clave de rastreo SPEI tiene formas muy variadas según el banco ordenante (`XXXX` + 20 díg., `9999XX` + 20 díg., `999XXXX` + 17 díg., 18 dígitos, y en cargos `99999999XXXXXXXX99999999`) → seudonimizar todo el token que sigue a `ABONO SPEI` / `CARGO SPEI`.
- **Excepción a "la primera línea es texto del banco"**: en `TRASPASO EN CUENTA` el concepto escrito por el usuario empieza en la primera línea → el parser corta la primera línea después del número de cuenta y el resto va a redacción como texto libre.
- El campo `CLABE:` del detalle puede contener una CLABE (18) **o una tarjeta (16)** → los detectores de CLABE y Luhn se aplican a ambos.
- El nombre del ordenante/beneficiario puede incluir comas y palabras como `DEL` (`XXXXXX XXXXXX,XXXX XXXXXX DEL`) → tomar todo el valor de la etiqueta, no palabras sueltas.
- Algunos `ABONO SPEI` traen solo la primera línea y un identificador largo, sin etiquetas.

## 5. Movimientos en aclaración

Tabla con columnas `Fecha`, `Folio`, `Fecha movimiento`, `Descripción`, `Importe` (vacía en este documento) → mapear a `disputes[]` (bloque nuevo, opcional).

## 6. Página 4 · Resumen e intereses

- `Resumen de la Cuenta`: `Saldo Anterior`, `+ Más Depósitos`, `− Menos Retiros`, `+ Más Intereses del Periodo`, `− Menos Comisiones`, `− Menos IVA Comisiones`, `Saldo Actual`.
- `Cálculo de Intereses`: `Saldo Promedio Mensual`, `Días del Periodo`, `Tasa Bruta Anual`, `Intereses Brutos`, `− Menos Retención`, `Intereses del Periodo`, y una leyenda con un saldo `(Saldo … de $99,999.99)`.

## 7. Páginas 5–6

- **5 Avisos legales**: datos de la UNE del banco (domicilio, correo, teléfono institucionales) → nunca emitir texto libre de esta página; el correo institucional no debe confundirse con PII del titular, pero tampoco se emite.
- **6 CFDI** (`<Comprobante> DE TU ESTADO DE CUENTA`), dos columnas:
  - `EMISOR`: razón social, RFC y domicilio del banco (públicos).
  - `RECEPTOR`: **nombre del titular** (4 palabras), **RFC del titular** (13 caracteres), `Número de Crédito` (= número de cuenta, 11 díg.), **domicilio completo con C.P.**
  - Certificados (20 dígitos), `Folio Fiscal` (UUID con `U+00AD`), método y forma de pago, cuenta de pago (4 díg.), lugar/fecha/hora de emisión y certificación (incluye **C.P. y ciudad**), sellos digitales, cadena original.
  - → **Se descarta todo**.

## 8. Mapeo a la salida JSON v1

| Origen | Campo JSON |
|---|---|
| `Período: … AL …` | `period.start`, `period.end` |
| `Días del Periodo` | `period.days` |
| Resumen de la Cuenta | `summary.opening_balance`, `total_credits`, `total_debits`, `interest_earned`, `fees_total`, `fees_vat` *(nuevo)*, `closing_balance` |
| `Saldo Promedio Mensual` | `summary.average_balance` |
| `Menos Retención` | `summary.tax_withheld` |
| GAT, Tasa Bruta Anual | `account.rates` |
| Movimiento | `transactions[]`; `balance` en todos; `counterparty_ref` desde `ORDENANTE:` / `BENEFICIARIO:`; `counterparty_bank` desde `BANCO EMISOR:` / `BANCO RECEPTOR:`; `value_date` *(nuevo)* desde `FECHA TRANSFERENCIA:` |
| Movimientos en aclaración | `disputes[]` *(nuevo)* |

## 9. Comparación con BBVA

| Aspecto | BBVA | BanCoppel |
|---|---|---|
| Fechas de movimiento | `DD/MES` (operación y liquidación) | `MM/DD` (una sola) |
| Saldo | Solo al final de cada día, dos saldos | En cada movimiento, uno |
| Detalle | Texto posicional sin etiquetas | Etiquetas `CAMPO:` |
| Nombre de contraparte | Renglón suelto sin etiqueta | `ORDENANTE:` / `BENEFICIARIO:` |
| CLABE del titular | Con espacios | Sin espacios |
| Signo negativo | `-` | `U+00AD` |
| Texto duplicado | No | Sí (pie) |

## 10. Pendientes

- Más estados de cuenta BanCoppel (otros meses) para confirmar estabilidad.
