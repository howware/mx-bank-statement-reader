# 01 · Análisis del problema

## 1. Contexto

Cada vez más flujos (contabilidad, conciliación, análisis de gastos, evaluación de crédito, asistentes personales) quieren que un modelo de IA **entienda estados de cuenta bancarios**. En México estos documentos llegan casi siempre como **PDF**, y contienen una cantidad importante de **datos personales y datos financieros identificables**.

Subir el PDF original a un servicio de IA implica:

- Enviar datos personales a un tercero (transferencia/remisión de datos bajo la LFPDPPP).
- Exponer números de cuenta, CLABE y tarjeta que permiten fraude o ingeniería social.
- Exponer datos de **terceros** (contrapartes de transferencias SPEI) que nunca consintieron.
- Gastar tokens en ruido (avisos legales, publicidad, glosarios, tablas UDIS, etc.).

## 2. Objetivo del proyecto

Construir **herramientas CLI orientadas a IA** que:

1. Lean un PDF de estado de cuenta de un banco mexicano **localmente** (sin red).
2. Extraigan la información financiera útil (periodo, saldos, movimientos, comisiones, intereses).
3. **Eliminen o seudonimicen los datos personales** antes de que salgan de la máquina.
4. Entreguen un **JSON estructurado, estable y validable** que una IA (o un agente) pueda consumir directamente.

> Principio rector: **lo que sale de la herramienta debe ser seguro de compartir por defecto**. Si la herramienta no está segura, falla (fail‑closed) en vez de filtrar datos.

## 3. Usuarios y escenarios

| Actor | Escenario |
|---|---|
| **Agente de IA** (Claude Code, MCP client, script con LLM) | Invoca la CLI como herramienta, lee el JSON de `stdout`, razona sobre los movimientos. |
| **Desarrollador / integrador** | Integra la CLI en un pipeline (batch de PDFs → JSON → API de IA). |
| **Usuario final técnico** | Quiere preguntarle a una IA "¿en qué gasté más este mes?" sin subir su estado de cuenta. |
| **Despacho contable** | Procesa estados de cuenta de clientes (datos de terceros → obligación reforzada de minimizar). |

### Casos de uso principales

- **CU‑1** Convertir un PDF a JSON anonimizado.
- **CU‑2** Detectar qué banco/producto es un PDF sin extraer todo.
- **CU‑3** Procesar un lote de PDFs (varios meses) y producir JSON por archivo o consolidado.
- **CU‑4** Auditar un JSON (o texto arbitrario) en busca de PII residual antes de enviarlo.
- **CU‑5** Obtener el JSON Schema de salida para que la IA sepa qué esperar.

## 4. Naturaleza de los estados de cuenta en México

### 4.1 Bancos y productos

Bancos objetivo probables (a priorizar con el usuario, ver [05-preguntas-abiertas.md](05-preguntas-abiertas.md)):

- BBVA México, Santander, Banorte, Banamex, HSBC, Scotiabank, Inbursa, BanBajío, Afirme, Banco Azteca, BanCoppel.
- Neobancos / fintech: Nu, Hey Banco, Mercado Pago, Spin by OXXO, Klar, Stori.

Productos con estructura distinta:

| Producto | Particularidades |
|---|---|
| Cuenta de débito / cheques / nómina | Saldo inicial/final, depósitos, retiros, SPEI con clave de rastreo, saldo promedio. |
| Tarjeta de crédito | Fecha de corte, fecha límite de pago, pago mínimo, pago para no generar intereses, CAT, MSI (meses sin intereses), intereses, IVA. |
| Inversión / pagarés | Rendimientos, ISR retenido, tasas, plazos. |
| Cuentas empresariales (persona moral) | RFC de 12 caracteres, mayor volumen de movimientos, múltiples cuentas por PDF. |

### 4.2 Características del documento

- Mayoritariamente **PDF digital (texto embebido)** generado por el banco. Algunos usuarios los tienen **escaneados o fotografiados** → requiere OCR.
- Algunos PDFs vienen **protegidos con contraseña**.
- Estructura regulada en parte por disposiciones de CNBV/Banxico (CAT, comisiones, avisos), por lo que hay **secciones recurrentes** aunque el layout varía por banco.
- Tablas de movimientos que **cruzan páginas**, con encabezados repetidos, descripciones **multilínea** y columnas Cargo/Abono/Saldo con alineación posicional.
- Formatos numéricos `1,234.56`, fechas `05/ENE/2026`, `05-01-26`, `05 ENE` (año implícito por periodo).
- Un mismo banco **cambia su layout** con el tiempo → los parsers deben ser versionables.
- Muchos estados de cuenta incluyen información fiscal (CFDI): RFC, folio fiscal (UUID), sello digital, código QR.

## 5. Inventario de datos personales (PII) en un estado de cuenta

Clasificación usada en todo el proyecto:

| Clase | Dato | Dónde aparece | Detección | Tratamiento por defecto |
|---|---|---|---|---|
| **Identidad directa** | Nombre del titular | Encabezado, cada página | Estructural (campo del encabezado) + diccionario | Eliminar |
| | Domicilio (calle, colonia, CP, municipio) | Encabezado | Estructural | Eliminar (opcional: conservar solo estado) |
| | RFC (12/13 caracteres) | Encabezado, CFDI | Regex + validación de formato | Eliminar |
| | CURP (18 caracteres) | Ocasional | Regex + validación | Eliminar |
| | Teléfono, email | Encabezado, avisos | Regex | Eliminar |
| **Identificadores financieros** | Número de cuenta | Encabezado, pies | Estructural + regex | Enmascarar (`****1234`) |
| | CLABE (18 dígitos) | Encabezado, movimientos SPEI | Regex + dígito verificador | Enmascarar |
| | Número de tarjeta (PAN) | Encabezado, movimientos | Regex + Luhn | Enmascarar |
| | Número de cliente, contrato | Encabezado | Estructural | Eliminar |
| **Datos de terceros** | Nombre de contraparte (ordenante/beneficiario SPEI) | Descripción de movimientos | Patrones por banco + NER opcional | Seudonimizar (`PERSONA_7f3a`) |
| | CLABE/cuenta de contraparte | Descripción | Regex | Enmascarar |
| | RFC de contraparte | Descripción | Regex | Eliminar |
| **Trazabilidad** | Clave de rastreo SPEI, referencia, autorización | Descripción | Patrones | Seudonimizar o eliminar |
| | Folio fiscal (UUID), sello digital, cadena original | Pie / última página | Regex | Eliminar |
| | Código QR / código de barras | Imagen | No se extraen imágenes | Ignorar |
| **Contexto** | Sucursal, ejecutivo de cuenta | Encabezado | Estructural | Eliminar |
| | Comercio (merchant) en compras con tarjeta | Descripción | — | **Conservar** (es útil y no es PII del titular) |
| | Montos, fechas, saldos | Movimientos | — | **Conservar** (es el propósito) |

> Nota: montos y fechas no son PII por sí mismos, pero combinados pueden reidentificar. Se documenta como **riesgo residual** y se prevén opciones de generalización, pendientes en v0.1.0 (ver [04-privacidad-y-redaccion.md](04-privacidad-y-redaccion.md)).

## 6. Marco legal y de cumplimiento (referencial, no es asesoría legal)

- **LFPDPPP** (nueva Ley Federal de Protección de Datos Personales en Posesión de los Particulares, DOF 20‑mar‑2025): principios de licitud, consentimiento, minimización, finalidad y proporcionalidad. Enviar datos a un proveedor de IA es una remisión/transferencia que debe estar justificada. **Minimizar antes de enviar** reduce drásticamente el riesgo.
- **Secreto bancario** (Ley de Instituciones de Crédito): obliga a los bancos; no al titular. Sin embargo, despachos o empresas que procesan estados de cuenta de terceros asumen deberes de confidencialidad contractuales y de protección de datos.
- **Datos de terceros**: las contrapartes de SPEI no son titulares del documento → deben seudonimizarse siempre.
- **PCI DSS** (si el usuario es comercio/procesador): el PAN completo nunca debe salir en claro.

Conclusión de diseño: **procesamiento 100 % local, sin telemetría, sin red**, y la salida debe minimizar por defecto.

## 7. Alternativas evaluadas

| Alternativa | Pros | Contras | Decisión |
|---|---|---|---|
| Subir el PDF directo al LLM (visión/PDF nativo) | Cero desarrollo | Expone toda la PII; no determinista; costo en tokens | ❌ Es el problema a resolver |
| Redactar el PDF (tachar) y subir el PDF redactado | La IA "ve" el documento | Redacción visual es frágil (texto oculto, capas); sigue siendo PDF caro de procesar | ❌ Como salida principal; ✅ como posible herramienta secundaria a futuro |
| Extraer todo el texto y aplicar regex de PII | Simple, genérico | Pierde estructura de tablas; nombres de personas no se detectan con regex | ⚠️ Solo como modo de respaldo (`generic`) |
| Usar un LLM local para extraer y anonimizar | Flexible con layouts nuevos | Pesado, no determinista, difícil de auditar | ⏳ Posible plugin futuro, nunca el camino por defecto |
| **Parsers deterministas por banco + capa genérica de redacción + validación contable** | Preciso, auditable, rápido, offline, reproducible | Requiere un parser por banco/layout | ✅ **Elegida** |

## 8. Requisitos

### 8.1 Funcionales

- **RF‑01** Leer PDFs con texto embebido; soportar PDFs protegidos con contraseña.
- **RF‑02** Detectar banco, producto y versión de layout (con nivel de confianza).
- **RF‑03** Extraer: periodo, fechas de corte, saldos, totales, movimientos (fecha, descripción, cargo/abono, saldo), comisiones, intereses, impuestos; para crédito además pago mínimo, pago para no generar intereses, límite de crédito, CAT, MSI.
- **RF‑04** Normalizar fechas (ISO‑8601), montos (decimal con signo), moneda (MXN/USD), tipo de movimiento (SPEI, compra, retiro, comisión, interés, etc.).
- **RF‑05** Eliminar / enmascarar / seudonimizar PII según política configurable.
- **RF‑06** Escanear la salida final en busca de PII residual y fallar si se detecta (fail‑closed).
- **RF‑07** Validar consistencia contable (saldo inicial + abonos − cargos = saldo final) e informar el resultado.
- **RF‑08** Emitir JSON conforme a un JSON Schema versionado y publicarlo vía CLI.
- **RF‑09** Procesar lotes y directorios.
- **RF‑10** Modo genérico (banco no soportado): extracción de mejor esfuerzo + redacción agresiva, marcado como baja confianza.
- **RF‑11** (Fase posterior) OCR para PDFs escaneados.

### 8.2 No funcionales

- **RNF‑01 Privacidad**: sin acceso a red; sin escribir texto crudo a disco salvo petición explícita; sin PII en logs.
- **RNF‑02 Determinismo**: misma entrada + misma configuración ⇒ misma salida byte a byte (incluida la seudonimización con sal fija).
- **RNF‑03 Ergonomía para IA**: salida JSON en `stdout`, diagnósticos en `stderr`, códigos de salida documentados, sin prompts interactivos, `--help` conciso, errores en JSON.
- **RNF‑04 Rendimiento**: < 2 s por PDF típico de 10 páginas en una laptop.
- **RNF‑05 Portabilidad**: Windows, macOS, Linux.
- **RNF‑06 Extensibilidad**: agregar un banco = agregar un módulo parser + fixtures, sin tocar el núcleo.
- **RNF‑07 Auditabilidad**: el JSON incluye un reporte de redacción (qué clases se eliminaron y cuántas veces, nunca los valores).

## 9. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Fuga de PII por un patrón no cubierto (p. ej. nombre de contraparte en formato nuevo) | Alto | Capas múltiples de redacción + escáner residual + diccionario con nombres del encabezado + lista de permitidos (allowlist) en lugar de lista de bloqueo para campos libres |
| Cambio de layout del banco rompe el parser | Medio | Detección por huella con versión; validación contable detecta extracción incorrecta; fallback a modo genérico |
| No contar con PDFs reales para pruebas (son sensibles) | Alto | Corpus privado local fuera de git + generador de PDFs sintéticos + pruebas "golden" solo sobre sintéticos |
| Reidentificación por montos/fechas | Bajo‑Medio | Opciones de generalización; documentar el riesgo residual |
| Licencias de librerías PDF (p. ej. AGPL) | Medio | Elegir dependencias MIT/BSD/Apache (ver especificación) |
| Contraseña del PDF expuesta en historial de shell | Medio | Leerla de variable de entorno o stdin, nunca como argumento obligatorio |

## 10. Alcance por fases

| Fase | Contenido |
|---|---|
| **F0 – Fundaciones** | Esqueleto CLI, modelo de datos, JSON Schema v1, motor de redacción genérico, escáner residual, modo `generic`, generador de fixtures sintéticos. |
| **F1 – MVP** | 2–3 bancos (débito) priorizados por el usuario, validación contable, `extract`, `detect`, `schema`, `audit`. |
| **F2** | Tarjetas de crédito de los mismos bancos, lote/directorio, consolidado multi‑mes, categorización básica de movimientos. |
| **F3** | Más bancos, OCR, servidor MCP que expone las mismas herramientas, empaquetado como binario único. |

> **Estado en v0.1.0**: F0 y F1 completas salvo el modo `generic` (un banco no soportado se rechaza con código 20/21 en lugar de extraerse en modo de respaldo). De F2 ya están las tarjetas de crédito BBVA; consolidado y categorización siguen pendientes. Ver [02 §11](02-especificacion-tecnica.md#11-estado-de-implementación-v010).
