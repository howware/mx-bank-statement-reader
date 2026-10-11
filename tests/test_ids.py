"""Identificadores estables (schema 1.1): statement_id, transactions[].id, installment_plans[].id."""

import hashlib
import hmac
import json
import re
from datetime import date
from decimal import Decimal

import pytest

from mxbank.models.raw import RawStatement, RawTransaction
from mxbank.models.statement import Validation
from mxbank.pipeline import Options, extract_file
from mxbank.privacy.pseudonym import Pseudonymizer
from mxbank.privacy.redactor import Redactor
from mxbank.privacy.residual_scan import scan
from tests.synthetic import bbva, bbva_credit

KEY = b"llave-de-prueba-ids"
ID_RE = re.compile(r"^(TX|ST|PLAN)_[0-9a-f]{16}$")


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory):
    d = tmp_path_factory.mktemp("ids")
    paths = {"debit": d / "debito.pdf", "credit": d / "credito_ago.pdf", "credit_next": d / "credito_sep.pdf"}
    bbva.make(paths["debit"])
    bbva_credit.make(paths["credit"])
    bbva_credit.make(paths["credit_next"], month=1)
    return paths


def _run(path, key=KEY, **opts):
    return extract_file(path, Options(**opts), Pseudonymizer(key) if key else Pseudonymizer())


def _ids(d):
    return {
        "statement": d["statement_id"],
        "tx": [t["id"] for t in d["transactions"]],
        "plans": [p["id"] for p in d["installment_plans"]],
    }


def test_format_and_uniqueness(pdfs):
    for name in pdfs:
        ids = _ids(_run(pdfs[name]))
        flat = [ids["statement"], *ids["tx"], *ids["plans"]]
        assert all(ID_RE.match(i) for i in flat), name
        assert len(set(flat)) == len(flat), name


def test_same_pdf_same_key_same_ids(pdfs):
    for name in pdfs:
        assert _ids(_run(pdfs[name])) == _ids(_run(pdfs[name])), name


def test_ids_do_not_depend_on_privacy_profile_or_concepts(pdfs):
    for name in pdfs:
        base = _ids(_run(pdfs[name]))
        assert _ids(_run(pdfs[name], profile="strict")) == base
        assert _ids(_run(pdfs[name], profile="minimal")) == base
        assert _ids(_run(pdfs[name], include_concepts=True)) == base


def test_different_key_different_ids(pdfs):
    a, b = _ids(_run(pdfs["credit"])), _ids(_run(pdfs["credit"], key=b"otra-llave"))
    assert a["statement"] != b["statement"]
    assert not set(a["tx"]) & set(b["tx"])
    assert not set(a["plans"]) & set(b["plans"])


def test_without_key_ids_only_valid_within_a_run(pdfs):
    a, b = _run(pdfs["credit"], key=None), _run(pdfs["credit"], key=None)
    assert a["privacy"]["pseudonym_scope"] == "run"
    assert _ids(a)["statement"] != _ids(b)["statement"]
    assert not set(_ids(a)["tx"]) & set(_ids(b)["tx"])


def test_identical_movements_same_day_get_distinct_stable_ids(pdfs):
    d = _run(pdfs["credit_next"])
    dup = [t for t in d["transactions"] if t["description"] == "OXXO CENTRO MTY"]
    assert len(dup) == 2 and dup[0]["date"] == dup[1]["date"] and dup[0]["amount"] == dup[1]["amount"]
    assert dup[0]["id"] != dup[1]["id"]
    again = [t["id"] for t in _run(pdfs["credit_next"])["transactions"] if t["description"] == "OXXO CENTRO MTY"]
    assert again == [dup[0]["id"], dup[1]["id"]]


def test_installment_plan_keeps_id_across_consecutive_statements(pdfs):
    aug, sep = _run(pdfs["credit"]), _run(pdfs["credit_next"])
    (p_aug,), (p_sep,) = aug["installment_plans"], sep["installment_plans"]
    # cambian la parcialidad y el saldo; el plan es el mismo
    assert (p_aug["installment_number"], p_sep["installment_number"]) == (2, 3)
    assert p_aug["pending_balance"] != p_sep["pending_balance"]
    assert p_aug["id"] == p_sep["id"]
    # mismo producto, otro periodo: otro estado de cuenta, misma cuenta
    assert aug["statement_id"] != sep["statement_id"]
    assert aug["account"]["account_ref"] == sep["account"]["account_ref"]


def test_same_movement_in_two_overlapping_statements_has_same_id():
    """El id depende de cuenta, fecha, monto y descripción cruda, no del estado ni de su posición."""
    def raw_with(txs, start, end):
        raw = RawStatement(bank="bbva", bank_name="BBVA", product="credit", product_name=None,
                           layout_version="x", confidence=1.0, pages=1, period_start=start, period_end=end)
        raw.header.account_number = "1234567890"
        raw.transactions = txs
        return raw

    def tx(day, amount, text, page):
        return RawTransaction(date=date(2026, 9, day), page=page, first_line=text, description=text,
                              type="card_purchase", debit=Decimal(amount))

    shared = ("OXXO CENTRO", "150.00")
    a = raw_with([tx(10, "50.00", "AMAZON", 1), tx(12, shared[1], shared[0], 1)], date(2026, 9, 1), date(2026, 9, 30))
    b = raw_with([tx(12, shared[1], shared[0], 3)], date(2026, 9, 12), date(2026, 10, 11))
    ids_a = Redactor(a, "standard", Pseudonymizer(KEY), False).build("a.pdf", "0" * 64, Validation(reconciled=True))
    ids_b = Redactor(b, "strict", Pseudonymizer(KEY), False).build("b.pdf", "1" * 64, Validation(reconciled=True))
    assert ids_a.transactions[1].id == ids_b.transactions[0].id
    assert ids_a.statement_id != ids_b.statement_id


def test_ids_are_keyed_hmac_not_plain_hash_and_do_not_leak_account(pdfs):
    d = _run(pdfs["credit"])
    out = json.dumps(d)
    account = bbva_credit.CREDIT_ACCOUNT
    assert account not in out
    # un hash sin llave de los mismos datos (cuenta, fecha, monto, descripción) no reproduce el id
    t = d["transactions"][0]
    for material in (
        f"bbva|credit|{account}|{t['date']}|{t['amount']}|OXXO CENTRO MTY|0",
        "\x1f".join(("mxbank-id/v1", "TX", "bbva", "credit", account, t["date"], t["amount"], "OXXO CENTRO MTY", "0")),
    ):
        assert hashlib.sha256(material.encode()).hexdigest()[:16] not in t["id"]


def test_residual_scan_exempts_only_well_formed_ids():
    ok = {"statement_id": "ST_0123456789abcdef", "transactions": [{"id": "TX_1234567890123456"}]}
    assert scan(ok) == []
    # mismo nombre de campo pero con otro contenido: se escanea normalmente
    assert scan({"transactions": [{"id": "1234567890123456"}]}) == [{"path": "transactions[0].id", "kind": "NUMERO_LARGO"}]
    assert scan({"statement_id": "ST_0123456789ABCDEF 4111111111111111"})
    # formato de id en un campo que no es de id: no se exime
    assert scan({"description": "TX_1234567890123456"}) == [{"path": "description", "kind": "NUMERO_LARGO"}]


def test_residual_scan_still_catches_planted_leak_next_to_ids(pdfs, monkeypatch):
    from mxbank.errors import ResidualPII
    from mxbank.parsers.bbva_credit import BBVACreditParser

    d = _run(pdfs["credit"])
    assert d["privacy"]["residual_scan"] == "passed"
    original = BBVACreditParser._header

    def leaky(self, doc, page, raw):
        original(self, doc, page, raw)
        raw.product_name = f"TARJETA {bbva_credit.CREDIT_ACCOUNT}"

    monkeypatch.setattr(BBVACreditParser, "_header", leaky)
    with pytest.raises(ResidualPII) as exc:
        _run(pdfs["credit"])
    assert {f["path"] for f in exc.value.details} == {"document.product_name"}


def test_account_is_an_input_but_not_visible():
    """La cuenta cambia el id (dos cuentas no comparten ids) sin aparecer en él."""
    def build(account):
        raw = RawStatement(bank="bbva", bank_name="BBVA", product="debit", product_name=None, layout_version="x",
                           confidence=1.0, pages=1, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))
        raw.header.account_number = account
        raw.transactions = [RawTransaction(date=date(2026, 9, 5), page=1, first_line="OXXO", description="OXXO",
                                           type="card_purchase", debit=Decimal("10.00"))]
        return Redactor(raw, "standard", Pseudonymizer(KEY), False).build("x.pdf", "0" * 64, Validation(reconciled=True))

    a, b = build("1111111111"), build("2222222222")
    assert a.transactions[0].id != b.transactions[0].id and a.statement_id != b.statement_id
    assert "1111111111" not in a.model_dump_json()


def test_id_collision_grows_hash():
    p = Pseudonymizer(KEY)
    first = p.ident("TX", "a")
    p._ids[first] = "otro material"  # simula colisión de 64 bits con datos distintos
    second = p.ident("TX", "a")
    assert second.startswith(first) and len(second) == len(first) + 2
    # aun con colisiones en todas las longitudes, termina al llegar al digest completo
    q = Pseudonymizer(KEY)
    digest = q.ident("TX", "b")[3:]
    q._ids.clear()
    material = "".join(("mxbank-id/v1", "TX", "b"))
    full = hmac.new(KEY, material.encode(), hashlib.sha256).hexdigest()
    assert full.startswith(digest)
    for size in range(16, 65, 2):
        q._ids[f"TX_{full[:size]}"] = "otro material"
    assert q.ident("TX", "b") == f"TX_{full}"


def test_cli_warns_on_stderr_without_key_in_batches(pdfs, monkeypatch):
    from typer.testing import CliRunner

    from mxbank.cli import app

    runner = CliRunner()
    files = [str(pdfs["credit"]), str(pdfs["credit_next"])]
    warn = "aviso: sin --pseudonym-key-env"
    assert warn in runner.invoke(app, ["extract", *files]).output
    assert warn in runner.invoke(app, ["extract", files[0], "--ndjson"]).output
    assert warn not in runner.invoke(app, ["extract", files[0]]).output
    monkeypatch.setenv("MXBANK_TEST_KEY", "llave")
    with_key = runner.invoke(app, ["extract", *files, "--pseudonym-key-env", "MXBANK_TEST_KEY"])
    assert with_key.exit_code == 0 and warn not in with_key.output
