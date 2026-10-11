import random
import socket

import pytest

from mxbank.models.raw import RawStatement
from mxbank.privacy.pseudonym import Pseudonymizer
from mxbank.privacy.redactor import Redactor
from tests.synthetic.common import make_clabe, make_pan


def _redactor() -> Redactor:
    raw = RawStatement(bank="x", bank_name="X", product="debit", product_name=None, layout_version="0",
                       confidence=1.0, pages=1)
    raw.header.add("holder_name", "JUANITA PÉREZ GARCÍA")
    raw.header.add("address", "AV INSURGENTES SUR 123 COL FLORIDA")
    return Redactor(raw, "standard", Pseudonymizer(b"k"), include_concepts=False)


def test_generated_identifiers_are_always_scrubbed():
    """Variante determinista de una prueba property-based: 300 CLABE/tarjetas en posiciones aleatorias."""
    rng = random.Random(20261010)
    r = _redactor()
    for _ in range(150):
        clabe = make_clabe("".join(rng.choice("0123456789") for _ in range(17)))
        pan = make_pan("4" + "".join(rng.choice("0123456789") for _ in range(14)))
        for value in (clabe, pan, f"{clabe[:3]} {clabe[3:6]} {clabe[6:17]} {clabe[17]}", " ".join(pan[i:i + 4] for i in range(0, 16, 4))):
            words = ["PAGO", "SPEI", "OXXO", "REF"]
            words.insert(rng.randrange(len(words) + 1), value)
            out = r.scrub(" ".join(words))
            assert value not in out and value.replace(" ", "") not in out.replace(" ", ""), (value, out)


def test_holder_dictionary_ignores_accents_and_case():
    r = _redactor()
    assert r.scrub("Transferencia a Juanita Perez") == "TRANSFERENCIA A [DATO]"
    assert r.scrub("OXXO INSURGENTES") == "OXXO [DATO]"
    assert r.scrub("BBVA MEXICO PAGO") == "BBVA MEXICO PAGO"  # palabras comunes no entran al diccionario


def test_network_is_blocked_in_tests():
    with pytest.raises(AssertionError):
        socket.create_connection(("example.com", 80))
