from types import SimpleNamespace

from src.assets_workspace import _asset_health, _replacement_priority


def _asset(**overrides):
    base = dict(status="Activo", usage_percent=20.0, warranty_status="Vigente")
    base.update(overrides)
    return SimpleNamespace(**base)


def test_replacement_priority_flags_end_of_life():
    assert _replacement_priority(_asset(usage_percent=92.0)) == "Alta"
    assert _replacement_priority(_asset(status="Fuera de servicio")) == "Crítica"


def test_asset_health_penalizes_operational_risk():
    healthy = _asset_health(_asset())
    risky = _asset_health(_asset(status="En mantenimiento", usage_percent=80.0, warranty_status="Vencida"))
    assert healthy == 100
    assert risky < healthy
