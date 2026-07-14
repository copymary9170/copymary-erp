"""Pruebas de `src/general_settings_process.py` — el módulo 'Configuración
General' que REALMENTE se muestra en la app (`process_quote_loader.py` lo
registra por encima de `src/general_settings.py`). Existen dos clases
`GeneralSettings` distintas con el mismo nombre; las tasas/comisiones deben
funcionar en esta, no solo en la otra, o el usuario nunca las ve."""

from __future__ import annotations

import streamlit as st

from src import general_settings_process as gsp


def test_defaults_fill_rate_fields_with_sensible_values_when_nothing_stored():
    st.session_state.pop("general_settings", None)
    defaults = gsp._defaults()
    assert defaults.bcv_rate == 0.0
    assert defaults.iva_rate == 16.0
    assert defaults.igtf_rate == 3.0


def test_defaults_preserve_previously_stored_rates():
    st.session_state["general_settings"] = gsp.GeneralSettings(
        business_name="Copy Mary", currency="USD", profit_margin=40.0, margin_method="Margen sobre venta",
        monthly_internet=5.0, monthly_electricity=3.0, estimated_monthly_units=200,
        bcv_rate=41.5, binance_rate=46.0, kontigo_in_rate=42.0, kontigo_out_rate=44.0,
        iva_rate=16.0, igtf_rate=3.0, mobile_payment_fee=1.5, pos_fee=2.5,
    )
    defaults = gsp._defaults()
    assert defaults.bcv_rate == 41.5
    assert defaults.kontigo_out_rate == 44.0
    assert defaults.pos_fee == 2.5


def test_defaults_do_not_crash_when_stored_settings_is_the_other_general_settings_class():
    """Si en sesión hay un GeneralSettings de src/general_settings.py (la
    otra clase, con el mismo nombre), _defaults() no debe romperse — debe
    leer lo que comparten por nombre de campo y completar el resto con su
    valor por defecto."""
    from src.general_settings import GeneralSettings as OtherGeneralSettings
    st.session_state["general_settings"] = OtherGeneralSettings(
        business_name="Otra instancia", currency="EUR", profit_margin=25.0,
        pricing_method="Recargo sobre costo", monthly_internet=10.0, monthly_electricity=2.0,
        estimated_monthly_units=100, selected_asset_ids=("AST-1",), bcv_rate=39.0,
    )
    defaults = gsp._defaults()
    assert defaults.business_name == "Otra instancia"
    assert defaults.currency == "EUR"
    assert defaults.bcv_rate == 39.0  # campo compartido por nombre, sí se preserva
    assert defaults.margin_method == "Margen sobre venta"  # no existe en la otra clase, usa default


# ---------------------------------------------------------------------------
# GeneralSettings.rate_for / fee_for_payment_method / net_after_fees
# (misma lógica que en la otra clase, duplicada a propósito porque son dos
# dataclasses independientes)
# ---------------------------------------------------------------------------

def _settings(**overrides) -> gsp.GeneralSettings:
    base = dict(
        business_name="Copy Mary", currency="USD", profit_margin=40.0, margin_method="Margen sobre venta",
        monthly_internet=5.0, monthly_electricity=3.0, estimated_monthly_units=200,
        bcv_rate=40.0, binance_rate=45.0, kontigo_in_rate=42.0, kontigo_out_rate=44.0,
        iva_rate=16.0, igtf_rate=3.0, mobile_payment_fee=1.5, pos_fee=2.5,
    )
    base.update(overrides)
    return gsp.GeneralSettings(**base)


def test_rate_for_returns_correct_named_rate():
    settings = _settings()
    assert settings.rate_for("BCV") == 40.0
    assert settings.rate_for("Kontigo (salida)") == 44.0


def test_fee_for_payment_method_matches_mobile_and_pos():
    settings = _settings(mobile_payment_fee=1.5, pos_fee=2.5)
    assert settings.fee_for_payment_method("Pago móvil") == 1.5
    assert settings.fee_for_payment_method("Punto de venta") == 2.5
    assert settings.fee_for_payment_method("Efectivo") == 0.0


def test_fee_for_payment_method_matches_kontigo_entrada_and_salida():
    settings = _settings(kontigo_in_fee=1.0, kontigo_out_fee=2.0)
    assert settings.fee_for_payment_method("Kontigo (entrada)") == 1.0
    assert settings.fee_for_payment_method("Kontigo (salida)") == 2.0


def test_net_after_fees_combines_payment_fee_and_igtf():
    settings = _settings(pos_fee=5.0, igtf_rate=3.0)
    net = settings.net_after_fees(100.0, "Tarjeta", apply_igtf=True)
    assert round(net, 4) == round(100.0 * 0.95 * 0.97, 4)
