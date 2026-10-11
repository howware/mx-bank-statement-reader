import json
import re

import pytest

from mxbank.errors import ResidualPII
from mxbank.loader import load_pdf
from mxbank.parsers import detect
from mxbank.parsers.bbva_debit import BBVADebitParser
from mxbank.pipeline import Options, extract_file
from mxbank.text import norm
from tests.synthetic import bancoppel, bbva


@pytest.fixture(scope="module")
def bbva_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("bbva") / "bbva_sintetico.pdf"
    bbva.make(path)
    return path


@pytest.fixture(scope="module")
def coppel_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("coppel") / "bancoppel_sintetico.pdf"
    bancoppel.make(path)
    return path


def _assert_no_leak(data: dict, fake_pii: list[str]) -> None:
    out = norm(json.dumps(data, ensure_ascii=False))
    for value in fake_pii:
        assert norm(value) not in out, value


# -- detección -----------------------------------------------------------------

def test_detection_picks_the_right_bank(bbva_pdf, coppel_pdf):
    assert detect(load_pdf(bbva_pdf))[0][0].bank == "bbva"
    assert detect(load_pdf(coppel_pdf))[0][0].bank == "bancoppel"


# -- BBVA ----------------------------------------------------------------------

def test_bbva_summary_and_period(bbva_pdf):
    d = extract_file(bbva_pdf, Options())
    assert d["document"]["bank"] == "bbva"
    assert d["document"]["product_name"] == "TARJETA NOMINA BASICA"
    assert d["period"] == {"start": "2026-08-15", "end": "2026-09-14", "statement_date": "2026-09-14", "days": 31}
    s = d["summary"]
    assert s["opening_balance"] == "5000.00"
    assert s["closing_balance"] == "7450.00"
    assert s["total_credits"] == "20000.00" and s["credits_count"] == 2
    assert s["total_debits"] == "17550.00" and s["debits_count"] == 5
    assert s["average_balance"] == "12345.67"
    assert d["account"]["account_last4"] == "6789"
    assert d["account"]["holder_type"] == "individual"


def test_bbva_transactions(bbva_pdf):
    d = extract_file(bbva_pdf, Options())
    txs = d["transactions"]
    assert [t["type"] for t in txs] == [
        "spei_in", "spei_out", "cash_withdrawal", "transfer_out", "cash_withdrawal", "cash_withdrawal", "cash_deposit",
    ]
    assert [t["amount"] for t in txs] == ["16000.00", "-3000.00", "-50.00", "-500.00", "-13000.00", "-1000.00", "4000.00"]
    assert txs[0]["counterparty_bank"] == "BANORTE"
    assert txs[1]["counterparty_ref"].startswith("PERSONA_")
    assert txs[3]["counterparty_account_ref"].startswith("CUENTA_")
    assert txs[4]["merchant"] == "OXXO" and txs[4]["description"] == "OXXO CASH"
    assert txs[5]["description"] == "DISPOSICION DE EFECTIVO"
    assert txs[1]["date"] == "2026-08-16" and txs[3]["date"] == "2026-09-05"
    assert all(t["concept"] is None for t in txs)


def test_bbva_validation(bbva_pdf):
    v = extract_file(bbva_pdf, Options())["validation"]
    assert v["reconciled"] is True and v["difference"] == "0.00"
    assert v["bank_totals_match"] is True
    assert v["running_balance_checked"] == 7 and v["running_balance_errors"] == 0


def test_bbva_no_leak(bbva_pdf):
    d = extract_file(bbva_pdf, Options())
    _assert_no_leak(d, bbva.FAKE_PII)
    assert d["privacy"]["removed"]["holder_name"] == 2  # encabezado + CFDI
    assert d["privacy"]["residual_scan"] == "passed"


def test_bbva_include_concepts_is_redacted(bbva_pdf):
    d = extract_file(bbva_pdf, Options(include_concepts=True))
    concepts = [t["concept"] for t in d["transactions"]]
    assert concepts[1] == "RENTA AGOSTO 16 AGO [NUM]"
    _assert_no_leak(d, [p for p in bbva.FAKE_PII if p not in ("RENTA", "PEDRO")])


def test_bbva_strict_profile(bbva_pdf):
    d = extract_file(bbva_pdf, Options(profile="strict"))
    assert d["account"]["account_last4"] is None
    assert d["source"]["file_name"] is None and d["source"]["file_sha256"] is None


def test_stable_pseudonyms_with_key(bbva_pdf):
    from mxbank.privacy.pseudonym import Pseudonymizer

    a = extract_file(bbva_pdf, Options(), Pseudonymizer(b"llave-de-prueba"))
    b = extract_file(bbva_pdf, Options(), Pseudonymizer(b"llave-de-prueba"))
    c = extract_file(bbva_pdf, Options(), Pseudonymizer(b"otra-llave"))
    assert a["account"]["account_ref"] == b["account"]["account_ref"] != c["account"]["account_ref"]
    assert a["privacy"]["pseudonym_scope"] == "key"


def test_residual_scan_fails_closed(bbva_pdf, monkeypatch):
    original = BBVADebitParser._header

    def leaky_header(self, doc, raw):
        original(self, doc, raw)
        raw.product_name = bbva.HOLDER  # simula un bug que copia el nombre a un campo no redactado

    monkeypatch.setattr(BBVADebitParser, "_header", leaky_header)
    with pytest.raises(ResidualPII) as exc:
        extract_file(bbva_pdf, Options())
    assert exc.value.details == [{"path": "document.product_name", "kind": "DICCIONARIO"}]
    assert bbva.HOLDER not in json.dumps(exc.value.to_dict())


# -- BanCoppel -------------------------------------------------------------------

def test_coppel_summary(coppel_pdf):
    d = extract_file(coppel_pdf, Options())
    assert d["document"]["bank"] == "bancoppel"
    assert d["period"]["start"] == "2026-04-15" and d["period"]["end"] == "2026-05-14"
    assert d["period"]["days"] == 30
    s = d["summary"]
    assert s["opening_balance"] == "10000.00" and s["closing_balance"] == "13403.50"
    assert s["total_credits"] == "6000.00" and s["total_debits"] == "2600.00"
    assert s["interest_earned"] == "3.50" and s["tax_withheld"] == "0.50"
    assert s["average_balance"] == "11000.00"
    assert d["rates"]["gat_real_percent"] == "-3.20"  # signo con guion suave U+00AD


def test_coppel_transactions(coppel_pdf):
    d = extract_file(coppel_pdf, Options())
    txs = d["transactions"]
    assert [t["type"] for t in txs] == [
        "interest", "spei_in", "spei_out", "transfer_out", "transfer_internal", "mobile_topup",
    ]
    assert [t["amount"] for t in txs] == ["3.50", "5000.00", "-2000.00", "-500.00", "1000.00", "-100.00"]
    assert txs[1]["counterparty_bank"] == "BBVA MEXICO"
    assert txs[1]["counterparty_ref"].startswith("PERSONA_") and txs[1]["value_date"] == "2026-04-20"
    # movimiento partido entre páginas: el detalle de la página 2 se asocia al cargo SPEI
    assert txs[2]["counterparty_bank"] == "BANORTE" and txs[2]["counterparty_ref"].startswith("PERSONA_")
    assert txs[3]["description"] == "TRASPASO EN CUENTA"
    assert txs[1]["date"] == "2026-04-20" and txs[5]["date"] == "2026-05-10"


def test_coppel_validation(coppel_pdf):
    v = extract_file(coppel_pdf, Options())["validation"]
    assert v["reconciled"] is True
    assert v["bank_totals_match"] is True
    assert v["running_balance_checked"] == 6 and v["running_balance_errors"] == 0


def test_coppel_no_leak(coppel_pdf):
    d = extract_file(coppel_pdf, Options())
    _assert_no_leak(d, bancoppel.FAKE_PII)
    assert d["privacy"]["removed"]["branch_staff"] == 1


def test_coppel_include_concepts(coppel_pdf):
    d = extract_file(coppel_pdf, Options(include_concepts=True))
    concepts = [t["concept"] for t in d["transactions"]]
    assert concepts[1] == "PAGO DE COLEGIATURA"
    assert concepts[3] == "JARDIN ABRIL MAYO"  # concepto que empieza en la primera línea
    _assert_no_leak(d, [p for p in bancoppel.FAKE_PII if p not in ("JARDIN", "COLEGIATURA")])


# -- BBVA tarjeta de crédito -------------------------------------------------------

@pytest.fixture(scope="module")
def tdc_pdf(tmp_path_factory):
    from tests.synthetic import bbva_credit

    path = tmp_path_factory.mktemp("tdc") / "bbva_tdc_sintetico.pdf"
    bbva_credit.make(path)
    return path


def test_tdc_detected_as_credit(tdc_pdf, bbva_pdf):
    assert (detect(load_pdf(tdc_pdf))[0][0].bank, detect(load_pdf(tdc_pdf))[0][0].product) == ("bbva", "credit")
    assert detect(load_pdf(bbva_pdf))[0][0].product == "debit"
    assert extract_file(tdc_pdf, Options(bank="bbva"))["document"]["product"] == "credit"


def test_tdc_credit_block(tdc_pdf):
    d = extract_file(tdc_pdf, Options())
    c = d["credit"]
    assert c["cut_off_date"] == "2026-09-14" and c["payment_due_date"] == "2026-10-08"
    assert c["no_interest_payment"] == "1965.00" and c["minimum_payment"] == "900.00"
    assert c["minimum_payment_with_installments"] == "1500.00"
    assert c["previous_balance"] == "15000.00" and c["payments_and_credits"] == "16000.00"
    assert c["interest_charged"] == "100.00" and c["vat_on_interest_and_fees"] == "16.00"
    assert c["credit_limit"] == "50000.00" and c["available_credit"] == "45535.00"
    assert c["cat_percent"] == "75.3" and c["annual_interest_rate_percent"] == "52.00"
    assert d["document"]["product_name"] == "TARJETA AZUL BBVA (CREDITO)"
    assert d["period"]["days"] == 31


def test_tdc_installment_plans(tdc_pdf):
    plans = extract_file(tdc_pdf, Options())["installment_plans"]
    assert re.fullmatch(r"PLAN_[0-9a-f]{16}", plans[0].pop("id"))
    assert plans == [{
        "description": "E TICKET", "start_date": "2026-07-10", "original_amount": "3000.00",
        "pending_balance": "2500.00", "required_payment": "500.00", "installment_number": 2,
        "installments_total": 6, "interest_rate_percent": "0.00",
    }]


def test_tdc_transactions(tdc_pdf):
    txs = extract_file(tdc_pdf, Options())["transactions"]
    assert [t["type"] for t in txs] == [
        "card_purchase", "card_purchase", "card_purchase", "card_payment", "installment",
        "installment_conversion", "installment_conversion", "fee", "card_purchase",
    ]
    assert [t["amount"] for t in txs][:4] == ["-150.00", "-1200.00", "-299.00", "13000.00"]
    assert txs[0]["description"] == "OXXO CENTRO MTY" and txs[0]["merchant"] == "OXXO"
    assert txs[1]["description"] == "AMAZON" and txs[1]["card_type"] == "digital"
    assert (txs[2]["original_currency"], txs[2]["original_amount"], txs[2]["exchange_rate"]) == ("USD", "15.00", "19.93")
    assert (txs[4]["installment_number"], txs[4]["installments_total"], txs[4]["description"]) == (2, 6, "E TICKET")
    assert txs[8]["description"] == "TACOS [DATO]"  # apellidos del titular en el comercio (colapsados)


def test_tdc_validation_and_no_leak(tdc_pdf):
    from tests.synthetic import bbva_credit

    d = extract_file(tdc_pdf, Options())
    assert d["validation"]["reconciled"] is True and d["validation"]["difference"] == "0.00"
    assert d["validation"]["bank_totals_match"] is True
    assert d["privacy"]["removed"]["card_number"] == 1
    _assert_no_leak(d, bbva_credit.FAKE_PII)
