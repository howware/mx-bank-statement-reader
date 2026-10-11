import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import layout_dump  # noqa: E402

FAKE_PII = [
    "JUANITA",
    "PÉREZ",
    "GARCÍA",
    "PEGJ800101AB1",
    "4152313412345678",
    "012180001234567891",
    "INSURGENTES",
    "06700",
    "juanita@example.com",
]


def _make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(40, 750, "BBVA MEXICO ESTADO DE CUENTA TARJETA DE CREDITO")
    c.drawString(40, 730, "JUANITA PÉREZ GARCÍA")
    c.drawString(40, 715, "AV INSURGENTES SUR 1234 COL DEL VALLE C.P. 06700")
    c.drawString(40, 700, "RFC: PEGJ800101AB1  juanita@example.com")
    c.drawString(40, 685, "Número de tarjeta: 4152313412345678  CLABE 012180001234567891")
    c.drawString(40, 660, "Fecha de corte: 10-SEP-2026   Pago mínimo: $1,520.00")
    c.drawString(40, 640, "12-AGO OXXO SUC 1234        85.50")
    c.save()


def test_dump_masks_pii(tmp_path):
    pdf = tmp_path / "fake.pdf"
    _make_pdf(pdf)
    out = "\n".join(layout_dump.dump(pdf, None))

    for value in FAKE_PII:
        assert value.upper() not in out.upper(), value
    # el vocabulario y los formatos se conservan
    assert "BBVA" in out and "corte" in out and "99-SEP-9999" in out
    assert "$9,999.99" in out and "99.99" in out


def test_reveal_tx_first_line_keeps_digits_masked(tmp_path):
    pdf = tmp_path / "fake.pdf"
    _make_pdf(pdf)
    out = "\n".join(layout_dump.dump(pdf, None, reveal_tx_first_line=True))

    assert ":99-AGO" in out and ":OXXO" in out  # renglón que inicia con fecha 99-MES: se revela
    for value in FAKE_PII:
        assert value.upper() not in out.upper(), value


def test_reveal_row_starting_with_tx_date(tmp_path):
    pdf = tmp_path / "tx.pdf"
    c = canvas.Canvas(str(pdf), pagesize=letter)
    c.drawString(15, 700, "05/AGO 05/AGO SPEI ENVIADO SANTANDER 1,234.56")
    c.drawString(106, 690, "JUANITA PEREZ 012180001234567891")
    c.save()
    out = "\n".join(layout_dump.dump(pdf, None, reveal_tx_first_line=True))

    assert all(f":{w}" in out for w in ("99/AGO", "SPEI", "ENVIADO", "SANTANDER"))
    assert "9,999.99" in out
    assert "JUANITA" not in out and "PEREZ" not in out


def test_reveal_numeric_tx_date(tmp_path):
    pdf = tmp_path / "coppel.pdf"
    c = canvas.Canvas(str(pdf), pagesize=letter)
    c.drawString(41, 700, "05/09 CARGO SPEI 12345ABC 1,234.56")
    c.drawString(80, 690, "BENEFICIARIO: JUANITA PEREZ")
    c.save()
    out = "\n".join(layout_dump.dump(pdf, None, reveal_tx_first_line=True))

    assert ":99/99" in out and ":CARGO" in out and ":99999ABC" in out
    assert "JUANITA" not in out and "PEREZ" not in out
