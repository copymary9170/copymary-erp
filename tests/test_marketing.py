"""Pruebas del módulo de Marketing."""

from src import marketing, marketing_ai_workbench, module_bootstrap, top_navigation_app


def test_marketing_summary_calculates_core_kpis():
    campaigns = [
        {"campaign_id": "C1", "status": "Activa"},
        {"campaign_id": "C2", "status": "Finalizada"},
    ]
    content = [
        {"content_id": "P1", "status": "Publicado"},
        {"content_id": "P2", "status": "Programado"},
    ]
    metrics = [
        {"impressions": 1000, "clicks": 50, "leads": 10, "sales": 2, "spend": 20, "revenue": 80},
        {"impressions": 500, "clicks": 25, "leads": 5, "sales": 1, "spend": 10, "revenue": 40},
    ]
    result = marketing.marketing_summary(campaigns, content, metrics)
    assert result["active_campaigns"] == 1
    assert result["published_content"] == 1
    assert result["pending_content"] == 1
    assert result["impressions"] == 1500
    assert result["clicks"] == 75
    assert result["leads"] == 15
    assert result["sales"] == 3
    assert result["spend"] == 30
    assert result["revenue"] == 120
    assert round(result["ctr"], 2) == 5.00
    assert round(result["cpl"], 2) == 2.00
    assert round(result["conversion"], 2) == 20.00
    assert round(result["roas"], 2) == 4.00


def test_marketing_summary_handles_zero_denominators():
    result = marketing.marketing_summary([], [], [])
    assert result["ctr"] == 0
    assert result["cpl"] == 0
    assert result["conversion"] == 0
    assert result["roas"] == 0


def test_marketing_ai_workbench_is_registered_as_functional_module():
    assert ("Marketing", "src.marketing_ai_workbench", "render_marketing") in module_bootstrap.MODULE_RENDERERS


def test_marketing_has_its_own_navigation_area():
    groups = top_navigation_app.navigation_groups()
    assert groups["Marketing"] == ("Marketing",)


def test_marketing_taxonomies_cover_strategy_and_funnel():
    assert "Confianza/Prueba social" in marketing.PILLARS
    assert marketing.FUNNEL_STAGES == ("Descubrimiento", "Interés", "Consideración", "Conversión", "Fidelización")


def test_prompt_builder_uses_class_structure():
    prompt = marketing_ai_workbench.build_marketing_prompt("Estratega", "Crear plan", "10 piezas", "Negocio local")
    assert "ROL:\nEstratega" in prompt
    assert "TAREA:\nCrear plan" in prompt
    assert "FORMATO:\n10 piezas" in prompt
    assert "CONTEXTO:\nNegocio local" in prompt


def test_ai_matrix_keeps_human_control_for_high_risk_work():
    label, explanation = marketing_ai_workbench.ai_use_recommendation("Alto", "Alto")
    assert label == "Criterio humano primero"
    assert "IA solo como apoyo" in explanation
