from src.marketing_growth_lab import smart_score, community_diagnosis


def test_complete_smart_goal_scores_100():
    score, failures = smart_score({
        "specific": "Conseguir consultas desde Instagram",
        "target": 20,
        "achievable": "Publicaré y responderé mensajes semanalmente",
        "relevant": "Genera oportunidades de venta",
        "deadline": "2026-09-30",
    })
    assert score == 100
    assert failures == []


def test_incomplete_smart_goal_is_flagged():
    score, failures = smart_score({"specific": "Crecer", "target": 0})
    assert score < 50
    assert any("medible" in item for item in failures)
    assert any("fecha" in item for item in failures)


def test_community_diagnosis_detects_followers_without_conversion():
    messages = community_diagnosis([
        {"stage": "Audiencia"},
        {"stage": "Comunidad"},
        {"stage": "Seguidores"},
    ])
    assert any("oportunidad comercial" in message for message in messages)


def test_community_diagnosis_promotes_advocacy_after_clients():
    messages = community_diagnosis([
        {"stage": "Clientes"},
    ])
    assert any("promotores" in message for message in messages)
