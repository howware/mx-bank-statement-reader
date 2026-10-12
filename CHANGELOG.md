# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).
El esquema JSON de salida tiene su propia versión (`schema_version`).

## [0.2.0] - 2026-10-10

Esquema de salida **1.1** (cambio aditivo; los consumidores de 1.0 siguen funcionando).

### Añadido

- `statement_id` (raíz), `transactions[].id` e `installment_plans[].id`: identificadores estables calculados con HMAC-SHA256 y la llave de seudónimos, para importar o reimportar estados (incluso estados que se enciman) sin duplicar movimientos ni planes a meses.
  - Con `--pseudonym-key-env` son iguales entre ejecuciones, PDFs y perfiles de privacidad; sin llave solo valen dentro de la ejecución, y la CLI lo advierte en stderr al procesar varios archivos o con `--ndjson`.
  - Dos movimientos idénticos el mismo día se distinguen con un ordinal de ocurrencia dentro del estado.
  - El escáner residual exime solo esos campos y solo con su formato exacto.
- Documentación de cómo se calculan y cuándo son estables (docs/03 §7, docs/04), y cómo usarlos para no duplicar (docs/AGENT.md, skill `mxbank`).

## [0.1.0] - 2026-10-10

Primera versión pública. Esquema de salida **1.0**.

### Añadido

- CLI `mxbank` con los comandos `extract`, `detect`, `audit`, `schema`, `banks` y `version`: JSON en stdout, diagnósticos en stderr, errores en JSON y códigos de salida estables.
- Parsers:
  - **BBVA México · cuenta de débito** (layout 2024.1).
  - **BBVA México · tarjeta de crédito** (layout 2025.1): bloque `credit`, planes a meses sin intereses, compras en moneda extranjera y parcialidades.
  - **BanCoppel · cuenta de débito** (layout 2025.1).
- Privacidad:
  - El encabezado (nombre, domicilio, RFC, CURP, cuentas, tarjeta, CLABE, cliente, sucursal) nunca llega a la salida.
  - Diccionario del documento: palabras del nombre y domicilio del titular se reemplazan en cualquier texto.
  - Detectores validados de CLABE (dígito verificador), tarjeta (Luhn), RFC, CURP y correo.
  - Seudónimos HMAC para contrapartes y cuentas, estables entre ejecuciones con `--pseudonym-key-env`.
  - Escáner residual **fail-closed**: si detecta PII en la salida, no emite nada (código 40).
  - Perfiles `minimal`, `standard` y `strict`; conceptos libres solo con `--include-concepts`.
- Validación contable: conciliación de saldos, totales reportados por el banco y saldo por movimiento.
- Herramientas de desarrollo: volcado enmascarado de layouts (`tools/layout_dump.py`), métricas sobre PDFs reales sin exponer contenido (`tools/corpus_check.py`) y guardia de git contra PDFs y datos personales (`tools/check_no_pii.py`).
- PDFs sintéticos con datos ficticios para las pruebas.

[0.2.0]: https://github.com/howware/mx-bank-statement-reader/releases/tag/v0.2.0
[0.1.0]: https://github.com/howware/mx-bank-statement-reader/releases/tag/v0.1.0
