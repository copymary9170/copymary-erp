"""Pruebas del costeo de consumibles por tecnología de impresión
(`print_cost_analyzer_v3._consumable_costs`) y de las etapas de acabado y
servicios sugeridos que acompañan al catálogo ampliado del taller.
"""

from __future__ import annotations

from src.print_cost_analyzer_v3 import INKJET_TECHNOLOGIES, THERMAL_TECHNOLOGIES, _consumable_costs
from src.print_cost_data_bridge import _consumable_profile


def _profile(**overrides) -> dict:
    """Perfil mínimo de impresora, con los mismos valores por defecto que
    produce `_consumable_profile` para una ficha vacía."""
    base = _consumable_profile({})
    base.update(overrides)
    return base


FULL_COVERAGE = {"C": 5.0, "M": 5.0, "Y": 5.0, "K": 5.0}


# ---------------------------------------------------------------------------
# Tecnologías térmicas: sin tinta, solo desgaste de cabezal
# ---------------------------------------------------------------------------

def test_thermal_technology_has_no_ink_costs():
    p = _profile(technology="Térmica directa (sin tinta)", head_cost=60.0, head_life=30000)
    costs, components = _consumable_costs(p, pages=100, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert costs == {}  # el % CMYK no genera costo de tinta
    assert "Desgaste de cabezal térmico" in components
    assert round(components["Desgaste de cabezal térmico"], 6) == round(100 * 60.0 / 30000, 6)


def test_tattoo_stencil_technology_behaves_like_thermal():
    p = _profile(technology="Esténcil térmico (tatuajes)", head_cost=80.0, head_life=10000)
    costs, components = _consumable_costs(p, pages=50, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert costs == {}
    assert round(components["Desgaste de cabezal térmico"], 6) == round(50 * 80.0 / 10000, 6)


def test_thermal_without_head_cost_has_no_components():
    p = _profile(technology="Térmica directa (sin tinta)", head_cost=0.0)
    costs, components = _consumable_costs(p, pages=100, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert costs == {}
    assert components == {}


# ---------------------------------------------------------------------------
# Tarjetas PVC: el ribbon rinde N tarjetas fijas, la cobertura no importa
# ---------------------------------------------------------------------------

def test_pvc_ribbon_cost_is_per_card_regardless_of_coverage():
    p = _profile(technology="Tarjetas PVC (ribbon)", black_cost=25.0, black_yield=250, head_cost=200.0, head_life=50000)
    low_coverage = {"C": 1.0, "M": 1.0, "Y": 1.0, "K": 1.0}
    high_coverage = {"C": 90.0, "M": 90.0, "Y": 90.0, "K": 90.0}
    costs_low, _ = _consumable_costs(p, pages=10, coverages=low_coverage, ink_factor=1.0)
    costs_high, _ = _consumable_costs(p, pages=10, coverages=high_coverage, ink_factor=1.0)
    assert costs_low["Ribbon"] == costs_high["Ribbon"]  # panel completo por tarjeta
    assert costs_low["Ribbon"] == 10 / 250 * 25.0  # 10 tarjetas a $0.10 c/u


def test_pvc_includes_printhead_wear():
    p = _profile(technology="Tarjetas PVC (ribbon)", black_cost=25.0, black_yield=250, head_cost=200.0, head_life=50000)
    _, components = _consumable_costs(p, pages=100, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert round(components["Desgaste de cabezal de impresión"], 6) == round(100 * 200.0 / 50000, 6)


# ---------------------------------------------------------------------------
# Sublimación con tanque: mismo modelo CMYK que el tanque normal
# ---------------------------------------------------------------------------

def test_sublimation_tank_costs_cmyk_channels_like_tank():
    kwargs = dict(c_cost=20.0, c_yield=5000, m_cost=20.0, m_yield=5000, y_cost=20.0, y_yield=5000, black_cost=20.0, black_yield=8000, head_cost=100.0, head_life=30000)
    tank = _profile(technology="Inyección con tanque", **kwargs)
    sublimation = _profile(technology="Sublimación con tanque", **kwargs)
    costs_tank, comp_tank = _consumable_costs(tank, pages=100, coverages=FULL_COVERAGE, ink_factor=1.0)
    costs_sub, comp_sub = _consumable_costs(sublimation, pages=100, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert costs_tank == costs_sub
    assert comp_tank == comp_sub  # el cabezal también se desgasta igual


def test_sublimation_tank_gets_head_wear():
    p = _profile(technology="Sublimación con tanque", head_cost=120.0, head_life=30000)
    _, components = _consumable_costs(p, pages=300, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert round(components["Desgaste de cabezales"], 6) == round(300 * 120.0 / 30000, 6)


# ---------------------------------------------------------------------------
# DTF: CMYK + tinta blanca (debajo de todo el diseño) + polvo por página
# ---------------------------------------------------------------------------

def test_dtf_adds_white_ink_and_powder_on_top_of_cmyk():
    p = _profile(
        technology="DTF (tinta + polvo)",
        c_cost=25.0, c_yield=4000, m_cost=25.0, m_yield=4000, y_cost=25.0, y_yield=4000,
        black_cost=25.0, black_yield=4000, white_cost=30.0, white_yield=4000, powder_page=0.05,
        head_cost=150.0, head_life=20000,
    )
    coverages = {"C": 10.0, "M": 10.0, "Y": 10.0, "K": 10.0}
    costs, components = _consumable_costs(p, pages=100, coverages=coverages, ink_factor=1.0)
    assert "Tinta C" in costs and "Tinta K" in costs
    assert "Tinta blanca" in costs
    assert "Polvo adhesivo DTF" in costs
    assert costs["Polvo adhesivo DTF"] == 100 * 0.05
    # cobertura blanca = min(100, 10+10+10+10) = 40%
    assert round(costs["Tinta blanca"], 6) == round(100 * (40.0 / 5) / 4000 * 30.0, 6)
    assert "Desgaste de cabezales" in components


def test_dtf_white_coverage_caps_at_100_percent():
    p = _profile(technology="DTF (tinta + polvo)", white_cost=30.0, white_yield=4000)
    heavy = {"C": 60.0, "M": 60.0, "Y": 60.0, "K": 60.0}  # suma 240 → tope 100
    costs, _ = _consumable_costs(p, pages=10, coverages=heavy, ink_factor=1.0)
    assert round(costs["Tinta blanca"], 6) == round(10 * (100.0 / 5) / 4000 * 30.0, 6)


def test_dtf_without_white_or_powder_configured_omits_those_lines():
    p = _profile(technology="DTF (tinta + polvo)", white_cost=0.0, powder_page=0.0)
    costs, _ = _consumable_costs(p, pages=10, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert "Tinta blanca" not in costs
    assert "Polvo adhesivo DTF" not in costs


# ---------------------------------------------------------------------------
# Regresión: las tecnologías originales no cambian
# ---------------------------------------------------------------------------

def test_mono_laser_unchanged_by_new_technologies():
    p = _profile(technology="Láser monocromática", black_cost=45.0, black_yield=1500, drum_cost=80.0, drum_life=12000, fuser_cost=120.0, fuser_life=50000)
    costs, components = _consumable_costs(p, pages=100, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert "Tóner negro" in costs
    assert "Desgaste de tambor" in components
    assert "Desgaste de fusor" in components


def test_tricolor_cartridge_unchanged():
    p = _profile(technology="Inyección con cartuchos", cartridge_layout="tricolor", black_cost=22.0, black_yield=300, color_cost=23.0, color_yield=100)
    costs, _ = _consumable_costs(p, pages=10, coverages=FULL_COVERAGE, ink_factor=1.0)
    assert "Cartucho negro" in costs
    assert "Cartucho tricolor" in costs


def test_consumable_profile_passes_through_dtf_fields():
    profile = _consumable_profile({"technology": "DTF (tinta + polvo)", "white_cost": 30.0, "white_yield": 4000, "powder_page": 0.05})
    assert profile["white_cost"] == 30.0
    assert profile["white_yield"] == 4000
    assert profile["powder_page"] == 0.05


def test_consumable_profile_defaults_dtf_fields_for_old_specs():
    """Fichas guardadas antes de estas tecnologías no deben romper nada."""
    profile = _consumable_profile({"technology": "Inyección con tanque"})
    assert profile["white_cost"] == 0.0
    assert profile["powder_page"] == 0.0


def test_technology_constant_groups_are_consistent():
    assert "Sublimación con tanque" in INKJET_TECHNOLOGIES
    assert "DTF (tinta + polvo)" in INKJET_TECHNOLOGIES
    assert "Térmica directa (sin tinta)" in THERMAL_TECHNOLOGIES
    assert "Esténcil térmico (tatuajes)" in THERMAL_TECHNOLOGIES


def test_printer_asset_specs_technologies_match_analyzer_groups():
    """Toda tecnología del costeo debe existir en la ficha técnica, o sería
    imposible configurarla."""
    from src.printer_asset_specs import TECHNOLOGIES
    for tech in (*INKJET_TECHNOLOGIES, *THERMAL_TECHNOLOGIES, "Tarjetas PVC (ribbon)", "Láser monocromática", "Láser color"):
        assert tech in TECHNOLOGIES, f"{tech} no está en printer_asset_specs.TECHNOLOGIES"
