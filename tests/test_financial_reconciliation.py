"""Pruebas de conciliación financiera (`src/financial_reconciliation.py`).

El foco es `_auto_candidates`, que empareja movimientos esperados (caja,
ventas, cobros, pagos a proveedores) contra líneas bancarias importadas,
dentro de una tolerancia de monto y de días.
"""

from __future__ import annotations

from src import financial_reconciliation as fr


def test_num_parses_comma_as_decimal_separator():
    assert fr._num("50,25") == 50.25


def test_num_returns_default_for_invalid_value():
    assert fr._num("no-es-numero", default=-1.0) == -1.0


def test_signed_cash_positive_for_ingreso():
    row = {"movement_type": "Ingreso", "amount": 100.0}
    assert fr._signed_cash(row) == 100.0


def test_signed_cash_negative_for_egreso():
    row = {"movement_type": "Egreso", "amount": 100.0}
    assert fr._signed_cash(row) == -100.0


def test_entry_key_combines_source_and_source_id():
    entry = {"source": "Venta", "source_id": "V-1"}
    assert fr._entry_key(entry) == "Venta::V-1"


def test_matched_keys_only_includes_conciliado_status():
    matches = [
        {"expected_key": "Venta::V-1", "bank_line_id": "B-1", "status": "Conciliado"},
        {"expected_key": "Venta::V-2", "bank_line_id": "B-2", "status": "Pendiente"},
    ]
    expected_keys, bank_keys = fr._matched_keys(matches)
    assert expected_keys == {"Venta::V-1"}
    assert bank_keys == {"B-1"}


def test_auto_candidates_matches_exact_amount_and_date():
    expected = [{
        "source": "Venta", "source_id": "V-1", "created_at_utc": "2026-07-01T10:00:00",
        "date": "2026-07-01", "amount": 100.0, "reference": "",
    }]
    bank_lines = [{"bank_line_id": "B-1", "date": "2026-07-01", "amount": 100.0, "reference": ""}]

    candidates = fr._auto_candidates(expected, bank_lines, matches=[], tolerance=0.5, days=2)

    assert len(candidates) == 1
    assert candidates[0]["expected_key"] == "Venta::V-1"
    assert candidates[0]["bank_line_id"] == "B-1"
    assert candidates[0]["amount_difference"] == 0.0


def test_auto_candidates_respects_amount_tolerance():
    expected = [{"source": "Venta", "source_id": "V-1", "created_at_utc": "2026-07-01", "amount": 100.0, "reference": ""}]
    bank_lines = [{"bank_line_id": "B-1", "date": "2026-07-01", "amount": 105.0, "reference": ""}]

    # Fuera de tolerancia (diferencia de 5, tolerancia de 1) -> sin candidatos.
    assert fr._auto_candidates(expected, bank_lines, matches=[], tolerance=1.0, days=2) == []
    # Dentro de tolerancia (tolerancia de 10) -> sí aparece.
    candidates = fr._auto_candidates(expected, bank_lines, matches=[], tolerance=10.0, days=2)
    assert len(candidates) == 1


def test_auto_candidates_respects_day_window():
    expected = [{"source": "Venta", "source_id": "V-1", "created_at_utc": "2026-07-01", "amount": 100.0, "reference": ""}]
    bank_lines = [{"bank_line_id": "B-1", "date": "2026-07-10", "amount": 100.0, "reference": ""}]

    # 9 días de diferencia, ventana de 2 días -> sin candidatos.
    assert fr._auto_candidates(expected, bank_lines, matches=[], tolerance=1.0, days=2) == []
    # Ventana de 10 días -> sí aparece.
    candidates = fr._auto_candidates(expected, bank_lines, matches=[], tolerance=1.0, days=10)
    assert len(candidates) == 1


def test_auto_candidates_excludes_already_matched_entries():
    expected = [{"source": "Venta", "source_id": "V-1", "created_at_utc": "2026-07-01", "amount": 100.0, "reference": ""}]
    bank_lines = [{"bank_line_id": "B-1", "date": "2026-07-01", "amount": 100.0, "reference": ""}]
    matches = [{"expected_key": "Venta::V-1", "bank_line_id": "B-1", "status": "Conciliado"}]

    assert fr._auto_candidates(expected, bank_lines, matches, tolerance=1.0, days=2) == []


def test_auto_candidates_scores_reference_match_higher():
    expected_with_ref = {"source": "Venta", "source_id": "V-1", "created_at_utc": "2026-07-01", "amount": 100.0, "reference": "REF123"}
    expected_without_ref = {"source": "Venta", "source_id": "V-2", "created_at_utc": "2026-07-01", "amount": 100.0, "reference": ""}
    bank_line = {"bank_line_id": "B-1", "date": "2026-07-01", "amount": 100.0, "reference": "PAGO REF123 CLIENTE"}

    with_ref = fr._auto_candidates([expected_with_ref], [bank_line], matches=[], tolerance=1.0, days=2)
    without_ref = fr._auto_candidates([expected_without_ref], [bank_line], matches=[], tolerance=1.0, days=2)

    assert with_ref[0]["reference_hit"] is True
    assert without_ref[0]["reference_hit"] is False
    assert with_ref[0]["score"] > without_ref[0]["score"]


def test_auto_candidates_sorted_by_score_descending():
    expected = [{"source": "Venta", "source_id": "V-1", "created_at_utc": "2026-07-01", "amount": 100.0, "reference": ""}]
    bank_lines = [
        {"bank_line_id": "FAR", "date": "2026-07-05", "amount": 100.0, "reference": ""},   # más lejos en fecha
        {"bank_line_id": "CLOSE", "date": "2026-07-01", "amount": 100.0, "reference": ""},  # exacto
    ]
    candidates = fr._auto_candidates(expected, bank_lines, matches=[], tolerance=1.0, days=10)
    assert candidates[0]["bank_line_id"] == "CLOSE"
