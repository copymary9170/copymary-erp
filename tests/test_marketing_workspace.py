from src.marketing_workspace import CONTENT_STATUSES, FUNNEL_STAGES, marketing_health, next_action


def test_workspace_taxonomies_have_expected_flow():
    assert CONTENT_STATUSES[0] == "Idea"
    assert CONTENT_STATUSES[-1] == "Medido"
    assert "Conversión" in FUNNEL_STAGES


def test_marketing_health_returns_bounded_scores(monkeypatch):
    monkeypatch.setattr("src.marketing_workspace.read_list", lambda _key: [])
    scores = marketing_health()
    assert set(scores) == {"total", "strategy", "research", "content", "campaigns", "analytics"}
    assert all(0 <= value <= 100 for value in scores.values())


def test_next_action_prioritizes_strategy(monkeypatch):
    monkeypatch.setattr("src.marketing_workspace.marketing_health", lambda: {
        "total": 0, "strategy": 20, "research": 0, "content": 0, "campaigns": 0, "analytics": 0,
    })
    icon, message = next_action()
    assert icon == "🔴"
    assert "Plan de Marketing" in message
