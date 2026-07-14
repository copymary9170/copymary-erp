"""Pruebas de `src/general_settings.py` (tasas y comisiones) y del bug real
corregido en `src/session_backup.py`: la restauración de la configuración
general seguía validando el esquema VIEJO (equipment_name/equipment_cost/
equipment_lifetime_units) después de que `GeneralSettings` cambiara a
pricing_method + selected_asset_ids (vinculado a Activos reales), así que
restaurar cualquier respaldo fallaba siempre."""

from __future__ import annotations

from src import session_backup
from src.general_settings import GeneralSettings

REQUIRED_FIELDS = {
    "business_name": "Copy Mary", "currency": "USD", "profit_margin": 40.0,
    "pricing_method": "Margen sobre venta", "monthly_internet": 25.0,
    "monthly_electricity": 4.0, "estimated_monthly_units": 400,
    "selected_asset_ids": ["AST-1", "AST-2"],
}


def _settings(**overrides) -> GeneralSettings:
    base = dict(
        business_name="Copy Mary", currency="USD", profit_margin=40.0, pricing_method="Margen sobre venta",
        monthly_internet=25.0, monthly_electricity=4.0, estimated_monthly_units=400,
        selected_asset_ids=("AST-1",),
        bcv_rate=40.0, binance_rate=45.0, kontigo_in_rate=42.0, kontigo_out_rate=44.0,
        iva_rate=16.0, igtf_rate=3.0, mobile_payment_fee=1.5, pos_fee=2.5,
    )
    base.update(overrides)
    return GeneralSettings(**base)


# ---------------------------------------------------------------------------
# GeneralSettings.rate_for
# ---------------------------------------------------------------------------

def test_rate_for_returns_correct_named_rate():
    settings = _settings(bcv_eur_rate=46.5)
    assert settings.rate_for("BCV") == 40.0
    assert settings.rate_for("BCV (EUR)") == 46.5
    assert settings.rate_for("Binance") == 45.0
    assert settings.rate_for("Kontigo (entrada)") == 42.0
    assert settings.rate_for("Kontigo (salida)") == 44.0


def test_rate_for_unknown_name_returns_zero():
    assert _settings().rate_for("Tasa inventada") == 0.0


# ---------------------------------------------------------------------------
# GeneralSettings.fee_for_payment_method / net_after_fees
# ---------------------------------------------------------------------------

def test_fee_for_payment_method_matches_mobile_payment():
    settings = _settings(mobile_payment_fee=1.5)
    assert settings.fee_for_payment_method("Pago móvil") == 1.5
    assert settings.fee_for_payment_method("pago movil") == 1.5  # sin tilde


def test_fee_for_payment_method_matches_kontigo_entrada_and_salida():
    settings = _settings(kontigo_in_fee=1.0, kontigo_out_fee=2.0)
    assert settings.fee_for_payment_method("Kontigo (entrada)") == 1.0
    assert settings.fee_for_payment_method("Kontigo (salida)") == 2.0


def test_settings_roundtrip_preserves_kontigo_fees():
    settings = _settings(kontigo_in_fee=1.25, kontigo_out_fee=2.75)
    serialized = session_backup._serialize(settings)
    restored = session_backup._settings(serialized)
    assert restored.kontigo_in_fee == 1.25
    assert restored.kontigo_out_fee == 2.75


def test_fee_for_payment_method_matches_pos_or_card():
    settings = _settings(pos_fee=2.5)
    assert settings.fee_for_payment_method("Punto de venta") == 2.5
    assert settings.fee_for_payment_method("Tarjeta") == 2.5


def test_fee_for_payment_method_returns_zero_for_cash_or_transfer():
    settings = _settings()
    assert settings.fee_for_payment_method("Efectivo") == 0.0
    assert settings.fee_for_payment_method("Transferencia") == 0.0


def test_net_after_fees_discounts_payment_method_fee():
    settings = _settings(pos_fee=5.0)
    net = settings.net_after_fees(100.0, "Punto de venta")
    assert net == 95.0


def test_net_after_fees_applies_igtf_only_when_requested():
    settings = _settings(igtf_rate=3.0)
    without_igtf = settings.net_after_fees(100.0, "Efectivo", apply_igtf=False)
    with_igtf = settings.net_after_fees(100.0, "Efectivo", apply_igtf=True)
    assert without_igtf == 100.0
    assert with_igtf == 97.0


def test_net_after_fees_combines_payment_fee_and_igtf():
    settings = _settings(pos_fee=5.0, igtf_rate=3.0)
    net = settings.net_after_fees(100.0, "Tarjeta", apply_igtf=True)
    assert round(net, 4) == round(100.0 * 0.95 * 0.97, 4)


# ---------------------------------------------------------------------------
# Bug real corregido: session_backup._settings() validaba el esquema viejo
# ---------------------------------------------------------------------------

def test_settings_restore_works_with_current_schema():
    """Antes de este arreglo, esto fallaba SIEMPRE: `_settings()` seguía
    exigiendo equipment_name/equipment_cost/equipment_lifetime_units, campos
    que ya no existen en `GeneralSettings` (reemplazados por pricing_method
    y selected_asset_ids). Ningún respaldo podía restaurarse."""
    restored = session_backup._settings(dict(REQUIRED_FIELDS))
    assert restored is not None
    assert restored.pricing_method == "Margen sobre venta"
    assert restored.selected_asset_ids == ("AST-1", "AST-2")


def test_settings_restore_accepts_old_backup_without_rate_fields():
    """Un respaldo de antes de agregar tasas/comisiones (sin esas claves)
    debe completarlas con su valor por defecto, no fallar."""
    restored = session_backup._settings(dict(REQUIRED_FIELDS))
    assert restored.bcv_rate == 0.0
    assert restored.iva_rate == 16.0
    assert restored.igtf_rate == 3.0


def test_settings_restore_accepts_new_backup_with_rate_fields():
    raw = dict(REQUIRED_FIELDS)
    raw.update({
        "bcv_rate": 40.0, "binance_rate": 45.0, "kontigo_in_rate": 42.0, "kontigo_out_rate": 44.0,
        "iva_rate": 16.0, "igtf_rate": 3.0, "mobile_payment_fee": 1.5, "pos_fee": 2.5,
    })
    restored = session_backup._settings(raw)
    assert restored.bcv_rate == 40.0
    assert restored.kontigo_out_rate == 44.0
    assert restored.pos_fee == 2.5


def test_settings_restore_still_rejects_missing_required_field():
    raw = dict(REQUIRED_FIELDS)
    del raw["currency"]
    try:
        session_backup._settings(raw)
        assert False, "debía lanzar ValueError por falta de un campo obligatorio"
    except ValueError:
        pass


def test_settings_restore_ignores_unknown_future_fields():
    """Igual de importante para adelante: si en el futuro se agrega otro
    campo más, un respaldo que ya lo traiga no debe romper la restauración
    en versiones que todavía no lo conocen."""
    raw = dict(REQUIRED_FIELDS)
    raw["campo_del_futuro_que_no_existe_todavia"] = "cualquier cosa"
    restored = session_backup._settings(raw)
    assert restored is not None
    assert restored.business_name == "Copy Mary"


def test_settings_restore_converts_selected_asset_ids_back_to_tuple():
    """JSON no tiene tuplas: tras exportar/importar, `selected_asset_ids`
    llega como lista y debe reconstruirse como tupla (tipo real del
    dataclass), no dejarse como lista."""
    raw = dict(REQUIRED_FIELDS)
    restored = session_backup._settings(raw)
    assert isinstance(restored.selected_asset_ids, tuple)


def test_settings_roundtrip_through_serialize_preserves_new_fields():
    settings = _settings(bcv_rate=41.5, igtf_rate=3.0, pos_fee=2.0)
    serialized = session_backup._serialize(settings)
    restored = session_backup._settings(serialized)
    assert restored.bcv_rate == 41.5
    assert restored.igtf_rate == 3.0
    assert restored.pos_fee == 2.0


def test_settings_roundtrip_preserves_pricing_method_and_assets():
    settings = _settings(pricing_method="Recargo sobre costo", selected_asset_ids=("AST-9", "AST-8"))
    serialized = session_backup._serialize(settings)
    restored = session_backup._settings(serialized)
    assert restored.pricing_method == "Recargo sobre costo"
    assert restored.selected_asset_ids == ("AST-9", "AST-8")
