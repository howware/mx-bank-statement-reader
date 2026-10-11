# AGENTS.md

Instrucciones para agentes de IA (y personas) que **desarrollan** este repositorio. Para **usar** la herramienta con un agente, ver [docs/AGENT.md](docs/AGENT.md) y el skill [.claude/skills/mxbank/SKILL.md](.claude/skills/mxbank/SKILL.md).

## Regla de oro: los datos reales nunca se leen directamente ni se versionan

Los estados de cuenta reales viven en `corpus/` o `docs/Estados/` (ignorados por git) y contienen datos personales del titular y de terceros.

- **No abras ni extraigas texto de un PDF real**, ni con herramientas de lectura ni con scripts propios. Su contenido terminaría en el contexto del modelo.
- Para estudiar un layout:
  1. Genera el volcado enmascarado **a un archivo, sin leerlo**: `uv run python tools/layout_dump.py <pdf> --out docs/Estados/layout_x.txt`. Agrega `--reveal-tx-first-line` si hace falta ver la primera línea de los movimientos.
  2. **Pide al titular que lo revise** y espera su aprobación.
  3. Solo entonces léelo.
- Para depurar un parser contra un PDF real, usa **diagnósticos que impriman solo booleanos, conteos y formas enmascaradas** (`9` por dígito, `X` por letra), nunca valores. Ejemplo de pregunta válida: "¿la suma de cargos coincide con el total del banco?" → `True/False`.
- Para validar, usa `uv run python tools/corpus_check.py <carpeta>`: solo imprime métricas.
- En la documentación de layouts (`docs/bancos/`) solo van formas genéricas (`<BANCO>`, `<COMERCIO>`, `<CIUDAD>`). Nunca nombres de comercios, ciudades, bancos de contrapartes ni conceptos que vengan de los estados del titular: aunque no sean PII por sí solos, ubican o perfilan a la persona.
- Los JSON de salida y los resúmenes generados a partir de datos reales se guardan en `docs/Estados/` y no se publican.

## Guardia de commits

```bash
git config core.hooksPath tools/git-hooks
```

[tools/check_no_pii.py](tools/check_no_pii.py) bloquea PDFs, las carpetas de datos reales y cualquier CLABE, tarjeta, RFC, CURP o correo. CI la corre sobre todo el repositorio. Si bloquea un valor **ficticio** de prueba, constrúyelo en código (como `tests/synthetic/common.py`) o agrégalo a `.pii-allowlist`. Nunca agregues ahí un valor real.

## Comandos

```bash
uv sync                              # dependencias
uv run pytest -q                     # pruebas (PDFs sintéticos; la red está bloqueada)
uvx ruff check src tests tools       # lint
uv run mxbank extract <pdf>          # probar la CLI
```

## Arquitectura en una línea

`loader` (palabras con coordenadas) → `parsers/<banco>_<producto>.py` (`RawStatement`, **con PII**) → `validate/reconcile` → `privacy/redactor` (`Statement`, sin PII) → `privacy/residual_scan` (fail-closed, código 40). `RawStatement` nunca se serializa.

## Agregar o corregir un parser

1. Documenta el layout en `docs/bancos/<banco>-<producto>.md` con formas enmascaradas.
2. Implementa el parser (contrato en `parsers/base.py`) y regístralo en `parsers/__init__.py`.
3. Crea su PDF sintético en `tests/synthetic/` reproduciendo las particularidades reales (orden de los movimientos, formato de fechas, signos, totales) y escribe pruebas de valores, conciliación y fuga de datos.
4. Valida con `tools/corpus_check.py`: conciliación con diferencia `0.00` y totales del banco coincidentes.
5. Si una regla contable no cuadra, encuéntrala con diagnósticos booleanos (qué combinación de campos cierra la diferencia) y documéntala como "verificada en N estados".

## Convenciones

- Código, comentarios, documentación y mensajes de la CLI en español; nombres de campos JSON en inglés `snake_case`.
- Montos siempre `Decimal`, nunca `float`.
- Un campo nuevo en la salida requiere actualizar `models/statement.py`, `docs/03-esquema-salida.md` y la revisión de privacidad.
- Commits sin líneas de atribución a herramientas de IA.
