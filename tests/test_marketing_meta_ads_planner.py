from src.marketing_meta_ads_planner import (
    estimated_budget,
    plan_diagnostics,
    preflight_score,
    recommended_objective,
)


def test_recommended_objective_connects_funnel_to_meta():
    assert recommended_objective("Reconocimiento") == "Reconocimiento"
    assert recommended_objective("CTA") == "Clientes potenciales"
    assert recommended_objective("Cliente") == "Ventas"


def test_estimated_budget_supports_daily_and_total_budget():
    assert estimated_budget("Diario", 5, 7) == 35
    assert estimated_budget("Total", 40, 7) == 40


def test_preflight_score_rewards_complete_plan():
    plan = {
        "name": "Campaña WhatsApp",
        "objective": "Clientes potenciales",
        "budget": 5,
        "location_include": "Caracas",
        "audience": "Público local amplio",
        "creative": "Reel producto",
        "copy": "Texto de anuncio",
        "cta": "Enviar mensaje",
        "destination": "WhatsApp",
        "success_metric": "20 conversaciones",
    }
    score, failures = preflight_score(plan)
    assert score == 100
    assert failures == []


def test_preflight_score_detects_missing_campaign_basics():
    score, failures = preflight_score({"objective": "Tráfico", "budget": 0})
    assert score < 50
    assert "Define un nombre de campaña." in failures
    assert "Asigna un presupuesto mayor que cero." in failures


def test_diagnostics_warns_about_conversion_and_ab_test():
    plan = {
        "objective": "Ventas",
        "audience_width": "Acotado",
        "ab_test": True,
        "ab_variable": "",
        "offer": "",
        "tracking": "",
        "audience_reason": "",
        "special_category": "Ninguna",
    }
    messages = plan_diagnostics(plan)
    assert any("atribuirá" in message for message in messages)
    assert any("oferta" in message for message in messages)
    assert any("prueba A/B" in message for message in messages)
