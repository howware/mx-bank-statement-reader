# Guía para agentes de IA

Instrucciones para un agente (Claude Code, un cliente MCP o cualquier script con un LLM) que use `mxbank` como herramienta. Copia esta sección a las instrucciones del agente si hace falta.

## Reglas

1. **Nunca leas ni subas el PDF original.** Invoca `mxbank extract` y trabaja solo con el JSON que devuelve.
2. Lee **stdout** como JSON. **stderr** solo trae diagnósticos legibles.
3. Revisa el **código de salida** antes de usar el resultado. Con `0` el JSON es seguro de usar; con cualquier otro, stdout trae `{"ok": false, "error": {...}}`.
4. No intentes reconstruir datos omitidos. Los seudónimos (`PERSONA_…`, `CUENTA_…`, `ACC_…`) sirven para agrupar, no para identificar.
5. Si `validation.reconciled` no es `true`, avisa al usuario que las cifras pueden estar incompletas.

## Comandos

```bash
mxbank extract estado.pdf                 # un objeto JSON (schema 1.0)
mxbank extract carpeta/ --ndjson          # un objeto por línea
mxbank detect estado.pdf                  # banco, producto y confianza, sin extraer
mxbank schema                             # JSON Schema de la salida
mxbank banks                              # bancos y productos soportados
mxbank audit archivo.json                 # buscar PII residual en cualquier texto/JSON
```

Opciones útiles de `extract`: `--privacy strict`, `--include-concepts`, `--pseudonym-key-env VAR` (seudónimos estables entre meses), `--password-env VAR` o `--password-stdin` (PDF protegido), `--fail-on-unbalanced`.

## Códigos de salida

| Código | Qué hacer |
|---|---|
| 0 | Usar el JSON |
| 2 | Corregir los argumentos |
| 10 | El archivo no existe o no es PDF |
| 11 | Pedir la contraseña al usuario y pasarla con `--password-env` (nunca como argumento) |
| 12 | El PDF es un escaneo; aún no hay OCR |
| 20 / 21 | Banco no soportado o detección dudosa; ver `mxbank banks` |
| 30 | La conciliación no cuadra (solo con `--fail-on-unbalanced`) |
| 40 | Se detectó posible PII en la salida y **no se emitió nada**; `error.details` dice qué campo, nunca el valor. Reportarlo como bug |

## Campos clave

- `transactions[].amount`: negativo = salida de dinero (cargo), positivo = entrada (abono).
- `transactions[].type`: `card_purchase`, `spei_in`, `spei_out`, `cash_withdrawal`, `card_payment`, `installment`, `fee`, `interest`, etc. La lista completa está en `mxbank schema`.
- `credit` (solo tarjetas): límite, disponible, fecha de corte, fecha límite de pago, pago mínimo, pago para no generar intereses, CAT y tasa.
- `installment_plans[]` (solo tarjetas): compras a meses con su saldo pendiente.
- `privacy`: qué se eliminó o seudonimizó (conteos, nunca valores).

## Ejemplo de uso en un agente

```text
Usuario: ¿en qué gasté más este mes?
Agente:  mxbank extract ~/estados/tarjeta_sep.pdf   → exit 0
         agrupa transactions con amount < 0 por merchant/description,
         excluye type = card_payment / installment_conversion,
         responde con las 5 categorías principales.
```
