# 04 · Privacidad y redacción

## 1. Modelo de amenaza

**Qué protegemos**: identidad del titular, identificadores financieros reutilizables para fraude, identidad de terceros (contrapartes).

**Contra quién**: el proveedor de IA y cualquiera con acceso a los prompts/logs (empleados, integraciones, fugas del proveedor).

**Fuera de alcance**: un atacante con acceso a la máquina local donde está el PDF original.

**Supuesto**: la herramienta corre en la máquina del usuario y no tiene red.

## 2. Principios

1. **Allowlist sobre blocklist**: la salida se construye campo por campo desde un modelo cerrado; no se "limpia" un volcado de texto.
2. **Defensa en profundidad**: varias capas independientes; una falla no basta para filtrar.
3. **Fail‑closed**: si el escáner residual encuentra algo, no se emite nada (exit 40).
4. **Sin valores en los reportes**: el bloque `privacy` y los logs cuentan, nunca muestran.
5. **Seudonimizar cuando la relación importa**: la IA necesita saber "es la misma persona que el mes pasado", no quién es.

## 3. Capas de redacción

| # | Capa | Cómo | Cubre |
|---|---|---|---|
| 1 | Estructural | El parser coloca encabezado en `header_pii`; `Statement` no tiene campos para ello. | Nombre, domicilio, RFC, cuenta, CLABE, cliente, sucursal |
| 2 | Diccionario del documento | Valores de `header_pii` y variantes (mayúsculas, sin acentos, cada apellido ≥ 4 letras, calle, colonia) se buscan en todo texto libre. | Nombre del titular dentro de descripciones (p. ej. "TRASPASO A JUAN PEREZ") |
| 3 | Patrones validados | Regex + verificación (ver §4). | RFC, CURP, CLABE, PAN, cuentas, email, teléfono, UUID, CP |
| 4 | Patrones por banco | Cada parser conoce la gramática SPEI de su banco (`"SPEI ENVIADO {BANCO} {NOMBRE} {CONCEPTO}"`) y extrae `counterparty`. | Contrapartes |
| 5 | NER (opcional) | spaCy `PER` sobre descripciones restantes. | Nombres no cubiertos por 4 |
| 6 | Escáner residual | Capas 2–3 (y 5 si disponible) sobre el JSON serializado final. | Red de seguridad |

## 4. Detectores con validación

| Dato | Patrón (simplificado) | Validación adicional |
|---|---|---|
| RFC persona física | `[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}` | Fecha válida en posiciones 5–10; dígito verificador (opcional, alto costo de falsos negativos si se exige) |
| RFC persona moral | `[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}` | Igual; se excluyen RFC de bancos (allowlist pública) |
| CURP | `[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d` | Entidad federativa válida + dígito verificador |
| CLABE | `\d{18}` (con o sin espacios) | Dígito verificador (pesos 3,7,1) + código de banco válido |
| Tarjeta (PAN) | `\d{15,16}` con separadores opcionales | Luhn |
| Cuenta | `\d{10,11}` en contexto ("CUENTA", "CTA", "NO.") | Contexto |
| Email | RFC 5322 simplificado | — |
| Teléfono MX | 10 dígitos, prefijos `+52`, `044`, `045` | Contexto o formato con separadores |
| Folio fiscal | UUID v4 | — |
| Clave de rastreo SPEI | Alfanumérico 1–30 tras "RASTREO", "CVE RAST" | Contexto |
| Código postal | `\d{5}` tras "C.P." / "CP" | Contexto |

Los números largos que **no** validan se tratan según perfil: en `strict` se enmascaran igual; en `standard` se enmascaran si tienen ≥ 10 dígitos.

## 5. Tratamientos

| Tratamiento | Resultado | Uso |
|---|---|---|
| Eliminar | El campo no existe / texto reemplazado por `[RFC]`, `[NOMBRE]` | Identidad directa |
| Enmascarar | `****4821` | Cuentas y tarjetas cuando los últimos 4 son útiles |
| Seudonimizar | `PERSONA_7f3a`, `EMPRESA_c01d`, `ACC_3b9e` | Contrapartes, cuentas propias, claves de rastreo |
| Generalizar | Fecha → mes, monto → rango | *Pendiente*: opción explícita en `strict` |

### Seudónimos

`token = PREFIJO + "_" + hex(HMAC-SHA256(llave, valor_normalizado))[:4..8]`

- `valor_normalizado`: mayúsculas, sin acentos, espacios colapsados.
- Llave **aleatoria por ejecución** por defecto (`pseudonym_scope: "run"`): tokens no comparables entre ejecuciones.
- Con `--pseudonym-key-env` (`pseudonym_scope: "key"`): tokens estables entre meses. La llave nunca se escribe en la salida ni en logs.
- La longitud del hash crece automáticamente si hay colisiones dentro del documento.

### Identificadores estables (`statement_id`, `transactions[].id`, `installment_plans[].id`)

`id = PREFIJO + "_" + hex(HMAC-SHA256(llave, "mxbank-id/v1" | PREFIJO | banco | producto | número de cuenta | …))[:16]` (detalle de las entradas en [03 §7](03-esquema-salida.md#7-identificadores-estables-schema-11)).

**Por qué HMAC y no un hash simple.** Las entradas son datos que un atacante puede conocer o adivinar: el número de cuenta tiene 10–11 dígitos, la fecha está acotada al periodo y el monto a unos cuantos miles de valores. Con un hash sin llave (`sha256(cuenta | fecha | monto | …)`) bastaría probar combinaciones hasta reproducir el id para **confirmar o recuperar el número de cuenta**, o para saber si alguien hizo un pago concreto. Con HMAC, sin la llave cada intento es indistinguible del azar, así que el id no deja derivar nada.

- La llave es la misma de los seudónimos (`--pseudonym-key-env`). Guárdala como cualquier secreto: quien la tenga puede verificar suposiciones sobre los ids.
- El número de cuenta entra **solo al HMAC**; nunca aparece en la salida.
- El escáner residual exime estos campos **solo** si se llaman `id` o `statement_id` **y** su valor coincide exactamente con `^(TX|ST|PLAN)_[0-9a-f]{16,64}$`; cualquier otro contenido en esos campos, o ese formato en otro campo, se escanea normalmente.

## 6. Perfiles

| Elemento | `minimal` | `standard` (default) | `strict` |
|---|---|---|---|
| Nombre/domicilio/RFC/CURP/cliente/sucursal del titular | Eliminado | Eliminado | Eliminado |
| Cuenta propia | Últimos 4 + token | Últimos 4 + token | Solo token |
| Tarjeta completa, CLABE | Eliminado | Eliminado | Eliminado |
| Contrapartes (nombre y cuenta) | Seudónimo | Seudónimo | Seudónimo |
| Banco de la contraparte | Sí | Sí | Sí |
| Comercio y descripción del banco | Sí (redactada) | Sí (redactada) | Sí; los movimientos sin tipo reconocido (`other`) salen como `[OTRO]` |
| Concepto libre de transferencias | Solo con `--include-concepts` (redactado) | Solo con `--include-concepts` (redactado) | Eliminado siempre |
| Clave de rastreo / referencia | Eliminado | Eliminado | Eliminado |
| `file_name`, `file_sha256` | Sí | Sí | No |
| Fechas y montos | Exactos | Exactos | Exactos |

En v0.1.0 `minimal` y `standard` producen la misma salida; `minimal` queda reservado para relajar reglas en el futuro (p. ej. conceptos por defecto). La generalización de fechas y montos (§5) **no está implementada**.

> `minimal` no significa "sin redacción": la identidad directa siempre se elimina. No existe perfil sin redacción.

## 7. Riesgos residuales documentados

- **Conceptos SPEI libres** escritos por terceros pueden contener cualquier cosa ("pago renta depto 4B calle X"). Mitigación: capas 2, 3, 5; `strict` elimina el concepto.
- **Patrones de montos/fechas** (nómina fija el día 15) pueden ayudar a reidentificar si se combinan con otras fuentes. Mitigación prevista: generalización opcional (pendiente).
- **Ubicación en descripciones de comercio**: los bancos agregan sucursal y ciudad al comercio (p. ej. `<COMERCIO><SUCURSAL> <CIUDAD>`). Repetidos, revelan dónde vive o trabaja el titular. Mitigación: conservar solo el comercio normalizado y eliminar sucursal/ciudad (en todos los perfiles excepto `minimal`).
- **Nombres comunes como palabras** (p. ej. apellido "LEON", "ROSA") pueden generar falsos positivos que borran texto útil; se prefiere el falso positivo.
- **Layouts nuevos** pueden mover PII a zonas no previstas; el diccionario del documento y el escáner residual son la red de seguridad.
