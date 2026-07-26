from src.legal_compliance_domain import (
    record_hash,
    retained_deletion_attempt,
    validate_fiscal_invoice,
    verify_hash_chain,
)


def valid_invoice():
    return {
        "issuer_name": "Copy Mary, C.A.", "issuer_rif": "J-12345678-9",
        "fiscal_address": "Caracas", "invoice_number": "000001",
        "control_number": "00-00000001", "issued_at": "2026-07-26T10:00:00Z",
        "issuance_method": "Digital autorizada", "digital_authorization": "SNAT-001",
        "items": [{"description": "Impresión", "quantity": 1, "unit_price": 10}], "total": 10,
    }


def test_invoice_without_rif_is_rejected():
    invoice = valid_invoice(); invoice["issuer_rif"] = ""
    result = validate_fiscal_invoice(invoice)
    assert not result.valid
    assert any("RIF" in error for error in result.errors)


def test_invoice_without_control_number_is_rejected():
    invoice = valid_invoice(); invoice["control_number"] = ""
    result = validate_fiscal_invoice(invoice)
    assert not result.valid
    assert any("control" in error.casefold() for error in result.errors)


def test_valid_digital_invoice_is_accepted():
    assert validate_fiscal_invoice(valid_invoice()).valid


def test_retained_rows_cannot_be_removed():
    current = [{"invoice_id": "FAC-1"}, {"invoice_id": "FAC-2"}]
    proposed = [{"invoice_id": "FAC-2"}]
    assert retained_deletion_attempt(current, proposed, "invoice_id") == ("FAC-1",)


def test_hash_chain_detects_tampering():
    first = {"record_id": "1", "amount": 10}
    first_hash = record_hash(first)
    second = {"record_id": "2", "amount": 20}
    second_hash = record_hash(second, first_hash)
    rows = [dict(first, previous_hash="", integrity_hash=first_hash), dict(second, previous_hash=first_hash, integrity_hash=second_hash)]
    assert verify_hash_chain(rows)
    rows[0]["amount"] = 99
    assert not verify_hash_chain(rows)
