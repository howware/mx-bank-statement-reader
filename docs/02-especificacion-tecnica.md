# 02 · Especificación técnica

## 1. Decisiones de stack

| Decisión | Elección | Razón |
|---|---|---|
| Lenguaje | **Python 3.12+** | Mejor ecosistema de extracción PDF y tablas; regex Unicode; fácil de extender por bancos. |
| Extracción de texto con posiciones | **pdfplumber** (sobre pdfminer.six) | MIT; da caracteres/palabras con coordenadas, necesario para reconstruir columnas Cargo/Abono/Saldo. |
| Render / PDFs difíciles | **pypdfium2** (dependencia de pdfplumber) | Apache/BSD; aún no se usa directamente. |
| Descartado | PyMuPDF | Licencia **AGPL** incompatible con distribución cerrada o embebida. |
| CLI | **Typer** (sobre Click) | Subcomandos tipados, ayuda generada. |
| Modelo de datos y JSON Schema | **Pydantic v2** | Validación + generación automática del JSON Schema publicado. |
| Montos | `decimal.Decimal` | Nunca `float` para dinero; se serializa como string en JSON. |
| OCR (F3, pendiente) | Tesseract (`spa`) vía `pytesseract`, opcional (`extra`) | No obliga dependencia nativa en el camino principal. |
| NER opcional (F2+, pendiente) | spaCy `es_core_news_sm`, opcional (`extra`) | Detección de nombres de personas en descripciones libres. |
| Empaquetado | `uv` / `pipx`; binario único con PyInstaller en F3 | Instalación simple para agentes. |
| Pruebas | pytest + PDFs sintéticos (reportlab) | Ver §9. |

Nombre del paquete: `mx-bank-statement-reader`. Nombre del ejecutable: **`mxbank`**.

## 2. Arquitectura

```
           ┌──────────────┐
 PDF ───▶  │  1. Loader   │  abre, desencripta, extrae palabras con coordenadas por página
           └──────┬───────┘
                  ▼
           ┌──────────────┐
           │ 2. Detector  │  huellas por banco → (bank, product, layout_version, confidence)
           └──────┬───────┘
                  ▼
           ┌──────────────┐
           │ 3. Parser    │  plugin específico del banco (o GenericParser)
           │   del banco  │  → RawStatement: header(PII), summary, transactions (texto crudo)
           └──────┬───────┘
                  ▼
           ┌──────────────┐
           │ 4. Normalizer│  fechas ISO, Decimal, tipo de movimiento, moneda
           └──────┬───────┘
                  ▼
           ┌──────────────┐
           │ 5. Redactor  │  política de privacidad: eliminar / enmascarar / seudonimizar
           └──────┬───────┘
                  ▼
           ┌──────────────┐
           │ 6. Validator │  conciliación contable + escáner de PII residual (fail-closed)
           └──────┬───────┘
                  ▼
           ┌──────────────┐
           │ 7. Emitter   │  JSON (schema v1) → stdout / archivo
           └──────────────┘
```

Regla clave: **el `RawStatement` con PII nunca se serializa**. Solo existe en memoria entre las etapas 3 y 5. El único objeto serializable es el `Statement` redactado.

### 2.1 Estructura de carpetas

```
src/mxbank/
  cli.py                  # Typer app, subcomandos
  pipeline.py             # orquestación: carga → parser → validación → redacción → escaneo residual
  loader.py               # apertura del PDF, contraseña, palabras con coordenadas agrupadas en renglones
  text.py                 # normalización (mayúsculas, acentos, guion suave U+00AD)
  errors.py               # errores con código estable y código de salida
  models/
    raw.py                # RawStatement (contiene PII, nunca se serializa)
    statement.py          # Statement (salida pública, Pydantic → JSON Schema)
  parsers/
    __init__.py           # registro de parsers y detección por huellas
    base.py               # contrato BankParser + columnas por borde derecho, búsqueda de etiquetas
    bbva_debit.py  bbva_credit.py  bancoppel_debit.py
    merchants.py          # comercios conocidos → nombre canónico
  normalize/
    dates.py  amounts.py
  privacy/
    vocab.py              # vocabulario bancario común (nunca es PII)
    detectors.py          # CLABE, tarjeta (Luhn), RFC, CURP, correo, números largos
    pseudonym.py          # tokens HMAC
    redactor.py           # diccionario del documento + construcción del Statement
    residual_scan.py      # escaneo final fail-closed
  validate/
    reconcile.py
tools/
  layout_dump.py          # volcado enmascarado para estudiar layouts
  corpus_check.py         # métricas sobre PDFs reales, sin contenido
  check_no_pii.py         # guardia de git (hook en tools/git-hooks/)
tests/
  synthetic/              # generadores de PDFs ficticios por banco
  test_*.py               # extracción, fugas, redacción, normalización, guardia
corpus/, docs/Estados/    # PDFs reales del desarrollador — en .gitignore, nunca se versionan
```

## 3. Interfaz de línea de comandos

Convenciones (orientadas a IA):

- **stdout** solo contiene el resultado (JSON). **stderr** contiene logs/diagnósticos (sin PII).
- Sin prompts interactivos nunca. Sin colores si no es TTY.
- Errores también como JSON en stdout cuando `--format json` (por defecto), con código de salida ≠ 0.
- Opciones con nombres largos y explícitos; los cortos son opcionales.

### 3.1 Subcomandos

| Comando | Propósito |
|---|---|
| `mxbank extract <pdf>...` | Extrae y anonimiza. Comando principal. |
| `mxbank detect <pdf>...` | Solo identifica banco/producto/layout y confianza. No extrae movimientos. |
| `mxbank audit <archivo\|->` | Escanea un JSON o texto en busca de PII residual. Útil como guardia antes de enviar cualquier cosa a una IA. |
| `mxbank schema [--version 1]` | Imprime el JSON Schema de salida. |
| `mxbank banks` | Lista bancos, productos y versiones de layout soportados. |
| `mxbank version` | Versión de la herramienta y del schema. |

### 3.2 `extract` – opciones

```
mxbank extract <pdf|dir>... [opciones]

  --out PATH                 Archivo de salida (por defecto stdout)
  --bank TEXT                Forzar banco (omite detección; se elige el producto con mejor huella)
  --privacy [strict|standard|minimal]   Perfil de privacidad (default: standard)
  --pseudonym-key-env NAME   Variable de entorno con la llave HMAC para tokens estables
                             entre ejecuciones (sin ella: llave aleatoria por ejecución)
  --password-env NAME        Variable de entorno con la contraseña del PDF
  --password-stdin           Leer contraseña de stdin
  --include-concepts         Incluir conceptos libres de transferencias (redactados). Default: no
  --consolidate              (pendiente F2) Con varios PDFs: un solo JSON con todos los periodos
  --fail-on-unbalanced       Exit ≠ 0 si la conciliación contable no cuadra
  --allow-low-confidence     Permitir salida con confianza de detección < umbral
  --pretty                   JSON indentado (default: compacto si no es TTY)
  --ndjson                   Un objeto por línea (lotes)
```

No existe opción para obtener texto crudo sin redactar en stdout. Para estudiar layouts se usa `tools/layout_dump.py` (volcado enmascarado) y para validar contra PDFs reales `tools/corpus_check.py`, que solo imprime métricas (conteos, conciliación, campos faltantes), nunca descripciones ni nombres.

### 3.3 Códigos de salida

| Código | Significado |
|---|---|
| 0 | Éxito |
| 2 | Uso incorrecto (argumentos) |
| 10 | Archivo no encontrado / no es PDF |
| 11 | PDF protegido: falta contraseña o es incorrecta |
| 12 | PDF sin texto (probablemente escaneado; requiere OCR) |
| 20 | Banco no reconocido (y no se permitió modo genérico) |
| 21 | Confianza de parseo por debajo del umbral |
| 30 | La conciliación contable no cuadra (solo con `--fail-on-unbalanced`) |
| 40 | **PII residual detectada en la salida — no se emitió nada** |
| 50 | Error interno |

### 3.4 Formato de error

```json
{
  "ok": false,
  "error": {
    "code": "PDF_PASSWORD_REQUIRED",
    "exit_code": 11,
    "message": "El PDF está protegido. Proporcione la contraseña con --password-env o --password-stdin.",
    "file": "estado_2026_09.pdf"
  }
}
```

`file` es el **nombre base** del archivo; nunca la ruta completa (las rutas suelen contener el nombre del usuario).

## 4. Detección de banco

Cada parser registra **huellas** (fingerprints) con peso:

- Cadenas exactas en la primera página (razón social del banco, nombre del producto).
- Metadatos del PDF (`Producer`, `Creator`).
- Posiciones características (p. ej. logo/encabezado en cierta región, títulos de columnas).
- RFC institucional del banco (dato público, no PII).

Resultado: lista ordenada `(bank, product, layout_version, score)`. Se elige el mayor si `score ≥ 0.8`; si no, `GenericParser` con `confidence: "low"`.

## 5. Contrato de un parser de banco

```python
class BankParser(Protocol):
    bank: str              # "bbva"
    product: str           # "debit"
    layout_version: str    # "2024.1"

    def fingerprint(self, doc: LoadedDocument) -> float: ...
    def parse(self, doc: LoadedDocument) -> RawStatement: ...
```

`RawStatement` separa explícitamente:

- `header_pii`: nombre, domicilio, RFC, CURP, cuenta, CLABE, tarjeta, cliente, sucursal… (se usa **solo** para alimentar el diccionario del redactor y luego se descarta).
- `summary`: saldos y totales.
- `transactions`: lista con `date_raw`, `description_raw` (multilínea unida), `debit`, `credit`, `balance`.
- `sections`: comisiones, intereses, MSI, etc.

Utilidades comunes en `parsers/base.py`: segmentación de tablas por columnas usando las coordenadas X de los encabezados, unión de descripciones multilínea, eliminación de encabezados/pies repetidos, inferencia de año en fechas sin año a partir del periodo.

## 6. Normalización

- **Fechas** → `YYYY-MM-DD`. Meses en español abreviados (`ENE, FEB, MAR, ABR, MAY, JUN, JUL, AGO, SEP/SEPT, OCT, NOV, DIC`). Año inferido por periodo, con manejo del cruce diciembre→enero.
- **Montos** → string decimal con 2 decimales, signo explícito en `amount` (negativo = salida de dinero). Se conservan `debit`/`credit` por claridad.
- **Moneda** → ISO 4217 (`MXN`, `USD`).
- **Tipo de movimiento** (`type`), por reglas sobre la descripción: `spei_in`, `spei_out`, `transfer_internal`, `card_purchase`, `cash_withdrawal`, `cash_deposit`, `payroll`, `fee`, `interest`, `tax`, `payment` (pago a tarjeta), `refund`, `direct_debit` (domiciliación), `other`.

## 7. Privacidad y redacción

Detalle completo en [04-privacidad-y-redaccion.md](04-privacidad-y-redaccion.md). Resumen:

1. **Estructural**: los campos del encabezado nunca pasan a la salida (allowlist de campos de salida).
2. **Diccionario**: todos los valores de `header_pii` (y sus variantes: mayúsculas, sin acentos, apellidos sueltos, tokens de domicilio) se buscan y reemplazan en todo texto libre.
3. **Patrones con validación**: RFC, CURP, CLABE (dígito verificador), PAN (Luhn), cuentas de 10–11 dígitos, email, teléfono, UUID, claves de rastreo.
4. **Patrones por banco**: cada parser sabe dónde aparece el nombre de la contraparte en su formato SPEI y lo marca como `counterparty`.
5. **NER opcional**: nombres de personas restantes.
6. **Escáner residual**: se ejecuta sobre el JSON final serializado; si detecta algo → exit 40 y no se emite.

## 8. Rendimiento y seguridad operativa

- Sin dependencias que hagan llamadas de red; `tests/conftest.py` bloquea los sockets en todas las pruebas.
- stderr solo recibe una línea por archivo con el código de error (`error: <archivo>: <CODIGO>`); nunca contenido del documento.
- Archivos temporales: no se crean; todo en memoria.
- Límites fijos: 50 MB y 200 páginas por PDF, para evitar PDFs maliciosos.

## 9. Estrategia de pruebas

| Tipo | Qué valida |
|---|---|
| **Unitarias** | Detectores (RFC/CURP/CLABE/Luhn), parseo de fechas y montos, inferencia de año. |
| **Generativas** | 300 CLABE/tarjetas válidas generadas con semilla fija, con y sin espacios, en posiciones aleatorias: el redactor siempre las elimina (`tests/test_redactor.py`). |
| **Sintéticas** | PDFs **sintéticos** por banco (reportlab imitando el layout) → valores esperados (`tests/test_extract_synthetic.py`). |
| **Fuga (leak)** | Se siembran valores PII conocidos en los fixtures; el test falla si cualquiera aparece (incluso parcialmente o sin acentos) en la salida. |
| **Conciliación** | Todos los sintéticos deben cuadrar contablemente y con los totales del banco. |
| **Corpus privado** | `tools/corpus_check.py` sobre `corpus/` (no versionado): solo métricas — banco, conteos por tipo, conciliación, campos faltantes, hallazgos residuales. |
| **Sin red** | Fixture global (`tests/conftest.py`) que falla si se abre un socket. |

## 10. Integración con IA

- **CLI como herramienta de agente**: `mxbank --help` y [docs/AGENT.md](AGENT.md) con reglas, códigos de salida y ejemplo de uso.
- **Servidor MCP (F3)**: `mxbank mcp` expone `extract_statement`, `detect_statement`, `audit_text`, `get_schema` reutilizando el mismo núcleo. El servidor recibe rutas locales, no contenido.
- La salida incluye `schema_version` y un bloque `privacy` para que la IA sepa qué fue omitido y no "invente" datos.

## 11. Estado de implementación (v0.2.0)

| Componente | Estado |
|---|---|
| `extract`, `detect`, `audit`, `schema`, `banks`, `version` | ✅ |
| BBVA cuenta de débito (layout 2024.1) | ✅ 4/4 estados reales conciliados, totales y saldos por día correctos |
| BanCoppel cuenta de débito (layout 2025.1) | ✅ 1/1 estado real conciliado, totales y saldos por renglón correctos |
| BBVA tarjeta de crédito (layout 2025.1) | ✅ 4/4 estados reales conciliados con el saldo de cargos regulares; bloque `credit`, planes a meses, tipo de cambio, parcialidades |
| Redacción (estructural, diccionario, patrones), seudónimos HMAC, escáner residual fail‑closed | ✅ |
| Identificadores estables `statement_id`, `transactions[].id`, `installment_plans[].id` (schema 1.1) | ✅ docs/03 §7 |
| Perfiles `minimal` / `standard` / `strict` | ✅ (diferencias en §6 de docs/04) |
| `--consolidate`, parser genérico (`generic`), generalización de fechas/montos, OCR, NER, servidor MCP, tarjetas de otros bancos | ⏳ |

Decisiones tomadas al implementar:

- **Conceptos libres fuera por defecto** (`--include-concepts` para incluirlos redactados). Los escriben personas y pueden traer nombres de terceros que ningún patrón detecta.
- **Fechas y montos no pasan por el escáner residual**: son valores tipados que genera el modelo (`YYYY-MM-DD`, decimales); el resto de strings sí, incluidos los números puros.
- **Números en el diccionario del documento**: solo de 5+ dígitos; los de 4 dígitos se eliminan del texto libre por patrón (evita que años y horas se marquen como PII).
- Tarjeta de crédito BBVA: la conciliación usa sus propias reglas (docs/bancos/bbva-credito.md §6) y el sufijo `; Tarjeta Digital ***NNNN` se elimina de las descripciones porque liga el movimiento a la tarjeta.
- BanCoppel imprime fechas **MM/DD** y lista los movimientos **del más reciente al más antiguo**; la salida siempre es cronológica.
