# Seguridad y privacidad

## Reportar un problema

Si encuentras una vulnerabilidad o un caso en el que `mxbank` **deja pasar información personal** en su salida, repórtalo **de forma privada**:

1. Ve a la pestaña **Security → Report a vulnerability** del repositorio (GitHub Security Advisories), o abre directamente https://github.com/proteo5/mx-bank-statement-reader/security/advisories/new.
2. Describe el problema **sin incluir datos reales**:
   - banco, producto y versión de `mxbank` (`mxbank version`);
   - qué campo del JSON contenía la información (`error.details` o la ruta, p. ej. `transactions[3].description`);
   - el **tipo** de dato (nombre, CLABE, tarjeta, domicilio…) y su **forma enmascarada**, por ejemplo `XXXX 9999999999`.

   Puedes generar la forma enmascarada de un renglón con `tools/layout_dump.py`. Revísala antes de enviarla.

**Nunca publiques** estados de cuenta, salidas JSON, volcados ni capturas con datos reales en issues, pull requests o discusiones públicas.

## Qué esperar

Es un proyecto personal mantenido en tiempo libre: se responde en cuanto sea posible, sin un plazo garantizado. Las fugas de información personal tienen prioridad sobre cualquier otro cambio.

## Versiones con soporte

Solo la versión más reciente publicada en `main`.

Ver también el [aviso legal y advertencias de uso](AVISO-LEGAL.md).
