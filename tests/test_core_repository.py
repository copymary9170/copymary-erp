"""Pruebas de persistencia y migración de datos núcleo."""

from __future__ import annotations

import streamlit as st

from src.core_data_startup import load_core_data_on_startup
from src.core_repository import load_entity, migrate_entity_if_missing, save_entity
from src.session_utils import read_list, save_list


def test_save_and_reload_preserves_inventory_and_customers():
    inventory = [{"item_id": "MAT-1", "name": "Papel bond", "quantity": 500}]
    customers = [{"customer_id": "CLI-1", "name": "Cliente A"}]
    save_list("inventory_registry", inventory)
    save_list("customers_registry", customers)

    st.session_state.clear()

    assert read_list("inventory_registry") == inventory
    assert read_list("customers_registry") == customers


def test_save_and_reload_preserves_rates():
    rates = {
        "business_name": "Copy Mary",
        "currency": "VES",
        "profit_margin": 40.0,
        "margin_method": "Margen sobre venta",
        "monthly_internet": 25.0,
        "monthly_electricity": 4.0,
        "estimated_monthly_units": 400,
        "bcv_rate": 46.61,
        "bcv_eur_rate": 50.0,
        "binance_rate": 52.0,
        "kontigo_in_rate": 51.0,
        "kontigo_out_rate": 53.0,
        "kontigo_in_fee": 0.0,
        "kontigo_out_fee": 0.0,
        "iva_rate": 16.0,
        "igtf_rate": 3.0,
        "mobile_payment_fee": 0.0,
        "pos_fee": 0.0,
        "rates_updated_at": "2026-07-26T12:00:00+00:00",
    }
    save_entity("general_settings", rates)
    st.session_state.clear()

    load_core_data_on_startup()

    settings = st.session_state["general_settings"]
    assert settings.currency == "VES"
    assert settings.bcv_rate == 46.61
    assert settings.binance_rate == 52.0
    assert settings.iva_rate == 16.0
    assert settings.igtf_rate == 3.0


def test_migration_is_idempotent_and_does_not_overwrite_database():
    original = [{"customer_id": "CLI-1", "name": "Persistido"}]
    replacement = [{"customer_id": "CLI-2", "name": "Snapshot viejo"}]

    assert migrate_entity_if_missing("customers_registry", original) is True
    assert migrate_entity_if_missing("customers_registry", replacement) is False
    assert load_entity("customers_registry") == original


def test_empty_startup_does_not_fail():
    load_core_data_on_startup()
    assert st.session_state["_core_data_startup_loaded"] is True
