"""Pruebas de `src/payment_fees.py` — el helper central que cualquier
módulo puede usar para aplicar comisiones de medio de pago e IGTF sin
duplicar la lógica de leer Configuración General."""

from __future__ import annotations

import streamlit as st

from src import payment_fees as pf
from src.general_settings_process import GeneralSettings


def _settings(**overrides) -> GeneralSettings:
    base = dict(
        business_name="Copy Mary", currency="USD", profit_margin=40.0, margin_method="Margen sobre venta",
        monthly_internet=5.0, monthly_electricity=3.0, estimated_monthly_units=200,
        bcv_rate=40.0, binance_rate=45.0, kontigo_in_rate=42.0, kontigo_out_rate=44.0,
        kontigo_in_fee=1.0, kontigo_out_fee=2.0, iva_rate=16.0, igtf_rate=3.0,
        mobile_payment_fee=1.5, pos_fee=2.5,
    )
    base.update(overrides)
    return GeneralSettings(**base)


# ---------------------------------------------------------------------------
# Sin configuración guardada: nunca falla, todo en 0
# ---------------------------------------------------------------------------

def test_without_settings_fee_rate_is_zero():
    st.session_state.pop("general_settings", None)
    assert pf.fee_rate_for("Punto de venta") == 0.0


def test_without_settings_net_amount_equals_gross():
    st.session_state.pop("general_settings", None)
    assert pf.net_amount(100.0, "Efectivo") == 100.0


def test_without_settings_exchange_rate_is_zero():
    st.session_state.pop("general_settings", None)
    assert pf.exchange_rate("BCV") == 0.0


# ---------------------------------------------------------------------------
# Con configuración guardada
# ---------------------------------------------------------------------------

def test_fee_rate_for_reads_from_stored_settings():
    st.session_state["general_settings"] = _settings(pos_fee=2.5)
    assert pf.fee_rate_for("Punto de venta") == 2.5


def test_exchange_rate_reads_from_stored_settings():
    st.session_state["general_settings"] = _settings(bcv_rate=40.0)
    assert pf.exchange_rate("BCV") == 40.0


def test_igtf_rate_and_iva_rate_read_from_stored_settings():
    st.session_state["general_settings"] = _settings(igtf_rate=3.0, iva_rate=16.0)
    assert pf.igtf_rate() == 3.0
    assert pf.iva_rate() == 16.0


# ---------------------------------------------------------------------------
# should_apply_igtf — regla automática divisas/cripto vs bolívares
# ---------------------------------------------------------------------------

def test_should_apply_igtf_true_for_foreign_currency_methods():
    assert pf.should_apply_igtf("Zelle") is True
    assert pf.should_apply_igtf("Kontigo (entrada)") is True
    assert pf.should_apply_igtf("Binance") is True


def test_should_apply_igtf_false_for_bolivar_methods():
    assert pf.should_apply_igtf("Efectivo") is False
    assert pf.should_apply_igtf("Pago móvil") is False
    assert pf.should_apply_igtf("Transferencia") is False


# ---------------------------------------------------------------------------
# fee_breakdown / net_amount
# ---------------------------------------------------------------------------

def test_fee_breakdown_does_not_apply_igtf_by_default_even_for_zelle():
    """El IGTF nunca se infiere solo, ni para medios en divisas: hay casos
    exentos según cómo se procese, así que queda en False salvo que se pida
    explícitamente."""
    st.session_state["general_settings"] = _settings(igtf_rate=3.0)
    breakdown = pf.fee_breakdown(100.0, "Zelle")
    assert breakdown["igtf_applied"] is False
    assert breakdown["net_amount"] == 100.0


def test_fee_breakdown_applies_igtf_only_when_explicitly_requested():
    st.session_state["general_settings"] = _settings(igtf_rate=3.0)
    breakdown = pf.fee_breakdown(100.0, "Zelle", apply_igtf=True)
    assert breakdown["igtf_applied"] is True
    assert round(breakdown["net_amount"], 4) == 97.0


def test_fee_breakdown_does_not_apply_igtf_for_cash():
    st.session_state["general_settings"] = _settings(igtf_rate=3.0)
    breakdown = pf.fee_breakdown(100.0, "Efectivo")
    assert breakdown["igtf_applied"] is False
    assert breakdown["net_amount"] == 100.0


def test_fee_breakdown_combines_pos_fee_and_explicit_igtf():
    st.session_state["general_settings"] = _settings(pos_fee=5.0, igtf_rate=3.0)
    breakdown = pf.fee_breakdown(100.0, "Punto de venta", apply_igtf=True)
    assert breakdown["fee_amount"] == 5.0
    assert round(breakdown["net_amount"], 4) == round(100.0 * 0.95 * 0.97, 4)


def test_fee_breakdown_apply_igtf_respected_even_for_bolivar_methods_if_requested():
    """La decisión es siempre manual — si alguien marca IGTF a mano para un
    medio que normalmente no lo paga (caso raro pero posible), se respeta."""
    st.session_state["general_settings"] = _settings(igtf_rate=3.0)
    breakdown = pf.fee_breakdown(100.0, "Efectivo", apply_igtf=True)
    assert breakdown["igtf_applied"] is True
    assert round(breakdown["net_amount"], 4) == 97.0


def test_net_amount_matches_fee_breakdown_net_amount():
    st.session_state["general_settings"] = _settings(pos_fee=5.0)
    assert pf.net_amount(200.0, "Tarjeta") == pf.fee_breakdown(200.0, "Tarjeta")["net_amount"]
