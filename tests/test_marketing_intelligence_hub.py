from src.marketing_intelligence_hub import kpis, potus_ready


def test_kpis_match_monthly_indicator_logic():
    result=kpis({"followers":1000,"interactions":100,"posts":10})
    assert result["engagement"] == 10
    assert result["interactions_per_post"] == 10


def test_kpis_are_safe_with_zero_denominators():
    result=kpis({"followers":0,"interactions":20,"posts":0})
    assert result["engagement"] == 0
    assert result["interactions_per_post"] == 0


def test_potus_ready_requires_five_components():
    score,missing=potus_ready({"purpose":"vender","objective":"leads","tactic":"reels","uniqueness":"rápido","segmentation":"Caracas"})
    assert score == 100
    assert missing == []


def test_potus_ready_reports_missing_components():
    score,missing=potus_ready({"purpose":"vender","objective":"","tactic":"reels","uniqueness":"","segmentation":"Caracas"})
    assert score == 60
    assert "Objetivo" in missing
    assert "Unicidad" in missing
