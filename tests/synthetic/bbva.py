"""Estado de cuenta sintético BBVA débito (layout de docs/bancos/bbva-cuenta.md). Datos FICTICIOS."""

from __future__ import annotations

from .common import Sheet, make_clabe

HOLDER = "JUANITA PEREZ GARCIA"
ADDRESS = ["AV INSURGENTES SUR 123 A", "COL FLORIDA", "ALCALDIA BENITO JUAREZ", "CDMX MEXICO CP 03100"]
ACCOUNT = "0123456789"
CLIENT = "12345678"
RFC = "PEGJ" + "800101" + "AB1"
CLABE = make_clabe("01218000123456789")
COUNTERPARTY = "MARIA LOPEZ HERNANDEZ"
THIRD_PARTY_ACCOUNT = "0987654321"
PHONE = "9876543210"
TRACKING = "MBAN" + "01002608160012345678"
CONCEPT = "Renta agosto"

FAKE_PII = [
    *HOLDER.split(), "INSURGENTES", "FLORIDA", "BENITO", "JUAREZ", "03100", ACCOUNT, CLIENT, RFC, CLABE,
    *COUNTERPARTY.split(), THIRD_PARTY_ACCOUNT, PHONE, TRACKING, "PEDRO", "RENTA",
]

# (oper, liq, primera línea, cargo, abono, saldo, detalles, solo_fechas)
TXS = [
    ("15/AGO", "15/AGO", "SPEI RECIBIDOBANORTE", None, "16,000.00", "21,000.00",
     ["0012345"], False),
    ("16/AGO", "16/AGO", "SPEI ENVIADO SANTANDER", "3,000.00", None, "18,000.00",
     [f"0098765{CONCEPT} 16 Ago 2026", "12345678901234567890", TRACKING, COUNTERPARTY], False),
    ("17/AGO", "17/AGO", "RET CAJ OTRO BCO COM IVA", "50.00", None, "17,950.00",
     ["AGO17 10:30 BNM A123 FOLIO:4321"], True),
    ("05/SEP", "05/SEP", "PAGO CUENTA DE TERCERO", "500.00", None, "17,450.00",
     [f"BNET {THIRD_PARTY_ACCOUNT} Prestamo a Pedro"], False),
    ("06/SEP", "06/SEP", "OXXOINSURGENTES CDMX CASH", "13,000.00", None, "4,450.00",
     ["RFC: CCO " + "8605231N4" + " 10:11 AUT: 123456"], False),
    ("10/SEP", "10/SEP", f"{PHONE}DISPOS.EFECTIVO", "1,000.00", None, "3,450.00",
     ["BMOV A12"], False),
    ("12/SEP", "12/SEP", "SU PAGO EN EFECTIVO", None, "4,000.00", "7,450.00",
     ["EN PRACTICAJA"], False),
]


def _page_header(s: Sheet, page: int, pages: int, top0: float) -> None:
    s.put(511, top0, "Estado de Cuenta", 12)
    s.put(453, top0 + 14, "TARJETA NOMINA BASICA BBVA", 11)
    s.put(550, top0 + 26, f"PAGINA {page} / {pages}", 9)


def _footer(s: Sheet) -> None:
    s.put(15, 764, "BBVA MEXICO, S.A., INSTITUCION DE BANCA MULTIPLE, GRUPO FINANCIERO BBVA MEXICO")


def _tx(s: Sheet, top: float, t) -> float:
    oper, liq, first, debit, credit, balance, details, dates_only = t
    s.put(15, top, oper)
    s.put(59, top, liq)
    if dates_only:
        top += 2
        s.put(107, top, first, 9.5)
    else:
        s.put(107, top, first)
    if debit:
        s.put(420, top + 2, debit, 8.5, right=True)
    if credit:
        s.put(465, top + 2, credit, 8.5, right=True)
    s.put(520, top + 2, balance, 8.5, right=True)
    s.put(600, top + 2, balance, 8.5, right=True)
    top += 12
    for d in details:
        s.put(106, top, d, 9.5)
        top += 10
    s.put(319, top - 10 if details else top, "Referencia")
    s.put(367, top - 10 if details else top, "0012345678")
    return top + 12


def make(path) -> None:
    s = Sheet(path)
    # --- página 1
    _page_header(s, 1, 3, 2)
    s.put(319, 48, "Periodo")
    s.put(481, 48, "DEL 15/08/2026 AL 14/09/2026")
    s.put(318, 64, "Fecha de Corte")
    s.put(555, 64, "14/09/2026")
    s.put(318, 78, "No. de Cuenta")
    s.put(550, 78, ACCOUNT)
    s.put(318, 94, "No. de Cliente")
    s.put(559, 94, CLIENT)
    s.put(41, 102, HOLDER)
    s.put(318, 108, "R.F.C")
    s.put(532, 108, RFC)
    for top, line in zip((114, 124, 136, 148), ADDRESS, strict=False):
        s.put(41, top, line)
    s.put(318, 124, "No. Cuenta CLABE")
    s.put(507, 124, f"{CLABE[:3]} {CLABE[3:6]} {CLABE[6:17]} {CLABE[17]}")
    s.put(318, 142, "SUCURSAL:")
    s.put(376, 142, "1234 PALMAS PRINCIPAL")
    s.put(318, 154, "DIRECCION:")
    s.put(410, 160, "AV. REFORMA 123 COL. TABACALERA")
    s.put(318, 176, "PLAZA:")
    s.put(410, 176, "POLANCO")
    s.put(318, 190, "TELEFONO:")
    s.put(410, 190, "5551234")

    s.put(10, 222, "Información Financiera", 12)
    s.put(465, 222, "MONEDA NACIONAL", 12)
    rows = [
        (260, "Saldo Promedio", "12,345.67", "Saldo Anterior", None, "5,000.00"),
        (274, "Días del Periodo", "31", "Depósitos / Abonos (+)", "2", "20,000.00"),
        (288, "Tasa Bruta Anual %", "0.000", "Retiros / Cargos (-)", "5", "17,550.00"),
        (302, "Saldo Promedio Gravable", "0.00", "Saldo Final", None, "7,450.00"),
        (316, "Intereses a Favor (+)", "0.00", "Saldo Promedio Mínimo Mensual:", None, "0.00"),
        (330, "ISR Retenido (-)", "0.00", None, None, None),
        (386, "Total Comisiones", "0.00", None, None, None),
    ]
    for top, ll, lv, rl, rc, rv in rows:
        s.put(11, top, ll)
        s.put(298, top, lv, right=True)
        if rl:
            s.put(308, top, rl)
            if rc:
                s.put(475, top, rc, right=True)
            s.put(590, top, rv, right=True)
    s.put(9, 484, "Detalle de Movimientos Realizados", 12)
    s.put(39, 514, "FECHA")
    s.put(519, 514, "SALDO")
    for x, label in ((21, "OPER"), (70, "LIQ"), (105, "DESCRIPCION"), (321, "REFERENCIA"),
                     (381, "CARGOS"), (427, "ABONOS"), (469, "OPERACION"), (536, "LIQUIDACION")):
        s.put(x, 524, label)
    top = 540
    for t in TXS[:3]:
        top = _tx(s, top, t)
    s.put(15, 752, "La GAT Real es el rendimiento que obtendría después de descontar la inflación")
    _footer(s)
    s.page()

    # --- página 2
    _page_header(s, 2, 3, 32)
    s.put(335, 98, "No. de Cuenta")
    s.put(545, 98, ACCOUNT)
    s.put(336, 116, "No. de Cliente")
    s.put(555, 116, CLIENT)
    top = 154
    for t in TXS[3:]:
        top = _tx(s, top, t)
    s.put(9, top + 10, "Total de Movimientos", 12)
    s.put(26, top + 34, "TOTAL IMPORTE CARGOS")
    s.put(290, top + 34, "17,550.00", right=True)
    s.put(316, top + 34, "TOTAL MOVIMIENTOS CARGOS")
    s.put(581, top + 34, "5")
    s.put(26, top + 48, "TOTAL IMPORTE ABONOS")
    s.put(290, top + 48, "20,000.00", right=True)
    s.put(317, top + 48, "TOTAL MOVIMIENTOS ABONOS")
    s.put(585, top + 48, "2")
    _footer(s)
    s.page()

    # --- página 3: CFDI
    _page_header(s, 3, 3, 22)
    s.put(11, 158, "Nombre del Receptor :")
    s.put(121, 160, HOLDER, 9)
    s.put(11, 170, "Código Postal de Domicilio Fiscal : 03100")
    s.put(13, 242, "Folio Fiscal:", 9)
    s.put(10, 256, "AB12CD3E-4F56-7890-A12B-CD345E67FGH8")
    _footer(s)
    s.save()
