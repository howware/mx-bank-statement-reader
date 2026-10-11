import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_no_pii  # noqa: E402

from mxbank.privacy import detectors  # noqa: E402


def _kinds(text, allow=frozenset()):
    return [kind for _, kind in check_no_pii.find_pii(text, set(allow))]


def test_detects_clabe_with_and_without_spaces():
    clabe = "032180000118359719"  # CLABE de ejemplo con dígito verificador válido
    assert detectors.clabe_ok(clabe)
    assert "CLABE" in _kinds(f"cuenta {clabe}")
    assert "CLABE" in _kinds("cuenta 032 180 00011835971 9")


def test_detects_card_luhn_and_ignores_invalid():
    assert "TARJETA" in _kinds("tarjeta 4111 1111 1111 1111")
    assert "TARJETA" not in _kinds("folio 4111111111111112")


def test_detects_rfc_curp_email():
    assert "RFC" in _kinds("RFC: GODE561231GR8")
    assert "RFC" in _kinds("RFC: CFE 370814QI0")
    assert "CURP" in _kinds("CURP GODE561231HDFRRN09")
    assert "EMAIL" in _kinds("correo alguien@gmail.com")
    assert "EMAIL" not in _kinds("noreply@anthropic.com")
    assert "EMAIL" not in _kinds("uvx ruff@0.6.9 check")
    assert "EMAIL" in _kinds("contacto@banco.com.mx")


def test_allowlist_and_masked_shapes():
    assert _kinds("RFC: GODE561231GR8", {"GODE561231GR8"}) == []
    assert _kinds("No. Cuenta CLABE 999 999 99999999999 9  XXXX999999XX9") == []
