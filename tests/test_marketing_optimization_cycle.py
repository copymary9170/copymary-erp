"""Pruebas del ciclo de auditoría y aprendizaje de Marketing."""

from src.marketing_optimization_cycle import (
    audit_score,
    compare_content,
    content_balance,
    five_second_test,
    piece_metrics,
    priority_actions,
)


def test_audit_score_uses_only_evaluated_checks():
    audit = {
        "Perfil": {
            "Qué vende": "Correcto",
            "Para quién": "Mejorable",
            "Propuesta de valor": "Problema",
        }
    }
    result = audit_score(audit)
    assert result["evaluated"] == 3
    assert round(result["score"], 2) == 60.00
    assert round(result["areas"]["Perfil"], 2) == 60.00


def test_five_second_test_requires_core_offer_elements():
    audit = {
        "Perfil": {
            "Qué vende": "Correcto",
            "Para quién": "Correcto",
            "Propuesta de valor": "Mejorable",
            "CTA": "Problema",
        }
    }
    result = five_second_test(audit)
    assert result["passed"] is False
    assert result["score"] == 50.0
    assert "CTA" in result["problems"]


def test_content_balance_flags_excessive_direct_sales():
    content = [
        {"marketing_goal": "Vender"},
        {"marketing_goal": "Vender"},
        {"marketing_goal": "Vender"},
        {"marketing_goal": "Educar"},
    ]
    result = content_balance(content)
    assert result["counts"]["Vender"] == 3
    assert result["percentages"]["Vender"] == 75.0
    assert any("75%" in warning for warning in result["warnings"])
    assert any("atracción" in warning.lower() for warning in result["warnings"])


def test_piece_metrics_and_comparator_reward_real_outcomes():
    a = {
        "views": 1000,
        "interactions": 100,
        "clicks": 40,
        "leads": 5,
        "sales": 1,
        "revenue": 50,
        "spend": 25,
    }
    b = {
        "views": 800,
        "interactions": 90,
        "clicks": 50,
        "leads": 12,
        "sales": 4,
        "revenue": 160,
        "spend": 40,
    }
    metrics = piece_metrics(b)
    assert metrics["engagement"] == 11.25
    assert round(metrics["sales_rate"], 2) == 33.33
    assert metrics["roas"] == 4.0
    assert compare_content(a, b)["winner"] == "B"


def test_priority_actions_are_grounded_in_detected_problems():
    audit = {
        "Perfil": {
            "Qué vende": "Correcto",
            "Propuesta de valor": "Problema",
            "CTA": "Problema",
        }
    }
    content = [
        {"marketing_goal": "Vender"},
        {"marketing_goal": "Vender"},
        {"marketing_goal": "Vender"},
        {"marketing_goal": "Educar"},
    ]
    actions = priority_actions(audit, content)
    assert len(actions) == 3
    assert any("propuesta de valor" in action.lower() for action in actions)
    assert any("llamada a la acción" in action.lower() for action in actions)
    assert any("contenido" in action.lower() for action in actions)
