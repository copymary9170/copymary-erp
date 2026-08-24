from src.marketing_meta_ads_execution import campaign_structure, structure_diagnostics, winner_score


def test_campaign_structure_counts_linked_sets_and_ads():
    adsets = [
        {"adset_id": "S1", "plan_id": "P1"},
        {"adset_id": "S2", "plan_id": "P1"},
        {"adset_id": "S3", "plan_id": "P2"},
    ]
    ads = [
        {"adset_id": "S1"}, {"adset_id": "S1"}, {"adset_id": "S2"}, {"adset_id": "S3"},
    ]
    assert campaign_structure("P1", adsets, ads) == {"adsets": 2, "ads": 3}


def test_structure_diagnostics_detects_weak_testing_structure():
    adsets = [{"adset_id": "S1", "plan_id": "P1", "name": "Público 1", "budget": 0}]
    ads = [{"adset_id": "S1", "name": "A1"}]
    messages = structure_diagnostics("P1", adsets, ads)
    assert any("menos de 2 conjuntos" in message for message in messages)
    assert any("menos de 2 creativos" in message for message in messages)
    assert any("sin presupuesto" in message for message in messages)


def test_winner_score_rewards_sales_and_leads():
    weak = {"ctr": 2, "cpc": 0.5, "leads": 1, "sales": 0}
    strong = {"ctr": 1.5, "cpc": 0.6, "leads": 3, "sales": 1}
    assert winner_score(strong) > winner_score(weak)
