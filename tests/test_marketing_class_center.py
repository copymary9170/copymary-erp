from src.marketing_class_center import (
    FUNNEL_STAGES,
    SECTIONS,
    content_metrics,
    funnel_stage_counts,
    marketing_diagnosis,
    normalized_stage,
)


def test_center_exposes_video_based_workflow():
    assert SECTIONS == (
        "Estrategia",
        "Buyer persona",
        "Pilares",
        "Contenido",
        "Calendario",
        "Embudo",
        "Campañas",
        "Métricas",
    )
    assert FUNNEL_STAGES == (
        "Reconocimiento",
        "Necesidad",
        "Solución",
        "Demostración",
        "Confianza",
        "CTA",
        "Lead",
        "Cliente",
    )


def test_legacy_funnel_stages_are_kept_compatible():
    assert normalized_stage({"funnel": "Descubrimiento"}) == "Reconocimiento"
    assert normalized_stage({"funnel": "Conversión"}) == "CTA"
    counts = funnel_stage_counts(
        [{"funnel": "Descubrimiento"}, {"funnel_stage": "Confianza"}],
        [{"stage": "Lead"}, {"stage": "Cliente"}],
    )
    assert counts["Reconocimiento"] == 1
    assert counts["Confianza"] == 1
    assert counts["Lead"] == 1
    assert counts["Cliente"] == 1


def test_content_metrics_calculate_conversion_and_roas():
    metrics = content_metrics([
        {
            "status": "Medido",
            "views": 1000,
            "interactions": 100,
            "clicks": 40,
            "leads": 10,
            "sales": 2,
            "revenue": 60,
            "spend": 20,
        }
    ])
    assert metrics["engagement"] == 10
    assert metrics["lead_conversion"] == 25
    assert metrics["sales_conversion"] == 20
    assert metrics["roas"] == 3


def test_diagnosis_detects_top_heavy_funnel():
    content = [
        {"funnel_stage": "Reconocimiento", "status": "Publicado"},
        {"funnel_stage": "Reconocimiento", "status": "Publicado"},
        {"funnel_stage": "Necesidad", "status": "Publicado"},
    ]
    messages = marketing_diagnosis(content)
    assert any("CTA" in message and "leads" in message for message in messages)
    assert any("no registran leads" in message for message in messages)
