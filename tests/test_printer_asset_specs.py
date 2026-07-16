"""Pruebas de `src/printer_asset_specs.py` — nivel de tinta actual por
impresora, con foto opcional (`build_ink_reading`/`ink_readings_for`)."""

from __future__ import annotations

import streamlit as st

from src import printer_asset_specs as pas


def _tiny_png_bytes() -> bytes:
    # PNG 1x1 válido mínimo, para probar la codificación base64 sin depender
    # de archivos externos.
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc0c0c00000030001a5f645400000000049454e44ae426082"
    )


# ---------------------------------------------------------------------------
# build_ink_reading
# ---------------------------------------------------------------------------

def test_build_ink_reading_without_photo():
    reading = pas.build_ink_reading("AST-1", "2026-07-15", 100.0, 20.0, 30.0, 5.0, note="Amarillo bajo")
    assert reading["asset_id"] == "AST-1"
    assert reading["k_percent"] == 100.0
    assert reading["y_percent"] == 5.0
    assert reading["note"] == "Amarillo bajo"
    assert reading["photo_base64"] == ""
    assert reading["reading_id"].startswith("INK-")


def test_build_ink_reading_clamps_percentages_to_0_100():
    reading = pas.build_ink_reading("AST-1", "2026-07-15", 150.0, -10.0, 50.0, 50.0)
    assert reading["k_percent"] == 100.0
    assert reading["c_percent"] == 0.0


def test_build_ink_reading_encodes_photo_as_base64():
    photo_bytes = _tiny_png_bytes()
    reading = pas.build_ink_reading("AST-1", "2026-07-15", 90.0, 80.0, 70.0, 60.0, photo_bytes=photo_bytes, photo_mime="image/png")
    assert reading["photo_base64"] != ""
    assert reading["photo_mime"] == "image/png"
    import base64
    assert base64.b64decode(reading["photo_base64"]) == photo_bytes


def test_build_ink_reading_without_photo_bytes_has_empty_mime_even_if_passed():
    reading = pas.build_ink_reading("AST-1", "2026-07-15", 90.0, 80.0, 70.0, 60.0, photo_bytes=None, photo_mime="image/png")
    assert reading["photo_base64"] == ""
    assert reading["photo_mime"] == ""


# ---------------------------------------------------------------------------
# ink_readings_for
# ---------------------------------------------------------------------------

def test_ink_readings_for_filters_by_asset_and_sorts_newest_first():
    st.session_state["ink_level_readings"] = [
        pas.build_ink_reading("AST-1", "2026-07-01", 100, 100, 100, 100),
        pas.build_ink_reading("AST-1", "2026-07-10", 50, 50, 50, 50),
        pas.build_ink_reading("AST-2", "2026-07-05", 90, 90, 90, 90),
    ]
    readings = pas.ink_readings_for("AST-1")
    assert len(readings) == 2
    assert readings[0]["recorded_date"] == "2026-07-10"
    assert readings[1]["recorded_date"] == "2026-07-01"


def test_ink_readings_for_empty_when_no_readings():
    st.session_state["ink_level_readings"] = []
    assert pas.ink_readings_for("AST-SIN-LECTURAS") == []


# ---------------------------------------------------------------------------
# lowest_ink_color
# ---------------------------------------------------------------------------

def test_lowest_ink_color_identifies_the_color_with_least_ink():
    reading = pas.build_ink_reading("AST-1", "2026-07-15", k_percent=100.0, c_percent=60.0, m_percent=40.0, y_percent=10.0)
    label, value = pas.lowest_ink_color(reading)
    assert label == "Amarillo (Y)"
    assert value == 10.0


def test_lowest_ink_color_with_all_full():
    reading = pas.build_ink_reading("AST-1", "2026-07-15", 100.0, 100.0, 100.0, 100.0)
    label, value = pas.lowest_ink_color(reading)
    assert value == 100.0


# ---------------------------------------------------------------------------
# save_ink_reading / latest_ink_reading — reemplaza en vez de acumular
# (a petición del usuario: "no deseo llenarme" de fotos)
# ---------------------------------------------------------------------------

def test_save_ink_reading_replaces_previous_of_same_type():
    st.session_state["ink_level_readings"] = []
    first = pas.build_ink_reading("AST-1", "2026-07-01", 100, 100, 100, 100, photo_type="Tanque", photo_bytes=b"foto1")
    pas.save_ink_reading(first)
    second = pas.build_ink_reading("AST-1", "2026-07-10", 50, 50, 50, 50, photo_type="Tanque", photo_bytes=b"foto2")
    pas.save_ink_reading(second)
    all_readings = st.session_state["ink_level_readings"]
    assert len(all_readings) == 1
    assert all_readings[0]["recorded_date"] == "2026-07-10"


def test_save_ink_reading_keeps_tanque_and_software_separate():
    st.session_state["ink_level_readings"] = []
    tank = pas.build_ink_reading("AST-1", "2026-07-01", 90, 90, 90, 90, photo_type="Tanque", photo_bytes=b"foto-tanque")
    software = pas.build_ink_reading("AST-1", "2026-07-02", 80, 80, 80, 80, photo_type="Software", photo_bytes=b"foto-software")
    pas.save_ink_reading(tank)
    pas.save_ink_reading(software)
    all_readings = st.session_state["ink_level_readings"]
    assert len(all_readings) == 2  # una de cada tipo, no se pisan entre sí


def test_save_ink_reading_does_not_affect_other_assets():
    st.session_state["ink_level_readings"] = []
    pas.save_ink_reading(pas.build_ink_reading("AST-1", "2026-07-01", 100, 100, 100, 100, photo_type="Tanque", photo_bytes=b"x"))
    pas.save_ink_reading(pas.build_ink_reading("AST-2", "2026-07-01", 50, 50, 50, 50, photo_type="Tanque", photo_bytes=b"y"))
    assert len(st.session_state["ink_level_readings"]) == 2


def test_latest_ink_reading_returns_the_stored_entry_for_that_type():
    st.session_state["ink_level_readings"] = []
    pas.save_ink_reading(pas.build_ink_reading("AST-1", "2026-07-10", 40, 40, 40, 40, photo_type="Software", photo_bytes=b"cap"))
    reading = pas.latest_ink_reading("AST-1", "Software")
    assert reading is not None
    assert reading["k_percent"] == 40.0


def test_latest_ink_reading_none_when_not_recorded():
    st.session_state["ink_level_readings"] = []
    assert pas.latest_ink_reading("AST-1", "Tanque") is None
