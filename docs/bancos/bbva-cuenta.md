# BBVA México · Cuenta de débito (Tarjeta Nómina Básica) — layout observado

Fuente: 4 PDFs reales de meses distintos (7 páginas cada uno), analizados **solo** mediante el volcado enmascarado de `tools/layout_dump.py`.
Todos los ejemplos usan la forma enmascarada (`9` = dígito, `X/x` = letra). Ningún valor real aparece aquí.

> El encabezado dice `TARJETA NOMINA BASICA BBVA`: es una **cuenta de depósito con tarjeta de débito** (saldo anterior / abonos / cargos / saldo final, saldo promedio, GAT, ISR retenido). No tiene fecha límite de pago, pago mínimo ni CAT, que son propios de una tarjeta de crédito.
>
> Fuentes: volcado enmascarado + volcado con la primera línea de cada movimiento y el glosario visibles (dígitos siempre enmascarados), ambos revisados por el titular.

## 1. Datos técnicos

| Elemento | Valor |
|---|---|
| Tamaño de página | 612 × 792 pt (carta) |
| Texto | Embebido (no requiere OCR); sin contraseña |
| Páginas | 7: 1–3 movimientos, 4 resumen gráfico, 5 avisos legales, 6 glosario, 7 CFDI |
| Fuentes | Tamaños 10 (cuerpo), 9.5/8.5 (detalle de movimiento), 12 (títulos) |
| Glifos sin mapeo | Página 7 contiene texto `(cid:NNN)` tamaño 5 (probable código QR/barras como fuente) → ignorar |

## 2. Huellas para detección

- Pie de cada página: `BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE, GRUPO FINANCIERO BBVA MEXICO` + domicilio y RFC institucional del banco (dato público; debe estar en la allowlist del escáner de PII).
- Encabezado de cada página: `Estado de Cuenta` / `TARJETA <PRODUCTO> BBVA` (p. ej. `TARJETA NOMINA BASICA BBVA`) / `PAGINA n / m`.
- Títulos: `Información Financiera … MONEDA NACIONAL`, `Detalle de Movimientos Realizados`, `Total de Movimientos`, `Glosario de Abreviaturas`.
- Encabezado de tabla: `FECHA OPER LIQ DESCRIPCION REFERENCIA CARGOS ABONOS SALDO OPERACION LIQUIDACION`.

## 3. Página 1 · Encabezado (zona de PII)

Columna izquierda (x≈41): **nombre del titular** (1 línea) y **domicilio** (4–5 líneas, termina en `<MUNICIPIO> MEXICO CP 99999`).

Columna derecha (x≈318 etiqueta, valor alineado a la derecha ≈ x 500–590):

| Etiqueta | Forma del valor | Clase |
|---|---|---|
| `Periodo DEL … AL …` | `99/99/9999` ×2 | conservar |
| `Fecha de Corte` | `99/99/9999` | conservar |
| `No. de Cuenta` | 10 dígitos | enmascarar / token |
| `No. de Cliente` | 8 dígitos | eliminar |
| `R.F.C` | `XXXX999999XX9` (persona física) | eliminar |
| `No. Cuenta CLABE` | `999 999 99999999999 9` (**con espacios**) | eliminar |
| `SUCURSAL:` | número + nombre | eliminar |
| `DIRECCION:` | domicilio de sucursal (2 líneas) | eliminar |
| `PLAZA:` | nombre | eliminar |
| `TELEFONO:` | 7 dígitos (sucursal) | eliminar |

Páginas 2–7 repiten `No. de Cuenta` y `No. de Cliente` en el encabezado → el diccionario del documento debe tomarlos de la página 1 y buscarlos en todas.

## 4. Página 1 · Información financiera

Dos columnas de pares etiqueta/valor (izquierda x≈11 valor x≈256–278; derecha x≈308 valor x≈537–565):

- Izquierda: `Saldo Promedio`, `Días del Periodo`, `Tasa Bruta Anual %`, `Saldo Promedio Gravable`, `Intereses a Favor (+)`, `ISR Retenido (-)`, `Comisiones` (sub‑renglones con conteo y monto, p. ej. cheques, manejo de cuenta), `Total Comisiones`, `Cargos Objetados` (conteo, monto), `Abonos Objetados` (conteo, monto).
- Derecha: `Saldo Anterior`, `Depósitos / Abonos (+)` (conteo + monto), `Retiros / Cargos (-)` (conteo + monto), `Saldo Final`, `Saldo Promedio Mínimo Mensual`.
- Tabla GAT (`GAT Nominal`, `GAT Real`, `Total de comisiones`, `Tasa de interés anual`) con valores `N/A` en este documento.

## 5. Detalle de movimientos (páginas 1–3)

Columnas (x del encabezado → borde de los valores):

| Columna | x encabezado | Valores |
|---|---|---|
| Fecha operación (`OPER`) | 21 | `99/MES` (x≈15) — sin año, se infiere del periodo |
| Fecha liquidación (`LIQ`) | 70 | `99/MES` (x≈59) |
| Descripción | 105 | x≈106–107, multilínea |
| Referencia | 321 | `Referencia 9999999999` o `Referencia ******9999` en renglón de detalle |
| Cargos | 381 | alineado a la derecha, termina ≈ x 420 |
| Abonos | 427 | alineado a la derecha, termina ≈ x 465 |
| Saldo operación | 469 | ≈ x 475–520 (no en todos los renglones) |
| Saldo liquidación | 536 | ≈ x 557–600 (no en todos los renglones) |

Reglas observadas:

1. **Inicio de movimiento** = renglón que empieza con dos fechas `99/MES 99/MES`.
2. El **monto puede estar 2 pt más abajo** que la descripción y en otra fuente (8.5) → agrupar renglones con tolerancia de ~3 pt, no por `top` exacto.
3. A veces la primera línea solo trae las fechas y la descripción va en el renglón siguiente.
4. Asignar cargo/abono/saldos por **borde derecho (x1)** del número, no por x0.
5. Los saldos solo aparecen en el último movimiento de cada día (no es saldo corrido por renglón).
6. Fin de la tabla: título `Total de Movimientos` con `TOTAL IMPORTE CARGOS`, `TOTAL IMPORTE ABONOS`, `TOTAL MOVIMIENTOS CARGOS/ABONOS` (conteos) → **sirve para validar** suma y conteo.

### Tipos de descripción vistos

La primera línea es texto generado por el banco. `<BANCO>` = banco de la contraparte.

| Primera línea | `type` propuesto | Líneas de detalle (forma) | PII en el detalle |
|---|---|---|---|
| `SPEI RECIBIDO<BANCO>` (**sin espacio** entre `RECIBIDO` y el banco) | `spei_in` | `9999999`; `Referencia 9999999999 999` | Ordenante/concepto (en otros casos) |
| `SPEI ENVIADO <BANCO>` (el banco puede tener varias palabras) | `spei_out` | `9999999<Concepto> 99 Mes 9999`; 20 dígitos; `XXXX` + 20 dígitos (clave de rastreo); **nombre del beneficiario** | Sí: nombre, concepto libre, clave de rastreo |
| `SPEI DEVUELTO<BANCO>` (sin espacio) | `spei_refund` (abono) | `9999999<concepto>`; `Referencia 9999999999 999` | Concepto libre |
| `PAGO CUENTA DE TERCERO` | `transfer_out` | `BNET 9999999999 <concepto libre>` | Sí: **cuenta de 10 dígitos de la contraparte**, concepto libre |
| `PAGO TARJETA DE CREDITO` | `card_payment` | `CUENTA: XXXX` | Referencia a la tarjeta |
| `PAGO DE PRESTAMO` | `loan_payment` | `TOTAL DE XXXXXX` | No |
| `RETIRO CAJERO AUTOMATICO` | `cash_withdrawal` | `MES99 99:99 BBVA X999 FOLIO:9999` | No |
| `RETIRO SIN TARJETA` | `cash_withdrawal` | `Referencia ******9999` | No |
| `RET CAJ OTRO BCO COM IVA` (retiro en cajero de otro banco; **el monto incluye el retiro + comisión + IVA**, p. ej. 3,000 + 32.40) | `cash_withdrawal` | `MES99 99:99 XXX X99999 FOLIO:9999` | No |
| `SU PAGO EN EFECTIVO` | `cash_deposit` | `EN <CORRESPONSAL>` | No |
| `<COMERCIO><SUCURSAL> <CIUDAD> CASH` (p. ej. retiro/depósito en OXXO) | `cash_withdrawal` / `card_purchase` | `RFC: XXX 9999999X9 99:99 AUT: 999999` | **RFC del comercio**; sucursal y ciudad (cuasi‑identificadores) |
| `9999999999DISPOS.EFECTIVO` (10 dígitos pegados) | `cash_withdrawal` | `XXXX X99` | **Los 10 dígitos pueden ser un teléfono** (retiro por celular) → eliminar |
| `SAT` | `tax_payment` | `CIE:` / `XXX:` referencias de convenio | Referencias |
| `RECARGAS Y PAQUETES BMOV` | `mobile_topup` | `99/MES 99:99 AUT:` | No |

Glosario relevante para normalizar (de la página 6): `RET`=retiro, `CAJ`=cajero, `BCO`=banco, `COM`=comisión, `BMOV`=BBVA México (app), `CIE`=concentración inmediata empresarial, `CW`=cash windows, `TDC`/`TDE`=tarjeta de crédito/débito, `TPV`=terminal punto de venta, `SBC`=salvo buen cobro, `DEV`/`DEVOL`=devolución, `REV`=reverso, `TRASP`=traspaso, `CGO`=cargo, `DEP`=depósito, `INT`=intereses.

Implicaciones para el parser/redactor:

- La **primera línea** es texto del banco → se conserva (normalizada) y alimenta `type`. Hay que separar palabras pegadas (`RECIBIDO<BANCO>`, `<COMERCIO><SUCURSAL>`).
- En compras/retiros en comercio, conservar solo el comercio normalizado (`OXXO`); **sucursal y ciudad se eliminan** porque revelan dónde vive o se mueve el titular.
- Las **líneas de detalle** se tratan como texto libre de alto riesgo: se extraen campos conocidos (referencia, rastreo, cuenta de contraparte, nombre) con patrones por tipo, y el resto pasa por redacción.
- El RFC puede venir **separado por espacio** (`XXX 9999999X9`) → el detector de RFC debe tolerar espacios.
- La CLABE puede venir **separada por espacios** (`999 999 99999999999 9`) en el encabezado **y en el texto legal de la página 5**.

## 6. Página 4 · Cuadro resumen

`Saldo Inicial`, `Depósitos / Abonos (+)`, `Comisiones (-)`, `Intereses a favor (+)`, `Retiros efectivo (-)`, `Otros cargos (-)`, `Saldo Final`, cada uno con monto y porcentaje → segunda fuente para validar el resumen de la página 1.

## 7. Páginas 5–7

- **5 Avisos legales**: contiene la CLABE del titular dentro del texto → nunca emitir texto libre de esta página.
- **6 Glosario de abreviaturas**: tabla de 4 pares de columnas (x 13/69, 188/259, 397/457) abreviatura → significado. Útil para normalizar descripciones (cargar como diccionario estático en el parser, no desde el PDF).
- **7 CFDI**: `Nombre del Receptor` (**nombre del titular otra vez**), `Código Postal de Domicilio Fiscal`, `Régimen Fiscal`, `Uso de CFDI`, `Folio Fiscal` (UUID), número de certificado (20 dígitos), `Sello Digital`, `Sello SAT`, cadena original, lugar y fecha de emisión → **todo se descarta**; como mucho se conserva la fecha de emisión.

## 8. Mapeo a la salida JSON v1

| Origen | Campo JSON |
|---|---|
| Periodo DEL/AL, Fecha de Corte | `period.start`, `period.end`, `period.statement_date` |
| Días del Periodo | `period.days` |
| Saldo Anterior / Abonos / Cargos / Saldo Final | `summary.opening_balance`, `total_credits`, `total_debits`, `closing_balance` (+ conteos) |
| Saldo Promedio, Saldo Promedio Mínimo Mensual | `summary.average_balance`, `summary.minimum_average_balance` *(campo nuevo)* |
| Intereses a Favor, ISR Retenido, Total Comisiones | `summary.interest_earned`, `tax_withheld`, `fees_total` |
| Tasa Bruta Anual, GAT | `account.rates` *(bloque nuevo, opcional)* |
| Movimiento | `transactions[]` con `date` = operación, `posting_date` = liquidación, `balance` = saldo liquidación cuando exista, `balance_operation` *(nuevo)* |
| Total de Movimientos | `validation` (suma y conteo de cargos/abonos) |

## 9. Estabilidad entre meses

Los 4 estados (meses consecutivos) tienen **el mismo layout**: 7 páginas, mismas coordenadas de columnas, mismos títulos y huellas. Lo único que varía es la posición vertical de `Total de Movimientos` según el número de movimientos (puede caer en la página 1, 2 o 3) y la cantidad de renglones.

Observaciones adicionales:

- ~1 de cada 4 movimientos trae un renglón **solo con fechas**; la descripción está en el renglón siguiente (confirmado en los 4 estados).
- El parser debe tolerar que un movimiento y sus líneas de detalle queden partidos entre páginas (no observado aún en BBVA, sí en BanCoppel).

## 10. Pendientes

- Aún no hay ejemplos de compras con tarjeta en comercio (`card_purchase`) ni de SPEI recibido con nombre de ordenante en el detalle.
- Analizar un estado de cuenta de **tarjeta de crédito** BBVA real, que tiene otro layout.
