"""Pruebas de `src/session_utils.py`.

Este módulo centraliza helpers que antes estaban duplicados de forma idéntica
en más de 80 archivos de `src/`. Estas pruebas fijan su comportamiento para
que cualquier cambio futuro sea intencional.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src import session_utils


def test_now_iso_returns_utc_isoformat_string():
    value = session_utils.now_iso()
    # Debe poder re-parsearse como fecha/hora ISO válida.
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


def test_read_list_returns_empty_when_key_missing():
    assert session_utils.read_list("no_existe") == []


def test_read_list_filters_out_non_dict_entries():
    st.session_state["mixed"] = [{"a": 1}, "texto", 42, {"b": 2}]
    assert session_utils.read_list("mixed") == [{"a": 1}, {"b": 2}]


def test_read_list_returns_copies_not_references():
    original = {"a": 1}
    st.session_state["items"] = [original]
    result = session_utils.read_list("items")
    result[0]["a"] = 999
    # Modificar el resultado no debe afectar el original guardado.
    assert original["a"] == 1


def test_save_list_writes_to_session_state():
    session_utils.save_list("my_key", [{"x": 1}])
    assert st.session_state["my_key"] == [{"x": 1}]


def test_save_then_read_round_trip():
    rows = [{"id": "1", "name": "Cliente A"}, {"id": "2", "name": "Cliente B"}]
    session_utils.save_list("clients", rows)
    assert session_utils.read_list("clients") == rows
