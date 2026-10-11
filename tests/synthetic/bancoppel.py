"""Estado de cuenta sintético BanCoppel débito (layout de docs/bancos/bancoppel-cuenta.md). Datos FICTICIOS."""

from __future__ import annotations

from .common import Sheet, make_clabe, make_pan

HOLDER = "JUANITA PEREZ GARCIA"
ACCOUNT = "12345678901"
CLIENT = "123456789"
CLABE = make_clabe("13718000012345678")
ORDERING_CLABE = make_clabe("01218000987654321")
CARD = make_pan("411111222233334")
RFC = "PEGJ" + "800101" + "AB1"
ORDENANTE = "CARLOS RUIZ DIAZ"
BENEFICIARIO = "LAURA MENDEZ SOTO"
STAFF = "ROBERTO GOMEZ SILVA"
DEST_ACCOUNT = "10987654321"
OWN_ACCOUNT = "11223344556"

FAKE_PII = [
    *HOLDER.split(), "INSURGENTES", "FLORIDA", "BENITO", "JUAREZ", "03100", ACCOUNT, CLIENT, CLABE,
    ORDERING_CLABE, CARD, RFC, *ORDENANTE.split(), *BENEFICIARIO.split(), *STAFF.split(), DEST_ACCOUNT,
    OWN_ACCOUNT, "JARDIN", "COLEGIATURA",
]

SOFT_MINUS = "­"
PROMO = "Utiliza tu tarjeta de débito BanCoppel Visa para compras en comercios."


def _footer(s: Sheet) -> None:
    # texto dibujado dos veces en la misma posición (como el PDF real)
    s.put(103, 748, PROMO, 8)
    s.put(103, 748, PROMO, 8)


def _movement_header(s: Sheet, top: float) -> None:
    s.put(32, top, "Detalle de Movimientos")
    s.put(34, top + 16, "Período: 15/ABR./2026 AL 14/MAY./2026")
    s.put(412, top + 16, "Moneda Nacional $")
    for x, label in ((40, "Fecha"), (178, "Descripción"), (356, "Retiros"), (431, "Depósitos"), (524, "Saldo")):
        s.put(x, top + 32, label)


def _tx(s: Sheet, top: float, date: str, first: str, debit: str | None, credit: str | None, balance: str) -> None:
    s.put(41, top, date)
    s.put(80, top, first)
    if debit:
        s.put(420, top, debit, right=True)
    if credit:
        s.put(500, top, credit, right=True)
    s.put(575, top, balance, right=True)


def make(path) -> None:
    s = Sheet(path)
    # --- página 1
    s.put(513, 48, "Hoja 1 de 4")
    s.put(31, 96, HOLDER, 8)
    s.put(31, 104, "AV INSURGENTES SUR 123")
    s.put(404, 110, "ESTADO DE CUENTA")
    s.put(31, 118, "COL FLORIDA")
    s.put(387, 122, "CUENTA EFECTIVA DIGITAL")
    s.put(31, 132, "BENITO JUAREZ")
    s.put(31, 146, "CDMX CIUDAD DE MEXICO C.P.03100")
    s.put(34, 182, "Sucursal: 1234 , AV REFORMA 500, CUAUHTEMOC, CDMX, Tel.")
    s.put(34, 196, "Gerente:")
    s.put(105, 198, STAFF)
    s.put(34, 210, "No. de cliente:")
    s.put(105, 212, CLIENT)
    s.put(35, 242, "Número de Cuenta:")
    s.put(194, 242, ACCOUNT)
    s.put(35, 256, "CLABE:")
    s.put(155, 256, CLABE)
    s.put(273, 274, "GAT Nominal")
    s.put(556, 274, "0.50", right=True)
    s.put(561, 274, "%")
    s.put(227, 276, "03100")
    s.put(35, 278, "Domicilio Fiscal:")
    s.put(273, 288, "GAT Real")
    # reportlab no dibuja U+00AD; el guion suave se prueba en tests/test_normalize.py
    s.put(556, 290, "-3.20", right=True)
    s.put(561, 290, "%")

    # BanCoppel lista del más reciente al más antiguo; el saldo es el posterior al movimiento
    _movement_header(s, 340)
    _tx(s, 388, "05/10", "RECARGA DE TIEMPO AIRE A TRAVÉS DE APP", "100.00", None, "13,403.50")
    s.put(80, 398, "TELCEL RECARGA")
    _tx(s, 418, "05/05", f"TRAS. ENTRE CTAS. {OWN_ACCOUNT}", None, "1,000.00", "13,503.50")
    s.put(80, 428, "Ahorro #12 Mayo '26")
    _tx(s, 448, "05/02", f"TRASPASO EN CUENTA {DEST_ACCOUNT} Jardin", "500.00", None, "12,503.50")
    s.put(80, 458, "abril mayo")
    # movimiento partido entre páginas
    _tx(s, 668, "04/25", "CARGO SPEI 12345678TRANSBPI12345678", "2,000.00", None, "13,003.50")
    s.put(80, 678, "BANCO RECEPTOR: BANORTE")
    _footer(s)
    s.page()

    # --- página 2
    s.put(513, 48, "Hoja 2 de 4")
    _movement_header(s, 74)
    for i, d in enumerate(["FECHA TRANSFERENCIA: 25/04/2026", f"CLABE: {CARD}", f"BENEFICIARIO: {BENEFICIARIO}",
                           "(Dato no verificado por esta Institución)", "REF: 7654321", "CONCEPTO: Renta"]):
        s.put(80, 122 + 10 * i, d)
    _tx(s, 182, "04/20", "ABONO SPEI MBAN01002604200012345678", None, "5,000.00", "15,003.50")
    for i, d in enumerate(["BANCO EMISOR: BBVA MEXICO", "FECHA TRANSFERENCIA: 20/04/2026", f"CLABE: {ORDERING_CLABE}",
                           f"ORDENANTE: {ORDENANTE}", "REF: 1234567", "CONCEPTO: Pago de colegiatura"]):
        s.put(80, 192 + 10 * i, d)
    _tx(s, 262, "04/18", "PAGO DE INTERESES", None, "3.50", "10,003.50")
    s.put(32, 300, "Movimientos en proceso de aclaración del periodo anterior")
    s.put(47, 320, "Fecha")
    s.put(115, 320, "Folio")
    _footer(s)
    s.page()

    # --- página 3: resumen
    s.put(513, 48, "Hoja 3 de 4")
    s.put(34, 102, "Resumen de la Cuenta")
    rows = [
        (116, "Saldo Anterior", "10,000.00"),
        (132, "+ Más Depósitos", "6,000.00"),  # sin intereses
        (148, f"{SOFT_MINUS} Menos Retiros", "2,600.00"),
        (164, "+ Más Intereses del Periodo", "3.50"),
        (180, f"{SOFT_MINUS} Menos Comisiones", "0.00"),
        (196, f"{SOFT_MINUS} Menos IVA Comisiones", "0.00"),
        (212, "Saldo Actual", "13,403.50"),
        (246, "Saldo Promedio Mensual", "11,000.00"),
        (260, "Días del Periodo", "30"),
        (276, "Tasa Bruta Anual Fija", "0.50"),
        (292, "Intereses Ganados", "4.00"),
        (310, f"{SOFT_MINUS} Menos Retención", "0.50"),
        (326, "Intereses del Periodo", "3.50"),
    ]
    for top, label, value in rows:
        s.put(36, top, label)
        s.put(270, top, value, right=True)
    s.put(35, 232, "Cálculo de Intereses")
    _footer(s)
    s.page()

    # --- página 4: CFDI
    s.put(513, 48, "Hoja 4 de 4")
    s.put(71, 96, "EMISOR", 7)
    s.put(309, 98, "RECEPTOR", 7)
    s.put(31, 132, "BANCOPPEL, S.A. INSTITUCION DE BANCA MULTIPLE", 7)
    s.put(272, 134, HOLDER, 7)
    s.put(272, 140, f"RFC: {RFC}", 7)
    s.put(272, 148, f"Número de Crédito: {ACCOUNT}", 7)
    s.put(272, 156, "INSURGENTES SUR 123", 7)
    s.put(272, 166, "COL FLORIDA BENITO JUAREZ", 7)
    s.put(223, 198, "Número de Certificado del Emisor:", 7)
    _footer(s)
    s.save()
