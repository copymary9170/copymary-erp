"""Pruebas de `src/print_jobs.py`: descuento real de inventario y uso de activos."""

from __future__ import annotations

import streamlit as st

from src import print_jobs


def _paper_item(item_id="PAP-1", available_quantity=500.0):
    return {
        "item_id": item_id,
        "name": "Bond carta 75 g",
        "category": "Papel",
        "unit_cost": 0.018,
        "available_quantity": available_quantity,
        "unit": "hoja",
    }


def _printer_asset(asset_id="AST-1", current_units=1000):
    return {
        "asset_id": asset_id,
        "name": "HP Smart Tank 580",
        "category": "Impresora",
        "acquisition_cost": 300.0,
        "lifetime_units": 30000,
        "current_units": current_units,
    }


# ---------------------------------------------------------------------------
# deduct_inventory_item
# ---------------------------------------------------------------------------

def test_deduct_inventory_item_reduces_available_quantity():
    st.session_state["inventory_registry"] = [_paper_item(available_quantity=500.0)]
    found = print_jobs.deduct_inventory_item("PAP-1", 120.0, "Trabajo de prueba")
    assert found is True
    assert st.session_state["inventory_registry"][0]["available_quantity"] == 380.0


def test_deduct_inventory_item_creates_movement_with_reason():
    st.session_state["inventory_registry"] = [_paper_item(available_quantity=500.0)]
    print_jobs.deduct_inventory_item("PAP-1", 120.0, "Trabajo de prueba")
    movements = st.session_state["inventory_movements"]
    assert len(movements) == 1
    assert movements[0]["movement_type"] == "Salida"
    assert movements[0]["quantity"] == 120.0
    assert movements[0]["reason"] == "Trabajo de prueba"
    assert movements[0]["previous_quantity"] == 500.0
    assert movements[0]["resulting_quantity"] == 380.0


def test_deduct_inventory_item_clamps_at_zero():
    st.session_state["inventory_registry"] = [_paper_item(available_quantity=50.0)]
    print_jobs.deduct_inventory_item("PAP-1", 999.0, "Trabajo grande")
    assert st.session_state["inventory_registry"][0]["available_quantity"] == 0.0


def test_deduct_inventory_item_returns_false_when_item_missing():
    st.session_state["inventory_registry"] = [_paper_item(item_id="PAP-OTRO")]
    found = print_jobs.deduct_inventory_item("PAP-NO-EXISTE", 10.0, "x")
    assert found is False
    assert "inventory_movements" not in st.session_state


def test_deduct_inventory_item_only_affects_targeted_item():
    st.session_state["inventory_registry"] = [
        _paper_item(item_id="PAP-1", available_quantity=100.0),
        _paper_item(item_id="PAP-2", available_quantity=100.0),
    ]
    print_jobs.deduct_inventory_item("PAP-1", 30.0, "x")
    items = {row["item_id"]: row["available_quantity"] for row in st.session_state["inventory_registry"]}
    assert items["PAP-1"] == 70.0
    assert items["PAP-2"] == 100.0


# ---------------------------------------------------------------------------
# increment_asset_usage
# ---------------------------------------------------------------------------

def test_increment_asset_usage_adds_units():
    st.session_state["assets_registry"] = [_printer_asset(current_units=1000)]
    found = print_jobs.increment_asset_usage("AST-1", 250)
    assert found is True
    assert st.session_state["assets_registry"][0]["current_units"] == 1250


def test_increment_asset_usage_returns_false_when_asset_missing():
    st.session_state["assets_registry"] = [_printer_asset(asset_id="AST-OTRO")]
    found = print_jobs.increment_asset_usage("AST-NO-EXISTE", 10)
    assert found is False


def test_increment_asset_usage_ignores_non_positive_units():
    st.session_state["assets_registry"] = [_printer_asset(current_units=1000)]
    found = print_jobs.increment_asset_usage("AST-1", 0)
    assert found is False
    assert st.session_state["assets_registry"][0]["current_units"] == 1000


# ---------------------------------------------------------------------------
# confirm_print_job
# ---------------------------------------------------------------------------

def test_confirm_print_job_deducts_paper_and_updates_asset():
    st.session_state["inventory_registry"] = [_paper_item(available_quantity=500.0)]
    st.session_state["assets_registry"] = [_printer_asset(current_units=1000)]

    result = {"archivo": "cotizacion.pdf", "costo_total_usd": 4.2, "precio_sugerido_usd": 7.0}
    job = print_jobs.confirm_print_job(
        result, paper_item_id="PAP-1", sheets=50.0, asset_id="AST-1", printed_pages=50
    )

    assert job["paper_deducted"] is True
    assert job["asset_updated"] is True
    assert job["status"] == "Confirmado"
    assert job["job_id"].startswith("IMP-")
    assert st.session_state["inventory_registry"][0]["available_quantity"] == 450.0
    assert st.session_state["assets_registry"][0]["current_units"] == 1050


def test_confirm_print_job_persists_to_print_jobs_list():
    st.session_state["inventory_registry"] = [_paper_item()]
    st.session_state["assets_registry"] = [_printer_asset()]
    result = {"archivo": "flyer.pdf"}
    job = print_jobs.confirm_print_job(result, paper_item_id="PAP-1", sheets=1.0, asset_id="AST-1", printed_pages=1)
    jobs = print_jobs.recent_jobs()
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == job["job_id"]
    assert print_jobs.job_by_id(job["job_id"])["archivo"] == "flyer.pdf"


def test_confirm_print_job_flags_missing_paper_without_raising():
    st.session_state["inventory_registry"] = []
    st.session_state["assets_registry"] = [_printer_asset()]
    job = print_jobs.confirm_print_job(
        {"archivo": "x.pdf"}, paper_item_id="NO-EXISTE", sheets=10.0, asset_id="AST-1", printed_pages=10
    )
    assert job["paper_deducted"] is False
    assert job["asset_updated"] is True
