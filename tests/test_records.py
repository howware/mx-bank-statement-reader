"""Registros comunes para la memoria (`mxbank records`): misma forma para todo howware, sin datos personales."""

import ast
import json

import pytest
from typer.testing import CliRunner

from mxbank import records
from mxbank.cli import app
from mxbank.pipeline import Options, extract_file
from mxbank.privacy.pseudonym import Pseudonymizer
from mxbank.privacy.residual_scan import scan
from tests.synthetic import bbva, bbva_credit

KEY = b"llave-de-prueba-registros"


@pytest.fixture(scope="module")
def statements(tmp_path_factory):
    d = tmp_path_factory.mktemp("records")
    bbva.make(d / "debito.pdf")
    bbva_credit.make(d / "credito.pdf")
    return {name: extract_file(d / f"{name}.pdf", Options(), Pseudonymizer(KEY)) for name in ("debito", "credito")}


def test_keys_are_the_stable_ids(statements):
    st = statements["debito"]
    doc, info = records.memory_document(st, "person:ana", "-07:00")
    keys = [e["key"] for e in doc["events"]]
    assert keys == [st["statement_id"]] + [tx["id"] for tx in st["transactions"]]
    assert info["transactions"] == len(st["transactions"]) and info["records_version"] == records.RECORDS_VERSION
    again, _ = records.memory_document(st, "person:ana", "-07:00")
    assert again == doc


def test_records_hold_what_the_statement_says_and_nothing_more(statements):
    doc, _ = records.memory_document(statements["credito"], "person:ana", "-07:00")
    txs = [e for e in doc["events"] if e["type"] == "transaction"]
    assert all(isinstance(e["attributes"]["amount"], int) for e in txs)
    assert all(e["occurred_at"].endswith("T12:00:00-07:00") for e in txs)
    assert {link["predicate"] for e in txs for link in e["links"]} == {"on_account", "imported_from"}
    declared = {p["id"] for p in doc["predicates"]}
    used = {k for e in doc["events"] for k in e["attributes"]} | {f["predicate"] for f in doc["facts"]}
    assert used <= declared
    assert not scan(doc)


def test_an_older_statement_does_not_replace_newer_balances(statements):
    doc, info = records.memory_document(statements["credito"], "person:ana", "-07:00")
    subjects = records.temporal_subjects(doc)
    assert info["account"] in subjects
    before = len(doc["facts"])
    skipped = records.keep_newer(doc, {(info["account"], "balance"): "2099-01-01T12:00:00-07:00"})
    assert skipped == 1 and len(doc["facts"]) == before - 1
    assert records.keep_newer(doc, {(info["account"], "credit_limit"): "2000-01-01T12:00:00-07:00"}) == 0


def test_refuses_ids_that_change_between_runs(tmp_path):
    bbva.make(tmp_path / "d.pdf")
    st = extract_file(tmp_path / "d.pdf", Options(), Pseudonymizer())
    with pytest.raises(records.RecordsError, match="pseudonym-key-env"):
        records.memory_document(st, "person:ana", "-07:00")


def test_cli_reads_json_and_ndjson(statements, tmp_path):
    single = tmp_path / "uno.json"
    single.write_text(json.dumps(statements["debito"]), encoding="utf-8")
    lines = tmp_path / "varios.ndjson"
    lines.write_text("\n".join(json.dumps(s) for s in statements.values()), encoding="utf-8")
    result = CliRunner().invoke(app, ["records", str(single), str(lines), "--by", "person:ana", "--tz", "-06:00"])
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["ok"] and len(out["documents"]) == 3 and len(out["statements"]) == 3
    bad = tmp_path / "malo.json"
    bad.write_text(json.dumps({"ok": False, "error": {"code": "X"}}), encoding="utf-8")
    result = CliRunner().invoke(app, ["records", str(bad), "--by", "person:ana"])
    assert result.exit_code == 2 and not json.loads(result.output)["ok"]


def test_module_runs_on_the_standard_library_alone():
    """Los howwares copian este archivo junto a sus herramientas: nada fuera de la biblioteca estándar."""
    tree = ast.parse(open(records.__file__, encoding="utf-8").read())
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
        {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules <= {"__future__", "datetime", "decimal", "typing"}
