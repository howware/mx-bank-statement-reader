"""Estado de cuenta sintético BBVA tarjeta de crédito (layout de docs/bancos/bbva-credito.md). Datos FICTICIOS.

Las cifras respetan las reglas observadas en estados reales:
- adeudo anterior + cargos − abonos (sin "ALTA PARA MESES") + intereses + IVA = saldo de cargos regulares
- "TOTAL CARGOS" no incluye las comisiones

``make(path, month=1)`` genera el estado del mes siguiente: misma cuenta, mismo plan a meses
(ahora en la parcialidad 3 de 6) y dos compras idénticas el mismo día.
"""

from __future__ import annotations

from .common import Sheet, make_clabe, make_pan

HOLDER = "JUANITA PEREZ GARCIA"
CARD = make_pan("455555666677772")
CLABE = make_clabe("01218000555566667")
CLIENT = "12345678"
CREDIT_ACCOUNT = "9876543210"
RFC = "PEGJ" + "800101" + "AB1"
LAST4 = CARD[-4:]

FAKE_PII = [*HOLDER.split(), "INSURGENTES", "FLORIDA", "BENITO", "JUAREZ", "03100", CARD, CLABE, CLIENT,
            CREDIT_ACCOUNT, RFC, f"***{LAST4}"]

DIGITAL = f" ; Tarjeta Digital ***{LAST4}"
# (operación, cargo, descripción, signo, monto, renglón extra)
TXS = [
    ("16-ago-2026", "16-ago-2026", "OXXO CENTRO MTY", "+", "$150.00", None),
    ("18-ago-2026", "18-ago-2026", f"AMAZON{DIGITAL}", "+", "$1,200.00", None),
    ("20-ago-2026", "20-ago-2026", f"NETFLIX{DIGITAL}", "+", "$299.00", "USD $15.00 TIPO DE CAMBIO $19.93"),
    ("25-ago-2026", "25-ago-2026", "BMOVIL.PAGO TDC", "-", "$13,000.00",
     "IVA : $ 16.00 Interes: $ 100.00 Comisiones:$0.00 Capital:$12,884.00"),
    ("01-sep-2026", "01-sep-2026", f"02 DE 06 E TICKET{DIGITAL}", "+", "$500.00", None),
    ("05-sep-2026", "05-sep-2026", "ALTA PARA MESES S/INTERESES", "+", "$3,000.00", None),
    ("05-sep-2026", "05-sep-2026", "ABONO FINANC. COMPRAS 06MSI", "-", "$3,000.00", None),
    ("07-sep-2026", "07-sep-2026", "COMISION ANUALIDAD", "+", "$600.00", None),
    ("10-sep-2026", "10-sep-2026", "TACOS PEREZ GARCIA", "+", "$100.00", None),
]

# mes siguiente: dos compras idénticas el mismo día (duplicado legítimo)
TXS_NEXT = [
    ("16-sep-2026", "16-sep-2026", "OXXO CENTRO MTY", "+", "$150.00", None),
    ("16-sep-2026", "16-sep-2026", "OXXO CENTRO MTY", "+", "$150.00", None),
    ("20-sep-2026", "20-sep-2026", f"NETFLIX{DIGITAL}", "+", "$299.00", "USD $15.00 TIPO DE CAMBIO $19.93"),
    ("01-oct-2026", "01-oct-2026", f"03 DE 06 E TICKET{DIGITAL}", "+", "$500.00", None),
    ("05-oct-2026", "05-oct-2026", "BMOVIL.PAGO TDC", "-", "$1,965.00", None),
]

# cifras por mes (adeudo anterior = saldo de cargos regulares del mes previo)
MONTHS = {
    0: dict(
        txs=TXS, period="15-ago-2026 al 14-sep-2026", cut="14-sep-2026", due="jueves, 08-oct-2026",
        no_interest="$1,965.00", min_msi="$1,500.00", minimum="$900.00",
        summary=["$15,000.00", "$1,749.00", "$500.00", "$100.00", "$600.00", "$16.00", "$16,000.00", "$1,965.00"],
        balances=["$1,965.00", "$2,500.00", "$4,465.00", "$50,000.00", "$45,535.00"],
        plan=("$3,000.00", "$2,500.00", "$500.00", "2 de 6"), totals=("$5,249.00", "-$16,000.00"),
    ),
    1: dict(
        txs=TXS_NEXT, period="15-sep-2026 al 14-oct-2026", cut="14-oct-2026", due="lunes, 09-nov-2026",
        no_interest="$1,099.00", min_msi="$800.00", minimum="$300.00",
        summary=["$1,965.00", "$599.00", "$500.00", "$0.00", "$0.00", "$0.00", "$1,965.00", "$1,099.00"],
        balances=["$1,099.00", "$2,000.00", "$3,099.00", "$50,000.00", "$46,901.00"],
        plan=("$3,000.00", "$2,000.00", "$500.00", "3 de 6"), totals=("$1,099.00", "-$1,965.00"),
    ),
}


def _footer(s: Sheet) -> None:
    s.put(13, 760, "Notas: Las notas en la columna “NOTAS ACLARATORIAS” en este estado de cuenta.", 9)


def _page_header(s: Sheet, n: int) -> None:
    s.put(14, 46, f"Número de cuenta: XXXXXX{CREDIT_ACCOUNT[-4:]}", 9)
    s.put(536, 46, f"Página {n} de 4", 9)


def make(path, month: int = 0) -> None:
    m = MONTHS[month]
    s = Sheet(path)
    # --- página 1: publicidad
    s.put(21, 100, "Tu tarjeta de crédito te da Puntos BBVA en cada compra")
    s.put(14, 732, "BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE, GRUPO FINANCIERO BBVA MEXICO.", 9)
    s.page()

    # --- página 2: encabezado y resumen
    s.put(530, 42, "Página 2 de 4", 9)
    s.put(366, 58, "TU PAGO REQUERIDO ESTE PERIODO", 9)
    s.put(20, 64, HOLDER, 9)
    s.put(309, 80, "Periodo:", 9)
    s.put(476, 80, m["period"], 9)
    s.put(20, 86, "Calle: AV INSURGENTES SUR 123 A", 9)
    s.put(309, 94, "Fecha de corte:", 9)
    s.put(539, 94, m["cut"], 9)
    s.put(20, 96, "Colonia: FLORIDA", 9)
    s.put(20, 106, "ALCALDIA BENITO JUAREZ ,CIUDAD DE MEXICO", 9)
    s.put(309, 106, "Número de días en el periodo", 9)
    s.put(560, 106, "31 días", 9)
    s.put(20, 116, "CP: 03100", 9)
    s.put(498, 132, m["due"])
    s.put(309, 136, "Fecha límite de pago:")
    s.put(20, 148, "TARJETA AZUL BBVA (CREDITO)")
    s.put(590, 150, m["no_interest"], right=True)
    s.put(309, 152, "Pago para no generar intereses:")
    s.put(20, 158, f"Número de tarjeta: {CARD}", 9)
    s.put(20, 168, f"Número de cliente:{CLIENT}", 9)
    s.put(309, 174, "Pago mínimo + compras y cargo diferidos a meses:", 9)
    s.put(590, 174, m["min_msi"], 9, right=True)
    s.put(20, 180, f"R.F.C: {RFC}", 9)
    s.put(309, 188, "Pago mínimo:", 9)
    s.put(590, 188, m["minimum"], 9, right=True)
    s.put(20, 190, f"CLABE: {CLABE}", 9)
    s.put(20, 200, "Sucursal: PALMAS PLAZA, 1234", 9)

    s.put(60, 374, "RESUMEN DE CARGOS Y ABONOS DEL PERIODO", 9)
    s.put(326, 374, "INFORMACION DEL COSTO ANUAL TOTAL DE LA TARJETA", 9)
    left = [
        (392, "Adeudo del periodo anterior"),
        (408, "Cargos regulares (no a meses) +"),
        (424, "Cargos compras a meses (capital) +"),
        (440, "Monto de intereses +"),
        (456, "Monto de comisiones +"),
        (470, "IVA de intereses y comisiones +"),
        (486, "Pagos y abonos -"),  # incluye ABONO FINANC.
        (506, "PAGO PARA NO GENERAR INTERESES"),
    ]
    for (top, label), value in zip(left, m["summary"], strict=True):
        s.put(24, top, label, 9)
        s.put(260, top, value, 9, right=True)
    s.put(321, 392, "Monto de intereses pagados en los últimos 12 meses:", 9)
    s.put(590, 392, "$1,100.00", 9, right=True)
    s.put(339, 478, "CAT:", 9)
    s.put(417, 478, "TASA DE INTERES ANUAL ORDINARIA", 9)
    s.put(323, 498, "75.3% Sin IVA", 9)
    s.put(485, 498, "52.00%", 9)
    right = [
        (602, "Saldo cargos regulares:"),
        (620, "Saldo cargo a meses:"),
        (636, "Saldo deudor total:"),
        (652, "Límite de crédito:"),
        (668, "Crédito disponible:"),
    ]
    for (top, label), value in zip(right, m["balances"], strict=True):
        s.put(323, top, label, 9)
        s.put(585, top, value, 9, right=True)
    s.put(14, 744, "Notas: Todos los importes están expresados en moneda nacional.")
    s.page()

    # --- página 3: meses sin intereses y movimientos regulares
    _page_header(s, 3)
    s.put(22, 70, "COMPRAS Y CARGOS DIFERIDOS A MESES SIN INTERESES", 9)
    s.put(435, 70, f"Tarjeta titular: XXXXXXXXXXXX{LAST4}", 9)
    s.put(21, 104, "Fecha de la", 9)
    s.put(165, 108, "Descripción", 9)
    s.put(19, 142, "10-jul-2026", 9)
    s.put(123, 142, f"E TICKET{DIGITAL}", 9)
    for x, v in zip((360, 418, 476), m["plan"][:3], strict=True):
        s.put(x, 142, v, 9, right=True)
    s.put(497, 142, m["plan"][3], 9)
    s.put(555, 142, "0.00%", 9)

    s.put(26, 200, "CARGOS,COMPRAS Y ABONOS REGULARES(NO A MESES)", 9)
    s.put(430, 200, f"Tarjeta titular: XXXXXXXXXXXX{LAST4}", 9)
    s.put(290, 234, "Descripción del movimiento", 9)
    top = 260
    for oper, cargo, desc, sign, amount, extra in m["txs"]:
        s.put(35, top, oper, 9)
        s.put(122, top, cargo, 9)
        s.put(203, top, desc, 9)
        s.put(516 if sign == "+" else 540, top, sign, 9)
        s.put(590, top, amount, 9, right=True)
        top += 16
        if extra:
            s.put(203 if extra.startswith("USD") else 230, top - 2, extra, 9)
            top += 14
    s.put(435, top + 4, "TOTAL CARGOS", 9)
    s.put(590, top + 4, m["totals"][0], 9, right=True)
    s.put(435, top + 20, "TOTAL ABONOS", 9)
    s.put(590, top + 20, m["totals"][1], 9, right=True)
    _footer(s)
    s.page()

    # --- página 4: CFDI
    s.put(546, 30, "Página 4 / 4", 9)
    s.put(391, 90, "Crédito", 9)
    s.put(544, 90, CREDIT_ACCOUNT, 9)
    s.put(391, 104, "No. de Cliente", 9)
    s.put(554, 104, CLIENT, 9)
    s.put(17, 130, f"Nombre del Receptor: {HOLDER}", 9)
    s.put(17, 140, "Código Postal de Domicilio Fiscal: 03100", 9)
    s.save()
