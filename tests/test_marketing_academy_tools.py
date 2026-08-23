"""Pruebas de las herramientas avanzadas de Marketing."""

from src import marketing_academy_tools as tools


def test_email_kpis_calculates_rates():
    result = tools.email_kpis(delivered=1000, opened=500, clicks=100, conversions=25)
    assert result["open_rate"] == 50.0
    assert result["ctr"] == 10.0
    assert result["ctor"] == 20.0
    assert result["conversion_rate"] == 2.5


def test_email_kpis_handles_zero_denominators():
    result = tools.email_kpis(0, 0, 0, 0)
    assert result == {"open_rate": 0.0, "ctr": 0.0, "ctor": 0.0, "conversion_rate": 0.0}


def test_readiness_score_uses_defined_checklist():
    values = {key: True for key, _label in tools.META_CHECKS}
    values[tools.META_CHECKS[0][0]] = False
    expected = (len(tools.META_CHECKS) - 1) / len(tools.META_CHECKS) * 100
    assert tools.readiness_score(values) == expected


def test_community_quote_range_preserves_base_without_adjustments():
    low, high = tools.community_quote_range("Calendario de contenido mensual", "Intermedio")
    assert low == 90.0
    assert high == 180.0


def test_community_quote_range_applies_adjustment_ranges():
    low, high = tools.community_quote_range(
        "Gestión mensual · 1 marca / 1 red",
        "Principiante",
        ["Entrega urgente", "Bilingüe"],
    )
    assert round(low, 2) == round(180 * 1.10 * 1.10, 2)
    assert round(high, 2) == round(350 * 1.30 * 1.20, 2)


def test_ads_management_quote_respects_minimum():
    assert tools.ads_management_quote(100, "Principiante") == (50.0, 50.0)
    low, high = tools.ads_management_quote(1000, "Senior")
    assert low == 200.0
    assert high == 200.0


def test_email_types_match_course_taxonomy():
    assert tools.EMAIL_TYPES == ("Newsletter", "Promocional", "Estacional", "Informativa")
