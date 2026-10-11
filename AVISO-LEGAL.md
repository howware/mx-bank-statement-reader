# Aviso legal y advertencias de uso

*Última revisión: octubre de 2026 · aplica a mx-bank-statement-reader (`mxbank`) v0.1.0 y posteriores.*

Este documento resume, hasta donde sabemos, los límites de responsabilidad y las advertencias de uso del proyecto. **No es asesoría legal.** Si vas a usar la herramienta con datos de otras personas o como parte de un servicio, consulta a un abogado especializado en protección de datos.

## 1. Software "tal cual", sin garantía

`mxbank` se distribuye bajo la [Licencia Apache 2.0](LICENSE). Conforme a sus secciones 7 y 8:

- Se entrega **"TAL CUAL" (AS IS), sin garantías** de ningún tipo, expresas o implícitas, incluidas las de comerciabilidad, idoneidad para un fin determinado, exactitud o no infracción.
- **En ningún caso el autor ni los contribuidores serán responsables** de daños directos, indirectos, incidentales, especiales o consecuentes (incluidas la pérdida de datos, la exposición de información, las decisiones financieras o fiscales y las sanciones regulatorias) derivados del uso o la imposibilidad de uso del software, en la máxima medida que permita la ley aplicable.
- Quien usa la herramienta **asume todos los riesgos** de su uso.

## 2. No es asesoría financiera, fiscal ni legal

La herramienta extrae y estructura información; **no recomienda ni decide nada**. Los resúmenes, categorías o conclusiones que tú o una IA obtengan a partir de su salida son responsabilidad de quien los produce y los usa.

## 3. Exactitud de los datos

- La extracción puede contener **errores u omisiones**, sobre todo si el banco cambia el formato de sus estados de cuenta. La validación contable (`validation.reconciled`) **reduce ese riesgo, pero no lo elimina**.
- **El documento válido es siempre el estado de cuenta original** emitido por el banco. Antes de cualquier decisión importante (pagos, declaraciones, aclaraciones, trámites), verifica las cifras contra él.

## 4. Privacidad: reduce el riesgo, no lo elimina

- `mxbank` elimina o seudonimiza los datos personales que sabe detectar y, si sospecha que quedó alguno, no emite resultado. Aun así, **ninguna herramienta automática es infalible**: un formato nuevo, un concepto escrito a mano o un error de software pueden dejar pasar información.
- **Revisa la salida antes de compartirla** con terceros o con un servicio de IA (`mxbank audit` ayuda, pero no sustituye tu revisión).
- La salida seudonimizada **puede seguir siendo información personal** en términos legales: los movimientos (montos, fechas, comercios) combinados con otros datos podrían permitir identificar a una persona.
- Al enviar la salida a un servicio de terceros, como un proveedor de IA, esa información queda sujeta a los **términos y políticas de privacidad de ese proveedor**, que el proyecto no controla.

## 5. Uso con datos de otras personas

Si procesas estados de cuenta que **no son tuyos** (clientes, empleados, usuarios de una aplicación), **tú eres responsable** de cumplir la legislación aplicable. Hasta donde sabemos, en México esto incluye la **Ley Federal de Protección de Datos Personales en Posesión de los Particulares** (DOF, 20 de marzo de 2025) y su normativa secundaria, que entre otras cosas exige:

- **consentimiento expreso** del titular para tratar sus datos financieros o patrimoniales;
- un **aviso de privacidad** y finalidades determinadas;
- **medidas de seguridad** administrativas, técnicas y físicas;
- reglas para **transferir o remitir** datos a terceros, por ejemplo a un proveedor de IA que procese la información por tu encargo.

También pueden aplicar obligaciones de confidencialidad contractuales o profesionales (por ejemplo, el secreto profesional de contadores y despachos). Para ese escenario, el proyecto recomienda como mínimo `--privacy strict`.

## 6. Uso permitido

Usa `mxbank` solo con documentos que tengas **derecho legítimo a procesar**. Queda fuera del propósito del proyecto, y bajo exclusiva responsabilidad de quien lo haga, cualquier uso para obtener información de terceros sin autorización, suplantar identidades, cometer fraude o eludir controles de seguridad.

## 7. Relación con bancos y reguladores

- El proyecto **no está afiliado, patrocinado ni respaldado** por BBVA México, BanCoppel ni ninguna otra institución financiera. Sus nombres se usan solo para identificar los formatos que la herramienta puede leer; las marcas pertenecen a sus respectivos titulares.
- `mxbank` **no se conecta a sistemas bancarios**: no usa credenciales, APIs ni extracción de sitios web. Solo lee archivos PDF que el banco ya entregó a su titular. Hasta donde sabemos, por eso no le aplican las disposiciones sobre acceso a sistemas financieros de la Ley para Regular las Instituciones de Tecnología Financiera. Ofrecer la herramienta como parte de un servicio a terceros puede implicar otras obligaciones, que deben evaluarse en cada caso.
- El **secreto bancario** obliga a las instituciones financieras, no al titular de la cuenta respecto de su propia información.

## 8. Reporte de problemas

Si encuentras un caso en el que la herramienta deja pasar información personal, repórtalo de forma privada según [SECURITY.md](SECURITY.md). **Nunca publiques datos reales** (estados de cuenta, salidas JSON o capturas) en issues, pull requests ni discusiones públicas.

## 9. Vigencia

Las referencias legales de este documento son indicativas y reflejan nuestro entendimiento a la fecha de la última revisión. Las leyes y su interpretación cambian; este aviso puede actualizarse sin previo aviso. La versión vigente es la publicada en la rama `main` del repositorio.
