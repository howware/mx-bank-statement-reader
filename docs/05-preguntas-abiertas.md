# 05 · Decisiones y preguntas abiertas

## Decididas (v0.1.0)

| # | Pregunta | Decisión |
|---|---|---|
| 1 | ¿Qué bancos van primero? | BBVA (débito y tarjeta de crédito) y BanCoppel (débito): son los estados reales disponibles para validar. |
| 2 | ¿Débito, crédito o ambos? | Ambos para BBVA; débito para BanCoppel. |
| 3 | ¿Persona física o moral? | Física. Los parsers ya detectan RFC de 12 caracteres (`holder_type: business`) pero no hay estados de persona moral para validar. |
| 4 | ¿Hay PDFs reales para desarrollar? | Sí, solo del autor, fuera de git (`docs/Estados/`, `corpus/`). Se estudian con volcados enmascarados revisados por el titular antes de que cualquier persona o IA los lea. |
| 5 | ¿Tokens estables entre meses? | Opcional con `--pseudonym-key-env`; por defecto la llave es aleatoria por ejecución. |
| 6 | ¿Estados de cuenta de terceros? | Fuera del alcance de v0.1.0 (uso personal). Para ese caso se recomienda `--privacy strict`. |
| 7 | ¿Lenguaje? | Python 3.12 con `uv`. |
| 8 | ¿Distribución? | Open source, licencia **Apache 2.0**. Dependencias solo MIT/BSD/Apache, compatibles con Apache 2.0 (se descartó PyMuPDF por AGPL). |
| 9 | ¿OCR en el MVP? | No. |
| 10 | ¿Categorización de gastos? | Solo `type` técnico (compra, SPEI, retiro, etc.) y `merchant` para comercios conocidos; la categoría semántica (supermercado, streaming…) la hace la IA. |
| 11 | ¿Servidor MCP? | Pendiente; reutilizará `pipeline.extract_file`. |
| 12 | ¿Qué se considera dato personal en los movimientos? | Criterio del proyecto: los movimientos (comercio, monto, fecha) se emiten tal cual; lo que no debe quedar es nada que los ligue al titular (nombre, domicilio, RFC, cuentas, tarjeta, CLABE). Los datos de terceros (contrapartes) se seudonimizan. |

## Abiertas

| # | Pregunta | Por qué importa |
|---|---|---|
| A | ¿Incluir los conceptos libres de transferencias por defecto? | Son útiles ("Renta", "Colegiatura") pero los escribe una persona y pueden traer nombres de terceros. Hoy requieren `--include-concepts`. |
| B | ¿Agregar un campo `category` (supermercado, streaming, gasolina…)? | Facilita apps de finanzas personales, pero requiere mantener un catálogo de comercios. |
| C | ¿Siguientes bancos? | Depende de conseguir estados reales para validar (Banorte, Santander, Nu…). |
| D | ¿Consolidado multi-mes (`--consolidate`)? | Permitiría detectar cargos recurrentes directamente en la herramienta. |
