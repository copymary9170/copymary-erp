"""Pruebas de `src/finishing_jobs.py`: cola de acabados y consumo real."""

from __future__ import annotations

import streamlit as st

from src import finishing_jobs


def _material(item_id="VIN-1", available_quantity=100.0, name="Vinil blanco", category="Vinil"):
    return {
        "item_id": item_id, "name": name, "category": category,
        "unit_cost": 1.5, "available_quantity": available_quantity, "unit": "hoja",
    }


def _machine(asset_id="CAM-1", name="Silhouette Cameo 5", category="Corte"):
    return {
        "asset_id": asset_id, "name": name, "category": category,
        "acquisition_cost": 250.0, "lifetime_units": 5000, "current_units": 10,
    }


# ---------------------------------------------------------------------------
# create_job / jobs_for_stage
# ---------------------------------------------------------------------------

def test_create_job_starts_as_pendiente():
    job = finishing_jobs.create_job(finishing_jobs.STAGE_CUTTING, description="Sticker redondo", quantity=5)
    assert job["status"] == "Pendiente"
    assert job["stage"] == finishing_jobs.STAGE_CUTTING
    assert job["finishing_id"].startswith("AC-")


def test_create_job_rejects_unknown_stage():
    try:
        finishing_jobs.create_job("Etapa inventada")
        assert False, "debía lanzar ValueError"
    except ValueError:
        pass


def test_jobs_for_stage_excludes_completed_by_default():
    job = finishing_jobs.create_job(finishing_jobs.STAGE_LAMINATING)
    finishing_jobs.complete_job(job["finishing_id"])
    assert finishing_jobs.jobs_for_stage(finishing_jobs.STAGE_LAMINATING) == []
    assert len(finishing_jobs.jobs_for_stage(finishing_jobs.STAGE_LAMINATING, include_done=True)) == 1


def test_jobs_for_stage_only_returns_matching_stage():
    finishing_jobs.create_job(finishing_jobs.STAGE_LAMINATING)
    finishing_jobs.create_job(finishing_jobs.STAGE_SUBLIMATION)
    assert len(finishing_jobs.jobs_for_stage(finishing_jobs.STAGE_LAMINATING)) == 1
    assert len(finishing_jobs.jobs_for_stage(finishing_jobs.STAGE_SUBLIMATION)) == 1


# ---------------------------------------------------------------------------
# start_job / cancel_job
# ---------------------------------------------------------------------------

def test_start_job_moves_to_en_proceso():
    job = finishing_jobs.create_job(finishing_jobs.STAGE_CUTTING)
    finishing_jobs.start_job(job["finishing_id"])
    updated = finishing_jobs.jobs_for_stage(finishing_jobs.STAGE_CUTTING)[0]
    assert updated["status"] == "En proceso"


def test_cancel_job_moves_to_cancelado_and_removes_from_pending():
    job = finishing_jobs.create_job(finishing_jobs.STAGE_CUTTING)
    finishing_jobs.cancel_job(job["finishing_id"], note="Cliente canceló")
    assert finishing_jobs.jobs_for_stage(finishing_jobs.STAGE_CUTTING) == []


# ---------------------------------------------------------------------------
# complete_job — consumo real de material y máquina
# ---------------------------------------------------------------------------

def test_complete_job_deducts_material_from_inventory():
    st.session_state["inventory_registry"] = [_material(available_quantity=100.0)]
    job = finishing_jobs.create_job(finishing_jobs.STAGE_CUTTING, quantity=10)
    finishing_jobs.complete_job(job["finishing_id"], material_item_id="VIN-1", material_quantity=10.0)
    assert st.session_state["inventory_registry"][0]["available_quantity"] == 90.0


def test_complete_job_increments_machine_usage():
    st.session_state["assets_registry"] = [_machine()]
    job = finishing_jobs.create_job(finishing_jobs.STAGE_CUTTING, quantity=5)
    finishing_jobs.complete_job(job["finishing_id"], asset_id="CAM-1", machine_units=5.0)
    assert st.session_state["assets_registry"][0]["current_units"] == 15


def test_complete_job_marks_status_completado():
    job = finishing_jobs.create_job(finishing_jobs.STAGE_LAMINATING)
    updated = finishing_jobs.complete_job(job["finishing_id"])
    assert updated["status"] == "Completado"
    assert updated["completed_at_utc"] != ""


def test_complete_job_without_material_or_asset_does_not_fail():
    job = finishing_jobs.create_job(finishing_jobs.STAGE_SUBLIMATION)
    updated = finishing_jobs.complete_job(job["finishing_id"], note="Sin insumos registrados aún")
    assert updated["status"] == "Completado"
    assert updated["material_deducted"] is False
    assert updated["asset_updated"] is False


# ---------------------------------------------------------------------------
# material_options / assets_by_keyword
# ---------------------------------------------------------------------------

def test_material_options_filters_by_keyword_in_name_or_category():
    st.session_state["inventory_registry"] = [
        _material(item_id="VIN-1", name="Vinil textil", category="Vinil"),
        _material(item_id="PAP-1", name="Bond carta", category="Papel"),
    ]
    result = finishing_jobs.material_options("vinil")
    assert [item["item_id"] for item in result] == ["VIN-1"]


def test_material_options_marks_valid_cost_and_available():
    st.session_state["inventory_registry"] = [_material(item_id="VIN-1", available_quantity=0.0)]
    result = finishing_jobs.material_options("vinil")
    assert result[0]["valid_cost"] is True
    assert result[0]["available"] is False


def test_assets_by_keyword_matches_name_case_insensitively():
    st.session_state["assets_registry"] = [_machine(name="Silhouette Cameo 5"), _machine(asset_id="AST-2", name="HP Smart Tank 580", category="Impresora")]
    result = finishing_jobs.assets_by_keyword("cameo")
    assert len(result) == 1
    assert result[0]["asset_id"] == "CAM-1"
