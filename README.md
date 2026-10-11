<h1 align="center">mxbank · Tus estados de cuenta, listos para la IA, sin tus datos personales</h1>

<p align="center">
  <b>Lee estados de cuenta de bancos mexicanos en PDF y entrega un JSON estructurado que no te identifica.</b><br>
  100 % local · cifras conciliadas · hecho para agentes de IA
</p>

<p align="center">
  <a href="https://github.com/proteo5/mx-bank-statement-reader/actions/workflows/ci.yml"><img src="https://github.com/proteo5/mx-bank-statement-reader/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/versión-0.1.0-blue" alt="Versión 0.1.0">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/licencia-Apache%202.0-green" alt="Licencia Apache 2.0">
</p>

<p align="center">
  <a href="https://proteo5.github.io/mx-bank-statement-reader/">Sitio del proyecto</a> ·
  <a href="#instalación">Instalación</a> ·
  <a href="#uso">Uso</a> ·
  <a href="#privacidad">Privacidad</a> ·
  <a href="docs/AGENT.md">Guía para agentes de IA</a>
</p>

Subir un estado de cuenta a un asistente de IA expone tu nombre, domicilio, RFC, número de tarjeta, CLABE y los datos de las personas a las que les transfieres. `mxbank` lee el PDF **en tu computadora**, extrae saldos y movimientos, elimina todo lo que te identifica, valida que las cifras cuadren y solo entonces emite el JSON.

```bash
mxbank extract estado.pdf > estado.json      # este archivo ya se puede compartir con una IA
```

---

## Contenido

- [Características](#características)
- [Bancos soportados](#bancos-soportados)
- [Instalación](#instalación)
- [Uso](#uso)
- [Salida](#salida)
- [Privacidad](#privacidad)
- [Uso con agentes de IA](#uso-con-agentes-de-ia)
- [Desarrollo](#desarrollo)
- [Documentación](#documentación)
- [Hoja de ruta](#hoja-de-ruta)
- [Licencia](#licencia)

## Características

- **100 % local**: sin red, sin telemetría y sin archivos temporales. El PDF nunca sale de tu máquina.
- **Privacidad por diseño**: la salida se construye campo por campo a partir de una lista cerrada. Un escáner final revisa el JSON completo y, si encuentra algo sospechoso, **no emite nada**.
- **Cifras verificadas**: cada estado se concilia contra sus saldos y contra los totales que reporta el propio banco.
- **Hecho para IA**: JSON en stdout, diagnósticos en stderr, errores también en JSON, códigos de salida estables, sin prompts interactivos y [JSON Schema](#salida) publicado.
- **Tarjetas de crédito completas**: pago mínimo, pago para no generar intereses, CAT, meses sin intereses, compras en moneda extranjera y parcialidades.

## Bancos soportados

| Banco | Producto | Layout | Validado con |
|---|---|---|---|
| BBVA México | Cuenta de débito (p. ej. Nómina) | 2024.1 | 4 estados reales: conciliación, totales y saldo por día exactos |
| BBVA México | Tarjeta de crédito | 2025.1 | 4 estados reales: conciliación y totales exactos |
| BanCoppel | Cuenta de débito digital | 2025.1 | 1 estado real: conciliación, totales y saldo por movimiento exactos |

Si un PDF no corresponde a un formato soportado, `mxbank` lo rechaza con el código 20 o 21; nunca intenta adivinar. ¿Quieres otro banco? Lee [cómo agregar uno](#agregar-un-banco).

## Instalación

Requiere Python 3.12+ y [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/proteo5/mx-bank-statement-reader.git
cd mx-bank-statement-reader
uv sync
uv run mxbank --help
```

Para tenerlo disponible como comando global:

```bash
uv tool install .
mxbank --help
```

## Uso

```bash
mxbank extract estado.pdf --pretty                     # un estado de cuenta
mxbank extract carpeta/ --ndjson > movimientos.jsonl   # todos los PDFs de una carpeta
mxbank extract estado.pdf --privacy strict             # sin últimos 4 dígitos ni nombre de archivo
mxbank extract estado.pdf --include-concepts           # incluye conceptos de transferencias (redactados)
mxbank detect estado.pdf                               # solo identifica banco y producto
mxbank audit cualquier_archivo.json                    # busca datos personales antes de compartir algo
mxbank schema                                          # JSON Schema de la salida
mxbank banks                                           # formatos soportados
```

**PDF con contraseña y seudónimos estables entre meses.** Los secretos se pasan por variable de entorno, nunca como argumento, para que no queden en el historial de la terminal:

```bash
export MXBANK_PDF_PASSWORD='...'
export MXBANK_KEY='una-llave-larga-y-privada'
mxbank extract estado.pdf --password-env MXBANK_PDF_PASSWORD --pseudonym-key-env MXBANK_KEY
```

Con la misma llave, la misma cuenta o contraparte recibe el mismo seudónimo (`ACC_…`, `PERSONA_…`) en todos los meses, así puedes agrupar sin revelar quién es.

### Códigos de salida

| Código | Significado |
|---|---|
| 0 | Éxito |
| 2 | Argumentos inválidos |
| 10 | Archivo no encontrado o no es PDF |
| 11 | PDF protegido: falta la contraseña o es incorrecta |
| 12 | El PDF no tiene texto (escaneo; requiere OCR) |
| 20 | Banco no reconocido |
| 21 | Confianza de detección baja |
| 30 | La conciliación no cuadra (solo con `--fail-on-unbalanced`) |
| 40 | **Se detectó posible información personal en la salida; no se emitió nada** |

## Salida

Extracto real generado a partir del PDF **sintético** de las pruebas, con datos ficticios:

```json
{
  "schema_version": "1.0",
  "ok": true,
  "document": { "bank": "bbva", "product": "credit", "product_name": "TARJETA AZUL BBVA (CREDITO)", "currency": "MXN" },
  "account": { "account_ref": "ACC_92d5", "account_last4": "3210", "holder_type": "individual" },
  "period": { "start": "2026-08-15", "end": "2026-09-14", "days": 31 },
  "credit": {
    "credit_limit": "50000.00", "available_credit": "45535.00",
    "cut_off_date": "2026-09-14", "payment_due_date": "2026-10-08",
    "minimum_payment": "900.00", "no_interest_payment": "1965.00", "cat_percent": "75.3"
  },
  "transactions": [
    { "date": "2026-08-18", "description": "AMAZON", "type": "card_purchase", "amount": "-1200.00",
      "merchant": "AMAZON", "card_type": "digital" },
    { "date": "2026-08-20", "description": "NETFLIX", "type": "card_purchase", "amount": "-299.00",
      "original_currency": "USD", "original_amount": "15.00", "exchange_rate": "19.93" },
    { "date": "2026-08-25", "description": "BMOVIL.PAGO TDC", "type": "card_payment", "amount": "13000.00" }
  ],
  "validation": { "reconciled": true, "difference": "0.00", "bank_totals_match": true },
  "privacy": {
    "removed": { "holder_name": 2, "address": 1, "rfc": 1, "card_number": 1, "clabe": 1, "client_number": 1 },
    "residual_scan": "passed"
  }
}
```

- Montos como **texto decimal** (`"1200.00"`), para no perder precisión. `amount` negativo = salida de dinero.
- Fechas ISO-8601. `null` significa que el dato no viene en el documento; nunca se inventa.
- El esquema completo se obtiene con `mxbank schema`; la semántica de cada campo está en [docs/03-esquema-salida.md](docs/03-esquema-salida.md).

## Privacidad

| Dato | Tratamiento |
|---|---|
| Nombre, domicilio, RFC, CURP, número de cliente, sucursal | Se eliminan |
| Número de cuenta / crédito | Seudónimo estable (`ACC_…`) + últimos 4 dígitos (se omiten en `--privacy strict`) |
| Tarjeta completa, CLABE, sufijo `Tarjeta Digital ***1234` | Se eliminan |
| Contrapartes de transferencias (terceros) | Seudónimo (`PERSONA_…`, `CUENTA_…`); nunca el nombre ni la cuenta |
| Claves de rastreo y referencias | Se eliminan |
| Conceptos libres de transferencias | Se omiten; con `--include-concepts` se incluyen redactados |
| Comercio, monto y fecha de cada movimiento | Se conservan: es el propósito de la herramienta |

Cómo se garantiza:

1. **Lista cerrada**: el modelo de salida no tiene campos donde quepa el encabezado del estado de cuenta.
2. **Diccionario del documento**: las palabras del nombre y domicilio del titular se buscan en todo texto emitido. Si aparecen, por ejemplo la colonia en el nombre de una sucursal, se reemplazan por `[DATO]`.
3. **Patrones validados**: CLABE (dígito verificador), tarjeta (Luhn), RFC, CURP, correo y números de 4+ dígitos.
4. **Escáner residual fail-closed**: revisa el JSON final completo; ante la duda sale con el código 40 y no emite nada.

Modelo de amenaza, perfiles y riesgos residuales: [docs/04-privacidad-y-redaccion.md](docs/04-privacidad-y-redaccion.md).

> **Aviso**: `mxbank` reduce drásticamente la información personal que compartes, pero ninguna herramienta automática es infalible. Revisa la salida antes de enviarla a terceros (`mxbank audit` ayuda). No es asesoría legal ni financiera.

## Uso con agentes de IA

`mxbank` está pensado para que un agente lo invoque como herramienta: el agente ejecuta `mxbank extract`, lee el JSON y razona sobre los movimientos sin ver nunca el PDF. Las reglas, los códigos de salida y un ejemplo están en [docs/AGENT.md](docs/AGENT.md), listos para copiarse a las instrucciones de un agente.

### Skill para Claude Code

El repositorio incluye el skill [`mxbank`](.claude/skills/mxbank/SKILL.md). Claude Code lo carga solo cuando le pides revisar, resumir o graficar un estado de cuenta, y con él la sesión sabe:

- usar `mxbank extract` en lugar de abrir el PDF;
- que pagos a la tarjeta y traslados a meses no son gasto;
- cómo detectar cargos recurrentes;
- cómo verificar las sumas contra el banco antes de responder.

- **Dentro de un clon del repositorio** ya está disponible; no hay que hacer nada.
- **Para tenerlo en todas tus sesiones**, instálalo en tu usuario:

  ```bash
  # macOS / Linux
  mkdir -p ~/.claude/skills/mxbank && curl -fsSL https://raw.githubusercontent.com/proteo5/mx-bank-statement-reader/main/.claude/skills/mxbank/SKILL.md -o ~/.claude/skills/mxbank/SKILL.md
  ```

  ```powershell
  # Windows (PowerShell)
  New-Item -ItemType Directory -Force "$HOME\.claude\skills\mxbank" | Out-Null; Invoke-WebRequest https://raw.githubusercontent.com/proteo5/mx-bank-statement-reader/main/.claude/skills/mxbank/SKILL.md -OutFile "$HOME\.claude\skills\mxbank\SKILL.md"
  ```

  Reinicia Claude Code y pide, por ejemplo: *"analiza mis gastos del estado de cuenta `~/estados/tarjeta_sep.pdf`"*. Para actualizar el skill, vuelve a ejecutar el mismo comando.

**Si desarrollas el proyecto con una IA**, las reglas están en [AGENTS.md](AGENTS.md).

## Desarrollo

```bash
uv sync                                       # dependencias, incluidas las de desarrollo
uv run pytest -q                              # pruebas sobre PDFs sintéticos
uvx ruff check src tests tools                # lint
git config core.hooksPath tools/git-hooks     # activa la guardia de commits (obligatorio)
```

### Regla de oro: nunca subir datos reales

- Los estados de cuenta reales van en `corpus/` o `docs/Estados/`, que están ignorados por git.
- La guardia de commits ([tools/check_no_pii.py](tools/check_no_pii.py)) bloquea PDFs, esas carpetas y cualquier CLABE, tarjeta, RFC, CURP o correo. CI la ejecuta sobre todos los archivos del repositorio.
- Las pruebas usan **PDFs sintéticos** ([tests/synthetic/](tests/synthetic/)) que imitan cada layout con datos ficticios; las CLABE y tarjetas de prueba tienen dígito verificador válido para que una fuga se detecte de verdad.
- Los valores ficticios que deben pasar la guardia se declaran en [.pii-allowlist](.pii-allowlist).

### Agregar un banco

1. Estudia el layout **sin exponer datos**: `uv run python tools/layout_dump.py corpus/estado.pdf --out corpus/layout.txt`. El volcado enmascara cada dígito y cada palabra que no sea vocabulario bancario; revísalo antes de compartirlo. `--reveal-tx-first-line` muestra las letras de la primera línea de cada movimiento.
2. Documenta el layout en `docs/bancos/<banco>-<producto>.md` usando solo formas enmascaradas.
3. Implementa un parser en `src/mxbank/parsers/` (contrato en [parsers/base.py](src/mxbank/parsers/base.py)) y regístralo en `parsers/__init__.py`.
4. Crea un PDF sintético en `tests/synthetic/` y sus pruebas: valores extraídos, conciliación y fuga de datos.
5. Valida contra PDFs reales viendo **solo métricas**: `uv run python tools/corpus_check.py corpus/`.

### Estructura

```
src/mxbank/
  cli.py            comandos de la CLI
  pipeline.py       PDF → parser → validación → redacción → escaneo residual
  loader.py         palabras con coordenadas, agrupadas en renglones
  parsers/          un módulo por banco y producto
  privacy/          detectores, diccionario, seudónimos, escáner residual
  validate/         conciliación contable
  models/           raw.py (interno, con PII) y statement.py (salida pública)
tools/              volcado enmascarado, métricas de corpus, guardia de git
tests/              pruebas y generadores de PDFs sintéticos
docs/               análisis, especificación, esquema, privacidad y layouts por banco
```

## Documentación

| Documento | Contenido |
|---|---|
| [01 · Análisis](docs/01-analisis.md) | Problema, datos personales en un estado de cuenta, marco legal, alternativas, requisitos |
| [02 · Especificación técnica](docs/02-especificacion-tecnica.md) | Arquitectura, CLI, parsers, pruebas, estado de implementación |
| [03 · Esquema de salida](docs/03-esquema-salida.md) | Forma y semántica del JSON |
| [04 · Privacidad y redacción](docs/04-privacidad-y-redaccion.md) | Modelo de amenaza, capas, detectores, perfiles, riesgos residuales |
| [05 · Decisiones](docs/05-preguntas-abiertas.md) | Decisiones tomadas y preguntas abiertas |
| [AGENT.md](docs/AGENT.md) | Guía para agentes de IA |
| Layouts | [BBVA débito](docs/bancos/bbva-cuenta.md) · [BBVA crédito](docs/bancos/bbva-credito.md) · [BanCoppel débito](docs/bancos/bancoppel-cuenta.md) |
| [CHANGELOG](CHANGELOG.md) | Historial de versiones |

## Hoja de ruta

- Más bancos: Banorte, Santander, Nu y otros, conforme haya estados reales para validar.
- Consolidado multi-mes (`--consolidate`) y detección de cargos recurrentes.
- Categoría semántica opcional por movimiento (supermercado, streaming, gasolina…).
- Servidor MCP que exponga las mismas herramientas.
- OCR para estados de cuenta escaneados.

## Licencia

[Apache 2.0](LICENSE). Este proyecto no está afiliado ni respaldado por BBVA México, BanCoppel ni ninguna otra institución financiera; los nombres de los bancos solo identifican los formatos que la herramienta puede leer. Ver [NOTICE](NOTICE).
